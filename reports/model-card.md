# Synthetic logistic baseline

Fully invented SIM companies, financials and labels. BANKRUPTCY_PROXY / DEMONSTRATION / DEMO_RESEARCH. Not bank PD; not validated for real companies.

Eight contract ratios only. Median imputation + indicators, scaling, regularized logistic regression. Preprocessing fits only train. Four-fold CV on train; version selected by validation AP; test opened after selection-lock. Provided split retained, no resampling. No calibration applied.

Policy selects a demonstration review budget on eligible validation rows, not a risk norm. No business auto-decline derives from model score. Test is excluded from seed selection. Model serialization must only be loaded from locally trusted prepared artifacts.
