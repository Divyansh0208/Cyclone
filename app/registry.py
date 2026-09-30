"""Model loading and inference. Models are stored as portable JSON (no pickle), loaded once at startup."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from xgboost import XGBRegressor

from app.features import FEATS

IMD = [(17, "Low pressure area"), (28, "Depression"), (34, "Deep depression"), (48, "Cyclonic storm"),
       (64, "Severe cyclonic storm"), (90, "Very severe cyclonic storm"), (120, "Extremely severe cyclonic storm")]


def category(kt: float) -> str:
    """IMD scale. Note: input winds come from JTWC (1-min sustained); IMD defines 3-min sustained, so read as approximate."""
    return next((name for lim, name in IMD if kt < lim), "Super cyclonic storm")


@dataclass(frozen=True)
class Intensity:
    booster: XGBRegressor
    meta: dict

    def predict(self, lat, lon, wind, pressure, wind_trend, pressure_trend) -> float:
        x = np.array([[lat, lon, wind, pressure, wind_trend, pressure_trend]], dtype=float)
        return float(np.clip(wind + self.booster.predict(x)[0], 0, 200))  # model predicts the 6 h change


@dataclass(frozen=True)
class Vulnerability:
    a: float
    b: float
    q10: float
    q90: float
    dmax: float
    meta: dict

    def predict(self, wind: float, density: np.ndarray, population: np.ndarray):
        """Vectorised over districts. Density is capped at the training maximum (no extrapolation) and people affected
        can never exceed the district's population. Returns (mid, low, high, density_was_capped)."""
        d = np.clip(density, 1, self.dmax)
        mid = self.a + self.b * wind + np.log(d)
        lo, mid, hi = (np.clip(np.expm1(mid + q), 0, population) for q in (self.q10, 0.0, self.q90))
        return mid, lo, hi, density > self.dmax


def load_intensity(models_dir: Path) -> Intensity:
    meta = json.loads((models_dir / "intensity.meta.json").read_text())
    if meta["features"] != FEATS:
        raise RuntimeError(f"intensity model expects {meta['features']}, code provides {FEATS}; retrain")
    m = XGBRegressor()
    m.load_model(models_dir / "intensity.json")
    return Intensity(m, meta)


def load_vulnerability(models_dir: Path) -> Vulnerability:
    raw = json.loads((models_dir / "vulnerability.json").read_text())
    return Vulnerability(**raw["model"], meta=raw["meta"])
