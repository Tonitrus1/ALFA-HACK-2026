"""Measure real loopback HTTP, cold readiness and four concurrent offline requests."""
import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np

from .catalog import Catalog
from .dataset import write_json
from .integration import make_request
from .ranker import ModelRanker
from .schemas import RankingResult


def smoke(bundle, output, kind='catboost', samples=200):
    from .learned import LearnedRanker
    catalog = Catalog()
    factory = LearnedRanker if kind == 'catboost' else ModelRanker
    t0 = time.perf_counter()
    model = factory(catalog, bundle)
    load = time.perf_counter() - t0
    request = make_request(catalog, request_id='local-smoke', exposure_id='local-smoke-exposure',
        candidate_ids=sorted(catalog.cards), profile=dict(task='PURCHASE', help='COST', depth='EXPLAINED'))
    warm, cached = [], []
    for _ in range(40):
        if hasattr(model, 'features'):
            model.features._similarities.cache_clear()
        start = time.perf_counter()
        model.rank(request)
        warm.append((time.perf_counter() - start) * 1000)
    for _ in range(40):
        start = time.perf_counter()
        model.rank(request)
        cached.append((time.perf_counter() - start) * 1000)
    token = 'local-smoke-token-not-a-secret'
    env = os.environ | dict(FEED_RANKER=kind, FEED_BUNDLE=str(Path(bundle).resolve()),
        ML_INTERNAL_TOKEN=token, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(32)
    port = listener.getsockname()[1]
    with Path(output).with_suffix('.server.log').open('w') as log:
        start = time.perf_counter()
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'ml.feed.server:create_app',
            '--factory', '--fd', str(listener.fileno()), '--no-access-log'],
            pass_fds=(listener.fileno(),), env=env, stdout=log, stderr=log)
        listener.close()
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=10,
                              headers={'X-Service-Token': token, 'Idempotency-Key': request.requestId}) as client:
                deadline = time.monotonic() + 90
                while True:
                    if process.poll() is not None:
                        raise RuntimeError('Smoke server exited; inspect the server log')
                    try:
                        if client.get('/health').status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError('Cold startup did not become ready in 90 seconds')
                    time.sleep(.2)
                cold = time.perf_counter() - start
                payload = request.model_dump(mode='json')
                expected = set(request.candidateIds)
                def once(j):
                    # Vary typed profiles to exercise the encoder, not just one cached query.
                    from .schemas import Task, Help, Depth, Business, Stage
                    profile = dict(task=list(Task)[j % 5].value, help=list(Help)[(j // 5) % 4].value,
                        depth=list(Depth)[(j // 20) % 3].value,
                        businessCategory=list(Business)[(j // 60) % 6].value,
                        applicationStage=list(Stage)[(j // 360) % 5].value)
                    begin = time.perf_counter()
                    response = client.post('/internal/v2/rankings', json=payload | {'profile': profile})
                    response.raise_for_status()
                    result = RankingResult.model_validate(response.json())
                    if (set(result.rankedIds) != expected or result.exposureId != request.exposureId
                            or result.candidateSetDigest != request.candidateSetDigest
                            or result.catalogDigest != request.catalogDigest):
                        raise ValueError('HTTP ranking identity mismatch')
                    return (time.perf_counter() - begin) * 1000
                for j in range(4):
                    once(j)
                begin = time.perf_counter()
                with ThreadPoolExecutor(max_workers=4) as pool:
                    durations = list(pool.map(once, range(samples)))
                elapsed = time.perf_counter() - begin
                cold_result = client.post('/internal/v2/rankings', json=payload | {'profile': {}})
                assert cold_result.json()['mode'] == 'RULES'
                assert client.post('/internal/v2/rankings', json=payload | {'catalogDigest': '0' * 64}).status_code == 409
                assert client.post('/internal/v2/rankings', json=payload, headers={'X-Service-Token': 'invalid'}).status_code == 403
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    report = dict(kind=kind, releaseId=model.release_id, platform=platform.platform(),
        cpuThreads=4, candidates=len(catalog.cards), concurrency=4, samples=samples,
        modelLoadSeconds=load, coldHTTPReadySeconds=cold,
        warmInferenceP95Ms=float(np.percentile(warm, 95)),
        cachedInferenceP95Ms=float(np.percentile(cached, 95)),
        httpP50Ms=float(np.percentile(durations, 50)), httpP95Ms=float(np.percentile(durations, 95)),
        httpP99Ms=float(np.percentile(durations, 99)), throughputRPS=samples / elapsed,
        errors=0, gates=dict(warmP95=float(np.percentile(warm, 95)) <= 200,
                            httpP95=float(np.percentile(durations, 95)) <= 500),
        limitations=['Single local machine and frozen bundle; not a production capacity estimate.',
                     'Warm inference clears the profile cache; HTTP uses varying typed profiles.'])
    write_json(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=Path('.local/feed-catboost'))
    parser.add_argument('--kind', choices=('e5', 'catboost'), default='catboost')
    parser.add_argument('--output', type=Path, default=Path('reports/hackathon/http-load.json'))
    parser.add_argument('--samples', type=int, default=200)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = smoke(args.bundle, args.output, args.kind, args.samples)
    print(json.dumps(report, indent=2))
    if not all(report['gates'].values()):
        raise SystemExit('Performance gates failed; inspect the saved report')


if __name__ == '__main__':
    main()
