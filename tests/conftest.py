from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "ibtracs_active_excerpt.csv"  # real IBTrACS rows: Cyclone Fani, Apr-May 2019


@pytest.fixture(scope="session")
def raw():
    from app.features import read_ibtracs
    return read_ibtracs(FIXTURE)


@pytest.fixture(scope="session")
def fixture_bytes():
    return FIXTURE.read_bytes()
