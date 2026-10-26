"""SDK wire contract only; does not claim real local model inference."""
import json
import unittest

import httpx
from openai import AsyncOpenAI
from alfa_assistant.config import Settings
from alfa_assistant.llm import OpenAICompatibleLLM


class LocalProviderContract(unittest.IsolatedAsyncioTestCase):
    async def test_ollama_tools_are_not_constrained_by_json_grammar(self):
        payloads = []

        def handler(request):
            payloads.append(json.loads(request.content))
            return httpx.Response(200, json={
                'id': 'test', 'object': 'chat.completion', 'created': 1, 'model': 'local',
                'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {
                    'role': 'assistant', 'content': None, 'tool_calls': [{
                        'id': 'call-1', 'type': 'function',
                        'function': {'name': 'list_credit_products', 'arguments': '{}'},
                    }]}}],
            })

        adapter = OpenAICompatibleLLM(Settings(
            llm_api_key='ollama', llm_json_with_tools=False, llm_reasoning_options=False,
        ))
        await adapter.client.close()
        adapter.client = AsyncOpenAI(
            api_key='ollama', base_url='http://local-model/v1', max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            tools = [{'type': 'function', 'function': {'name': 'list_credit_products',
                      'parameters': {'type': 'object', 'properties': {}}}}]
            result = await adapter.complete([{'role': 'user', 'content': 'products'}], tools, {'model': 'local'})
            self.assertEqual(result.calls[0]['function']['name'], 'list_credit_products')
            self.assertNotIn('response_format', payloads[0])
            await adapter.complete([{'role': 'user', 'content': 'JSON'}], [], {'model': 'local'})
            self.assertEqual(payloads[1]['response_format'], {'type': 'json_object'})
        finally:
            await adapter.close()

    async def test_local_endpoint_omits_provider_extensions(self):
        for enabled in (False, True):
            payloads = []

            def handler(request):
                payloads.append(json.loads(request.content))
                return httpx.Response(200, json={
                    'id': 'test', 'object': 'chat.completion', 'created': 1, 'model': 'local',
                    'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {
                        'role': 'assistant', 'content': '{"answer":"ok"}'}}],
                })

            settings = Settings(llm_api_key='ollama', llm_reasoning_options=enabled)
            adapter = OpenAICompatibleLLM(settings)
            await adapter.client.close()
            adapter.client = AsyncOpenAI(
                api_key='ollama', base_url='http://local-model/v1', max_retries=0,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            )
            try:
                result = await adapter.complete([{'role': 'user', 'content': 'test'}], [], {'model': 'local'})
                self.assertEqual(result.content, '{"answer":"ok"}')
                self.assertEqual('reasoning' in payloads[0], enabled)
                self.assertEqual('chat_template_kwargs' in payloads[0], enabled)
                self.assertEqual(payloads[0]['response_format'], {'type': 'json_object'})
            finally:
                await adapter.close()


if __name__ == '__main__':
    unittest.main()
