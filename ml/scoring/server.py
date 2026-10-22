import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import numpy as np
import psycopg
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from typing import Literal
from .features import build, digest, code_digest, FEATURES
from .bundle import load_bundle, read_manifest, predict_probability

class FinancialInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    periodStart:str
    periodEnd:str
    reportingStandard:Literal['DEMO']
    currency:Literal['RUB']
    values:dict[str,StrictInt]
    sourceDocumentReferences:list=Field(max_length=0)
class FeatureInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    applicationId:str=Field(min_length=1,max_length=128)
    submissionSnapshotId:str=Field(min_length=1,max_length=128)
    financialSnapshotId:str=Field(min_length=1,max_length=128)
    financialSnapshotDigest:str=Field(pattern='^[0-9a-f]{64}$')
    financialStatementVersion:StrictInt=Field(ge=1,le=9007199254740991)
    asOf:str
    latestSourceAvailableAt:str
    purpose:Literal['DEMO_RESEARCH']
    financialStatement:FinancialInput
class RiskRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    requestId:str=Field(min_length=1,max_length=128)
    featureSnapshotId:str=Field(min_length=1,max_length=128)
    featureSnapshotDigest:str=Field(pattern='^[0-9a-f]{64}$')
    bundleDigest:str=Field(pattern='^[0-9a-f]{64}$')
    purpose:Literal['DEMO_RESEARCH']
    featureSchemaVersion:Literal[2]

BUNDLE=Path(os.environ.get('MODEL_BUNDLE','ml/artifacts/baseline'))
DSN=os.environ['ML_DATABASE_URL']
TOKEN=os.environ['ML_INTERNAL_TOKEN']
if len(TOKEN)<16: raise RuntimeError('Internal token must be explicitly configured (at least 16 characters)')
model=None; manifest=None; policy=None

def db(): return psycopg.connect(DSN, row_factory=dict_row, connect_timeout=2, options='-c statement_timeout=2000')
def error(n,msg): raise HTTPException(n,msg)
def auth(authorization: str=Header('')):
    import secrets
    if not secrets.compare_digest(authorization,'Bearer '+TOKEN): error(403,'Internal role required')
def get_manifest():
    return read_manifest(BUNDLE)
@asynccontextmanager
async def lifespan(app):
    global model,manifest,policy
    model,manifest,policy=load_bundle(BUNDLE)
    with db() as c: c.execute('select count(*) from ml.inferences').fetchone()
    yield
app=FastAPI(title='Risk API v2',lifespan=lifespan,dependencies=[Depends(auth)])

@app.exception_handler(psycopg.Error)
def persistence_unavailable(request,exc):
    return JSONResponse(status_code=503,content={'detail':'ML persistence unavailable; successful inference requires a committed record'})

@app.get('/health')
def health():
    with db() as c: c.execute('select 1').fetchone()
    return {'ready':True,'bundleDigest':manifest['bundleDigest']}
