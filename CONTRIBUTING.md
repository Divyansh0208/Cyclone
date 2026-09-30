# Contributing

Thanks for helping. This is decision-support software for cyclone exposure, so a few rules matter more than usual.

## Ground rules
1. **Real data only.** No synthetic or made-up data in training, tests, or the UI. Test fixtures are real excerpts (see `tests/fixtures/`).
2. **Honest uncertainty.** The impact model is trained on 61 events. Anything user-facing must keep the "relative ranking" wording and the 10-90% range. Do not add false precision.
3. **Not a warning system.** IMD is the official authority. Do not word anything in the UI as an official alert.
4. **Licensed data stays out.** EM-DAT exports and raw IBTrACS files are not committed (see `.gitignore`). Cite sources in the README when you add a dataset.
5. **Train and serve share features.** Feature code lives in `app/features.py` and is used by both. Do not fork it.

## Setup
```bash
git clone https://github.com/Divyansh0208/Cyclone.git && cd Cyclone
python -m venv env && source env/bin/activate      # Windows: env\Scripts\activate
pip install -r requirements-train.txt
python -m pytest -q
uvicorn app.main:app --reload --port 8000           # http://localhost:8000
```
Docker: `docker build -t cyclone . && docker run -p 8000:8000 cyclone`

## Retraining
See "Retrain" in the README. If you change a model, update `models/*.meta.json` and report cross-validated metrics against the baselines (storm-grouped CV for intensity, repeated CV for impact). A change that does not beat the baseline on held-out data does not ship.

## Pull requests
- One topic per PR; link the issue (`Closes #N`).
- Add or update tests in `tests/`. CI runs `pytest` and a Docker build.
- Keep the frontend a single file with no build step unless the issue says otherwise.
- Describe what you changed and how you checked it.

## Good first issues
Filter by the `good first issue` label. Ask in the issue before starting anything labelled `research` or `model`.

## Reporting problems
Use the issue templates. For wrong predictions, include the storm state (lat, lon, wind, pressure, trends) so it can be reproduced.
