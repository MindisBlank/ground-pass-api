"""Regenerate the example API responses shown in the README.

Calls the real API in-process, with a live TLE from CelesTrak, and
writes:

    docs/examples/passes.json        GET /passes
    docs/examples/pass_detail.json   GET /passes/{pass_id}, highest pass

It also prints each pass's TCA and maximum elevation, the two numbers
to compare against an independent predictor such as Heavens-Above or
gpredict (both are independent of the elevation mask, unlike AOS/LOS).

Usage:

    python scripts/make_examples.py
    python scripts/make_examples.py --norad-id 25544 --station south_point
"""

import argparse
import json
import warnings
from pathlib import Path

# Starlette warns about its test client's HTTP library; not our concern.
warnings.filterwarnings("ignore", message="Using `httpx`")

from fastapi.testclient import TestClient  # noqa: E402

from groundpass.api import app  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "examples"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--norad-id", type=int, default=43013)
    parser.add_argument("--station", default="esrange")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--downlink-hz", type=float, default=2.2e9)
    parser.add_argument("--step-s", type=float, default=10.0)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {path}")


def main() -> None:
    args = parse_args()
    client = TestClient(app)

    response = client.get(
        "/passes",
        params={
            "norad_id": args.norad_id,
            "station": args.station,
            "hours": args.hours,
        },
    )
    response.raise_for_status()
    passes = response.json()
    if not passes:
        raise SystemExit("No passes in the window")

    best = max(passes, key=lambda p: p["max_elevation_deg"])
    response = client.get(
        f"/passes/{best['pass_id']}",
        params={"downlink_hz": args.downlink_hz, "step_s": args.step_s},
    )
    response.raise_for_status()
    detail = response.json()

    write_json(args.output_dir / "passes.json", passes)
    write_json(args.output_dir / "pass_detail.json", detail)

    print(f"\n{passes[0]['satellite_name']} over {args.station}")
    print(f"{'TCA (UTC)':<22}{'max el':>8}{'duration':>10}")
    for p in passes:
        tca = p["tca"].replace("T", " ")[:19]
        print(
            f"{tca:<22}{p['max_elevation_deg']:>7.1f}°"
            f"{p['duration_s'] / 60:>9.1f}m"
        )

    print(f"\nHighest pass: {best['pass_id']}")
    print(f"  max elevation     {best['max_elevation_deg']:.1f}°")
    print(f"  max Doppler       ±{detail['max_doppler_hz'] / 1e3:.1f} kHz")
    print(f"  max azimuth rate  {detail['max_azimuth_rate_deg_s']:.2f} °/s")


if __name__ == "__main__":
    main()
