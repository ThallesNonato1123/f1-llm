from f1llm.tools.qualifying_segments import (
    QualifyingSegmentsResponse,
    TeamSegmentTime,
    build_qualifying_pace_evolution_chart,
    build_qualifying_segment_bar_chart,
)


def team(name, q1=None, q2=None, q3=None, team_color="#E8002D"):
    return TeamSegmentTime(team=name, team_color=team_color, q1_seconds=q1, q2_seconds=q2, q3_seconds=q3)


def segments_response(teams, event_name="Italian Grand Prix"):
    return QualifyingSegmentsResponse(found=True, event_name=event_name, teams=list(teams))


def test_segment_bar_chart_shows_gap_to_the_fastest_in_the_chosen_segment():
    result = segments_response([
        team("Ferrari", q1=80.0, q2=79.5, q3=79.0),
        team("Mercedes", q1=80.5, q2=79.8, q3=None),  # out in Q2
        team("Haas", q1=81.0, q2=None, q3=None),  # out in Q1
    ])

    chart = build_qualifying_segment_bar_chart(result, year=2023, segment="Q2")

    [bar] = chart["data"]
    assert bar["type"] == "bar"
    assert bar["orientation"] == "h"
    assert bar["y"] == ["Ferrari", "Mercedes"]
    assert bar["x"] == [0.0, 0.3]
    assert chart["layout"]["title"] == "2023 Italian Grand Prix - Q2"


def test_pace_evolution_chart_plots_each_teams_time_across_the_segments_it_reached():
    result = segments_response([
        team("Ferrari", q1=80.0, q2=79.5, q3=79.0, team_color="#E8002D"),
        team("Haas", q1=81.0, q2=None, q3=None, team_color="#B6BABD"),
    ])

    chart = build_qualifying_pace_evolution_chart(result, year=2023)

    traces_by_name = {t["name"]: t for t in chart["data"]}
    assert traces_by_name["Ferrari"]["x"] == ["Q1", "Q2", "Q3"]
    assert traces_by_name["Ferrari"]["y"] == [80.0, 79.5, 79.0]
    assert traces_by_name["Haas"]["x"] == ["Q1"]
    assert traces_by_name["Haas"]["y"] == [81.0]
