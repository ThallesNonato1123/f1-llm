from datetime import timedelta

import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.lap_times import LapTime, build_lap_times_chart, get_lap_times


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_lap_times(year=2023, event="Bahrain", session_type="Practice", drivers=["VER"])


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_lap_times(year=2017, event="Bahrain", session_type="Race", drivers=["VER"])


def test_rejects_empty_drivers_list():
    with pytest.raises(ValueError, match="drivers"):
        get_lap_times(year=2023, event="Bahrain", session_type="Race", drivers=[])


def test_returns_transformed_laps_for_known_session():
    raw_rows = [
        {"Driver": "VER", "LapNumber": 1.0, "LapTime": timedelta(minutes=1, seconds=34, milliseconds=123)},
        {"Driver": "VER", "LapNumber": 2.0, "LapTime": None},
        {"Driver": "HAM", "LapNumber": 1.0, "LapTime": timedelta(minutes=1, seconds=35, milliseconds=789)},
    ]

    result = get_lap_times(
        year=2023,
        event="Bahrain",
        session_type="Race",
        drivers=["VER", "HAM"],
        load_laps=lambda year, event, session_type, drivers: raw_rows,
    )

    assert result.found is True
    assert result.laps == [
        LapTime(lap_number=1, driver_code="VER", seconds=94.123, formatted="0:01:34.123000"),
        LapTime(lap_number=2, driver_code="VER", seconds=None, formatted=None),
        LapTime(lap_number=1, driver_code="HAM", seconds=95.789, formatted="0:01:35.789000"),
    ]


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type, drivers):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_lap_times(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        drivers=["VER"],
        load_laps=raise_not_found,
    )

    assert result.found is False
    assert result.laps is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"


def test_builds_one_chart_line_per_driver_skipping_laps_without_a_time():
    laps = [
        LapTime(lap_number=1, driver_code="VER", seconds=94.123, formatted="0:01:34.123000"),
        LapTime(lap_number=2, driver_code="VER", seconds=None, formatted=None),
        LapTime(lap_number=3, driver_code="VER", seconds=93.456, formatted="0:01:33.456000"),
        LapTime(lap_number=1, driver_code="HAM", seconds=95.789, formatted="0:01:35.789000"),
    ]

    chart = build_lap_times_chart(laps)

    assert chart["data"] == [
        {"type": "scatter", "mode": "lines+markers", "name": "VER", "x": [1, 3], "y": [94.123, 93.456]},
        {"type": "scatter", "mode": "lines+markers", "name": "HAM", "x": [1], "y": [95.789]},
    ]
    assert chart["layout"]["xaxis"]["title"] == "Volta"
    assert chart["layout"]["yaxis"]["title"] == "Tempo de volta (s)"
