import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.fastf1_client import load_laps, load_results, load_stint_data, load_telemetry


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
