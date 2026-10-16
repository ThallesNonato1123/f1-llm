import pytest

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.top_speeds import DriverTopSpeeds, TopSpeedsResponse, build_top_speeds_chart, get_top_speeds


def row(driver, lap_number, speed):
    return {"Driver": driver, "LapNumber": lap_number, "TopSpeed": speed}


def speeds_data(rows, event_name="Abu Dhabi Grand Prix"):
    return {"event_name": event_name, "rows": rows}


def test_keeps_only_the_15_fastest_laps_per_driver_sorted_descending():
    # VER: 20 laps at speeds 300..319 (20 distinct values); keep only the top 15.
    data = speeds_data([row("VER", lap, 300 + lap) for lap in range(1, 21)])

    result = get_top_speeds(
        year=2021, event="Abu Dhabi", session_type="Race",
        load_top_speeds=lambda year, event, session_type, drivers: data,
    )

    assert result.found is True
    assert result.event_name == "Abu Dhabi Grand Prix"
    ver = result.drivers[0]
    assert ver.driver_code == "VER"
    assert ver.top_speeds == [320.0 - i for i in range(15)]
    assert len(ver.top_speeds) == 15


def test_sorts_drivers_by_their_own_top_speed_descending_and_reports_the_session_max():
    data = speeds_data([
        row("HAM", 1, 350.0),
        row("VER", 1, 340.0), row("VER", 2, 345.0),
        row("GAS", 1, 330.0),
    ])

    result = get_top_speeds(
        year=2021, event="Abu Dhabi", session_type="Race",
        load_top_speeds=lambda year, event, session_type, drivers: data,
    )

    assert [driver.driver_code for driver in result.drivers] == ["HAM", "VER", "GAS"]
    assert result.session_max == 350.0


def test_averages_only_the_laps_a_driver_actually_has():
    data = speeds_data([row("VER", 1, 300.0), row("VER", 2, 310.0)])  # fewer than 15 laps

    result = get_top_speeds(
        year=2021, event="Abu Dhabi", session_type="Race",
        load_top_speeds=lambda year, event, session_type, drivers: data,
    )

    ver = result.drivers[0]
    assert ver.top_speeds == [310.0, 300.0]
    assert ver.average == pytest.approx(305.0)


def test_forwards_the_requested_drivers_to_the_loader():
    calls = []

    def load(year, event, session_type, drivers):
        calls.append(drivers)
        return speeds_data([row("VER", 1, 300.0)])

    get_top_speeds(
        year=2021, event="Abu Dhabi", session_type="Race",
        drivers=["VER", "HAM"],
        load_top_speeds=load,
    )

    assert calls == [["VER", "HAM"]]


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type, drivers):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_top_speeds(
        year=2023, event="Imaginary Grand Prix", session_type="Race",
        load_top_speeds=raise_not_found,
    )

    assert result.found is False
    assert result.drivers is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"


def driver_speeds(code, speeds, average=None):
    return DriverTopSpeeds(driver_code=code, top_speeds=speeds, average=average if average is not None else sum(speeds) / len(speeds))


def speeds_response(drivers, event_name="Abu Dhabi Grand Prix"):
    return TopSpeedsResponse(
        found=True, event_name=event_name, drivers=drivers,
        session_max=max(speed for driver in drivers for speed in driver.top_speeds),
    )


def test_chart_table_has_one_row_per_driver_padded_to_15_laps_plus_average():
    result = speeds_response([
        driver_speeds("HAM", [350.0, 338.0]),
        driver_speeds("VER", list(range(330, 315, -1))),  # 15 laps, no padding needed
    ])

    chart = build_top_speeds_chart(result, year=2026, session_type="Race")

    [table] = chart["data"]
    assert table["type"] == "table"
    columns = table["cells"]["values"]
    # column 0 = driver codes, columns 1..15 = laps, column 16 = average
    assert columns[0] == ["HAM", "VER"]
    assert columns[1] == ["350", "330"]
    assert columns[2] == ["338", "329"]
    assert columns[3] == [None, "328"]  # HAM only has 2 laps: rest is blank
    assert columns[15] == [None, "316"]
    assert columns[16] == ["344.0", "323.0"]  # average column
    assert table["header"]["values"] == (
        ["Piloto"] + [str(n) for n in range(1, 16)] + ["Média"]
    )


