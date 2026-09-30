# usage: python -m models.build_emdat <emdat.xlsx> <ibtracs.NI.csv>  ->  data/emdat_joined.csv
import re, sys
from pathlib import Path
import pandas as pd
from app.features import COLS

# Census 2011 state densities computed from data/states.csv (real district totals; see models/build_districts.py)
STATES = pd.read_csv(Path(__file__).resolve().parent.parent / "data" / "states.csv")
DENS = {s.lower(): d for s, d in zip(STATES.state, STATES.density)}
DENS["andaman"] = DENS.pop("andaman and nicobar")
DENS["jammu"] = DENS.pop("jammu and kashmir")
ALIAS = {"orissa": "odisha", "pondicherry": "puducherry", "bengal": "west bengal",
         "madras": "tamil nadu", "tanjore": "tamil nadu", "thanjavur": "tamil nadu", "midnapore": "west bengal"}
STOP = {"tropical", "cyclone", "storm", "cyclonic", "severe", "depression", "very"}
PAT = re.compile(r"\b(" + "|".join(list(DENS) + list(ALIAS)) + r")\b")

def pop_density(text):
    s = {ALIAS.get(m, m) for m in PAT.findall(str(text).lower())}
    return sum(DENS[k] for k in s) / len(s) if s else None

def ibtracs(path):
    df = pd.read_csv(path, skiprows=[1], low_memory=False, na_values=[" ", ""])
    out = pd.DataFrame({"sid": df.SID, "name": df.NAME.fillna("").str.lower(), "t": pd.to_datetime(df.ISO_TIME, errors="coerce"),
                        "lat": pd.to_numeric(df.LAT, errors="coerce"), "lon": pd.to_numeric(df.LON, errors="coerce")})
    have = [c for c in COLS["wind"] if c in df]
    out["wind"] = df[have].apply(pd.to_numeric, errors="coerce").bfill(axis=1).iloc[:, 0]
    return out.dropna()

def main(xlsx, ib_path, out="data/emdat_joined.csv"):
    e = pd.read_excel(xlsx, sheet_name=0)
    e = e[e["Total Affected"] > 0].copy()
    e["date"] = pd.to_datetime(dict(year=e["Start Year"], month=e["Start Month"], day=e["Start Day"]), errors="coerce")
    ib = ibtracs(ib_path)
    ib = ib[ib.lat.between(5, 27) & ib.lon.between(65, 95)]  # near India
    rows = []
    for _, r in e.iterrows():
        dens = pop_density(f"{r.Location} {r['Admin Units']}")
        if dens is None: continue
        wind, src = None, None
        if pd.notna(r.date):
            w = ib[(ib.t - r.date).abs() <= pd.Timedelta(days=2)]
            nm = [x for x in re.findall(r"[a-z]{4,}", str(r["Event Name"]).lower()) if x not in STOP]
            hit = w[w.name.apply(lambda n: any(x in n for x in nm))] if nm else w[:0]
            if len(hit): w = hit  # named storm beats "whatever was active within 2 days"
            if len(w): wind, src = w.wind.max(), "ibtracs"
        if wind is None and pd.notna(r.Magnitude): wind, src = r.Magnitude / 1.852, "emdat"  # kph -> kt
        if wind is None: continue
        rows.append({"event": r["Event Name"], "year": r["Start Year"], "wind_speed": round(wind, 1),
                     "pop_density": round(dens), "wind_src": src, "Total Affected": r["Total Affected"]})
    d = pd.DataFrame(rows)
    Path(out).parent.mkdir(exist_ok=True)
    d.to_csv(out, index=False)
    print(f"{len(e)} rows with Total Affected -> {len(d)} usable | wind from: {d.wind_src.value_counts().to_dict()}")

if __name__ == "__main__":
    main(*sys.argv[1:3])
