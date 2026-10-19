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
            {"Driver": "LEC", "LapNumber": 1.0, "LapTime": timedelta(seconds=85.5), "Compound": "SOFT"},
            {"Driver": "LEC", "LapNumber": 2.0, "LapTime": timedelta(seconds=84.0), "Compound": "SOFT"},
            {"Driver": "LEC", "LapNumber": 3.0, "LapTime": None, "Compound": "SOFT"},
            {"Driver": "LEC", "LapNumber": 4.0, "LapTime": timedelta(seconds=86.1), "Compound": "MEDIUM"},
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
        return [{"Driver": "LEC", "LapNumber": 1.0, "LapTime": timedelta(seconds=85.5), "Compound": "SOFT"}]

    outcome = run_tool(
        "get_lap_times",
        {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["LEC"], "plot": True},
        loaders=SimpleNamespace(load_laps=load_laps),
    )

    [trace] = outcome.figure["data"]
    assert (trace["name"], trace["x"], trace["y"]) == ("LEC", [1], [85.5])


def test_lap_times_chart_colors_by_compound_when_asked():
    def load_laps(year, event, session_type, drivers):
        return [{"Driver": "LEC", "LapNumber": 1.0, "LapTime": timedelta(seconds=85.5), "Compound": "SOFT"}]

    outcome = run_tool(
        "get_lap_times",
        {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["LEC"],
         "by_compound": True, "plot": True},
        loaders=SimpleNamespace(load_laps=load_laps),
    )

    [trace] = outcome.figure["data"]
    assert trace["name"] == "Macio"


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


def test_gap_to_winner_sends_the_gap_every_five_laps_and_at_the_flag():
    outcome = run_tool(
        "get_gap_to_winner",
        {"year": 2024, "event": "Monza", "session_type": "Race", "plot": False},
        loaders=SimpleNamespace(load_race_pace_data=monza_pace),
    )

    assert outcome == ToolOutcome(
        content={
            "event_name": "Italian Grand Prix",
            "drivers": [
                {"driver_code": "LEC", "position": 1, "team_name": "Ferrari", "pit_out_laps": [],
                 "gaps_to_winner": [{"lap": 5, "seconds": 0.0}, {"lap": 7, "seconds": 0.0}]},
                {"driver_code": "NOR", "position": 2, "team_name": "McLaren", "pit_out_laps": [4],
                 "gaps_to_winner": [{"lap": 5, "seconds": -10.0}, {"lap": 7, "seconds": -14.0}]},
            ],
            "safety_car_periods": [],
        },
    )


def test_gap_to_winner_comes_with_the_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_gap_to_winner",
        {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["LEC"], "plot": True},
        loaders=SimpleNamespace(load_race_pace_data=monza_pace),
    )

    assert outcome.figure["layout"]["title"] == "2024 Italian Grand Prix - Race"
    assert [trace["name"] for trace in outcome.figure["data"]] == ["LEC"]


def monza_top_speeds(year, event, session_type, drivers):
    assert (year, event, session_type) == (2024, "Monza", "Race")
    return {
        "event_name": "Italian Grand Prix",
        "rows": [
            {"Driver": "LEC", "LapNumber": 1.0, "TopSpeed": 350.0},
            {"Driver": "LEC", "LapNumber": 2.0, "TopSpeed": 340.0},
            {"Driver": "NOR", "LapNumber": 1.0, "TopSpeed": 330.0},
        ],
    }


def test_top_speeds_sends_each_drivers_own_best_and_average():
    outcome = run_tool(
        "get_top_speeds",
        {"year": 2024, "event": "Monza", "session_type": "Race", "plot": False},
        loaders=SimpleNamespace(load_top_speeds=monza_top_speeds),
    )

    assert outcome == ToolOutcome(
        content={
            "event_name": "Italian Grand Prix",
            "session_max": 350.0,
            "drivers": [
                {"driver_code": "LEC", "top_speed": 350.0, "average": 345.0},
                {"driver_code": "NOR", "top_speed": 330.0, "average": 330.0},
            ],
        },
    )


def test_top_speeds_comes_with_the_table_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_top_speeds",
        {"year": 2024, "event": "Monza", "session_type": "Race", "plot": True},
        loaders=SimpleNamespace(load_top_speeds=monza_top_speeds),
    )

    assert outcome.figure["layout"]["title"].startswith("2024 Italian Grand Prix - Race")
    assert outcome.figure["data"][0]["type"] == "table"


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


def monza_driver_standings(year, event):
    assert (year, event) == (2024, "Monza")
    return [
        {"position": 1, "driverCode": "VER", "givenName": "Max", "familyName": "Verstappen",
         "constructorNames": ["Red Bull"], "points": 400.0, "wins": 8},
    ]


