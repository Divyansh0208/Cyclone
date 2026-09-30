from pathlib import Path

import numpy as np
import pytest

from app.exposure import Exposure, haversine_km
from app.registry import category, load_intensity, load_vulnerability

ROOT = Path(__file__).resolve().parent.parent


def test_haversine_known_distance():  # Mumbai - Delhi is about 1150 km
    assert 1120 < haversine_km(19.076, 72.878, np.array([28.614]), np.array([77.209]))[0] < 1180


def test_exposure_data_is_sane():
    e = Exposure(ROOT / "data" / "districts.csv")
    assert len(e) > 600 and e.df.lat.between(6, 38).all() and e.df.lon.between(68, 98).all()
    assert (e.df.population > 0).all() and (e.df.area_km2 > 0).all()
    puri = e.within(19.8, 85.8, 30)
    assert "Puri" in set(puri.district)


def test_categories():
    assert category(10) == "Low pressure area" and category(70) == "Very severe cyclonic storm" and category(150) == "Super cyclonic storm"


def test_vulnerability_bounds():
    v = load_vulnerability(ROOT / "models")
    dens, pop = np.array([50.0, 500.0, 40000.0]), np.array([1e6, 2e6, 3e6])
    mid, lo, hi, capped = v.predict(100, dens, pop)
    assert (lo <= mid).all() and (mid <= hi).all() and (hi <= pop).all()  # never more affected than the district population
    assert capped.tolist() == [False, False, True]
    assert v.predict(120, dens[:1], pop[:1])[0] > v.predict(60, dens[:1], pop[:1])[0]  # stronger storm, more affected


def test_intensity_beats_baseline_and_is_sane():
    m = load_intensity(ROOT / "models")
    assert m.meta["cv_mae"] < m.meta["baseline_mae"]
    assert 0 <= m.predict(15.5, 87.5, 80, 970, 10, -8) <= 200
