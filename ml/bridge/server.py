"""Internal backend facade. Upstream inference remains in the original Risk/Feed services."""
import hashlib
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from typing import Literal

from feed.catalog import Catalog, candidate_digest
from feed.integration import make_request
from feed.ranker import RulesRanker, validate_request, RankingError
from feed.schemas import RankingRequest, RankingResult
from scoring.features import digest
from .store import Conflict, Store

FIELDS = ['totalAssetsMinor', 'totalLiabilitiesMinor', 'currentAssetsMinor',
          'currentLiabilitiesMinor', 'equityMinor', 'revenueMinor', 'netProfitMinor', 'ebitMinor']


class FeatureCall(BaseModel):
    model_config = ConfigDict(extra='forbid')
    applicationId: str = Field(min_length=1, max_length=128)
    submissionSnapshotId: str = Field(min_length=1, max_length=128)
    financialStatementVersion: StrictInt = Field(ge=1)
    asOf: datetime
    purpose: Literal['DEMO_RESEARCH']
    financialSnapshotId: str = Field(min_length=1, max_length=128)
    financialSnapshotDigest: str = Field(pattern='^[0-9a-f]{64}$')
    financialStatement: dict
    latestSourceAvailableAt: datetime


class RiskCall(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: str = Field(min_length=1, max_length=128)
    featureSnapshotId: str = Field(min_length=1, max_length=128)
    featureSnapshotDigest: str = Field(pattern='^[0-9a-f]{64}$')
    featureSchemaVersion: Literal[2]
    purpose: Literal['DEMO_RESEARCH']


def backend_statement_digest(statement, version):
    """P15 FinancialStatementService.snapshotStatement LinkedHashMap serialization."""
    ordered = dict(statementVersion=version, periodStart=statement['periodStart'],
                   periodEnd=statement['periodEnd'], reportingStandard=statement['reportingStandard'],
                   currency=statement['currency'], values={k: statement['values'][k] for k in FIELDS},
                   sourceDocumentReferences=[dict(documentId=r['documentId'], documentVersion=r['documentVersion'], objectVersion=r['objectVersion'])
                                             for r in statement['sourceDocumentReferences']])
    return hashlib.sha256(json.dumps(ordered, ensure_ascii=False, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def create_app(store=None, risk_transport=None, feed_transport=None, token=None):
    token = token or os.environ.get('ML_SERVICE_TOKEN', '')
    risk_token = os.environ.get('RISK_SERVICE_TOKEN', token)
    feed_token = os.environ.get('FEED_SERVICE_TOKEN', token)
    if len(token) < 32:
        raise RuntimeError('ML_SERVICE_TOKEN must contain at least 32 characters')
    store = store or Store(os.environ['ML_DATABASE_URL'])
    catalog = Catalog()
    rules = RulesRanker(catalog)
    risk = httpx.Client(base_url=os.environ.get('RISK_BASE_URL', 'http://risk:8001'),
                        headers={'Authorization': 'Bearer ' + risk_token}, transport=risk_transport,
                        timeout=httpx.Timeout(1.6, connect=.4))
    feed = httpx.Client(base_url=os.environ.get('FEED_BASE_URL', 'http://feed:8002'),
                        headers={'X-Service-Token': feed_token}, transport=feed_transport,
                        timeout=httpx.Timeout(1.4, connect=.3))

    @asynccontextmanager
    async def lifespan(app):
        store.ready()
        yield
        risk.close()
        feed.close()

    def auth(x_service_token: str = Header('')):
        if not secrets.compare_digest(x_service_token.encode(), token.encode()):
            raise HTTPException(403, 'Internal role required')

    app = FastAPI(title='Backend ML compatibility API', version='1.0.0',
                  lifespan=lifespan, dependencies=[Depends(auth)])

    @app.middleware('http')
    async def no_store(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={'code': 'CONTRACT_CONFLICT', 'message': str(exc)})

    @app.exception_handler(RankingError)
    async def ranking_error(request, exc):
        return JSONResponse(status_code=exc.status, content={'code': exc.code, 'message': exc.message})

    @app.exception_handler(psycopg.Error)
    async def unavailable(request, exc):
        return JSONResponse(status_code=503, content={'code': 'PERSISTENCE_UNAVAILABLE'})

    def upstream(client, method, path, body=None, key=None):
        try:
            response = client.request(method, path, json=body,
                                      headers={'Idempotency-Key': key} if key else {})
        except httpx.TransportError:
            raise HTTPException(503, 'Upstream unavailable') from None
        if response.status_code >= 400:
            raise HTTPException(response.status_code if response.status_code in (403, 404, 409, 422) else 503,
                                'Upstream rejected request')
        try:
            return response.json()
        except ValueError:
            raise HTTPException(502, 'Invalid upstream response') from None

    def ranking(body):
        validate_request(catalog, body)
        def execute(pinned):
            if pinned['catalogDigest'] != catalog.digest:
                raise Conflict('Pinned catalog is unavailable')
            try:
                raw = upstream(feed, 'POST', '/internal/v2/rankings', pinned,
                               pinned['requestId'])
            except HTTPException as exc:
                if exc.status_code not in (429, 500, 502, 503, 504):
                    raise
                return rules.rank(body).model_dump(mode='json')
            result = RankingResult.model_validate(raw)
            if (result.requestId != body.requestId or result.exposureId != body.exposureId
                    or result.candidateSetDigest != body.candidateSetDigest
                    or result.catalogDigest != body.catalogDigest
                    or set(result.rankedIds) != set(body.candidateIds)):
                raise Conflict('Upstream ranking identity/permutation mismatch')
            return result.model_dump(mode='json')
        payload = body.model_dump(mode='json', exclude_none=True)
        return store.call('feed:' + body.requestId, payload, lambda: payload, execute)

    @app.get('/health')
    def health():
        store.ready()
        r = upstream(risk, 'GET', '/health')
        f = upstream(feed, 'GET', '/health')
        return {'ready': bool(r.get('ready') and f.get('ready')), 'risk': r, 'feed': f}

    @app.post('/internal/v2/feature-snapshots')
    def features(body: FeatureCall, idempotency_key: str = Header(alias='Idempotency-Key')):
        expected_key = 'risk:' + body.financialSnapshotId + ':features'
        if idempotency_key != expected_key:
            raise Conflict('Feature key must identify the financial snapshot')
        if body.asOf.tzinfo is None or body.latestSourceAvailableAt.tzinfo is None:
            raise HTTPException(422, 'Timezone required')
        if body.latestSourceAvailableAt > body.asOf:
            raise HTTPException(422, 'Source unavailable at asOf')
        try:
            if backend_statement_digest(body.financialStatement, body.financialStatementVersion) != body.financialSnapshotDigest:
                raise Conflict('Backend financial snapshot digest mismatch')
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, Conflict):
                raise
            raise HTTPException(422, 'Invalid backend statement') from None
        payload = body.model_dump(mode='json')
        # Backend supplies the immutable snapshot creation time; retries do not use the worker clock.
        def prepare():
            metadata = upstream(risk, 'GET', '/internal/v2/bundle')
            manifest = metadata['manifest']
            normalized = dict(payload, financialSnapshotDigest=digest(body.financialStatement))
            return {'body': normalized, 'bundleDigest': manifest['bundleDigest'],
                    'featureCodeDigest': manifest['featureCodeDigest'],
                    'inputAdapterDigest': metadata['backendInputAdapterDigest']}
        def execute(pinned):
            result = upstream(risk, 'POST', '/internal/compat/v1/feature-snapshots', pinned['body'])
            unsigned = {k: v for k, v in result.items() if k != 'snapshotDigest'}
            if (result['snapshotDigest'] != digest(unsigned)
                    or result['featureCodeDigest'] != pinned['featureCodeDigest']
                    or result.get('inputAdapterDigest') != pinned['inputAdapterDigest']
                    or result['financialSnapshotId'] != body.financialSnapshotId
                    or result['financialSnapshotDigest'] != pinned['body']['financialSnapshotDigest']):
                raise Conflict('Upstream financial/feature snapshot mismatch')
            public = dict(result, financialSnapshotDigest=body.financialSnapshotDigest)
            # Extra adapter metadata is persisted internally; Java consumes its original DTO.
            public.pop('inputAdapterDigest', None)
            public['snapshotDigest'] = digest({k: v for k, v in public.items() if k != 'snapshotDigest'})
            return {'native': result, 'backend': public, 'bundleDigest': pinned['bundleDigest']}
        saved = store.call('features:' + body.financialSnapshotId, payload, prepare, execute)
        return saved['backend']

    @app.post('/internal/v2/risk/evaluations')
    def evaluate(body: RiskCall, idempotency_key: str = Header(alias='Idempotency-Key')):
        if idempotency_key != body.requestId + ':evaluation':
            raise Conflict('Risk idempotency key mismatch')
        if not body.requestId.startswith('risk:'):
            raise Conflict('Risk request must identify financial snapshot')
        row = store.get('features:' + body.requestId.removeprefix('risk:'))
        if not row or row['response'] is None:
            raise Conflict('Unknown prepared feature snapshot')
        saved = row['response']
        if (saved['backend']['featureSnapshotId'] != body.featureSnapshotId
                or saved['backend']['snapshotDigest'] != body.featureSnapshotDigest):
            raise Conflict('Feature reference mismatch')
        payload = body.model_dump(mode='json')
        def prepare():
            return dict(payload, featureSnapshotDigest=saved['native']['snapshotDigest'],
                        bundleDigest=saved['bundleDigest'])
        def execute(pinned):
            result = upstream(risk, 'POST', '/internal/v2/risk/evaluations', pinned)
            if (result.get('bundleDigest') != pinned['bundleDigest'] or result.get('requestId') != body.requestId
                    or result.get('featureSnapshotId') != body.featureSnapshotId
                    or result.get('featureSnapshotDigest') != pinned['featureSnapshotDigest']
                    or result.get('scoreKind') != 'BANKRUPTCY_PROXY'
                    or result.get('calibrationStatus') != 'DEMONSTRATION'
                    or type(result.get('score')) not in (int, float) or not 0 <= result['score'] <= 1):
                raise Conflict('Invalid risk result')
            return {k: v for k, v in dict(result, featureSnapshotDigest=body.featureSnapshotDigest).items()
                    if k != 'purpose'}
        return store.call('risk:' + body.requestId, payload, prepare, execute)

    @app.post('/internal/v2/feed/rankings')
    def feed_ranking(body: RankingRequest, idempotency_key: str = Header(alias='Idempotency-Key')):
        if idempotency_key != body.requestId:
            raise Conflict('Feed idempotency key mismatch')
        return ranking(body)

    @app.post('/internal/v2/rankings')
    def legacy_ranking(body: dict, idempotency_key: str = Header(alias='Idempotency-Key')):
        if body.get('scope') != 'FEED':
            raise HTTPException(422, 'PRODUCT uses backend eligibility/rules; no product model configured')
        ids = body.get('candidateIds', [])
        legacy_digest = hashlib.sha256('\n'.join(ids).encode()).hexdigest()
        if body.get('candidateSetDigest') != legacy_digest or body.get('requestId') != idempotency_key:
            raise Conflict('Backend candidate digest/key mismatch')
        # Only exact enum mappings enter the encoder. Free contextText is intentionally unused.
        profile = {}
        for old, new, allowed in [('stage', 'applicationStage', {'DRAFT','SUBMITTED','NEEDS_INFORMATION','REVIEW','DECISION'}),
                                  ('contextCategory', 'businessCategory', {'RETAIL','SERVICES','MANUFACTURING','WHOLESALE','HOSPITALITY','OTHER'}),
                                  ('fundingPurpose', 'task', {'PURCHASE','CASH_GAP','EQUIPMENT','EXPANSION','EXPLORING'})]:
            if body.get(old) in allowed:
                profile[new] = body[old]
        request = make_request(catalog, request_id=body['requestId'], exposure_id='exposure-' + body['requestId'],
                               candidate_ids=ids, profile=profile)
        if body.get('catalogVersion') != catalog.version:
            raise Conflict('Catalog version mismatch')
        if body.get('candidateTexts'):
            request.candidateTexts = body['candidateTexts']
            request = RankingRequest.model_validate(request.model_dump())
        result = ranking(request)
        return {k: v for k, v in dict(result, candidateSetDigest=legacy_digest).items()
                if k not in ('catalogDigest', 'explanations')}

    return app
