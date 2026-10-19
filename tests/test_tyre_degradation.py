from datetime import timedelta

import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.tyre_degradation import (
    TyreDegradationPoint,
    get_tyre_degradation,
)


def lap(team, compound, *, lap_number, tyre_life, seconds, track_status="1",
        pit_in=False, pit_out=False):
    return {
        "Team": team,
        "Compound": compound,
        "LapNumber": float(lap_number),
        "TyreLife": float(tyre_life),
        "LapTime": timedelta(seconds=seconds),
        "TrackStatus": track_status,
        "PitInTime": timedelta(seconds=1) if pit_in else None,
        "PitOutTime": timedelta(seconds=1) if pit_out else None,
    }


def result_row(abbreviation, position, team, team_color="E8002D"):
    return {"Abbreviation": abbreviation, "Position": position, "Team": team, "TeamColor": team_color}


def degradation_data(laps, results=None, event_name="Italian Grand Prix"):
    return {
        "event_name": event_name,
        "laps": laps,
        "results": results if results is not None else [],
    }


def test_corrects_a_clean_laps_time_for_the_fixed_fuel_burn_model():
    # ADR 0005: 110kg of fuel at the start of a 4-lap race, burning down linearly
    # to 0 by the last lap; the car loses 0.03s per kg of fuel it still carries.
    data = degradation_data(
        laps=[
            # Dropped: first lap on this tyre set (TyreLife <= 1) and first lap of the race.
            lap("FERRARI", "SOFT", lap_number=1, tyre_life=1, seconds=92.0),
            lap("FERRARI", "SOFT", lap_number=2, tyre_life=2, seconds=89.0),
            # Different team, just here to push the race's total lap count to 4.
            lap("MERCEDES", "SOFT", lap_number=3, tyre_life=1, seconds=90.0),
            lap("MERCEDES", "SOFT", lap_number=4, tyre_life=2, seconds=90.0),
        ],
    )

    result = get_tyre_degradation(
        year=2023,
        event="Monza",
        session_type="Race",
        teams=["FERRARI"],
        load_tyre_degradation=lambda year, event, session_type: data,
    )

    assert result.found is True
    [entry] = result.entries
    assert entry.team == "FERRARI"
    assert entry.compound == "SOFT"
    # fuel at lap 2 of 4 = 110 - 2*(110/4) = 55; fuel-corrected time = 89.0 - 0.03*55 = 87.35
    assert entry.points == [TyreDegradationPoint(tyre_age=1, fuel_corrected_lap_time=87.35)]
    assert entry.slope is None  # fewer than 3 clean laps
    assert entry.r_squared is None


def test_fits_a_trend_line_once_there_are_at_least_3_clean_laps():
    # 4-lap race; raw times are picked so the fuel-corrected time is a perfect
    # line of 90.0, 90.1, 90.2s at tyre ages 1, 2, 3 -> slope 0.1s/lap, R^2 1.0.
    data = degradation_data(
        laps=[
            lap("FERRARI", "SOFT", lap_number=1, tyre_life=1, seconds=90.0),  # dropped
            lap("FERRARI", "SOFT", lap_number=2, tyre_life=2, seconds=91.65),
            lap("FERRARI", "SOFT", lap_number=3, tyre_life=3, seconds=90.925),
            lap("FERRARI", "SOFT", lap_number=4, tyre_life=4, seconds=90.2),
        ],
    )

    result = get_tyre_degradation(
        year=2023,
        event="Monza",
        session_type="Race",
        teams=["FERRARI"],
        load_tyre_degradation=lambda year, event, session_type: data,
    )

    [entry] = result.entries
    assert entry.points == [
        TyreDegradationPoint(tyre_age=1, fuel_corrected_lap_time=pytest.approx(90.0)),
        TyreDegradationPoint(tyre_age=2, fuel_corrected_lap_time=pytest.approx(90.1)),
        TyreDegradationPoint(tyre_age=3, fuel_corrected_lap_time=pytest.approx(90.2)),
    ]
    assert entry.slope == pytest.approx(0.1)
    assert entry.r_squared == pytest.approx(1.0)


