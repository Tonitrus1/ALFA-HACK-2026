#!/usr/bin/env python3
"""Start the packaged Java backend against the dedicated acceptance PostgreSQL."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
LOCAL=ROOT/'.local/integration-native'
p=argparse.ArgumentParser();p.add_argument('--java',type=Path,required=True);p.add_argument('--jar',type=Path,default=ROOT/'backend/app/target/credit-app-0.1.0-SNAPSHOT.jar');a=p.parse_args()
cfg=json.loads((LOCAL/'config.json').read_text())
if (LOCAL/'backend.pid').exists():raise SystemExit('Existing backend PID file; stop dedicated native environment first.')
import psycopg
with psycopg.connect(host='127.0.0.1',port=55440,dbname='postgres',user='integration_admin',password=cfg['password'],autocommit=True) as db:
    if not db.execute("select 1 from pg_database where datname='integration_backend'").fetchone():db.execute('create database integration_backend')
env=os.environ.copy();env.update(SPRING_PROFILES_ACTIVE='demo',DB_URL='jdbc:postgresql://127.0.0.1:55440/integration_backend',
    DB_USER='integration_admin',DB_PASSWORD=cfg['password'],ML_MODE='http',ML_BASE_URL='http://127.0.0.1:18000',
    ML_SERVICE_TOKEN=cfg['token'],SERVER_PORT='18080',SERVER_ADDRESS='127.0.0.1',CREDIT_SCANNER_ENABLED='false',OBJECTS_ROOT=str(LOCAL/'objects'))
with (LOCAL/'backend.log').open('ab') as log:
    process=subprocess.Popen([str(a.java.absolute()),'-jar',str(a.jar.absolute())],env=env,cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
(LOCAL/'backend.pid').write_text(str(process.pid))
for _ in range(120):
    if process.poll() is not None:raise RuntimeError('Backend exited; inspect dedicated backend.log')
    try:
        with urllib.request.urlopen('http://127.0.0.1:18080/demo/api/v1/accounts',timeout=1) as r:
            if r.status==200:break
    except OSError:time.sleep(.25)
else:raise RuntimeError('Backend readiness timeout')
print('Packaged backend ready at http://127.0.0.1:18080. Dedicated synthetic database; credentials not printed.')
