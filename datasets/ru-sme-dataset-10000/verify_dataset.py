import json,re,hashlib
from pathlib import Path
from collections import Counter
from decimal import Decimal
import pyarrow.parquet as pq
def identifier(value,kind='inn'):
    assert isinstance(value,str) and value.isascii() and value.isdigit()
    if kind=='inn':
        assert len(value)==10 and sum(int(a)*b for a,b in zip(value[:9],[2,4,10,3,5,9,4,6,8]))%11%10==int(value[-1])
    else:
        assert len(value)==13 and int(value[:12])%11%10==int(value[-1])
root=Path(__file__).resolve().parent
registry=pq.read_table(root/'registry_companies_real.parquet').to_pylist()
hybrid=pq.read_table(root/'hybrid_real_msps_synthetic_financials.parquet').to_pylist()
sim=pq.read_table(root/'training_simulation.parquet').to_pylist()
assert len(registry)==len(hybrid)==len(sim)==10000
assert len({r['inn'] for r in registry})==10000 and len({r['ogrn'] for r in registry})==10000
for r in registry:
 identifier(r['inn']);identifier(r['ogrn'],'ogrn')
 assert not r['is_synthetic'] and r['okved'][:2] not in ('64','65','66') and r['legal_form']=='LLC'
for r in hybrid+sim:
 assert r['total_assets']==r['equity']+r['total_liabilities']
 assert r['total_liabilities']==r['current_liabilities']+r['long_term_liabilities']
 assert r['total_assets']==r['current_assets']+r['non_current_assets']
 assert r['current_assets']==r['cash']+r['receivables']+r['inventories']+r['other_current_assets']
 assert r['net_profit']==r['ebit']-r['interest_expense']+r['other_income']-r['tax_expense']
 assert r['is_synthetic'] and r['financial_is_synthetic'] and r['currency']=='RUB'
assert all(r['target_12m'] is None and not r['label_is_synthetic'] for r in hybrid)
assert all(r['company_id'].startswith('SIM:') and r['label_is_synthetic'] and r['target_12m'] in (0,1) for r in sim)
assert 'inn' not in sim[0] and 'name' not in sim[0] and 'true_probability_synthetic' not in sim[0]
for r in sim:
 if r['target_12m']: assert r['as_of_date']<r['event_date']<=r['horizon_end']
 else: assert r['event_date'] is None
splits={s:pq.read_table(root/'simulation_splits'/(s+'.parquet')).to_pylist() for s in ['train','validation','test']}
ids={s:{r['company_id'] for r in rows} for s,rows in splits.items()}
assert not ids['train']&ids['validation'] and not ids['train']&ids['test'] and not ids['validation']&ids['test']
assert len(set().union(*ids.values()))==10000
raw=(root/'raw/rsmp_selected_documents.xml').read_text(encoding='utf-8')
doc_hashes={hashlib.sha256(m.group(0).encode()).hexdigest() for m in re.finditer(r'<Документ(?=\s|>).*?</Документ>',raw,re.S)}
assert len(doc_hashes)==10000 and doc_hashes=={r['source_document_sha256'] for r in registry}
assert '<ИПВклМСП' not in raw
report={'status':'PASS','real_registry_rows':len(registry),'hybrid_rows':len(hybrid),'simulation_rows':len(sim),'unique_inns':10000,'unique_ogrns':10000,
 'regional_codes':len({r['region'] for r in registry}),'okved_divisions':len({r['okved'][:2] for r in registry}),
 'msp_categories':dict(Counter(r['msp_category'] for r in registry)), 'source_document_hashes_verified':10000,
 'accounting_identities_checked_on_rows':20000,'real_outcomes_known':0,'synthetic_positive_labels':sum(r['target_12m'] for r in sim),
 'disjoint_splits':{s:len(x) for s,x in ids.items()},'synthetic_labels_attached_to_real_inns':False,
 'note':'Synthetic financials and labels are not evidence about real company solvency.'}
(root/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
