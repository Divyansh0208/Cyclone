"""District-level exposure from Census 2011 (data/districts.csv, built by models/build_districts.py)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

EARTH_R_KM = 6371.0088


def haversine_km(lat, lon, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    p1, p2 = np.radians(lat), np.radians(lats)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lons - lon) / 2) ** 2
    return 2 * EARTH_R_KM * np.arcsin(np.sqrt(a))


class Exposure:
    def __init__(self, path: Path):
        self.df = pd.read_csv(path)
        missing = {"state", "district", "population", "area_km2", "lat", "lon", "density"} - set(self.df.columns)
        if missing:
            raise RuntimeError(f"{path} is missing columns {sorted(missing)}")
        self._lat, self._lon = self.df.lat.to_numpy(), self.df.lon.to_numpy()

    def __len__(self) -> int:
        return len(self.df)

    def within(self, lat: float, lon: float, radius_km: float) -> pd.DataFrame:
        dist = haversine_km(lat, lon, self._lat, self._lon)
        near = self.df[dist <= radius_km].copy()
        near["distance_km"] = dist[dist <= radius_km].round(0)
        return near
