#!/usr/bin/env python3
"""Public HTTP acceptance for a running Compose/native stack. Never emits credentials."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]

class Client:
    def __init__(self,base):
        self.base=base;self.session=None
        self.http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,path,method='GET',body=None,extra=None,expected=None):
        headers={'Origin':'http://localhost:5173',**(extra or {})}
        if self.session:
            headers['X-Company-Context']=str(self.session['contextVersion'])
            if method!='GET':headers['X-CSRF-Token']=self.session['csrfToken']
        data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
        if data is not None:headers['Content-Type']='application/json'
        try:
            with self.http.open(urllib.request.Request(self.base+path,data=data,headers=headers,method=method),timeout=8) as r:
                raw=r.read();return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if expected==e.code:return {'expectedHttpStatus':e.code}
            raise AssertionError(f'{method} {path}: unexpected HTTP {e.code}') from None
    def login(self,account='representative-a',company='company-a'):
        self.session=self.call('/demo/api/v1/session','POST',{'accountId':account})
        self.session=self.call('/api/v1/session/company','POST',{'companyId':company})

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8080');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--replay',action='store_true');p.add_argument('--expect-feed',choices=['MODEL','RULES'],default='MODEL');p.add_argument('--risk-outage',action='store_true')
    a=p.parse_args();c=Client(a.base)
    for _ in range(90):
        try:c.call('/demo/api/v1/accounts');break
        except (OSError,AssertionError):time.sleep(1)
    else:raise RuntimeError('Backend did not become ready')
    c.login();statefile=ROOT/'.local/smoke-state.json';report={'status':'PASS','checks':[]}
    def checked(name):report['checks'].append(name)
    state=json.loads(statefile.read_text()) if statefile.exists() else {}
    if a.replay:
        assert state,'Initial smoke state required'
        assert c.call('/api/v1/applications/'+state['applicationId']+'/decision')['outcome']=='APPROVED'
        first=c.call('/api/v1/feed?companyId=company-a&cursor='+state['cursor'])
        assert first==state['page'],'Saved page/exposure changed across restart'
        assert c.call('/api/v1/recommendation-feedback','POST',state['event'])==state['receipt']
        checked('restart_preserves_decision_page_and_feedback_replay')
    else:
        if not a.risk_outage:
            c.call('/api/v1/feed/preferences?companyId=company-a','PUT',{'task':'EQUIPMENT','help':'COST','depth':'PRACTICAL'})
            page=c.call('/api/v1/feed?companyId=company-a')
            assert page['rankingMode']==a.expect_feed,(page['rankingMode'],a.expect_feed)
            assert len(page['cards'])==6 and len({x['contentId'] for x in page['cards']})==6
            checked('real_E5_ranking' if a.expect_feed=='MODEL' else 'feed_outage_rules_fallback')
            cursor=page['nextCursor'];next_page=c.call('/api/v1/feed?companyId=company-a&cursor='+cursor)
            assert not {x['contentId'] for x in page['cards']} & {x['contentId'] for x in next_page['cards']}
            assert next_page==c.call('/api/v1/feed?companyId=company-a&cursor='+cursor)
            event=dict(clientEventId=str(uuid4()),exposureId=page['rankingMetadata']['exposureId'],itemId=page['cards'][0]['contentId'],action='HELPFUL',occurredAt='2026-10-22T12:00:00Z')
            receipt=c.call('/api/v1/recommendation-feedback','POST',event)
            assert receipt==c.call('/api/v1/recommendation-feedback','POST',event)
            saved=c.call('/api/v1/feed/saved?companyId=company-a')
            assert event['itemId'] in [x['contentId'] for x in saved['cards']]
            checked('feed_cursor_feedback_saved_and_idempotency')
            # Schema checks cover public FEED wire shape, including required explicit null reactions.
            try:
                from jsonschema import Draft202012Validator
                spec=json.loads((ROOT/'docs/architecture/contracts/public.openapi.json').read_text())
                for schema,value in [('Feed',page),('Feed',next_page),('SavedFeed',saved),('MLReceipt',receipt)]:
                    Draft202012Validator({'$ref':'#/components/schemas/'+schema,'components':spec['components']}).validate(value)
                checked('public_openapi_schemas')
            except ImportError:raise RuntimeError('Install jsonschema to run mandatory public schema validation') from None
            state.update(cursor=cursor,page=next_page,event=event,receipt=receipt)
        values=dict(totalAssetsMinor=100000000,totalLiabilitiesMinor=40000000,currentAssetsMinor=50000000,currentLiabilitiesMinor=20000000,equityMinor=60000000,revenueMinor=300000000,netProfitMinor=10000000,ebitMinor=15000000)
        app=c.call('/api/v1/applications','POST',dict(companyId='company-a',productId='working-capital',productVersion=1,
                   need=dict(purpose='Закупка товара',amount=dict(amountMinor=50000000,currency='RUB'),termMonths=12)),{'Idempotency-Key':str(uuid4())})
        identifier=app['applicationId'];path='/api/v1/applications/'+identifier
        updated=c.call(path,'PATCH',{'business':{'businessAgeMonths':40}},{'If-Match':'"v1"'})
        form=dict(periodStart='2025-01-01',periodEnd='2025-12-31',reportingStandard='DEMO',currency='RUB',values=values,sourceDocumentReferences=[])
        statement=c.call(path+'/financial-statement','PUT',form,{'If-Match':'"v2"','Idempotency-Key':str(uuid4())})
        confirmed=c.call(path+'/financial-statement/confirm','POST',dict(expectedStatementVersion=statement['statementVersion'],confirmedFieldNames=list(values),documentReferences=[]),
                         {'If-Match':'"v'+str(statement['containerVersion'])+'"','Idempotency-Key':str(uuid4())})
        body=dict(expectedVersion=confirmed['containerVersion'],consentRecordIds=[],documentIds=[],documentReferences=[],requirementsVersion=1,financialStatementVersion=confirmed['statementVersion'])
        key=str(uuid4());receipt=c.call(path+'/submit','POST',body,{'Idempotency-Key':key})
        assert receipt==c.call(path+'/submit','POST',body,{'Idempotency-Key':key})
        target='MANUAL' if a.risk_outage else 'APPROVED'
        for _ in range(60):
            status=c.call(path+'/status')
            if status['status']==target:break
            if status['status'] in ('DECLINED','ALTERNATIVE','NEEDS_INFO'):raise AssertionError('Unexpected decision '+status['status'])
            time.sleep(.5)
        else:raise AssertionError('Decision deadline exceeded: '+status['status'])
        assert not any(key in json.dumps(status) for key in ('internalReasonCodes','bundleDigest','Service-Token'))
        checked('risk_outage_manual' if a.risk_outage else 'application_real_risk_approved')
        if not a.risk_outage:state['applicationId']=identifier
        b=Client(a.base);b.login('representative-b','company-b')
        assert b.call(path,expected=404)=={'expectedHttpStatus':404}
        checked('company_isolation')
        statefile.parent.mkdir(parents=True,exist_ok=True);statefile.write_text(json.dumps(state,ensure_ascii=False));statefile.chmod(0o600)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