def test_chart_colors_non_max_cells_along_a_dark_purple_to_yellow_scale():
    # Lap 1 (360.0) is the session max: it gets the highlight color (tested separately),
    # not a Plasma color, so it's excluded from this scale check.
    result = speeds_response([driver_speeds("HAM", [360.0, 350.0, 330.0, 310.0])])

    chart = build_top_speeds_chart(result, year=2026, session_type="Race")

    [table] = chart["data"]
    colors = [table["cells"]["fill"]["color"][lap][0] for lap in range(1, 5)]
    assert colors[0] == "#fff59d"  # lap 1 (360.0): the session max, highlighted
    assert colors[3] == "#0d0887"  # lap 4 (310.0): the slowest value, bottom of the scale
    assert colors[1] != colors[2] != colors[3]  # strictly different colors across the scale
    # The driver-code column stays uncolored (not part of the heatmap).
    assert table["cells"]["fill"]["color"][0][0] not in colors


def test_chart_highlights_the_single_fastest_cell_in_the_session():
    result = speeds_response([
        driver_speeds("HAM", [350.0, 338.0]),
        driver_speeds("VER", [340.0, 330.0]),
    ])

    chart = build_top_speeds_chart(result, year=2026, session_type="Race")

    [table] = chart["data"]
    colors = table["cells"]["fill"]["color"]
    assert colors[1][0] == "#fff59d"  # HAM's 350.0, the session's single highest value
    assert colors[1][1] != "#fff59d"  # VER's 340.0 is high but not the session max
    assert colors[2][0] != "#fff59d"  # HAM's own second-best lap isn't the max either


def test_chart_height_grows_with_the_number_of_drivers():
    few = speeds_response([driver_speeds("VER", [330.0]), driver_speeds("HAM", [320.0])])
    many = speeds_response([driver_speeds(f"D{i}", [300.0 + i]) for i in range(20)])

    few_chart = build_top_speeds_chart(few, year=2021, session_type="Race")
    many_chart = build_top_speeds_chart(many, year=2021, session_type="Race")

    assert many_chart["layout"]["height"] > few_chart["layout"]["height"]


def test_chart_rounds_lap_speeds_to_whole_numbers_and_average_to_one_decimal():
    result = speeds_response([driver_speeds("VER", [330.6666, 320.3333], average=325.49999)])

    chart = build_top_speeds_chart(result, year=2021, session_type="Race")

    [table] = chart["data"]
    values = table["cells"]["values"]
    assert values[1][0] == "331"  # lap 1, rounded to a whole number
    assert values[2][0] == "320"  # lap 2
    assert values[16][0] == "325.5"  # average, one decimal


def test_chart_title_footer_and_background():
    result = speeds_response([driver_speeds("VER", [330.0])], event_name="Belgian Grand Prix")

    chart = build_top_speeds_chart(result, year=2026, session_type="Qualifying")

    layout = chart["layout"]
    assert layout["title"] == "2026 Belgian Grand Prix - Qualifying - Velocidade máxima (km/h) por volta"
    assert layout["annotations"][0]["text"] == (
        "Voltas ordenadas pela velocidade máxima (15 melhores exibidas, média à direita)"
    )
    assert layout["paper_bgcolor"] == "#ffffff"
    assert layout["plot_bgcolor"] == "#ffffff"


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_top_speeds(year=2023, event="Bahrain", session_type="Practice")


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_top_speeds(year=2017, event="Bahrain", session_type="Race")
