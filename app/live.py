"""Near-real-time storm feed: NOAA NCEI IBTrACS ACTIVE file -> current state of every active North Indian Ocean storm.

Design: single upstream fetch shared by all requests (TTL cache + conditional GET), stale-if-error, ordered fallback URLs,
parsing off the event loop. Failures never raise into request handlers: they surface as `error` / `stale` on the snapshot.
"""
from __future__ import annotations

import asyncio
import io
import logging
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

import httpx
import pandas as pd

from app.config import Settings
from app.features import FEATS, fixes, read_ibtracs

log = logging.getLogger("cyclone.live")
TRACK_POINTS = 16  # last 4 days of 6-hourly fixes, for the map trail


@dataclass(frozen=True)
class Snapshot:
    storms: list[dict] = field(default_factory=list)
    fetched_at: datetime | None = None
    source: str | None = None
    stale: bool = False
    error: str | None = None


def _num(x) -> float | None:
    return None if pd.isna(x) else round(float(x), 1)


def current_states(raw: pd.DataFrame, now: datetime, max_age_h: float) -> list[dict]:
    """Latest usable fix of each storm whose last fix is at most max_age_h old. `now` is timezone-aware UTC."""
    f = fixes(raw)
    now_naive = now.astimezone(timezone.utc).replace(tzinfo=None)
    out = []
    for sid, g in f.groupby("sid"):
        last = g.iloc[-1]
        age_h = (now_naive - last.t).total_seconds() / 3600
        if age_h > max_age_h or age_h < -6:  # -6: tolerate small clock skew, reject anything from the future
            continue
        state = {k: _num(last[k]) for k in FEATS}
        out.append({"sid": sid, "name": (last["name"] or "UNNAMED").title(), "time": last.t.strftime("%Y-%m-%dT%H:%MZ"), **state,
                    "r34_km": _num(last.r34_km), "forecastable": all(state[k] is not None for k in FEATS),
                    "track": g[["lat", "lon"]].tail(TRACK_POINTS).round(2).values.tolist()})
    return sorted(out, key=lambda s: s["time"], reverse=True)


class LiveFeed:
    def __init__(self, cfg: Settings, client: httpx.AsyncClient | None = None):
        self.cfg = cfg
        self._own = client is None
        self._client = client or httpx.AsyncClient(timeout=cfg.live_timeout_s, follow_redirects=True,
                                                   transport=httpx.AsyncHTTPTransport(retries=2),
                                                   headers={"User-Agent": "cyclone-impact-forecaster/1.0"})
        self._lock = asyncio.Lock()
        self._snap = Snapshot()
        self._next_check = 0.0
        self._etag: dict[str, str] = {}
        self._raw: dict[str, pd.DataFrame] = {}

    async def aclose(self) -> None:
        if self._own:
            await self._client.aclose()

    async def snapshot(self) -> Snapshot:
        async with self._lock:  # one refresh at a time; concurrent requests wait and reuse it
            if time.monotonic() < self._next_check:
                return self._snap
            try:
                self._snap = await self._refresh()
                self._next_check = time.monotonic() + self.cfg.live_ttl_s
            except Exception as e:  # noqa: BLE001 - upstream can fail in many ways; never take the API down
                log.warning("live refresh failed: %s", e)
                self._snap = replace(self._snap, stale=self._snap.fetched_at is not None, error=f"{type(e).__name__}: {e}")
                self._next_check = time.monotonic() + self.cfg.live_retry_s
            return self._snap

    async def _refresh(self) -> Snapshot:
        errors = []
        for url in self.cfg.live_urls:
            try:
                headers = {"If-None-Match": self._etag[url]} if url in self._etag and url in self._raw else {}
                r = await self._client.get(url, headers=headers)
                if r.status_code == 304:
                    raw = self._raw[url]
                elif r.status_code == 200:
                    raw = await asyncio.to_thread(lambda: read_ibtracs(io.BytesIO(r.content)))
                    self._raw[url] = raw
                    if r.headers.get("etag"): self._etag[url] = r.headers["etag"]
                else:
                    errors.append(f"{url}: HTTP {r.status_code}")
                    continue
                now = datetime.now(timezone.utc)
                storms = await asyncio.to_thread(current_states, raw, now, self.cfg.live_max_age_h)
                log.info("live: %d active NI storm(s) from %s", len(storms), url)
                return Snapshot(storms=storms, fetched_at=now, source=url)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{url}: {type(e).__name__}: {e}")
        raise RuntimeError("; ".join(errors) or "no live URLs configured")
