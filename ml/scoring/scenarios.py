import copy,json,os,time,platform
from pathlib import Path
import requests
from .client import RiskClient
from .demo_policy import precheck,after_risk
from .decision_client import DecisionClient
ROOT=Path(__file__).resolve().parents[2]
def main():
    bundle=Path(os.environ.get('MODEL_BUNDLE',ROOT/'ml/artifacts/baseline'));manifest=json.loads((bundle/'manifest.json').read_text());policy=json.loads((bundle/'policy.json').read_text())
    fixture=json.loads((ROOT/'ml/fixtures/scenarios.json').read_text());expected=json.loads((ROOT/'ml/fixtures/expectations.json').read_text())
    assert fixture['bundleDigest']==manifest['bundleDigest'],'Regenerate fixtures for this bundle'
    client=RiskClient(os.environ.get('ML_API_URL','http://127.0.0.1:8001'),os.environ['ML_INTERNAL_TOKEN'],manifest['bundleDigest']);results=[];latency=[]
    for company in fixture['companies']:
        name=company['companyId'].split(':')[-1];statement=company['initial'];reference=company['reference'];amount=company['amountMinor'];term=company['termMonths'];attempts=[]
        def evaluate(s,correction=False):
            initial=precheck(s,reference,amount,term,correction=correction)
            if initial:return {'policy':initial,'inference':None,'mlCalled':False}
            start=time.perf_counter();snapshot_request=client.snapshot_request(s,company['availableAt']);snapshot=client.create_snapshot(snapshot_request);risk_request=client.risk_request(snapshot)
            failure=None;inference=None
            try:

                inference=client.evaluate(risk_request,'http://127.0.0.1:1' if name=='S06' else None)
            except requests.RequestException as e:failure=type(e).__name__
            decision=after_risk(s,amount,None if inference is None else inference['score'],policy['T_manual'],ml_error=failure is not None)
            return {'policy':decision,'mlCalled':True,'snapshotRequest':snapshot_request,'snapshot':snapshot,'riskRequest':risk_request,'inference':inference,'failure':failure,'seconds':time.perf_counter()-start}
        attempts.append(evaluate(statement))
        if name=='S03':
            correction=copy.deepcopy(statement);correction['values']['revenueMinor']=reference['values']['revenueMinor'];attempts.append(evaluate(correction,True))
            assert statement['values']['revenueMinor']!=correction['values']['revenueMinor']
        outcomes=[a['policy']['outcome'] for a in attempts];assert outcomes==expected[name],(name,outcomes)
        results.append({'scenario':name,'companyId':company['companyId'],'expected':expected[name],'actual':outcomes,'attempts':attempts});print(name,' → '.join(outcomes),flush=True)

    for _ in range(30):
        start=time.perf_counter();s=client.create_snapshot(client.snapshot_request(fixture['companies'][0]['reference']));client.evaluate(client.risk_request(s));latency.append(time.perf_counter()-start)
    p95=sorted(latency)[int(.95*len(latency))-1];assert p95<3
    report={'scope':'Standalone real Python/PostgreSQL ML service + executable reference policy. No UI, bank simulator or offer lifecycle implementation claimed.',
            'bundleDigest':manifest['bundleDigest'],'modelVersion':manifest['modelVersion'],'policyVersion':policy['version'],'T_manual':policy['T_manual'],
            'scenarios':results,'latency':{'requests':30,'concurrency':1,'p95Seconds':p95,'maxSeconds':max(latency),'samplesSeconds':latency,'platform':platform.platform(),'logicalCpu':os.cpu_count()},'passed':True}
    (ROOT/'reports/ml-scenarios.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    example=results[0]['attempts'][0]
    for name,key in [('create-feature.request.json','snapshotRequest'),('feature-snapshot.response.json','snapshot'),('risk.request.json','riskRequest'),('risk.response.json','inference')]:
        (ROOT/'ml/examples'/name).write_text(json.dumps(example[key],ensure_ascii=False,indent=2)+'\n')
    print('Actual results: reports/ml-scenarios.json; examples: ml/examples/; p95 seconds:',p95)


def dual_main():
    risk_bundle=Path(os.environ.get('MODEL_BUNDLE',ROOT/'ml/artifacts/baseline'))
    fraud_bundle=Path(os.environ.get('FRAUD_MODEL_BUNDLE',ROOT/'ml/artifacts/fraud-demo-v1'))
    manifest=json.loads((risk_bundle/'manifest.json').read_text())
    fraud_manifest=json.loads((fraud_bundle/'manifest.json').read_text())
    policy=json.loads((fraud_bundle/'policy.json').read_text())
    fixture=json.loads((ROOT/'ml/fixtures/scenarios.json').read_text())
    expected=json.loads((ROOT/'ml/fixtures/expectations.json').read_text())
    assert fixture['bundleDigest']==manifest['bundleDigest']
    client=RiskClient(os.environ.get('ML_API_URL','http://127.0.0.1:8001'),os.environ['ML_INTERNAL_TOKEN'],manifest['bundleDigest'])
    decision=DecisionClient(client,fraud_manifest,policy)
    results=[]
    def attempt(statement,reference,amount,term=12,application_id=None,reference_id=None,financial_version=1,**kwargs):
        body=client.snapshot_request(statement)
        if application_id is not None:body['applicationId']=application_id
        body['financialStatementVersion']=financial_version
        return decision.evaluate(body,reference,reference_id or 'DEMO:REFERENCE:'+str(__import__('uuid').uuid4()),amount,term,**kwargs)
    for company in fixture['companies']:
        name=company['companyId'].split(':')[-1]
        refid='DEMO:REFERENCE:'+str(__import__('uuid').uuid4())
        attempts=[attempt(company['initial'],company['reference'],company['amountMinor'],company['termMonths'],application_id=company['companyId'],reference_id=refid,fault='risk' if name=='S06' else None)]
        if name=='S03':
            correction=copy.deepcopy(company['initial']);correction['values']['revenueMinor']=company['reference']['values']['revenueMinor']
            attempts.append(attempt(correction,company['reference'],company['amountMinor'],application_id=company['companyId'],reference_id=refid,financial_version=2,correction=True))
            original,amended=(a['snapshotRequest'] for a in attempts)
            assert original['applicationId']==amended['applicationId']
            assert original['submissionSnapshotId']!=amended['submissionSnapshotId']
            assert original['financialSnapshotDigest']!=amended['financialSnapshotDigest']
            assert attempts[0]['referenceSnapshotDigest']==attempts[1]['fraudInference']['referenceSnapshotDigest']
        assert [a['policy']['outcome'] for a in attempts]==expected[name],(name,attempts)
        results.append({'scenario':name,'variant':'primary','attempts':attempts})
        print(name,' → '.join(a['policy']['outcome'] for a in attempts),flush=True)
    for case in json.loads((fraud_bundle/'scenario-fixtures.json').read_text())['cases']:
        a=attempt(case['statement'],case['reference'],20000000)
        assert a['policy']['outcome']=='MANUAL' and a['failure'] is None
        codes=a['policy']['reasonCodes'];assert 'SUSPECTED_FINANCIAL_MANIPULATION' in codes
        assert ('MODEL_REVIEW_BUDGET' in codes)==(case['variant']=='both')
        results.append({'scenario':'S05','variant':case['variant'],'attempts':[a]})
    base=fixture['companies'][0]
    a=attempt(base['reference'],base['reference'],20000000,fault='fraud')
    assert a['policy']['outcome']=='MANUAL' and a['fraudInference'] is None and a['inference'] is not None
    results.append({'scenario':'S06','variant':'fraud_failure','attempts':[a]})
    latency=[]
    for _ in range(30):
        a=attempt(base['reference'],base['reference'],20000000)
        assert a['policy']['outcome']=='APPROVED' and a['failure'] is None
        latency.append(a['seconds'])
    p95=sorted(latency)[int(.95*len(latency))-1];assert max(latency)<3
    report={'scope':'Standalone two-model API + executable backend reference policy; no real credit/fraud claims',
            'riskBundleDigest':manifest['bundleDigest'],'fraudBundleDigest':fraud_manifest['bundleDigest'],
            'policyVersion':policy['version'],'scenarios':results,'passed':True,
            'latency':{'requests':30,'concurrency':1,'p95Seconds':p95,'maxSeconds':max(latency)},
            'generalization':json.loads((fraud_bundle/'evaluation.json').read_text())['heldOutAttackFamily']}
    (ROOT/'reports/dual-model-scenarios.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    examples=ROOT/'ml/examples/fraud';examples.mkdir(exist_ok=True)
    first=results[0]['attempts'][0]
    for name,key in [('create-feature.request.json','fraudSnapshotRequest'),('feature-snapshot.response.json','fraudSnapshot'),('evaluation.request.json','fraudRequest'),('evaluation.response.json','fraudInference')]:
        (examples/name).write_text(json.dumps(first[key],ensure_ascii=False,indent=2)+'\n')
    print('Dual-model scenarios and failure variants passed; p95:',p95)


if __name__=='__main__':dual_main()
