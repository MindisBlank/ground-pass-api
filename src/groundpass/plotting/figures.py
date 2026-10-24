"""Pass figures: elevation, Doppler and sky track.

All styling comes from ``groundpass.plotting.style``. Nothing in this
file should hard-code a colour, font or size.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.projections.polar import PolarAxes

from groundpass.plotting import style

if TYPE_CHECKING:
    from groundpass.passes import PassDetail


def _minutes_since_aos(detail: PassDetail) -> np.ndarray:
    return detail.seconds_since_aos / 60.0


def _title(detail: PassDetail) -> str:
    p = detail.pass_
    return (
        f"{p.satellite_name} over {p.station_key} | "
        f"AOS {p.aos:%Y-%m-%d %H:%M} UTC"
    )


def _new_axes(
    ax: Axes | None, figsize_key: str, polar: bool = False
) -> tuple[Figure, Axes]:
    if ax is not None:
        return ax.figure, ax
    subplot_kw = {"projection": "polar"} if polar else None
    fig, ax = plt.subplots(
        figsize=style.FIGSIZE[figsize_key], subplot_kw=subplot_kw
    )
    return fig, ax


@style.styled
def plot_elevation(detail: PassDetail, ax: Axes | None = None) -> Figure:
    """Elevation against time since AOS, with the elevation mask."""
    fig, ax = _new_axes(ax, "single")
    minutes = _minutes_since_aos(detail)
    elevation = detail.elevation_deg
    i_max = int(np.argmax(elevation))

    ax.plot(minutes, elevation, color=style.COLORS["primary"])
    ax.axhline(
        detail.pass_.min_elevation_deg,
        color=style.COLORS["threshold"],
        linestyle="--",
        linewidth=style.THIN_LINE_WIDTH,
        label=f"Mask {detail.pass_.min_elevation_deg:.0f}°",
    )
    ax.plot(
        minutes[i_max],
        elevation[i_max],
        marker="o",
        linestyle="none",
        color=style.COLORS["accent"],
        label=f"TCA {elevation[i_max]:.1f}°",
    )
    ax.set_xlabel("Time since AOS [min]")
    ax.set_ylabel("Elevation [°]")
    ax.set_ylim(0, max(90.0, float(elevation.max()) + 5.0))
    ax.set_xlim(minutes[0], minutes[-1])
    ax.set_title("Elevation")
    ax.legend(loc="upper right")
    return fig


@style.styled
def plot_doppler(detail: PassDetail, ax: Axes | None = None) -> Figure:
    """Doppler shift on the downlink against time since AOS."""
    fig, ax = _new_axes(ax, "single")
    minutes = _minutes_since_aos(detail)
    doppler_khz = detail.doppler_hz / 1e3

    ax.plot(minutes, doppler_khz, color=style.COLORS["secondary"])
    ax.axhline(
        0.0,
        color=style.COLORS["threshold"],
        linewidth=style.THIN_LINE_WIDTH,
    )
    ax.set_xlabel("Time since AOS [min]")
    ax.set_ylabel("Doppler shift [kHz]")
    ax.set_xlim(minutes[0], minutes[-1])
    ax.set_title(
        f"Doppler at {detail.downlink_hz / 1e9:.3f} GHz "
        f"(max ±{detail.max_doppler_hz / 1e3:.1f} kHz)"
    )
    return fig


@style.styled
def plot_sky_track(detail: PassDetail, ax: Axes | None = None) -> Figure:
    """Polar sky plot as the antenna sees it: north up, east right,
    zenith in the centre, horizon at the rim."""
    fig, ax = _new_axes(ax, "square", polar=True)
    if not isinstance(ax, PolarAxes):
        raise TypeError("plot_sky_track needs a polar Axes")

    azimuth = np.radians(detail.azimuth_deg)
    zenith_distance = 90.0 - detail.elevation_deg

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.plot(azimuth, zenith_distance, color=style.COLORS["primary"])
    ax.plot(
        azimuth[0],
        zenith_distance[0],
        marker="o",
        linestyle="none",
        color=style.COLORS["accent"],
        label="AOS",
    )
    ax.plot(
        azimuth[-1],
        zenith_distance[-1],
        marker="s",
        linestyle="none",
        color=style.COLORS["secondary"],
        label="LOS",
    )
    ax.set_rlim(0, 90)
    ax.set_rticks([0, 30, 60, 90])
    ax.set_yticklabels(["90°", "60°", "30°", "0°"])
    ax.set_xticks(np.radians([0, 90, 180, 270]))
    ax.set_xticklabels(["N", "E", "S", "W"])
    ax.set_rlabel_position(112.5)  # keep ring labels off the N axis
    ax.set_title("Sky track", pad=18)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2)
    return fig


@style.styled
def plot_pass_overview(detail: PassDetail) -> Figure:
    """Elevation and Doppler on the left, sky track on the right."""
    fig = plt.figure(figsize=style.FIGSIZE["overview"])
    grid = fig.add_gridspec(2, 2, width_ratios=[1.6, 1.0])
    plot_elevation(detail, ax=fig.add_subplot(grid[0, 0]))
    plot_doppler(detail, ax=fig.add_subplot(grid[1, 0]))
    plot_sky_track(detail, ax=fig.add_subplot(grid[:, 1], projection="polar"))
    fig.suptitle(_title(detail), fontsize=style.FONT_SIZE["title"])
    return fig
