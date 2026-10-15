from dataclasses import dataclass
from datetime import date

from f1llm.charts import dark_layout
from f1llm.errors import SessionDataUnavailable

MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class DriverStanding:
    position: int
    driver_code: str
    driver: str
    team: str
    points: float
    wins: int


@dataclass(frozen=True)
class DriverStandingsResponse:
    found: bool
    standings: list[DriverStanding] | None = None
    reason: str | None = None


def get_driver_standings(*, year: int, event: str | None = None, load_driver_standings=None):
    current_year = date.today().year
    if not (MIN_SUPPORTED_YEAR <= year <= current_year):
        raise ValueError(
            f"Unsupported year {year!r}; "
            f"expected between {MIN_SUPPORTED_YEAR} and {current_year}"
        )

    try:
        raw_rows = load_driver_standings(year, event)
    except SessionDataUnavailable as exc:
        return DriverStandingsResponse(found=False, reason=str(exc))

    standings = [
        DriverStanding(
            position=int(row["position"]),
            driver_code=row["driverCode"],
            driver=f"{row['givenName']} {row['familyName']}",
            team=", ".join(row["constructorNames"]),
            points=row["points"],
            wins=int(row["wins"]),
        )
        for row in raw_rows
    ]
    return DriverStandingsResponse(found=True, standings=standings)


def build_driver_standings_chart(standings: list[DriverStanding]) -> dict:
    ordered = sorted(standings, key=lambda standing: standing.position)
    return {
        "data": [
            {
                "type": "bar",
                "x": [standing.driver_code for standing in ordered],
                "y": [standing.points for standing in ordered],
            }
        ],
        "layout": dark_layout(
            {
                "xaxis": {"title": "Piloto", "showgrid": True},
                "yaxis": {"title": "Pontos", "showgrid": True},
            }
        ),
    }


@dataclass(frozen=True)
class TeamStanding:
    position: int
    team: str
    points: float
    wins: int


@dataclass(frozen=True)
class TeamStandingsResponse:
    found: bool
    standings: list[TeamStanding] | None = None
    reason: str | None = None


def get_team_standings(*, year: int, event: str | None = None, load_team_standings=None):
    current_year = date.today().year
    if not (MIN_SUPPORTED_YEAR <= year <= current_year):
        raise ValueError(
            f"Unsupported year {year!r}; "
            f"expected between {MIN_SUPPORTED_YEAR} and {current_year}"
        )

    try:
        raw_rows = load_team_standings(year, event)
    except SessionDataUnavailable as exc:
        return TeamStandingsResponse(found=False, reason=str(exc))

    standings = [
        TeamStanding(
            position=int(row["position"]),
            team=row["constructorName"],
            points=row["points"],
            wins=int(row["wins"]),
        )
        for row in raw_rows
    ]
    return TeamStandingsResponse(found=True, standings=standings)


def build_team_standings_chart(standings: list[TeamStanding]) -> dict:
    ordered = sorted(standings, key=lambda standing: standing.position)
    return {
        "data": [
            {
                "type": "bar",
                "x": [standing.team for standing in ordered],
                "y": [standing.points for standing in ordered],
            }
        ],
        "layout": dark_layout(
            {
                "xaxis": {"title": "Equipe", "showgrid": True},
                "yaxis": {"title": "Pontos", "showgrid": True},
            }
        ),
    }
