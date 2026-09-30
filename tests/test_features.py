import pandas as pd

from app.features import FEATS, STEP, fixes, training_frame


def test_fixes_are_six_hourly_and_sorted(raw):
    f = fixes(raw)
    assert (f.t.dt.hour % 6 == 0).all()
    assert f.t.is_monotonic_increasing and not f.duplicated(["sid", "t"]).any()


def test_trends_only_across_consecutive_fixes(raw):
    f = fixes(raw)
    gap = f.groupby("sid").t.diff()
    assert f.loc[gap != STEP, "wind_trend"].isna().all()
    ok = gap == STEP
    assert (f.wind_trend[ok] == f.groupby("sid").wind.diff()[ok]).all() and ok.any()


def test_training_target_is_next_fix(raw):
    d = training_frame(raw)
    f = fixes(raw).set_index("t")
    assert len(d) > 10 and not d[FEATS + ["y"]].isna().any().any()
    r = d.iloc[5]
    assert f.loc[r.t + STEP, "wind"] == r.y


def test_r34_converted_to_km(raw):
    f = fixes(raw)
    assert f.r34_km.dropna().between(20, 900).all()
