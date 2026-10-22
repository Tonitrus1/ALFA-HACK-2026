from copy import deepcopy
import json
from pathlib import Path
import pytest
from scoring.fraud_features import build as original
from scoring.fraud_backend_input import build

def reference():
    return json.loads(Path('reports/ui-feed-antifraud/synthetic-reference-manifest.json').read_text())[0]['statement']

def test_delta_parity_and_backend_signed_tolerance_documents():
    ref=reference(); declared=deepcopy(ref)
    for field in ('netProfitMinor','equityMinor','ebitMinor'):
        declared=deepcopy(ref);declared['values'][field]+=100
        if field=='equityMinor':declared['values']['totalAssetsMinor']+=100
        assert build(declared,ref)==original(declared,ref)
    declared=deepcopy(ref);declared['values']['netProfitMinor']=-100
    declared['values']['equityMinor']+=1000000
    declared['sourceDocumentReferences']=[dict(documentId='doc',documentVersion=1,objectVersion='v1')]
    assert build(declared,ref)['delta_netProfitMinor']<0
    assert declared['values']['equityMinor']==61000000

def test_reference_period_and_invalid_values_are_not_repaired():
    ref=reference();declared=deepcopy(ref);declared['periodStart']='2024-01-01';declared['periodEnd']='2024-12-31'
    with pytest.raises(ValueError):build(declared,ref)
    declared=deepcopy(ref);declared['values']['totalAssetsMinor']=None
    with pytest.raises(ValueError):build(declared,ref)
