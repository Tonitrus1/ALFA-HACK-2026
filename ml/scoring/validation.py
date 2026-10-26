"""Seal already obtained independent and integration evidence into an offline candidate."""
import argparse
import json
from pathlib import Path
import shutil

from .bundle import load_bundle
from .train import ROOT, finalize_manifest, write


def seal(candidate, independent_report, compatibility_report):
    candidate=Path(candidate).resolve()
    if ROOT/'ml/artifacts' in candidate.parents:
        raise ValueError('Published artifacts are immutable; validate an offline candidate')
    _,manifest,_=load_bundle(candidate)
    if manifest.get('releaseStatus')!='candidate' or (candidate/'independent-validation.json').exists():
        raise ValueError('Candidate already evaluated; do not select among repeated holdouts')
    independent=json.loads(Path(independent_report).read_text())
    compatibility=json.loads(Path(compatibility_report).read_text())
    model_hash=manifest['artifacts']['model.joblib']
    if (independent['protocol']['candidateModelHash']!=model_hash
        or compatibility['modelHash']!=model_hash or not compatibility['passed']):
        raise ValueError('Evidence does not match the candidate model or API verification failed')
    criteria=independent['protocol']['promotionCriteria']
    if criteria!={'recallDifferenceLower95Above':0.,'APDifferenceAtLeast':0.,'LoglossDifferenceAtMost':.002}:
        raise ValueError('Unexpected confirmation criteria')
    checks={'primaryRecallLower95Positive':independent['paired95']['recall5'][0]>0,
            'APNotWorse':independent['eligiblePairedDifference']['averagePrecision']>=0,
            'ordinaryLoglossGuard':independent['eligiblePairedDifference']['logLoss']<=.002}
    if independent['checks']!=checks or independent['passed']!=all(checks.values()):
        raise ValueError('Confirmation decision inconsistent with metrics')
    shutil.copy2(independent_report,candidate/'independent-validation.json')
    shutil.copy2(compatibility_report,candidate/'compatibility.json')
    metadata={k:v for k,v in manifest.items() if k not in {'artifacts','bundleDigest'}}
    metadata['releaseStatus']='validated-demo' if independent['passed'] else 'evaluated-candidate'
    lock=json.loads((candidate/'selection-lock.json').read_text())
    lock['independentEvaluation']='passed on new synthetic data' if independent['passed'] else 'completed; primary superiority not established'
    write(candidate/'selection-lock.json',lock)
    finalized=finalize_manifest(candidate,metadata)
    load_bundle(candidate)
    return {'releaseStatus':finalized['releaseStatus'],'bundleDigest':finalized['bundleDigest'],'activated':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',required=True);p.add_argument('--independent-report',required=True);p.add_argument('--compatibility-report',required=True)
    a=p.parse_args();print(json.dumps(seal(a.candidate,a.independent_report,a.compatibility_report),indent=2))


if __name__=='__main__':main()
