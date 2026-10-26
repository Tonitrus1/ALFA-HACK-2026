#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports/all-branches
# No local model cache or host bundle: bootstrap real E5 into an empty named volume.
docker compose up -d --wait --wait-timeout 600 gateway
python3 scripts/integration/smoke.py --output reports/all-branches/public-flow.json
docker build --target testing -f deploy/Dockerfile.risk -t credit-risk-tests:local .
docker run --rm --network credit-integrated-mvp_internal --env-file .env -e PYTHONPATH=/tests/ml -e ML_BASE_URL=http://risk:8001 -v "$PWD:/tests:ro" -w /tests --entrypoint sh credit-risk-tests:local -c 'export ML_INTERNAL_TOKEN="$ML_SERVICE_TOKEN"; python -m pytest ml/tests ml/bridge/test_bridge.py ml/bridge/test_fraud_adapter.py ml/bridge/test_fraud_native.py -q --tb=short -p no:cacheprovider'
UI_BASE_URL=http://127.0.0.1:8080 npm --prefix frontend run test:e2e
docker compose up -d ocr
python3 scripts/integration/extended_smoke.py --output reports/all-branches/documents.json
# All AI processes start, without substituting the unavailable external LLM.
docker compose up -d assistant ocr ocr-worker
python3 scripts/integration/ai_readiness.py --output reports/all-branches/ai-readiness.json
# Exercise the real installed OCR engine on a synthetic page, without any LLM call.
docker compose exec -T ocr python - <<'PY'
from PIL import Image, ImageDraw, ImageFont
from alfa_ocr.engines import Engine
image=Image.new('RGB',(1600,500),'white')
draw=ImageDraw.Draw(image)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',48)
draw.text((40,80),'Revenue 123456.78 RUB',font=font,fill='black')
engine=Engine('tesseract');engine.load()
blocks=engine.recognize(image)
assert '123456.78' in ' '.join(b.text for b in blocks)
print('REAL_TESSERACT_CPU_PASS')
PY
python3 scripts/integration/smoke.py --output reports/all-branches/before-restart.json
docker compose restart backend ml-bridge risk
python3 scripts/integration/smoke.py --replay --output reports/all-branches/restart.json
docker compose stop feed
python3 scripts/integration/smoke.py --expect-feed RULES --output reports/all-branches/feed-outage.json
docker compose up -d --wait --wait-timeout 300 gateway
docker compose stop risk
python3 scripts/integration/smoke.py --risk-outage --output reports/all-branches/risk-outage.json
docker compose up -d --wait --wait-timeout 300 gateway
# Recreate the containers, retaining all volumes and model artifacts.
docker compose down
docker compose up -d --wait --wait-timeout 300 gateway
python3 scripts/integration/smoke.py --replay --output reports/all-branches/recreate.json
docker compose up -d assistant ocr ocr-worker
python3 scripts/integration/ai_readiness.py --output reports/all-branches/ai-restart.json

# Preserve both recommendation implementations in one service; train a new synthetic release.
mkdir -p .local
# The model volume contains the checksum-verified E5 downloaded on this clean runner.
docker build --target preparation -f deploy/Dockerfile.feed -t credit-feed-tools:local .
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -v credit-integrated-mvp_feed-bundle:/legacy:ro -v "$PWD/.local:/releases" -v "$PWD/reports/all-branches:/evidence" --entrypoint python credit-feed-tools:local -m feed_v2.pipeline --work /releases/feed-v2 --reports /evidence/feed-v2 --model-source /legacy/model --users 500 --skip-http
export FEED_RELEASE=v2 FEED_BUNDLE_PATH=./.local/feed-v2/e5 FEED_RANKER=e5 FRAUD_MODE=synthetic
docker compose up -d --wait --wait-timeout 300 gateway
python3 scripts/integration/smoke.py --output reports/all-branches/feed-v2-e5.json
python3 scripts/integration/review_smoke.py --output reports/all-branches/dual-model-review.json
export FEED_RANKER=catboost FEED_BUNDLE_PATH=./.local/feed-v2/catboost
docker compose up -d --wait --wait-timeout 300 gateway
python3 scripts/integration/smoke.py --output reports/all-branches/feed-v2-catboost.json
