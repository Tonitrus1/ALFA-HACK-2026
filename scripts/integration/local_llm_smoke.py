#!/usr/bin/env python3
"""Real local inference, tool call and cited RAG answer; no mock or external LLM."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
# Executed inside the running assistant, so credentials never leave its environment.
PROBE = r'''
import asyncio, json, os, time
from uuid import uuid4
import httpx
from alfa_assistant.config import Settings
from alfa_assistant.llm import OpenAICompatibleLLM
from alfa_assistant.schemas import ModelAnswer

async def main():
    cfg = Settings()
    assert cfg.llm_base_url == 'http://ollama:11434/v1', 'Not the bundled local model'
    started = time.monotonic()
    llm = OpenAICompatibleLLM(cfg)
    parameters = {'model': cfg.llm_model, 'temperature': 0, 'max_tokens': 128}
    try:
        answer = await llm.complete([{'role':'user','content':
            'Ответь только JSON: {"status":"ANSWER","answer":"Привет","citation_ids":[]}'}], [], parameters)
        ModelAnswer.model_validate_json(answer.content)
        tools = [{'type':'function','function':{'name':'list_credit_products',
            'description':'Получить кредитные продукты','parameters':{'type':'object','properties':{}}}}]
        call = await llm.complete([{'role':'user','content':
            'Вызови инструмент list_credit_products, чтобы получить список кредитных продуктов.'}], tools, parameters)
        assert any(c['function']['name']=='list_credit_products' for c in call.calls), 'Missing tool call'
    finally:
        await llm.close()
    headers = {'X-Admin-Key':os.environ['ADMIN_API_KEY']}
    async with httpx.AsyncClient(base_url='http://localhost:8000', timeout=190) as client:
        query = 'Что публикует ФНС в реестре получателей поддержки МСП?'
        found = await client.get('/v1/knowledge/search', params={'q':query}, headers=headers)
        found.raise_for_status()
        assert found.json()['results'], 'No local knowledge retrieved'
        created = await client.post('/v1/sessions', json={})
        created.raise_for_status()
        session = created.json()
        sid = session['session_id']
        auth = {'Authorization':'Bearer '+session['session_token']}
        try:
            response = await client.post('/v1/sessions/'+sid+'/messages', headers=auth,
                json={'client_message_id':str(uuid4()),'message':query})
            response.raise_for_status()
            result = response.json()
            assert result['status']=='ANSWER' and result['citations'], 'No generated answer with citations: '+json.dumps(result,ensure_ascii=False)
            assert result['usage']['error_code'] is None
            print(json.dumps({'passed':True,'model':cfg.llm_model,'base_url':cfg.llm_base_url,
                'checks':['real_json_generation','real_tool_call','local_retrieval','generated_cited_answer'],
                'latency_seconds':round(time.monotonic()-started,2),
                'rag_latency_ms':result['latency_ms'],'answer':result['answer'],
                'citations':len(result['citations'])},ensure_ascii=False))
        finally:
            await client.delete('/v1/sessions/'+sid,headers=auth)
asyncio.run(main())
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--project')
    parser.add_argument('--context')
    parser.add_argument('--selectel', action='store_true')
    args = parser.parse_args()
    command = ['docker'] + (['--context', args.context] if args.context else [])
    command += ['compose', '--env-file', str(args.env_file), '-f', str(ROOT / 'compose.yaml'),
                '-f', str(ROOT / 'deploy/compose.local-llm.yaml')]
    if args.selectel:
        command += ['-f', str(ROOT / 'deploy/selectel/compose.yaml')]
    if args.project:
        command += ['--project-name', args.project]
    subprocess.run(command + ['exec', '-T', 'assistant', 'python', '-c', PROBE], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
