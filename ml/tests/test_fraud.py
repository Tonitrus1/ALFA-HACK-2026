import copy
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pyarrow.parquet as pq
import pytest

from scoring import fraud_data, fraud_features
from scoring.demo_policy import after_models, precheck
from scoring.features import digest, validate
from scoring.fraud_api import FraudRuntime
from scoring.fraud_train import select_threshold

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / 'ml/artifacts/fraud-demo-v1'


@pytest.fixture
def reference():
    return copy.deepcopy(json.loads((ROOT/'ml/fixtures/scenarios.json').read_text())['companies'][0]['reference'])


def test_features_have_no_ids_target_or_amount_and_handle_zero(reference):
    statement = copy.deepcopy(reference)
    statement['values']['revenueMinor'] += 100
    f = fraud_features.build(statement, reference)
    assert list(f) == fraud_features.FEATURES and len(f) == 16
    assert f['delta_revenueMinor'] > 0
    assert f['abs_delta_revenueMinor'] == f['delta_revenueMinor']
    reference['values']['netProfitMinor'] = 0
    assert np.isfinite(list(fraud_features.build(statement, reference).values())).all()
    for forbidden in ('target', 'companyId', 'split', 'family', 'amount'):
        assert not any(forbidden in name for name in f)


def test_generator_is_deterministic_valid_and_not_bankruptcy_target():
    rows, pairs = fraud_data.load_split(ROOT/'datasets/ru-sme-dataset-10000', 'validation')
    assert pairs[:7] == fraud_data.pairs_for_row(rows[0])
    assert {p['target'] for p in pairs} == {0, 1}
    assert {p['family'] for p in pairs}.isdisjoint({fraud_data.HELD_OUT_FAMILY})
    for pair in pairs:
        validate(pair['statement'])
        validate(pair['reference'])
    for label in (0, 1):
        assert any(p['target'] == label and fraud_features.build(p['statement'], p['reference'])['delta_revenueMinor'] > .1
                   and precheck(p['statement'], p['reference'], 20000000, 12) is None for p in pairs)


def test_artifacts_locked_before_test_and_companies_disjoint():
    manifest = json.loads((BUNDLE/'manifest.json').read_text())
    lock = json.loads((BUNDLE/'selection-lock.json').read_text())
    assert lock['testOpened'] is False  # state at the moment of selection lock
    assert lock['modelHash'] == manifest['artifacts']['model.joblib']
    assert lock['policyHash'] == manifest['artifacts']['policy.json']
    assert lock['featureCodeDigest'] == fraud_features.code_digest()
    assert lock['generatorDigest'] == fraud_data.code_digest()
    groups = []
    for split in ('train', 'validation', 'test'):
        data = pq.read_table(ROOT/'ml/experiments/fraud-demo-v1'/f'{split}.parquet', columns=['companyId', 'family'])
        ids = set(data['companyId'].to_pylist())
        groups.append(ids)
        assert fraud_data.HELD_OUT_FAMILY not in set(data['family'].to_pylist())
    assert not groups[0] & groups[1] and not groups[0] & groups[2] and not groups[1] & groups[2]
    assert groups[0] == set(lock['trainCompanies']) and groups[1] == set(lock['validationCompanies'])
    for name, expected in manifest['artifacts'].items():
        assert hashlib.sha256((BUNDLE/name).read_bytes()).hexdigest() == expected


def test_release_gate_and_honest_generalization_report():
    report = json.loads((BUNDLE/'evaluation.json').read_text())
    assert report['routingEnabled']
    for split in ('validation', 'test'):
        r = report[split]
        assert r['falsePositiveRate'] <= .05 and r['additionalBeyondCreditReview'] > 0
        assert r['manualRateAfter'] > r['manualRateBefore']
    # An unseen-family failure must remain visible; no assertion of generality.
    assert report['heldOutGeneralizationSupported'] == (report['heldOutAttackFamily']['recall'] > 0)


