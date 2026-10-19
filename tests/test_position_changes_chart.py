from dark_theme import assert_dark_theme

from f1llm.tools.position_changes import (
    DriverPositions,
    PositionChangesResponse,
    PositionPoint,
    build_position_changes_chart,
)


def point(lap_number, position):
    return PositionPoint(lap_number=lap_number, position=position)


def driver_positions(driver_code, points, team_color="#E8002D"):
    return DriverPositions(driver_code=driver_code, team_color=team_color, points=list(points))


def positions_response(drivers, event_name="Italian Grand Prix"):
    return PositionChangesResponse(found=True, event_name=event_name, drivers=list(drivers))


def test_chart_plots_one_line_per_driver_with_y_axis_inverted():
    result = positions_response([
        driver_positions("VER", [point(1, 2), point(2, 1)], team_color="#0600EF"),
        driver_positions("HAM", [point(1, 1), point(2, 2)], team_color="#27F4D2"),
    ])

    chart = build_position_changes_chart(result, year=2023, session_type="Race")

    traces_by_name = {t["name"]: t for t in chart["data"]}
    assert traces_by_name["VER"]["x"] == [1, 2]
    assert traces_by_name["VER"]["y"] == [2, 1]
    assert traces_by_name["VER"]["line"]["color"] == "#0600EF"
    assert traces_by_name["HAM"]["line"]["color"] == "#27F4D2"
    assert chart["layout"]["yaxis"]["autorange"] == "reversed"
    assert chart["layout"]["xaxis"]["title"] == "Volta"
    assert chart["layout"]["yaxis"]["title"] == "Posição"
    assert_dark_theme(chart["layout"])
