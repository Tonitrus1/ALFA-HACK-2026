#!/usr/bin/env python3
"""Clear the A/B cabinets, preserving accounts, catalog, models and a private database backup."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='credit-integrated-mvp')
    parser.add_argument('--context')
    args = parser.parse_args()
    docker = ['docker'] + (['--context', args.context] if args.context else [])
    compose = docker + ['compose', '-f', str(ROOT / 'compose.yaml'), '--project-name', args.project]

    def run(command, **kwargs):
        return subprocess.run(command, cwd=ROOT, check=True, **kwargs)

    running = run(compose + ['ps', '--status', 'running', '--services'], capture_output=True, text=True).stdout.splitlines()
    writers = [name for name in ('backend', 'ocr-worker') if name in running]
    if writers:
        run(compose + ['stop'] + writers)
    try:
        run(compose + ['up', '-d', '--no-deps', '--wait', 'backend-db'])
        backup = ROOT / '.local' / 'backups' / ('cabinets-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.dump')
        backup.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            run(compose + ['exec', '-T', 'backend-db', 'pg_dump', '-U', 'credit', '-d', 'credit', '-Fc'], stdout=stream)
        if not backup.stat().st_size:
            raise RuntimeError('Database backup is empty; reset aborted')
        run(compose + ['exec', '-T', 'backend-db', 'psql', '-X', '-U', 'credit', '-d', 'credit', '-v', 'ON_ERROR_STOP=1'],
            input=(ROOT / 'scripts/sql/reset_demo_cabinets.sql').read_bytes())
        print('Cabinets A/B cleared. Backup: ' + str(backup))
    finally:
        if writers:
            run(compose + ['start'] + writers)
        if 'backend-db' not in running:
            run(compose + ['stop', 'backend-db'])


if __name__ == '__main__':
    main()
