"""Ranking metrics with complete relevance judgments and user-clustered intervals."""
import numpy as np


def quality(ids, relevance):
    gains = np.array([relevance[i] for i in ids], dtype=float)
    ideal = np.sort(np.array(list(relevance.values()), dtype=float))[::-1]
    out = {}
    for k in (3, 6):
        discounts = np.log2(np.arange(2, min(k, len(gains)) + 2))
        dcg = np.sum((2 ** gains[:k] - 1) / discounts)
        best = np.sum((2 ** ideal[:k] - 1) / discounts)
        out['ndcg' + str(k)] = float(dcg / best) if best else 0.
    total = sum(v >= 2 for v in relevance.values())
    out['recall6'] = sum(relevance[i] >= 2 for i in ids[:6]) / total if total else 0.
    return out


def clustered_interval(differences, seed=20261022, samples=1000):
    values = np.asarray(list(differences), dtype=float)
    if not len(values):
        return [None, None]
    rng = np.random.default_rng(seed)
    means = [float(np.mean(rng.choice(values, size=len(values), replace=True))) for _ in range(samples)]
    return list(map(float, np.quantile(means, [.025, .975])))