def test_excludes_pit_in_pit_out_and_safety_car_laps_from_the_clean_laps():
    data = degradation_data(
        laps=[
            lap("FERRARI", "SOFT", lap_number=1, tyre_life=1, seconds=90.0),  # dropped: first lap on tyre
            lap("FERRARI", "SOFT", lap_number=2, tyre_life=2, seconds=90.0),  # clean
            lap("FERRARI", "SOFT", lap_number=3, tyre_life=3, seconds=90.0, pit_in=True),
            lap("FERRARI", "SOFT", lap_number=4, tyre_life=4, seconds=90.0, pit_out=True),
            lap("FERRARI", "SOFT", lap_number=5, tyre_life=5, seconds=90.0, track_status="4"),  # Safety car
            lap("FERRARI", "SOFT", lap_number=6, tyre_life=6, seconds=90.0),  # clean
        ],
    )

    result = get_tyre_degradation(
        year=2023,
        event="Monza",
        session_type="Race",
        teams=["FERRARI"],
        load_tyre_degradation=lambda year, event, session_type: data,
    )

    [entry] = result.entries
    assert [point.tyre_age for point in entry.points] == [1, 5]


def test_defaults_to_the_top_4_teams_by_their_best_drivers_final_position():
    data = degradation_data(
        laps=[
            lap("A", "SOFT", lap_number=2, tyre_life=2, seconds=90.0),
            lap("B", "SOFT", lap_number=2, tyre_life=2, seconds=90.0),
            lap("C", "SOFT", lap_number=2, tyre_life=2, seconds=90.0),
            lap("D", "SOFT", lap_number=2, tyre_life=2, seconds=90.0),
            lap("E", "SOFT", lap_number=2, tyre_life=2, seconds=90.0),
        ],
        results=[
            result_row("A1", 1, "A"),
            result_row("B1", 2, "B"),
            result_row("C1", 3, "C"),
            result_row("D1", 4, "D"),
            result_row("E1", 5, "E"),
        ],
    )

    result = get_tyre_degradation(
        year=2023,
        event="Monza",
        session_type="Race",
        load_tyre_degradation=lambda year, event, session_type: data,
    )

    assert {entry.team for entry in result.entries} == {"A", "B", "C", "D"}


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_tyre_degradation(year=2023, event="Monza", session_type="Qualifying")


def test_rejects_2018_because_compound_names_were_absolute_that_season():
    with pytest.raises(ValueError, match="year"):
        get_tyre_degradation(year=2018, event="Monza", session_type="Race")


def test_rejects_empty_teams_list():
    with pytest.raises(ValueError, match="teams"):
        get_tyre_degradation(year=2023, event="Monza", session_type="Race", teams=[])


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_tyre_degradation(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        load_tyre_degradation=raise_not_found,
    )

    assert result.found is False
    assert result.entries is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"


def test_ignores_laps_on_wet_compounds():
    data = degradation_data(
        laps=[
            lap("FERRARI", "INTERMEDIATE", lap_number=2, tyre_life=2, seconds=90.0),
            lap("FERRARI", "WET", lap_number=3, tyre_life=1, seconds=95.0),
        ],
    )

    result = get_tyre_degradation(
        year=2023,
        event="Monza",
        session_type="Race",
        teams=["FERRARI"],
        load_tyre_degradation=lambda year, event, session_type: data,
    )

    assert result.found is False


def test_reports_not_found_when_no_dry_compound_clean_laps_exist():
    data = degradation_data(
        laps=[lap("FERRARI", "INTERMEDIATE", lap_number=2, tyre_life=2, seconds=90.0)],
    )

    result = get_tyre_degradation(
        year=2023,
        event="Monza",
        session_type="Race",
        teams=["FERRARI"],
        load_tyre_degradation=lambda year, event, session_type: data,
    )

    assert result.found is False
    assert result.entries is None
    assert "Monza" in result.reason


def test_includes_the_teams_color_from_the_session_results():
    data = degradation_data(
        laps=[
            lap("FERRARI", "SOFT", lap_number=2, tyre_life=2, seconds=90.0),
        ],
        results=[result_row("LEC", 1, "FERRARI", team_color="E8002D")],
    )

    result = get_tyre_degradation(
        year=2023,
        event="Monza",
        session_type="Race",
        teams=["FERRARI"],
        load_tyre_degradation=lambda year, event, session_type: data,
    )

    [entry] = result.entries
    assert entry.team_color == "#E8002D"


def test_reports_no_team_color_when_results_do_not_have_the_team():
    data = degradation_data(
        laps=[lap("FERRARI", "SOFT", lap_number=2, tyre_life=2, seconds=90.0)],
    )

    result = get_tyre_degradation(
        year=2023,
        event="Monza",
        session_type="Race",
        teams=["FERRARI"],
        load_tyre_degradation=lambda year, event, session_type: data,
    )

    [entry] = result.entries
    assert entry.team_color is None
