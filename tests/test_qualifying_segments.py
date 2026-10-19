from datetime import timedelta

import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.qualifying_segments import get_qualifying_segments


def row(team, q1=None, q2=None, q3=None, team_color="E8002D"):
    return {
        "team": team,
        "team_color": team_color,
        "q1": timedelta(seconds=q1) if q1 is not None else None,
        "q2": timedelta(seconds=q2) if q2 is not None else None,
        "q3": timedelta(seconds=q3) if q3 is not None else None,
    }


def segments_data(rows, event_name="Italian Grand Prix"):
    return {"event_name": event_name, "teams": rows}


def test_reshapes_boundary_rows_into_the_response():
    data = segments_data([
        row("Ferrari", q1=80.0, q2=79.5, q3=79.0),
        row("Haas", q1=81.0, q2=None, q3=None),  # eliminated in Q1
    ])

    result = get_qualifying_segments(
        year=2023,
        event="Monza",
        load_qualifying_segments=lambda year, event: data,
    )

    assert result.found is True
    ferrari = next(t for t in result.teams if t.team == "Ferrari")
    assert ferrari.team_color == "#E8002D"
    assert ferrari.q1_seconds == pytest.approx(80.0)
    assert ferrari.q2_seconds == pytest.approx(79.5)
    assert ferrari.q3_seconds == pytest.approx(79.0)
    haas = next(t for t in result.teams if t.team == "Haas")
    assert haas.q2_seconds is None
    assert haas.q3_seconds is None


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_qualifying_segments(year=2017, event="Monza")


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Qualifying")

    result = get_qualifying_segments(
        year=2023,
        event="Imaginary Grand Prix",
        load_qualifying_segments=raise_not_found,
    )

    assert result.found is False
    assert result.teams is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Qualifying"
