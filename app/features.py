"""IBTrACS parsing + feature engineering, shared by training and serving so the two can never drift apart."""
from __future__ import annotations

import pandas as pd

FEATS = ["lat", "lon", "wind", "pressure", "wind_trend", "pressure_trend"]
COLS = {"lat": ["LAT", "USA_LAT"], "lon": ["LON", "USA_LON"],
        "wind": ["USA_WIND", "WMO_WIND"], "pressure": ["USA_PRES", "WMO_PRES"]}  # first non-null wins
R34 = ["USA_R34_NE", "USA_R34_SE", "USA_R34_SW", "USA_R34_NW"]  # gale-force (34 kt) wind radii, nautical miles
STEP = pd.Timedelta(hours=6)
NMI_KM = 1.852


def read_ibtracs(src) -> pd.DataFrame:
    """src: path, URL or file-like. Row 2 of an IBTrACS CSV holds units, so it is skipped."""
    return pd.read_csv(src, skiprows=[1], low_memory=False, na_values=[" ", ""])


def fixes(raw: pd.DataFrame, basin: str = "NI") -> pd.DataFrame:
    """Tidy 6-hourly fixes with trends. Trends are only computed across consecutive 6 h fixes (else NaN)."""
    df = raw[raw.BASIN == basin] if "BASIN" in raw else raw
    out = pd.DataFrame({"sid": df.SID, "t": pd.to_datetime(df.ISO_TIME, errors="coerce"),
                        "name": df["NAME"].fillna("") if "NAME" in df else ""})
    for k, cands in COLS.items():
        have = [c for c in cands if c in df]
        out[k] = df[have].apply(pd.to_numeric, errors="coerce").bfill(axis=1).iloc[:, 0]
    r = [c for c in R34 if c in df]
    out["r34_km"] = (df[r].apply(pd.to_numeric, errors="coerce").max(axis=1) * NMI_KM) if r else float("nan")
    out = out.dropna(subset=["t", *COLS])
    out = out[out.t.dt.hour % 6 == 0].sort_values(["sid", "t"]).drop_duplicates(["sid", "t"])
    g = out.groupby("sid")
    consecutive = g.t.diff() == STEP
    out["wind_trend"] = g.wind.diff().where(consecutive)
    out["pressure_trend"] = g.pressure.diff().where(consecutive)
    return out.reset_index(drop=True)


def training_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Rows with all features and the next-6h wind target `y` (only when the next fix is exactly 6 h later)."""
    f = fixes(raw)
    g = f.groupby("sid")
    f["y"] = g.wind.shift(-1).where((g.t.shift(-1) - f.t) == STEP)
    return f.dropna(subset=[*FEATS, "y"]).reset_index(drop=True)