def test_driver_standings_sends_the_full_classification_to_the_model():
    outcome = run_tool(
        "get_driver_standings",
        {"year": 2024, "event": "Monza", "plot": False},
        loaders=SimpleNamespace(load_driver_standings=monza_driver_standings),
    )

    assert outcome == ToolOutcome(
        content={
            "standings": [
                {"position": 1, "driver_code": "VER", "driver": "Max Verstappen",
                 "team": "Red Bull", "points": 400.0, "wins": 8},
            ]
        },
        figure=None,
        is_error=False,
    )


def test_driver_standings_come_with_the_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_driver_standings",
        {"year": 2024, "event": "Monza", "plot": True},
        loaders=SimpleNamespace(load_driver_standings=monza_driver_standings),
    )

    assert outcome.figure["data"][0]["x"] == ["VER"]


def monza_team_standings(year, event):
    assert (year, event) == (2024, "Monza")
    return [{"position": 1, "constructorName": "Red Bull", "points": 600.0, "wins": 12}]


def test_team_standings_sends_the_full_classification_to_the_model():
    outcome = run_tool(
        "get_team_standings",
        {"year": 2024, "event": "Monza", "plot": False},
        loaders=SimpleNamespace(load_team_standings=monza_team_standings),
    )

    assert outcome == ToolOutcome(
        content={"standings": [{"position": 1, "team": "Red Bull", "points": 600.0, "wins": 12}]},
        figure=None,
        is_error=False,
    )


def test_team_standings_come_with_the_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_team_standings",
        {"year": 2024, "event": "Monza", "plot": True},
        loaders=SimpleNamespace(load_team_standings=monza_team_standings),
    )

    assert outcome.figure["data"][0]["x"] == ["Red Bull"]


def monza_degradation(year, event, session_type):
    return {
        "event_name": "Italian Grand Prix",
        "laps": [
            {"Team": "Ferrari", "Compound": "SOFT", "LapNumber": 1.0, "TyreLife": 1.0,
             "LapTime": timedelta(seconds=92.0), "TrackStatus": "1", "PitInTime": None, "PitOutTime": None},
            {"Team": "Ferrari", "Compound": "SOFT", "LapNumber": 2.0, "TyreLife": 2.0,
             "LapTime": timedelta(seconds=89.0), "TrackStatus": "1", "PitInTime": None, "PitOutTime": None},
        ],
        "results": [{"Abbreviation": "LEC", "Position": 1.0, "Team": "Ferrari", "TeamColor": "E8002D"}],
    }


def test_tyre_degradation_sends_each_teams_compound_entries_without_a_chart_when_not_asked_to_plot():
    outcome = run_tool(
        "get_tyre_degradation",
        {"year": 2024, "event": "Monza", "session_type": "Race", "teams": ["Ferrari"], "plot": False},
        loaders=SimpleNamespace(load_tyre_degradation=monza_degradation),
    )

    assert outcome == ToolOutcome(
        content={
            "event_name": "Italian Grand Prix",
            "entries": [
                {
                    "team": "Ferrari",
                    "compound": "SOFT",
                    "team_color": "#E8002D",
                    "points": [{"tyre_age": 1, "fuel_corrected_lap_time": 89.0}],
                    "slope": None,
                    "r_squared": None,
                }
            ],
        },
        figure=None,
        is_error=False,
    )


def test_tyre_degradation_comes_with_the_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_tyre_degradation",
        {"year": 2024, "event": "Monza", "session_type": "Race", "teams": ["Ferrari"], "plot": True},
        loaders=SimpleNamespace(load_tyre_degradation=monza_degradation),
    )

    assert outcome.figure["layout"]["title"] == "2024 Italian Grand Prix - Race - Degradação de pneu"


def monza_quadrant(year, event, session_type):
    return {
        "event_name": "Italian Grand Prix",
        "laps": [
            {"Team": "Ferrari", "TeamColor": "E8002D", "LapTime": timedelta(seconds=90.0),
             "TopSpeed": 320.0, "LapDistance": 5000.0},
        ],
    }


def test_speed_quadrant_sends_each_teams_mean_and_top_speed_without_a_chart_when_not_asked_to_plot():
    outcome = run_tool(
        "get_speed_quadrant",
        {"year": 2024, "event": "Monza", "session_type": "Qualifying", "plot": False},
        loaders=SimpleNamespace(load_speed_quadrant=monza_quadrant),
    )

    assert outcome == ToolOutcome(
        content={
            "event_name": "Italian Grand Prix",
            "teams": [
                {"team": "Ferrari", "team_color": "#E8002D", "mean_speed": 200.0, "top_speed": 320.0},
            ],
        },
        figure=None,
        is_error=False,
    )


def test_speed_quadrant_comes_with_the_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_speed_quadrant",
        {"year": 2024, "event": "Monza", "session_type": "Qualifying", "plot": True},
        loaders=SimpleNamespace(load_speed_quadrant=monza_quadrant),
    )

    assert outcome.figure["layout"]["title"] == "2024 Italian Grand Prix - Qualifying (Melhor volta de cada equipe)"


