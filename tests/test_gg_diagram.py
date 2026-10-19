import math
from datetime import timedelta

import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.gg_diagram import get_gg_diagram


def straight_line_constant_speed(speed_kmh=200.0, n=12, dt=0.1):
    speed_ms = speed_kmh / 3.6
    rows = []
    for i in range(n):
        t = i * dt
        distance = speed_ms * t
        rows.append({
            "Speed": speed_kmh,
            "Distance": distance,
            "Time": timedelta(seconds=t),
            "X": distance,
            "Y": 0.0,
        })
    return rows


def straight_line_constant_acceleration(initial_speed_kmh=100.0, accel_ms2=5.0, n=12, dt=0.1):
    initial_speed_ms = initial_speed_kmh / 3.6
    rows = []
    for i in range(n):
        t = i * dt
        speed_ms = initial_speed_ms + accel_ms2 * t
        distance = initial_speed_ms * t + 0.5 * accel_ms2 * t * t
        rows.append({
            "Speed": speed_ms * 3.6,
            "Distance": distance,
            "Time": timedelta(seconds=t),
            "X": distance,
            "Y": 0.0,
        })
    return rows


def circular_motion_constant_speed(radius=100.0, speed_kmh=200.0, n=20, dt=0.05):
    speed_ms = speed_kmh / 3.6
    omega = speed_ms / radius
    rows = []
    for i in range(n):
        t = i * dt
        angle = omega * t
        rows.append({
            "Speed": speed_kmh,
            "Distance": speed_ms * t,
            "Time": timedelta(seconds=t),
            "X": radius * math.cos(angle),
            "Y": radius * math.sin(angle),
        })
    return rows


def gg_data(drivers_telemetry, event_name="Italian Grand Prix"):
    """drivers_telemetry: dict[driver_code] -> (compound, telemetry_rows)."""
    return {
        "event_name": event_name,
        "drivers": [
            {"driver_code": code, "compound": compound, "telemetry": rows}
            for code, (compound, rows) in drivers_telemetry.items()
        ],
    }


def test_lateral_and_longitudinal_are_near_zero_on_a_straight_line_at_constant_speed():
    data = gg_data({"VER": ("SOFT", straight_line_constant_speed())})

    result = get_gg_diagram(
        year=2023,
        event="Monza",
        session_type="Race",
        drivers=["VER"],
        load_gg_diagram=lambda year, event, session_type, drivers: data,
    )

    assert result.found is True
    [driver] = result.drivers
    assert driver.driver_code == "VER"
    assert driver.compound == "SOFT"
    for point in driver.points:
        assert point.lateral == pytest.approx(0.0, abs=0.05)
        assert point.longitudinal == pytest.approx(0.0, abs=0.05)


def test_longitudinal_matches_the_known_constant_acceleration_on_a_straight_line():
    accel_ms2 = 5.0
    data = gg_data({"VER": ("SOFT", straight_line_constant_acceleration(accel_ms2=accel_ms2))})
    expected_g = accel_ms2 / 9.81

    result = get_gg_diagram(
        year=2023,
        event="Monza",
        session_type="Race",
        drivers=["VER"],
        load_gg_diagram=lambda year, event, session_type, drivers: data,
    )

    [driver] = result.drivers
    for point in driver.points:
        assert point.longitudinal == pytest.approx(expected_g, abs=0.01)
        assert point.lateral == pytest.approx(0.0, abs=0.01)


def test_lateral_matches_the_centripetal_formula_on_a_circular_path_at_constant_speed():
    radius = 100.0
    speed_kmh = 200.0
    data = gg_data({"VER": ("SOFT", circular_motion_constant_speed(radius=radius, speed_kmh=speed_kmh))})
    speed_ms = speed_kmh / 3.6
    expected_g = (speed_ms**2 / radius) / 9.81

    result = get_gg_diagram(
        year=2023,
        event="Monza",
        session_type="Race",
        drivers=["VER"],
        load_gg_diagram=lambda year, event, session_type, drivers: data,
    )

    [driver] = result.drivers
    # Skip the first/last few points: the stencil's one-sided edge formulas
    # are less accurate for a curved (non-polynomial) path than mid-lap.
    interior = driver.points[5:-5]
    for point in interior:
        assert point.lateral == pytest.approx(expected_g, rel=0.05)
        assert point.longitudinal == pytest.approx(0.0, abs=0.05)


def test_clips_implausible_spikes_instead_of_reporting_them():
    rows = straight_line_constant_speed()
    rows[6]["Speed"] = 200.0 + 50_000.0  # a telemetry glitch, not a real car
    data = gg_data({"VER": ("SOFT", rows)})

    result = get_gg_diagram(
        year=2023,
        event="Monza",
        session_type="Race",
        drivers=["VER"],
        load_gg_diagram=lambda year, event, session_type, drivers: data,
    )

    [driver] = result.drivers
    assert all(abs(point.longitudinal) <= 7.5 for point in driver.points)
    assert all(abs(point.lateral) <= 7.5 for point in driver.points)


def test_computes_average_combined_acceleration_per_driver_and_groups_them():
    accel_ms2 = 5.0
    data = gg_data({
        "VER": ("SOFT", straight_line_constant_speed()),
        "HAM": ("MEDIUM", straight_line_constant_acceleration(accel_ms2=accel_ms2)),
    })

    result = get_gg_diagram(
        year=2023,
        event="Monza",
        session_type="Race",
        drivers=["VER", "HAM"],
        load_gg_diagram=lambda year, event, session_type, drivers: data,
    )

    assert {d.driver_code for d in result.drivers} == {"VER", "HAM"}
    ver = next(d for d in result.drivers if d.driver_code == "VER")
    assert ver.average_combined_g == pytest.approx(0.0, abs=0.01)
    ham = next(d for d in result.drivers if d.driver_code == "HAM")
    assert ham.average_combined_g == pytest.approx(accel_ms2 / 9.81, abs=0.01)


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_gg_diagram(year=2023, event="Monza", session_type="Practice", drivers=["VER"])


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_gg_diagram(year=2017, event="Monza", session_type="Race", drivers=["VER"])


def test_rejects_empty_drivers_list():
    with pytest.raises(ValueError, match="drivers"):
        get_gg_diagram(year=2023, event="Monza", session_type="Race", drivers=[])


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type, drivers):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_gg_diagram(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        drivers=["VER"],
        load_gg_diagram=raise_not_found,
    )

    assert result.found is False
    assert result.drivers is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"
