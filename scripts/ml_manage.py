import argparse,hashlib,json,os,secrets,signal,subprocess,time,urllib.request
from pathlib import Path
import psycopg
from psycopg import sql
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT)
PGPORT=int(os.environ.get('ML_DATABASE_PORT','55432'));APIPORT=int(os.environ.get('ML_API_PORT','8001'))
LOCAL=ROOT/'.local';CLUSTER=LOCAL/'pgdata';PG=LOCAL/'tools/pg/bin';DBNAME='credit_scoring_demo';CONFIG=LOCAL/'runtime.json'
def run(args,**kw):return subprocess.run([str(x) for x in args],check=True,**kw)
def config():
    LOCAL.mkdir(exist_ok=True)
    if not CONFIG.exists():
        CONFIG.write_text(json.dumps({'adminPassword':secrets.token_urlsafe(24),'mlPassword':secrets.token_urlsafe(24),'ML_INTERNAL_TOKEN':secrets.token_urlsafe(32),'databasePort':PGPORT,'apiPort':APIPORT}));CONFIG.chmod(0o600)
    return json.loads(CONFIG.read_text())
def admin(database=DBNAME):
    return psycopg.connect(host='127.0.0.1',port=config().get('databasePort',PGPORT),dbname=database,user='demo_admin',password=config()['adminPassword'],autocommit=True)
def guard():assert (LOCAL/'cluster-marker').read_text()==str(CLUSTER.resolve()),'Not this dedicated local cluster'
def db_start(offline=False):
    cfg=config()
    if not CLUSTER.exists():
        pw=LOCAL/'init-password';pw.write_text(cfg['adminPassword']);pw.chmod(0o600)
        try:run([PG/'initdb','-D',CLUSTER,'-U','demo_admin','--pwfile',pw,'--auth-local=trust','--auth-host=scram-sha-256','--encoding=UTF8','--locale=C'],stdout=subprocess.DEVNULL)
        finally:pw.unlink()
        (LOCAL/'sockets').mkdir(exist_ok=True);(LOCAL/'sockets').chmod(0o700)
        with (CLUSTER/'postgresql.conf').open('a') as f:f.write(f"\nlisten_addresses='127.0.0.1'\nport={cfg.get('databasePort',PGPORT)}\nunix_socket_directories='{LOCAL/'sockets'}'\nmax_connections=40\n")
        (LOCAL/'cluster-marker').write_text(str(CLUSTER.resolve()))
    guard()
    running=subprocess.run([str(PG/'pg_ctl'),'-D',str(CLUSTER),'status'],stdout=subprocess.DEVNULL).returncode==0
    mode=LOCAL/'pg-network-mode'
    if offline and running and (not mode.exists() or mode.read_text()!='offline'):
        run([PG/'pg_ctl','-D',CLUSTER,'stop','-m','fast','-w'],stdout=subprocess.DEVNULL);running=False
    if not running:
        prefix=['/usr/bin/sandbox-exec','-f',ROOT/'scripts/offline.sb'] if offline else []
        run(prefix+[PG/'pg_ctl','-D',CLUSTER,'-l',LOCAL/'postgres.log','start','-w'],stdout=subprocess.DEVNULL)
        mode.write_text('offline' if offline else 'local')
def migrate():
    db_start();cfg=config()
    with admin('postgres') as db:
        if not db.execute("select 1 from pg_roles where rolname='ml_runtime'").fetchone():db.execute(sql.SQL('create role ml_runtime login password {}').format(sql.Literal(cfg['mlPassword'])))
        if not db.execute('select 1 from pg_database where datname=%s',(DBNAME,)).fetchone():db.execute(sql.SQL('create database {}').format(sql.Identifier(DBNAME)))
    with admin() as db:
        db.execute('create table if not exists public.demo_identity(id int primary key check(id=1),project text not null,synthetic boolean not null check(synthetic))')
        row=db.execute('select project from public.demo_identity where id=1').fetchone()
        if row:assert row[0]==str(ROOT)
        else:db.execute('insert into public.demo_identity values(1,%s,true)',(str(ROOT),))
        db.execute('create table if not exists public.demo_migrations(name text primary key,digest text not null)')
        for p in sorted((ROOT/'ml/migrations').glob('*.sql')):
            h=hashlib.sha256(p.read_bytes()).hexdigest();old=db.execute('select digest from public.demo_migrations where name=%s',(p.name,)).fetchone()
            if old:assert old[0]==h,'Applied migration changed'
            else:
                with db.transaction():db.execute(p.read_text());db.execute('insert into public.demo_migrations values(%s,%s)',(p.name,h))
    print('Standalone ML database prepared')
