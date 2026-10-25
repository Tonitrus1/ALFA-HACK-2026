"""Render the real local deployment and check its model boundary and CPU budgets."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LocalLLMTests(unittest.TestCase):
    def test_local_stack_needs_no_provider_and_keeps_model_private(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / '.env'
            env_file.write_text('\n'.join(
                line.split('=', 1)[0] + '=test-only-secret-with-at-least-32-characters'
                if line.endswith('=') and not line.startswith('#') else line
                for line in (ROOT / '.env.example').read_text().splitlines()
            ))
            environment = {k: v for k, v in os.environ.items()
                           if k not in {'LOCAL_RAG_MODEL', 'LOCAL_OCR_MODEL', 'COMPOSE_PROJECT_NAME', 'FEED_BUNDLE_PATH'}}
            result = subprocess.run(['docker', 'compose', '--env-file', str(env_file),
                                     '-f', str(ROOT / 'compose.yaml'),
                                     '-f', str(ROOT / 'deploy/compose.local-llm.yaml'),
                                     'config', '--format', 'json'],
                                    check=True, capture_output=True, text=True, env=environment)
            baseline = subprocess.run(['docker', 'compose', '--env-file', str(env_file),
                                       '-f', str(ROOT / 'compose.yaml'), 'config', '--format', 'json'],
                                      check=True, capture_output=True, text=True, env=environment)
        model = json.loads(result.stdout)
        services = model['services']
        # Only the extraction LLM changes; recognition and the backend worker stay intact.
        ocr = services['ocr']['environment']
        original = json.loads(baseline.stdout)['services']['ocr']['environment']
        self.assertEqual(ocr['OCR_ENGINE'], original['OCR_ENGINE'])
        self.assertEqual(ocr['CPU_THREADS'], original['CPU_THREADS'])
        self.assertEqual(ocr['LLM_RESPONSE_FORMAT'], 'json_object')
        self.assertGreater(int(ocr['MAX_CONTEXT_CHARS']), 10000)
        self.assertEqual(services['ocr-worker'], json.loads(baseline.stdout)['services']['ocr-worker'])
        for name in ('assistant', 'ocr'):
            settings = services[name]['environment']
            self.assertEqual(settings['LLM_BASE_URL'], 'http://ollama:11434/v1')
            self.assertEqual(settings['LLM_MODEL'], 'qwen2.5:3b')
            self.assertEqual(settings['LLM_API_KEY'], 'ollama')
            self.assertEqual(services[name]['depends_on']['ollama-init']['condition'],
                             'service_completed_successfully')
        self.assertFalse(services['ollama'].get('ports'))
        self.assertEqual(services['ollama']['environment']['OLLAMA_NO_CLOUD'], '1')
        self.assertEqual(services['ollama']['environment']['OLLAMA_NUM_PARALLEL'], '1')
        assistant = services['assistant']['environment']
        self.assertLessEqual(int(assistant['CONTEXT_TOKENS']) + int(assistant['LLM_MAX_TOKENS']),
                             int(services['ollama']['environment']['OLLAMA_CONTEXT_LENGTH']))
        self.assertLess(int(assistant['LLM_TIMEOUT_SECONDS']), int(assistant['TURN_DEADLINE_SECONDS']))
        for name in ('assistant', 'assistant-init'):
            cache = [v['source'] for v in services[name]['volumes'] if v['target'] == '/app/model-cache']
            self.assertEqual(cache, ['assistant-local-models'])
            self.assertEqual(services[name]['environment']['TOKENIZER_MODEL'], 'Qwen/Qwen2.5-3B-Instruct')


if __name__ == '__main__':
    unittest.main()
