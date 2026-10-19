from datetime import timedelta

import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.gap_to_pole import get_gap_to_pole


def row(driver_code, lap_time_seconds, team_color="E8002D"):
    return {"driver_code": driver_code, "team_color": team_color, "lap_time": timedelta(seconds=lap_time_seconds)}


def gap_data(rows, event_name="Italian Grand Prix"):
    return {"event_name": event_name, "drivers": rows}


def test_sorts_by_lap_time_and_computes_gap_to_the_fastest():
    data = gap_data([
        row("HAM", 91.5),
        row("VER", 90.0),
        row("LEC", 90.8),
    ])

    result = get_gap_to_pole(
        year=2023,
        event="Monza",
        session_type="Qualifying",
        load_gap_to_pole=lambda year, event, session_type, drivers: data,
    )

    assert result.found is True
    assert [d.driver_code for d in result.drivers] == ["VER", "LEC", "HAM"]
    assert result.drivers[0].gap_seconds == pytest.approx(0.0)
    assert result.drivers[1].gap_seconds == pytest.approx(0.8)
    assert result.drivers[2].gap_seconds == pytest.approx(1.5)
    assert result.drivers[0].team_color == "#E8002D"
    assert result.drivers[0].lap_time_seconds == pytest.approx(90.0)


def test_reports_no_team_color_when_missing():
    data = gap_data([row("VER", 90.0, team_color=None)])

    result = get_gap_to_pole(
        year=2023,
        event="Monza",
        session_type="Qualifying",
        load_gap_to_pole=lambda year, event, session_type, drivers: data,
    )

    assert result.drivers[0].team_color is None


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_gap_to_pole(year=2023, event="Monza", session_type="Practice")


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_gap_to_pole(year=2017, event="Monza", session_type="Race")


def test_rejects_empty_drivers_list():
    with pytest.raises(ValueError, match="drivers"):
        get_gap_to_pole(year=2023, event="Monza", session_type="Race", drivers=[])


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type, drivers):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_gap_to_pole(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        load_gap_to_pole=raise_not_found,
    )

    assert result.found is False
    assert result.drivers is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"
