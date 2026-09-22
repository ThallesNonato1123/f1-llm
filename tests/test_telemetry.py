import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.telemetry import (
    TelemetrySample,
    build_telemetry_chart,
    get_telemetry_comparison,
)


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_telemetry_comparison(
            year=2023, event="Bahrain", session_type="Practice", drivers=["VER"]
        )


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_telemetry_comparison(
            year=2017, event="Bahrain", session_type="Race", drivers=["VER"]
        )


def test_rejects_empty_drivers_list():
    with pytest.raises(ValueError, match="drivers"):
        get_telemetry_comparison(
            year=2023, event="Bahrain", session_type="Race", drivers=[]
        )


def test_returns_transformed_samples_for_known_telemetry():
    raw_rows = [
        {"Driver": "VER", "LapNumber": 45.0, "Distance": 0.0, "Speed": 100.0, "Throttle": 50.0, "Brake": False, "nGear": 3},
        {"Driver": "VER", "LapNumber": 45.0, "Distance": 10.0, "Speed": 120.0, "Throttle": 80.0, "Brake": False, "nGear": 4},
        {"Driver": "HAM", "LapNumber": 12.0, "Distance": 0.0, "Speed": 95.0, "Throttle": 40.0, "Brake": True, "nGear": 2},
    ]

    result = get_telemetry_comparison(
        year=2023,
        event="Bahrain",
        session_type="Race",
        drivers=["VER", "HAM"],
        load_telemetry=lambda year, event, session_type, drivers, laps: raw_rows,
    )

    assert result.found is True
    assert result.samples == [
        TelemetrySample(driver_code="VER", lap_number=45, distance=0.0, speed=100.0, throttle=50.0, brake=False, gear=3),
        TelemetrySample(driver_code="VER", lap_number=45, distance=10.0, speed=120.0, throttle=80.0, brake=False, gear=4),
        TelemetrySample(driver_code="HAM", lap_number=12, distance=0.0, speed=95.0, throttle=40.0, brake=True, gear=2),
    ]


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type, drivers, laps):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_telemetry_comparison(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        drivers=["VER"],
        load_telemetry=raise_not_found,
    )

    assert result.found is False
    assert result.samples is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"


def test_builds_four_stacked_subplots_with_one_line_per_driver_per_channel():
    samples = [
        TelemetrySample(driver_code="VER", lap_number=45, distance=0.0, speed=100.0, throttle=50.0, brake=False, gear=3),
        TelemetrySample(driver_code="VER", lap_number=45, distance=10.0, speed=120.0, throttle=80.0, brake=False, gear=4),
        TelemetrySample(driver_code="HAM", lap_number=12, distance=0.0, speed=95.0, throttle=40.0, brake=True, gear=2),
    ]

    chart = build_telemetry_chart(samples)

    assert chart["data"] == [
        {"type": "scatter", "mode": "lines", "name": "VER", "x": [0.0, 10.0], "y": [100.0, 120.0], "xaxis": "x", "yaxis": "y"},
        {"type": "scatter", "mode": "lines", "name": "VER", "x": [0.0, 10.0], "y": [50.0, 80.0], "xaxis": "x", "yaxis": "y2"},
        {"type": "scatter", "mode": "lines", "name": "VER", "x": [0.0, 10.0], "y": [False, False], "xaxis": "x", "yaxis": "y3"},
        {"type": "scatter", "mode": "lines", "name": "VER", "x": [0.0, 10.0], "y": [3, 4], "xaxis": "x", "yaxis": "y4"},
        {"type": "scatter", "mode": "lines", "name": "HAM", "x": [0.0], "y": [95.0], "xaxis": "x", "yaxis": "y"},
        {"type": "scatter", "mode": "lines", "name": "HAM", "x": [0.0], "y": [40.0], "xaxis": "x", "yaxis": "y2"},
        {"type": "scatter", "mode": "lines", "name": "HAM", "x": [0.0], "y": [True], "xaxis": "x", "yaxis": "y3"},
        {"type": "scatter", "mode": "lines", "name": "HAM", "x": [0.0], "y": [2], "xaxis": "x", "yaxis": "y4"},
    ]
    assert chart["layout"]["xaxis"]["title"] == "Distância (m)"
    assert chart["layout"]["yaxis"]["title"] == "Velocidade (km/h)"
    assert chart["layout"]["yaxis2"]["title"] == "Throttle (%)"
    assert chart["layout"]["yaxis3"]["title"] == "Freio"
    assert chart["layout"]["yaxis4"]["title"] == "Marcha"