def straight_line_telemetry(speed_kmh=200.0, n=10, dt=0.1):
    speed_ms = speed_kmh / 3.6
    rows = []
    for i in range(n):
        t = i * dt
        distance = speed_ms * t
        rows.append({"Speed": speed_kmh, "Distance": distance, "Time": timedelta(seconds=t), "X": distance, "Y": 0.0})
    return rows


def monza_gg_diagram(year, event, session_type, drivers):
    return {
        "event_name": "Italian Grand Prix",
        "drivers": [
            {"driver_code": driver, "compound": "SOFT", "telemetry": straight_line_telemetry()}
            for driver in drivers
        ],
    }


def test_gg_diagram_sends_each_drivers_average_combined_accel_without_a_chart_when_not_asked_to_plot():
    outcome = run_tool(
        "get_gg_diagram",
        {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["VER"], "plot": False},
        loaders=SimpleNamespace(load_gg_diagram=monza_gg_diagram),
    )

    assert outcome == ToolOutcome(
        content={
            "event_name": "Italian Grand Prix",
            "drivers": [{"driver_code": "VER", "compound": "SOFT", "average_combined_g": 0.0}],
        },
        figure=None,
        is_error=False,
    )


def test_gg_diagram_comes_with_the_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_gg_diagram",
        {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["VER"], "plot": True},
        loaders=SimpleNamespace(load_gg_diagram=monza_gg_diagram),
    )

    assert outcome.figure["layout"]["title"] == "2024 Italian Grand Prix - Race - Diagrama G-G"


def monza_speed_delta_trace(year, event, session_type, drivers, laps):
    return {
        "event_name": "Italian Grand Prix",
        "drivers": [
            {"driver_code": drivers[0], "distance": [0.0, 10.0], "speed": [280.0, 290.0]},
            {"driver_code": drivers[1], "distance": [0.0, 10.0], "speed": [275.0, 285.0]},
        ],
        "delta": {"distance": [0.0, 10.0], "seconds": [0.0, -0.08]},
        "corners": [{"number": 1, "distance": 5.0}],
    }


def test_speed_delta_trace_sends_top_min_speed_and_final_delta_without_a_chart_when_not_asked_to_plot():
    outcome = run_tool(
        "get_speed_delta_trace",
        {"year": 2024, "event": "Monza", "session_type": "Qualifying", "drivers": ["VER", "HAM"], "plot": False},
        loaders=SimpleNamespace(load_speed_delta_trace=monza_speed_delta_trace),
    )

    assert outcome == ToolOutcome(
        content={
            "event_name": "Italian Grand Prix",
            "drivers": [
                {"driver_code": "VER", "top_speed_kmh": 290.0, "min_speed_kmh": 280.0},
                {"driver_code": "HAM", "top_speed_kmh": 285.0, "min_speed_kmh": 275.0},
            ],
            "final_delta_seconds": -0.08,
            "corners": [{"number": 1, "distance": 5.0}],
        },
        figure=None,
        is_error=False,
    )


def test_speed_delta_trace_comes_with_the_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_speed_delta_trace",
        {"year": 2024, "event": "Monza", "session_type": "Qualifying", "drivers": ["VER", "HAM"], "plot": True},
        loaders=SimpleNamespace(load_speed_delta_trace=monza_speed_delta_trace),
    )

    assert outcome.figure["layout"]["title"] == "2024 Italian Grand Prix - Qualifying - Traço de velocidade com delta"


def monza_gap_to_pole(year, event, session_type, drivers):
    return {
        "event_name": "Italian Grand Prix",
        "drivers": [
            {"driver_code": "VER", "team_color": "0600EF", "lap_time": timedelta(seconds=90.0)},
            {"driver_code": "LEC", "team_color": "E8002D", "lap_time": timedelta(seconds=90.8)},
        ],
    }


def test_gap_to_pole_sends_each_drivers_gap_without_a_chart_when_not_asked_to_plot():
    outcome = run_tool(
        "get_gap_to_pole",
        {"year": 2024, "event": "Monza", "session_type": "Qualifying", "plot": False},
        loaders=SimpleNamespace(load_gap_to_pole=monza_gap_to_pole),
    )

    assert outcome == ToolOutcome(
        content={
            "event_name": "Italian Grand Prix",
            "drivers": [
                {"driver_code": "VER", "team_color": "#0600EF", "lap_time_seconds": 90.0, "gap_seconds": 0.0},
                {"driver_code": "LEC", "team_color": "#E8002D", "lap_time_seconds": 90.8, "gap_seconds": 0.8},
            ],
        },
        figure=None,
        is_error=False,
    )


def test_gap_to_pole_comes_with_the_chart_when_asked_to_plot():
    outcome = run_tool(
        "get_gap_to_pole",
        {"year": 2024, "event": "Monza", "session_type": "Qualifying", "plot": True},
        loaders=SimpleNamespace(load_gap_to_pole=monza_gap_to_pole),
    )

    assert outcome.figure["layout"]["title"] == "2024 Italian Grand Prix - Qualifying - Gap para a pole"
