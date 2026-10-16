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
class DriverGap:
    driver_code: str
    position: int | None
    team_name: str | None
    team_color: str | None  # "#RRGGBB"
    # Index 0 is lap 1. Positive = ahead of the winner, so always <= 0 except for
    # the winner's own (all-zero) line.
    gaps_to_winner: list[float]
    pit_out_laps: list[int]


@dataclass(frozen=True)
class GapToWinnerResponse:
    found: bool
    event_name: str | None = None
    drivers: list[DriverGap] | None = None
    safety_car_periods: list[SafetyCarPeriod] | None = None
    reason: str | None = None


def get_gap_to_winner(
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

    try:
        data = load_race_pace_data(year, event, session_type)
    except SessionDataUnavailable as exc:
        return GapToWinnerResponse(found=False, reason=str(exc))

    results_by_driver = {row["Abbreviation"]: row for row in data["results"]}

    laps_by_driver: dict[str, list[dict]] = {}
    for row in sorted(data["laps"], key=lambda row: row["LapNumber"]):
        laps_by_driver.setdefault(row["Driver"], []).append(row)

    elapsed_by_driver = {
        driver_code: [(row["Time"] - data["race_start"]).total_seconds() for row in rows]
        for driver_code, rows in laps_by_driver.items()
    }

    winner_code = next(
        (code for code, row in results_by_driver.items() if row["Position"] == 1.0), None
    )
    if winner_code is None or winner_code not in elapsed_by_driver:
        return GapToWinnerResponse(
            found=False,
            reason=f"No classified winner found for {event} {year} {session_type}",
        )
    winner_elapsed = elapsed_by_driver[winner_code]

    selected_codes = (
        set(drivers) if drivers is not None
        else _top_n_codes(elapsed_by_driver.keys(), results_by_driver, n=6)
    )

    driver_gaps = [
        DriverGap(
            driver_code=driver_code,
            position=_final_position(results_by_driver.get(driver_code)),
            team_name=results_by_driver.get(driver_code, {}).get("TeamName"),
            team_color=_team_color(results_by_driver.get(driver_code)),
            gaps_to_winner=[
                winner_elapsed[index] - driver_elapsed
                for index, driver_elapsed in enumerate(elapsed)
            ],
            pit_out_laps=_pit_out_laps(laps_by_driver[driver_code]),
        )
        for driver_code, elapsed in elapsed_by_driver.items()
        if driver_code in selected_codes
    ]
    driver_gaps.sort(key=lambda d: (d.position is None, d.position or 0))

    return GapToWinnerResponse(
        found=True,
        event_name=data["event_name"],
        drivers=driver_gaps,
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


UNKNOWN_TEAM_COLOR = "#808080"
_LAP_MARKER_SIZE = 5
_PIT_OUT_MARKER_SIZE = 11


def build_gap_to_winner_chart(result: GapToWinnerResponse, *, year: int, session_type: str) -> dict:
    # The winner's own line is flat at 0, so position 1 identifies them unambiguously.
    winner = next((driver for driver in result.drivers if driver.position == 1), None)
    winner_pit_laps = winner.pit_out_laps if winner is not None else []

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
                "x": list(range(len(driver.gaps_to_winner) + 1)),
                "y": [0.0] + driver.gaps_to_winner,
                "line": {"color": driver.team_color or UNKNOWN_TEAM_COLOR, "dash": dash},
                "marker": {
                    "symbol": [
                        "circle-open" if lap in driver.pit_out_laps else "circle"
                        for lap in range(len(driver.gaps_to_winner) + 1)
                    ],
                    "size": [
                        _PIT_OUT_MARKER_SIZE if lap in driver.pit_out_laps else _LAP_MARKER_SIZE
                        for lap in range(len(driver.gaps_to_winner) + 1)
                    ],
                },
            }
            for driver, dash in zip(result.drivers, dashes)
        ]
        + safety_car_legend_entries(result.safety_car_periods),
        "layout": dark_layout({
            "title": f"{year} {result.event_name} - {session_type}",
            "xaxis": {"title": "Volta", "showgrid": True},
            "yaxis": {"title": "Gap para o vencedor (s)", "showgrid": True},
            "legend": {"x": 0, "y": 0, "xanchor": "left", "yanchor": "bottom"},
            "shapes": safety_car_band_shapes(result.safety_car_periods) + [
                {
                    "type": "line",
                    "xref": "x",
                    "yref": "paper",
                    "x0": lap, "x1": lap,
                    "y0": 0, "y1": 1,
                    "line": {"color": "white", "dash": "dash", "width": 1},
                }
                for lap in winner_pit_laps
            ],
            "annotations": [
                {
                    "x": lap,
                    "y": 1,
                    "yref": "paper",
                    "text": f"{winner.driver_code} pits",
                    "showarrow": False,
                    "yanchor": "bottom",
                }
                for lap in winner_pit_laps
            ],
        }),
    }


def _pit_out_laps(rows: list[dict]) -> list[int]:
    """Laps on which a new Stint starts, i.e. the driver just left the pits."""
    return [
        int(row["LapNumber"])
        for previous, row in zip(rows, rows[1:])
        if row["Stint"] != previous["Stint"]
    ]


def _top_n_codes(codes, results_by_driver: dict[str, dict], *, n: int) -> set[str]:
    ranked = sorted(codes, key=lambda code: (_final_position(results_by_driver.get(code)) is None,
                                              _final_position(results_by_driver.get(code)) or 0))
    return set(ranked[:n])
