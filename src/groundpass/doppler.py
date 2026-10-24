"""Doppler shift on a one-way space-to-ground link.

Sign convention: range rate is positive when the satellite is moving
away from the station. An approaching satellite (negative range rate)
therefore gives a positive Doppler shift, so the received carrier sits
above the transmitted one before closest approach and below it after.

The first-order formula is used. The relativistic term is of order
(v / c)^2, about 5e-10 for a LEO satellite, which is roughly 1 Hz at
S-band and can be ignored here.
"""

import numpy as np
from numpy.typing import ArrayLike

SPEED_OF_LIGHT_M_S = 299_792_458.0


def doppler_shift_hz(
    carrier_hz: float, range_rate_m_s: ArrayLike
) -> np.ndarray:
    """Return the Doppler shift (received minus transmitted) in Hz."""
    range_rate = np.asarray(range_rate_m_s, dtype=float)
    return -carrier_hz * range_rate / SPEED_OF_LIGHT_M_S


def received_frequency_hz(
    carrier_hz: float, range_rate_m_s: ArrayLike
) -> np.ndarray:
    """Return the frequency seen at the ground station in Hz."""
    return carrier_hz + doppler_shift_hz(carrier_hz, range_rate_m_s)
