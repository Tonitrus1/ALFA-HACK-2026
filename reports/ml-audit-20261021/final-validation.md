# Independent validation acceptance — 21 October 2026

PASS. No unresolved blocking defects in the frozen integration checkout `integration checkout`, branch `integration/ml-audit-20261021`. Import origins were checked explicitly inside this checkout; reused dependency environments did not redirect imports to the original repositories.

| Verification | Result |
|---|---|
| CatBoost baseline isolated HTTP/PG, port 18742 | 31 passed |
| Evaluated logistic candidate isolated HTTP/PG, port 18743 | 31 passed |
| Real offline E5 tests | 58 passed, no skipped; one dependency deprecation warning |
| Feed typed profiles + paraphrases CLI | 5 scenarios passed; warm p95 44.34ms / 30 samples |
| Architecture static verification | 426 passed; 185 schema fixtures, 104 negative |
| Saved independent evaluation replay | All metrics and 1000 paired bootstrap replicates match; gate remains false |
| Protected artifact paths/symlinks | Regression tests passed before data access/training |
| Probability=1 boundary tie | Explicit safe rejection; feasible thresholds round-trip correctly |
| Actual evaluated candidate activation | Rejected; selection pointer unchanged |
| Tampered saved evidence | Rejected on checksum before evaluation |
| Frozen source snapshot | 134 file hashes checked; only separately approved relative evidence-link change |
| Dataset/baseline/candidate/evidence/architecture checksums | All match; 7 external E5 model files verified against pinned local bundle |
| Handoff links and staged hygiene | No broken local handoff links, no staged .local/venv files or files over 10MiB |

Both HTTP/PG runs check unchanged OpenAPI, all six decision scenarios, exact model inference, authentication, concurrency/idempotency, missing denominators, restart persistence and 503 on failed persistence. Neither run changed the active model or the production API processes. The existing dedicated synthetic test database was used with isolated temporary HTTP servers.

The independently restored saved OOF evidence also matches all three repeats/five outer folds (21,048 membership rows), all 60 fold metric records and four family summaries; final serialized imputer/scaler match train-only inputs. Candidate and preserved holdout/protocol/result are byte-identical to the historical experiment. This verifies saved artifact consistency and development provenance, not a new retraining run.

The active model remains `catboost-optuna-v1`, bundle `56b30e55f012515557beba0f80d51fe27cf5cffeb9fb511965a72ba03266ab2e`. The logistic package remains `evaluated-candidate`, bundle `1875fa0e05086e2f6cc9e55f13cd23ecc4548deee0a9e2571ce0f3f0574980ef`.

Replay confirms eligible 16,284 / 467 synthetic events, 113 baseline vs 123 candidate events found at rank-budget 5%, and Recall difference interval [0, 0.0460602561868247]. Strict superiority lower95>0 is false. Static candidate threshold coverage is 5.41%; exact top5% selection is a separate ranking-budget operation. Baseline policy-3/20% is unchanged.

No clean installation, CI, frontend/backend application E2E, human banking review or observed real-default evaluation was performed. Feed's five reviewed profiles do not establish user benefit. Local E5 weights are reused pinned files outside Git and need preparation or artifact transfer on a new machine. Replay repeats existing evidence and is not a new independent test.

Machine-readable evidence: `final-validation.json`, with detailed sibling artifacts `integration-baseline-http/`, `integration-candidate-http/`, `integration-feed-tests.xml`, `integration-feed-evaluation.json`, `integration-replay.json`, `integration-architecture/`, `integration-integrity.json`, `integration-negative-checks.json`, and `source-oof-validation.json`. Git publication remains the git steward's responsibility.
