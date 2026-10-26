"""Train-only synthetic integration examples; never read by the model."""
import json
from .features import canonical

def create_fixtures(rows, statements, prediction, threshold, bundle_digest, policy_version):
    valid = [
        i for i, statement in enumerate(statements)
        if statement['values']['equityMinor'] >= 0
        and statement['values']['totalLiabilitiesMinor'] * 10
        < statement['values']['totalAssetsMinor'] * 9
        and statement['values']['revenueMinor'] // 4 > 50000000
    ]
    low = min(valid, key=lambda i: prediction[i])
    high = max(valid, key=lambda i: prediction[i])
    assert prediction[low] < threshold * 0.7
    assert prediction[high] > threshold * 1.3
    base = statements[low]
    adverse = statements[high]
    refused = json.loads(canonical(base))
    values = refused['values']
    values['totalLiabilitiesMinor'] = values['totalAssetsMinor'] * 95 // 100
    values['equityMinor'] = values['totalAssetsMinor'] - values['totalLiabilitiesMinor']
    values['currentLiabilitiesMinor'] = min(
        values['currentLiabilitiesMinor'], values['totalLiabilitiesMinor']
    )
    companies = []
    configurations = [
        ('S01', 'Одобрение', base, 20000000),
        ('S02', 'Отказ по правилу', refused, 20000000),
        ('S03', 'Уточнение выручки', base, 20000000),
        ('S04', 'Другие условия', base, 500000001),
        ('S05', 'Ручная проверка', adverse, 20000000),
        ('S06', 'Сбой ML', base, 20000000),
    ]
    for number, name, statement, amount in configurations:
        initial = json.loads(canonical(statement))
        if number == 'S03':
            initial['values']['revenueMinor'] *= 2
        companies.append({
            'companyId': 'DEMO:' + number,
            'name': f'Демо {number} · {name}',
            'businessAgeMonths': 36,
            'synthetic': True,
            'sourceRecordId': 'SIM:SOURCE:' + number,
            'sourceVersion': 1,
            'availableAt': '2026-04-01T00:00:00Z',
            'reference': statement,
            'initial': initial,
            'amountMinor': amount,
            'termMonths': 12,
        })
    return {
        'synthetic': True,
        'bundleDigest': bundle_digest,
        'policyVersion': policy_version,
        'selectionSource': 'train',
        'sourceTrainIds': {'low': rows[low]['company_id'], 'high': rows[high]['company_id']},
        'companies': companies,
    }
