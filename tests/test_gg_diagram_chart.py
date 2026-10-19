from f1llm.tools.gg_diagram import (
    AccelerationPoint,
    DriverAcceleration,
    GGDiagramResponse,
    build_gg_diagram_chart,
)
from f1llm.tools.telemetry import DRIVER_COLORS


def point(lateral, longitudinal):
    return AccelerationPoint(lateral=lateral, longitudinal=longitudinal)


def driver_accel(driver_code, compound, points, average_combined_g=0.0):
    return DriverAcceleration(
        driver_code=driver_code, compound=compound, points=list(points), average_combined_g=average_combined_g
    )


def gg_response(drivers, event_name="Italian Grand Prix"):
    return GGDiagramResponse(found=True, event_name=event_name, drivers=list(drivers))


def point_traces(chart):
    return [t for t in chart["data"] if t["mode"] == "markers"]


def envelope_traces(chart):
    return [t for t in chart["data"] if t["mode"] == "lines"]


def test_chart_plots_each_drivers_points_colored_and_semi_transparent():
    result = gg_response([
        driver_accel("VER", "SOFT", [point(0.5, 0.2), point(-0.3, 1.0)]),
        driver_accel("HAM", "MEDIUM", [point(0.1, -0.5)]),
    ])

    chart = build_gg_diagram_chart(result, year=2023, session_type="Qualifying")

    traces_by_name = {t["name"]: t for t in point_traces(chart)}
    assert traces_by_name["VER"]["x"] == [0.5, -0.3]
    assert traces_by_name["VER"]["y"] == [0.2, 1.0]
    assert traces_by_name["VER"]["marker"]["color"] == DRIVER_COLORS[0]
    assert traces_by_name["VER"]["marker"]["opacity"] < 1.0
    assert traces_by_name["HAM"]["marker"]["color"] == DRIVER_COLORS[1]


def test_chart_draws_a_dashed_envelope_around_each_drivers_convex_hull():
    # A square with one interior point: the hull is just the 4 corners.
    result = gg_response([
        driver_accel("VER", "SOFT", [
            point(1, 1), point(1, -1), point(-1, -1), point(-1, 1), point(0, 0),
        ]),
    ])

    chart = build_gg_diagram_chart(result, year=2023, session_type="Qualifying")

    [envelope] = envelope_traces(chart)
    assert envelope["name"] == "VER"
    assert envelope["line"]["color"] == DRIVER_COLORS[0]
    assert envelope["line"]["dash"] == "dash"
    assert envelope["showlegend"] is False

    hull_points = set(zip(envelope["x"], envelope["y"]))
    assert hull_points == {(1, 1), (1, -1), (-1, -1), (-1, 1)}
    # Closed loop: the line comes back to its starting point.
    assert (envelope["x"][0], envelope["y"][0]) == (envelope["x"][-1], envelope["y"][-1])


def test_chart_skips_the_envelope_when_the_points_are_collinear_or_identical():
    # A straight line (or all-identical points) has no 2D convex hull.
    result = gg_response([
        driver_accel("VER", "SOFT", [point(0, 0)] * 10),
    ])

    chart = build_gg_diagram_chart(result, year=2023, session_type="Qualifying")

    assert envelope_traces(chart) == []
    assert len(point_traces(chart)) == 1  # the points themselves still render


def test_chart_shows_each_drivers_average_combined_acceleration_with_compound_letter():
    result = gg_response([
        driver_accel("NOR", "SOFT", [point(0.5, 0.5)], average_combined_g=2.041),
        driver_accel("HAM", "MEDIUM", [point(0.1, 0.1)], average_combined_g=1.837),
    ])

    chart = build_gg_diagram_chart(result, year=2023, session_type="Qualifying")

    texts = {a["text"] for a in chart["layout"]["annotations"]}
    assert "NOR (S) Average Accel = 2.04g" in texts
    assert "HAM (M) Average Accel = 1.84g" in texts


def test_chart_axes_circles_theme_title_and_footnote():
    result = gg_response(
        [driver_accel("VER", "SOFT", [point(2.3, -1.1), point(0.5, 0.5)])],
        event_name="Monza Grand Prix",
    )

    chart = build_gg_diagram_chart(result, year=2023, session_type="Qualifying")
    layout = chart["layout"]

    assert layout["title"] == "2023 Monza Grand Prix - Qualifying - Diagrama G-G"
    assert layout["paper_bgcolor"] == "#111111"
    assert layout["plot_bgcolor"] == "#111111"

    # Symmetric around 0, wide enough to fit the largest magnitude (2.3 -> 3).
    assert layout["xaxis"]["range"] == [-3, 3]
    assert layout["yaxis"]["range"] == [-3, 3]
    assert layout["yaxis"]["scaleanchor"] == "x"
    assert layout["yaxis"]["scaleratio"] == 1

    circle_shapes = [s for s in layout["shapes"] if s["type"] == "circle"]
    assert len(circle_shapes) == 3  # 1g, 2g, 3g

    annotation_texts = {a["text"] for a in layout["annotations"]}
    assert "Curvas à Direita ← → Curvas à Esquerda" in annotation_texts
    assert "Frenagem / Tração" in annotation_texts
    assert "Pontos distantes do centro indicam alta aderência" in annotation_texts
