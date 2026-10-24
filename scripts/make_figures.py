"""Generate the README figures and print upcoming passes.

Examples
--------
Next good pass of NOAA-20 over Esrange, live TLE from CelesTrak::

    python scripts/make_figures.py

Another satellite, station and band::

    python scripts/make_figures.py --norad-id 25544 --station south_point \\
        --downlink-hz 2.2e9

Offline, from a local TLE file::

    python scripts/make_figures.py --tle-file tests/data/iss_2014.tle \\
        --norad-id 25544 --station south_point --start 2014-01-23T00:00Z
"""

import argparse
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt

from groundpass.passes import (
    TIMESCALE,
    compute_pass_detail,
    find_passes,
)
from groundpass.plotting import figures, style
from groundpass.stations import get_station
from groundpass.tle import CelestrakSource, FileSource, load_satellite

DEFAULT_NORAD_ID = 43013  # NOAA-20 (JPSS-1), polar orbit, seen from Esrange
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "figures"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--norad-id", type=int, default=DEFAULT_NORAD_ID)
    parser.add_argument("--station", default="esrange")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--min-elevation-deg", type=float, default=5.0)
    parser.add_argument("--downlink-hz", type=float, default=2.2e9)
    parser.add_argument(
        "--start",
        type=datetime.fromisoformat,
        default=None,
        help="Window start, ISO 8601 (default: now, UTC)",
    )
    parser.add_argument("--tle-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = FileSource(args.tle_file) if args.tle_file else CelestrakSource()
    satellite = load_satellite(source.get(args.norad_id), TIMESCALE)
    station = get_station(args.station)
    start = args.start or datetime.now(UTC)
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)

    passes = find_passes(
        satellite,
        station,
        start=start,
        hours=args.hours,
        min_elevation_deg=args.min_elevation_deg,
    )
    if not passes:
        raise SystemExit(
            f"No passes of {satellite.name} over {station.key} "
            f"in the next {args.hours:g} h"
        )

    print(f"{satellite.name} over {station.name}")
    print(f"{'AOS (UTC)':<20} {'LOS (UTC)':<20} {'max el':>7} {'dur':>6}")
    for p in passes:
        print(
            f"{p.aos:%Y-%m-%d %H:%M:%S}  {p.los:%Y-%m-%d %H:%M:%S}  "
            f"{p.max_elevation_deg:6.1f}°  {p.duration_s / 60:5.1f}m"
        )

    best = max(passes, key=lambda p: p.max_elevation_deg)
    detail = compute_pass_detail(
        satellite, station, best, downlink_hz=args.downlink_hz
    )
    print(
        f"\nPlotting highest pass: {best.pass_id} "
        f"(max el {best.max_elevation_deg:.1f}°, "
        f"max Doppler ±{detail.max_doppler_hz / 1e3:.1f} kHz)"
    )

    plots = {
        "pass_overview": figures.plot_pass_overview,
        "elevation": figures.plot_elevation,
        "doppler": figures.plot_doppler,
        "sky_track": figures.plot_sky_track,
    }
    for name, plot in plots.items():
        fig = plot(detail)
        path = style.save(fig, args.output_dir / name)
        plt.close(fig)
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
