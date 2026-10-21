from dataclasses import dataclass
from datetime import date

from f1llm.charts import dark_layout
from f1llm.errors import SessionDataUnavailable

MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class TeamSegmentTime:
    team: str
    team_color: str | None
    q1_seconds: float | None
    q2_seconds: float | None
    q3_seconds: float | None


@dataclass(frozen=True)
class QualifyingSegmentsResponse:
    found: bool
    event_name: str | None = None
    teams: list[TeamSegmentTime] | None = None
    reason: str | None = None


def _seconds(value):
    return value.total_seconds() if value is not None else None


def get_qualifying_segments(
    *,
    year: int,
    event: str,
    load_qualifying_segments=None,
):
    current_year = date.today().year
    if not (MIN_SUPPORTED_YEAR <= year <= current_year):
        raise ValueError(
            f"Unsupported year {year!r}; "
            f"expected between {MIN_SUPPORTED_YEAR} and {current_year}"
        )

    try:
        data = load_qualifying_segments(year, event)
    except SessionDataUnavailable as exc:
        return QualifyingSegmentsResponse(found=False, reason=str(exc))

    teams = [
        TeamSegmentTime(
            team=row["team"],
            team_color=f"#{row['team_color']}" if row["team_color"] else None,
            q1_seconds=_seconds(row["q1"]),
            q2_seconds=_seconds(row["q2"]),
            q3_seconds=_seconds(row["q3"]),
        )
        for row in data["teams"]
    ]

    return QualifyingSegmentsResponse(found=True, event_name=data["event_name"], teams=teams)


_SEGMENT_FIELDS = {"Q1": "q1_seconds", "Q2": "q2_seconds", "Q3": "q3_seconds"}


def build_qualifying_segment_bar_chart(result: QualifyingSegmentsResponse, *, year: int, segment: str) -> dict:
    attr = _SEGMENT_FIELDS[segment]
    timed = [team for team in result.teams if getattr(team, attr) is not None]
    ordered = sorted(timed, key=lambda team: getattr(team, attr))
    fastest = getattr(ordered[0], attr) if ordered else 0.0

    return {
        "data": [{
            "type": "bar",
            "orientation": "h",
            "y": [team.team for team in ordered],
            "x": [round(getattr(team, attr) - fastest, 3) for team in ordered],
            "marker": {"color": [team.team_color for team in ordered]},
        }],
        "layout": dark_layout({
            "title": f"{year} {result.event_name} - {segment}",
            "xaxis": {"title": "Gap (s)", "showgrid": True},
            "yaxis": {"autorange": "reversed"},
        }),
    }


def build_qualifying_pace_evolution_chart(result: QualifyingSegmentsResponse, *, year: int) -> dict:
    data = []
    for team in result.teams:
        segments = [(label, getattr(team, attr)) for label, attr in _SEGMENT_FIELDS.items()]
        reached = [(label, seconds) for label, seconds in segments if seconds is not None]
        data.append({
            "type": "scatter",
            "mode": "lines+markers",
            "name": team.team,
            "x": [label for label, _ in reached],
            "y": [seconds for _, seconds in reached],
            "line": {"color": team.team_color},
        })

    return {
        "data": data,
        "layout": dark_layout({
            "title": f"{year} {result.event_name} - Evolução do ritmo na Qualifying",
            "xaxis": {"title": "Segmento", "showgrid": True},
            "yaxis": {"title": "Tempo de volta (s)", "showgrid": True},
        }),
    }