@app.get('/internal/v2/bundle')
def bundle(): return {'manifest':manifest,'policy':policy}
@app.post('/internal/v2/feature-snapshots')
def create_snapshot(body:FeatureInput):
    body=body.model_dump()
    required={'applicationId','submissionSnapshotId','financialStatementVersion','asOf','purpose','financialSnapshotId','financialSnapshotDigest','financialStatement','latestSourceAvailableAt'}
    if set(body)!=required or body['purpose']!='DEMO_RESEARCH': error(422,'Unsupported snapshot input/purpose')
    if digest(body['financialStatement'])!=body['financialSnapshotDigest']: error(409,'Financial digest mismatch')
    try:
        available=datetime.fromisoformat(body['latestSourceAvailableAt'].replace('Z','+00:00'));as_of=datetime.fromisoformat(body['asOf'].replace('Z','+00:00'))
        if available.tzinfo is None or as_of.tzinfo is None or available>as_of or available.date()<=datetime.fromisoformat(body['financialStatement']['periodEnd']).date(): error(422,'Source/report/asOf chronology invalid')
        features=build(body['financialStatement'])
    except (ValueError,KeyError,TypeError) as e: error(422,str(e))
    identity=body['submissionSnapshotId']+':'+manifest['featureCodeDigest']; h=digest(body)
    with db() as c:
        c.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',(identity,))
        old=c.execute('select * from ml.features where identity=%s',(identity,)).fetchone()
        if old:
            if old['input_hash']!=h: error(409,'Snapshot identity reused with different input')
            return old['payload']
        snap={'featureSnapshotId':str(uuid4()),'submissionSnapshotId':body['submissionSnapshotId'],
              'financialStatementVersion':body['financialStatementVersion'],'featureSchemaVersion':2,
              'featureCodeDigest':manifest['featureCodeDigest'],'featureAsOf':body['asOf'],
              'latestSourceAvailableAt':body['latestSourceAvailableAt'],'financialSnapshotId':body['financialSnapshotId'],
              'financialSnapshotDigest':body['financialSnapshotDigest'],'features':features,
              'missingFeatures':[k for k,v in features.items() if v is None]}
        snap['snapshotDigest']=digest(snap)
        c.execute('insert into ml.features(id,identity,input_hash,payload) values(%s,%s,%s,%s)',(snap['featureSnapshotId'],identity,h,Jsonb(snap)))
    return snap
@app.get('/internal/v2/feature-snapshots/{snapshot_id}')
def snapshot(snapshot_id:str):
    with db() as c: row=c.execute('select payload from ml.features where id=%s',(snapshot_id,)).fetchone()
    if not row: error(404,'Unknown snapshot')
    return row['payload']
@app.post('/internal/v2/risk/evaluations')
def evaluate(body:RiskRequest):
    body=body.model_dump()
    required={'requestId','featureSnapshotId','featureSnapshotDigest','bundleDigest','purpose','featureSchemaVersion'}
    if set(body)!=required or body['purpose']!='DEMO_RESEARCH' or body['featureSchemaVersion']!=2: error(422,'Only DEMO_RESEARCH/schema 2 supported')
    if body['bundleDigest']!=manifest['bundleDigest']: error(409,'Bundle mismatch')
    h=digest(body)
    with db() as c:
        c.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',(body['requestId'],))
        old=c.execute('select * from ml.inferences where request_id=%s',(body['requestId'],)).fetchone()
        if old:
            if old['input_hash']!=h: error(409,'requestId reused with different input')
            return old['payload']
        row=c.execute('select payload from ml.features where id=%s',(body['featureSnapshotId'],)).fetchone()
        if not row: error(404,'Unknown feature snapshot')
        s=row['payload']; check=dict(s); check.pop('snapshotDigest')
        if digest(check)!=s['snapshotDigest'] or s['snapshotDigest']!=body['featureSnapshotDigest'] or s['featureCodeDigest']!=manifest['featureCodeDigest']: error(409,'Snapshot integrity mismatch')
        vector=np.array([[np.nan if s['features'][k] is None else s['features'][k] for k in FEATURES]])
        score=float(predict_probability(model,vector)[0])
        result={'requestId':body['requestId'],'inferenceId':str(uuid4()),'featureSnapshotId':s['featureSnapshotId'],
                'featureSnapshotDigest':s['snapshotDigest'],'modelVersion':manifest['modelVersion'],'bundleDigest':manifest['bundleDigest'],
                'score':score,'scoreKind':'BANKRUPTCY_PROXY','calibrationStatus':'DEMONSTRATION','releaseId':manifest['modelVersion'],'purpose':'DEMO_RESEARCH','internalReasonCodes':['SYNTHETIC_SIMULATION']}
        c.execute('insert into ml.inferences(id,request_id,input_hash,payload) values(%s,%s,%s,%s)',(result['inferenceId'],body['requestId'],h,Jsonb(result)))

    return result
