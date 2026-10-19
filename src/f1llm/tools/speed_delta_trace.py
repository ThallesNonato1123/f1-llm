from dataclasses import dataclass
from datetime import date

from f1llm.charts import dark_layout
from f1llm.errors import SessionDataUnavailable
from f1llm.tools.telemetry import DRIVER_COLORS

SUPPORTED_SESSION_TYPES = {"Race", "Qualifying", "Sprint"}
MIN_SUPPORTED_YEAR = 2018
REQUIRED_DRIVER_COUNT = 2


@dataclass(frozen=True)
class SpeedTracePoint:
    distance: float
    speed: float


@dataclass(frozen=True)
class DeltaPoint:
    distance: float
    seconds: float


@dataclass(frozen=True)
class Corner:
    number: int
    distance: float


@dataclass(frozen=True)
class DriverSpeedTrace:
    driver_code: str
    points: list[SpeedTracePoint]


@dataclass(frozen=True)
class SpeedDeltaTraceResponse:
    found: bool
    event_name: str | None = None
    drivers: list[DriverSpeedTrace] | None = None
    delta: list[DeltaPoint] | None = None
    corners: list[Corner] | None = None
    reason: str | None = None


def get_speed_delta_trace(
    *,
    year: int,
    event: str,
    session_type: str,
    drivers: list[str],
    laps: dict[str, int] | None = None,
    load_speed_delta_trace=None,
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

    if len(drivers) != REQUIRED_DRIVER_COUNT:
        raise ValueError(
            f"drivers must contain exactly {REQUIRED_DRIVER_COUNT} driver codes "
            f"(the delta is a comparison between a pair); got {drivers!r}"
        )

    try:
        data = load_speed_delta_trace(year, event, session_type, drivers, laps)
    except SessionDataUnavailable as exc:
        return SpeedDeltaTraceResponse(found=False, reason=str(exc))

    driver_traces = [
        DriverSpeedTrace(
            driver_code=entry["driver_code"],
            points=[
                SpeedTracePoint(distance=d, speed=s)
                for d, s in zip(entry["distance"], entry["speed"])
            ],
        )
        for entry in data["drivers"]
    ]

    delta_points = [
        DeltaPoint(distance=d, seconds=s)
        for d, s in zip(data["delta"]["distance"], data["delta"]["seconds"])
    ]

    corners = [Corner(number=c["number"], distance=c["distance"]) for c in data["corners"]]

    return SpeedDeltaTraceResponse(
        found=True,
        event_name=data["event_name"],
        drivers=driver_traces,
        delta=delta_points,
        corners=corners,
    )


def build_speed_delta_trace_chart(result: SpeedDeltaTraceResponse, *, year: int, session_type: str) -> dict:
    data = [
        {
            "type": "scatter",
            "mode": "lines",
            "name": driver.driver_code,
            "x": [point.distance for point in driver.points],
            "y": [point.speed for point in driver.points],
            "line": {"color": DRIVER_COLORS[index % len(DRIVER_COLORS)]},
        }
        for index, driver in enumerate(result.drivers)
    ]
    data.append({
        "type": "scatter",
        "mode": "lines",
        "name": "Delta",
        "x": [point.distance for point in result.delta],
        "y": [point.seconds for point in result.delta],
        "line": {"color": "#ffffff", "dash": "dash"},
        "yaxis": "y2",
    })

    layout = dark_layout({
        "title": f"{year} {result.event_name} - {session_type} - Traço de velocidade com delta",
        "xaxis": {"title": "Distância (m)", "showgrid": True},
        "yaxis": {"title": "Velocidade (km/h)", "showgrid": True},
        "yaxis2": {"title": "Delta (s)", "overlaying": "y", "side": "right"},
        "shapes": [_corner_line_shape(corner) for corner in result.corners],
        "annotations": [_corner_number_annotation(corner) for corner in result.corners],
    })

    return {"data": data, "layout": layout}


def _corner_line_shape(corner: Corner) -> dict:
    return {
        "type": "line",
        "xref": "x", "yref": "paper",
        "x0": corner.distance, "x1": corner.distance, "y0": 0, "y1": 1,
        "line": {"color": "#555555", "dash": "dot"},
    }


def _corner_number_annotation(corner: Corner) -> dict:
    return {
        "text": str(corner.number),
        "xref": "x", "yref": "paper",
        "x": corner.distance, "y": 1.0,
        "showarrow": False,
        "yanchor": "bottom",
    }
