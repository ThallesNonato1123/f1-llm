from datetime import timedelta

import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.session_results import DriverResult, get_session_results


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_session_results(year=2023, event="Bahrain", session_type="Practice")


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_session_results(year=2017, event="Bahrain", session_type="Race")


def test_returns_transformed_results_for_known_session():
    raw_rows = [
        {
            "Position": 1.0,
            "Abbreviation": "VER",
            "FullName": "Max Verstappen",
            "TeamName": "Red Bull Racing",
            "Time": timedelta(hours=1, minutes=33, seconds=56, milliseconds=736),
            "Points": 25.0,
        },
        {
            "Position": 2.0,
            "Abbreviation": "HAM",
            "FullName": "Lewis Hamilton",
            "TeamName": "Mercedes",
            "Time": timedelta(seconds=11, milliseconds=987),
            "Points": 18.0,
        },
    ]

    result = get_session_results(
        year=2023,
        event="Bahrain",
        session_type="Race",
        load_results=lambda year, event, session_type: raw_rows,
    )

    assert result.found is True
    assert result.results == [
        DriverResult(
            position=1,
            driver="Max Verstappen",
            driver_code="VER",
            team="Red Bull Racing",
            time="1:33:56.736000",
            points=25.0,
        ),
        DriverResult(
            position=2,
            driver="Lewis Hamilton",
            driver_code="HAM",
            team="Mercedes",
            time="0:00:11.987000",
            points=18.0,
        ),
    ]


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_session_results(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        load_results=raise_not_found,
    )

    assert result.found is False
    assert result.results is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"
