"""Ground station definitions.

Coordinates are approximate public figures, good to roughly a kilometre.
That is well inside the error of an SGP4 propagation from a TLE, so it
does not limit the accuracy of the pass predictions. Replace them with
surveyed antenna positions if you ever have them.
"""

from dataclasses import dataclass

from skyfield.api import wgs84
from skyfield.toposlib import GeographicPosition


@dataclass(frozen=True)
class GroundStation:
    """A ground station antenna site."""

    key: str
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float

    def topos(self) -> GeographicPosition:
        """Return the station as a skyfield WGS84 position."""
        return wgs84.latlon(
            self.latitude_deg,
            self.longitude_deg,
            elevation_m=self.elevation_m,
        )


STATIONS: dict[str, GroundStation] = {
    station.key: station
    for station in (
        GroundStation(
            key="esrange",
            name="Esrange Space Center, Kiruna, Sweden",
            latitude_deg=67.88,
            longitude_deg=21.07,
            elevation_m=330.0,
        ),
        GroundStation(
            key="inuvik",
            name="Inuvik, Northwest Territories, Canada",
            latitude_deg=68.32,
            longitude_deg=-133.55,
            elevation_m=90.0,
        ),
        GroundStation(
            key="south_point",
            name="South Point, Hawaii, USA",
            latitude_deg=19.01,
            longitude_deg=-155.66,
            elevation_m=370.0,
        ),
    )
}


class UnknownStationError(KeyError):
    """Raised when a station key is not in STATIONS."""


def get_station(key: str) -> GroundStation:
    """Look up a station by key, e.g. ``"esrange"``."""
    try:
        return STATIONS[key]
    except KeyError:
        known = ", ".join(sorted(STATIONS))
        raise UnknownStationError(
            f"Unknown station '{key}'. Known stations: {known}"
        ) from None
