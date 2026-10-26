import copy
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from scoring.bundle import load_bundle, predict_probability, read_manifest
from scoring.evaluation import evaluate, create_policy, financial_eligible
from scoring.features import digest, matrix
from scoring.learning import estimator
from scoring.releases import activate, selected_bundle, verify_scenarios
from scoring.train import train, finalize_manifest

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def project(tmp_path):
    shutil.copytree(ROOT/'ml/artifacts/baseline',tmp_path/'ml/artifacts/baseline')
    shutil.copytree(ROOT/'ml/fixtures',tmp_path/'ml/fixtures')
    return tmp_path


def test_legacy_bundle_keeps_exact_predictions_and_routes():
    model,manifest,_=load_bundle(ROOT/'ml/artifacts/baseline')
    statements=[r['reference'] for r in json.loads((ROOT/'ml/fixtures/scenarios.json').read_text())['companies']]
    np.testing.assert_array_equal(predict_probability(model,matrix(statements)),model.predict_proba(matrix(statements))[:,1])
    assert verify_scenarios(ROOT/'ml/artifacts/baseline',ROOT)==json.loads((ROOT/'ml/fixtures/expectations.json').read_text())


def test_atomic_selection_and_legacy_rollback(project):
    baseline=project/'ml/artifacts/baseline'
    assert selected_bundle(project)==baseline
    selection=activate(baseline,project)
    assert selection['path']=='ml/artifacts/baseline' and selected_bundle(project)==baseline
    pointer=project/'ml/active-bundle.json'
    bad={**selection,'bundleDigest':'0'*64};pointer.write_text(json.dumps(bad))
    with pytest.raises(ValueError,match='selection digest'):selected_bundle(project)


def test_unverified_candidate_cannot_replace_selection(project):
    baseline=project/'ml/artifacts/baseline';activate(baseline,project)
    pointer=project/'ml/active-bundle.json';before=pointer.read_bytes()
    candidate=project/'ml/artifacts/unverified';shutil.copytree(baseline,candidate)
    with pytest.raises(ValueError,match='Independent confirmation'):activate(candidate,project)
    assert pointer.read_bytes()==before


@pytest.mark.parametrize('fault',['artifact','shape','path'])
def test_corrupt_and_incompatible_bundle_rejected_before_loading(project,fault):
    bundle=project/'ml/artifacts/baseline'
    if fault=='artifact':
        (bundle/'policy.json').write_text('{}')
    else:
        m=json.loads((bundle/'manifest.json').read_text());m.pop('bundleDigest')
        if fault=='shape':m['features']=['different']
        else:m['artifacts']['../escape.json']='0'*64
        m['bundleDigest']=digest(m);(bundle/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(ValueError):read_manifest(bundle)


def test_pipeline_handles_missing_ratios_without_changing_input_contract():
    rng=np.random.default_rng(123);x=rng.normal(size=(60,8));y=np.tile([0,1],30)
    model=estimator({'family':'logistic','C':.1,'balanced':False},1);model.fit(x,y)
    probes=x[:2].copy();probes[0,[3,5]]=np.nan
    assert np.isfinite(predict_probability(model,probes)).all()
    with pytest.raises(ValueError):predict_probability(model,np.zeros((2,36)))
    with pytest.raises(ValueError):predict_probability(model,np.full((1,8),np.inf))


def test_capacity_ties_and_invalid_probabilities():
    y=np.tile([0,1],50);p=np.linspace(0,.8,100);eligible=np.ones(100,dtype=bool)
    p[-7:]=.9
    policy=create_policy(y,p,eligible,'test')
    assert policy['manualRows']<=5 and policy['T_manual']>.9
    report=evaluate(y,p);assert report['top5']['reviewed']==5
    for bad in [np.full(100,np.nan),np.full(100,1.1)]:
        with pytest.raises(ValueError):evaluate(y,bad)
    with pytest.raises(ValueError):evaluate(np.full(100,2),p)


def test_cohort_matches_precheck_financial_boundaries():
    statement=json.loads((ROOT/'ml/fixtures/scenarios.json').read_text())['companies'][0]['reference']
    assert financial_eligible(statement)
    for ratio,expected in [(89,True),(90,False),(91,False)]:
        s=copy.deepcopy(statement);v=s['values'];v['totalAssetsMinor']=((v['totalAssetsMinor']+99)//100)*100;v['totalLiabilitiesMinor']=v['totalAssetsMinor']*ratio//100;v['equityMinor']=v['totalAssetsMinor']-v['totalLiabilitiesMinor']
        assert financial_eligible(s)==expected
    statement['values']['revenueMinor']=0;assert not financial_eligible(statement)


def test_training_refuses_existing_or_published_directories(tmp_path):
    for path in [tmp_path,ROOT/'ml/artifacts/baseline',ROOT/'reports/new-model']:
        with pytest.raises(ValueError,match='new candidate'):train(ROOT/'datasets/ru-sme-dataset-10000',path)


def test_http_schema_is_unchanged(monkeypatch):
    monkeypatch.setenv('ML_DATABASE_URL','postgresql://unused')
    monkeypatch.setenv('ML_INTERNAL_TOKEN','schema-test-only-token')
    from scoring.server import app
    assert app.openapi()==json.loads((ROOT/'ml/openapi.json').read_text())


def test_verified_release_is_published_with_its_fixtures_and_can_roll_back(project):
    # Constructed acceptance evidence tests deployment mechanics, not model quality.
    baseline=project/'ml/artifacts/baseline'
    candidate=project/'offline-candidate';shutil.copytree(baseline,candidate)
    manifest=json.loads((candidate/'manifest.json').read_text())
    model_hash=manifest['artifacts']['model.joblib'];policy_hash=manifest['artifacts']['policy.json']
    fixture=json.loads((project/'ml/fixtures/scenarios.json').read_text());fixture.pop('bundleDigest')
    fixture.update(modelHash=model_hash,policyHash=policy_hash)
    (candidate/'scenarios.json').write_text(json.dumps(fixture))
    shutil.copy2(project/'ml/fixtures/expectations.json',candidate/'expectations.json')
    (candidate/'independent-validation.json').write_text(json.dumps({'passed':True,
        'checks':{'primaryRecallLower95Positive':True,'APNotWorse':True,'ordinaryLoglossGuard':True},
        'eligiblePairedDifference':{'averagePrecision':.01,'logLoss':-.001},
        'protocol':{'candidateModelHash':model_hash,'baselineModelHash':model_hash},'paired95':{'recall5':[.01,.02]}}))
    (candidate/'compatibility.json').write_text(json.dumps({'passed':True,'modelHash':model_hash}))
    metadata={k:v for k,v in manifest.items() if k not in {'artifacts','bundleDigest'}}
    metadata.update(modelVersion='scoring-v2-000000000001',releaseStatus='validated-demo')
    finalized=finalize_manifest(candidate,metadata)
    selection=activate(candidate,project)
    published=project/selection['path']
    assert published!=candidate and published.is_dir() and selected_bundle(project)==published
    assert load_bundle(published)[1]['bundleDigest']==finalized['bundleDigest']
    assert verify_scenarios(published,project)==json.loads((project/'ml/fixtures/expectations.json').read_text())
    activate(baseline,project);assert selected_bundle(project)==baseline
