"""Build data/districts.csv (Census 2011, district level) from the public recurze/IndianCities dataset.

usage: python -m models.build_districts [local_csv]
Drops rows without population/area (districts created after 2011 with no census figures).
"""
import sys
from pathlib import Path
import pandas as pd

BASE = "https://raw.githubusercontent.com/recurze/IndianCities/master/"
URL, CITIES_URL = BASE + "final_districts.csv", BASE + "final_cities.csv"
# Source has (0,0) placeholders for some districts. Fill from the district's most populous city (same dataset);
# for the coastal districts still missing, use the district HQ town. Anything left is dropped, not guessed.
HQ = {("Gujarat", "Gir Somnath"): (20.91, 70.37),          # Veraval
      ("West Bengal", "Purba Medinipur"): (22.30, 87.92),   # Tamluk
      ("West Bengal", "Hooghly"): (22.90, 88.40),           # Chinsurah
      ("Puducherry", "Mahé"): (11.70, 75.54)}               # Mahé
OUT = Path(__file__).resolve().parent.parent / "data" / "districts.csv"


def build(src: str = URL) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pd.read_csv(src, dtype=str)
    d = d.rename(columns={"State": "state", "District": "district", "Population": "population",
                          "Area (in km^2)": "area_km2", "Latitude": "lat", "Longitude": "lon"})
    for c in ("population", "area_km2", "lat", "lon"):
        d[c] = pd.to_numeric(d[c].str.replace(",", "", regex=False).str.strip(), errors="coerce")
    d = d.dropna(subset=["population", "area_km2"])
    d = d[(d.population > 0) & (d.area_km2 > 0)]
    sts = d.groupby("state").agg(population=("population", "sum"), area_km2=("area_km2", "sum"))
    sts["density"] = (sts.population / sts.area_km2).round(1)  # state totals use every district, even those without coordinates
    bad = ~(d.lat.between(6, 38) & d.lon.between(68, 98))
    c = pd.read_csv(CITIES_URL if src == URL else Path(src).with_name("cities.csv"))
    c = c.sort_values("Population", key=lambda x: pd.to_numeric(x.astype(str).str.replace(",", ""), errors="coerce"), ascending=False)
    c = c[c.Latitude.between(6, 38) & c.Longitude.between(68, 98)].drop_duplicates(["State", "District"])
    fill = d[bad].merge(c, left_on=["state", "district"], right_on=["State", "District"], how="left")
    d.loc[bad, "lat"], d.loc[bad, "lon"] = fill.Latitude.values, fill.Longitude.values
    for (st, di), (la, lo) in HQ.items():
        m = (d.state == st) & (d.district == di) & ~(d.lat.between(6, 38) & d.lon.between(68, 98))
        d.loc[m, ["lat", "lon"]] = la, lo
    d = d.dropna()
    d = d[(d.population > 0) & (d.area_km2 > 0) & d.lat.between(6, 38) & d.lon.between(68, 98)]  # India bbox: drops (0,0) placeholders
    d = d.drop_duplicates(["state", "district"])
    d["district"] = d.district.str.strip().str.title()
    d["density"] = (d.population / d.area_km2).round(1)
    return d.sort_values(["state", "district"]).reset_index(drop=True), sts.reset_index()


if __name__ == "__main__":
    df, sts = build(*sys.argv[1:2])
    OUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False)
    sts.to_csv(OUT.with_name("states.csv"), index=False)
    print(f"{len(df)} districts, {len(sts)} states/UTs -> {OUT}")
