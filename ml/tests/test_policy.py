"""Controlled scores here are explicit unit test inputs, not integrated inference evidence."""
import copy,json
from pathlib import Path
from scoring.demo_policy import precheck,after_risk
ROOT=Path(__file__).resolve().parents[2]
def fixture():return copy.deepcopy(json.loads((ROOT/'ml/fixtures/scenarios.json').read_text())['companies'][0]['reference'])
def test_threshold_equality_and_risk_priority():
    s=fixture();assert after_risk(s,900000000,.04,.04)['outcome']=='MANUAL'
    assert after_risk(s,900000000,.041,.04)['outcome']=='MANUAL'
    assert after_risk(s,900000000,.039,.04)['outcome']=='ALTERNATIVE'
def test_zero_cap_and_minimum():
    s=fixture();s['values']['revenueMinor']=39999999
    assert after_risk(s,20000000,.001,.04)['rule']=='CAP_BELOW_MINIMUM'
    s['values']['revenueMinor']=40000003
    assert after_risk(s,20000000,.001,.04)['offerAmountMinor']==10000000
    assert after_risk(s,10000000,.001,.04)['outcome']=='APPROVED'
def test_hard_rule_and_rfi():
    s=fixture();ref=copy.deepcopy(s);s['values']['revenueMinor']*=2
    assert precheck(s,ref,20000000,12)['outcome']=='NEEDS_INFO'
    assert precheck(s,ref,20000000,12,correction=True,explanation='Искусственное подтверждение')['outcome']=='MANUAL'
    v=s['values'];s['values']['revenueMinor']=ref['values']['revenueMinor'];v['totalLiabilitiesMinor']=v['totalAssetsMinor']*9//10+1;v['equityMinor']=v['totalAssetsMinor']-v['totalLiabilitiesMinor']
    assert precheck(s,ref,20000000,12)['outcome']=='DECLINED'
def test_failed_risk_never_approves():
    for score in [None,float('nan'),float('inf'),-.1,1.1]:assert after_risk(fixture(),10000000,score,.04)['outcome']=='MANUAL'
