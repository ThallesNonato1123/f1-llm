import json
from datetime import timedelta
from types import SimpleNamespace

import pytest

from f1llm.errors import SessionDataUnavailable

from f1llm.preview import PreviewRequest, PreviewResult, build_preview, parse_args, to_html


def test_parses_positional_chart_year_event_session_and_drivers():
    request = parse_args(["lap_times", "2024", "Monza", "Race", "LEC", "NOR"])

    assert request == PreviewRequest(
        chart="lap_times",
        year=2024,
        event="Monza",
        session_type="Race",
        drivers=["LEC", "NOR"],
    )


def test_parses_tyre_degradation_teams_through_the_drivers_slot():
    request = parse_args(["tyre_degradation", "2024", "Monza", "Race", "Ferrari", "McLaren"])

    assert request == PreviewRequest(
        chart="tyre_degradation",
        year=2024,
        event="Monza",
        session_type="Race",
        drivers=["Ferrari", "McLaren"],
    )


def test_rejects_unknown_chart():
    with pytest.raises(SystemExit):
        parse_args(["pit_stops", "2024", "Monza", "Race"])


def request(chart, drivers=None, session_type="Race"):
    return PreviewRequest(
        chart=chart, year=2024, event="Monza", session_type=session_type, drivers=drivers or []
    )


def test_builds_lap_times_chart_from_the_requested_session():
    calls = []

    def load_laps(year, event, session_type, drivers):
        calls.append((year, event, session_type, drivers))
        return [
            {"Driver": "LEC", "LapNumber": 1.0, "LapTime": timedelta(seconds=85.5), "Compound": "SOFT"},
            {"Driver": "LEC", "LapNumber": 2.0, "LapTime": timedelta(seconds=84.0), "Compound": "SOFT"},
        ]

    result = build_preview(request("lap_times", ["LEC"]), loaders=SimpleNamespace(load_laps=load_laps))

    assert calls == [(2024, "Monza", "Race", ["LEC"])]
    assert result.found is True
    [trace] = result.figure["data"]
    assert trace["name"] == "LEC"
    assert trace["x"] == [1, 2]
    assert trace["y"] == [85.5, 84.0]


def test_builds_lap_times_by_compound_chart():
    def load_laps(year, event, session_type, drivers):
        return [{"Driver": "LEC", "LapNumber": 1.0, "LapTime": timedelta(seconds=85.5), "Compound": "SOFT"}]

    result = build_preview(
        request("lap_times_by_compound", ["LEC"]), loaders=SimpleNamespace(load_laps=load_laps)
    )

    assert result.found is True
    [trace] = result.figure["data"]
    assert trace["name"] == "Macio"


def test_builds_telemetry_chart_from_each_drivers_fastest_lap():
    calls = []

    def load_telemetry(year, event, session_type, drivers, laps):
        calls.append((year, event, session_type, drivers, laps))
        return [
            {"Driver": "LEC", "LapNumber": 30.0, "Distance": 0.0, "Speed": 310.0, "Throttle": 100.0, "Brake": False, "nGear": 8},
            {"Driver": "LEC", "LapNumber": 30.0, "Distance": 50.0, "Speed": 200.0, "Throttle": 0.0, "Brake": True, "nGear": 4},
        ]

    result = build_preview(
        request("telemetry", ["LEC"]), loaders=SimpleNamespace(load_telemetry=load_telemetry)
    )

    assert calls == [(2024, "Monza", "Race", ["LEC"], None)]
    assert result.found is True
    speed_trace = result.figure["data"][0]
    assert speed_trace["name"] == "LEC"
    assert speed_trace["x"] == [0.0, 50.0]
    assert speed_trace["y"] == [310.0, 200.0]


def stint_lap(driver, lap_number):
    return {
        "Driver": driver, "LapNumber": float(lap_number), "Position": 1.0, "Stint": 1.0,
        "Compound": "HARD", "TyreLife": float(lap_number), "FreshTyre": True, "TrackStatus": "1",
    }


def test_builds_stints_chart_for_every_driver_when_none_are_requested():
    calls = []

    def load_stint_data(year, event, session_type):
        calls.append((year, event, session_type))
        return {
            "event_name": "Italian Grand Prix",
            "laps": [stint_lap("LEC", 1), stint_lap("NOR", 1)],
            "results": [{"Abbreviation": "LEC", "Position": 1.0}, {"Abbreviation": "NOR", "Position": 3.0}],
        }

    result = build_preview(request("stints"), loaders=SimpleNamespace(load_stint_data=load_stint_data))

    assert calls == [(2024, "Monza", "Race")]
    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Race"
    assert result.figure["layout"]["yaxis"]["categoryarray"] == ["LEC", "NOR"]


