"""Retry a complete pip operation, including interrupted wheel downloads."""
import subprocess
import os
import sys
import time

environment = os.environ.copy()
environment.setdefault('PIP_DEFAULT_TIMEOUT', '120')
environment.setdefault('PIP_RETRIES', '8')
for attempt in range(1, 4):
    result = subprocess.run([sys.executable, '-m', 'pip', 'install', *sys.argv[1:]], env=environment)
    if result.returncode == 0:
        break
    if attempt == 3:
        sys.exit(result.returncode)
    print(f'Package installation interrupted; retrying ({attempt}/3).', flush=True)
    time.sleep(5)
