"""Real ML HTTP calls plus reference policy; test expectations are read only here."""
import copy,json,os,time,platform
from pathlib import Path
import requests
from .client import RiskClient
from .demo_policy import precheck,after_risk
ROOT=Path(__file__).resolve().parents[2]
def main():
    bundle=Path(os.environ.get('MODEL_BUNDLE',ROOT/'ml/artifacts/baseline'));manifest=json.loads((bundle/'manifest.json').read_text());policy=json.loads((bundle/'policy.json').read_text())
    fixture=json.loads((ROOT/'ml/fixtures/scenarios.json').read_text());expected=json.loads((ROOT/'ml/fixtures/expectations.json').read_text())
    assert fixture['bundleDigest']==manifest['bundleDigest'],'Regenerate fixtures for this bundle'
    client=RiskClient('http://127.0.0.1:8001',os.environ['ML_INTERNAL_TOKEN'],manifest['bundleDigest']);results=[];latency=[]
    for company in fixture['companies']:
        name=company['companyId'].split(':')[-1];statement=company['initial'];reference=company['reference'];amount=company['amountMinor'];term=company['termMonths'];attempts=[]
        def evaluate(s,correction=False):
            initial=precheck(s,reference,amount,term,correction=correction)
            if initial:return {'policy':initial,'inference':None,'mlCalled':False}
            start=time.perf_counter();snapshot_request=client.snapshot_request(s,company['availableAt']);snapshot=client.create_snapshot(snapshot_request);risk_request=client.risk_request(snapshot)
            failure=None;inference=None
            try:
                # Explicit fault-injection only in this local demo client, scoped to S06.
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
    # Warm end-to-end feature creation + persisted inference, serial load, real backend-facing API.
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
if __name__=='__main__':main()
