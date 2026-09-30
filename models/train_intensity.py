"""usage: python -m models.train_intensity data/ibtracs.NI.csv  ->  models/intensity.json + intensity.meta.json

Target is the 6 h wind CHANGE (next - current); serving adds it back to the current wind. Trees fit changes far better
than they fit the identity mapping wind -> next wind. Trained with an absolute-error objective to match the MAE metric.
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xgboost
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from xgboost import XGBRegressor

from app.features import FEATS, read_ibtracs, training_frame

OUT = Path(__file__).resolve().parent
PARAMS = dict(n_estimators=400, max_depth=3, learning_rate=0.03, subsample=0.8, min_child_weight=10,
              objective="reg:absoluteerror", random_state=0)


def main(path: str) -> dict:
    d = training_frame(read_ibtracs(path))
    X, w, y, g = d[FEATS].values, d.wind.values, d.y.values, d.sid.values
    mae, base = [], []
    for tr, te in GroupKFold(n_splits=5).split(X, y, g):  # folds split by storm, never by row
        m = XGBRegressor(**PARAMS).fit(X[tr], y[tr] - w[tr])
        mae.append(mean_absolute_error(y[te], w[te] + m.predict(X[te])))
        base.append(mean_absolute_error(y[te], w[te]))  # last-value baseline
    XGBRegressor(**PARAMS).fit(X, y - w).save_model(OUT / "intensity.json")  # served model is refit on every storm
    meta = {"n_rows": len(d), "n_storms": int(d.sid.nunique()), "cv_folds": 5,
            "cv_mae": round(float(np.mean(mae)), 2), "cv_std": round(float(np.std(mae)), 2),
            "baseline_mae": round(float(np.mean(base)), 2), "folds_won": round(float(np.mean(np.array(mae) < np.array(base))), 2),
            "target": "delta", "features": FEATS, "source": Path(path).name, "data_through": str(d.t.max()),
            "xgboost": xgboost.__version__, "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (OUT / "intensity.meta.json").write_text(json.dumps(meta, indent=2))
    print(meta)
    return meta


if __name__ == "__main__":
    main(sys.argv[1])
