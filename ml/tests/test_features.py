import copy
import json
from pathlib import Path
import joblib
import numpy as np
import pytest
from scoring.features import build, matrix, rub_to_minor, code_digest, digest, FIELDS
ROOT=Path(__file__).resolve().parents[2]
@pytest.fixture
def statement():return json.loads((ROOT/'ml/generated/companies.json').read_text())[0]['reference']
def test_exact_conversion():
    assert rub_to_minor('90071992547409.91')==9007199254740991
    assert rub_to_minor('-123.45')==-12345
    with pytest.raises(ValueError):rub_to_minor('0.001')
def test_zero_debt_missing(statement):
    v=statement['values'];v.update(totalLiabilitiesMinor=0,currentLiabilitiesMinor=0,equityMinor=v['totalAssetsMinor'])
    f=build(statement);assert f['X4'] is None and f['X8'] is None and f['X2']==0
    model=joblib.load(ROOT/'ml/artifacts/baseline/model.joblib');assert np.isfinite(model.predict_proba(matrix([statement]))).all()
def test_invalid_and_negative(statement):
    for k in ['equityMinor','netProfitMinor','ebitMinor']:statement['values'][k]=-12300
    with pytest.raises(ValueError):build(statement)
    statement['values']['totalLiabilitiesMinor']=statement['values']['totalAssetsMinor']+12300
    assert build(statement)['X1']<0
    statement['values']['totalAssetsMinor']=0
    with pytest.raises(ValueError):build(statement)
def test_batch_online_same_transform_and_no_leakage(statement):
    model=joblib.load(ROOT/'ml/artifacts/baseline/model.joblib');f=build(statement)
    x=np.array([[np.nan if n is None else n for n in f.values()]])
    np.testing.assert_array_equal(x,matrix([statement]));np.testing.assert_array_equal(model.predict_proba(x),model.predict_proba(matrix([statement])))
    assert list(FIELDS)==['total_assets','current_assets','total_liabilities','current_liabilities','equity','revenue','net_profit','ebit']
    m=json.loads((ROOT/'ml/artifacts/baseline/manifest.json').read_text());assert m['featureCodeDigest']==code_digest();assert m['rawWhitelist']==list(FIELDS)
def test_bundle_selection_lock():
    p=ROOT/'ml/artifacts/baseline';m=json.loads((p/'manifest.json').read_text());h=m.pop('bundleDigest');assert h==digest(m)
    lock=json.loads((p/'selection-lock.json').read_text());assert lock['modelHash']==m['artifacts']['model.joblib'];assert lock['policyHash']==m['artifacts']['policy.json']
