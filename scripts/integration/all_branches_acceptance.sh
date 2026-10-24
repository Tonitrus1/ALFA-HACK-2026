#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports/all-branches
# No local model cache or host bundle: bootstrap real E5 into an empty named volume.
docker compose up -d --wait --wait-timeout 600 gateway
python3 scripts/integration/smoke.py --output reports/all-branches/public-flow.json
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
