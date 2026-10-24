"""Restart, durability, real DB failure and immutable-record checks on own demo DB."""
import hashlib
import json
import os
import subprocess
import time
from uuid import uuid4

import psycopg
from psycopg import sql

from ml_manage import ROOT, admin, down, env, up
from scoring.client import RiskClient
from scoring.decision_client import DecisionClient


def main():
    environment = env()
    risk = json.loads((ROOT/'ml/artifacts/baseline/manifest.json').read_text())
    fraud = json.loads((ROOT/'ml/artifacts/fraud-demo-v1/manifest.json').read_text())
    policy = json.loads((ROOT/'ml/artifacts/fraud-demo-v1/policy.json').read_text())
    client = RiskClient(environment['ML_API_URL'], environment['ML_INTERNAL_TOKEN'], risk['bundleDigest'])
    decision = DecisionClient(client, fraud, policy)
    statement = json.loads((ROOT/'ml/fixtures/scenarios.json').read_text())['companies'][0]['reference']
    body = client.snapshot_request(statement)
    reference_id, request_id = str(uuid4()), str(uuid4())
    before = decision.evaluate(body, statement, reference_id, 20000000, 12, request_id=request_id)
    assert before['policy']['outcome'] == 'APPROVED' and before['failure'] is None
    down()
    up(True)
    after = decision.evaluate(body, statement, reference_id, 20000000, 12, request_id=request_id)
    assert after['inference'] == before['inference'] and after['fraudInference'] == before['fraudInference']
    assert after['snapshot'] == before['snapshot'] and after['fraudSnapshot'] == before['fraudSnapshot']
    checks = [{'name': 'restart_preserves_both_exact_model_results_and_snapshots', 'passed': True}]
    for table in ('inferences', 'fraud_inferences'):
        body = client.snapshot_request(statement)
        rid, refid = str(uuid4()), str(uuid4())
        with admin() as connection:
            connection.execute('begin')
            connection.execute(sql.SQL('lock ml.{} in access exclusive mode').format(sql.Identifier(table)))
            started = time.monotonic()
            try:
                result = decision.evaluate(body, statement, refid, 20000000, 12, request_id=rid)
                elapsed = time.monotonic() - started
                assert result['policy']['rule'] == 'ML_FAILURE' and elapsed < 3.5
                assert result['inference' if table == 'inferences' else 'fraudInference'] is None
            finally:
                connection.execute('rollback')
            count = connection.execute(sql.SQL('select count(*) from ml.{} where request_id=%s').format(sql.Identifier(table)), (rid,)).fetchone()[0]
            assert count == 0, 'Successful inference must not be fabricated on persistence failure'
        recovered = decision.evaluate(body, statement, refid, 20000000, 12, request_id=rid)
        assert recovered['policy']['outcome'] == 'APPROVED' and recovered['failure'] is None
        checks.append({'name': 'durability_failure_'+table+'_falls_back_then_recovers', 'passed': True, 'seconds': elapsed})
    for table in ('fraud_features', 'fraud_inferences'):
        for operation in ('update', 'delete'):
            with admin() as connection:
                query = ('update ml.{} set payload=payload' if operation == 'update' else 'delete from ml.{}')
                try:
                    connection.execute(sql.SQL(query).format(sql.Identifier(table)))
                except psycopg.errors.RaiseException as exc:
                    assert 'immutable ML record' in str(exc)
                else:
                    raise AssertionError('Immutable fraud record changed')
        with psycopg.connect(environment['ML_DATABASE_URL']) as connection:
            try:
                connection.execute(sql.SQL('update ml.{} set payload=payload').format(sql.Identifier(table)))
            except psycopg.errors.InsufficientPrivilege:
                pass
            else:
                raise AssertionError('Runtime role must not update records')
    checks.append({'name': 'fraud_records_immutable_and_runtime_insert_select_only', 'passed': True})
    baseline_hashes = {}
    for path in (ROOT/'ml/artifacts/baseline').iterdir():
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        original = subprocess.check_output(['git', 'show', 'HEAD:'+relative], cwd=ROOT)
        assert original == path.read_bytes(), 'Credit baseline changed: '+relative
        baseline_hashes[path.name] = hashlib.sha256(original).hexdigest()
    checks.append({'name': 'every_credit_baseline_artifact_byte_identical_to_git_HEAD', 'passed': True})
    external = subprocess.run(['/usr/bin/sandbox-exec', '-f', str(ROOT/'scripts/offline.sb'),
        str(ROOT/'.venv/bin/python'), '-c', "import socket; socket.create_connection(('1.1.1.1',443),timeout=1)"],
        capture_output=True, text=True)
    assert external.returncode != 0 and 'Operation not permitted' in external.stderr
    checks.append({'name': 'external_network_denied_by_os_profile', 'passed': True})
    report = {'passed': True, 'scope': 'Own isolated local two-model demo API/PostgreSQL',
              'checks': checks, 'riskBundleDigest': risk['bundleDigest'], 'fraudBundleDigest': fraud['bundleDigest'],
              'baselineHashes': baseline_hashes, 'apiUrl': environment['ML_API_URL']}
    (ROOT/'reports/dual-model-runtime.json').write_text(json.dumps(report, indent=2)+'\n')
    # The runtime contract is additive; the original risk operations are retained.
    openapi = client.call('/openapi.json')
    (ROOT/'ml/openapi.json').write_text(json.dumps(openapi, indent=2)+'\n')
    fraud_api = {**openapi, 'info': {'title': 'Synthetic manipulation proxy — additive internal API', 'version': '1.0.0'},
                 'paths': {p: v for p, v in openapi['paths'].items() if p.startswith('/internal/v1/fraud/')}}
    (ROOT/'ml/fraud.openapi.json').write_text(json.dumps(fraud_api, indent=2)+'\n')
    print('Dual-model restart, durability, immutability, baseline and offline checks passed')


if __name__ == '__main__':
    main()
