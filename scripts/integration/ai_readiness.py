#!/usr/bin/env python3
"""Verify genuine AI readiness, recording missing external LLM configuration explicitly."""
import argparse
import json
import subprocess
import time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
report={}
for service,port in [('assistant',8000),('ocr',8001)]:
    command=['docker','compose','exec','-T',service,'python','-c',f'''import json,urllib.request,urllib.error
try:
    r=urllib.request.urlopen('http://localhost:{port}/health/ready',timeout=6)
except urllib.error.HTTPError as e:r=e
print(json.dumps({{"httpStatus":r.code,"body":json.load(r)}}))''']
    for i in range(150):
        result=subprocess.run(command,capture_output=True,text=True)
        try:
            state=json.loads(result.stdout)
            body=state['body']
            local=(body.get('dependencies',{}).get('knowledge') and body['dependencies'].get('qdrant') and body['dependencies'].get('searxng')) if service=='assistant' else body.get('ocr_ready')
            if local:break
        except (ValueError,KeyError):pass
        time.sleep(2)
    else:raise SystemExit(service+' local models/index/engine not ready')
    configured=body['dependencies']['llm_key_configured'] if service=='assistant' else body['llm_configured']
    assert state['httpStatus']==(200 if configured else 503), state
    report[service]={**state,'externalLlmInference':'NOT_VERIFIED' if configured else 'BLOCKED_LLM_API_KEY_MISSING'}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
