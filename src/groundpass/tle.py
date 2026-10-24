"""Two-line element (TLE) sources.

Two sources are provided:

* ``CelestrakSource`` fetches the latest TLE for a NORAD catalogue
  number from CelesTrak and caches it on disk, so repeated requests do
  not hammer their servers. If CelesTrak cannot be reached, a stale
  cached copy is used rather than failing.
* ``FileSource`` reads TLEs from a local file. Used by the tests and
  for working offline.
"""

import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from skyfield.api import EarthSatellite
from skyfield.timelib import Timescale

CELESTRAK_URL = (
    "https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
)
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "groundpass"
DEFAULT_MAX_AGE_HOURS = 6.0


@dataclass(frozen=True)
class Tle:
    """One satellite's two-line element set."""

    name: str
    line1: str
    line2: str

    @property
    def norad_id(self) -> int:
        return int(self.line1[2:7])


class TleNotFoundError(LookupError):
    """No TLE exists for the requested NORAD id."""


class TleUnavailableError(RuntimeError):
    """The TLE source could not be reached and nothing is cached."""


class TleSource(Protocol):
    """Anything that can return a TLE for a NORAD id."""

    def get(self, norad_id: int) -> Tle: ...


def parse_tle_text(text: str) -> dict[int, Tle]:
    """Parse TLE text in two-line or three-line (named) format.

    Returns a dict keyed by NORAD catalogue number.
    """
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    tles: dict[int, Tle] = {}
    i = 0
    while i < len(lines) - 1:
        line = lines[i]
        following = lines[i + 1]
        if line.startswith("1 ") and following.startswith("2 "):
            previous = lines[i - 1] if i > 0 else ""
            is_name = previous and not previous.startswith(("1 ", "2 "))
            norad_id = int(line[2:7])
            name = previous.strip() if is_name else f"NORAD {norad_id}"
            tles[norad_id] = Tle(name=name, line1=line, line2=following)
            i += 2
        else:
            i += 1
    return tles


class FileSource:
    """Serve TLEs from a local text file."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._tles = parse_tle_text(self.path.read_text(encoding="utf-8"))

    def get(self, norad_id: int) -> Tle:
        try:
            return self._tles[norad_id]
        except KeyError:
            raise TleNotFoundError(
                f"NORAD {norad_id} not found in {self.path}"
            ) from None


class CelestrakSource:
    """Fetch TLEs from CelesTrak, with an on-disk cache."""

    def __init__(
        self,
        cache_dir: str | os.PathLike[str] = DEFAULT_CACHE_DIR,
        max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
        timeout_s: float = 10.0,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.max_age_s = max_age_hours * 3600.0
        self.timeout_s = timeout_s

    def _cache_path(self, norad_id: int) -> Path:
        return self.cache_dir / f"{norad_id}.tle"

    def _download(self, norad_id: int) -> str:
        url = CELESTRAK_URL.format(norad_id=norad_id)
        with urllib.request.urlopen(url, timeout=self.timeout_s) as response:
            return response.read().decode("utf-8")

    def get(self, norad_id: int) -> Tle:
        cache_path = self._cache_path(norad_id)
        is_fresh = (
            cache_path.exists()
            and time.time() - cache_path.stat().st_mtime < self.max_age_s
        )
        if not is_fresh:
            try:
                text = self._download(norad_id)
            except (urllib.error.URLError, TimeoutError) as error:
                if not cache_path.exists():
                    raise TleUnavailableError(
                        f"Could not reach CelesTrak for NORAD {norad_id} "
                        "and no cached TLE exists"
                    ) from error
                # Fall through and use the stale cached copy.
            else:
                tles = parse_tle_text(text)
                if norad_id not in tles:
                    raise TleNotFoundError(
                        f"CelesTrak has no TLE for NORAD {norad_id}"
                    )
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text, encoding="utf-8")
                return tles[norad_id]

        tles = parse_tle_text(cache_path.read_text(encoding="utf-8"))
        if norad_id not in tles:
            raise TleNotFoundError(f"Cached file {cache_path} is invalid")
        return tles[norad_id]


def load_satellite(tle: Tle, ts: Timescale) -> EarthSatellite:
    """Build a skyfield satellite from a TLE."""
    return EarthSatellite(tle.line1, tle.line2, tle.name, ts)
