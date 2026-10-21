```json
{
  "modelType": "CatBoostClassifier",
  "modelVersion": "catboost-optuna-v1",
  "params": {
    "iterations": 302,
    "depth": 3,
    "learning_rate": 0.017169946473376285,
    "l2_leaf_reg": 7.543876335558273,
    "random_strength": 0.4890915518202954,
    "bagging_temperature": 0.23694932167282895,
    "rsm": 0.6930882696132237,
    "border_count": 64,
    "auto_class_weights": "None"
  },
  "features": [
    "X1",
    "X2",
    "X3",
    "X4",
    "X7",
    "X8",
    "X9",
    "X10"
  ],
  "missingValueMode": "Min",
  "optimization": {
    "library": "optuna",
    "trials": 30,
    "folds": 3,
    "objective": "train_stratified_cv_average_precision",
    "selectedTrial": 28,
    "params": {
      "iterations": 302,
      "depth": 3,
      "learning_rate": 0.017169946473376285,
      "l2_leaf_reg": 7.543876335558273,
      "random_strength": 0.4890915518202954,
      "bagging_temperature": 0.23694932167282895,
      "rsm": 0.6930882696132237,
      "border_count": 64,
      "auto_class_weights": "None"
    }
  },
  "calibration": null,
  "dataOrigin": "SYNTHETIC_FINANCE_V1",
  "scoreKind": "BANKRUPTCY_PROXY",
  "purpose": "DEMO_RESEARCH"
}
```
