from datetime import timedelta
from types import SimpleNamespace

from f1llm.errors import SessionDataUnavailable
from f1llm.llm.tools import ToolOutcome, run_tool


def test_session_results_sends_the_full_classification_to_the_model():
    def load_results(year, event, session_type):
        assert (year, event, session_type) == (2024, "Monza", "Race")
        return [
            {"Position": 1.0, "Abbreviation": "LEC", "FullName": "Charles Leclerc", "TeamName": "Ferrari",
             "Time": timedelta(hours=1, minutes=14, seconds=40, milliseconds=727), "Points": 25.0},
            {"Position": 2.0, "Abbreviation": "PIA", "FullName": "Oscar Piastri", "TeamName": "McLaren",
             "Time": timedelta(seconds=2, milliseconds=664), "Points": 18.0},
        ]

    outcome = run_tool(
        "get_session_results",
        {"year": 2024, "event": "Monza", "session_type": "Race"},
        loaders=SimpleNamespace(load_results=load_results),
    )

    assert outcome == ToolOutcome(
        content={
            "results": [
                {"position": 1, "driver": "Charles Leclerc", "driver_code": "LEC", "team": "Ferrari",
                 "time": "1:14:40.727000", "points": 25.0},
                {"position": 2, "driver": "Oscar Piastri", "driver_code": "PIA", "team": "McLaren",
                 "time": "0:00:02.664000", "points": 18.0},
            ]
        },
        figure=None,
        is_error=False,
    )


def test_invalid_input_is_reported_to_the_model_as_an_error():
    outcome = run_tool(
        "get_session_results",
        {"year": 2017, "event": "Monza", "session_type": "Race"},
        loaders=SimpleNamespace(load_results=None),
    )

    assert outcome.is_error is True
    assert "year" in outcome.content["error"]
    assert outcome.figure is None


def test_missing_session_data_is_reported_to_the_model_as_an_error():
    def load_results(year, event, session_type):
        raise SessionDataUnavailable("Session not found: Atlantis 2024 Race")

    outcome = run_tool(
        "get_session_results",
        {"year": 2024, "event": "Atlantis", "session_type": "Race"},
        loaders=SimpleNamespace(load_results=load_results),
    )

    assert outcome == ToolOutcome(content={"error": "Session not found: Atlantis 2024 Race"}, is_error=True)


def stint_lap(driver, lap_number, *, stint=1.0, compound="MEDIUM", track_status="1"):
    return {
        "Driver": driver, "LapNumber": float(lap_number), "Position": 1.0, "Stint": stint,
        "Compound": compound, "TyreLife": float(lap_number), "FreshTyre": True, "TrackStatus": track_status,
    }


def monza_stints(year, event, session_type):
    return {
        "event_name": "Italian Grand Prix",
        "laps": [
            stint_lap("LEC", 1),
            stint_lap("LEC", 2, track_status="4"),
            stint_lap("LEC", 3, stint=2.0, compound="HARD"),
        ],
        "results": [{"Abbreviation": "LEC", "Position": 1.0}],
    }


def test_stints_send_every_stint_and_neutralization_without_a_chart_when_not_asked_to_plot():
    outcome = run_tool(
        "get_stints",
        {"year": 2024, "event": "Monza", "session_type": "Race", "plot": False},
        loaders=SimpleNamespace(load_stint_data=monza_stints),
    )

    assert outcome == ToolOutcome(
        content={
            "event_name": "Italian Grand Prix",
            "drivers": [
                {
                    "driver_code": "LEC",
                    "position": 1,
                    "stints": [
                        {"number": 1, "compound": "MEDIUM", "start_lap": 1, "end_lap": 2, "lap_count": 2,
                         "fresh": True, "tyre_age_at_start": 0},
                        {"number": 2, "compound": "HARD", "start_lap": 3, "end_lap": 3, "lap_count": 1,
                         "fresh": True, "tyre_age_at_start": 2},
                    ],
                }
            ],
            "safety_car_periods": [{"kind": "safety_car", "start_lap": 2, "end_lap": 2}],
        },
        figure=None,
    )


def test_stints_come_with_the_stints_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_stints",
        {"year": 2024, "event": "Monza", "session_type": "Race", "plot": True},
        loaders=SimpleNamespace(load_stint_data=monza_stints),
    )

    assert outcome.figure["layout"]["title"] == "2024 Italian Grand Prix - Race"
    assert outcome.content["drivers"][0]["driver_code"] == "LEC"


def test_lap_times_send_best_mean_median_and_every_lap_per_driver():
    def load_laps(year, event, session_type, drivers):
        assert drivers == ["LEC"]
        return [
            {"Driver": "LEC", "LapNumber": 1.0, "LapTime": timedelta(seconds=85.5)},
            {"Driver": "LEC", "LapNumber": 2.0, "LapTime": timedelta(seconds=84.0)},
            {"Driver": "LEC", "LapNumber": 3.0, "LapTime": None},
            {"Driver": "LEC", "LapNumber": 4.0, "LapTime": timedelta(seconds=86.1)},
        ]

    outcome = run_tool(
        "get_lap_times",
        {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["LEC"], "plot": False},
        loaders=SimpleNamespace(load_laps=load_laps),
    )

    assert outcome == ToolOutcome(
        content={
            "drivers": [
                {
                    "driver_code": "LEC",
                    "best_lap": {"lap": 2, "seconds": 84.0},
                    "mean_seconds": 85.2,
                    "median_seconds": 85.5,
                    "laps": [
                        {"lap": 1, "seconds": 85.5},
                        {"lap": 2, "seconds": 84.0},
                        {"lap": 3, "seconds": None},
                        {"lap": 4, "seconds": 86.1},
                    ],
                }
            ]
        },
    )


