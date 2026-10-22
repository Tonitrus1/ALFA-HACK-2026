#!/usr/bin/env python3
"""Dedicated native acceptance environment; never touches existing demo databases.

Uses explicitly supplied PostgreSQL binaries and existing Python environments.
Secrets, database cluster and PIDs live only in .local/integration-native/.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
LOCAL=ROOT/'.local/integration-native'
PORT=55440

def run(args,**kw):return subprocess.run([str(x) for x in args],check=True,**kw)
def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['up','down']);p.add_argument('--pg-bin',type=Path)
    p.add_argument('--risk-python',type=Path);p.add_argument('--feed-python',type=Path);p.add_argument('--feed-bundle',type=Path)
    a=p.parse_args();LOCAL.mkdir(parents=True,exist_ok=True)
    config=LOCAL/'config.json'
    if a.command=='down':
        if not config.exists():return
        cfg=json.loads(config.read_text())
        for file in LOCAL.glob('*.pid'):
            try:os.killpg(int(file.read_text()),signal.SIGTERM)
            except ProcessLookupError:pass
            file.unlink()
        if (LOCAL/'pgdata').exists():run([Path(cfg['pgBin'])/'pg_ctl','-D',LOCAL/'pgdata','stop','-m','fast','-w'],stdout=subprocess.DEVNULL)
        print('Dedicated native services stopped; data preserved.');return
    if not all((a.pg_bin,a.risk_python,a.feed_python,a.feed_bundle)):p.error('up requires pg-bin, risk-python, feed-python, feed-bundle')
    if list(LOCAL.glob('*.pid')):raise SystemExit('Existing PID files; run down before up.')
    if not config.exists():
        cfg=dict(password=secrets.token_urlsafe(32),token=secrets.token_urlsafe(36),pgBin=str(a.pg_bin.resolve()))
        fd=os.open(config,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as out:json.dump(cfg,out)
    cfg=json.loads(config.read_text());cluster=LOCAL/'pgdata';pg=Path(cfg['pgBin']);pw=LOCAL/'init-password'
    if not cluster.exists():
        pw.write_text(cfg['password']);pw.chmod(0o600)
        try:run([pg/'initdb','-D',cluster,'-U','integration_admin','--pwfile',pw,'--auth-host=scram-sha-256','--auth-local=trust','--encoding=UTF8','--locale=C'],stdout=subprocess.DEVNULL)
        finally:pw.unlink()
        with (cluster/'postgresql.conf').open('a') as out:out.write(f"\nport={PORT}\nlisten_addresses='127.0.0.1'\nunix_socket_directories='{LOCAL}'\n")
    if subprocess.run([str(pg/'pg_ctl'),'-D',str(cluster),'status'],stdout=subprocess.DEVNULL).returncode:
        run([pg/'pg_ctl','-D',cluster,'-l',LOCAL/'postgres.log','start','-w'],stdout=subprocess.DEVNULL)
    import psycopg
    from psycopg import sql
    dsn=f"postgresql://integration_admin:{cfg['password']}@127.0.0.1:{PORT}/postgres"
    with psycopg.connect(dsn,autocommit=True) as db:
        if not db.execute("select 1 from pg_roles where rolname='ml_runtime'").fetchone():db.execute(sql.SQL('create role ml_runtime login password {}').format(sql.Literal(cfg['password'])))
        if not db.execute("select 1 from pg_database where datname='integration_ml'").fetchone():db.execute('create database integration_ml')
    admin_dsn=dsn.replace('/postgres','/integration_ml')
    with psycopg.connect(admin_dsn) as db:
        db.execute('create table if not exists public.integration_migrations(name text primary key,sha text not null)')
        import hashlib
        for f in sorted((ROOT/'ml/migrations').glob('*.sql')):
            sha=hashlib.sha256(f.read_bytes()).hexdigest()
            old=db.execute('select sha from public.integration_migrations where name=%s',(f.name,)).fetchone()
            if old:
                if old[0]!=sha:raise RuntimeError('Applied migration changed: '+f.name)
            else:db.execute(f.read_text());db.execute('insert into public.integration_migrations values(%s,%s)',(f.name,sha))
    env=os.environ.copy();env.update(PYTHONPATH=str(ROOT/'ml'),ML_DATABASE_URL=admin_dsn.replace('integration_admin:','ml_runtime:'),
        ML_INTERNAL_TOKEN=cfg['token'],ML_SERVICE_TOKEN=cfg['token'],MODEL_BUNDLE=str(ROOT/'ml/artifacts/baseline'),
        FEED_BUNDLE=str(a.feed_bundle.resolve()),RISK_BASE_URL='http://127.0.0.1:18001',FEED_BASE_URL='http://127.0.0.1:18002',
        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',FEED_CPU_THREADS='2',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    for name,python,module,port,factory,header in [('risk',a.risk_python,'scoring.server:app',18001,False,'Authorization'),
            ('feed',a.feed_python,'feed.server:create_app',18002,True,'X-Service-Token'),
            ('bridge',a.risk_python,'bridge.server:create_app',18000,True,'X-Service-Token')]:
        with (LOCAL/(name+'.log')).open('ab') as log:
            process=subprocess.Popen([str(python.absolute()),'-m','uvicorn',module,*(['--factory'] if factory else []),'--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True)
        (LOCAL/(name+'.pid')).write_text(str(process.pid))
        for _ in range(200):
            if process.poll() is not None:raise RuntimeError(name+' failed; inspect dedicated log')
            try:
                auth=('Bearer ' if header=='Authorization' else '')+cfg['token']
                with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/health',headers={header:auth}),timeout=2) as r:
                    if r.status==200:break
            except OSError:time.sleep(.2)
        else:raise RuntimeError(name+' readiness timeout')
    print('Real Risk, offline E5 and durable bridge ready on dedicated ports 18001/18002/18000. Credentials were not printed.')

if __name__=='__main__':main()
