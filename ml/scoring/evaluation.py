"""Shared offline metrics; no target or cohort markers enter the model input."""
import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score


def financial_hard_rules_pass(statement):
    v = statement['values']
    return (v['equityMinor'] >= 0
            and v['totalLiabilitiesMinor'] * 10 < v['totalAssetsMinor'] * 9)


def financial_eligible(statement):
    """Financial portion of precheck only; application/product checks stay in backend."""
    return financial_hard_rules_pass(statement) and statement['values']['revenueMinor'] > 0


def evaluate(y, probability):
    y = np.asarray(y)
    p = np.asarray(probability, dtype=float)
    if y.ndim != 1 or not len(y) or not np.isin(y, [0, 1]).all() or p.shape != y.shape or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Nonempty aligned targets and finite probabilities required')
    events = int(y.sum())
    both = len(np.unique(y)) == 2
    result = {'rows': len(y), 'events': events, 'prevalence': float(y.mean()),
              'baselineAP': float(y.mean()),
              'averagePrecision': float(average_precision_score(y, p)) if events else None,
              'rocAuc': float(roc_auc_score(y, p)) if both else None,
              'logLoss': float(log_loss(y, p, labels=[0, 1])),
              'brier': float(brier_score_loss(y, p)), 'meanPrediction': float(p.mean())}
    for percent in (5, 10, 20):
        count = int(np.floor(len(y) * percent / 100))
        chosen = np.argsort(-p, kind='stable')[:count]
        hits = int(y[chosen].sum())
        result[f'top{percent}'] = {'reviewed': count, 'eventsFound': hits,
                                 'precision': hits / count if count else None,
                                 'recall': hits / events if events else None,
                                 'coverage': count / len(y)}
    return result


def operating_key(y, p, eligible):
    if not np.any(eligible) or len(np.unique(y[eligible])) != 2:
        raise ValueError('Both outcomes required in the eligible development cohort')
    report = evaluate(y[eligible], p[eligible])
    return (report['top5']['recall'], report['averagePrecision'], -report['logLoss'])


def create_policy(y, p, eligible, version):
    y, p, eligible = np.asarray(y), np.asarray(p, dtype=float), np.asarray(eligible)
    if (y.ndim != 1 or not len(y) or not np.isin(y, [0, 1]).all()
            or p.shape != y.shape or not np.isfinite(p).all()
            or ((p < 0) | (p > 1)).any()
            or eligible.shape != y.shape or eligible.dtype != np.bool_):
        raise ValueError('Aligned binary targets, finite probabilities and boolean eligibility required')
    scores = p[eligible]
    count = int(np.floor(.05 * len(scores)))
    if count < 1:
        raise ValueError('Insufficient eligible development rows for a 5% policy')
    ordered = np.sort(scores)[::-1]
    threshold = float(ordered[count - 1])
    # Serving compares >=. Exclude an entire boundary tie rather than exceed capacity.
    if count < len(scores) and ordered[count] == threshold:
        if threshold == 1.0:
            raise ValueError('Cannot exclude the probability=1 boundary tie with a threshold in [0,1]; no valid 5% policy')
        threshold = float(np.nextafter(threshold, np.inf))
    chosen = np.asarray(eligible) & (p >= threshold)
    return {'version': version, 'T_manual': threshold, 'selectionSplit': 'train_oof',
            'manualQuantile': .95, 'eligibleRows': int(np.sum(eligible)),
            'eligibleEvents': int(y[eligible].sum()), 'manualRows': int(chosen.sum()),
            'manualEvents': int(y[chosen].sum()), 'actualCoverage': float(chosen.sum() / len(scores)),
            'comparison': '>=', 'synthetic': True, 'capacityTarget': .05,
            'eligibility': 'equity>=0; liabilities/assets<0.9; revenue>0; application checks unavailable',
            'capacityGuarantee': 'development cohort only; future static threshold cannot guarantee 5%',
            'tiePolicy': 'exclude whole boundary tie when necessary'}
