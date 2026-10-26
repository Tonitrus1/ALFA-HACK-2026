#!/usr/bin/env python3
"""Check the four documented branches on the LOCAL demo only; creates synthetic cases."""
import datetime,http.cookiejar,json,time,urllib.request,urllib.error
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[2]
cfg=json.loads((ROOT/'docs/jury/demo-scenarios.json').read_text());base='http://127.0.0.1:8080'
settings=dict(line.split('=',1) for line in (ROOT/'.env').read_text().splitlines() if '=' in line and not line.lstrip().startswith('#'))
http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));session=None

def call(path,method='GET',body=None,extra=None):
 headers={'Origin':'http://localhost:5173','Content-Type':'application/json',**(extra or {})}
 if session:
  headers['X-Company-Context']=str(session['contextVersion'])
  if method!='GET':headers['X-CSRF-Token']=session['csrfToken']
 try:
  with http.open(urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method),timeout=40) as r:
   raw=r.read();return json.loads(raw) if raw else None
 except urllib.error.HTTPError as e:raise RuntimeError(f'{method} {path}: HTTP {e.code}; '+e.read().decode()[:350]) from None
session=call('/api/v1/auth/login','POST',{'login':'company-a','password':settings['CABINET_A_PASSWORD']})
report={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseUrl':base,'scope':'Four new labelled synthetic applications on the local Docker demo. No external-server mutations. No offers accepted.','source':'docs/jury/demo-scenarios.json','checks':[]}
for s in cfg['scenarios']:
 app=call('/api/v1/applications','POST',{'companyId':'company-a','productId':cfg['productId'],'productVersion':cfg['productVersion'],'need':{'purpose':'Проверка жюри: '+s['name'],'amount':{'amountMinor':cfg['requestedAmountRub']*100,'currency':'RUB'},'termMonths':cfg['termMonths']}},{'Idempotency-Key':str(uuid4())})
 path='/api/v1/applications/'+app['applicationId']
 call(path,'PATCH',{'business':{'businessAgeMonths':cfg['businessAgeMonths'],'annualRevenue':{'amountMinor':s['preliminaryRevenueRub']*100,'currency':'RUB'}}},{'If-Match':'"v1"'})
 values={k+'Minor':v*100 for k,v in s['valuesRub'].items()}
 statement=call(path+'/financial-statement','PUT',{'periodStart':cfg['periodStart'],'periodEnd':cfg['periodEnd'],'reportingStandard':'DEMO','currency':'RUB','values':values,'sourceDocumentReferences':[]},{'If-Match':'"v2"','Idempotency-Key':str(uuid4())})
 confirmed=call(path+'/financial-statement/confirm','POST',{'expectedStatementVersion':statement['statementVersion'],'confirmedFieldNames':list(values),'documentReferences':[]},{'If-Match':'"v'+str(statement['containerVersion'])+'"','Idempotency-Key':str(uuid4())})
 call(path+'/submit','POST',{'expectedVersion':confirmed['containerVersion'],'consentRecordIds':[],'documentIds':[],'documentReferences':[],'requirementsVersion':1,'financialStatementVersion':confirmed['statementVersion']},{'Idempotency-Key':str(uuid4())})
 for _ in range(90):
  state=call(path+'/status')
  if state['status'] in ['APPROVED','DECLINED','MANUAL','ALTERNATIVE','NEEDS_INFO']:break
  time.sleep(1)
 decision=call(path+'/decision') if state['status'] in ['APPROVED','DECLINED','ALTERNATIVE'] else {};row={'scenario':s['name'],'applicationId':app['applicationId'],'expected':s['expected'],'actual':state['status'],'status':'PASS' if state['status']==s['expected'] else 'FAIL','explanation':decision.get('publicExplanation')}
 if decision.get('offerIds'):
  offer=call('/api/v1/offers/'+decision['offerIds'][0]);row['offerAmountRub']=offer['amount']['amountMinor']/100
  if s['expectedOfferRub'] is not None and row['offerAmountRub']!=s['expectedOfferRub']:row['status']='FAIL'
 report['checks'].append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
report['status']='PASS' if all(r['status']=='PASS' for r in report['checks']) else 'FAIL';(ROOT/'docs/jury/evidence/local-scenarios.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');raise SystemExit(report['status']!='PASS')
