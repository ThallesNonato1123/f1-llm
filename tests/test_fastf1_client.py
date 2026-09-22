import pytest

from f1llm.fastf1_client import load_results
from f1llm.tools.session_results import SessionDataUnavailable


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
