"""Explicit release selection with legacy rollback; training never calls activation."""
import json
import os
import re
from pathlib import Path
import shutil
import tempfile

from .bundle import file_hash, load_bundle
from .features import matrix
from .demo_policy import precheck, after_risk


def selected_bundle(project, override=None):
    project = Path(project).resolve()
    if override:
        return Path(override).resolve()
    pointer = project/'ml/active-bundle.json'
    if not pointer.exists():
        return project/'ml/artifacts/baseline'
    selection = json.loads(pointer.read_text())
    path = (project/selection['path']).resolve()
    if project/'ml/artifacts' not in path.parents:
        raise ValueError('Active bundle must be a project artifact directory')
    _, manifest, _ = load_bundle(path)
    if manifest['bundleDigest'] != selection['bundleDigest']:
        raise ValueError('Active selection digest mismatch; never modify a published bundle')
    return path


def verify_scenarios(path, project):
    path, project = Path(path), Path(project)
    model, manifest, policy = load_bundle(path)
    root = path if (path/'scenarios.json').exists() else project/'ml/fixtures'
    fixtures = json.loads((root/'scenarios.json').read_text())
    expected = json.loads((root/'expectations.json').read_text())
    if 'bundleDigest' in fixtures:
        if fixtures['bundleDigest'] != manifest['bundleDigest']:
            raise ValueError('Fixture bundle mismatch')
    elif (fixtures.get('modelHash'), fixtures.get('policyHash')) != (manifest['artifacts']['model.joblib'], manifest['artifacts']['policy.json']):
        raise ValueError('Fixture model/policy mismatch')
    results = {}
    for company in fixtures['companies']:
        sid = company['companyId'].split(':')[-1]
        statement, reference = company['initial'], company['reference']
        def decide(s):
            before = precheck(s, reference, company['amountMinor'], company['termMonths'], policy_version=policy['version'])
            if before:
                return before
            probability = float(model.predict_proba(matrix([s]))[0,1])
            return after_risk(s, company['amountMinor'], None if sid=='S06' else probability, policy['T_manual'],
                              ml_error=sid=='S06', policy_version=policy['version'])
        decisions = [decide(statement)]
        if sid == 'S03':
            decisions.append(decide(reference))
        results[sid] = [d['outcome'] for d in decisions]
        if results[sid] != expected[sid] or any(d['policyVersion'] != policy['version'] for d in decisions):
            raise ValueError('Integration scenario mismatch: '+sid)
    return results


def activate(path, project):
    project, path = Path(project).resolve(), Path(path).resolve()
    _, manifest, _ = load_bundle(path)
    baseline = project/'ml/artifacts/baseline'
    verify_scenarios(path, project)
    if path != baseline:
        if manifest.get('releaseStatus') != 'validated-demo':
            raise ValueError('Independent confirmation and compatibility checks required before activation')
        if not re.fullmatch(r'scoring-v2-[0-9a-f]{12}',manifest['modelVersion']):
            raise ValueError('Invalid immutable release version')
        evidence = json.loads((path/'independent-validation.json').read_text())
        compatibility = json.loads((path/'compatibility.json').read_text())
        expected_checks={'primaryRecallLower95Positive':evidence['paired95']['recall5'][0]>0,
                         'APNotWorse':evidence['eligiblePairedDifference']['averagePrecision']>=0,
                         'ordinaryLoglossGuard':evidence['eligiblePairedDifference']['logLoss']<=.002}
        if (not evidence['passed'] or evidence['checks']!=expected_checks or not all(expected_checks.values())
            or evidence['protocol']['candidateModelHash'] != manifest['artifacts']['model.joblib']
            or evidence['protocol']['baselineModelHash'] != file_hash(baseline/'model.joblib')
            or evidence['paired95']['recall5'][0] <= 0
            or not compatibility['passed'] or compatibility['modelHash'] != manifest['artifacts']['model.joblib']):
            raise ValueError('Release evidence does not establish the required improvement/compatibility')
        destination = project/'ml/artifacts'/manifest['modelVersion']
        if path != destination:
            if destination.exists():
                _, prior, _ = load_bundle(destination)
                if prior['bundleDigest'] != manifest['bundleDigest']:
                    raise ValueError('Release version already exists with different contents')
            else:
                staging = Path(tempfile.mkdtemp(prefix='.release-', dir=destination.parent))
                try:
                    shutil.copytree(path, staging, dirs_exist_ok=True)
                    load_bundle(staging)
                    os.rename(staging, destination)
                finally:
                    if staging.exists():shutil.rmtree(staging)
            path = destination
    selection = {'path':str(path.relative_to(project)), 'bundleDigest':manifest['bundleDigest'], 'modelVersion':manifest['modelVersion']}
    pointer = project/'ml/active-bundle.json'
    descriptor, temp = tempfile.mkstemp(prefix='.active-bundle-', dir=pointer.parent)
    try:
        with os.fdopen(descriptor,'w') as f:
            json.dump(selection, f, indent=2)
            f.write('\n')
            f.flush();os.fsync(f.fileno())
        os.replace(temp,pointer)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return selection
