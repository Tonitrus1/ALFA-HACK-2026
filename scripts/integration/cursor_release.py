#!/usr/bin/env python3
"""Prove a catalog change expires old cursors, and rollback replays their exact content."""
import argparse,json
from pathlib import Path
from smoke import Client
p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8080');p.add_argument('--state',type=Path,required=True);p.add_argument('--expired',action='store_true');p.add_argument('--capture',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
c=Client(a.base)
if a.capture:
 c.login('representative-b','company-b');first=c.call('/api/v1/feed?companyId=company-b');cursor=first['nextCursor'];page=c.call('/api/v1/feed?companyId=company-b&cursor='+cursor)
 a.state.parent.mkdir(parents=True,exist_ok=True);a.state.write_text(json.dumps(dict(cursor=cursor,page=page)))
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(dict(status='PASS',check='capture_foreign_company_untouched_cursor'))+'\n');raise SystemExit(0)
s=json.loads(a.state.read_text());c.login('representative-b','company-b')
url='/api/v1/feed?companyId=company-b&cursor='+s['cursor']
if a.expired:assert c.call(url,expected=409)=={'expectedHttpStatus':409}
else:assert c.call(url)==s['page'],'Rollback must not substitute old content/exposure'
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'status':'PASS','check':'old_cursor_expires' if a.expired else 'rollback_cursor_exact_replay'})+'\n')
