#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports/integration-linux .local/feed-bundle
export FEED_RELEASE=v1 FEED_RANKER=e5 FRAUD_MODE=off FEED_BUNDLE_PATH=./.local/feed-bundle
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 -v "$PWD/.local/feed-bundle:/bundle" --entrypoint python credit-mvp-feed:local -m feed.prepare --bundle /bundle --download
docker compose up -d --wait --wait-timeout 300
python3 scripts/integration/smoke.py --output reports/integration-linux/baseline.json
docker compose restart backend ml-bridge risk
python3 scripts/integration/smoke.py --replay --output reports/integration-linux/baseline-restart.json
docker compose stop feed
python3 scripts/integration/smoke.py --expect-feed RULES --output reports/integration-linux/baseline-feed-outage.json
docker compose start feed
docker compose stop risk
python3 scripts/integration/smoke.py --risk-outage --output reports/integration-linux/baseline-risk-outage.json
docker compose up -d --wait --wait-timeout 300
python3 scripts/integration/cursor_release.py --capture --output reports/integration-linux/cursor-capture.json --state .local/release-cursor.json
# Build-time/preparation tools only. Source, fixed seeds and evaluation protocol are versioned.
docker build --target preparation -f deploy/Dockerfile.feed -t credit-mvp-feed-tools:local .
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/.local:/releases" -v "$PWD/reports/integration-linux:/evidence" --entrypoint python credit-mvp-feed-tools:local -m feed_v2.pipeline --work /releases/feed-v2-linux --reports /evidence/feed-v2 --model-source /releases/feed-bundle/model --users 500 --skip-http
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -e FEED_V2_TEST_BUNDLE=/releases/feed-v2-linux/e5 -e FEED_LEARNED_TEST_BUNDLE=/releases/feed-v2-linux/catboost -v "$PWD/.local:/releases" -v "$PWD/docs:/app/docs:ro" --entrypoint python credit-mvp-feed-tools:local -m pytest ml/feed_v2/tests --with-model --with-learned -q
export FEED_RELEASE=v2 FEED_BUNDLE_PATH=./.local/feed-v2-linux/e5 FRAUD_MODE=synthetic
docker compose up -d --wait --wait-timeout 300
python3 scripts/integration/cursor_release.py --expired --state .local/release-cursor.json --output reports/integration-linux/old-cursor-expired.json
python3 scripts/integration/smoke.py --output reports/integration-linux/v2-synthetic.json
python3 scripts/integration/review_smoke.py --output reports/integration-linux/review-synthetic.json
UI_BASE_URL=http://127.0.0.1:8080 npm --prefix frontend run test:e2e
# Risk remains healthy; only its optional fraud router is disabled. Backend still requires fraud.
FRAUD_MODE=off docker compose up -d --no-deps --force-recreate --wait risk
python3 scripts/integration/review_smoke.py --expect-proxy UNAVAILABLE --output reports/integration-linux/fraud-outage.json
docker compose up -d --wait --wait-timeout 300
docker compose stop feed
python3 scripts/integration/smoke.py --expect-feed RULES --output reports/integration-linux/v2-feed-outage.json
docker compose up -d --wait --wait-timeout 300
python3 scripts/integration/smoke.py --output reports/integration-linux/v2-before-restart.json
docker compose restart backend ml-bridge risk
python3 scripts/integration/smoke.py --replay --output reports/integration-linux/v2-restart.json
docker compose exec -T ml-bridge python -c "import socket; s=socket.socket(); s.settimeout(2); r=s.connect_ex(('1.1.1.1',443)); s.close(); assert r != 0"
docker compose exec -T backend-db psql -U credit -d credit -c "SELECT count(*) AS bound_attempts FROM integration.fraud_attempt; SELECT count(*) AS persisted_results FROM integration.fraud_result;" > reports/integration-linux/fraud-persistence.txt
# Roll back configuration over the same volumes. No compose down -v, schema downgrade or user-data deletion.
export FEED_RELEASE=v1 FEED_BUNDLE_PATH=./.local/feed-bundle FRAUD_MODE=off
docker compose up -d --wait --wait-timeout 300
python3 scripts/integration/cursor_release.py --state .local/release-cursor.json --output reports/integration-linux/rollback-cursor.json
python3 scripts/integration/smoke.py --output reports/integration-linux/rollback-public-flow.json
# Roll back application Java sources to the verified base, retaining the applied additive migration pack.
mkdir -p .local/rollback-source
git archive 5b937b5b3e6761545a6f368ec134d2817d7b1ad7 backend | tar -x -C .local/rollback-source
cp backend/app/src/main/resources/db/migration/integration/V17__offer_commands.sql backend/app/src/main/resources/db/migration/integration/V18__synthetic_reference.sql .local/rollback-source/backend/app/src/main/resources/db/migration/integration/
cp backend/app/src/main/resources/db/seed/demo/R__demo_synthetic_reference_seed.sql .local/rollback-source/backend/app/src/main/resources/db/seed/demo/
docker build -f deploy/Dockerfile.backend -t credit-mvp-backend-rollback:local .local/rollback-source
printf 'services:\n  backend:\n    image: credit-mvp-backend-rollback:local\n' > .local/rollback-compose.yaml
docker compose -f compose.yaml -f .local/rollback-compose.yaml up -d --no-build --wait --wait-timeout 300 backend
python3 scripts/integration/smoke.py --output reports/integration-linux/rollback-java-baseline.json
python3 scripts/integration/cursor_release.py --state .local/release-cursor.json --output reports/integration-linux/rollback-java-cursor.json
docker compose up -d --wait --wait-timeout 300 backend
# Leave the prepared demonstration on E5 v2 and the explicitly selected synthetic proxy.
export FEED_RELEASE=v2 FEED_BUNDLE_PATH=./.local/feed-v2-linux/e5 FRAUD_MODE=synthetic
docker compose up -d --wait --wait-timeout 300
