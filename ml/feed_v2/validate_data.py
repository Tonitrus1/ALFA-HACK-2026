"""Replay the observable log to detect leakage, broken lineage and invalid feedback."""
import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .backend_reference import FeedbackProjection
from .catalog import Catalog
from .dataset import load_manifest, rows, write_json
from .integration import eligible_ids
from .ranker import validate_request
from .schemas import RankingRequest


def record_validators():
    schema = json.loads(Path(__file__).with_name('analytics.schema.json').read_text())
    return {name: Draft202012Validator(
        {'$ref': '#/$defs/' + definition, '$defs': schema['$defs']},
        format_checker=FormatChecker())
        for name, definition in [('requests.parquet', 'RequestSnapshot'),
                                 ('issued.parquet', 'IssuedItem'),
                                 ('events.parquet', 'AcceptedEvent')]}


def checked_rows(root, name, validator):
    for row in rows(root, name):
        error = next(validator.iter_errors(row), None)
        if error is not None:
            location = '.'.join(map(str, error.absolute_path)) or '<record>'
            raise ValueError(f'Invalid analytics record in {name}: {location}')
        if name == 'events.parquet' and not math.isfinite(row['visibleFraction']):
            raise ValueError('Invalid analytics record: non-finite visibleFraction')
        yield row


def validate(root):
    manifest = load_manifest(root)
    validators = record_validators()
    catalog = Catalog()
    if manifest['catalogDigest'] != catalog.digest or manifest['catalogVersion'] != catalog.version:
        raise ValueError('Dataset/catalog mismatch')
    issued, events = defaultdict(list), defaultdict(list)
    for name, grouped in [('issued.parquet', issued), ('events.parquet', events)]:
        count = 0
        for row in checked_rows(root, name, validators[name]):
            if row['isSynthetic'] is not True:
                raise ValueError('Mixed provenance')
            grouped[row['exposureId']].append(row)
            count += 1
        if count != manifest['counts'][name]:
            raise ValueError('Count mismatch: ' + name)
    exposure_ids, event_ids = set(), set()
    subject_splits, company_splits = {}, {}
    states, sessions, sent, previous_time, previous_order = {}, {}, {}, {}, {}
    requests = 0
    labels = defaultdict(int)
    for row in checked_rows(root, 'requests.parquet', validators['requests.parquet']):
        requests += 1
        if row['isSynthetic'] is not True or row['split'] not in ('train', 'validation', 'test'):
            raise ValueError('Invalid request provenance/split')
        context = (row['subjectId'], row['companyId'])
        for mapping, key in ((subject_splits, context[0]), (company_splits, context[1])):
            if mapping.setdefault(key, row['split']) != row['split']:
                raise ValueError('Context crosses dataset splits')
        request = RankingRequest.model_validate_json(row['requestJson'])
        validate_request(catalog, request)
        ex = row['exposureId']
        if request.exposureId != ex or ex in exposure_ids:
            raise ValueError('Invalid/duplicate exposure identity')
        exposure_ids.add(ex)
        state = states.setdefault(context, FeedbackProjection(catalog))
        at = datetime.fromisoformat(row['requestedAt'])
        if at <= previous_time.get(context, datetime.min.replace(tzinfo=at.tzinfo)):
            raise ValueError('Non-increasing request timestamp or future-event leakage')
        if sessions.get(context) != row['sessionId']:
            sessions[context], sent[context] = row['sessionId'], set()
        if set(request.candidateIds) != set(eligible_ids(catalog, viewed=state.viewed,
                hidden=state.hidden, issued=sent[context])):
            raise ValueError('Eligibility mismatch or future history')
        snapshot = {k.value: v.model_dump() for k, v in request.topicReactions.items()}
        if snapshot != state.topic_reactions:
            raise ValueError('Reaction snapshot contains future/missing events')
        page = sorted(issued.get(ex, []), key=lambda i: i['position'])
        if not 1 <= len(page) <= 6 or [i['position'] for i in page] != list(range(1, len(page) + 1)):
            raise ValueError('Invalid page positions/size')
        if len({i['itemId'] for i in page}) != len(page):
            raise ValueError('Duplicate issued item')
        for i in page:
            if ((i['subjectId'], i['companyId']) != context or i['split'] != row['split']
                    or i['sessionId'] != row['sessionId'] or i['itemId'] not in request.candidateIds
                    or i['cardVersion'] != catalog.cards[i['itemId']].version
                    or i['issuedAt'] != row['requestedAt']):
                raise ValueError('Issued item lineage mismatch')
        state.issue(ex, [i['itemId'] for i in page])
        sent[context].update(i['itemId'] for i in page)
        for event in events.get(ex, []):
            if (event['subjectId'], event['companyId']) != context or event['split'] != row['split'] or event['sessionId'] != row['sessionId']:
                raise ValueError('Foreign feedback context')
            event_at, accepted_at = map(datetime.fromisoformat, (event['occurredAt'], event['acceptedAt']))
            if not at <= event_at <= accepted_at or event['acceptedOrder'] <= previous_order.get(context, 0):
                raise ValueError('Invalid event timestamp/server order')
            event_key = (*context, event['clientEventId'])
            if event_key in event_ids:
                raise ValueError('Duplicate accepted event')
            event_ids.add(event_key)
            payload = {k: event[k] for k in ('clientEventId', 'itemId', 'exposureId', 'action', 'occurredAt')}
            state.apply(payload, visible_fraction=event['visibleFraction'], visible_ms=event['visibleMs'])
            previous_order[context] = event['acceptedOrder']
            previous_time[context] = max(previous_time.get(context, at), accepted_at)
            labels[event['action']] += 1
        previous_time[context] = max(previous_time.get(context, at), at)
    if (set(issued) - exposure_ids or set(events) - exposure_ids
            or requests != manifest['counts']['requests.parquet']):
        raise ValueError('Orphan event/issued row or request count mismatch')
    if len(subject_splits) != manifest['config']['users']:
        raise ValueError('Missing contexts')
    return dict(valid=True, isSynthetic=True, requests=requests, contexts=len(states),
                events=len(event_ids), actions=dict(labels),
                splits={s: sum(v == s for v in subject_splits.values()) for s in ('train','validation','test')},
                checks=['checksums','analytics_schema','context_disjoint_splits','exposure_membership','versions',
                        'positions','event_id_uniqueness','timestamps','eligibility_replay','point_in_time_reactions'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('reports/hackathon/data-validation.json'))
    args = parser.parse_args()
    report = validate(args.data)
    write_json(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
