from f1llm.tools.tyre_degradation import (
    TeamCompoundDegradation,
    TyreDegradationPoint,
    TyreDegradationResponse,
    build_tyre_degradation_chart,
)


def point(tyre_age, lap_time):
    return TyreDegradationPoint(tyre_age=tyre_age, fuel_corrected_lap_time=lap_time)


def entry(team, compound, points, *, team_color="#E8002D", slope=None, r_squared=None):
    return TeamCompoundDegradation(
        team=team,
        compound=compound,
        team_color=team_color,
        points=list(points),
        slope=slope,
        r_squared=r_squared,
    )


def degradation_response(entries, event_name="Italian Grand Prix"):
    return TyreDegradationResponse(found=True, event_name=event_name, entries=list(entries))


def point_traces(chart):
    return [trace for trace in chart["data"] if trace["mode"] == "markers"]


def line_traces(chart):
    return [trace for trace in chart["data"] if trace["mode"] == "lines"]


def legend_shown_traces(chart):
    return [trace["name"] for trace in chart["data"] if trace.get("showlegend") is True]


def test_chart_plots_each_entrys_points_in_its_compounds_subplot():
    result = degradation_response([
        entry("FERRARI", "SOFT", [point(1, 90.0), point(2, 90.5)], team_color="#E8002D"),
        entry("MERCEDES", "HARD", [point(1, 91.0)], team_color="#27F4D2"),
    ])

    chart = build_tyre_degradation_chart(result, year=2023, session_type="Race")

    traces = {trace["name"]: trace for trace in point_traces(chart)}
    assert traces["FERRARI"]["x"] == [1, 2]
    assert traces["FERRARI"]["y"] == [90.0, 90.5]
    assert traces["FERRARI"]["marker"]["color"] == "#E8002D"
    assert traces["FERRARI"]["xaxis"] == "x3"  # SOFT is the 3rd subplot
    assert traces["FERRARI"]["yaxis"] == "y3"

    assert traces["MERCEDES"]["xaxis"] == "x"  # HARD is the 1st subplot
    assert traces["MERCEDES"]["yaxis"] == "y"


def test_chart_draws_a_trend_line_when_the_entry_has_a_slope():
    result = degradation_response([
        entry("FERRARI", "SOFT",
              [point(1, 90.0), point(2, 90.1), point(3, 90.2)],
              team_color="#E8002D", slope=0.1),
    ])

    chart = build_tyre_degradation_chart(result, year=2023, session_type="Race")

    [line] = line_traces(chart)
    assert line["x"] == [1, 3]
    assert line["y"] == [90.0, 90.2]
    assert line["line"]["color"] == "#E8002D"
    assert line["xaxis"] == "x3"
    assert line["yaxis"] == "y3"


def test_chart_omits_the_trend_line_when_the_entry_has_no_slope():
    result = degradation_response([
        entry("FERRARI", "SOFT", [point(1, 90.0)], slope=None),
    ])

    chart = build_tyre_degradation_chart(result, year=2023, session_type="Race")

    assert line_traces(chart) == []


def test_chart_shows_each_team_once_in_the_legend_even_across_compounds():
    result = degradation_response([
        entry("FERRARI", "HARD", [point(1, 91.0)]),
        entry("FERRARI", "MEDIUM", [point(1, 90.5)]),
        entry("MERCEDES", "SOFT", [point(1, 89.0)]),
    ])

    chart = build_tyre_degradation_chart(result, year=2023, session_type="Race")

    assert legend_shown_traces(chart) == ["FERRARI", "MERCEDES"]


def test_chart_places_the_3_compound_subplots_side_by_side_with_titled_axes():
    result = degradation_response([entry("FERRARI", "HARD", [point(1, 91.0)])])

    chart = build_tyre_degradation_chart(result, year=2023, session_type="Race")

    layout = chart["layout"]
    assert layout["xaxis"]["domain"] == [0.0, 0.3]
    assert layout["xaxis2"]["domain"] == [0.35, 0.65]
    assert layout["xaxis3"]["domain"] == [0.7, 1.0]
    for axis in ["xaxis", "xaxis2", "xaxis3"]:
        assert layout[axis]["title"] == "Idade do pneu (voltas)"
        assert layout[axis]["showgrid"] is True
    assert layout["yaxis"]["title"] == "Tempo de volta corrigido por combustível (s)"
    for axis in ["yaxis", "yaxis2", "yaxis3"]:
        assert layout[axis]["showgrid"] is True


def test_chart_uses_the_same_y_axis_range_across_all_3_subplots():
    result = degradation_response([
        entry("FERRARI", "HARD", [point(1, 85.0)]),
        entry("MERCEDES", "SOFT", [point(1, 95.0)]),
    ])

    chart = build_tyre_degradation_chart(result, year=2023, session_type="Race")

    layout = chart["layout"]
    assert layout["yaxis"]["range"] == [85.0, 95.0]
    assert layout["yaxis2"]["range"] == [85.0, 95.0]
    assert layout["yaxis3"]["range"] == [85.0, 95.0]


def test_chart_labels_each_subplot_with_its_compounds_portuguese_name():
    result = degradation_response([entry("FERRARI", "HARD", [point(1, 91.0)])])

    chart = build_tyre_degradation_chart(result, year=2023, session_type="Race")

    annotations = {a["text"]: a for a in chart["layout"]["annotations"]}
    assert set(annotations) == {"Duro", "Médio", "Macio"}
    assert annotations["Duro"]["xref"] == "x domain"
    assert annotations["Médio"]["xref"] == "x2 domain"
    assert annotations["Macio"]["xref"] == "x3 domain"


def test_chart_title_background_and_legend():
    result = degradation_response([entry("FERRARI", "HARD", [point(1, 91.0)])], event_name="Monza Grand Prix")

    chart = build_tyre_degradation_chart(result, year=2023, session_type="Race")

    layout = chart["layout"]
    assert layout["title"] == "2023 Monza Grand Prix - Race - Degradação de pneu"
    assert layout["paper_bgcolor"] == "#ffffff"
    assert layout["plot_bgcolor"] == "#ffffff"
    assert layout["legend"]["title"]["text"] == "Equipe"
