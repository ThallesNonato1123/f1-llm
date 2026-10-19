from datetime import timedelta

import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.best_sectors import get_best_sectors


def row(driver_code, s1, s2, s3, team_color="E8002D"):
    return {
        "driver_code": driver_code,
        "team_color": team_color,
        "sector_1": timedelta(seconds=s1) if s1 is not None else None,
        "sector_2": timedelta(seconds=s2) if s2 is not None else None,
        "sector_3": timedelta(seconds=s3) if s3 is not None else None,
    }


def sectors_data(rows, event_name="Italian Grand Prix"):
    return {"event_name": event_name, "laps": rows}


def test_picks_the_best_sector_times_independently_per_sector():
    data = sectors_data([
        row("VER", 28.0, 35.0, 27.0),
        row("VER", 27.5, 36.0, 26.8),  # better S1 and S3, worse S2
    ])

    result = get_best_sectors(
        year=2023,
        event="Monza",
        session_type="Qualifying",
        load_best_sectors=lambda year, event, session_type: data,
    )

    assert result.found is True
    [driver] = result.drivers
    assert driver.driver_code == "VER"
    assert driver.sector_1 == pytest.approx(27.5)
    assert driver.sector_2 == pytest.approx(35.0)
    assert driver.sector_3 == pytest.approx(26.8)
    assert driver.team_color == "#E8002D"


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_best_sectors(year=2023, event="Monza", session_type="Practice")


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_best_sectors(year=2017, event="Monza", session_type="Race")


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_best_sectors(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        load_best_sectors=raise_not_found,
    )

    assert result.found is False
    assert result.drivers is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"
