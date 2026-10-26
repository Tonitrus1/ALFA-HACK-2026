import json
from pathlib import Path

import joblib
from catboost import CatBoostClassifier

ROOT = Path(__file__).resolve().parents[2]


def test_catboost_bundle_and_optuna_selection():
    bundle = ROOT / 'ml/artifacts/baseline'
    model = joblib.load(bundle / 'model.joblib')
    assert isinstance(model, CatBoostClassifier)
    assert model.get_param('nan_mode') == 'Min'
    report = json.loads((bundle / 'evaluation.json').read_text())
    study = json.loads((bundle / 'optuna-study.json').read_text())
    lock = json.loads((bundle / 'selection-lock.json').read_text())
    assert report['optimization']['library'] == 'optuna'
    assert study['objective'] == 'train_stratified_cv_average_precision'
    assert study['selectedTrial'] == lock['selectedTrial']
    completed = [trial for trial in study['trials'] if trial['state'] == 'COMPLETE']
    assert completed
    selected = next(trial for trial in completed if trial['number'] == lock['selectedTrial'])
    assert len(selected['userAttrs']['foldAveragePrecision']) == study['folds']
    assert model.tree_count_ == lock['params']['iterations']
    assert lock['params']['depth'] == selected['params']['depth']
    assert report['splits']['test']['rows'] == 1490
    assert report['splits']['validation']['rows'] == 1494
