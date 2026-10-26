"""Backend envelope validation with byte-identical training delta transformation.

No value repair, no dependence on preliminary revenue, IDs or risk score.
"""
import hashlib
from pathlib import Path
from .backend_input import build_backend
from .features import FIELDS

def adapter_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def build(statement, reference):
    build_backend(statement)
    build_backend(reference)
    if (statement['periodStart'], statement['periodEnd'], statement['currency']) != (reference['periodStart'], reference['periodEnd'], reference['currency']):
        raise ValueError('Reference period/currency mismatch')
    declared, trusted = statement['values'], reference['values']
    result = {}
    for field in FIELDS.values():
        delta=(declared[field]-trusted[field])/max(abs(trusted[field]),100)
        result['delta_'+field]=delta
        result['abs_delta_'+field]=abs(delta)
    return result
