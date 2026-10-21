from dataclasses import dataclass
from datetime import date

from f1llm.charts import dark_layout
from f1llm.errors import SessionDataUnavailable

SUPPORTED_SESSION_TYPES = {"Race", "Qualifying", "Sprint"}
MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class TeamSpeedPoint:
    team: str
    team_color: str | None
    mean_speed: float
    top_speed: float


@dataclass(frozen=True)
class SpeedQuadrantResponse:
    found: bool
    event_name: str | None = None
    teams: list[TeamSpeedPoint] | None = None
    reason: str | None = None


def get_speed_quadrant(
    *,
    year: int,
    event: str,
    session_type: str,
    teams: list[str] | None = None,
    load_speed_quadrant=None,
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
        raise ValueError("teams must be None (every team) or contain at least one team")

    try:
        data = load_speed_quadrant(year, event, session_type)
    except SessionDataUnavailable as exc:
        return SpeedQuadrantResponse(found=False, reason=str(exc))

    fastest_by_team: dict[str, dict] = {}
    for row in data["laps"]:
        team = row["Team"]
        current = fastest_by_team.get(team)
        if current is None or row["LapTime"] < current["LapTime"]:
            fastest_by_team[team] = row

    team_points = [
        TeamSpeedPoint(
            team=team,
            team_color=f"#{row['TeamColor']}" if row["TeamColor"] else None,
            mean_speed=row["LapDistance"] / row["LapTime"].total_seconds() * 3.6,
            top_speed=row["TopSpeed"],
        )
        for team, row in fastest_by_team.items()
        if teams is None or team in teams
    ]

    if not team_points:
        return SpeedQuadrantResponse(
            found=False,
            reason=f"No lap data found for teams {teams} in {event} {year} {session_type}",
        )

    return SpeedQuadrantResponse(found=True, event_name=data["event_name"], teams=team_points)


def build_speed_quadrant_chart(result: SpeedQuadrantResponse, *, year: int, session_type: str) -> dict:
    data = [{
        "type": "scatter",
        "mode": "markers+text",
        "x": [team.mean_speed for team in result.teams],
        "y": [team.top_speed for team in result.teams],
        "text": [team.team for team in result.teams],
        "textposition": "middle right",
        "marker": {"color": [team.team_color for team in result.teams], "size": 10},
        "showlegend": False,
    }]

    layout = dark_layout({
        "title": f"{year} {result.event_name} - {session_type} (Melhor volta de cada equipe)",
        "xaxis": {"title": "Velocidade média (km/h)", "showgrid": True},
        "yaxis": {"title": "Velocidade máxima (km/h)", "showgrid": True},
    })

    return {"data": data, "layout": layout}
