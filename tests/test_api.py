import pytest
from fastapi.testclient import TestClient

from conftest import ISS_NORAD_ID, ISS_TLE_FILE
from groundpass.api import app, get_tle_source
from groundpass.tle import FileSource

START = "2014-01-23T00:00:00Z"


@pytest.fixture
def client():
    app.dependency_overrides[get_tle_source] = lambda: FileSource(ISS_TLE_FILE)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _list_passes(client, **params):
    query = {
        "norad_id": ISS_NORAD_ID,
        "station": "south_point",
        "start": START,
        **params,
    }
    return client.get("/passes", params=query)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_stations_include_esrange(client):
    keys = {s["key"] for s in client.get("/stations").json()}
    assert "esrange" in keys


def test_list_passes(client):
    response = _list_passes(client)
    assert response.status_code == 200
    passes = response.json()
    assert passes
    first = passes[0]
    assert first["norad_id"] == ISS_NORAD_ID
    assert first["station"] == "south_point"
    assert first["aos"] < first["tca"] < first["los"]


def test_pass_detail_round_trip(client):
    pass_id = _list_passes(client).json()[0]["pass_id"]
    response = client.get(f"/passes/{pass_id}", params={"step_s": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["pass_id"] == pass_id
    assert body["downlink_hz"] == pytest.approx(2.2e9)
    assert len(body["samples"]) > 10
    assert body["samples"][0]["doppler_hz"] > 0
    assert body["samples"][-1]["doppler_hz"] < 0


def test_unknown_station_is_404(client):
    assert _list_passes(client, station="atlantis").status_code == 404


def test_unknown_satellite_is_404(client):
    assert _list_passes(client, norad_id=99999).status_code == 404


def test_malformed_pass_id_is_422(client):
    assert client.get("/passes/not-a-pass").status_code == 422


def test_window_too_long_is_422(client):
    assert _list_passes(client, hours=500).status_code == 422
