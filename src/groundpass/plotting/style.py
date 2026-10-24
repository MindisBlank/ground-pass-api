"""Project style guide: the ONE place that defines how figures look.

Every plot in this project takes its colours, fonts, sizes, line widths
and export settings from this file. To restyle all figures, edit the
constants below and re-run ``python scripts/make_figures.py``.

Usage
-----
In plotting code, decorate the function with ``@styled`` and pull
colours from ``COLORS`` by meaning, never by hex value::

    from groundpass.plotting import style

    @style.styled
    def my_plot(...):
        fig, ax = plt.subplots(figsize=style.FIGSIZE["single"])
        ax.plot(x, y, color=style.COLORS["primary"])
        return fig

    style.save(fig, "docs/figures/my_plot")

In a notebook, call ``style.apply()`` once to use the same look.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

import matplotlib as mpl
from matplotlib.figure import Figure

# ---------------------------------------------------------------------------
# Colours, by meaning. Plots refer to the key, never to the hex value.
# ---------------------------------------------------------------------------
COLORS: dict[str, str] = {
    "primary": "#1F4E79",  # main data trace (elevation, sky track)
    "secondary": "#C8553D",  # second quantity (Doppler)
    "accent": "#2A9D8F",  # event markers (AOS, TCA, LOS)
    "threshold": "#8D99AE",  # elevation mask, limits, reference lines
    "text": "#222222",
    "muted_text": "#5C6370",
    "grid": "#D9DDE3",
    "background": "#FFFFFF",
}

# Colour cycle for plots with several series (e.g. several stations).
CYCLE: list[str] = [
    COLORS["primary"],
    COLORS["secondary"],
    COLORS["accent"],
    "#E9C46A",
    "#6D597A",
    "#264653",
]

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
FONT_FAMILY = "DejaVu Sans"  # ships with matplotlib, so works everywhere
TITLE_WEIGHT = "bold"
FONT_SIZE = {
    "base": 10,
    "title": 12,
    "label": 10,
    "tick": 9,
    "legend": 9,
}

# ---------------------------------------------------------------------------
# Figure sizes in inches (width, height)
# ---------------------------------------------------------------------------
FIGSIZE: dict[str, tuple[float, float]] = {
    "single": (6.4, 3.8),
    "square": (5.0, 5.0),
    "wide": (10.0, 3.8),
    "overview": (11.0, 6.0),
}

# ---------------------------------------------------------------------------
# Lines and markers
# ---------------------------------------------------------------------------
LINE_WIDTH = 1.8
THIN_LINE_WIDTH = 1.0
MARKER_SIZE = 6

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
EXPORT = {
    "format": "png",  # "png" for the README, "pdf" for LaTeX
    "dpi": 200,
    "transparent": False,
}


def rc_params() -> dict[str, Any]:
    """Return the matplotlib rcParams implied by the constants above."""
    return {
        "font.family": FONT_FAMILY,
        "font.size": FONT_SIZE["base"],
        "axes.titlesize": FONT_SIZE["title"],
        "axes.titleweight": TITLE_WEIGHT,
        "axes.labelsize": FONT_SIZE["label"],
        "axes.labelcolor": COLORS["text"],
        "axes.edgecolor": COLORS["muted_text"],
        "axes.linewidth": 0.8,
        "axes.facecolor": COLORS["background"],
        "axes.grid": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": mpl.cycler(color=CYCLE),
        "grid.color": COLORS["grid"],
        "grid.linewidth": 0.6,
        "xtick.labelsize": FONT_SIZE["tick"],
        "ytick.labelsize": FONT_SIZE["tick"],
        "xtick.color": COLORS["muted_text"],
        "ytick.color": COLORS["muted_text"],
        "legend.fontsize": FONT_SIZE["legend"],
        "legend.frameon": False,
        "lines.linewidth": LINE_WIDTH,
        "lines.markersize": MARKER_SIZE,
        "text.color": COLORS["text"],
        "figure.facecolor": COLORS["background"],
        "figure.dpi": 100,
        "figure.constrained_layout.use": True,
        "savefig.dpi": EXPORT["dpi"],
        "savefig.format": EXPORT["format"],
        "savefig.transparent": EXPORT["transparent"],
    }


def apply() -> None:
    """Apply the project style globally (handy in notebooks)."""
    mpl.rcParams.update(rc_params())


@contextmanager
def context() -> Iterator[None]:
    """Apply the project style only inside a ``with`` block."""
    with mpl.rc_context(rc_params()):
        yield


F = TypeVar("F", bound=Callable[..., Any])


def styled(func: F) -> F:
    """Decorator: run a plotting function inside the project style."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with context():
            return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def save(fig: Figure, path: str | Path) -> Path:
    """Save a figure using the export settings. Returns the file path.

    ``path`` may omit the extension; ``EXPORT["format"]`` is used then.
    """
    path = Path(path)
    if not path.suffix:
        path = path.with_suffix(f".{EXPORT['format']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        path,
        dpi=EXPORT["dpi"],
        transparent=EXPORT["transparent"],
        facecolor=COLORS["background"],
    )
    return path
