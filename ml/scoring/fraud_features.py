"""Demonstration manipulation features. No IDs, labels or generator metadata."""
import hashlib
from pathlib import Path

import numpy as np

from .features import FIELDS, validate

FEATURES = [prefix + field for field in FIELDS.values() for prefix in ('delta_', 'abs_delta_')]
SCHEMA_VERSION = 1
SCORE_KIND = 'SYNTHETIC_MANIPULATION_PROXY'


def code_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def build(statement, reference):
    declared, trusted = validate(statement), validate(reference)
    result = {}
    for field in FIELDS.values():
        # A one-rouble floor keeps zero/near-zero reference values finite.
        delta = (declared[field] - trusted[field]) / max(abs(trusted[field]), 100)
        result['delta_' + field] = delta
        result['abs_delta_' + field] = abs(delta)
    return result


def matrix(pairs):
    return np.asarray([list(build(p['statement'], p['reference']).values()) for p in pairs], dtype=float)
