import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.speed_delta_trace import (
    Corner,
    DeltaPoint,
    DriverSpeedTrace,
    SpeedTracePoint,
    get_speed_delta_trace,
)


def boundary_data(drivers_telemetry, delta, corners, event_name="Italian Grand Prix"):
    return {
        "event_name": event_name,
        "drivers": drivers_telemetry,
        "delta": delta,
        "corners": corners,
    }


def test_reshapes_boundary_data_into_the_response_dataclasses():
    data = boundary_data(
        drivers_telemetry=[
            {"driver_code": "VER", "distance": [0.0, 10.0], "speed": [280.0, 290.0]},
            {"driver_code": "HAM", "distance": [0.0, 10.0], "speed": [275.0, 285.0]},
        ],
        delta={"distance": [0.0, 10.0], "seconds": [0.0, -0.05]},
        corners=[{"number": 1, "distance": 350.0}],
    )

    result = get_speed_delta_trace(
        year=2023,
        event="Monza",
        session_type="Qualifying",
        drivers=["VER", "HAM"],
        load_speed_delta_trace=lambda year, event, session_type, drivers, laps: data,
    )

    assert result.found is True
    assert result.event_name == "Italian Grand Prix"
    assert result.drivers == [
        DriverSpeedTrace("VER", [SpeedTracePoint(0.0, 280.0), SpeedTracePoint(10.0, 290.0)]),
        DriverSpeedTrace("HAM", [SpeedTracePoint(0.0, 275.0), SpeedTracePoint(10.0, 285.0)]),
    ]
    assert result.delta == [DeltaPoint(0.0, 0.0), DeltaPoint(10.0, -0.05)]
    assert result.corners == [Corner(1, 350.0)]


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_speed_delta_trace(year=2023, event="Monza", session_type="Practice", drivers=["VER", "HAM"])


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_speed_delta_trace(year=2017, event="Monza", session_type="Race", drivers=["VER", "HAM"])


def test_rejects_fewer_than_2_drivers():
    with pytest.raises(ValueError, match="drivers"):
        get_speed_delta_trace(year=2023, event="Monza", session_type="Race", drivers=["VER"])


def test_rejects_more_than_2_drivers():
    with pytest.raises(ValueError, match="drivers"):
        get_speed_delta_trace(year=2023, event="Monza", session_type="Race", drivers=["VER", "HAM", "LEC"])


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type, drivers, laps):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_speed_delta_trace(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        drivers=["VER", "HAM"],
        load_speed_delta_trace=raise_not_found,
    )

    assert result.found is False
    assert result.drivers is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"
