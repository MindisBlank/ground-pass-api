"""REST API for pass prediction.

Run locally:

    uvicorn groundpass.api:app --reload

then open http://127.0.0.1:8000/docs for the interactive documentation.

Configuration (environment variables):

    GROUNDPASS_TLE_FILE   Serve TLEs from this local file instead of
                          CelesTrak (offline use, demos, tests).
    GROUNDPASS_CACHE_DIR  Where CelesTrak TLEs are cached
                          (default ~/.cache/groundpass).
"""

import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field
from skyfield.api import EarthSatellite

from groundpass import __version__
from groundpass.passes import (
    TIMESCALE,
    Pass,
    PassDetail,
    compute_pass_detail,
    find_pass_by_tca,
    find_passes,
    parse_pass_id,
)
from groundpass.stations import (
    STATIONS,
    GroundStation,
    UnknownStationError,
    get_station,
)
from groundpass.tle import (
    DEFAULT_CACHE_DIR,
    CelestrakSource,
    FileSource,
    TleNotFoundError,
    TleSource,
    TleUnavailableError,
    load_satellite,
)

DEFAULT_DOWNLINK_HZ = 2.2e9  # S-band, typical for TT&C

app = FastAPI(
    title="Ground Pass API",
    version=__version__,
    description=(
        "Predicts satellite passes over ground stations: AOS, TCA, LOS, "
        "elevation, azimuth, range and downlink Doppler. Orbits are "
        "propagated with SGP4 from public TLEs."
    ),
)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class StationOut(BaseModel):
    key: str
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float


class PassSummary(BaseModel):
    pass_id: str = Field(description="Use with GET /passes/{pass_id}")
    norad_id: int
    satellite_name: str
    station: str
    aos: datetime
    tca: datetime
    los: datetime
    duration_s: float
    max_elevation_deg: float
    min_elevation_deg: float


class PassSample(BaseModel):
    time: datetime
    elevation_deg: float
    azimuth_deg: float
    range_km: float
    range_rate_km_s: float
    doppler_hz: float


class PassDetailOut(BaseModel):
    summary: PassSummary
    downlink_hz: float
    step_s: float
    max_doppler_hz: float
    max_azimuth_rate_deg_s: float = Field(
        description=(
            "Peak antenna azimuth rate. Very high values mean a "
            "near-overhead pass that an az-el mount may not track."
        )
    )
    samples: list[PassSample]


def _summary(p: Pass) -> PassSummary:
    return PassSummary(
        pass_id=p.pass_id,
        norad_id=p.norad_id,
        satellite_name=p.satellite_name,
        station=p.station_key,
        aos=p.aos,
        tca=p.tca,
        los=p.los,
        duration_s=round(p.duration_s, 1),
        max_elevation_deg=round(p.max_elevation_deg, 2),
        min_elevation_deg=p.min_elevation_deg,
    )


def _detail_out(detail: PassDetail, step_s: float) -> PassDetailOut:
    samples = [
        PassSample(
            time=t,
            elevation_deg=round(float(el), 3),
            azimuth_deg=round(float(az), 3),
            range_km=round(float(rng), 3),
            range_rate_km_s=round(float(rr), 5),
            doppler_hz=round(float(dop), 1),
        )
        for t, el, az, rng, rr, dop in zip(
            detail.times,
            detail.elevation_deg,
            detail.azimuth_deg,
            detail.range_km,
            detail.range_rate_km_s,
            detail.doppler_hz,
            strict=True,
        )
    ]
    return PassDetailOut(
        summary=_summary(detail.pass_),
        downlink_hz=detail.downlink_hz,
        step_s=step_s,
        max_doppler_hz=round(detail.max_doppler_hz, 1),
        max_azimuth_rate_deg_s=round(detail.max_azimuth_rate_deg_s, 3),
        samples=samples,
    )


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_tle_source() -> TleSource:
    """TLE source, chosen once from the environment."""
    tle_file = os.environ.get("GROUNDPASS_TLE_FILE")
    if tle_file:
        return FileSource(tle_file)
    cache_dir = os.environ.get("GROUNDPASS_CACHE_DIR", DEFAULT_CACHE_DIR)
    return CelestrakSource(cache_dir=cache_dir)


TleSourceDep = Annotated[TleSource, Depends(get_tle_source)]


def _station_or_404(key: str) -> GroundStation:
    try:
        return get_station(key)
    except UnknownStationError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


def _satellite_or_error(source: TleSource, norad_id: int) -> EarthSatellite:
    try:
        return load_satellite(source.get(norad_id), TIMESCALE)
    except TleNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except TleUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/stations", response_model=list[StationOut], tags=["stations"])
def list_stations() -> list[StationOut]:
    """All ground stations the service knows about."""
    return [
        StationOut(
            key=s.key,
            name=s.name,
            latitude_deg=s.latitude_deg,
            longitude_deg=s.longitude_deg,
            elevation_m=s.elevation_m,
        )
        for s in STATIONS.values()
    ]


@app.get("/passes", response_model=list[PassSummary], tags=["passes"])
def list_passes(
    source: TleSourceDep,
    norad_id: Annotated[
        int, Query(ge=1, description="NORAD catalogue number, e.g. 25544")
    ],
    station: Annotated[str, Query(description="Station key")] = "esrange",
    hours: Annotated[
        float, Query(gt=0, le=168, description="Search window length")
    ] = 24.0,
    min_elevation_deg: Annotated[float, Query(ge=0, lt=90)] = 5.0,
    start: Annotated[
        datetime | None,
        Query(description="Window start, ISO 8601. Defaults to now (UTC)"),
    ] = None,
) -> list[PassSummary]:
    """Upcoming passes of one satellite over one station."""
    ground_station = _station_or_404(station)
    satellite = _satellite_or_error(source, norad_id)
    if start is None:
        start = datetime.now(UTC)
    elif start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    passes = find_passes(
        satellite,
        ground_station,
        start=start,
        hours=hours,
        min_elevation_deg=min_elevation_deg,
    )
    return [_summary(p) for p in passes]


@app.get("/passes/{pass_id}", response_model=PassDetailOut, tags=["passes"])
def get_pass(
    source: TleSourceDep,
    pass_id: Annotated[
        str, Path(description="pass_id as returned by GET /passes")
    ],
    downlink_hz: Annotated[
        float, Query(gt=0, description="Downlink carrier frequency [Hz]")
    ] = DEFAULT_DOWNLINK_HZ,
    step_s: Annotated[float, Query(ge=1, le=60)] = 5.0,
    min_elevation_deg: Annotated[float, Query(ge=0, lt=90)] = 5.0,
) -> PassDetailOut:
    """Geometry and Doppler through one pass, sampled every ``step_s``."""
    try:
        norad_id, station_key, tca = parse_pass_id(pass_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None

    ground_station = _station_or_404(station_key)
    satellite = _satellite_or_error(source, norad_id)
    found = find_pass_by_tca(
        satellite, ground_station, tca, min_elevation_deg=min_elevation_deg
    )
    if found is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No pass of NORAD {norad_id} over {station_key} near "
                f"{tca.isoformat()} above {min_elevation_deg}° elevation"
            ),
        )
    detail = compute_pass_detail(
        satellite, ground_station, found, downlink_hz, step_s=step_s
    )
    return _detail_out(detail, step_s)
