"""usage: python -m models.export_storms data/ibtracs.NI.csv -> frontend/storms.json (recent severe NI storms for replay)"""
import json, sys
from pathlib import Path

from app.features import read_ibtracs, training_frame

d = training_frame(read_ibtracs(sys.argv[1]))
d = d[d.t.dt.year >= 1990]
out = []
for sid, g in d.groupby("sid"):
    if g.wind.max() < 64: continue  # very severe and above
    nm, yr = g.name.iloc[0], int(g.t.dt.year.iloc[0])
    label = f"{nm.title()} {yr}" if nm not in ("", "UNNAMED", "NOT_NAMED") else f"{sid} ({yr})"
    steps = [{"t": str(r.t)[:16], "lat": round(r.lat, 1), "lon": round(r.lon, 1), "wind": r.wind, "pressure": r.pressure,
              "wind_trend": r.wind_trend, "pressure_trend": r.pressure_trend, "next_wind": r.y,
              "r34_km": None if r.r34_km != r.r34_km else round(r.r34_km)} for r in g.itertuples()]
    out.append({"label": label, "start": str(g.t.iloc[0]), "steps": steps})
out = sorted(out, key=lambda s: s["start"])[-30:]
Path(__file__).resolve().parent.parent.joinpath("frontend", "storms.json").write_text(json.dumps(out))
print(len(out), "storms:", [s["label"] for s in out][-8:])
