#!/usr/bin/env python3
"""Cross-platform deployment entry point. Requires Python 3.10+ and Compose v2."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SECRET_KEYS = ('BACKEND_DB_PASSWORD', 'ML_ADMIN_PASSWORD', 'ML_DB_PASSWORD',
               'ML_SERVICE_TOKEN', 'ASSISTANT_SERVICE_TOKEN', 'OCR_API_KEY',
               'DOCUMENT_OCR_TOKEN', 'SEARXNG_SECRET', 'CABINET_A_PASSWORD', 'CABINET_B_PASSWORD')


def configure(root=ROOT):
    """Only add missing keys. Never rotate existing credentials, including empty values."""
    target = root / '.env'
    existing = target.read_text(encoding='utf-8-sig') if target.exists() else ''
    present = {line.split('=', 1)[0].strip() for line in existing.splitlines()
               if '=' in line and not line.lstrip().startswith('#')}
    defaults = dict(line.split('=', 1) for line in (root / '.env.example').read_text(encoding='utf-8').splitlines()
                    if '=' in line and not line.lstrip().startswith('#'))
    missing = {key: (secrets.token_urlsafe(36) if key in SECRET_KEYS else value)
               for key, value in defaults.items() if key not in present}
    if missing:
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        with os.fdopen(os.open(target, flags, 0o600), 'a', encoding='utf-8', newline='\n') as stream:
            stream.write(('\n' if existing else '') + ''.join(f'{k}={v}\n' for k, v in missing.items()))
    values = dict(line.split('=', 1) for line in target.read_text(encoding='utf-8-sig').splitlines()
                  if '=' in line and not line.lstrip().startswith('#'))
    if all(values.get(key) for key in ('CABINET_A_PASSWORD', 'CABINET_B_PASSWORD')):
        handoff = root / '.local' / 'cabinet-access.md'
        handoff.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(handoff, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w', encoding='utf-8') as stream:
            stream.write('# Доступ в кабинет\n\nАдрес: http://127.0.0.1:8080/login\n\n'
                         '| Компания | Логин | Пароль |\n|---|---|---|\n'
                         f'| А | company-a | {values["CABINET_A_PASSWORD"]} |\n'
                         f'| Б | company-b | {values["CABINET_B_PASSWORD"]} |\n')
        handoff.chmod(0o600)
    print('Configuration ready; existing credentials preserved. Secrets are not displayed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'doctor', 'build', 'up', 'down', 'status', 'logs'])
    parser.add_argument('--mode', choices=['core', 'full', 'local'], default='full')
    parser.add_argument('--project', help='Keep the same project name to reuse its data volumes')
    parser.add_argument('--context', help='Docker context; omitted uses your current context')
    parser.add_argument('--parallel', type=int, default=1, help='Concurrent builds (default: 1 to reduce peak RAM)')
    parser.add_argument('--no-build', action='store_true', help='Start previously built images')
    args = parser.parse_args()
    if args.parallel < 1:
        parser.error('--parallel must be positive')
    if args.command in ('init', 'up', 'build'):
        configure()
    if args.command == 'init':
        return
    docker = ['docker'] + (['--context', args.context] if args.context else [])
    compose = docker + ['compose', '--parallel', str(args.parallel), '-f', str(ROOT / 'compose.yaml')]
    if args.mode == 'local':
        compose += ['-f', str(ROOT / 'deploy/compose.local-llm.yaml')]
    if args.project:
        compose += ['--project-name', args.project]

    def run(command):
        subprocess.run(command, cwd=ROOT, check=True)

    if args.command == 'doctor':
        run(docker + ['compose', 'version'])
        info = subprocess.run(docker + ['info', '--format', '{{.OSType}} {{.Architecture}} {{.NCPU}} {{.MemTotal}}'],
                              cwd=ROOT, check=True, capture_output=True, text=True, encoding='utf-8')
        system, architecture, cpus, memory = info.stdout.strip().split()
        if system != 'linux':
            raise SystemExit('Switch Docker Desktop to Linux containers, then run doctor again.')
        gib = int(memory) / (1024 ** 3)
        print(f'Docker: {system}/{architecture}; CPUs: {cpus}; allocated RAM: {gib:.1f} GiB')
        if gib < (8 if args.mode == 'core' else 12):
            print('Resource warning: below the recommended RAM for this mode. Prefer core or increase Docker memory.')
        if architecture not in ('amd64', 'x86_64'):
            print('Platform warning: this architecture has not passed full acceptance; see docs/deployment.md.')
        run(compose + ['config', '--quiet'])
        print('Configuration is valid. Allow >=8 GB Docker RAM for core, >=12 GB for full; local LLM needs additional RAM/VRAM.')
        print('First build and model preparation need internet and substantial free disk space (recommend >=30 GB).')
    elif args.command in ('build', 'up'):
        # Targeted core startup does not pull/build the optional AI services.
        targets = ['gateway'] if args.mode == 'core' else []
        if args.command == 'build' or not args.no_build:
            # Compose Bake can ignore --parallel for build targets. Invoke one
            # service at a time by default, deduplicating shared images.
            if args.parallel == 1:
                result = subprocess.run(compose + ['config', '--format', 'json'], cwd=ROOT,
                                        check=True, capture_output=True, text=True, encoding='utf-8')
                services = json.loads(result.stdout)['services']
                selected = set()
                def include(name):
                    if name in selected:
                        return
                    selected.add(name)
                    for dependency in services[name].get('depends_on', {}):
                        include(dependency)
                for name in targets or services:
                    include(name)
                built = set()
                for name, service in services.items():
                    identity = service.get('image', name)
                    if name in selected and 'build' in service and identity not in built:
                        run(compose + ['build', name])
                        built.add(identity)
            else:
                run(compose + ['build'] + (['--with-dependencies', 'gateway'] if targets else []))
        if args.command == 'up':
            run(compose + ['up', '-d', '--wait', '--wait-timeout', '1200'] + targets)
            print('Cabinet: http://127.0.0.1:8080')
    elif args.command == 'down':
        run(compose + ['down'])  # Intentionally no --volumes: user data is retained.
    elif args.command == 'status':
        run(compose + ['ps', '--all'])
    else:
        run(compose + ['logs', '--tail', '100', '--follow'])


if __name__ == '__main__':
    try:
        main()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f'Deployment stopped: {exc}. Run doctor and inspect service logs.', file=sys.stderr)
        sys.exit(1)
