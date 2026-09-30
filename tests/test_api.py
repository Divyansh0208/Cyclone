import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.live import LiveFeed
from app.main import create_app

BODY = dict(lat=15.5, lon=87.5, wind=80, pressure=970, wind_trend=10, pressure_trend=-8)


@pytest.fixture()
def client(fixture_bytes):
    cfg = Settings(live_urls=("https://x.test/a.csv",), live_max_age_h=1e9)
    feed = LiveFeed(cfg, httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=fixture_bytes))))
    with TestClient(create_app(cfg, feed)) as c:
        yield c


def test_health_and_status(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json()["districts"] > 600
    s = client.get("/api/v1/status").json()
    assert s["intensity"]["cv_mae"] < s["intensity"]["baseline_mae"] and "synthetic" not in str(s)


def test_forecast_ranks_districts(client):
    r = client.post("/api/v1/forecast", json={**BODY, "lat": 20.0, "lon": 86.0}).json()
    d = r["districts"]
    assert r["intensity"]["next_wind_kt"] > 0 and 0 < len(d) <= 25 and r["districts_in_range"] >= len(d)
    assert [x["affected"] for x in d] == sorted((x["affected"] for x in d), reverse=True)
    assert all(x["low"] <= x["affected"] <= x["high"] <= x["population"] for x in d)


def test_forecast_over_open_sea_has_no_districts(client):
    r = client.post("/api/v1/forecast", json={**BODY, "lat": 5, "lon": 95, "radius_km": 100}).json()
    assert r["districts"] == []


@pytest.mark.parametrize("bad", [{"lat": 99}, {"wind": -5}, {"pressure": 10}, {"radius_km": 0}])
def test_validation(client, bad):
    assert client.post("/api/v1/forecast", json={**BODY, **bad}).status_code == 422


def test_live_endpoint(client):
    j = client.get("/api/v1/live").json()
    assert j["error"] is None and j["storms"] and "age_h" in j["storms"][0] and "near-real-time" in j["note"]


def test_live_endpoint_survives_upstream_failure():
    cfg = Settings(live_urls=("https://x.test/a.csv",))
    feed = LiveFeed(cfg, httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    with TestClient(create_app(cfg, feed)) as c:
        r = c.get("/api/v1/live")
        assert r.status_code == 200 and r.json()["storms"] == [] and r.json()["error"]
