from datetime import timedelta

import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.fastf1_client import (
    load_driver_standings,
    load_gg_diagram,
    load_laps,
    load_race_pace_data,
    load_results,
    load_speed_quadrant,
    load_stint_data,
    load_team_standings,
    load_telemetry,
    load_top_speeds,
    load_tyre_degradation,
)
from f1llm.tools.gg_diagram import get_gg_diagram


@pytest.mark.integration
def test_loads_results_for_a_known_historical_race():
    rows = load_results(2021, "Abu Dhabi", "Race")

    assert rows[0]["Abbreviation"] == "VER"
    assert rows[0]["Position"] == 1.0
    assert rows[1]["Abbreviation"] == "HAM"
    assert rows[1]["Position"] == 2.0


@pytest.mark.integration
def test_raises_not_found_for_a_session_that_did_not_exist_that_year():
    # The Sprint format was introduced in 2021; 2018 race weekends had no Sprint session.
    with pytest.raises(SessionDataUnavailable):
        load_results(2018, "Bahrain", "Sprint")


@pytest.mark.integration
def test_loads_laps_for_the_requested_drivers_only():
    rows = load_laps(2021, "Abu Dhabi", "Race", ["VER", "HAM"])

    drivers_present = {row["Driver"] for row in rows}
    assert drivers_present == {"VER", "HAM"}

    ver_lap_numbers = sorted(row["LapNumber"] for row in rows if row["Driver"] == "VER")
    assert ver_lap_numbers[0] == 1.0


@pytest.mark.integration
def test_raises_not_found_when_no_requested_driver_appears():
    with pytest.raises(SessionDataUnavailable):
        load_laps(2021, "Abu Dhabi", "Race", ["ZZZ"])


@pytest.mark.integration
def test_rejects_laps_when_fastf1_fails_to_load_them_without_raising():
    # Same real, uncached-session failure mode as load_race_pace_data: session.load()
    # does not raise, but `.laps` stays unset. Must surface as SessionDataUnavailable.
    with pytest.raises(SessionDataUnavailable):
        load_laps(2025, "Monza", "Race", ["VER"])


@pytest.mark.integration
def test_loads_telemetry_for_fastest_lap_by_default():
    rows = load_telemetry(2021, "Abu Dhabi", "Race", ["VER"], None)

    assert all(row["Driver"] == "VER" for row in rows)
    lap_numbers = {row["LapNumber"] for row in rows}
    assert len(lap_numbers) == 1  # a single lap was selected
    assert all(0 < row["Speed"] < 370 for row in rows)  # plausible F1 speed range (km/h)


@pytest.mark.integration
def test_loads_telemetry_for_an_explicitly_requested_lap():
    rows = load_telemetry(2021, "Abu Dhabi", "Race", ["VER"], {"VER": 10})

    assert all(row["LapNumber"] == 10.0 for row in rows)


@pytest.mark.integration
def test_raises_not_found_for_unknown_driver():
    with pytest.raises(SessionDataUnavailable):
        load_telemetry(2021, "Abu Dhabi", "Race", ["ZZZ"], None)


@pytest.mark.integration
def test_rejects_telemetry_when_fastf1_fails_to_load_laps_without_raising():
    # Same real, uncached-session failure mode as the other loaders.
    with pytest.raises(SessionDataUnavailable):
        load_telemetry(2025, "Monza", "Race", ["VER"], None)


@pytest.mark.integration
def test_loads_stint_data_for_every_driver_with_track_status_and_results():
    data = load_stint_data(2021, "Abu Dhabi", "Race")

    assert data["event_name"] == "Abu Dhabi Grand Prix"

    ham_stints = {row["Stint"] for row in data["laps"] if row["Driver"] == "HAM"}
    assert len(ham_stints) >= 2  # HAM pitted at least once

    drivers_present = {row["Driver"] for row in data["laps"]}
    assert len(drivers_present) == 19  # every starter, not a filtered subset (MAZ did not start)

    # The race-deciding Safety car came out in the closing laps.
    leader_statuses = [row["TrackStatus"] for row in data["laps"] if row["Position"] == 1]
    assert any("4" in (status or "") for status in leader_statuses)

    results = {row["Abbreviation"]: row["Position"] for row in data["results"]}
    assert results["VER"] == 1.0


@pytest.mark.integration
def test_rejects_stint_data_when_fastf1_fails_to_load_laps_without_raising():
    # Same real, uncached-session failure mode as the other loaders.
    with pytest.raises(SessionDataUnavailable):
        load_stint_data(2025, "Monza", "Race")


@pytest.mark.integration
def test_loads_race_pace_data_with_lap_end_times_for_every_starter():
    data = load_race_pace_data(2021, "Abu Dhabi", "Race")

    assert data["event_name"] == "Abu Dhabi Grand Prix"

    drivers_present = {row["Driver"] for row in data["laps"]}
    assert len(drivers_present) == 19  # MAZ did not start

    # Lap end times never go missing, unlike LapTime (absent on Safety car laps).
    assert all(row["Time"] is not None for row in data["laps"])
    first_lap_end = min(row["Time"] for row in data["laps"] if row["LapNumber"] == 1)
    assert first_lap_end - data["race_start"] > timedelta(seconds=80)  # a plausible opening lap

    teams = {row["Abbreviation"]: (row["TeamName"], row["TeamColor"]) for row in data["results"]}
    assert teams["VER"][0] == "Red Bull Racing"
    assert len(teams["VER"][1]) == 6  # bare hex digits, e.g. "0600EF"


