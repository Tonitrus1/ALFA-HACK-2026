"""Internal-only fraud API, bound to an exact persisted risk attempt."""
import hashlib
import importlib.metadata
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

import joblib
import numpy as np
from fastapi import APIRouter, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, create_model

from . import fraud_features
from .features import digest


def fail(status, message):
    raise HTTPException(status, message)


def check_time(value, as_of, period_end):
    available = datetime.fromisoformat(value.replace('Z', '+00:00'))
    moment = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
    if (available.tzinfo is None or moment.tzinfo is None or available > moment
            or available.date() <= datetime.fromisoformat(period_end).date()):
        raise ValueError('Source/report/asOf chronology invalid')


class FraudRuntime:
    def __init__(self, path):
        self.path = Path(path)
        self.manifest = self.policy = self.model = None

    def load(self, risk_bundle_digest):
        manifest = json.loads((self.path / 'manifest.json').read_text())
        claimed = manifest.pop('bundleDigest')
        if digest(manifest) != claimed or manifest['featureCodeDigest'] != fraud_features.code_digest():
            raise RuntimeError('Fraud bundle/feature code integrity mismatch')
        if (manifest['scoreKind'], manifest['validationStatus'], manifest['purpose']) != (
                fraud_features.SCORE_KIND, 'DEMONSTRATION', 'DEMO_RESEARCH'):
            raise RuntimeError('Unsupported fraud interpretation')
        if manifest['features'] != fraud_features.FEATURES or manifest['riskBundleDigest'] != risk_bundle_digest:
            raise RuntimeError('Fraud feature schema/risk bundle mismatch')
        for name, expected in manifest['artifacts'].items():
            if Path(name).name != name or hashlib.sha256((self.path / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError('Fraud artifact checksum mismatch: ' + name)
        for name, expected in manifest['libraries'].items():
            if importlib.metadata.version(name) != expected:
                raise RuntimeError('Fraud library version mismatch: ' + name)
        policy = json.loads((self.path / 'policy.json').read_text())
        evaluation = json.loads((self.path / 'evaluation.json').read_text())
        if (policy['riskBundleDigest'] != risk_bundle_digest or not math.isfinite(policy['T_fraud'])
                or not 0 <= policy['T_fraud'] <= 1
                or manifest['routingEnabled'] != evaluation['routingEnabled']):
            raise RuntimeError('Invalid fraud policy/gate')
        manifest['bundleDigest'] = claimed
        self.manifest, self.policy = manifest, policy
        self.model = joblib.load(self.path / 'model.joblib')
        self.model.predict_proba(np.zeros((1, len(fraud_features.FEATURES))))


def create_router(db, feature_input_cls, financial_input_cls, runtime):
    router = APIRouter(prefix='/internal/v1/fraud', tags=['Demonstration manipulation proxy'])

    class FraudFeatureInput(feature_input_cls):
        riskFeatureSnapshotId: str = Field(min_length=1, max_length=128)
        referenceSnapshotId: str = Field(min_length=1, max_length=128)
        referenceSnapshotDigest: str = Field(pattern='^[0-9a-f]{64}$')
        referenceAvailableAt: str
        referenceStatement: financial_input_cls

    class FraudRequest(BaseModel):
        model_config = ConfigDict(extra='forbid')
        requestId: str = Field(min_length=1, max_length=128)
        featureSnapshotId: str = Field(min_length=1, max_length=128)
        featureSnapshotDigest: str = Field(pattern='^[0-9a-f]{64}$')
        bundleDigest: str = Field(pattern='^[0-9a-f]{64}$')
        riskInferenceId: str = Field(min_length=1, max_length=128)
        purpose: Literal['DEMO_RESEARCH']
        featureSchemaVersion: Literal[1]

    features_cls = create_model('FraudFeatures', __config__=ConfigDict(extra='forbid'),
                                **{key: (float, ...) for key in fraud_features.FEATURES})

    class FraudSnapshot(FraudFeatureInput):
        featureSnapshotId: str
        featureSchemaVersion: Literal[1]
        featureCodeDigest: str
        features: features_cls
        snapshotDigest: str

    class FraudResult(BaseModel):
        model_config = ConfigDict(extra='forbid')
        requestId: str
        riskInferenceId: str
        inferenceId: str
        applicationId: str
        submissionSnapshotId: str
        financialSnapshotDigest: str
        referenceSnapshotId: str
        referenceSnapshotDigest: str
        riskFeatureSnapshotId: str
        featureSnapshotId: str
        featureSnapshotDigest: str
        modelVersion: str
        bundleDigest: str
        riskBundleDigest: str
        score: float = Field(ge=0, le=1, allow_inf_nan=False)
        scoreKind: Literal['SYNTHETIC_MANIPULATION_PROXY']
        calibrationStatus: Literal['DEMONSTRATION']
        purpose: Literal['DEMO_RESEARCH']

    @router.get('/bundle')
    def bundle():
        return {'manifest': runtime.manifest, 'policy': runtime.policy}

    @router.post('/feature-snapshots', response_model=FraudSnapshot)
    def create_snapshot(body: FraudFeatureInput):
        body = body.model_dump()
        base = {key: body[key] for key in feature_input_cls.model_fields}
        if digest(body['financialStatement']) != body['financialSnapshotDigest']:
            fail(409, 'Declared financial digest mismatch')
        if digest(body['referenceStatement']) != body['referenceSnapshotDigest']:
            fail(409, 'Reference financial digest mismatch')
        try:
            for value, statement in [(body['latestSourceAvailableAt'], body['financialStatement']),
                                     (body['referenceAvailableAt'], body['referenceStatement'])]:
                check_time(value, body['asOf'], statement['periodEnd'])
            features = fraud_features.build(body['financialStatement'], body['referenceStatement'])
        except (ValueError, KeyError, TypeError) as exc:
            fail(422, str(exc))
        identity = body['submissionSnapshotId'] + ':' + runtime.manifest['featureCodeDigest']
        input_hash = digest(body)
        with db() as connection:
            connection.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))', ('fraud:' + identity,))
            risk = connection.execute('select * from ml.features where id=%s', (body['riskFeatureSnapshotId'],)).fetchone()
            if not risk:
                fail(404, 'Unknown risk feature snapshot')
            # Includes applicationId/asOf and exact original declared values.
            if risk['input_hash'] != digest(base):
                fail(409, 'Fraud and risk snapshots belong to different inputs/attempts')
            old = connection.execute('select * from ml.fraud_features where identity=%s', (identity,)).fetchone()
            if old:
                if old['input_hash'] != input_hash:
                    fail(409, 'Fraud snapshot identity reused with different reference/input')
                return old['payload']
            snapshot = {key: body[key] for key in (
                'applicationId', 'submissionSnapshotId', 'financialSnapshotId', 'financialSnapshotDigest',
                'financialStatementVersion', 'asOf', 'latestSourceAvailableAt', 'riskFeatureSnapshotId', 'purpose',
                'referenceSnapshotId', 'referenceSnapshotDigest', 'referenceAvailableAt',
                'financialStatement', 'referenceStatement')}
            snapshot.update({'featureSnapshotId': str(uuid4()), 'featureSchemaVersion': 1,
                             'featureCodeDigest': runtime.manifest['featureCodeDigest'], 'features': features})
            snapshot['snapshotDigest'] = digest(snapshot)
            connection.execute('insert into ml.fraud_features(id,identity,input_hash,payload) values(%s,%s,%s,%s)',
                               (snapshot['featureSnapshotId'], identity, input_hash, Jsonb(snapshot)))
        return snapshot

    @router.get('/feature-snapshots/{snapshot_id}', response_model=FraudSnapshot)
    def get_snapshot(snapshot_id: str):
        with db() as connection:
            row = connection.execute('select payload from ml.fraud_features where id=%s', (snapshot_id,)).fetchone()
        if not row:
            fail(404, 'Unknown fraud feature snapshot')
        return row['payload']

    @router.post('/evaluations', response_model=FraudResult)
    def evaluate(body: FraudRequest):
        body = body.model_dump()
        if not runtime.manifest['routingEnabled']:
            fail(503, 'Fraud model failed release gate; manual review required')
        if body['bundleDigest'] != runtime.manifest['bundleDigest']:
            fail(409, 'Fraud bundle mismatch')
        input_hash = digest(body)
        with db() as connection:
            connection.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))', ('fraud:' + body['requestId'],))
            old = connection.execute('select * from ml.fraud_inferences where request_id=%s', (body['requestId'],)).fetchone()
            if old:
                if old['input_hash'] != input_hash:
                    fail(409, 'Fraud requestId reused with different input')
                return old['payload']
            row = connection.execute('select payload from ml.fraud_features where id=%s', (body['featureSnapshotId'],)).fetchone()
            if not row:
                fail(404, 'Unknown fraud feature snapshot')
            snapshot = row['payload']
            check = dict(snapshot)
            check.pop('snapshotDigest')
            if (digest(check) != snapshot['snapshotDigest'] or snapshot['snapshotDigest'] != body['featureSnapshotDigest']
                    or snapshot['featureCodeDigest'] != runtime.manifest['featureCodeDigest']):
                fail(409, 'Fraud snapshot integrity mismatch')
            risk = connection.execute('select payload from ml.inferences where id=%s', (body['riskInferenceId'],)).fetchone()
            if not risk:
                fail(404, 'Unknown persisted risk inference')
            risk = risk['payload']
            if (risk['requestId'] != body['requestId'] or risk['featureSnapshotId'] != snapshot['riskFeatureSnapshotId']
                    or risk['bundleDigest'] != runtime.manifest['riskBundleDigest']):
                fail(409, 'Fraud and risk inferences belong to different attempts/releases')
            vector = np.array([[snapshot['features'][key] for key in fraud_features.FEATURES]])
            score = float(runtime.model.predict_proba(vector)[0, 1])
            if not math.isfinite(score) or not 0 <= score <= 1:
                fail(503, 'Invalid fraud model output')
            result = {key: snapshot[key] for key in (
                'submissionSnapshotId', 'applicationId', 'financialSnapshotDigest',
                'referenceSnapshotId', 'referenceSnapshotDigest', 'riskFeatureSnapshotId')}
            result.update({'requestId': body['requestId'], 'riskInferenceId': body['riskInferenceId'],
                           'inferenceId': str(uuid4()), 'featureSnapshotId': snapshot['featureSnapshotId'],
                           'featureSnapshotDigest': snapshot['snapshotDigest'], 'score': score,
                           'scoreKind': fraud_features.SCORE_KIND, 'calibrationStatus': 'DEMONSTRATION',
                           'purpose': 'DEMO_RESEARCH', 'modelVersion': runtime.manifest['modelVersion'],
                           'bundleDigest': runtime.manifest['bundleDigest'],
                           'riskBundleDigest': runtime.manifest['riskBundleDigest']})
            connection.execute('insert into ml.fraud_inferences(id,request_id,input_hash,payload) values(%s,%s,%s,%s)',
                               (result['inferenceId'], body['requestId'], input_hash, Jsonb(result)))
        return result

    return router
