from dataclasses import dataclass
from datetime import date

from f1llm.charts import BACKGROUND_COLOR, dark_layout
from f1llm.errors import SessionDataUnavailable
from f1llm.track_status import (
    SafetyCarPeriod,
    legend_entry,
    safety_car_band_shapes,
    safety_car_legend_entries,
    safety_car_periods,
)

SUPPORTED_SESSION_TYPES = {"Race", "Qualifying", "Sprint"}
# Since 2019 compound names (SOFT/MEDIUM/HARD) are relative to each Grand Prix;
# 2018 used absolute names with a different color scheme, so it is out of scope.
MIN_SUPPORTED_YEAR = 2019


@dataclass(frozen=True)
class Stint:
    number: int
    compound: str
    start_lap: int
    end_lap: int
    lap_count: int
    fresh: bool | None
    tyre_age_at_start: int | None


@dataclass(frozen=True)
class DriverStints:
    driver_code: str
    position: int | None
    stints: list[Stint]


@dataclass(frozen=True)
class StintsResponse:
    found: bool
    event_name: str | None = None
    drivers: list[DriverStints] | None = None
    safety_car_periods: list[SafetyCarPeriod] | None = None
    reason: str | None = None


def get_stints(
    *,
    year: int,
    event: str,
    session_type: str,
    drivers: list[str] | None = None,
    load_stint_data=None,
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
        data = load_stint_data(year, event, session_type)
    except SessionDataUnavailable as exc:
        return StintsResponse(found=False, reason=str(exc))

    positions = {
        row["Abbreviation"]: int(row["Position"])
        for row in data["results"]
        if row["Position"] is not None
    }

    laps_by_driver_and_stint: dict[str, dict[int, list[dict]]] = {}
    for row in data["laps"]:
        if drivers is not None and row["Driver"] not in drivers:
            continue
        laps_by_driver_and_stint.setdefault(row["Driver"], {}).setdefault(
            int(row["Stint"]), []
        ).append(row)

    if not laps_by_driver_and_stint:
        return StintsResponse(
            found=False,
            reason=f"No stint data found for drivers {drivers} in {event} {year} {session_type}",
        )

    driver_stints = [
        DriverStints(
            driver_code=driver_code,
            position=positions.get(driver_code),
            stints=[_build_stint(number, rows) for number, rows in stints.items()],
        )
        for driver_code, stints in laps_by_driver_and_stint.items()
    ]
    driver_stints.sort(key=lambda d: (d.position is None, d.position or 0))

    return StintsResponse(
        found=True,
        event_name=data["event_name"],
        drivers=driver_stints,
        safety_car_periods=safety_car_periods(data["laps"]),
    )


def _build_stint(number: int, rows: list[dict]) -> Stint:
    first, last = rows[0], rows[-1]
    return Stint(
        number=number,
        compound=first["Compound"] or "UNKNOWN",
        start_lap=int(first["LapNumber"]),
        end_lap=int(last["LapNumber"]),
        lap_count=len(rows),
        fresh=first["FreshTyre"],
        tyre_age_at_start=None if first["TyreLife"] is None else int(first["TyreLife"]) - 1,
    )


# Official Pirelli sidewall colors (see "Composto de pneu" in CONTEXT.md).
COMPOUND_COLORS = {
    "SOFT": "#DA291C",
    "MEDIUM": "#FFD12E",
    "HARD": "#F0F0EC",
    "INTERMEDIATE": "#43B02A",
    "WET": "#0067AD",
}
UNKNOWN_COMPOUND_COLOR = "#808080"

# Plotly bar pattern shapes: solid for a Pneu novo, hatched for a Pneu usado,
# dotted when FastF1 does not know whether the set was new.
_FRESHNESS_PATTERNS = {True: "", False: "/", None: "."}

_FRESHNESS_LEGEND_NAMES = {True: "Pneu novo", False: "Pneu usado", None: "Desconhecido"}
_LEGEND_SWATCH_COLOR = "#BBBBBB"
_COMPOUND_NAMES_PT = {
    "SOFT": "Macio",
    "MEDIUM": "Médio",
    "HARD": "Duro",
    "INTERMEDIATE": "Intermediário",
    "WET": "Chuva",
}


def build_stints_chart(result: StintsResponse, *, year: int, session_type: str) -> dict:
    stint_bars = [
        {
            "type": "bar",
            "orientation": "h",
            "showlegend": False,
            "y": [driver.driver_code],
            "base": [stint.start_lap - 1],
            "x": [stint.lap_count],
            "marker": {
                "color": COMPOUND_COLORS.get(stint.compound, UNKNOWN_COMPOUND_COLOR),
                "pattern": {"shape": _FRESHNESS_PATTERNS[stint.fresh]},
                # A background-colored outline leaves a gap between adjacent stints.
                "line": {"color": BACKGROUND_COLOR, "width": 2},
            },
            "hovertemplate": _stint_hover_text(driver.driver_code, stint),
        }
        for driver in result.drivers
        for stint in driver.stints
    ]

    # Legend-only traces: an empty bar per band kind and tyre style actually present.
    freshness_values = [
        f for f in _FRESHNESS_LEGEND_NAMES
        if any(stint.fresh is f for driver in result.drivers for stint in driver.stints)
    ]
    legend_entries = safety_car_legend_entries(result.safety_car_periods) + [
        legend_entry(
            _FRESHNESS_LEGEND_NAMES[fresh],
            {"color": _LEGEND_SWATCH_COLOR, "pattern": {"shape": _FRESHNESS_PATTERNS[fresh]}},
        )
        for fresh in freshness_values
    ]

    return {
        "data": stint_bars + legend_entries,
        "layout": dark_layout({
            "title": f"{year} {result.event_name} - {session_type}",
            "barmode": "overlay",
            "xaxis": {"title": "Volta", "showgrid": True},
            "yaxis": {
                "showgrid": True,
                "categoryorder": "array",
                "categoryarray": [driver.driver_code for driver in result.drivers],
                "autorange": "reversed",
            },
            "shapes": safety_car_band_shapes(result.safety_car_periods),
        }),
    }


def _stint_hover_text(driver_code: str, stint: Stint) -> str:
    compound = _COMPOUND_NAMES_PT.get(stint.compound, "Desconhecido")
    freshness = _FRESHNESS_LEGEND_NAMES[stint.fresh]
    if stint.start_lap == stint.end_lap:
        laps = f"Volta {stint.start_lap}"
    else:
        laps = f"Voltas {stint.start_lap}–{stint.end_lap}"
    age = "desconhecida" if stint.tyre_age_at_start is None else _laps(stint.tyre_age_at_start)
    return (
        f"{driver_code}<br>{compound} · {freshness}<br>"
        f"{laps} ({_laps(stint.lap_count)})<br>Idade no início: {age}<extra></extra>"
    )


def _laps(count: int) -> str:
    return f"{count} volta" if count == 1 else f"{count} voltas"
