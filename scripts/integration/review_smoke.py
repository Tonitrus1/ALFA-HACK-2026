#!/usr/bin/env python3
"""Public review regression on the running real-model stack; no scores are exposed."""
import argparse,json,time
from pathlib import Path
from uuid import uuid4
from smoke import Client
p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8080');p.add_argument('--expect-proxy',choices=['MODEL','UNAVAILABLE'],default='MODEL');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
c=Client(a.base);c.login();checks=[];apps=[]
def create(year='2025',signed=False):
    wire=c.call('/api/v1/applications','POST',dict(companyId='company-a',productId='working-capital',productVersion=1,need=dict(purpose='Синтетическая приёмка',amount=dict(amountMinor=50000001,currency='RUB'),termMonths=12)),{'Idempotency-Key':str(uuid4())})
    app=wire['applicationId'];url='/api/v1/applications/'+app
    wire=c.call(url,'PATCH',{'business':{'businessAgeMonths':40}},{'If-Match':'"v1"'})
    values=dict(totalAssetsMinor=100000001,totalLiabilitiesMinor=40000000,currentAssetsMinor=50000000,currentLiabilitiesMinor=20000000,equityMinor=60000001,revenueMinor=300000001,netProfitMinor=-1 if signed else 10000000,ebitMinor=-2 if signed else 15000000)
    form=dict(periodStart=year+'-01-01',periodEnd=year+'-12-31',reportingStandard='DEMO',currency='RUB',values=values,sourceDocumentReferences=[])
    statement=c.call(url+'/financial-statement','PUT',form,{'If-Match':'"v2"','Idempotency-Key':str(uuid4())})
    assert statement['statement']['values']==values
    statement=c.call(url+'/financial-statement/confirm','POST',dict(expectedStatementVersion=statement['statementVersion'],confirmedFieldNames=list(values),documentReferences=[]),{'If-Match':'"v'+str(statement['containerVersion'])+'"','Idempotency-Key':str(uuid4())})
    receipt=c.call(url+'/submit','POST',dict(expectedVersion=statement['containerVersion'],financialStatementVersion=statement['statementVersion'],requirementsVersion=1,consentRecordIds=[],documentIds=[],documentReferences=[]),{'Idempotency-Key':str(uuid4())})
    for _ in range(90):
        status=c.call(url+'/status')
        assert not any(s in json.dumps(status) for s in ('"score"','internalReasonCodes','bundleDigest','Service-Token'))
        if status['status'] not in ('SUBMITTED','REVIEW'):break
        time.sleep(.2)
    else:raise AssertionError('Review timeout')
    apps.append(dict(applicationId=app,status=status['status'],year=year,signed=signed))
    return status['status']
assert create() == ('APPROVED' if a.expect_proxy=='MODEL' else 'MANUAL')
checks.append('real_dual_model_approved' if a.expect_proxy=='MODEL' else 'required_fraud_outage_manual')
assert create('2024')=='MANUAL';checks.append('missing_independent_reference_manual')
# This verifies round-trip signed kopecks; the model/policy outcome may legitimately be MANUAL.
assert create(signed=True) in ('APPROVED','MANUAL');checks.append('signed_kopeck_roundtrip_no_public_scores')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(dict(status='PASS',checks=checks,applications=apps),indent=2)+'\n');print(json.dumps(dict(status='PASS',checks=checks)))