@pytest.mark.integration
def test_rejects_race_pace_data_for_a_session_that_did_not_exist_that_year():
    with pytest.raises(SessionDataUnavailable):
        load_race_pace_data(2018, "Bahrain", "Sprint")


@pytest.mark.integration
def test_rejects_race_pace_data_when_fastf1_fails_to_load_laps_without_raising():
    # A valid, uncached session: fastf1.Session.load() does not raise here, but when
    # its lap timing source is unavailable it only logs a warning and leaves `.laps`
    # unset. The later `session.laps` access must not escape as a raw DataNotLoadedError.
    with pytest.raises(SessionDataUnavailable):
        load_race_pace_data(2025, "Monza", "Race")


@pytest.mark.integration
def test_loads_tyre_degradation_data_with_teams_and_compounds():
    data = load_tyre_degradation(2021, "Abu Dhabi", "Race")

    assert data["event_name"] == "Abu Dhabi Grand Prix"

    teams_present = {row["Team"] for row in data["laps"]}
    assert "Red Bull Racing" in teams_present

    compounds_present = {row["Compound"] for row in data["laps"]}
    assert compounds_present & {"SOFT", "MEDIUM", "HARD"}

    team_colors = {row["Team"]: row["TeamColor"] for row in data["results"]}
    assert len(team_colors["Red Bull Racing"]) == 6  # bare hex digits, e.g. "0600EF"


@pytest.mark.integration
def test_rejects_tyre_degradation_data_when_fastf1_fails_to_load_laps_without_raising():
    # Same real, uncached-session failure mode as the other loaders.
    with pytest.raises(SessionDataUnavailable):
        load_tyre_degradation(2025, "Monza", "Race")


@pytest.mark.integration
def test_loads_speed_quadrant_data_with_team_mean_and_top_speed():
    data = load_speed_quadrant(2021, "Abu Dhabi", "Race")

    assert data["event_name"] == "Abu Dhabi Grand Prix"

    teams_present = {row["Team"] for row in data["laps"]}
    assert "Red Bull Racing" in teams_present

    row = next(r for r in data["laps"] if r["Team"] == "Red Bull Racing")
    assert row["TopSpeed"] > 200  # plausible top speed in km/h
    assert row["LapDistance"] > 4000  # the Yas Marina lap is ~5.5km
    assert len(row["TeamColor"]) == 6  # bare hex digits, e.g. "0600EF"


@pytest.mark.integration
def test_rejects_speed_quadrant_data_when_fastf1_fails_to_load_laps_without_raising():
    with pytest.raises(SessionDataUnavailable):
        load_speed_quadrant(2025, "Monza", "Race")


@pytest.mark.integration
def test_loads_gg_diagram_telemetry_with_plausible_accelerations():
    result = get_gg_diagram(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        drivers=["VER"],
        load_gg_diagram=load_gg_diagram,
    )

    assert result.found is True
    [driver] = result.drivers
    assert driver.compound in {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}
    # A real lap combines braking, cornering and traction; a unit mismatch
    # between X/Y and Distance would blow this far past 7.5g or collapse it
    # near 0, so this is also a sanity check on the FastF1 boundary itself.
    assert 0.3 < driver.average_combined_g < 7.5


@pytest.mark.integration
def test_rejects_gg_diagram_data_when_fastf1_fails_to_load_laps_without_raising():
    with pytest.raises(SessionDataUnavailable):
        load_gg_diagram(2025, "Monza", "Race", ["VER"])


@pytest.mark.integration
def test_loads_driver_standings_through_a_given_event():
    # 2021 Abu Dhabi was the season finale, decided by 8 points between VER and HAM.
    rows = load_driver_standings(2021, "Abu Dhabi")

    assert rows[0]["driverCode"] == "VER"
    assert rows[0]["points"] == 395.5
    assert rows[1]["driverCode"] == "HAM"
    assert rows[1]["points"] == 387.5


@pytest.mark.integration
def test_loads_latest_driver_standings_when_no_event_is_given():
    # 2023 is a closed season: VER won the title with 575 points.
    rows = load_driver_standings(2023, None)

    assert rows[0]["driverCode"] == "VER"
    assert rows[0]["points"] == 575.0


@pytest.mark.integration
def test_loads_team_standings_through_a_given_event():
    # 2021 Abu Dhabi: Mercedes won the constructors' title over Red Bull.
    rows = load_team_standings(2021, "Abu Dhabi")

    assert rows[0]["constructorName"] == "Mercedes"
    assert rows[0]["points"] == 613.5
    assert rows[1]["constructorName"] == "Red Bull"
    assert rows[1]["points"] == 585.5


@pytest.mark.integration
def test_loads_the_true_telemetry_top_speed_for_every_lap_of_the_requested_driver():
    data = load_top_speeds(2021, "Abu Dhabi", "Race", ["VER"])

    assert data["event_name"] == "Abu Dhabi Grand Prix"
    ver_lap_1 = next(row for row in data["rows"] if row["LapNumber"] == 1.0)
    assert ver_lap_1["Driver"] == "VER"
    assert ver_lap_1["TopSpeed"] == 319.0


@pytest.mark.integration
def test_loads_top_speeds_for_every_driver_when_none_are_requested():
    data = load_top_speeds(2021, "Abu Dhabi", "Race")

    drivers_present = {row["Driver"] for row in data["rows"]}
    assert len(drivers_present) == 19  # every starter, not a filtered subset (MAZ did not start)


@pytest.mark.integration
def test_raises_not_found_for_top_speeds_of_a_session_that_did_not_exist_that_year():
    with pytest.raises(SessionDataUnavailable):
        load_top_speeds(2018, "Bahrain", "Sprint")
