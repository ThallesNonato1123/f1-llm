from f1llm.tools.gap_to_pole import (
    DriverGapToPole,
    GapToPoleResponse,
    build_gap_to_pole_chart,
)


def driver(driver_code, gap_seconds, team_color="#E8002D", lap_time_seconds=90.0):
    return DriverGapToPole(
        driver_code=driver_code, team_color=team_color, lap_time_seconds=lap_time_seconds, gap_seconds=gap_seconds
    )


def gap_response(drivers, event_name="Italian Grand Prix"):
    return GapToPoleResponse(found=True, event_name=event_name, drivers=list(drivers))


def test_chart_draws_a_horizontal_bar_per_driver_colored_by_team_fastest_on_top():
    result = gap_response([
        driver("VER", 0.0, team_color="#0600EF"),
        driver("LEC", 0.8, team_color="#E8002D"),
        driver("HAM", 1.5, team_color="#27F4D2"),
    ])

    chart = build_gap_to_pole_chart(result, year=2023, session_type="Qualifying")

    [bar] = chart["data"]
    assert bar["type"] == "bar"
    assert bar["orientation"] == "h"
    assert bar["y"] == ["VER", "LEC", "HAM"]
    assert bar["x"] == [0.0, 0.8, 1.5]
    assert bar["marker"]["color"] == ["#0600EF", "#E8002D", "#27F4D2"]
    assert chart["layout"]["yaxis"]["autorange"] == "reversed"
    assert chart["layout"]["paper_bgcolor"] == "#ffffff"
    assert chart["layout"]["plot_bgcolor"] == "#ffffff"
