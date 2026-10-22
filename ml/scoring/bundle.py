"""Stable eight-feature serving interface, independent of the classifier family."""
import hashlib
import importlib.metadata
import json
from pathlib import Path

import joblib
import numpy as np

from .features import FEATURES, FIELDS, code_digest, digest


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_manifest(path):
    root = Path(path).resolve()
    manifest = json.loads((root / 'manifest.json').read_text())
    unsigned = {k: v for k, v in manifest.items() if k != 'bundleDigest'}
    if digest(unsigned) != manifest.get('bundleDigest'):
        raise ValueError('Bundle digest mismatch')
    if manifest.get('featureCodeDigest') != code_digest():
        raise ValueError('Feature code digest mismatch')
    if (manifest.get('featureSchemaVersion'), manifest.get('features'), manifest.get('rawWhitelist')) != (2, FEATURES, list(FIELDS)):
        raise ValueError('Only the existing eight-feature schema 2 interface is supported')
    if tuple(manifest.get(k) for k in ('scoreKind', 'validationStatus', 'purpose')) != ('BANKRUPTCY_PROXY', 'DEMONSTRATION', 'DEMO_RESEARCH'):
        raise ValueError('Unsupported risk interpretation')
    required = {'model.joblib', 'policy.json', 'selection-lock.json', 'evaluation.json', 'feature-schema.json', 'model-card.md'}
    if not required <= manifest.get('artifacts', {}).keys():
        raise ValueError('Incomplete bundle')
    for name, expected in manifest['artifacts'].items():
        artifact = (root / name).resolve()
        if artifact.parent != root or not artifact.is_file() or file_hash(artifact) != expected:
            raise ValueError('Artifact path/checksum mismatch: ' + name)
    for lib in ('numpy', 'scikit-learn', 'scipy', 'joblib', 'catboost'):
        if importlib.metadata.version(lib) != manifest['libraries'].get(lib):
            raise ValueError('Library version mismatch: ' + lib)
    lock = json.loads((root / 'selection-lock.json').read_text())
    if lock['modelHash'] != manifest['artifacts']['model.joblib'] or lock['policyHash'] != manifest['artifacts']['policy.json']:
        raise ValueError('Selection lock mismatch')
    policy = json.loads((root / 'policy.json').read_text())
    threshold = policy.get('T_manual')
    if type(threshold) not in (int, float) or not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('Invalid manual-review threshold')
    if manifest['artifacts']['feature-schema.json'] != manifest['featureSchemaDigest']:
        raise ValueError('Feature schema digest mismatch')
    return manifest


def predict_probability(model, x):
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or x.shape[1] != len(FEATURES) or np.isinf(x).any():
        raise ValueError('Expected an eight-feature matrix; missing ratios may be NaN')
    if list(model.classes_) != [0, 1]:
        raise ValueError('Expected binary classes [0, 1]')
    probability = np.asarray(model.predict_proba(x))
    if probability.shape != (len(x), 2) or not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
        raise ValueError('Invalid model probabilities')
    if not np.allclose(probability.sum(axis=1), 1, atol=1e-8):
        raise ValueError('Class probabilities do not sum to one')
    return probability[:, 1]


def load_bundle(path):
    manifest = read_manifest(path)
    # Only trusted local, checksum-verified joblib artifacts may be deserialized.
    model = joblib.load(Path(path) / 'model.joblib')
    probes = np.zeros((2, len(FEATURES)))
    probes[1, [3, 5]] = np.nan
    predict_probability(model, probes)
    return model, manifest, json.loads((Path(path) / 'policy.json').read_text())
