# Architecture — Cyclone Impact Forecaster

```
NCEI IBTrACS ACTIVE csv ──► app/live.py (TTL cache, ETag, stale-if-error) ──► /api/v1/live ─┐
                                                                                             ├─► frontend/index.html (MapLibre 3D globe)
storm state ──► app/registry.py Intensity (XGBoost, delta target) ──┐                        │
Census 2011 districts (data/districts.csv) ─► app/exposure.py ──────┴─► Vulnerability ──► /api/v1/forecast
```
Training (offline): IBTrACS NI csv -> `models.train_intensity`; EM-DAT xlsx + IBTrACS wind + Census state density -> `models.build_emdat` -> `models.train_vulnerability`.
`app/features.py` is shared by training and serving, so features cannot drift between the two.

## Model 1 — intensity nowcast
XGBoost, target = wind change over the next 6 h (served wind = current + predicted change), absolute-error objective.
Features: lat, lon, wind, pressure, wind/pressure trend over the previous consecutive 6 h fix (no trend across data gaps).
Evaluation: 5-fold CV grouped by storm (never by row): MAE 3.04 ± 0.20 kt vs 3.49 kt last-value baseline, better in 5/5 folds. Served model is refit on all storms.

## Model 2 — impact estimate
`log(1+affected) = a + b·wind + log(density)`; density coefficient fixed at 1 (61 events cannot support more parameters; a free fit gave ~1.08).
A RandomForest scored worse than the mean baseline on the same data. Density is capped at the training maximum and predictions are bounded by district population.
CV (5-fold x 20): MAE 2.50 ± 0.41 vs 2.69 baseline (log scale), better in ~78% of folds. Range = 10–90% out-of-fold residual band.

## Serving
FastAPI, models as JSON (no pickle), loaded at startup (fail-fast), GZip, optional CORS, `/healthz` + `/readyz`, non-root Docker image, CI runs tests and builds the image.

## Data
- IBTrACS (NOAA NCEI): training history and near-real-time ACTIVE feed. Wind = JTWC (USA_WIND) first, WMO as fallback.
- EM-DAT (CRED, UCLouvain): India tropical-cyclone event totals, joined to IBTrACS by name then by date (±2 days).
- Census of India 2011 via public district dataset (`models/build_districts.py`); coordinates missing in the source are filled from the district's largest city, four coastal districts from their HQ town, others dropped.