def env():
    cfg=config();e=os.environ.copy();e.update({'PYTHONPATH':str(ROOT/'ml'),'MODEL_BUNDLE':str(ROOT/'ml/artifacts/baseline'),'FRAUD_MODEL_BUNDLE':os.environ.get('FRAUD_MODEL_BUNDLE',str(ROOT/'ml/artifacts/fraud-demo-v1')),'ML_API_URL':f"http://127.0.0.1:{cfg.get('apiPort',APIPORT)}",'ML_INTERNAL_TOKEN':cfg['ML_INTERNAL_TOKEN'],'ML_DATABASE_URL':f"postgresql://ml_runtime:{cfg['mlPassword']}@127.0.0.1:{cfg.get('databasePort',PGPORT)}/{DBNAME}",'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONUNBUFFERED':'1'});return e
def up(offline=False):
    assert (ROOT/'ml/artifacts/baseline/manifest.json').exists(),'Train offline before startup'
    db_start(offline);pid=LOCAL/'ml.pid'
    if pid.exists():
        try:os.kill(int(pid.read_text()),0);raise RuntimeError('ML already running; use down before changing mode')
        except ProcessLookupError:pid.unlink()
    prefix=['/usr/bin/sandbox-exec','-f',ROOT/'scripts/offline.sb'] if offline else []
    with (LOCAL/'ml.log').open('ab') as log:p=subprocess.Popen([str(x) for x in prefix+[ROOT/'.venv/bin/python','-m','uvicorn','scoring.server:app','--host','127.0.0.1','--port',str(config().get('apiPort',APIPORT)),'--no-access-log']],env=env(),stdout=log,stderr=log,start_new_session=True)
    pid.write_text(str(p.pid))
    for _ in range(100):
        if p.poll() is not None:raise RuntimeError('ML startup failed; see .local/ml.log')
        try:
            req=urllib.request.Request(env()['ML_API_URL']+'/health',headers={'Authorization':'Bearer '+config()['ML_INTERNAL_TOKEN']})
            with urllib.request.urlopen(req,timeout=1) as r:
                if r.status==200:print('Risk + fraud API ready: '+env()['ML_API_URL']+' | network mode: '+('OS loopback-only' if offline else 'local'));return
        except OSError:time.sleep(.1)
    raise RuntimeError('ML not ready; see .local/ml.log')
def down(stop_db=True):
    pid=LOCAL/'ml.pid'
    if pid.exists():
        try:os.killpg(int(pid.read_text()),signal.SIGTERM)
        except ProcessLookupError:pass
        pid.unlink()
        time.sleep(.3)
    if stop_db and CLUSTER.exists():
        guard();subprocess.run([str(PG/'pg_ctl'),'-D',str(CLUSTER),'stop','-m','fast','-w'],stdout=subprocess.DEVNULL)
def reset(confirmation):
    assert confirmation==DBNAME,'Use --confirm credit_scoring_demo'
    down();db_start();guard()
    with admin() as db,db.transaction():
        assert db.info.dbname==DBNAME and db.execute('select project,synthetic from public.demo_identity where id=1').fetchone()==(str(ROOT),True)
        db.execute('truncate ml.features,ml.inferences,ml.fraud_features,ml.fraud_inferences')
    print('Cleared only ML feature/inference tables in dedicated synthetic database; bundles/fixtures retained')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['migrate','up','down','train','train-fraud','scenarios','test','reset']);p.add_argument('--offline',action='store_true');p.add_argument('--confirm');p.add_argument('--trials',type=int,default=30);p.add_argument('--folds',type=int,default=3);p.add_argument('--threads',type=int,default=4);p.add_argument('--shortlist',type=int,default=5);p.add_argument('--storage');p.add_argument('--output',default=str(ROOT/'ml/artifacts/fraud-demo-v1'));p.add_argument('--dataset',default=os.environ.get('DATASET_PATH',str(ROOT/'datasets/ru-sme-dataset-10000')));a=p.parse_args()
    if a.command=='migrate':migrate()
    elif a.command=='up':up(a.offline)
    elif a.command=='down':down()
    elif a.command=='reset':reset(a.confirm)
    elif a.command=='train':run([ROOT/'.venv/bin/python','-m','scoring.train','--dataset',a.dataset,'--trials',a.trials,'--folds',a.folds,'--threads',a.threads,'--shortlist',a.shortlist]+(['--storage',a.storage] if a.storage else []),env=env())
    elif a.command=='train-fraud':run([ROOT/'.venv/bin/python','-m','scoring.fraud_train','--dataset',a.dataset,'--output',a.output],env=env())
    elif a.command=='scenarios':run([ROOT/'.venv/bin/python','-m','scoring.scenarios'],env=env())
    elif a.command=='test':run([ROOT/'.venv/bin/python','-m','pytest','ml/tests','-q','--junitxml=reports/ml-tests.xml'],env=env())
