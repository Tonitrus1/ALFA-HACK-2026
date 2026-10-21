import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

FIELDS = dict(zip(
    ['total_assets','current_assets','total_liabilities','current_liabilities','equity','revenue','net_profit','ebit'],
    ['totalAssetsMinor','currentAssetsMinor','totalLiabilitiesMinor','currentLiabilitiesMinor','equityMinor','revenueMinor','netProfitMinor','ebitMinor']))
FEATURES = ['X1','X2','X3','X4','X7','X8','X9','X10']
MAX_MINOR = 9007199254740991

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def code_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def rub_to_minor(value):

    number = Decimal(str(value)) * 100
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError('Money must have exactly kopeck precision')
    n = int(number)
    if abs(n) > MAX_MINOR:
        raise ValueError('Money exceeds safe integer range')
    return n

def statement_from_row(row):
    return {'periodStart':'2025-01-01','periodEnd':'2025-12-31','currency':'RUB','reportingStandard':'DEMO',
            'values':{api:rub_to_minor(row[src]) for src,api in FIELDS.items()},'sourceDocumentReferences':[]}

def validate(statement):
    if set(statement) != {'periodStart','periodEnd','currency','reportingStandard','values','sourceDocumentReferences'}:
        raise ValueError('Unexpected statement fields')
    if statement['currency'] != 'RUB' or statement['reportingStandard'] != 'DEMO':
        raise ValueError('Only DEMO annual RUB statements are supported')
    start, end = date.fromisoformat(statement['periodStart']), date.fromisoformat(statement['periodEnd'])
    if start != date(2025,1,1) or end != date(2025,12,31):
        raise ValueError('MVP requires full calendar year 2025')
    if statement['sourceDocumentReferences']:
        raise ValueError('Document pipeline is outside scoring MVP')
    v = statement['values']
    if set(v) != set(FIELDS.values()):
        raise ValueError('All eight financial fields are required; no extra fields')
    for k,n in v.items():
        if type(n) is not int or abs(n)>MAX_MINOR:
            raise ValueError(f'{k}: integer kopecks required')
        if k not in {'equityMinor','netProfitMinor','ebitMinor'} and n<0:
            raise ValueError(f'{k}: nonnegative value required')
    a,l,e = (v[k] for k in ['totalAssetsMinor','totalLiabilitiesMinor','equityMinor'])
    if a<=0 or v['currentAssetsMinor']>a or v['currentLiabilitiesMinor']>l:
        raise ValueError('Assets must be positive; current components cannot exceed totals')
    if abs(a-l-e)>1:
        raise ValueError('Balance mismatch exceeds one kopeck; check units')
    return v

def build(statement):
    v = validate(statement)
    a,c,l,cl,e,r,n,b = (Decimal(v[FIELDS[x]]) for x in FIELDS)
    def ratio(x,y): return None if y==0 else float(x/y)
    return dict(zip(FEATURES,[ratio(n,a),ratio(l,a),ratio(c-cl,a),ratio(c,cl),ratio(b,a),ratio(e,l),ratio(r,a),ratio(e,a)]))

def matrix(statements):
    import numpy as np
    return np.array([[float('nan') if v is None else v for v in build(s).values()] for s in statements])
