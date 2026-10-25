"""SDK wire contract only; does not claim real local model inference."""
import json
import unittest

import httpx
from openai import AsyncOpenAI
from alfa_assistant.config import Settings
from alfa_assistant.llm import OpenAICompatibleLLM


class LocalProviderContract(unittest.IsolatedAsyncioTestCase):
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
