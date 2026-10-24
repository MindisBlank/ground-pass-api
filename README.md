# Ground Pass API

Predicts when a satellite is visible from a ground station and what the
link geometry looks like during the pass: AOS, TCA and LOS, elevation and
azimuth, slant range, and Doppler shift on the downlink. A small FastAPI
service exposes it over REST.

Orbits are propagated with SGP4 (via [skyfield](https://rhodesmill.org/skyfield/))
from public TLEs fetched from [CelesTrak](https://celestrak.org).

![Pass overview](docs/figures/pass_overview.png)

## Why

Ground station networks sold as a service schedule customer passes
through an API. This is a small version of the piece that comes first:
working out when the passes are and what the antenna and receiver have
to do during them (where to point, how fast to slew, how far the carrier
moves).

It is a learning project, not an operational tool. See
[Limitations](#limitations).

## Quick start

Requires [conda](https://docs.conda.io/) (Miniconda or Anaconda).

```bash
conda env create -f environment.yml
conda activate ground-pass-api
pytest
```

Run the API:

```bash
uvicorn groundpass.api:app --reload
```

Interactive docs: <http://127.0.0.1:8000/docs>

Generate the figures and print upcoming passes:

```bash
python scripts/make_figures.py                      # NOAA-20 over Esrange
python scripts/make_figures.py --norad-id 25544 --station south_point
```

## API

| Method | Path                | Returns                                         |
|--------|---------------------|-------------------------------------------------|
| GET    | `/health`           | Service status                                  |
| GET    | `/stations`         | Known ground stations                           |
| GET    | `/passes`           | Passes of one satellite over one station        |
| GET    | `/passes/{pass_id}` | Elevation, azimuth, range and Doppler over time |

List the next 24 h of NOAA-20 passes over Esrange:

```bash
curl "http://127.0.0.1:8000/passes?norad_id=43013&station=esrange"
```

```json
[
  {
    "pass_id": "43013-esrange-20261024T101530Z",
    "norad_id": 43013,
    "satellite_name": "NOAA 20 (JPSS-1)",
    "station": "esrange",
    "aos": "2026-10-24T10:09:12Z",
    "tca": "2026-10-24T10:15:30Z",
    "los": "2026-10-24T10:21:49Z",
    "duration_s": 757.0,
    "max_elevation_deg": 61.4,
    "min_elevation_deg": 5.0
  }
]
```

*(Illustrative values. Run it to get real ones.)*

Detail of one pass at X-band, sampled every 10 s:

```bash
curl "http://127.0.0.1:8000/passes/43013-esrange-20261024T101530Z?downlink_hz=8.2e9&step_s=10"
```

Query parameters for `/passes`: `norad_id` (required), `station`
(default `esrange`), `hours` (default 24, max 168), `min_elevation_deg`
(default 5), `start` (ISO 8601, default now).

Query parameters for `/passes/{pass_id}`: `downlink_hz` (default 2.2e9),
`step_s` (default 5), `min_elevation_deg` (default 5).

## Docker

```bash
docker build -t ground-pass-api .
docker run --rm -p 8000:8000 ground-pass-api
```

## Design notes

**Doppler.** One-way, first order: `Δf = −f₀ · ṙ / c`, where `ṙ` is the
range rate (positive when the satellite moves away). The relativistic
term is about 5 × 10⁻¹⁰ for LEO, roughly 1 Hz at S-band, and is ignored.
Doppler scales with carrier frequency, so a LEO pass that moves an S-band
carrier by about ±50 kHz moves an X-band carrier by about ±180 kHz.

**Pass ids from TCA.** A pass id is `{norad_id}-{station}-{TCA}`. TCA does
not depend on the elevation mask, while AOS and LOS do, so the same
physical pass keeps the same id whatever mask the client asks for. The
service is stateless: the detail endpoint recomputes the pass from the
id.

**Azimuth rate.** Each pass detail reports the peak azimuth rate. On a
near-overhead pass this rises sharply as the satellite crosses close to
zenith, which is the "keyhole" problem for az-el antenna mounts.

**TLE cache.** TLEs are cached on disk for 6 hours, which is plenty given
how often CelesTrak updates them. If CelesTrak cannot be reached, a stale
cached copy is used. Set `GROUNDPASS_TLE_FILE` to serve from a local file
instead.

## Validation

- The pass finder reproduces the ISS pass times published in skyfield's
  documentation to within 2 s (`tests/test_passes.py`).
- Physical checks in the tests: AOS < TCA < LOS, minimum range at
  maximum elevation, Doppler sign change across TCA, Doppler magnitude
  bounded by orbital velocity.
- TODO: compare one live pass against gpredict or Heavens-Above and note
  the difference here.

## Limitations

- SGP4 from TLEs is accurate to around a kilometre near epoch and gets
  worse with TLE age. Fine for scheduling and pointing estimates, not for
  precise orbit determination.
- No atmospheric refraction, which matters a little at very low
  elevation.
- No antenna model: no slew or acceleration limits, no local horizon
  mask, no keyhole handling beyond reporting the azimuth rate.
- Station coordinates are approximate public figures.
- The detail endpoint searches one hour either side of TCA, which assumes
  LEO.

## Project layout

```
src/groundpass/
    stations.py        ground station definitions
    tle.py             TLE parsing, CelesTrak fetch and cache
    passes.py          pass finding and pass detail
    doppler.py         Doppler shift
    api.py             FastAPI service
    plotting/
        style.py       style guide: every colour, font and size lives here
        figures.py     elevation, Doppler and sky-track plots
scripts/make_figures.py
tests/
```

## Plot style

All figures take their look from `src/groundpass/plotting/style.py`.
Change a colour, font, figure size or the export format there and
re-run `scripts/make_figures.py`. Set `EXPORT["format"] = "pdf"` for
figures going into LaTeX.

## Development

Code follows PEP 8 (79-character lines), checked with ruff:

```bash
ruff check .
ruff format .
```
