import numpy as np
import pytest

from groundpass.doppler import (
    SPEED_OF_LIGHT_M_S,
    doppler_shift_hz,
    received_frequency_hz,
)


def test_approaching_satellite_shifts_up():
    assert doppler_shift_hz(2.2e9, -7000.0) > 0


def test_receding_satellite_shifts_down():
    assert doppler_shift_hz(2.2e9, 7000.0) < 0


def test_magnitude_at_s_band():
    # 7 km/s closing speed at 2.2 GHz: 2.2e9 * 7000 / c ≈ 51.4 kHz.
    expected = 2.2e9 * 7000.0 / SPEED_OF_LIGHT_M_S
    assert doppler_shift_hz(2.2e9, -7000.0) == pytest.approx(expected)
    assert expected == pytest.approx(51_368.0, abs=5.0)


def test_scales_linearly_with_carrier():
    s_band = doppler_shift_hz(2.2e9, -7000.0)
    x_band = doppler_shift_hz(8.2e9, -7000.0)
    assert x_band / s_band == pytest.approx(8.2 / 2.2)


def test_received_frequency_and_arrays():
    range_rate = np.array([-7000.0, 0.0, 7000.0])
    received = received_frequency_hz(2.2e9, range_rate)
    assert received[0] > 2.2e9
    assert received[1] == pytest.approx(2.2e9)
    assert received[2] < 2.2e9
