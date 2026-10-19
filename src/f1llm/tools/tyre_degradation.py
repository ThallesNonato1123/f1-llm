from dataclasses import dataclass
from datetime import date

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.stints import COMPOUND_NAMES_PT
from f1llm.track_status import neutralization_kind

SUPPORTED_SESSION_TYPES = {"Race", "Sprint"}
# Since 2019 compound names (SOFT/MEDIUM/HARD) are relative to each Grand Prix;
# 2018 used absolute names with a different color scheme, so it is out of scope.
MIN_SUPPORTED_YEAR = 2019
DRY_COMPOUNDS = {"SOFT", "MEDIUM", "HARD"}

# ADR 0005: FastF1 doesn't expose real fuel load, so lap times are corrected
# against a fixed linear burn model instead of a measured value.
STARTING_FUEL_KG = 110
FUEL_EFFECT_SECONDS_PER_KG = 0.03

DEFAULT_TEAM_COUNT = 4


@dataclass(frozen=True)
class TyreDegradationPoint:
    tyre_age: int
    fuel_corrected_lap_time: float


@dataclass(frozen=True)
class TeamCompoundDegradation:
    team: str
    compound: str
    team_color: str | None  # "#RRGGBB"
    points: list[TyreDegradationPoint]
    slope: float | None
    r_squared: float | None


@dataclass(frozen=True)
class TyreDegradationResponse:
    found: bool
    event_name: str | None = None
    entries: list[TeamCompoundDegradation] | None = None
    reason: str | None = None


