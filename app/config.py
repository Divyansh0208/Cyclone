"""Runtime settings, all overridable through environment variables."""
import os
from dataclasses import dataclass, field

_BASE = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    # Near-real-time source: NOAA NCEI IBTrACS "ACTIVE" file (JTWC provisional fixes for currently active storms).
    # NCEI rebuilds it about 3x/week, so this is near-real-time, not live telemetry. Fallback: last-3-years file.
    live_urls: tuple[str, ...] = field(default_factory=lambda: tuple(
        u.strip() for u in _env("LIVE_URLS", f"{_BASE}ibtracs.ACTIVE.list.v04r01.csv,{_BASE}ibtracs.last3years.list.v04r01.csv").split(",") if u.strip()))
    live_ttl_s: int = field(default_factory=lambda: int(_env("LIVE_TTL_S", "900")))        # re-check upstream at most every 15 min
    live_retry_s: int = field(default_factory=lambda: int(_env("LIVE_RETRY_S", "60")))     # after a failed refresh
    live_timeout_s: float = field(default_factory=lambda: float(_env("LIVE_TIMEOUT_S", "30")))
    live_max_age_h: float = field(default_factory=lambda: float(_env("LIVE_MAX_AGE_H", "72")))  # last fix older than this = not active
    default_radius_km: float = field(default_factory=lambda: float(_env("DEFAULT_RADIUS_KM", "400")))
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(o.strip() for o in _env("CORS_ORIGINS", "").split(",") if o.strip()))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
