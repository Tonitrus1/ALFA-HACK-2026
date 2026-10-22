# Saved synthetic confirmation: offline replay

This directory preserves the one already evaluated 20,000-row synthetic holdout,
its predeclared protocol and result. Replaying it is **not a new independent test**;
do not tune models, thresholds, seeds or promotion criteria against these results.
The strict superiority gate is false. The active bundle remains `ml/artifacts/baseline`.

From the repository root, after `./scripts/setup-ml.sh` has installed pinned dependencies:

```sh
.venv/bin/python scripts/replay_scoring_evidence.py
```

Replay needs no network, database or generation package. It verifies evidence SHA256,
the full candidate/baseline bundles, original dataset hashes, saved holdout dataHash,
unique IDs and all 18 financial fields against original and split data, then recomputes
all/eligible metrics, static threshold coverage and 1,000 paired bootstrap replicates.
Every numerical result must agree with `independent_result.json` within 1e-12.
Expected: eligible rows 16284, events 467; found baseline 113 / candidate 123;
Recall difference interval [0, 0.0460602561868247], `qualityGatePassed=false`.
It prints its verification summary to stdout and never writes evidence, trains or activates.
Optional `--evidence`, `--candidate`, `--baseline`, `--dataset` paths permit a relocated checkout.

`provenance.json` pins candidate/baseline bundle digests, original dataset files and
financial-vector fields. `SHA256SUMS` covers the saved evidence and archives.
`independent_result.json` is also byte-identical to the immutable candidate's sealed
`independent-validation.json`.

The `archive/*.txt` files are **archive-only source references**, never imported or
executed by replay/runtime. The generator is the exact historical source with SHA256
`22948c56106202986b597426ed19502339a6af6712049f6d6893e41778a3565a`;
its relative imports require its original generation package, which replay does not need.
`train.py.txt` and `learning.py.txt` match the historical hashes in the candidate protocol.
Current training code subsequently gained stricter output protection; existing artifacts
were not rewritten. Replay reproduces evaluation, not bit-identical model retraining.

All labels and finances are synthetic. These results do not establish real credit-default
quality. Exact 5% here is a ranking budget; the candidate's static threshold reviews 5.41%.
The eight raw financial fields/schema 2 and baseline policy-3/20% remain unchanged.
