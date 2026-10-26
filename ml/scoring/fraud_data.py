"""Reproducible paired simulation, NOT evidence of real fraud detection.

The latent generation process assigns labels. Identical observable changes can
have either label: financial differences alone cannot establish intent.
"""
import copy
import hashlib
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from .features import FIELDS, statement_from_row, validate

SEED = 20261022
VERSION = 'paired-financial-manipulation-v1'
HELD_OUT_FAMILY = 'combined_assets_profit'


def code_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def changed(reference, family, fraction):
    statement = copy.deepcopy(reference)
    v = statement['values']
    if family == 'revenue':
        v['revenueMinor'] += round(abs(v['revenueMinor']) * fraction)
    elif family == 'profit':
        for field in ('netProfitMinor', 'ebitMinor'):
            v[field] += round(max(abs(v[field]), v['totalAssetsMinor'] // 100) * fraction)
    elif family == 'liabilities':
        change = round(v['totalLiabilitiesMinor'] * fraction)
        v['totalLiabilitiesMinor'] -= change
        v['currentLiabilitiesMinor'] = min(v['currentLiabilitiesMinor'], v['totalLiabilitiesMinor'])
        v['equityMinor'] += change
    elif family == HELD_OUT_FAMILY:
        change = round(v['totalAssetsMinor'] * fraction)
        v['totalAssetsMinor'] += change
        v['equityMinor'] += change
        for field in ('netProfitMinor', 'ebitMinor'):
            v[field] += round(max(abs(v[field]), v['totalAssetsMinor'] // 100) * fraction)
    else:
        raise ValueError('Unknown simulation family')
    validate(statement)
    return statement


def pairs_for_row(row):
    reference = statement_from_row(row)
    # Stable across ordering, Python versions and independent split reads.
    seed = int(hashlib.sha256(f'{SEED}:{row["company_id"]}'.encode()).hexdigest()[:16], 16)
    rng = np.random.default_rng(seed)
    pairs = []

    def add(statement, label, family):
        pairs.append({'companyId': row['company_id'], 'reference': reference,
                      'statement': statement, 'target': label, 'family': family})

    add(copy.deepcopy(reference), 0, 'unchanged')
    # Benign restatements include the same positive directions and ranges as
    # attacks. In most benign cases the correction is downward; some are upward.
    for family in ('revenue', 'profit', 'liabilities'):
        fraction = float(rng.uniform(.01, .19))
        direction = 1 if rng.random() < .12 else -1
        if family == 'liabilities' and direction < 0:
            # Increasing debt can make equity negative, but still is valid data.
            statement = copy.deepcopy(reference)
            v = statement['values']
            delta = round(v['totalLiabilitiesMinor'] * fraction)
            v['totalLiabilitiesMinor'] += delta
            v['equityMinor'] -= delta
            validate(statement)
        else:
            statement = changed(reference, family, direction * fraction)
        add(statement, 0, 'benign_' + family)
        add(changed(reference, family, float(rng.uniform(.01, .19))), 1, family)
    return pairs


def load_split(dataset, split):
    # Deliberately do not even load target_12m or generator truth.
    rows = pq.read_table(Path(dataset) / 'simulation_splits' / f'{split}.parquet',
                         columns=['company_id', *FIELDS]).to_pylist()
    return rows, [pair for row in rows for pair in pairs_for_row(row)]


def held_out_pairs(rows):
    return [{'companyId': row['company_id'], 'reference': statement_from_row(row),
             'statement': changed(statement_from_row(row), HELD_OUT_FAMILY, .12),
             'target': 1, 'family': HELD_OUT_FAMILY} for row in rows]
