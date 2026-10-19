from dataclasses import dataclass
from datetime import date

from f1llm.errors import SessionDataUnavailable

SUPPORTED_SESSION_TYPES = {"Race", "Qualifying", "Sprint"}
MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class DriverGapToPole:
    driver_code: str
    team_color: str | None
    lap_time_seconds: float
    gap_seconds: float


@dataclass(frozen=True)
class GapToPoleResponse:
    found: bool
    event_name: str | None = None
    drivers: list[DriverGapToPole] | None = None
    reason: str | None = None


def get_gap_to_pole(
    *,
    year: int,
    event: str,
    session_type: str,
    drivers: list[str] | None = None,
    load_gap_to_pole=None,
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
        data = load_gap_to_pole(year, event, session_type, drivers)
    except SessionDataUnavailable as exc:
        return GapToPoleResponse(found=False, reason=str(exc))

    ordered = sorted(data["drivers"], key=lambda row: row["lap_time"])
    pole_time = ordered[0]["lap_time"].total_seconds()

    driver_gaps = [
        DriverGapToPole(
            driver_code=row["driver_code"],
            team_color=f"#{row['team_color']}" if row["team_color"] else None,
            lap_time_seconds=row["lap_time"].total_seconds(),
            gap_seconds=round(row["lap_time"].total_seconds() - pole_time, 3),
        )
        for row in ordered
    ]

    return GapToPoleResponse(found=True, event_name=data["event_name"], drivers=driver_gaps)


def build_gap_to_pole_chart(result: GapToPoleResponse, *, year: int, session_type: str) -> dict:
    return {
        "data": [{
            "type": "bar",
            "orientation": "h",
            "y": [driver.driver_code for driver in result.drivers],
            "x": [driver.gap_seconds for driver in result.drivers],
            "marker": {"color": [driver.team_color for driver in result.drivers]},
        }],
        "layout": {
            "title": f"{year} {result.event_name} - {session_type} - Gap para a pole",
            "paper_bgcolor": "#ffffff",
            "plot_bgcolor": "#ffffff",
            "xaxis": {"title": "Gap (s)", "showgrid": True},
            "yaxis": {"autorange": "reversed"},
        },
    }
