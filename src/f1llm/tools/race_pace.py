from dataclasses import dataclass
from datetime import date

from f1llm.charts import dark_layout
from f1llm.errors import SessionDataUnavailable
from f1llm.track_status import (
    SafetyCarPeriod,
    safety_car_band_shapes,
    safety_car_legend_entries,
    safety_car_periods,
)

# Qualifying has no race distance to accumulate lap times over.
SUPPORTED_SESSION_TYPES = {"Race", "Sprint"}
MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class DriverPace:
    driver_code: str
    position: int | None
    team_name: str | None
    team_color: str | None  # "#RRGGBB"
    # Index 0 is lap 1; a driver's laps are contiguous, so the list simply ends on retirement.
    # Positive = ahead of the reference driver (see "Ritmo de corrida" in CONTEXT.md).
    gaps_to_reference: list[float]
    pit_out_laps: list[int]


@dataclass(frozen=True)
class RacePaceResponse:
    found: bool
    event_name: str | None = None
    drivers: list[DriverPace] | None = None
    safety_car_periods: list[SafetyCarPeriod] | None = None
    reason: str | None = None


def get_race_pace(
    *,
    year: int,
    event: str,
    session_type: str,
    drivers: list[str] | None = None,
    load_race_pace_data=None,
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
        raise ValueError("drivers must be None (all drivers) or contain at least one driver code")

    try:
        data = load_race_pace_data(year, event, session_type)
    except SessionDataUnavailable as exc:
        return RacePaceResponse(found=False, reason=str(exc))

    results_by_driver = {row["Abbreviation"]: row for row in data["results"]}

    laps_by_driver: dict[str, list[dict]] = {}
    for row in sorted(data["laps"], key=lambda row: row["LapNumber"]):
        laps_by_driver.setdefault(row["Driver"], []).append(row)

    elapsed_by_driver = {
        driver_code: [(row["Time"] - data["race_start"]).total_seconds() for row in rows]
        for driver_code, rows in laps_by_driver.items()
    }

    reference_elapsed = _reference_elapsed(elapsed_by_driver)

    driver_paces = [
        DriverPace(
            driver_code=driver_code,
            position=_final_position(results_by_driver.get(driver_code)),
            team_name=results_by_driver.get(driver_code, {}).get("TeamName"),
            team_color=_team_color(results_by_driver.get(driver_code)),
            gaps_to_reference=[
                reference_elapsed[index] - driver_elapsed
                for index, driver_elapsed in enumerate(elapsed)
            ],
            pit_out_laps=_pit_out_laps(laps_by_driver[driver_code]),
        )
        for driver_code, elapsed in elapsed_by_driver.items()
        if drivers is None or driver_code in drivers
    ]

    driver_paces.sort(key=lambda d: (d.position is None, d.position or 0))

    if not driver_paces:
        return RacePaceResponse(
            found=False,
            reason=f"No lap data found for drivers {drivers} in {event} {year} {session_type}",
        )

    return RacePaceResponse(
        found=True,
        event_name=data["event_name"],
        drivers=driver_paces,
        safety_car_periods=safety_car_periods(data["laps"]),
    )


def _final_position(result_row: dict | None) -> int | None:
    if result_row is None or result_row["Position"] is None:
        return None
    return int(result_row["Position"])


def _team_color(result_row: dict | None) -> str | None:
    # FastF1 gives the team color as bare hex digits, e.g. "0600EF".
    if result_row is None or not result_row["TeamColor"]:
        return None
    return f"#{result_row['TeamColor']}"


def _reference_elapsed(elapsed_by_driver: dict[str, list[float]]) -> list[float]:
    """Cumulative time of a fictitious driver who does, on every lap, the average lap time
    of the drivers still on the leader's lap."""
    # The leader ends lap N+1 first; anyone ending lap N after that has been lapped.
    leader_lap_end = [
        min(elapsed[index] for elapsed in elapsed_by_driver.values() if len(elapsed) > index)
        for index in range(max(len(elapsed) for elapsed in elapsed_by_driver.values()))
    ]

    lap_times_by_lap: dict[int, list[float]] = {}
    for elapsed in elapsed_by_driver.values():
        previous = 0.0
        for index, lap_end in enumerate(elapsed):
            lapped = index + 1 < len(leader_lap_end) and lap_end > leader_lap_end[index + 1]
            if not lapped:
                lap_times_by_lap.setdefault(index, []).append(lap_end - previous)
            previous = lap_end

    reference: list[float] = []
    total = 0.0
    for index in sorted(lap_times_by_lap):
        lap_times = lap_times_by_lap[index]
        total += sum(lap_times) / len(lap_times)
        reference.append(total)
    return reference


def _pit_out_laps(rows: list[dict]) -> list[int]:
    """Laps on which a new Stint starts, i.e. the driver just left the pits."""
    return [
        int(row["LapNumber"])
        for previous, row in zip(rows, rows[1:])
        if row["Stint"] != previous["Stint"]
    ]


UNKNOWN_TEAM_COLOR = "#808080"
_LAP_MARKER_SIZE = 5
_PIT_OUT_MARKER_SIZE = 11


def build_race_pace_chart(result: RacePaceResponse, *, year: int, session_type: str) -> dict:
    # Drivers arrive in finishing order, so the first of each team seen is the one ahead.
    teams_seen: set[str] = set()
    dashes = []
    for driver in result.drivers:
        dashes.append("dash" if driver.team_name in teams_seen else "solid")
        if driver.team_name is not None:
            teams_seen.add(driver.team_name)

    return {
        "data": [
            {
                "type": "scatter",
                "mode": "lines+markers",
                "name": driver.driver_code,
                # Lap 0 is the start, where every driver is level with the reference.
                "x": list(range(len(driver.gaps_to_reference) + 1)),
                "y": [0.0] + driver.gaps_to_reference,
                "line": {"color": driver.team_color or UNKNOWN_TEAM_COLOR, "dash": dash},
                "marker": {
                    "symbol": [
                        "circle-open" if lap in driver.pit_out_laps else "circle"
                        for lap in range(len(driver.gaps_to_reference) + 1)
                    ],
                    "size": [
                        _PIT_OUT_MARKER_SIZE if lap in driver.pit_out_laps else _LAP_MARKER_SIZE
                        for lap in range(len(driver.gaps_to_reference) + 1)
                    ],
                },
            }
            for driver, dash in zip(result.drivers, dashes)
        ]
        + safety_car_legend_entries(result.safety_car_periods),
        "layout": dark_layout({
            "title": f"{year} {result.event_name} - {session_type}",
            "xaxis": {"title": "Volta", "showgrid": True},
            "yaxis": {"title": "Diferença para a referência (s)", "showgrid": True},
            "shapes": safety_car_band_shapes(result.safety_car_periods),
        }),
    }
