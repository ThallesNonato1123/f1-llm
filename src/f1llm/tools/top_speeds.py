from dataclasses import dataclass
from datetime import date

from f1llm.errors import SessionDataUnavailable

SUPPORTED_SESSION_TYPES = {"Race", "Qualifying", "Sprint"}
MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class DriverTopSpeeds:
    driver_code: str
    # Sorted descending; the driver's fastest laps by top speed, up to 15 of them.
    top_speeds: list[float]
    average: float


@dataclass(frozen=True)
class TopSpeedsResponse:
    found: bool
    event_name: str | None = None
    drivers: list[DriverTopSpeeds] | None = None
    session_max: float | None = None
    reason: str | None = None


def get_top_speeds(
    *,
    year: int,
    event: str,
    session_type: str,
    drivers: list[str] | None = None,
    load_top_speeds=None,
):
    if session_type not in SUPPORTED_SESSION_TYPES:
        raise ValueError(
            f"Unsupported session_type {session_type!r}; "
            f"expected one of {sorted(SUPPORTED_SESSION_TYPES)}"
        )

    current_year = date.today().year
    if not (MIN_SUPPORTED_YEAR <= year <= current_year):
        raise ValueError(
            f"Unsupported year {year!r}; "
            f"expected between {MIN_SUPPORTED_YEAR} and {current_year}"
        )

    try:
        data = load_top_speeds(year, event, session_type, drivers)
    except SessionDataUnavailable as exc:
        return TopSpeedsResponse(found=False, reason=str(exc))

    speeds_by_driver: dict[str, list[float]] = {}
    for row in data["rows"]:
        speeds_by_driver.setdefault(row["Driver"], []).append(row["TopSpeed"])

    driver_top_speeds = []
    for driver_code, speeds in speeds_by_driver.items():
        top_15 = sorted(speeds, reverse=True)[:15]
        driver_top_speeds.append(
            DriverTopSpeeds(driver_code=driver_code, top_speeds=top_15, average=sum(top_15) / len(top_15))
        )
    driver_top_speeds.sort(key=lambda d: d.top_speeds[0], reverse=True)

    return TopSpeedsResponse(
        found=True,
        event_name=data["event_name"],
        drivers=driver_top_speeds,
        session_max=max(speed for speeds in speeds_by_driver.values() for speed in speeds),
    )


_COLUMN_COUNT = 15
_DRIVER_COLUMN_COLOR = "#e6e6e6"
_SESSION_MAX_HIGHLIGHT_COLOR = "#fff59d"

# Dark purple -> magenta -> orange -> yellow, approximating Plotly's "Plasma".
_PLASMA_STOPS = [
    (0.00, (13, 8, 135)),
    (0.25, (126, 3, 168)),
    (0.50, (204, 71, 120)),
    (0.75, (248, 148, 65)),
    (1.00, (240, 249, 33)),
]


def _plasma_color(value: float, vmin: float, vmax: float) -> str:
    t = 0.5 if vmax == vmin else (value - vmin) / (vmax - vmin)
    t = min(1.0, max(0.0, t))
    for (t0, rgb0), (t1, rgb1) in zip(_PLASMA_STOPS, _PLASMA_STOPS[1:]):
        if t0 <= t <= t1:
            span = t1 - t0
            fraction = 0.0 if span == 0 else (t - t0) / span
            rgb = tuple(round(a + (b - a) * fraction) for a, b in zip(rgb0, rgb1))
            return "#{:02x}{:02x}{:02x}".format(*rgb)
    return "#{:02x}{:02x}{:02x}".format(*_PLASMA_STOPS[-1][1])


def build_top_speeds_chart(result: TopSpeedsResponse, *, year: int, session_type: str) -> dict:
    driver_column = [driver.driver_code for driver in result.drivers]
    lap_columns = [
        [
            driver.top_speeds[lap_index] if lap_index < len(driver.top_speeds) else None
            for driver in result.drivers
        ]
        for lap_index in range(_COLUMN_COUNT)
    ]
    average_column = [driver.average for driver in result.drivers]

    all_speeds = [speed for driver in result.drivers for speed in driver.top_speeds]
    vmin, vmax = min(all_speeds), max(all_speeds)

    def colors_for(column):
        return [
            _DRIVER_COLUMN_COLOR if value is None
            else _SESSION_MAX_HIGHLIGHT_COLOR if value == result.session_max
            else _plasma_color(value, vmin, vmax)
            for value in column
        ]

    fill_colors = (
        [[_DRIVER_COLUMN_COLOR] * len(driver_column)]
        + [colors_for(column) for column in lap_columns]
        + [colors_for(average_column)]
    )

    display_lap_columns = [
        [None if value is None else f"{round(value)}" for value in column] for column in lap_columns
    ]
    display_average_column = [f"{value:.1f}" for value in average_column]

    return {
        "data": [{
            "type": "table",
            "header": {"values": ["Piloto"] + [str(n) for n in range(1, _COLUMN_COUNT + 1)] + ["Média"]},
            "cells": {
                "values": [driver_column] + display_lap_columns + [display_average_column],
                "fill": {"color": fill_colors},
            },
        }],
        "layout": {
            "title": f"{year} {result.event_name} - {session_type} - Velocidade máxima (km/h) por volta",
            "height": 110 + 28 * len(result.drivers),
            "paper_bgcolor": "#ffffff",
            "plot_bgcolor": "#ffffff",
            "annotations": [{
                "text": "Voltas ordenadas pela velocidade máxima (15 melhores exibidas, média à direita)",
                "showarrow": False,
                "xref": "paper", "yref": "paper",
                "x": 0.5, "y": -0.08,
            }],
        },
    }
