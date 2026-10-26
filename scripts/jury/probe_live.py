#!/usr/bin/env python3
"""Non-destructive live API/contract probe using approved public demo credentials."""
import argparse
import datetime
import http.cookiejar
import json
from pathlib import Path
import urllib.error
import urllib.request

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--base-url')
parser.add_argument('--output', type=Path, default=ROOT/'docs/jury/evidence/live-readonly.json')
args = parser.parse_args()
config = json.loads((ROOT/'docs/jury/demo-access.json').read_text())
spec = json.loads((ROOT/'docs/jury/api/openapi.json').read_text())
base = (args.base_url or config['baseUrl']).rstrip('/')
report = {'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'baseUrl':base,
          'scope':'Login and read-only API/schema checks; no application, offer, document or preference was changed. Feed GET may record normal page exposure.', 'checks':[]}
for account in config['accounts']:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    def call(path, data=None, context=None):
        headers = {'Content-Type':'application/json','Origin':base,'ngrok-skip-browser-warning':'jury-contract-check'}
        if context is not None: headers['X-Company-Context'] = str(context)
        request = urllib.request.Request(base+path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        with opener.open(request, timeout=35) as response:
            return json.load(response)
    row = {'login':account['login'], 'checks':[]}
    try:
        session = call('/api/v1/auth/login', {'login':account['login'],'password':account['password']})
        context = session['contextVersion']
        row.update(authentication='PASS', companyId=session.get('companyId'))
        endpoints = [('/api/v1/session','Session'),('/api/v1/companies','CompanyList'),
          ('/api/v1/companies/'+account['companyId'],'Company'),
          ('/api/v1/products?companyId='+account['companyId'],'ProductList'),
          ('/api/v1/applications?companyId='+account['companyId'],'ApplicationList'),
          ('/api/v1/feed/preferences?companyId='+account['companyId'],'FeedPreferences'),
          ('/api/v1/feed?companyId='+account['companyId'],'Feed'),
          ('/api/v1/feed/saved?companyId='+account['companyId'],'SavedFeed')]
        for path, schema in endpoints:
            value = call(path, context=context)
            validator = Draft202012Validator({'$ref':'#/components/schemas/'+schema,'components':spec['components']})
            errors = [e.json_path for e in validator.iter_errors(value)]
            result = {'path':path,'schema':schema,'status':'PASS' if not errors else 'FAIL','schemaErrorPaths':errors}
            for key in ('items','cards'):
                if isinstance(value.get(key),list): result[key] = len(value[key])
            if 'rankingMode' in value: result['rankingMode'] = value['rankingMode']
            if 'rankingMetadata' in value:
                result['rankingMetadata'] = {k:v for k,v in value['rankingMetadata'].items() if k in ('modelVersion','catalogVersion','releaseId','ranker','bundleDigest')}
            row['checks'].append(result)
        other = 'company-b' if account['companyId']=='company-a' else 'company-a'
        try:
            call('/api/v1/companies/'+other,context=context)
            row['foreignCompany'] = {'status':'FAIL','httpStatus':200}
        except urllib.error.HTTPError as error:
            row['foreignCompany'] = {'status':'PASS' if error.code in (403,404) else 'FAIL','httpStatus':error.code}
    except urllib.error.HTTPError as error:
        row.update(authentication='FAIL',httpStatus=error.code)
    except Exception as error:
        row.update(authentication='ERROR',errorType=type(error).__name__)
    report['checks'].append(row)
report['status'] = 'PASS' if all(r.get('authentication')=='PASS' and r.get('foreignCompany',{}).get('status')=='PASS' and all(x['status']=='PASS' for x in r['checks']) for r in report['checks']) else 'FAIL'
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(report['status']!='PASS')
