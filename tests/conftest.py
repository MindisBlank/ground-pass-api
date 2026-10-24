"""Shared test fixtures.

All tests run offline against a fixed 2014 ISS TLE. It is the TLE used in
skyfield's own documentation, which publishes the pass times it produces,
so the pass finder can be checked against an independent reference.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from groundpass.passes import TIMESCALE
from groundpass.stations import GroundStation, get_station
from groundpass.tle import FileSource, load_satellite

DATA_DIR = Path(__file__).parent / "data"
ISS_TLE_FILE = DATA_DIR / "iss_2014.tle"
ISS_NORAD_ID = 25544

# Start of the search window used throughout, close to the TLE epoch.
WINDOW_START = datetime(2014, 1, 23, tzinfo=UTC)


@pytest.fixture
def tle_source() -> FileSource:
    return FileSource(ISS_TLE_FILE)


@pytest.fixture
def iss(tle_source):
    return load_satellite(tle_source.get(ISS_NORAD_ID), TIMESCALE)


@pytest.fixture
def south_point() -> GroundStation:
    # The ISS (51.6° inclination) rarely clears 5° at Esrange's 67.9° N,
    # so tests that need several good passes use South Point, Hawaii.
    return get_station("south_point")


@pytest.fixture
def bluffton() -> GroundStation:
    # The observer used in skyfield's documentation example.
    return GroundStation(
        key="bluffton",
        name="Bluffton, Ohio (skyfield docs example)",
        latitude_deg=40.8939,
        longitude_deg=-83.8917,
        elevation_m=0.0,
    )
