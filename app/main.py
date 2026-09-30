"""Cyclone Impact Forecaster API.  Run: uvicorn app.main:app"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.exposure import Exposure
from app.live import LiveFeed
from app.registry import category, load_intensity, load_vulnerability
from app.schemas import DistrictImpact, Forecast, Intensity, StormState

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("cyclone.api")
TOP_N = 25


def create_app(cfg: Settings | None = None, feed: LiveFeed | None = None) -> FastAPI:
    cfg = cfg or Settings()
    logging.basicConfig(level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.cfg = cfg
        app.state.intensity = load_intensity(ROOT / "models")  # fail fast at startup, not on the first request
        app.state.vuln = load_vulnerability(ROOT / "models")
        app.state.exposure = Exposure(ROOT / "data" / "districts.csv")
        app.state.feed = feed or LiveFeed(cfg)
        log.info("ready: %d districts, intensity CV MAE %s kt", len(app.state.exposure), app.state.intensity.meta["cv_mae"])
        yield
        await app.state.feed.aclose()

    app = FastAPI(title="Cyclone Impact Forecaster", version="1.0.0", lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if cfg.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(cfg.cors_origins), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.get("/healthz", include_in_schema=False)
    def healthz():  # liveness: process is up
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz(request: Request):  # readiness: models and data are loaded (lifespan guarantees it, kept for orchestrators)
        s = request.app.state
        return {"status": "ready", "districts": len(s.exposure)}

    @app.get("/api/v1/status")
    def status(request: Request):
        s = request.app.state
        return {"intensity": s.intensity.meta, "vulnerability": s.vuln.meta, "districts": len(s.exposure),
                "live": {"sources": list(cfg.live_urls), "ttl_s": cfg.live_ttl_s, "max_age_h": cfg.live_max_age_h}}

    def assess(s, st: StormState) -> Forecast:
        nxt = s.intensity.predict(st.lat, st.lon, st.wind, st.pressure, st.wind_trend, st.pressure_trend)
        radius = st.radius_km or cfg.default_radius_km
        near = s.exposure.within(st.lat, st.lon, radius)
        mid, lo, hi, capped = s.vuln.predict(nxt, near.density.to_numpy(), near.population.to_numpy())
        near = near.assign(affected=mid.round(), low=lo.round(), high=hi.round(), density_capped=capped)
        top = near.sort_values("affected", ascending=False).head(TOP_N)
        return Forecast(intensity=Intensity(next_wind_kt=round(nxt, 1), delta_kt=round(nxt - st.wind, 1), category=category(nxt)),
                        radius_km=radius, districts_in_range=len(near),
                        districts=[DistrictImpact(**r) for r in top.to_dict("records")])

    @app.post("/api/v1/forecast", response_model=Forecast)
    def forecast(st: StormState, request: Request):
        return assess(request.app.state, st)

    @app.get("/api/v1/live")
    async def live(request: Request):
        snap = await request.app.state.feed.snapshot()
        now = datetime.now(timezone.utc)
        storms = []
        for x in snap.storms:
            age = (now - datetime.strptime(x["time"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)).total_seconds() / 3600
            storms.append({**x, "age_h": round(age, 1)})
        return {"storms": storms, "fetched_at": snap.fetched_at, "source": snap.source, "stale": snap.stale, "error": snap.error,
                "note": "IBTrACS/JTWC provisional fixes, rebuilt by NCEI about 3x/week: near-real-time, not live telemetry."}

    if (ROOT / "frontend").is_dir():
        app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True))
    return app


app = create_app()
