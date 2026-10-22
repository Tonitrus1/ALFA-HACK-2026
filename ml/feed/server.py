"""Separate app on port 8002. Importing it cannot initialize the Risk API."""
import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from .catalog import Catalog
from .ranker import ModelRanker, RankingError, RulesRanker, build_query, validate_request
from .schemas import MLError, RankingRequest, RankingResult

logger = logging.getLogger(__name__)
service_identity = APIKeyHeader(name='X-Service-Token', scheme_name='ServiceIdentity',
                                description='Internal FEED service token; never expose to the browser.',
                                auto_error=False)
NO_STORE = {'Cache-Control': {'schema': {'const': 'no-store'}}}


def error_contract(description, *, retry=False):
    headers = dict(NO_STORE)
    if retry:
        headers['Retry-After'] = {'schema': {'type': 'integer', 'minimum': 1, 'maximum': 3600}}
    return {'model': MLError, 'description': description, 'headers': headers}


def create_app(bundle: Path | None = None, token: str | None = None, ranker_factory=None):
    token = token if token is not None else os.environ.get('ML_INTERNAL_TOKEN', '')
    if len(token) < 16:
        raise RuntimeError('ML_INTERNAL_TOKEN must be configured (at least 16 characters)')
    kind = os.environ.get('FEED_RANKER', 'e5')
    if kind not in ('e5', 'catboost'):
        raise RuntimeError('FEED_RANKER must be e5 or catboost')
    if ranker_factory is None:
        if kind == 'catboost':
            from .learned import LearnedRanker
            ranker_factory = LearnedRanker
        else:
            ranker_factory = ModelRanker
    default_bundle = '.local/feed-catboost' if kind == 'catboost' else '.local/feed-bundle'
    bundle = bundle or Path(os.environ.get('FEED_BUNDLE', default_bundle))

    def auth(service_token: str | None = Security(service_identity)):
        if not secrets.compare_digest((service_token or '').encode(), token.encode()):
            raise RankingError('FORBIDDEN', 'Internal role required', 403)

    @asynccontextmanager
    async def lifespan(app):
        app.state.catalog = Catalog()
        app.state.rules = RulesRanker(app.state.catalog)
        app.state.ranker = None
        try:
            app.state.ranker = ranker_factory(app.state.catalog, bundle,
                                            threads=int(os.environ.get('FEED_CPU_THREADS', '4')))
        except Exception:
            logger.exception('Feed model unavailable; backend must use RULES')
        yield

    app = FastAPI(title='Feed Ranking API v2', version='1.0.1', lifespan=lifespan,
                  dependencies=[Depends(auth)], responses={
                      403: error_contract('Missing or invalid internal service token'),
                      422: error_contract('Invalid FEED ranking request'),
                  })

    def error_response(status, code, message):
        return JSONResponse(status_code=status,
                            content=MLError(code=code, message=message, correlationId=str(uuid4()),
                                            fallbackAction='RULES' if status == 503 else 'NONE').model_dump(),
                            headers={'Cache-Control': 'no-store', **({'Retry-After': '5'} if status == 503 else {})})

    @app.middleware('http')
    async def no_cache(request, call_next):
        # Authenticated internal requests only; never log profiles or request bodies.
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(RankingError)
    async def ranking_error(request, error):
        return error_response(error.status, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return error_response(422, 'INVALID_REQUEST', 'Invalid FEED ranking request')

    @app.get('/health', operation_id='feedHealth', responses={
        200: {'headers': NO_STORE},
        503: error_contract('Feed model is unavailable', retry=True),
    })
    def health(request: Request):
        if request.app.state.ranker is None:
            raise RankingError('MODEL_UNAVAILABLE', 'Feed model is unavailable', 503)
        return {'ready': True, 'catalogVersion': request.app.state.catalog.version,
                'catalogDigest': request.app.state.catalog.digest,
                'releaseId': request.app.state.ranker.release_id}

    @app.post('/internal/v2/rankings', response_model=RankingResult,
              operation_id='rankEligibleCandidates', responses={
                  200: {'headers': NO_STORE},
                  409: error_contract('Catalog, candidate or idempotency conflict'),
                  503: error_contract('Model unavailable; backend must use RULES', retry=True),
              })
    def rank(body: RankingRequest, request: Request,
             idempotency_key: str = Header(alias='Idempotency-Key', min_length=1, max_length=128)):
        if idempotency_key != body.requestId:
            raise RankingError('IDEMPOTENCY_KEY_MISMATCH', 'Idempotency-Key must equal requestId')
        validate_request(request.app.state.catalog, body)
        if not build_query(body.profile):
            return request.app.state.rules.rank(body)
        if request.app.state.ranker is None:
            raise RankingError('MODEL_UNAVAILABLE', 'Feed model is unavailable; use backend rules', 503)
        try:
            return request.app.state.ranker.rank(body)
        except RankingError:
            raise
        except Exception:
            logger.exception('Feed inference failed')
            raise RankingError('MODEL_UNAVAILABLE', 'Feed inference failed; use backend rules', 503)

    return app


# Uvicorn --factory calls create_app. No environment reads/model imports at module import.
