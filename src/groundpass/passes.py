"""Pass prediction: when a satellite is visible from a ground station,
and what the geometry and Doppler look like during the pass.

Terminology
-----------
AOS  Acquisition of signal: the satellite rises above the minimum
     elevation.
TCA  Time of closest approach: the moment of maximum elevation.
LOS  Loss of signal: the satellite sets below the minimum elevation.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
from skyfield.api import EarthSatellite, load
from skyfield.timelib import Timescale

from groundpass.doppler import doppler_shift_hz
from groundpass.stations import GroundStation

# skyfield ships its own leap-second and Delta-T tables, so this needs
# no network access.
TIMESCALE: Timescale = load.timescale()

_EVENT_RISE, _EVENT_CULMINATE, _EVENT_SET = 0, 1, 2
_PASS_ID_TIME_FORMAT = "%Y%m%dT%H%M%SZ"


@dataclass(frozen=True)
class Pass:
    """One visibility window of a satellite over a station."""

    norad_id: int
    satellite_name: str
    station_key: str
    aos: datetime
    tca: datetime
    los: datetime
    max_elevation_deg: float
    min_elevation_deg: float

    @property
    def duration_s(self) -> float:
        return (self.los - self.aos).total_seconds()

    @property
    def pass_id(self) -> str:
        """Stable identifier, e.g. ``25544-esrange-20261024T101530Z``.

        Built from TCA rather than AOS because TCA does not depend on
        the minimum-elevation threshold, so the same physical pass gets
        the same id whatever mask the client asked for.
        """
        tca = self.tca.strftime(_PASS_ID_TIME_FORMAT)
        return f"{self.norad_id}-{self.station_key}-{tca}"


@dataclass(frozen=True)
class PassDetail:
    """Time series of the geometry through one pass."""

    pass_: Pass
    downlink_hz: float
    times: list[datetime]
    elevation_deg: np.ndarray
    azimuth_deg: np.ndarray
    range_km: np.ndarray
    range_rate_km_s: np.ndarray
    azimuth_rate_deg_s: np.ndarray
    doppler_hz: np.ndarray
    tca_azimuth_rate_deg_s: float

    @property
    def seconds_since_aos(self) -> np.ndarray:
        aos = self.pass_.aos
        return np.array([(t - aos).total_seconds() for t in self.times])

    @property
    def max_doppler_hz(self) -> float:
        return float(np.max(np.abs(self.doppler_hz)))

    @property
    def max_azimuth_rate_deg_s(self) -> float:
        """Peak azimuth rate, independent of the sampling step.

        The rate peaks where the satellite passes closest to zenith,
        i.e. at TCA. On a near-overhead pass that peak is so narrow that
        fixed-step samples miss it, so the rate at TCA is included.
        """
        sampled = float(np.max(np.abs(self.azimuth_rate_deg_s)))
        return max(sampled, abs(self.tca_azimuth_rate_deg_s))


def parse_pass_id(pass_id: str) -> tuple[int, str, datetime]:
    """Split a pass id into (norad_id, station_key, tca).

    Raises ``ValueError`` if the id is malformed.
    """
    norad_text, _, rest = pass_id.partition("-")
    station_key, _, tca_text = rest.rpartition("-")
    if not norad_text.isdigit() or not station_key or not tca_text:
        raise ValueError(f"Malformed pass id: '{pass_id}'")
    tca = datetime.strptime(tca_text, _PASS_ID_TIME_FORMAT)
    return int(norad_text), station_key, tca.replace(tzinfo=UTC)


def _to_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("Datetimes must be timezone-aware")
    return moment.astimezone(UTC)


def find_passes(
    satellite: EarthSatellite,
    station: GroundStation,
    start: datetime,
    hours: float = 24.0,
    min_elevation_deg: float = 5.0,
    ts: Timescale = TIMESCALE,
) -> list[Pass]:
    """Return all complete passes that start within the search window.

    A pass already in progress at ``start``, or still in progress at the
    end of the window, is left out: its AOS or LOS would be wrong.
    """
    start = _to_utc(start)
    t0 = ts.from_datetime(start)
    t1 = ts.from_datetime(start + timedelta(hours=hours))
    topos = station.topos()

    times, events = satellite.find_events(
        topos, t0, t1, altitude_degrees=min_elevation_deg
    )
    if len(events) == 0:
        return []

    elevations = (satellite - topos).at(times).altaz()[0].degrees
    norad_id = int(satellite.model.satnum)

    passes: list[Pass] = []
    aos = tca = None
    max_el = -math.inf
    for t, event, elevation in zip(
        times.utc_datetime(), events, elevations, strict=True
    ):
        if event == _EVENT_RISE:
            aos, tca, max_el = t, None, -math.inf
        elif event == _EVENT_CULMINATE and aos is not None:
            # A pass can culminate more than once; keep the highest.
            if elevation > max_el:
                tca, max_el = t, float(elevation)
        elif event == _EVENT_SET and aos is not None and tca is not None:
            passes.append(
                Pass(
                    norad_id=norad_id,
                    satellite_name=satellite.name or f"NORAD {norad_id}",
                    station_key=station.key,
                    aos=aos,
                    tca=tca,
                    los=t,
                    max_elevation_deg=max_el,
                    min_elevation_deg=min_elevation_deg,
                )
            )
            aos = tca = None
    return passes


def find_pass_by_tca(
    satellite: EarthSatellite,
    station: GroundStation,
    tca: datetime,
    min_elevation_deg: float = 5.0,
    tolerance_s: float = 5.0,
    ts: Timescale = TIMESCALE,
) -> Pass | None:
    """Recompute the pass whose TCA is within ``tolerance_s`` of ``tca``.

    Searches one hour either side, which covers any LEO pass.
    """
    tca = _to_utc(tca)
    candidates = find_passes(
        satellite,
        station,
        start=tca - timedelta(hours=1),
        hours=2.0,
        min_elevation_deg=min_elevation_deg,
        ts=ts,
    )
    for candidate in candidates:
        if abs((candidate.tca - tca).total_seconds()) <= tolerance_s:
            return candidate
    return None


def compute_pass_detail(
    satellite: EarthSatellite,
    station: GroundStation,
    pass_: Pass,
    downlink_hz: float,
    step_s: float = 5.0,
    ts: Timescale = TIMESCALE,
) -> PassDetail:
    """Sample elevation, azimuth, range and Doppler from AOS to LOS."""
    n_samples = max(int(pass_.duration_s // step_s) + 1, 2)
    times = ts.linspace(
        ts.from_datetime(pass_.aos), ts.from_datetime(pass_.los), n_samples
    )
    topos = station.topos()
    topocentric = (satellite - topos).at(times)

    # With the station itself as the reference frame, skyfield returns
    # (elevation, azimuth, range) and their rates in a single call.
    (
        elevation,
        azimuth,
        distance,
        _elevation_rate,
        azimuth_rate,
        range_rate,
    ) = topocentric.frame_latlon_and_rates(topos)

    at_tca = (satellite - topos).at(ts.from_datetime(pass_.tca))
    tca_azimuth_rate = at_tca.frame_latlon_and_rates(topos)[4]

    return PassDetail(
        pass_=pass_,
        downlink_hz=downlink_hz,
        times=list(times.utc_datetime()),
        elevation_deg=elevation.degrees,
        azimuth_deg=azimuth.degrees,
        range_km=distance.km,
        range_rate_km_s=range_rate.km_per_s,
        azimuth_rate_deg_s=azimuth_rate.degrees.per_second,
        doppler_hz=doppler_shift_hz(downlink_hz, range_rate.m_per_s),
        tca_azimuth_rate_deg_s=float(tca_azimuth_rate.degrees.per_second),
    )
