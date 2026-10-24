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
# A missing LLM key permits genuine search-only evidence, never generated text.
if report['assistant']['body']['dependencies']['llm_key_configured'] is False:
    from smoke import Client
    from uuid import uuid4
    client=Client('http://127.0.0.1:8080'); client.login()
    conversation='acceptance-'+str(uuid4())
    path='/api/v1/assistant/conversations/'+conversation
    assert client.call(path+'/messages')['messages']==[]
    answer=client.call(path+'/messages','POST',{'clientMessageId':str(uuid4()),'text':'Какие документы нужны для Демо Оборотный?'})
    assert answer['status']=='SEARCH_ONLY' and answer['citations'], answer.get('status')
    citation=next(c for c in answer['citations'] if c['type']=='KNOWLEDGE')
    source=client.call(path+'/sources/'+citation['document_id']+'/'+str(citation['version']))
    assert source['text']
    assert len(client.call(path+'/messages')['messages'])==1
    other=Client(client.base); other.login('representative-b','company-b')
    assert other.call(path+'/messages')['messages']==[]
    report['publicAssistant']={'status':'PASS','checks':['cookie/CSRF backend adapter','real E5/BM25 search-only','cited source content','history','company isolation'],'generatedLlmAnswer':'NOT_VERIFIED'}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
