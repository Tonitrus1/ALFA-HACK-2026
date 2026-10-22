import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from jsonschema import Draft202012Validator, FormatChecker

from ml.feed.catalog import Catalog, digest, file_digest
from ml.feed.dataset import load_manifest, rows, write_json
from ml.feed.features import CATEGORICAL, NAMES, FeatureBuilder
from ml.feed.metrics import clustered_interval, quality
from ml.feed.simulate import generate
from ml.feed.train_ranker import observed_labels, training_pools
from ml.feed.validate_data import validate


@pytest.fixture
def config():
    value = json.loads(Path('ml/feed/simulation.json').read_text())
    return value | {'users': 40, 'sessions': 2, 'pages': 2}


@pytest.fixture
def data(tmp_path, config):
    path = tmp_path / 'simulation'
    generate(path, config)
    return path


def rewrite(data, name, change):
    table = pq.read_table(data / name)
    values = table.to_pylist()
    change(values)
    pq.write_table(pa.Table.from_pylist(values, schema=table.schema), data / name, compression='zstd')
    manifest = json.loads((data / 'manifest.json').read_text())
    manifest['files'][name] = file_digest(data / name)
    write_json(data / 'manifest.json', manifest)


def test_reproducible_data_and_disjoint_splits(tmp_path, config):
    a, b = tmp_path / 'a', tmp_path / 'b'
    first, second = generate(a, config), generate(b, config)
    assert first == second
    report = validate(a)
    assert report['valid'] and report['contexts'] == 40
    assert report['splits'] == {'train': 28, 'validation': 6, 'test': 6}
    with pytest.raises(FileExistsError):
        generate(a, config)


def test_observable_export_matches_strict_contract(data):
    schema = json.loads(Path('ml/feed/analytics.schema.json').read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for name in ('requests.parquet','issued.parquet','events.parquet'):
        for record in rows(data, name):
            validator.validate(record)


def test_checksum_and_truth_isolation(data):
    (data / 'private/truth.parquet').write_bytes(b'private oracle intentionally unavailable')
    assert validate(data)['valid']
    with pytest.raises(ValueError, match='checksum'):
        load_manifest(data, truth=True)
    (data / 'events.parquet').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='checksum'):
        validate(data)


def test_reject_future_reaction_snapshot(data):
    def change(records):
        value = json.loads(records[0]['requestJson'])
        value['topicReactions'] = {'CASH_GAP': {'helpful': 99, 'notInterested': 0}}
        records[0]['requestJson'] = json.dumps(value)
    rewrite(data, 'requests.parquet', change)
    with pytest.raises(ValueError, match='snapshot'):
        validate(data)


@pytest.mark.parametrize('defect', ['foreign_context', 'unissued', 'duplicate', 'visibility', 'timestamp'])
def test_reject_broken_event_lineage(data, defect):
    def change(records):
        if defect == 'foreign_context': records[0]['companyId'] = 'SIM-FOREIGN'
        elif defect == 'unissued': records[0]['itemId'] = 'not-issued'
        elif defect == 'duplicate': records[1]['clientEventId'] = records[0]['clientEventId']
        elif defect == 'visibility': records[0]['visibleMs'] = 999
        elif defect == 'timestamp': records[0]['occurredAt'] = '2020-01-01T00:00:00+00:00'
    rewrite(data, 'events.parquet', change)
    with pytest.raises(ValueError):
        validate(data)


def test_reject_cross_split_context(data):
    def change(records):
        records[1]['split'] = 'test' if records[0]['split'] != 'test' else 'train'
    rewrite(data, 'requests.parquet', change)
    with pytest.raises(ValueError, match='splits'):
        validate(data)


@pytest.mark.parametrize('defect', ['range', 'non_finite', 'non_view_visibility', 'naive_timestamp', 'extra_field', 'missing_field'])
def test_validator_rejects_analytics_schema_violations(data, defect):
    def change(records):
        view = next(e for e in records if e['action'] == 'VIEW')
        if defect == 'range':
            view['visibleFraction'] = 99.0
        elif defect == 'non_finite':
            view['visibleFraction'] = float('nan')
        elif defect == 'non_view_visibility':
            next(e for e in records if e['action'] != 'VIEW')['visibleMs'] = 1200
        elif defect == 'naive_timestamp':
            view['occurredAt'] = '2026-10-01T00:00:00'
        elif defect == 'extra_field':
            for event in records:
                event['unexpected'] = 'not-in-contract'
        else:
            for event in records:
                del event['visibleMs']
    if defect in ('extra_field', 'missing_field'):
        # Preserve the altered column inventory rather than coercing to the original schema.
        records = list(rows(data, 'events.parquet'))
        change(records)
        pq.write_table(pa.Table.from_pylist(records), data / 'events.parquet')
        manifest = json.loads((data / 'manifest.json').read_text())
        manifest['files']['events.parquet'] = file_digest(data / 'events.parquet')
        write_json(data / 'manifest.json', manifest)
    else:
        rewrite(data, 'events.parquet', change)
    with pytest.raises(ValueError, match='Invalid analytics record'):
        validate(data)


