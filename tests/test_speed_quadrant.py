from datetime import timedelta

import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.speed_quadrant import get_speed_quadrant


def lap(team, *, lap_time, top_speed, lap_distance, team_color="E8002D"):
    return {
        "Team": team,
        "TeamColor": team_color,
        "LapTime": timedelta(seconds=lap_time),
        "TopSpeed": top_speed,
        "LapDistance": lap_distance,
    }


def quadrant_data(laps, event_name="Italian Grand Prix"):
    return {"event_name": event_name, "laps": laps}


def test_picks_the_faster_drivers_lap_and_computes_mean_speed_for_the_team():
    # 5000m in 90s -> 55.5..m/s -> 200.0 km/h exactly.
    data = quadrant_data(laps=[
        lap("FERRARI", lap_time=90.0, top_speed=320.0, lap_distance=5000.0),
        lap("FERRARI", lap_time=91.0, top_speed=318.0, lap_distance=5000.0),
    ])

    result = get_speed_quadrant(
        year=2023,
        event="Monza",
        session_type="Qualifying",
        load_speed_quadrant=lambda year, event, session_type: data,
    )

    assert result.found is True
    [team] = result.teams
    assert team.team == "FERRARI"
    assert team.team_color == "#E8002D"
    assert team.top_speed == 320.0
    assert team.mean_speed == pytest.approx(200.0)


def test_returns_every_team_present_by_default():
    data = quadrant_data(laps=[
        lap("FERRARI", lap_time=90.0, top_speed=320.0, lap_distance=5000.0),
        lap("MERCEDES", lap_time=91.0, top_speed=318.0, lap_distance=5000.0),
    ])

    result = get_speed_quadrant(
        year=2023,
        event="Monza",
        session_type="Qualifying",
        load_speed_quadrant=lambda year, event, session_type: data,
    )

    assert {team.team for team in result.teams} == {"FERRARI", "MERCEDES"}


def test_filters_to_the_requested_teams():
    data = quadrant_data(laps=[
        lap("FERRARI", lap_time=90.0, top_speed=320.0, lap_distance=5000.0),
        lap("MERCEDES", lap_time=91.0, top_speed=318.0, lap_distance=5000.0),
    ])

    result = get_speed_quadrant(
        year=2023,
        event="Monza",
        session_type="Qualifying",
        teams=["FERRARI"],
        load_speed_quadrant=lambda year, event, session_type: data,
    )

    assert {team.team for team in result.teams} == {"FERRARI"}


def test_reports_no_team_color_when_missing():
    data = quadrant_data(laps=[
        lap("FERRARI", lap_time=90.0, top_speed=320.0, lap_distance=5000.0, team_color=None),
    ])

    result = get_speed_quadrant(
        year=2023,
        event="Monza",
        session_type="Qualifying",
        load_speed_quadrant=lambda year, event, session_type: data,
    )

    assert result.teams[0].team_color is None


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_speed_quadrant(year=2023, event="Monza", session_type="Practice")


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_speed_quadrant(year=2017, event="Monza", session_type="Race")


def test_rejects_empty_teams_list():
    with pytest.raises(ValueError, match="teams"):
        get_speed_quadrant(year=2023, event="Monza", session_type="Race", teams=[])


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_speed_quadrant(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        load_speed_quadrant=raise_not_found,
    )

    assert result.found is False
    assert result.teams is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"


def test_reports_not_found_when_no_lap_matches_the_requested_teams():
    data = quadrant_data(laps=[lap("FERRARI", lap_time=90.0, top_speed=320.0, lap_distance=5000.0)])

    result = get_speed_quadrant(
        year=2023,
        event="Monza",
        session_type="Race",
        teams=["MERCEDES"],
        load_speed_quadrant=lambda year, event, session_type: data,
    )

    assert result.found is False
    assert result.teams is None
    assert "MERCEDES" in result.reason