def test_threshold_ties_and_false_positive_budget():
    y = np.r_[np.zeros(200, dtype=int), np.ones(20, dtype=int)]
    scores = np.r_[np.full(200, .1), np.full(20, .8)]
    threshold = select_threshold(y, scores)
    assert threshold == .8
    with pytest.raises(ValueError):
        select_threshold(np.zeros(4), np.ones(4))


@pytest.mark.parametrize('risk,fraud,codes', [
    (.01, .1, ['WITHIN_DEMO_RULES']),
    (.05, .1, ['MODEL_REVIEW_BUDGET']),
    (.01, .9, ['SUSPECTED_FINANCIAL_MANIPULATION']),
    (.05, .9, ['SUSPECTED_FINANCIAL_MANIPULATION', 'MODEL_REVIEW_BUDGET']),
])
def test_dual_policy_independent_reasons(reference, risk, fraud, codes):
    r = after_models(reference, 20000000, risk, .04, fraud, .8)
    assert r['reasonCodes'] == codes
    assert r['outcome'] == ('APPROVED' if len(codes) == 1 and codes[0] == 'WITHIN_DEMO_RULES' else 'MANUAL')


@pytest.mark.parametrize('invalid', [None, float('nan'), float('inf'), -.1, 1.1, True, '0.1'])
def test_partial_success_never_approves(reference, invalid):
    assert after_models(reference, 20000000, .01, .04, invalid, .8)['rule'] == 'ML_FAILURE'
    assert after_models(reference, 20000000, invalid, .04, .1, .8)['rule'] == 'ML_FAILURE'


def test_fraud_precedes_alternative_and_equality_counts(reference):
    assert after_models(reference, 900000000, .01, .04, .8, .8)['rule'] == 'SUSPECTED_FINANCIAL_MANIPULATION'
    assert after_models(reference, 900000000, .04, .04, .1, .8)['rule'] == 'MODEL_REVIEW_BUDGET'
    assert after_models(reference, 900000000, .01, .04, .1, .8)['outcome'] == 'ALTERNATIVE'


def test_runtime_rejects_corrupt_bundle(tmp_path):
    import shutil
    path = tmp_path/'bundle'
    shutil.copytree(BUNDLE, path)
    risk_digest = json.loads((BUNDLE/'manifest.json').read_text())['riskBundleDigest']
    runtime = FraudRuntime(path)
    runtime.load(risk_digest)
    (path/'policy.json').write_text('{}')
    with pytest.raises(RuntimeError, match='checksum'):
        FraudRuntime(path).load(risk_digest)


def test_disabled_server_gate_requires_manual_without_touching_database():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pydantic import BaseModel
    from scoring.fraud_api import create_router

    class Empty(BaseModel):
        pass

    class Runtime:
        manifest = {'routingEnabled': False}

    def forbidden_db():
        raise AssertionError('Disabled model must not access DB or predict')

    app = FastAPI()
    app.include_router(create_router(forbidden_db, Empty, Empty, Runtime()))
    with TestClient(app) as client:
        response = client.post('/internal/v1/fraud/evaluations', json={
            'requestId': 'r', 'featureSnapshotId': 'f', 'featureSnapshotDigest': '0'*64,
            'bundleDigest': '0'*64, 'riskInferenceId': 'risk', 'purpose': 'DEMO_RESEARCH', 'featureSchemaVersion': 1})
    assert response.status_code == 503


def test_train_s05_examples_are_real_predictions_with_separate_targets():
    m = joblib.load(BUNDLE/'model.joblib')
    threshold = json.loads((BUNDLE/'policy.json').read_text())['T_fraud']
    examples = json.loads((BUNDLE/'scenario-fixtures.json').read_text())
    lock = json.loads((BUNDLE/'selection-lock.json').read_text())
    for case in examples['cases']:
        assert case['sourceCompanyId'] in lock['trainCompanies']
        assert float(m.predict_proba(fraud_features.matrix([case]))[0, 1]) >= threshold