def test_event_ids_are_scoped_to_subject_company(data):
    def change(records):
        first = records[0]
        other = next(e for e in records if (e['subjectId'], e['companyId']) !=
                     (first['subjectId'], first['companyId']))
        other['clientEventId'] = first['clientEventId']
    rewrite(data, 'events.parquet', change)
    assert validate(data)['valid']


def test_both_catalog_versions_and_original_content(catalog):
    original = Catalog(Path('ml/feed/catalog/versions/v1/cards.json'))
    assert original.validate_editorial()['cards'] == 36
    original.validate_publication()
    assert catalog.validate_editorial()['cards'] == 72
    assert all(catalog.cards[i] == card for i, card in original.cards.items())
    assert {(c.topic, c.businessCategories[0]) for i, c in catalog.cards.items() if i not in original.cards} == {
        (topic, business) for topic in {c.topic for c in catalog.cards.values()}
        for business in ('RETAIL','SERVICES','MANUFACTURING','WHOLESALE','HOSPITALITY','OTHER')}


class FakeSemantic:
    def __init__(self, catalog):
        self.catalog = catalog
        self.vectors = {i: np.ones(384, dtype=np.float32) / np.sqrt(384) for i in catalog.cards}
        self.encoder = self

    def encode(self, texts):
        return np.ones((len(texts), 384), dtype=np.float32) / np.sqrt(384)


def test_feature_allowlist_and_training_serving_parity(catalog, request_body):
    builder = FeatureBuilder(FakeSemantic(catalog))
    full = builder.rows(request_body)
    ids = request_body.candidateIds[::3]
    subset = builder.rows(request_body.model_copy(update={'candidateIds': ids}))
    assert subset == [full[request_body.candidateIds.index(i)] for i in ids]
    assert len(full[0]) == len(NAMES)
    assert not {'subjectId','companyId','itemId','position','utilities','latentJson'} & set(NAMES)
    assert set(CATEGORICAL) <= set(NAMES)
    assert all(np.isfinite(row[len(CATEGORICAL):]).all() for row in full)


def test_training_does_not_read_private_truth_or_select_on_test(data, catalog):
    import ml.feed.train_ranker as module
    original_rows = module.rows
    def guarded(root, name):
        assert name != 'private/truth.parquet'
        yield from original_rows(root, name)
    (data / 'private/truth.parquet').write_bytes(b'not training data')
    with patch.object(module, 'rows', guarded):
        pools, counts = training_pools(data, FeatureBuilder(FakeSemantic(catalog)))
    assert set(pools) == {'train','validation'}
    assert counts['train_rows'] > 0 and counts['validation_rows'] > 0


def test_labels_ignore_views_and_replace_reactions(data):
    labels = observed_labels(data)
    by_group = {}
    for event in rows(data, 'events.parquet'):
        by_group.setdefault(event['exposureId'], []).append(event)
    for ex, events in by_group.items():
        for item in {e['itemId'] for e in events}:
            actions = [e['action'] for e in events if e['itemId'] == item]
            explicit = [a for a in actions if a in ('HELPFUL','NOT_INTERESTED')]
            expected = (2 if explicit[-1] == 'HELPFUL' else 0) if explicit else (1 if 'CLICK' in actions else None)
            assert labels[ex].get(item) == expected


def test_metrics_known_order_and_cluster_interval():
    relevant = {'a':3,'b':2,'c':1,'d':0,'e':0,'f':0}
    perfect = quality(list(relevant), relevant)
    assert perfect['ndcg6'] == 1 and perfect['recall6'] == 1
    assert quality(list(reversed(relevant)), relevant)['ndcg6'] < 1
    assert clustered_interval([.1] * 10) == pytest.approx([.1,.1])


def test_no_manual_boosts_on_learned_path(catalog, request_body):
    from ml.feed.ranker import RulesRanker
    body = request_body.model_copy(update={'topicReactions': {}})
    scores = {i: float(j) for j, i in enumerate(body.candidateIds)}
    untouched = dict(scores)
    result = RulesRanker(catalog).result(body, scores, 'MODEL', 'unit-learned', adjustments=False)
    assert scores == untouched
    assert set(result.rankedIds) == set(body.candidateIds)


def test_unknown_ranker_configuration(monkeypatch):
    from ml.feed.server import create_app
    monkeypatch.setenv('FEED_RANKER', 'unknown')
    with pytest.raises(RuntimeError, match='FEED_RANKER'):
        create_app(token='test-internal-service-token')


def test_ai_review_cannot_pass_promotion_gate(catalog):
    from ml.feed.benchmark import content_review
    from types import SimpleNamespace
    import ml.feed.benchmark as module
    fake = SimpleNamespace(catalog=catalog)
    order = sorted(catalog.cards)
    with patch.object(module, 'orders', lambda *a: {n:(order,order) for n in module.ALGORITHMS}):
        result = content_review(fake, Path('ml/feed/fixtures/content-review.json'))
    assert result['status'] == 'pending_human_review' and not result['passed']
