from dataclasses import dataclass
from datetime import date

from f1llm.charts import dark_layout
from f1llm.errors import SessionDataUnavailable

SUPPORTED_SESSION_TYPES = {"Race", "Sprint"}
MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class PositionPoint:
    lap_number: int
    position: int


@dataclass(frozen=True)
class DriverPositions:
    driver_code: str
    team_color: str | None
    points: list[PositionPoint]


@dataclass(frozen=True)
class PositionChangesResponse:
    found: bool
    event_name: str | None = None
    drivers: list[DriverPositions] | None = None
    reason: str | None = None


def get_position_changes(
    *,
    year: int,
    event: str,
    session_type: str,
    drivers: list[str] | None = None,
    load_position_changes=None,
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

    if drivers is not None and not drivers:
        raise ValueError("drivers must be None (every driver) or contain at least one driver code")

    try:
        data = load_position_changes(year, event, session_type, drivers)
    except SessionDataUnavailable as exc:
        return PositionChangesResponse(found=False, reason=str(exc))

    points_by_driver: dict[str, list[PositionPoint]] = {}
    colors_by_driver: dict[str, str | None] = {}
    for row in data["laps"]:
        driver = row["Driver"]
        points_by_driver.setdefault(driver, []).append(
            PositionPoint(lap_number=int(row["LapNumber"]), position=int(row["Position"]))
        )
        colors_by_driver[driver] = f"#{row['TeamColor']}" if row["TeamColor"] else None

    driver_positions = [
        DriverPositions(driver_code=driver, team_color=colors_by_driver[driver], points=points)
        for driver, points in points_by_driver.items()
    ]

    return PositionChangesResponse(found=True, event_name=data["event_name"], drivers=driver_positions)


def build_position_changes_chart(result: PositionChangesResponse, *, year: int, session_type: str) -> dict:
    return {
        "data": [
            {
                "type": "scatter",
                "mode": "lines",
                "name": driver.driver_code,
                "x": [point.lap_number for point in driver.points],
                "y": [point.position for point in driver.points],
                "line": {"color": driver.team_color},
            }
            for driver in result.drivers
        ],
        "layout": dark_layout({
            "title": f"{year} {result.event_name} - {session_type} - Posição por volta",
            "xaxis": {"title": "Volta", "showgrid": True},
            "yaxis": {"title": "Posição", "showgrid": True, "autorange": "reversed"},
        }),
    }
