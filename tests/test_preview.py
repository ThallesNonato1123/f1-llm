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
            {"Driver": "LEC", "LapNumber": 1.0, "LapTime": timedelta(seconds=85.5)},
            {"Driver": "LEC", "LapNumber": 2.0, "LapTime": timedelta(seconds=84.0)},
        ]

    result = build_preview(request("lap_times", ["LEC"]), loaders=SimpleNamespace(load_laps=load_laps))

    assert calls == [(2024, "Monza", "Race", ["LEC"])]
    assert result.found is True
    [trace] = result.figure["data"]
    assert trace["name"] == "LEC"
    assert trace["x"] == [1, 2]
    assert trace["y"] == [85.5, 84.0]


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
