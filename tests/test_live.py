import asyncio
from datetime import datetime, timezone

import httpx
import pandas as pd

from app.config import Settings
from app.live import LiveFeed, current_states

MID = datetime(2019, 5, 2, 14, 0, tzinfo=timezone.utc)  # two hours after Fani's 12:00 fix, over the Bay of Bengal


def _mid_storm(raw):
    return raw[pd.to_datetime(raw.ISO_TIME) <= "2019-05-02 12:00"]


def test_current_state_is_latest_fix(raw):
    (s,) = current_states(_mid_storm(raw), MID, max_age_h=72)
    assert s["name"] == "Fani" and s["time"] == "2019-05-02T12:00Z"
    assert s["forecastable"] and s["wind"] > 60 and len(s["track"]) > 5


def test_old_storm_is_not_active(raw):
    assert current_states(_mid_storm(raw), datetime(2019, 5, 20, tzinfo=timezone.utc), max_age_h=72) == []


def _feed(handler, **kw):
    cfg = Settings(live_urls=("https://x.test/a.csv", "https://x.test/b.csv"), **kw)
    return LiveFeed(cfg, httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_ttl_cache_single_fetch(fixture_bytes):
    calls = []
    def h(req): calls.append(1); return httpx.Response(200, content=fixture_bytes)
    async def run():
        f = _feed(h, live_max_age_h=1e9)
        a, b = await asyncio.gather(f.snapshot(), f.snapshot())
        assert a is b and a.storms and not a.stale
    asyncio.run(run()); assert len(calls) == 1


def test_fallback_to_second_url(fixture_bytes):
    def h(req): return httpx.Response(404) if req.url.path.endswith("a.csv") else httpx.Response(200, content=fixture_bytes)
    snap = asyncio.run(_feed(h, live_max_age_h=1e9).snapshot())
    assert snap.storms and snap.source.endswith("b.csv")


def test_stale_if_error_keeps_last_good(fixture_bytes):
    state = {"ok": True}
    def h(req): return httpx.Response(200, content=fixture_bytes) if state["ok"] else httpx.Response(503)
    async def run():
        f = _feed(h, live_max_age_h=1e9, live_ttl_s=0)
        good = await f.snapshot()
        state["ok"] = False
        bad = await f.snapshot()
        assert bad.stale and bad.error and bad.storms == good.storms
    asyncio.run(run())


def test_total_failure_is_reported_not_raised():
    snap = asyncio.run(_feed(lambda r: httpx.Response(500)).snapshot())
    assert snap.storms == [] and snap.error and not snap.stale


def test_conditional_get_reuses_parsed_data(fixture_bytes):
    seen = []
    def h(req):
        seen.append(req.headers.get("if-none-match"))
        return httpx.Response(304) if req.headers.get("if-none-match") else httpx.Response(200, content=fixture_bytes, headers={"etag": '"v1"'})
    async def run():
        f = _feed(h, live_max_age_h=1e9, live_ttl_s=0)
        a = await f.snapshot(); b = await f.snapshot()
        assert a.storms == b.storms
    asyncio.run(run()); assert seen == [None, '"v1"']
