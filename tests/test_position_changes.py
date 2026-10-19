import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.position_changes import PositionPoint, get_position_changes


def row(driver, lap_number, position, team_color="E8002D"):
    return {"Driver": driver, "TeamColor": team_color, "LapNumber": lap_number, "Position": position}


def position_data(rows, event_name="Italian Grand Prix"):
    return {"event_name": event_name, "laps": rows}


def test_groups_laps_by_driver_with_team_color():
    data = position_data([
        row("VER", 1, 2),
        row("VER", 2, 1),
        row("HAM", 1, 1, team_color="27F4D2"),
        row("HAM", 2, 2, team_color="27F4D2"),
    ])

    result = get_position_changes(
        year=2023,
        event="Monza",
        session_type="Race",
        load_position_changes=lambda year, event, session_type, drivers: data,
    )

    assert result.found is True
    ver = next(d for d in result.drivers if d.driver_code == "VER")
    assert ver.team_color == "#E8002D"
    assert ver.points == [PositionPoint(1, 2), PositionPoint(2, 1)]
    ham = next(d for d in result.drivers if d.driver_code == "HAM")
    assert ham.points == [PositionPoint(1, 1), PositionPoint(2, 2)]


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_position_changes(year=2023, event="Monza", session_type="Qualifying")


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_position_changes(year=2017, event="Monza", session_type="Race")


def test_rejects_empty_drivers_list():
    with pytest.raises(ValueError, match="drivers"):
        get_position_changes(year=2023, event="Monza", session_type="Race", drivers=[])


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type, drivers):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_position_changes(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        load_position_changes=raise_not_found,
    )

    assert result.found is False
    assert result.drivers is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"
