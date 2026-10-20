"""Offline-only preparation. The synthetic truth file is never opened."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import joblib
import numpy as np
import pyarrow.parquet as pq
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss, confusion_matrix
from .features import FIELDS, FEATURES, statement_from_row, matrix, code_digest, digest, canonical

def file_hash(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def pipeline(c):
    return Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True)),('scaler',StandardScaler()),
                     ('model',LogisticRegression(C=c,max_iter=2000,random_state=42))])
def load(p):
    columns=list(FIELDS)+['company_id','target_12m','split']
    rows=pq.read_table(p,columns=columns).to_pylist()
    return rows,[statement_from_row(r) for r in rows],np.array([r['target_12m'] for r in rows])
def evaluate(y,s,t):
    return {'rows':len(y),'events':int(y.sum()),'prevalence':float(y.mean()),'rocAuc':float(roc_auc_score(y,s)),
            'averagePrecision':float(average_precision_score(y,s)),'brier':float(brier_score_loss(y,s)),
            'logLoss':float(log_loss(y,s)),'confusionMatrixAtManualThreshold':confusion_matrix(y,s>=t).tolist(),
            'scoreQuantiles':dict(zip(['min','p10','p50','p80','p90','p99','max'],np.quantile(s,[0,.1,.5,.8,.9,.99,1]).tolist()))}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--dataset',type=Path,required=True); parser.add_argument('--output',type=Path,default=Path('ml/artifacts/baseline')); args=parser.parse_args()
    root,out=args.dataset.resolve(),args.output; out.mkdir(parents=True,exist_ok=True)
    manifest_lines=(root/'MANIFEST.sha256').read_text().splitlines()
    published={line.split(maxsplit=1)[1].lstrip('*'):line.split()[0] for line in manifest_lines if line.strip()}
    paths={k:root/'simulation_splits'/f'{k}.parquet' for k in ['train','validation','test']}
    hashes={k:file_hash(v) for k,v in paths.items()}
    for k,p in paths.items():
        assert hashes[k]==published[str(p.relative_to(root))], f'Published checksum mismatch: {k}'
    tr,ts,ty=load(paths['train']); va,vs,vy=load(paths['validation'])
    assert (len(tr),int(ty.sum()),len(va),int(vy.sum()))==(7016,352,1494,80)
    assert not set(r['company_id'] for r in tr)&set(r['company_id'] for r in va)
    x,vx=matrix(ts),matrix(vs)
    candidates=[]
    for c in [.01,.1,1.,10.]:
        cv=cross_val_score(pipeline(c),x,ty,cv=StratifiedKFold(4,shuffle=True,random_state=42),scoring='average_precision',n_jobs=1)
        m=pipeline(c).fit(x,ty); score=m.predict_proba(vx)[:,1]
        candidates.append((float(average_precision_score(vy,score)),c,m,{'C':c,'cvAveragePrecision':cv.tolist(),'validationAveragePrecision':float(average_precision_score(vy,score))}))
    _,c,model,_=max(candidates,key=lambda a:(a[0],-a[1]))
    score=model.predict_proba(vx)[:,1]
    eligible=np.array([s['values']['equityMinor']>=0 and s['values']['totalLiabilitiesMinor']*10<s['values']['totalAssetsMinor']*9 and s['values']['revenueMinor']>=40000000 for s in vs])
    threshold=float(np.quantile(score[eligible],.8,method='higher'))
    selected=eligible&(score>=threshold)
    policy={'version':'synthetic-demo-policy-2','T_manual':threshold,'selection':'validation only; upper ~20% of hard-rule eligible observations; working-capital minimum cap; all business ages fixed eligible',
            'eligibleRows':int(eligible.sum()),'manualRows':int(selected.sum()),'manualEvents':int(vy[selected].sum()),'eligibleEvents':int(vy[eligible].sum()),
            'actualCoverage':float(selected.sum()/eligible.sum()),'tiedAtThreshold':int((score[eligible]==threshold).sum()),'comparison':'>=','synthetic':True}
    joblib.dump(model,out/'model.joblib'); write(out/'policy.json',policy)
    # Lock model and policy BEFORE opening test for evaluation. No tuning uses test.
    lock={'modelHash':file_hash(out/'model.joblib'),'policyHash':file_hash(out/'policy.json'),'C':c,'featureCodeDigest':code_digest()}
    write(out/'selection-lock.json',lock)
    te,es,ey=load(paths['test']); assert (len(te),int(ey.sum()))==(1490,80)
    ids=[set(r['company_id'] for r in rows) for rows in [tr,va,te]]
    assert not ids[0]&ids[2] and not ids[1]&ids[2]
    assert all(r['split']==k for k,rows in [('train',tr),('validation',va),('test',te)] for r in rows)
    report={'warning':'Metrics of fully synthetic financials and synthetic labels; no claim about Russian companies or bank PD.',
            'selectionLock':lock,'candidates':[a[3] for a in candidates],'splits':{k:evaluate(y,model.predict_proba(matrix(ss))[:,1],threshold) for k,ss,y in [('train',ts,ty),('validation',vs,vy),('test',es,ey)]},
            'datasetHashes':hashes,'uncertainty':'Single fixed synthetic sample; no population accuracy claim; intervals not estimated.'}
    write(out/'evaluation.json',report)
    manifest={'modelVersion':'synthetic-logistic-v1','featureSchemaVersion':2,'featureCodeDigest':code_digest(),'features':FEATURES,
              'rawWhitelist':list(FIELDS),'scoreKind':'BANKRUPTCY_PROXY','validationStatus':'DEMONSTRATION','purpose':'DEMO_RESEARCH',
              'financialsSynthetic':True,'labelsSynthetic':True,'datasetHashes':hashes,'datasetHash':file_hash(root/'training_simulation.parquet'),
              'splitMembershipDigest':digest({k:sorted(ids[i]) for i,k in enumerate(paths)}),'python':platform.python_version(),
              'libraries':{p:importlib.metadata.version(p) for p in ['numpy','scikit-learn','scipy','joblib','pyarrow']},
              'artifacts':{p.name:file_hash(p) for p in out.iterdir() if p.is_file() and p.name in ['model.joblib','policy.json','selection-lock.json','evaluation.json']}}
    manifest['bundleDigest']=digest(manifest); write(out/'manifest.json',manifest)
    (out/'model-card.md').write_text('# Synthetic logistic baseline\n\nFully invented SIM companies, financials and labels. BANKRUPTCY_PROXY / DEMONSTRATION / DEMO_RESEARCH. Not bank PD; not validated for real companies.\n\nEight contract ratios only. Median imputation + indicators, scaling, regularized logistic regression. Preprocessing fits only train. Four-fold CV on train; version selected by validation AP; test opened after selection-lock. Provided split retained, no resampling. No calibration applied.\n\nPolicy selects a demonstration review budget on eligible validation rows, not a risk norm. No business auto-decline derives from model score. Test is excluded from seed selection. Model serialization must only be loaded from locally trusted prepared artifacts.\n')
    # Demonstration examples selected exclusively from TRAIN after model/policy lock.
    preds=model.predict_proba(x)[:,1]
    valid=[i for i,s in enumerate(ts) if s['values']['equityMinor']>=0 and s['values']['totalLiabilitiesMinor']*10<s['values']['totalAssetsMinor']*9 and s['values']['revenueMinor']//4>50000000]
    low=min(valid,key=lambda i:preds[i]); high=max(valid,key=lambda i:preds[i]); assert preds[low]<threshold*.7 and preds[high]>threshold*1.3
    base=ts[low]; adverse=ts[high]; refused=json.loads(canonical(base)); refused['values']['totalLiabilitiesMinor']=refused['values']['totalAssetsMinor']*95//100; refused['values']['equityMinor']=refused['values']['totalAssetsMinor']-refused['values']['totalLiabilitiesMinor']; refused['values']['currentLiabilitiesMinor']=min(refused['values']['currentLiabilitiesMinor'],refused['values']['totalLiabilitiesMinor'])
    seed=[]
    for n,name,statement,amount in [('S01','Одобрение',base,20000000),('S02','Отказ по demo-правилу',refused,20000000),('S03','Уточнение выручки',base,20000000),('S04','Другие условия',base,500000001),('S05','Ручная проверка',adverse,20000000),('S06','Сбой ML (включает оператор)',base,20000000)]:
        initial=json.loads(canonical(statement))
        if n=='S03': initial['values']['revenueMinor']*=2
        seed.append({'companyId':'DEMO:'+n,'name':f'Демо {n} · {name}','businessAgeMonths':36,'synthetic':True,'sourceRecordId':'SIM:SOURCE:'+n,'sourceVersion':1,'availableAt':'2026-04-01T00:00:00Z','reference':statement,'initial':initial,'amountMinor':amount,'termMonths':12})
    generated=out.parent.parent/'generated'; generated.mkdir(exist_ok=True); write(generated/'companies.json',seed)
    fixtures=Path('ml/fixtures');fixtures.mkdir(exist_ok=True);write(fixtures/'scenarios.json',{'synthetic':True,'bundleDigest':manifest['bundleDigest'],'policyVersion':policy['version'],'selectionSource':'train only; test excluded','sourceTrainIds':{'low':tr[low]['company_id'],'high':tr[high]['company_id']},'companies':seed})
    reports=Path('reports'); reports.mkdir(exist_ok=True)
    for name in ['manifest.json','evaluation.json','policy.json','selection-lock.json','model-card.md']:
        (reports/name).write_bytes((out/name).read_bytes())
    print(json.dumps({'bundleDigest':manifest['bundleDigest'],'threshold':threshold,'trainSeedScores':[float(preds[low]),float(preds[high])],'test':report['splits']['test']},indent=2))
if __name__=='__main__': main()
