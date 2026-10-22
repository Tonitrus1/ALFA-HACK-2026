import copy
from datetime import datetime,timezone
import uuid
import requests
from .features import digest
class RiskClient:
    def __init__(self,base_url,token,bundle_digest):
        self.base_url=base_url.rstrip('/');self.bundle_digest=bundle_digest
        self.http=requests.Session();self.http.trust_env=False;self.http.headers['Authorization']='Bearer '+token
    def call(self,path,body=None,base_url=None,timeout=3):
        url=(base_url or self.base_url)+path
        response=self.http.get(url,timeout=timeout) if body is None else self.http.post(url,json=body,timeout=timeout)
        response.raise_for_status();return response.json()
    def snapshot_request(self,statement,source_available_at='2026-04-01T00:00:00Z'):

        return {'applicationId':'DEMO:'+str(uuid.uuid4()),'submissionSnapshotId':str(uuid.uuid4()),'financialSnapshotId':str(uuid.uuid4()),
                'financialSnapshotDigest':digest(statement),'financialStatementVersion':1,'asOf':datetime.now(timezone.utc).isoformat(),
                'latestSourceAvailableAt':source_available_at,'purpose':'DEMO_RESEARCH','financialStatement':copy.deepcopy(statement)}
    def create_snapshot(self,request):return self.call('/internal/v2/feature-snapshots',request)
    def risk_request(self,snapshot,request_id=None):
        return {'requestId':request_id or str(uuid.uuid4()),'featureSnapshotId':snapshot['featureSnapshotId'],
                'featureSnapshotDigest':snapshot['snapshotDigest'],'featureSchemaVersion':2,'bundleDigest':self.bundle_digest,'purpose':'DEMO_RESEARCH'}
    def evaluate(self,request,base_url=None):return self.call('/internal/v2/risk/evaluations',request,base_url)