def get_tyre_degradation(
    *,
    year: int,
    event: str,
    session_type: str,
    teams: list[str] | None = None,
    load_tyre_degradation=None,
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

    if teams is not None and not teams:
        raise ValueError("teams must be None (top 4) or contain at least one team")

    try:
        data = load_tyre_degradation(year, event, session_type)
    except SessionDataUnavailable as exc:
        return TyreDegradationResponse(found=False, reason=str(exc))

    selected_teams = teams if teams is not None else _top_teams_by_best_driver_position(data["results"])

    total_laps = max(int(row["LapNumber"]) for row in data["laps"])

    points_by_team_compound: dict[tuple[str, str], list[TyreDegradationPoint]] = {}
    for row in data["laps"]:
        team = row["Team"]
        if team not in selected_teams:
            continue
        if row["Compound"] not in DRY_COMPOUNDS:
            continue

        tyre_life = row["TyreLife"]
        lap_number = int(row["LapNumber"])
        if tyre_life is None or tyre_life <= 1 or lap_number <= 1:
            continue
        if row["PitInTime"] is not None or row["PitOutTime"] is not None:
            continue
        if neutralization_kind(row["TrackStatus"] or "") is not None:
            continue

        fuel_remaining = STARTING_FUEL_KG - lap_number * (STARTING_FUEL_KG / total_laps)
        fuel_corrected_lap_time = row["LapTime"].total_seconds() - FUEL_EFFECT_SECONDS_PER_KG * fuel_remaining

        point = TyreDegradationPoint(tyre_age=int(tyre_life) - 1, fuel_corrected_lap_time=fuel_corrected_lap_time)
        points_by_team_compound.setdefault((team, row["Compound"]), []).append(point)

    if not points_by_team_compound:
        return TyreDegradationResponse(
            found=False,
            reason=f"No dry-compound clean laps found in {event} {year} {session_type}",
        )

    team_colors = _team_colors_by_team(data["results"])

    entries = []
    for (team, compound), points in points_by_team_compound.items():
        slope, r_squared = _fit_trend_line(points)
        entries.append(
            TeamCompoundDegradation(
                team=team,
                compound=compound,
                team_color=team_colors.get(team),
                points=points,
                slope=slope,
                r_squared=r_squared,
            )
        )

    return TyreDegradationResponse(found=True, event_name=data["event_name"], entries=entries)


def _team_colors_by_team(results: list[dict]) -> dict[str, str]:
    # FastF1 gives the team color as bare hex digits, e.g. "0600EF".
    return {row["Team"]: f"#{row['TeamColor']}" for row in results if row["TeamColor"]}


def _top_teams_by_best_driver_position(results: list[dict]) -> list[str]:
    best_position_by_team: dict[str, float] = {}
    for row in results:
        position = row["Position"]
        if position is None:
            continue
        team = row["Team"]
        if team not in best_position_by_team or position < best_position_by_team[team]:
            best_position_by_team[team] = position

    ranked_teams = sorted(best_position_by_team, key=lambda team: best_position_by_team[team])
    return ranked_teams[:DEFAULT_TEAM_COUNT]


_MIN_POINTS_FOR_TREND_LINE = 3


def _fit_trend_line(points: list[TyreDegradationPoint]) -> tuple[float | None, float | None]:
    if len(points) < _MIN_POINTS_FOR_TREND_LINE:
        return None, None

    xs = [point.tyre_age for point in points]
    ys = [point.fuel_corrected_lap_time for point in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)

    s_xx = sum((x - mean_x) ** 2 for x in xs)
    s_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = s_xy / s_xx
    intercept = mean_y - slope * mean_x

    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_squared = 1 - ss_res / ss_tot

    return slope, r_squared


# Left to right, matching the spec's subplot order.
_COMPOUND_AXES = {
    "HARD": ("x", "y"),
    "MEDIUM": ("x2", "y2"),
    "SOFT": ("x3", "y3"),
}


def build_tyre_degradation_chart(result: TyreDegradationResponse, *, year: int, session_type: str) -> dict:
    data = []
    teams_in_legend = set()
    for entry in result.entries:
        xaxis, yaxis = _COMPOUND_AXES[entry.compound]
        data.append({
            "type": "scatter",
            "mode": "markers",
            "name": entry.team,
            "legendgroup": entry.team,
            "showlegend": entry.team not in teams_in_legend,
            "x": [point.tyre_age for point in entry.points],
            "y": [point.fuel_corrected_lap_time for point in entry.points],
            "xaxis": xaxis,
            "yaxis": yaxis,
            "marker": {"color": entry.team_color},
        })
        teams_in_legend.add(entry.team)
        if entry.slope is not None:
            x0, x1 = _trend_line_x_range(entry.points)
            intercept = _trend_line_intercept(entry.points, entry.slope)
            data.append({
                "type": "scatter",
                "mode": "lines",
                "name": entry.team,
                "legendgroup": entry.team,
                "x": [x0, x1],
                "y": [entry.slope * x0 + intercept, entry.slope * x1 + intercept],
                "xaxis": xaxis,
                "yaxis": yaxis,
                "line": {"color": entry.team_color},
                "showlegend": False,
            })

    all_lap_times = [point.fuel_corrected_lap_time for entry in result.entries for point in entry.points]
    y_range = [min(all_lap_times), max(all_lap_times)]

    layout = {
        "title": f"{year} {result.event_name} - {session_type} - Degradação de pneu",
        "paper_bgcolor": "#ffffff",
        "plot_bgcolor": "#ffffff",
        "legend": {"title": {"text": "Equipe"}},
        "xaxis": {"domain": [0.0, 0.3], "title": "Idade do pneu (voltas)", "showgrid": True},
        "xaxis2": {"domain": [0.35, 0.65], "title": "Idade do pneu (voltas)", "showgrid": True},
        "xaxis3": {"domain": [0.7, 1.0], "title": "Idade do pneu (voltas)", "showgrid": True},
        "yaxis": {"title": "Tempo de volta corrigido por combustível (s)", "showgrid": True, "range": y_range},
        "yaxis2": {"showgrid": True, "range": y_range, "anchor": "x2"},
        "yaxis3": {"showgrid": True, "range": y_range, "anchor": "x3"},
        "annotations": [
            {
                "text": COMPOUND_NAMES_PT[compound],
                "xref": f"{xref} domain", "yref": "paper",
                "x": 0.5, "y": 1.05,
                "showarrow": False,
            }
            for compound, (xref, _yaxis) in _COMPOUND_AXES.items()
        ],
    }

    return {"data": data, "layout": layout}


def _trend_line_x_range(points: list[TyreDegradationPoint]) -> tuple[int, int]:
    ages = [point.tyre_age for point in points]
    return min(ages), max(ages)


def _trend_line_intercept(points: list[TyreDegradationPoint], slope: float) -> float:
    mean_x = sum(point.tyre_age for point in points) / len(points)
    mean_y = sum(point.fuel_corrected_lap_time for point in points) / len(points)
    return mean_y - slope * mean_x
