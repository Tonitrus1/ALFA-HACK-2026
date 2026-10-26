"""Server deployment invariants. Compose rendering does not require a running daemon."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location('selectel_deployment', Path(__file__).with_name('selectel.py'))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class SelectelTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env_file = self.root / '.env.selectel'
        self.handoff_root = self.root / 'handoff'
        with patch.object(server, 'ROOT', self.handoff_root):
            server.initialize(self.env_file, 'cabinet.example.com', 'admin@example.com')

    def deployment(self):
        return server.Deployment(self.env_file)

    def test_init_is_private_and_preserves_secrets(self):
        before = server.read_env(self.env_file)
        with patch.object(server, 'ROOT', self.handoff_root):
            server.initialize(self.env_file)
        self.assertEqual(before, server.read_env(self.env_file))
        self.assertEqual(self.env_file.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(before['CABINET_A_PASSWORD'], before['CABINET_B_PASSWORD'])
        handoff = self.handoff_root / '.local/selectel/cabinet-access.md'
        self.assertIn('https://cabinet.example.com/login', handoff.read_text())
        self.assertEqual(handoff.stat().st_mode & 0o777, 0o600)

    def test_requires_domain_and_cannot_accidentally_retarget_existing_volumes(self):
        for value in ('127.0.0.1', 'https://cabinet.example.com', 'cabinet.example.com/path', '*.example.com'):
            with self.assertRaises(ValueError):
                server.domain_name(value)
        with self.assertRaises(ValueError), patch.object(server, 'ROOT', self.handoff_root):
            server.initialize(self.env_file, project='different-project')

    def test_full_launch_requires_llm_but_configuration_does_not(self):
        values = server.read_env(self.env_file)
        values['LLM_MODE'] = 'external'
        server.validate(values, require_llm=False)
        with self.assertRaisesRegex(ValueError, 'LLM_API_KEY'):
            server.validate(values)

    def test_local_launch_needs_no_provider_key_and_rejects_unbudgeted_models(self):
        values = server.read_env(self.env_file)
        self.assertEqual(values['LLM_MODE'], 'local')
        self.assertEqual(values['LLM_API_KEY'], '')
        server.validate(values)
        for updates in ({'LLM_MODE': 'typo'}, {'LOCAL_RAG_MODEL': 'qwen2.5:7b'},
                        {'LOCAL_OCR_MODEL': 'qwen2.5:7b'}):
            with self.assertRaises(ValueError):
                server.validate(values | updates)

    def test_init_fills_blank_template_secrets_without_rotating_existing_passwords(self):
        original = server.read_env(self.env_file)['CABINET_A_PASSWORD']
        self.env_file.write_text(self.env_file.read_text().replace('ML_SERVICE_TOKEN=' +
                server.read_env(self.env_file)['ML_SERVICE_TOKEN'], 'ML_SERVICE_TOKEN='))
        with patch.object(server, 'ROOT', self.handoff_root):
            server.initialize(self.env_file)
        values = server.read_env(self.env_file)
        self.assertEqual(values['CABINET_A_PASSWORD'], original)
        self.assertGreaterEqual(len(values['ML_SERVICE_TOKEN']), 32)

    def test_ambient_local_credentials_cannot_override_server_settings(self):
        with patch.dict(os.environ, {'BACKEND_DB_PASSWORD': 'local-password', 'PUBLIC_DOMAIN': 'wrong.example.com',
                                     'FEED_BUNDLE_PATH': '/local/path', 'COMPOSE_FILE': 'wrong.yaml'}):
            deployment = self.deployment()
        for key in ('BACKEND_DB_PASSWORD', 'PUBLIC_DOMAIN', 'FEED_BUNDLE_PATH', 'COMPOSE_FILE'):
            self.assertNotIn(key, deployment.environment)

    def test_compose_keeps_all_services_and_publishes_only_tls_edge(self):
        try:
            model = self.deployment().model()
        except FileNotFoundError:
            self.skipTest('Docker Compose CLI is not installed')
        self.assertEqual(model['name'], 'credit-selectel')
        self.assertTrue({'backend', 'gateway', 'risk', 'feed', 'ml-bridge', 'scanner', 'assistant',
                         'assistant-init', 'ocr', 'ocr-worker', 'qdrant', 'searxng', 'edge'} <= set(model['services']))
        published = {name: service['ports'] for name, service in model['services'].items() if service.get('ports')}
        self.assertEqual(set(published), {'edge'})
        self.assertEqual({p['published'] for p in published['edge']}, {'80', '443'})
        backend = model['services']['backend']['environment']
        self.assertEqual(backend['SPRING_PROFILES_ACTIVE'], 'selectel')
        self.assertEqual(backend['PUBLIC_ORIGIN'], 'https://cabinet.example.com')
        self.assertTrue(all(v['name'].startswith('credit-selectel_') for v in model['volumes'].values()))
        self.assertEqual(model['services']['feed']['volumes'][0]['source'], 'feed-bundle')
        self.assertTrue({'ollama', 'ollama-init'} <= set(model['services']))
        self.assertEqual(model['services']['assistant']['environment']['LLM_MODEL'], 'qwen2.5:3b')
        self.assertEqual(model['services']['assistant']['environment']['LLM_BASE_URL'], 'http://ollama:11434/v1')
        self.assertEqual(model['services']['ocr']['environment']['LLM_BASE_URL'], 'http://ollama:11434/v1')
        self.assertEqual(model['services']['ocr']['environment']['LLM_MODEL'], 'qwen2.5:3b')
        self.assertEqual(model['services']['ocr']['environment']['OCR_ENGINE'], 'tesseract')
        self.assertIn('ollama-init', model['services']['ocr']['depends_on'])

    def test_restore_refuses_existing_volumes_before_any_write(self):
        deployment = self.deployment()
        archive = self.root / 'objects.tar.gz'
        archive.write_bytes(b'archive-for-preflight-test')
        (self.root / 'manifest.json').write_text(json.dumps({'format': 1, 'volumes': {
            'objects': {'archive': archive.name, 'sha256': server.digest(archive)},
        }}))
        with patch.object(deployment, 'model', return_value={'volumes': {'objects': {'name': 'existing_objects'}}}), \
             patch.object(deployment, 'archive') as extract, \
             patch.object(server.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            with self.assertRaisesRegex(ValueError, 'no existing volumes'):
                deployment.restore(self.root)
        extract.assert_not_called()
        self.assertEqual(run.call_args.args[0][-3:], ['volume', 'inspect', 'existing_objects'])

    def test_restore_creates_compose_labels_for_the_next_start(self):
        deployment = self.deployment()
        archive = self.root / 'objects.tar.gz'
        archive.write_bytes(b'test')
        (self.root / 'manifest.json').write_text(json.dumps({'format': 1, 'volumes': {
            'objects': {'archive': archive.name, 'sha256': server.digest(archive)},
        }}))
        with patch.object(deployment, 'model', return_value={'volumes': {'objects': {'name': 'credit-selectel_objects'}}}), \
             patch.object(deployment, 'archive') as extract, \
             patch.object(deployment, 'run') as create, \
             patch.object(server.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
            deployment.restore(self.root)
        self.assertIn('com.docker.compose.project=credit-selectel', create.call_args.args[0])
        self.assertIn('com.docker.compose.volume=objects', create.call_args.args[0])
        extract.assert_called_once()

    def test_literal_dollar_in_provider_key_survives_reinitialization_and_compose(self):
        content = self.env_file.read_text().replace('LLM_API_KEY=\n', "LLM_API_KEY='provider-$literal#token'\n").replace('LLM_MODE=local', 'LLM_MODE=external')
        self.env_file.write_text(content)
        with patch.object(server, 'ROOT', self.handoff_root):
            server.initialize(self.env_file)
        try:
            model = self.deployment().model()
        except FileNotFoundError:
            self.skipTest('Docker Compose CLI is not installed')
        self.assertEqual(server.read_env(self.env_file)['LLM_API_KEY'], 'provider-$literal#token')
        # `compose config` escapes dollars for safe reuse as a Compose input file.
        self.assertEqual(model['services']['assistant']['environment']['LLM_API_KEY'].replace('$$', '$'),
                         'provider-$literal#token')
        self.assertNotIn('ollama', model['services'])

    def test_backup_restarts_services_if_archive_fails(self):
        deployment = self.deployment()
        def run(command, **kwargs):
            return SimpleNamespace(stdout='backend\nedge\n', returncode=0)
        with patch.object(deployment, 'model', return_value={'volumes': {'objects': {'name': 'test_objects'}}}), \
             patch.object(deployment, 'run', side_effect=run) as calls, \
             patch.object(deployment, 'archive', side_effect=RuntimeError('storage unavailable')):
            with self.assertRaises(RuntimeError):
                deployment.backup(self.root / 'backups')
        self.assertIn('stop', calls.call_args_list[2].args[0])
        self.assertEqual(calls.call_args.args[0][-2:], ['backend', 'edge'])
        self.assertIn('--no-deps', calls.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