def pace_lap(driver, lap_number, seconds_since_start):
    return {
        "Driver": driver, "LapNumber": float(lap_number), "Time": timedelta(hours=1, seconds=seconds_since_start),
        "Stint": 1.0, "Position": 1.0, "TrackStatus": "1",
    }


def test_builds_race_pace_chart_for_the_requested_drivers():
    calls = []

    def load_race_pace_data(year, event, session_type):
        calls.append((year, event, session_type))
        return {
            "event_name": "Italian Grand Prix",
            "race_start": timedelta(hours=1),
            "laps": [pace_lap("LEC", 1, 90.0), pace_lap("NOR", 1, 92.0)],
            "results": [],
        }

    result = build_preview(
        request("race_pace", ["LEC"], session_type="Sprint"),
        loaders=SimpleNamespace(load_race_pace_data=load_race_pace_data),
    )

    assert calls == [(2024, "Monza", "Sprint")]
    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Sprint"
    [trace] = result.figure["data"]
    assert trace["name"] == "LEC"
    assert trace["y"] == [0.0, 1.0]


def test_builds_gap_to_winner_chart_for_the_requested_drivers():
    calls = []

    def load_race_pace_data(year, event, session_type):
        calls.append((year, event, session_type))
        return {
            "event_name": "Italian Grand Prix",
            "race_start": timedelta(hours=1),
            "laps": [pace_lap("LEC", 1, 90.0), pace_lap("NOR", 1, 92.0)],
            "results": [{"Abbreviation": "LEC", "Position": 1.0, "TeamName": "Ferrari", "TeamColor": "E8002D"}],
        }

    result = build_preview(
        request("gap_to_winner", ["LEC"], session_type="Sprint"),
        loaders=SimpleNamespace(load_race_pace_data=load_race_pace_data),
    )

    assert calls == [(2024, "Monza", "Sprint")]
    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Sprint"
    [trace] = result.figure["data"]
    assert trace["name"] == "LEC"
    assert trace["y"] == [0.0, 0.0]


def test_builds_top_speeds_chart_for_the_requested_drivers():
    calls = []

    def load_top_speeds(year, event, session_type, drivers):
        calls.append((year, event, session_type, drivers))
        return {
            "event_name": "Italian Grand Prix",
            "rows": [
                {"Driver": "LEC", "LapNumber": 1.0, "TopSpeed": 350.0},
                {"Driver": "LEC", "LapNumber": 2.0, "TopSpeed": 340.0},
            ],
        }

    result = build_preview(
        request("top_speeds", ["LEC"]), loaders=SimpleNamespace(load_top_speeds=load_top_speeds)
    )

    assert calls == [(2024, "Monza", "Race", ["LEC"])]
    assert result.found is True
    [table] = result.figure["data"]
    assert table["type"] == "table"
    assert table["cells"]["values"][0] == ["LEC"]


def test_builds_tyre_degradation_chart_from_the_requested_teams():
    def load_tyre_degradation(year, event, session_type):
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

    result = build_preview(
        request("tyre_degradation", ["Ferrari"]),
        loaders=SimpleNamespace(load_tyre_degradation=load_tyre_degradation),
    )

    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Race - Degradação de pneu"


def test_builds_speed_quadrant_chart_from_the_requested_teams():
    def load_speed_quadrant(year, event, session_type):
        return {
            "event_name": "Italian Grand Prix",
            "laps": [
                {"Team": "Ferrari", "TeamColor": "E8002D", "LapTime": timedelta(seconds=90.0),
                 "TopSpeed": 320.0, "LapDistance": 5000.0},
            ],
        }

    result = build_preview(
        request("speed_quadrant", ["Ferrari"]),
        loaders=SimpleNamespace(load_speed_quadrant=load_speed_quadrant),
    )

    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Race (Melhor volta de cada equipe)"


