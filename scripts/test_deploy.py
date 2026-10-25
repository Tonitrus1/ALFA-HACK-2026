"""Deployment invariants: configuration must never rotate database passwords."""
import importlib.util
import hashlib
import json
import runpy
from pathlib import Path
import tempfile
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deployment', Path(__file__).with_name('deploy.py'))
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


class ConfigurationTests(unittest.TestCase):
    def test_interrupted_package_download_retries_complete_operation(self):
        installer = Path(__file__).resolve().parents[1] / 'deploy/install.py'
        with patch('sys.argv', [str(installer), 'example==1.0']), patch('subprocess.run', side_effect=[
            SimpleNamespace(returncode=1), SimpleNamespace(returncode=0)
        ]) as run, patch('time.sleep') as sleep:
            runpy.run_path(str(installer), run_name='__main__')
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0], run.call_args_list[1])
        sleep.assert_called_once_with(5)

    def test_windows_source_matches_published_model_after_lf_restoration(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / 'ml/artifacts/baseline/manifest.json').read_text(encoding='utf-8'))
        source = (root / 'ml/scoring/features.py').read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(hashlib.sha256(source).hexdigest(), manifest['featureCodeDigest'])
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target / 'features.py').write_bytes(source.replace(b'\n', b'\r\n'))
            binary = b'\x00\xff\r\n'
            (target / 'model.joblib').write_bytes(binary)
            subprocess.run([deployment.sys.executable, str(root / 'deploy/normalize_text.py'), folder], check=True)
            self.assertEqual((target / 'features.py').read_bytes(), source)
            self.assertEqual((target / 'model.joblib').read_bytes(), binary)

    def test_repeat_preserves_credentials_and_adds_only_missing_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.env.example').write_text('BACKEND_DB_PASSWORD=\nLLM_API_KEY=\nNEW_SETTING=value\n')
            (root / '.env').write_text('# custom\nBACKEND_DB_PASSWORD=existing\nLLM_API_KEY=private-value\n')
            deployment.configure(root)
            first = (root / '.env').read_bytes()
            deployment.configure(root)
            self.assertEqual(first, (root / '.env').read_bytes())
            self.assertIn(b'BACKEND_DB_PASSWORD=existing', first)
            self.assertIn(b'LLM_API_KEY=private-value', first)
            self.assertEqual(first.count(b'NEW_SETTING=value'), 1)

    def test_fresh_config_generates_nonempty_distinct_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.env.example').write_text('BACKEND_DB_PASSWORD=\nML_DB_PASSWORD=\nLLM_API_KEY=\n')
            deployment.configure(root)
            values = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines())
            self.assertGreaterEqual(len(values['BACKEND_DB_PASSWORD']), 32)
            self.assertNotEqual(values['BACKEND_DB_PASSWORD'], values['ML_DB_PASSWORD'])
            self.assertEqual(values['LLM_API_KEY'], '')

    def test_core_build_excludes_optional_services_and_deduplicates_images(self):
        services = {
            'feed-init': {'image': 'feed', 'build': {}},
            'feed': {'image': 'feed', 'build': {}, 'depends_on': {'feed-init': {}}},
            'assistant': {'build': {}},
            'gateway': {'build': {}, 'depends_on': {'feed': {}}},
        }
        with patch.object(deployment, 'configure'), patch('sys.argv', ['deploy.py', 'build', '--mode', 'core']), patch.object(
            deployment.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps({'services': services}))
        ) as run:
            deployment.main()
        builds = [call.args[0][-1] for call in run.call_args_list if 'build' in call.args[0]]
        self.assertEqual(builds, ['feed-init', 'gateway'])

    def test_down_never_removes_volumes(self):
        with patch('sys.argv', ['deploy.py', 'down']), patch.object(deployment.subprocess, 'run') as run:
            deployment.main()
        command = run.call_args.args[0]
        self.assertEqual(command[-1], 'down')
        self.assertNotIn('--volumes', command)
        self.assertNotIn('-v', command)


if __name__ == '__main__':
    unittest.main()
