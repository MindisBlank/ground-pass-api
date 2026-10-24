import pytest

mpl = pytest.importorskip("matplotlib")
mpl.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from conftest import WINDOW_START  # noqa: E402
from groundpass.passes import compute_pass_detail, find_passes  # noqa: E402
from groundpass.plotting import figures, style  # noqa: E402


def test_style_rc_params_are_valid():
    # rc_context raises if any key or value is invalid.
    with style.context():
        assert mpl.rcParams["font.size"] == style.FONT_SIZE["base"]


def test_overview_figure_renders(tmp_path, iss, south_point):
    p = find_passes(iss, south_point, WINDOW_START, hours=24)[0]
    detail = compute_pass_detail(iss, south_point, p, 2.2e9)

    fig = figures.plot_pass_overview(detail)
    path = style.save(fig, tmp_path / "overview")
    plt.close(fig)

    assert path.suffix == f".{style.EXPORT['format']}"
    assert path.stat().st_size > 0
