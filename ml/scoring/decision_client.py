"""Executable backend reference orchestration; no application/offer writes."""
import time
from uuid import uuid4

import requests

from .demo_policy import DUAL_VERSION, after_models, precheck
from .features import digest
from .fraud_features import SCORE_KIND


class DecisionClient:
    def __init__(self, risk_client, fraud_manifest, policy):
        self.client = risk_client
        self.fraud_manifest = fraud_manifest
        self.policy = policy
        if (fraud_manifest['riskBundleDigest'] != risk_client.bundle_digest
                or policy['riskBundleDigest'] != risk_client.bundle_digest
                or policy['version'] != DUAL_VERSION):
            raise ValueError('Decision models/policy releases are incompatible')

    def evaluate(self, snapshot_request, reference, reference_id, amount, term,
                 request_id=None, correction=False, explanation='', age=36,
                 product='working', reference_available_at='2026-04-01T00:00:00Z',
                 fault=None):
        """Caller persists these exact inputs/requestId for retries.

        fault is a test-client-only closed-port injection; never part of ML API.
        """
        started = time.monotonic()
        deadline = started + 3
        statement = snapshot_request['financialStatement']
        initial = precheck(statement, reference, amount, term, age, product, correction, explanation)
        if initial:
            return {'policy': {**initial, 'policyVersion': DUAL_VERSION, 'reasonCodes': [initial['rule']]},
                    'mlCalled': False, 'inference': None, 'fraudInference': None,
                    'snapshotRequest': snapshot_request, 'referenceSnapshotId': reference_id,
                    'referenceSnapshotDigest': digest(reference)}
        request_id = request_id or str(uuid4())
        evidence = {'mlCalled': True, 'requestId': request_id, 'snapshotRequest': snapshot_request,
                    'inference': None, 'fraudInference': None, 'failure': None}

        def call(path, body, fault_at=None):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Shared three-second decision deadline exceeded')
            response = self.client.call(path, body,
                base_url='http://127.0.0.1:1' if fault_at == fault and fault is not None else None,
                timeout=remaining)
            if time.monotonic() > deadline:
                raise TimeoutError('Late result after shared decision deadline')
            return response

        try:
            if not self.fraud_manifest['routingEnabled']:
                raise ValueError('Fraud release gate disabled')
            snapshot = call('/internal/v2/feature-snapshots', snapshot_request)
            evidence['snapshot'] = snapshot
            risk_request = self.client.risk_request(snapshot, request_id)
            evidence['riskRequest'] = risk_request
            risk = call('/internal/v2/risk/evaluations', risk_request, 'risk')
            evidence['inference'] = risk
            if (risk['requestId'] != request_id or risk['featureSnapshotId'] != snapshot['featureSnapshotId']
                    or risk['featureSnapshotDigest'] != snapshot['snapshotDigest']
                    or risk['bundleDigest'] != self.client.bundle_digest
                    or risk['scoreKind'] != 'BANKRUPTCY_PROXY'
                    or risk['purpose'] != 'DEMO_RESEARCH' or risk['calibrationStatus'] != 'DEMONSTRATION'):
                raise ValueError('Risk result does not match the pinned attempt')
            fraud_input = {**snapshot_request, 'riskFeatureSnapshotId': snapshot['featureSnapshotId'],
                           'referenceSnapshotId': reference_id, 'referenceSnapshotDigest': digest(reference),
                           'referenceAvailableAt': reference_available_at, 'referenceStatement': reference}
            evidence['fraudSnapshotRequest'] = fraud_input
            fraud_snapshot = call('/internal/v1/fraud/feature-snapshots', fraud_input)
            evidence['fraudSnapshot'] = fraud_snapshot
            fraud_request = {'requestId': request_id, 'featureSnapshotId': fraud_snapshot['featureSnapshotId'],
                             'featureSnapshotDigest': fraud_snapshot['snapshotDigest'],
                             'bundleDigest': self.fraud_manifest['bundleDigest'],
                             'riskInferenceId': risk['inferenceId'], 'purpose': 'DEMO_RESEARCH', 'featureSchemaVersion': 1}
            evidence['fraudRequest'] = fraud_request
            fraud = call('/internal/v1/fraud/evaluations', fraud_request, 'fraud')
            evidence['fraudInference'] = fraud
            expected = {'requestId': request_id, 'riskInferenceId': risk['inferenceId'],
                        'applicationId': snapshot_request['applicationId'],
                        'submissionSnapshotId': snapshot_request['submissionSnapshotId'],
                        'financialSnapshotDigest': snapshot_request['financialSnapshotDigest'],
                        'referenceSnapshotId': reference_id, 'referenceSnapshotDigest': digest(reference),
                        'riskFeatureSnapshotId': snapshot['featureSnapshotId'],
                        'featureSnapshotId': fraud_snapshot['featureSnapshotId'],
                        'featureSnapshotDigest': fraud_snapshot['snapshotDigest'],
                        'bundleDigest': self.fraud_manifest['bundleDigest'],
                        'modelVersion': self.fraud_manifest['modelVersion'],
                        'riskBundleDigest': self.client.bundle_digest, 'scoreKind': SCORE_KIND,
                        'purpose': 'DEMO_RESEARCH', 'calibrationStatus': 'DEMONSTRATION'}
            if any(fraud.get(key) != value for key, value in expected.items()):
                raise ValueError('Fraud result does not match the pinned attempt/reference/release')
            decision = after_models(statement, amount, risk['score'], self.policy['T_manual'],
                                    fraud['score'], self.policy['T_fraud'], product)
        except (requests.RequestException, TimeoutError, ValueError, KeyError, TypeError) as exc:
            evidence['failure'] = type(exc).__name__ + ': ' + str(exc).split('\n')[0][:160]
            decision = after_models(statement, amount, None, self.policy['T_manual'], None,
                                    self.policy['T_fraud'], product, ml_error=True)
        evidence.update({'policy': decision, 'seconds': time.monotonic() - started,
                         'riskBundleDigest': self.client.bundle_digest,
                         'fraudBundleDigest': self.fraud_manifest['bundleDigest']})
        return evidence
