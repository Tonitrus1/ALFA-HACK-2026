#!/usr/bin/env python3
"""Deploy the entire service to one Selectel VM. Uses independent secrets and volumes."""
import argparse
import hashlib
import http.cookiejar
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import urllib.error
import urllib.request

from deploy import SECRET_KEYS

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'deploy/selectel/.env.selectel.example'


def read_env(path):
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or key in values:
            raise ValueError('Invalid or duplicate environment key; use one KEY=value per line')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            quote = value[0]
            value = value[1:-1]
            if quote == "'":
                value = value.replace("\\'", "'")
        values[key] = value
    return values


def domain_name(value):
    value = value.strip().rstrip('.').encode('idna').decode('ascii').lower()
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise ValueError('Use a DNS domain, not an IP address')
    if len(value) > 253 or '.' not in value or any(
        not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
        for label in value.split('.')
    ):
        raise ValueError('PUBLIC_DOMAIN must be a DNS name without a scheme, port or path')
    return value


def private_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    temporary.chmod(0o600)
    temporary.replace(path)


def initialize(path, domain=None, email=None, project=None):
    existing = read_env(path) if path.exists() else {}
    defaults = read_env(TEMPLATE)
    supplied = {'PUBLIC_DOMAIN': domain, 'ACME_EMAIL': email, 'COMPOSE_PROJECT_NAME': project}
    for key, value in supplied.items():
        if value is not None:
            if existing.get(key) and existing[key] != value:
                raise ValueError(f'{key} already exists; edit the server environment explicitly to change it')
            defaults[key] = value
    values = {key: existing.get(key) or (secrets.token_urlsafe(36) if key in SECRET_KEYS else value)
              for key, value in defaults.items()}
    for key, value in supplied.items():
        if value is not None and not existing.get(key):
            values[key] = value
    values['PUBLIC_DOMAIN'] = domain_name(values['PUBLIC_DOMAIN'])
    validate(values, require_llm=False)
    # Existing secrets and extra provider options survive repeated initialization.
    values = {**existing, **values}
    # Quote values containing Compose interpolation characters; preserve their literal values.
    def dotenv(value):
        if any(c in value for c in '\r\n\x00'):
            raise ValueError('Environment values must be single-line')
        return "'" + value.replace("'", "\\'") + "'" if any(c in value for c in "$ #'\"") else value
    private_write(path, '# Private Selectel installation settings. Do not commit.\n' +
                  ''.join(f'{key}={dotenv(value)}\n' for key, value in values.items()))
    handoff = ROOT / '.local/selectel/cabinet-access.md'
    private_write(handoff, '# Доступ к серверному кабинету\n\n' +
                  f'Адрес: https://{values["PUBLIC_DOMAIN"]}/login\n\n' +
                  '| Компания | Логин | Пароль |\n|---|---|---|\n' +
                  f'| А | company-a | {values["CABINET_A_PASSWORD"]} |\n' +
                  f'| Б | company-b | {values["CABINET_B_PASSWORD"]} |\n')
    print('Server configuration and private access handoff prepared. Existing passwords preserved.')


def validate(values, require_llm=True):
    domain_name(values.get('PUBLIC_DOMAIN', ''))
    if not re.fullmatch(r'[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+\.[^\s@\x00-\x1f]+', values.get('ACME_EMAIL', '')):
        raise ValueError('Set a valid ACME_EMAIL')
    project = values.get('COMPOSE_PROJECT_NAME', '')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}', project) or project == 'credit-integrated-mvp':
        raise ValueError('Use a separate COMPOSE_PROJECT_NAME, e.g. credit-selectel')
    for key in SECRET_KEYS:
        if len(values.get(key, '')) < 32:
            raise ValueError(f'Set a strong nonempty {key}; init generates it for new installations')
    mode = values.get('LLM_MODE', 'external')
    if mode not in ('local', 'external'):
        raise ValueError('LLM_MODE must be local or external')
    if mode == 'local':
        if values.get('LOCAL_RAG_MODEL', 'qwen2.5:3b') != 'qwen2.5:3b':
            raise ValueError('This CPU profile requires LOCAL_RAG_MODEL=qwen2.5:3b')
    if require_llm and not values.get('LLM_API_KEY', '').strip():
        raise ValueError('Set LLM_API_KEY for the unchanged OCR configuration; local RAG does not require it')
    if require_llm and not values.get('LLM_BASE_URL', '').startswith('https://'):
        raise ValueError('Use an HTTPS LLM_BASE_URL')
    required_models = ('OCR_LLM_MODEL',) if mode == 'local' else ('ASSISTANT_LLM_MODEL', 'OCR_LLM_MODEL')
    if require_llm and any(not values.get(key, '').strip() for key in required_models):
        raise ValueError('Set the model IDs available from your LLM provider')


