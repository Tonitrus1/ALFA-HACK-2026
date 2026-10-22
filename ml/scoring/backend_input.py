"""Versioned backend financial envelope; strict legacy feature module stays byte-identical.

The backend profile accepts confirmed annual statements and its documented balance tolerance.
Numbers are never repaired. Model inputs are the same eight Decimal ratios, tested against build().
Document references are retained as provenance; neither text nor document bytes enter the model.
"""
import hashlib
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .features import FIELDS, FEATURES, MAX_MINOR


def adapter_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def build_backend(statement):
    if set(statement) != {'periodStart', 'periodEnd', 'currency', 'reportingStandard',
                          'values', 'sourceDocumentReferences'}:
        raise ValueError('Unexpected statement fields')
    if statement['currency'] != 'RUB' or statement['reportingStandard'] != 'DEMO':
        raise ValueError('Only DEMO RUB statements are supported')
    start, end = date.fromisoformat(statement['periodStart']), date.fromisoformat(statement['periodEnd'])
    if start != date(start.year, 1, 1) or end != date(start.year, 12, 31):
        raise ValueError('Full calendar year required')
    values = statement['values']
    if set(values) != set(FIELDS.values()):
        raise ValueError('Exactly eight financial fields required')
    for name, value in values.items():
        if type(value) is not int or abs(value) > MAX_MINOR:
            raise ValueError('Safe integer kopecks required')
        if name not in {'equityMinor', 'netProfitMinor', 'ebitMinor'} and value < 0:
            raise ValueError('Negative unsigned financial field')
    a, c, l, cl, e, r, n, b = (Decimal(values[FIELDS[x]]) for x in FIELDS)
    if a <= 0 or c > a or cl > l:
        raise ValueError('Financial component invariant violated')
    tolerance = max(Decimal(100), (a * Decimal('.01')).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if abs(a - l - e) > tolerance:
        raise ValueError('Balance exceeds backend demo tolerance')
    references = statement['sourceDocumentReferences']
    if not isinstance(references, list) or len(references) > 100:
        raise ValueError('Invalid source references')
    for ref in references:
        if set(ref) != {'documentId', 'documentVersion', 'objectVersion'} or type(ref['documentVersion']) is not int or ref['documentVersion'] < 1 or not all(isinstance(ref[k], str) and 0 < len(ref[k]) <= 128 for k in ('documentId','objectVersion')):
            raise ValueError('Exact document references required')
    def ratio(x, y):
        return None if y == 0 else float(x / y)
    return dict(zip(FEATURES, [ratio(n, a), ratio(l, a), ratio(c-cl, a), ratio(c, cl),
                               ratio(b, a), ratio(e, l), ratio(r, a), ratio(e, a)]))
