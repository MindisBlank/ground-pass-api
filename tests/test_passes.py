from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from conftest import WINDOW_START
from groundpass.doppler import SPEED_OF_LIGHT_M_S
from groundpass.passes import (
    compute_pass_detail,
    find_pass_by_tca,
    find_passes,
    parse_pass_id,
)

S_BAND_HZ = 2.2e9


def _utc(hour, minute, second):
    return datetime(2014, 1, 23, hour, minute, second, tzinfo=UTC)


def test_matches_skyfield_documented_passes(iss, bluffton):
    """Reproduce the two 30° passes published in skyfield's docs."""
    expected = [
        (_utc(6, 25, 37), _utc(6, 26, 58), _utc(6, 28, 19)),
        (_utc(12, 54, 56), _utc(12, 56, 27), _utc(12, 57, 58)),
    ]
    passes = find_passes(
        iss, bluffton, WINDOW_START, hours=24, min_elevation_deg=30.0
    )

    assert len(passes) == len(expected)
    for found, (aos, tca, los) in zip(passes, expected, strict=True):
        assert abs((found.aos - aos).total_seconds()) < 2
        assert abs((found.tca - tca).total_seconds()) < 2
        assert abs((found.los - los).total_seconds()) < 2


def test_passes_are_ordered_and_bounded(iss, south_point):
    passes = find_passes(iss, south_point, WINDOW_START, hours=24)

    assert passes, "expected at least one ISS pass in 24 h"
    for p in passes:
        assert p.aos < p.tca < p.los
        assert 5.0 <= p.max_elevation_deg <= 90.0
        # A LEO pass at 5° mask lasts minutes, not hours.
        assert 60 < p.duration_s < 20 * 60


def test_pass_in_progress_at_window_start_is_dropped(iss, south_point):
    first = find_passes(iss, south_point, WINDOW_START, hours=24)[0]
    later = find_passes(iss, south_point, first.tca, hours=6)

    assert all(p.aos >= first.tca for p in later)


def test_pass_id_round_trip(iss, south_point):
    p = find_passes(iss, south_point, WINDOW_START, hours=24)[0]
    norad_id, station_key, tca = parse_pass_id(p.pass_id)

    assert norad_id == 25544
    assert station_key == "south_point"
    found = find_pass_by_tca(iss, south_point, tca)
    assert found is not None
    assert abs((found.aos - p.aos).total_seconds()) < 2


@pytest.mark.parametrize("bad_id", ["", "abc", "25544-esrange", "x-y-z"])
def test_malformed_pass_id_raises(bad_id):
    with pytest.raises(ValueError):
        parse_pass_id(bad_id)


def test_naive_datetime_rejected(iss, south_point):
    with pytest.raises(ValueError):
        find_passes(iss, south_point, datetime(2014, 1, 23), hours=1)


def test_pass_detail_physics(iss, south_point):
    passes = find_passes(iss, south_point, WINDOW_START, hours=24)
    p = max(passes, key=lambda candidate: candidate.max_elevation_deg)
    detail = compute_pass_detail(iss, south_point, p, S_BAND_HZ, step_s=2)

    # Elevation starts and ends at the mask and peaks at TCA.
    assert detail.elevation_deg[0] == pytest.approx(5.0, abs=0.5)
    assert detail.elevation_deg[-1] == pytest.approx(5.0, abs=0.5)
    assert detail.elevation_deg.max() == pytest.approx(
        p.max_elevation_deg, abs=0.5
    )

    # Closest approach coincides with maximum elevation.
    i_min_range = int(np.argmin(detail.range_km))
    i_max_el = int(np.argmax(detail.elevation_deg))
    assert abs(i_min_range - i_max_el) <= 2

    # Approaching then receding: Doppler goes from positive to negative.
    assert detail.doppler_hz[0] > 0
    assert detail.doppler_hz[-1] < 0

    # Range rate can never exceed LEO orbital speed (~7.7 km/s), which
    # bounds the S-band Doppler at about 57 kHz.
    bound_hz = S_BAND_HZ * 7.8e3 / SPEED_OF_LIGHT_M_S
    assert 20e3 < detail.max_doppler_hz < bound_hz


def test_detail_samples_cover_the_pass(iss, south_point):
    p = find_passes(iss, south_point, WINDOW_START, hours=24)[0]
    detail = compute_pass_detail(iss, south_point, p, S_BAND_HZ, step_s=5)

    assert detail.times[0] - p.aos < timedelta(seconds=1)
    assert p.los - detail.times[-1] < timedelta(seconds=1)
    assert len(detail.times) == len(detail.doppler_hz)


def test_peak_azimuth_rate_does_not_depend_on_step(iss, south_point):
    """Coarse sampling must not hide the azimuth-rate peak at TCA."""
    passes = find_passes(iss, south_point, WINDOW_START, hours=24)
    p = max(passes, key=lambda candidate: candidate.max_elevation_deg)
    fine = compute_pass_detail(iss, south_point, p, S_BAND_HZ, step_s=1)
    coarse = compute_pass_detail(iss, south_point, p, S_BAND_HZ, step_s=30)

    assert coarse.max_azimuth_rate_deg_s == pytest.approx(
        fine.max_azimuth_rate_deg_s, rel=0.02
    )
