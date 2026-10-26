#!/usr/bin/env python3
"""Regenerate only executable integration contracts and synchronized feed assets."""
import json
import os
from pathlib import Path
import shutil
import sys
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'ml'))
os.environ.setdefault('ML_DATABASE_URL','postgresql://unused/unused')
os.environ.setdefault('ML_INTERNAL_TOKEN','schema-generation-token-not-a-live-secret')
from bridge.server import create_app
from scoring.server import app as risk
from feed.catalog import Catalog
bridge=create_app(token='schema-generation-token-not-a-live-secret')
for path,value in [(root/'docs/architecture/contracts/backend-ml.openapi.json',bridge.openapi()),
                   (root/'ml/openapi.json',risk.openapi())]:
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
source=root/'ml/feed/catalog';target=root/'backend/app/src/main/resources/feed'
target.mkdir(parents=True,exist_ok=True)
shutil.copy2(source/'cards.json',target/'cards.json')
shutil.copytree(source/'illustrations',target/'illustrations',dirs_exist_ok=True)
shutil.copy2(root/'ml/bridge/fixtures/backend-policy.json', root/'backend/app/src/test/resources/backend-policy.json')
print(json.dumps({'bridgeVersion':bridge.version,'catalogDigest':Catalog().digest,'runtimeRiskPaths':len(risk.openapi()['paths'])}))
