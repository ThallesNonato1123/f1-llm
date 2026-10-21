from f1llm.tools.speed_quadrant import (
    SpeedQuadrantResponse,
    TeamSpeedPoint,
    build_speed_quadrant_chart,
)


def team_point(team, *, mean_speed, top_speed, team_color="#E8002D"):
    return TeamSpeedPoint(team=team, team_color=team_color, mean_speed=mean_speed, top_speed=top_speed)


def quadrant_response(teams, event_name="Italian Grand Prix"):
    return SpeedQuadrantResponse(found=True, event_name=event_name, teams=list(teams))


def test_chart_plots_one_point_per_team_colored_with_its_name_shown():
    result = quadrant_response([
        team_point("FERRARI", mean_speed=200.0, top_speed=320.0, team_color="#E8002D"),
        team_point("MERCEDES", mean_speed=195.0, top_speed=315.0, team_color="#27F4D2"),
    ])

    chart = build_speed_quadrant_chart(result, year=2023, session_type="Qualifying")

    [trace] = [t for t in chart["data"] if t["type"] == "scatter"]
    assert trace["x"] == [200.0, 195.0]
    assert trace["y"] == [320.0, 315.0]
    assert trace["text"] == ["FERRARI", "MERCEDES"]
    assert trace["marker"]["color"] == ["#E8002D", "#27F4D2"]


def test_chart_has_no_region_annotations_crowding_the_plot_area():
    # Region hints used to be 8 arrow annotations converging on the data's
    # mean point; with closely-clustered teams they all overlapped into an
    # unreadable mess. The quadrant reading now lives in the axis titles
    # instead, which never collide with the data.
    result = quadrant_response([
        team_point("FERRARI", mean_speed=200.0, top_speed=320.0),
        team_point("MERCEDES", mean_speed=195.0, top_speed=315.0),
    ])

    chart = build_speed_quadrant_chart(result, year=2023, session_type="Qualifying")

    assert "annotations" not in chart["layout"]


def test_chart_title_axes_and_background():
    result = quadrant_response(
        [team_point("FERRARI", mean_speed=200.0, top_speed=320.0)],
        event_name="Monza Grand Prix",
    )

    chart = build_speed_quadrant_chart(result, year=2023, session_type="Qualifying")

    layout = chart["layout"]
    assert layout["title"] == "2023 Monza Grand Prix - Qualifying (Melhor volta de cada equipe)"
    assert layout["xaxis"]["title"] == "Velocidade média (km/h)"
    assert layout["xaxis"]["showgrid"] is True
    assert layout["yaxis"]["title"] == "Velocidade máxima (km/h)"
    assert layout["yaxis"]["showgrid"] is True
    assert layout["paper_bgcolor"] == "#111111"
    assert layout["plot_bgcolor"] == "#111111"
