import pytest

from conftest import ISS_TLE_FILE
from groundpass.tle import FileSource, TleNotFoundError, parse_tle_text

LINE1 = "1 25544U 98067A   14020.93268519  .00009878  00000-0  18200-3 0  5082"
LINE2 = "2 25544  51.6498 109.4756 0003572  55.9686 274.8005 15.49815350868473"


def test_parse_three_line_format():
    tles = parse_tle_text(f"ISS (ZARYA)\n{LINE1}\n{LINE2}\n")
    assert tles[25544].name == "ISS (ZARYA)"
    assert tles[25544].line1 == LINE1
    assert tles[25544].line2 == LINE2


def test_parse_two_line_format_gets_default_name():
    tles = parse_tle_text(f"{LINE1}\n{LINE2}\n")
    assert tles[25544].name == "NORAD 25544"


def test_parse_ignores_blank_lines_and_windows_newlines():
    tles = parse_tle_text(f"\r\nISS (ZARYA)\r\n{LINE1}\r\n\r\n{LINE2}\r\n")
    assert tles[25544].norad_id == 25544


def test_parse_rejects_garbage():
    assert parse_tle_text("No GP data found") == {}


def test_file_source_lookup():
    source = FileSource(ISS_TLE_FILE)
    assert source.get(25544).name == "ISS (ZARYA)"
    with pytest.raises(TleNotFoundError):
        source.get(99999)