def test_lap_times_come_with_the_lap_times_chart_when_asked_to_plot():
    def load_laps(year, event, session_type, drivers):
        return [{"Driver": "LEC", "LapNumber": 1.0, "LapTime": timedelta(seconds=85.5)}]

    outcome = run_tool(
        "get_lap_times",
        {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["LEC"], "plot": True},
        loaders=SimpleNamespace(load_laps=load_laps),
    )

    [trace] = outcome.figure["data"]
    assert (trace["name"], trace["x"], trace["y"]) == ("LEC", [1], [85.5])


def pace_lap(driver, lap_number, lap_seconds, *, stint=1.0):
    return {
        "Driver": driver, "LapNumber": float(lap_number),
        "Time": timedelta(hours=1, seconds=lap_number * lap_seconds),
        "Stint": stint, "Position": 1.0, "TrackStatus": "1",
    }


def monza_pace(year, event, session_type):
    # LEC laps in 90 s and NOR in 92 s, so the reference laps in 91 s:
    # LEC gains 1 s on it every lap and NOR loses 1 s.
    return {
        "event_name": "Italian Grand Prix",
        "race_start": timedelta(hours=1),
        "laps": [pace_lap("LEC", lap, 90.0) for lap in range(1, 8)]
        + [pace_lap("NOR", lap, 92.0, stint=1.0 if lap < 4 else 2.0) for lap in range(1, 8)],
        "results": [
            {"Abbreviation": "LEC", "Position": 1.0, "TeamName": "Ferrari", "TeamColor": "E8002D"},
            {"Abbreviation": "NOR", "Position": 2.0, "TeamName": "McLaren", "TeamColor": "FF8000"},
        ],
    }


def test_race_pace_sends_the_gap_every_five_laps_and_at_the_flag():
    outcome = run_tool(
        "get_race_pace",
        {"year": 2024, "event": "Monza", "session_type": "Race", "plot": False},
        loaders=SimpleNamespace(load_race_pace_data=monza_pace),
    )

    assert outcome == ToolOutcome(
        content={
            "event_name": "Italian Grand Prix",
            "drivers": [
                {"driver_code": "LEC", "position": 1, "team_name": "Ferrari", "pit_out_laps": [],
                 "gaps_to_reference": [{"lap": 5, "seconds": 5.0}, {"lap": 7, "seconds": 7.0}]},
                {"driver_code": "NOR", "position": 2, "team_name": "McLaren", "pit_out_laps": [4],
                 "gaps_to_reference": [{"lap": 5, "seconds": -5.0}, {"lap": 7, "seconds": -7.0}]},
            ],
            "safety_car_periods": [],
        },
    )


def test_race_pace_comes_with_the_race_pace_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_race_pace",
        {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["LEC"], "plot": True},
        loaders=SimpleNamespace(load_race_pace_data=monza_pace),
    )

    assert outcome.figure["layout"]["title"] == "2024 Italian Grand Prix - Race"
    assert [trace["name"] for trace in outcome.figure["data"]] == ["LEC"]


def sample(distance, speed, throttle, brake, gear):
    return {"Driver": "LEC", "LapNumber": 12.0, "Distance": distance, "Speed": speed,
            "Throttle": throttle, "Brake": brake, "nGear": gear}


def test_telemetry_sends_speed_throttle_brake_and_gear_figures_for_the_requested_lap():
    calls = []

    def load_telemetry(year, event, session_type, drivers, laps):
        calls.append((drivers, laps))
        # Each sample's state holds until the next one: 200 m flat out, then 100 m braking.
        return [
            sample(0.0, 300.0, 100.0, False, 7),
            sample(100.0, 320.0, 100.0, False, 8),
            sample(200.0, 150.0, 0.0, True, 4),
            sample(300.0, 200.0, 60.0, False, 5),
        ]

    outcome = run_tool(
        "get_telemetry_comparison",
        {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["LEC"],
         "laps": [{"driver": "LEC", "lap": 12}], "plot": False},
        loaders=SimpleNamespace(load_telemetry=load_telemetry),
    )

    assert calls == [(["LEC"], {"LEC": 12})]
    assert outcome == ToolOutcome(
        content={
            "drivers": [
                {"driver_code": "LEC", "lap": 12, "top_speed_kmh": 320.0, "min_speed_kmh": 150.0,
                 "full_throttle_pct_of_distance": 66.7, "braking_pct_of_distance": 33.3,
                 "min_gear": 4, "max_gear": 8},
            ]
        },
    )


def test_telemetry_comes_with_the_telemetry_chart_when_asked_to_plot():
    def load_telemetry(year, event, session_type, drivers, laps):
        return [sample(0.0, 300.0, 100.0, False, 7), sample(100.0, 320.0, 100.0, False, 8)]

    outcome = run_tool(
        "get_telemetry_comparison",
        {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["LEC"], "plot": True},
        loaders=SimpleNamespace(load_telemetry=load_telemetry),
    )

    speed_trace = outcome.figure["data"][0]
    assert (speed_trace["name"], speed_trace["x"], speed_trace["y"]) == ("LEC", [0.0, 100.0], [300.0, 320.0])