class Deployment:
    def __init__(self, env_file, context=None):
        self.env_file = env_file.resolve()
        self.values = read_env(self.env_file)
        self.docker = ['docker'] + (['--context', context] if context else [])
        self.compose = self.docker + ['compose', '--env-file', str(self.env_file),
                       '--project-name', self.values['COMPOSE_PROJECT_NAME'],
                       '-f', str(ROOT / 'compose.yaml')]
        if self.values.get('LLM_MODE', 'external') == 'local':
            self.compose += ['-f', str(ROOT / 'deploy/compose.local-llm.yaml')]
        self.compose += ['-f', str(ROOT / 'deploy/selectel/compose.yaml')]
        # Compose shell variables override --env-file. Remove all installation keys so a
        # caller's local/project credentials cannot silently replace the server settings.
        self.environment = {k: v for k, v in os.environ.items() if k not in self.values}
        for key in ('COMPOSE_FILE', 'COMPOSE_PROFILES', 'COMPOSE_PROJECT_NAME', 'FEED_BUNDLE_PATH'):
            self.environment.pop(key, None)

    def run(self, command, **kwargs):
        return subprocess.run(command, cwd=ROOT, env=self.environment, check=True, **kwargs)

    def version(self):
        version = self.run(self.docker + ['compose', 'version', '--short'], capture_output=True, text=True).stdout
        numbers = re.search(r'(\d+)\.(\d+)\.(\d+)', version)
        if not numbers or tuple(map(int, numbers.groups())) < (2, 24, 4):
            raise ValueError('Docker Compose >=2.24.4 is required')

    def model(self):
        return json.loads(self.run(self.compose + ['config', '--format', 'json'], capture_output=True, text=True).stdout)

    def build(self):
        built = set()
        for name, service in self.model()['services'].items():
            identity = service.get('image', name)
            if service.get('build') and identity not in built:
                self.run(self.compose + ['build', name])
                built.add(identity)

    def backup(self, output):
        model = self.model()
        volumes = {key: value['name'] for key, value in model['volumes'].items()}
        for name in volumes.values():
            self.run(self.docker + ['volume', 'inspect', name], stdout=subprocess.DEVNULL)
        running = self.run(self.compose + ['ps', '--status', 'running', '--services'],
                           capture_output=True, text=True).stdout.splitlines()
        output = output.resolve() / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        output.mkdir(parents=True, mode=0o700)
        try:
            self.run(self.compose + ['stop', '--timeout', '60'])
            revision = self.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
            manifest = {'format': 1, 'revision': revision, 'domain': self.values['PUBLIC_DOMAIN'], 'volumes': {}}
            for key, name in volumes.items():
                archive = key + '.tar.gz'
                self.archive(name, output, archive, restore=False)
                manifest['volumes'][key] = {'archive': archive, 'sha256': digest(output / archive)}
            shutil.copyfile(self.env_file, output / '.env.selectel')
            (output / '.env.selectel').chmod(0o600)
            private_write(output / 'manifest.json', json.dumps(manifest, indent=2) + '\n')
            print('Cold backup complete: ' + str(output))
        finally:
            if running:
                self.run(self.compose + ['up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '1800'] + running)

    def archive(self, volume, directory, archive, *, restore):
        source = f'type=volume,src={volume},dst=/volume' + ('' if restore else ',readonly')
        target = f'type=bind,src={directory},dst=/backup' + (',readonly' if restore else '')
        self.run(self.docker + ['run', '--rm', '--pull', 'never', '--network', 'none',
                 '--mount', source, '--mount', target, '--entrypoint', 'tar', 'postgres:17.11-bookworm',
                 '-xzf' if restore else '-czf', '/backup/' + archive, '-C', '/volume'] + ([] if restore else ['.']))

    def restore(self, source):
        source = source.resolve()
        manifest = json.loads((source / 'manifest.json').read_text())
        volumes = self.model()['volumes']
        if manifest['format'] != 1 or set(manifest['volumes']) != set(volumes):
            raise ValueError('Backup volume set does not match this release')
        backup_values = read_env(source / '.env.selectel')
        if any(self.values.get(key) != backup_values.get(key) for key in SECRET_KEYS):
            raise ValueError('Restore the private environment from the backup before restoring its volumes')
        for key, item in manifest['volumes'].items():
            if item['archive'] != key + '.tar.gz' or digest(source / item['archive']) != item['sha256']:
                raise ValueError('Backup checksum mismatch')
        for value in volumes.values():
            found = subprocess.run(self.docker + ['volume', 'inspect', value['name']], env=self.environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if found.returncode == 0:
                raise ValueError('Restore requires a fresh project with no existing volumes; nothing overwritten')
        created = []
        try:
            for key, value in volumes.items():
                self.run(self.docker + ['volume', 'create', '--label',
                         'com.docker.compose.project=' + self.values['COMPOSE_PROJECT_NAME'], '--label',
                         'com.docker.compose.volume=' + key, value['name']], stdout=subprocess.DEVNULL)
                created.append(value['name'])
                self.archive(value['name'], source, manifest['volumes'][key]['archive'], restore=True)
        except Exception:
            for name in reversed(created):
                subprocess.run(self.docker + ['volume', 'rm', name], stdout=subprocess.DEVNULL, env=self.environment)
            raise
        print('Volumes restored. Start the same release with up --no-build.')


def digest(path):
    with path.open('rb') as stream:
        checksum = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
        return checksum.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'config', 'doctor', 'build', 'up', 'down', 'status', 'logs', 'check', 'backup', 'restore'])
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env.selectel')
    parser.add_argument('--domain')
    parser.add_argument('--email')
    parser.add_argument('--project')
    parser.add_argument('--context')
    parser.add_argument('--no-build', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / '.local/selectel/backups')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    if args.command == 'init':
        initialize(args.env_file, args.domain, args.email, args.project)
        return
    deployment = Deployment(args.env_file, args.context)
    validate(deployment.values, require_llm=args.command in ('doctor', 'up', 'check'))
    deployment.version()
    if args.command == 'config':
        deployment.run(deployment.compose + ['config', '--quiet'])
        print('Server Compose configuration is valid. Secret values are not displayed.')
    elif args.command == 'doctor':
        info = json.loads(deployment.run(deployment.docker + ['info', '--format', '{{json .}}'], capture_output=True, text=True).stdout)
        if info['OSType'] != 'linux' or info['Architecture'] not in ('amd64', 'x86_64'):
            raise ValueError('Use a Linux x86_64 VM for this deployment')
        deployment.run(deployment.compose + ['config', '--quiet'])
        print(f'Docker ready; RAM {info["MemTotal"] / 1024**3:.1f} GiB. LLM mode: {deployment.values.get("LLM_MODE", "external")}.')
        print('For CPU Qwen 3B: start with 8 vCPU / 16 GB RAM / 160 GB disk; measure whole-stack memory and latency.')
    elif args.command in ('build', 'up'):
        if args.command == 'build' or not args.no_build:
            deployment.build()
        if args.command == 'up':
            deployment.run(deployment.compose + ['up', '-d', '--no-build', '--wait', '--wait-timeout', '1800'])
            print('Cabinet: https://' + deployment.values['PUBLIC_DOMAIN'])
    elif args.command == 'down':
        deployment.run(deployment.compose + ['down'])
    elif args.command == 'status':
        deployment.run(deployment.compose + ['ps', '--all'])
    elif args.command == 'logs':
        deployment.run(deployment.compose + ['logs', '--tail', '100', '--follow'])
    elif args.command == 'check':
        check_https(deployment.values)
    elif args.command == 'backup':
        deployment.backup(args.output)
    elif args.command == 'restore':
        if not args.backup:
            parser.error('restore requires --backup PATH')
        deployment.restore(args.backup)


def check_https(values):
    origin = 'https://' + values['PUBLIC_DOMAIN']
    for suffix in ('A', 'B'):
        jar = http.cookiejar.CookieJar()
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        body = json.dumps({'login': 'company-' + suffix.lower(), 'password': values['CABINET_' + suffix + '_PASSWORD']}).encode()
        request = urllib.request.Request(origin + '/api/v1/auth/login', data=body,
                  headers={'Origin': origin, 'Content-Type': 'application/json'})
        with client.open(request, timeout=90) as response:
            session = json.load(response)
            cookie = response.headers.get('Set-Cookie', '')
            if not all(flag in cookie for flag in ('Secure', 'HttpOnly', 'SameSite=Strict')):
                raise ValueError('Session cookie flags are incorrect')
        own = 'company-' + suffix.lower()
        if session['companyId'] != own:
            raise ValueError('Incorrect company in session')
        with client.open(origin + '/api/v1/companies', timeout=30) as response:
            companies = json.load(response)['items']
        if [item['companyId'] for item in companies] != [own]:
            raise ValueError('Company isolation failed')
        foreign = 'company-b' if suffix == 'A' else 'company-a'
        try:
            client.open(origin + '/api/v1/companies/' + foreign, timeout=30).close()
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
        else:
            raise ValueError('Foreign company was accessible')
    print('HTTPS, password login, secure cookies and company isolation verified. No LLM requests sent.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Do not print command arguments or HTTP response bodies containing credentials.
        print('Selectel operation stopped: ' + (str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
