"""Training must not mutate published releases; policies must load as emitted."""
import importlib
import json
import shutil

import numpy as np
import pytest

from scoring.bundle import file_hash, load_bundle
from scoring.evaluation import create_policy
from scoring.train import ROOT, finalize_manifest

training = importlib.import_module('scoring.train')


def test_training_rejects_entire_publication_tree_before_reading_data(tmp_path, monkeypatch):
    project = tmp_path / 'project'
    artifacts = project / 'ml/artifacts'
    artifacts.mkdir(parents=True)
    sentinel = artifacts / 'release/model.joblib'
    sentinel.parent.mkdir()
    sentinel.write_bytes(b'published immutable artifact')
    outside = tmp_path / 'outside'
    outside.mkdir()
    (artifacts / 'escape').symlink_to(outside, target_is_directory=True)
    alias = tmp_path / 'artifact-alias'
    alias.symlink_to(artifacts, target_is_directory=True)
    monkeypatch.setattr(training, 'ROOT', project)
    before = sentinel.read_bytes()
    dataset = tmp_path / 'missing-data'
    forbidden = [artifacts, artifacts.parent, project, artifacts / 'new-unpublished-release',
                 artifacts / 'escape/new-candidate', alias / 'new-candidate']
    for output in forbidden:
        with pytest.raises(ValueError, match='new candidate'):
            training.train(dataset, output)
    assert sentinel.read_bytes() == before
    assert not list(outside.iterdir())
    assert not (artifacts / 'new-unpublished-release').exists()
    # An ordinary new offline output reaches dataset validation (no training).
    with pytest.raises(FileNotFoundError, match='MANIFEST.sha256'):
        training.train(dataset, outside / 'valid-offline-candidate')
    assert not (outside / 'valid-offline-candidate').exists()


def test_probability_one_boundary_tie_has_explicit_safe_failure():
    y = np.tile([0, 1], 50)
    eligible = np.ones(100, dtype=bool)
    with pytest.raises(ValueError, match=r'probability=1 boundary tie.*\[0,1\]'):
        create_policy(y, np.ones(100), eligible, 'test')


@pytest.mark.parametrize('scores', [np.zeros(100), np.full(100, .9),
                                  np.r_[np.linspace(0, .9, 95), np.ones(5)]])
def test_feasible_policies_roundtrip_in_complete_bundle(tmp_path, scores):
    eligible = np.ones(100, dtype=bool)
    policy = create_policy(np.tile([0, 1], 50), scores, eligible, 'test')
    assert 0 <= policy['T_manual'] <= 1 and policy['manualRows'] <= 5
    candidate = tmp_path / 'candidate'
    shutil.copytree(ROOT / 'ml/artifacts/baseline', candidate)
    manifest = json.loads((candidate / 'manifest.json').read_text())
    (candidate / 'policy.json').write_text(json.dumps(policy))
    lock = json.loads((candidate / 'selection-lock.json').read_text())
    lock['policyHash'] = file_hash(candidate / 'policy.json')
    (candidate / 'selection-lock.json').write_text(json.dumps(lock))
    finalize_manifest(candidate, {k: v for k, v in manifest.items() if k not in {'bundleDigest', 'artifacts'}})
    _, loaded, restored = load_bundle(candidate)
    assert restored == policy and loaded['featureSchemaVersion'] == 2
    assert len(loaded['rawWhitelist']) == 8