def test_builds_gg_diagram_chart_from_the_requested_drivers():
    def straight_line_telemetry(speed_kmh=200.0, n=10, dt=0.1):
        speed_ms = speed_kmh / 3.6
        rows = []
        for i in range(n):
            t = i * dt
            distance = speed_ms * t
            rows.append(
                {"Speed": speed_kmh, "Distance": distance, "Time": timedelta(seconds=t), "X": distance, "Y": 0.0}
            )
        return rows

    def load_gg_diagram(year, event, session_type, drivers):
        return {
            "event_name": "Italian Grand Prix",
            "drivers": [
                {"driver_code": driver, "compound": "SOFT", "telemetry": straight_line_telemetry()}
                for driver in drivers
            ],
        }

    result = build_preview(
        request("gg_diagram", ["VER", "HAM"]),
        loaders=SimpleNamespace(load_gg_diagram=load_gg_diagram),
    )

    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Race - Diagrama G-G"


def test_builds_speed_delta_trace_chart_from_the_requested_drivers():
    def load_speed_delta_trace(year, event, session_type, drivers, laps):
        return {
            "event_name": "Italian Grand Prix",
            "drivers": [
                {"driver_code": drivers[0], "distance": [0.0, 10.0], "speed": [280.0, 290.0]},
                {"driver_code": drivers[1], "distance": [0.0, 10.0], "speed": [275.0, 285.0]},
            ],
            "delta": {"distance": [0.0, 10.0], "seconds": [0.0, -0.08]},
            "corners": [{"number": 1, "distance": 5.0}],
        }

    result = build_preview(
        request("speed_delta_trace", ["VER", "HAM"]),
        loaders=SimpleNamespace(load_speed_delta_trace=load_speed_delta_trace),
    )

    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Race - Traço de velocidade com delta"


def test_builds_gap_to_pole_chart_for_every_driver_when_none_are_requested():
    def load_gap_to_pole(year, event, session_type, drivers):
        return {
            "event_name": "Italian Grand Prix",
            "drivers": [{"driver_code": "VER", "team_color": "0600EF", "lap_time": timedelta(seconds=90.0)}],
        }

    result = build_preview(request("gap_to_pole"), loaders=SimpleNamespace(load_gap_to_pole=load_gap_to_pole))

    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Race - Gap para a pole"


def test_builds_position_changes_chart_for_every_driver_when_none_are_requested():
    def load_position_changes(year, event, session_type, drivers):
        return {
            "event_name": "Italian Grand Prix",
            "laps": [{"Driver": "VER", "TeamColor": "0600EF", "LapNumber": 1, "Position": 1}],
        }

    result = build_preview(
        request("position_changes"), loaders=SimpleNamespace(load_position_changes=load_position_changes)
    )

    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Race - Posição por volta"


def test_builds_best_sectors_chart():
    def load_best_sectors(year, event, session_type):
        return {
            "event_name": "Italian Grand Prix",
            "laps": [
                {"driver_code": "VER", "team_color": "0600EF", "sector_1": timedelta(seconds=28.0),
                 "sector_2": timedelta(seconds=35.0), "sector_3": timedelta(seconds=27.0)},
            ],
        }

    result = build_preview(
        request("best_sectors"), loaders=SimpleNamespace(load_best_sectors=load_best_sectors)
    )

    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Race - Melhores setores"


def test_builds_qualifying_segments_bar_chart():
    def load_qualifying_segments(year, event):
        return {
            "event_name": "Italian Grand Prix",
            "teams": [
                {"team": "Ferrari", "team_color": "E8002D", "q1": timedelta(seconds=80.0),
                 "q2": timedelta(seconds=79.5), "q3": timedelta(seconds=79.0)},
            ],
        }

    result = build_preview(
        request("qualifying_segments_bar"),
        loaders=SimpleNamespace(load_qualifying_segments=load_qualifying_segments),
    )

    assert result.found is True
    assert result.figure["layout"]["title"] == "2024 Italian Grand Prix - Q3"


def test_reports_not_found_with_the_tools_reason_when_session_has_no_data():
    def load_laps(year, event, session_type, drivers):
        raise SessionDataUnavailable("No data for Monza 2024 Race")

    result = build_preview(request("lap_times", ["LEC"]), loaders=SimpleNamespace(load_laps=load_laps))

    assert result == PreviewResult(found=False, reason="No data for Monza 2024 Race")


def test_html_page_loads_plotly_and_embeds_the_figure_under_the_title():
    figure = {"data": [{"type": "scatter", "name": "LEC", "x": [1], "y": [85.5]}], "layout": {}}

    html = to_html(figure, title="lap_times 2024 Monza Race")

    assert "<title>lap_times 2024 Monza Race</title>" in html
    assert "plotly" in html and "<script src=" in html
    assert json.dumps(figure) in html
