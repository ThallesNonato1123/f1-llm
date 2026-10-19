from dark_theme import assert_dark_theme

from f1llm.tools.speed_delta_trace import (
    Corner,
    DeltaPoint,
    DriverSpeedTrace,
    SpeedDeltaTraceResponse,
    SpeedTracePoint,
    build_speed_delta_trace_chart,
)
from f1llm.tools.telemetry import DRIVER_COLORS


def speed_point(distance, speed):
    return SpeedTracePoint(distance=distance, speed=speed)


def driver_trace(driver_code, points):
    return DriverSpeedTrace(driver_code=driver_code, points=list(points))


def delta_point(distance, seconds):
    return DeltaPoint(distance=distance, seconds=seconds)


def corner(number, distance):
    return Corner(number=number, distance=distance)


def trace_response(drivers, delta=(), corners=(), event_name="Italian Grand Prix"):
    return SpeedDeltaTraceResponse(
        found=True, event_name=event_name, drivers=list(drivers), delta=list(delta), corners=list(corners)
    )


def line_traces(chart):
    return [t for t in chart["data"] if t["type"] == "scatter" and t["mode"] == "lines"]


def test_chart_plots_each_drivers_speed_trace_in_its_own_color():
    result = trace_response([
        driver_trace("VER", [speed_point(0.0, 280.0), speed_point(50.0, 290.0)]),
        driver_trace("HAM", [speed_point(0.0, 275.0), speed_point(50.0, 285.0)]),
    ])

    chart = build_speed_delta_trace_chart(result, year=2023, session_type="Qualifying")

    traces_by_name = {t["name"]: t for t in line_traces(chart) if t["name"] in {"VER", "HAM"}}
    assert traces_by_name["VER"]["x"] == [0.0, 50.0]
    assert traces_by_name["VER"]["y"] == [280.0, 290.0]
    assert traces_by_name["VER"]["line"]["color"] == DRIVER_COLORS[0]
    assert traces_by_name["HAM"]["line"]["color"] == DRIVER_COLORS[1]


def test_chart_plots_the_delta_as_a_white_dashed_line_on_a_secondary_axis():
    result = trace_response(
        [driver_trace("VER", [speed_point(0.0, 280.0)]), driver_trace("HAM", [speed_point(0.0, 275.0)])],
        delta=[delta_point(0.0, 0.0), delta_point(50.0, -0.12)],
    )

    chart = build_speed_delta_trace_chart(result, year=2023, session_type="Qualifying")

    [delta_trace] = [t for t in line_traces(chart) if t["name"] == "Delta"]
    assert delta_trace["x"] == [0.0, 50.0]
    assert delta_trace["y"] == [0.0, -0.12]
    assert delta_trace["line"]["color"] == "#ffffff"
    assert delta_trace["line"]["dash"] == "dash"
    assert delta_trace["yaxis"] == "y2"


def test_chart_marks_each_corner_with_a_dotted_vertical_line_and_its_number():
    result = trace_response(
        [driver_trace("VER", [speed_point(0.0, 280.0)]), driver_trace("HAM", [speed_point(0.0, 275.0)])],
        corners=[corner(1, 350.0), corner(2, 820.0)],
    )

    chart = build_speed_delta_trace_chart(result, year=2023, session_type="Qualifying")

    corner_lines = [s for s in chart["layout"]["shapes"] if s["type"] == "line"]
    assert [(line["x0"], line["x1"]) for line in corner_lines] == [(350.0, 350.0), (820.0, 820.0)]
    for line in corner_lines:
        assert line["line"]["dash"] == "dot"

    corner_labels = {a["text"] for a in chart["layout"]["annotations"]}
    assert corner_labels == {"1", "2"}


def test_chart_title_axes_and_dark_theme():
    result = trace_response(
        [driver_trace("VER", [speed_point(0.0, 280.0)]), driver_trace("HAM", [speed_point(0.0, 275.0)])],
        event_name="Monza Grand Prix",
    )

    chart = build_speed_delta_trace_chart(result, year=2023, session_type="Qualifying")
    layout = chart["layout"]

    assert layout["title"] == "2023 Monza Grand Prix - Qualifying - Traço de velocidade com delta"
    assert layout["xaxis"]["title"] == "Distância (m)"
    assert layout["xaxis"]["showgrid"] is True
    assert layout["yaxis"]["title"] == "Velocidade (km/h)"
    assert layout["yaxis"]["showgrid"] is True
    assert layout["yaxis2"]["title"] == "Delta (s)"
    assert layout["yaxis2"]["overlaying"] == "y"
    assert layout["yaxis2"]["side"] == "right"
    assert_dark_theme(layout)
