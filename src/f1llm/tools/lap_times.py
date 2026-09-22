from dataclasses import dataclass
from datetime import date

from f1llm.errors import SessionDataUnavailable

SUPPORTED_SESSION_TYPES = {"Race", "Qualifying", "Sprint"}
MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class LapTime:
    lap_number: int
    driver_code: str
    seconds: float | None
    formatted: str | None


@dataclass(frozen=True)
class LapTimesResponse:
    found: bool
    laps: list[LapTime] | None = None
    reason: str | None = None


def get_lap_times(
    *,
    year: int,
    event: str,
    session_type: str,
    drivers: list[str],
    load_laps=None,
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

    if not drivers:
        raise ValueError("drivers must contain at least one driver code")

    try:
        raw_rows = load_laps(year, event, session_type, drivers)
    except SessionDataUnavailable as exc:
        return LapTimesResponse(found=False, reason=str(exc))

    laps = [
        LapTime(
            lap_number=int(row["LapNumber"]),
            driver_code=row["Driver"],
            seconds=row["LapTime"].total_seconds() if row["LapTime"] is not None else None,
            formatted=str(row["LapTime"]) if row["LapTime"] is not None else None,
        )
        for row in raw_rows
    ]
    return LapTimesResponse(found=True, laps=laps)


def build_lap_times_chart(laps: list[LapTime]) -> dict:
    laps_by_driver: dict[str, list[LapTime]] = {}
    for lap in laps:
        if lap.seconds is None:
            continue
        laps_by_driver.setdefault(lap.driver_code, []).append(lap)

    return {
        "data": [
            {
                "type": "scatter",
                "mode": "lines+markers",
                "name": driver_code,
                "x": [lap.lap_number for lap in driver_laps],
                "y": [lap.seconds for lap in driver_laps],
            }
            for driver_code, driver_laps in laps_by_driver.items()
        ],
        "layout": {
            "xaxis": {"title": "Volta"},
            "yaxis": {"title": "Tempo de volta (s)"},
        },
    }
