from datetime import timedelta

import pytest
from dark_theme import assert_dark_theme

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.race_pace import DriverPace, RacePaceResponse, build_race_pace_chart, get_race_pace
from f1llm.track_status import SafetyCarPeriod

RACE_START = timedelta(hours=1)


def lap(driver, lap_number, seconds_since_start, *, stint=1.0, position=1.0, track_status="1"):
    return {
        "Driver": driver,
        "LapNumber": float(lap_number),
        "Time": RACE_START + timedelta(seconds=seconds_since_start),
        "Stint": stint,
        "Position": position,
        "TrackStatus": track_status,
    }


def pace_data(laps, results=None, event_name="Abu Dhabi Grand Prix"):
    return {
        "event_name": event_name,
        "race_start": RACE_START,
        "laps": laps,
        "results": results if results is not None else [],
    }


def result_row(driver, position, team_name="Team", team_color="123456"):
    return {"Abbreviation": driver, "Position": position, "TeamName": team_name, "TeamColor": team_color}


def two_driver_race():
    # VER laps: 90, 90, 90 s. HAM laps: 92, 91, 89 s.
    # Reference laps (average): 91, 90.5, 89.5 -> cumulative 91, 181.5, 271.
    return pace_data(
        laps=[
            lap("VER", 1, 90), lap("VER", 2, 180), lap("VER", 3, 270),
            lap("HAM", 1, 92, position=2.0), lap("HAM", 2, 183, position=2.0), lap("HAM", 3, 272, position=2.0),
        ],
        results=[result_row("VER", 1.0), result_row("HAM", 2.0)],
    )


def test_gap_to_reference_is_the_cumulative_difference_to_the_average_lap_time():
    data = two_driver_race()

    result = get_race_pace(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    assert result.found is True
    gaps = {driver.driver_code: driver.gaps_to_reference for driver in result.drivers}
    assert gaps["VER"] == pytest.approx([1.0, 1.5, 1.0])
    assert gaps["HAM"] == pytest.approx([-1.0, -1.5, -1.0])


def test_reference_uses_every_driver_even_when_only_some_are_requested():
    data = two_driver_race()

    result = get_race_pace(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        drivers=["VER"],
        load_race_pace_data=lambda year, event, session_type: data,
    )

    assert [driver.driver_code for driver in result.drivers] == ["VER"]
    assert result.drivers[0].gaps_to_reference == pytest.approx([1.0, 1.5, 1.0])


def test_retired_driver_line_ends_and_later_reference_laps_average_only_remaining_drivers():
    # VER: 90, 90, 90. HAM: 92, 91, then retires. LEC: 88, 89, 91.
    # Reference laps: (90+92+88)/3 = 90, (90+91+89)/3 = 90, (90+91)/2 = 90.5
    # -> cumulative 90, 180, 270.5.
    data = pace_data(
        laps=[
            lap("VER", 1, 90), lap("VER", 2, 180), lap("VER", 3, 270),
            lap("HAM", 1, 92, position=3.0), lap("HAM", 2, 183, position=3.0),
            lap("LEC", 1, 88, position=2.0), lap("LEC", 2, 177, position=2.0), lap("LEC", 3, 268, position=2.0),
        ],
        results=[result_row("VER", 1.0), result_row("LEC", 2.0), result_row("HAM", 3.0)],
    )

    result = get_race_pace(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    gaps = {driver.driver_code: driver.gaps_to_reference for driver in result.drivers}
    assert gaps["VER"] == pytest.approx([0.0, 0.0, 0.5])
    assert gaps["HAM"] == pytest.approx([-2.0, -3.0])
    assert gaps["LEC"] == pytest.approx([2.0, 3.0, 2.5])


def test_reference_excludes_laps_of_drivers_already_lapped_by_the_leader():
    # VER laps: 90 s each (ends laps at 90, 180, 270, 360). RUS laps: 130 s each (130, 260, 390).
    # RUS ends lap 3 at 390 s, after VER already ended lap 4 at 360 s: lapped, so his lap 3
    # stays out of the reference. Reference laps: (90+130)/2 = 110, 110, then 90, 90
    # -> cumulative 110, 220, 310, 400.
    data = pace_data(
        laps=[
            lap("VER", 1, 90), lap("VER", 2, 180), lap("VER", 3, 270), lap("VER", 4, 360),
            lap("RUS", 1, 130, position=2.0), lap("RUS", 2, 260, position=2.0), lap("RUS", 3, 390, position=2.0),
        ],
        results=[result_row("VER", 1.0), result_row("RUS", 2.0)],
    )

    result = get_race_pace(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    gaps = {driver.driver_code: driver.gaps_to_reference for driver in result.drivers}
    assert gaps["VER"] == pytest.approx([20.0, 40.0, 40.0, 40.0])
    assert gaps["RUS"] == pytest.approx([-20.0, -40.0, -80.0])


def test_pit_out_laps_are_the_first_lap_of_each_new_stint():
    data = pace_data(
        laps=[
            lap("VER", 1, 90), lap("VER", 2, 180), lap("VER", 3, 270), lap("VER", 4, 360),
            lap("HAM", 1, 92, stint=1.0, position=2.0),
            lap("HAM", 2, 183, stint=2.0, position=2.0),
            lap("HAM", 3, 272, stint=2.0, position=2.0),
            lap("HAM", 4, 361, stint=3.0, position=2.0),
        ],
        results=[result_row("VER", 1.0), result_row("HAM", 2.0)],
    )

    result = get_race_pace(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    pit_out_laps = {driver.driver_code: driver.pit_out_laps for driver in result.drivers}
    assert pit_out_laps == {"VER": [], "HAM": [2, 4]}


def test_rejects_qualifying_because_race_pace_needs_a_race_distance():
    with pytest.raises(ValueError, match="session_type"):
        get_race_pace(year=2021, event="Abu Dhabi", session_type="Qualifying")


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_race_pace(year=2017, event="Abu Dhabi", session_type="Race")


def test_rejects_empty_drivers_list():
    with pytest.raises(ValueError, match="drivers"):
        get_race_pace(year=2021, event="Abu Dhabi", session_type="Race", drivers=[])


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2021 Race")

    result = get_race_pace(
        year=2021,
        event="Imaginary Grand Prix",
        session_type="Race",
        load_race_pace_data=raise_not_found,
    )

    assert result.found is False
    assert result.drivers is None
    assert result.reason == "No data for Imaginary Grand Prix 2021 Race"


def test_reports_not_found_when_no_requested_driver_took_part():
    data = two_driver_race()

    result = get_race_pace(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        drivers=["ZZZ"],
        load_race_pace_data=lambda year, event, session_type: data,
    )

    assert result.found is False
    assert result.drivers is None
    assert "ZZZ" in result.reason


def test_orders_drivers_by_final_position_with_unclassified_drivers_last():
    data = pace_data(
        laps=[lap("LEC", 1, 88), lap("HAM", 1, 92), lap("VER", 1, 90)],
        results=[result_row("VER", 1.0), result_row("HAM", 2.0), result_row("LEC", None)],
    )

    result = get_race_pace(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    assert [(d.driver_code, d.position) for d in result.drivers] == [
        ("VER", 1),
        ("HAM", 2),
        ("LEC", None),
    ]


def test_carries_team_name_and_color_as_a_css_hex():
    data = pace_data(
        laps=[lap("VER", 1, 90), lap("HAM", 1, 92, position=2.0)],
        results=[
            result_row("VER", 1.0, team_name="Red Bull Racing", team_color="0600EF"),
            result_row("HAM", 2.0, team_name=None, team_color=None),
        ],
    )

    result = get_race_pace(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    assert [(d.team_name, d.team_color) for d in result.drivers] == [
        ("Red Bull Racing", "#0600EF"),
        (None, None),
    ]


def test_reports_safety_car_and_virtual_safety_car_periods():
    data = pace_data(
        laps=[
            lap("VER", 1, 90, track_status="1"),
            lap("VER", 2, 200, track_status="6"),
            lap("VER", 3, 330, track_status="4"),
        ],
        results=[result_row("VER", 1.0)],
    )

    result = get_race_pace(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    assert result.safety_car_periods == [
        SafetyCarPeriod(kind="virtual_safety_car", start_lap=2, end_lap=2),
        SafetyCarPeriod(kind="safety_car", start_lap=3, end_lap=3),
    ]


def driver_pace(code, position, gaps, *, team="Team", color="#123456", pit_out_laps=()):
    return DriverPace(driver_code=code, position=position, team_name=team, team_color=color,
                      gaps_to_reference=gaps, pit_out_laps=list(pit_out_laps))


def pace_response(drivers, safety_car_periods=(), event_name="Abu Dhabi Grand Prix"):
    return RacePaceResponse(found=True, event_name=event_name, drivers=drivers,
                            safety_car_periods=list(safety_car_periods))


def driver_lines(chart):
    return [trace for trace in chart["data"] if trace["type"] == "scatter"]


def test_chart_draws_one_line_with_markers_per_driver_in_team_color_starting_at_zero():
    result = pace_response([
        driver_pace("VER", 1, [1.0, 1.5, 1.0], color="#0600EF"),
        driver_pace("HAM", 2, [-1.0, -1.5], color="#00D2BE"),
    ])

    chart = build_race_pace_chart(result, year=2021, session_type="Race")

    lines = driver_lines(chart)
    assert [(line["name"], line["mode"], line["line"]["color"]) for line in lines] == [
        ("VER", "lines+markers", "#0600EF"),
        ("HAM", "lines+markers", "#00D2BE"),
    ]
    assert (lines[0]["x"], lines[0]["y"]) == ([0, 1, 2, 3], [0.0, 1.0, 1.5, 1.0])
    assert (lines[1]["x"], lines[1]["y"]) == ([0, 1, 2], [0.0, -1.0, -1.5])


def test_chart_dashes_the_line_of_the_teammate_who_finished_behind():
    result = pace_response([
        driver_pace("VER", 1, [1.0], team="Red Bull Racing"),
        driver_pace("HAM", 2, [0.5], team="Mercedes"),
        driver_pace("BOT", 6, [0.0], team="Mercedes"),
        driver_pace("PER", None, [-1.0], team="Red Bull Racing"),
    ])

    chart = build_race_pace_chart(result, year=2021, session_type="Race")

    dashes = {line["name"]: line["line"]["dash"] for line in driver_lines(chart)}
    assert dashes == {"VER": "solid", "HAM": "solid", "BOT": "dash", "PER": "dash"}


def test_chart_draws_drivers_without_team_data_as_solid_gray_lines():
    result = pace_response([
        driver_pace("AAA", 1, [1.0], team=None, color=None),
        driver_pace("BBB", 2, [0.0], team=None, color=None),
    ])

    chart = build_race_pace_chart(result, year=2021, session_type="Race")

    assert [(line["line"]["color"], line["line"]["dash"]) for line in driver_lines(chart)] == [
        ("#808080", "solid"),
        ("#808080", "solid"),
    ]


def test_chart_marks_pit_out_laps_with_a_larger_open_marker():
    result = pace_response([driver_pace("HAM", 1, [0.5, -18.0, -17.0], pit_out_laps=[2])])

    chart = build_race_pace_chart(result, year=2021, session_type="Race")

    marker = driver_lines(chart)[0]["marker"]
    # Points are lap 0 (start), 1, 2, 3.
    assert marker["symbol"] == ["circle", "circle", "circle-open", "circle"]
    regular, pit = marker["size"][1], marker["size"][2]
    assert pit > regular
    assert marker["size"][0] == marker["size"][1] == marker["size"][3]


def test_chart_shades_safety_car_periods_and_explains_them_in_the_legend():
    result = pace_response(
        [driver_pace("VER", 1, [1.0] * 58)],
        safety_car_periods=[
            SafetyCarPeriod(kind="virtual_safety_car", start_lap=36, end_lap=38),
            SafetyCarPeriod(kind="safety_car", start_lap=53, end_lap=57),
        ],
    )

    chart = build_race_pace_chart(result, year=2021, session_type="Race")

    vsc_band, sc_band = chart["layout"]["shapes"]
    assert (vsc_band["x0"], vsc_band["x1"]) == (35, 38)
    assert (sc_band["x0"], sc_band["x1"]) == (52, 57)
    assert vsc_band["fillcolor"] != sc_band["fillcolor"]
    legend_only = [trace["name"] for trace in chart["data"] if trace["type"] == "bar"]
    assert legend_only == ["SC", "VSC"]


def test_chart_title_and_axes():
    result = pace_response([driver_pace("VER", 1, [1.0])], event_name="Belgian Grand Prix")

    chart = build_race_pace_chart(result, year=2023, session_type="Sprint")

    layout = chart["layout"]
    assert layout["title"] == "2023 Belgian Grand Prix - Sprint"
    assert layout["xaxis"]["title"] == "Volta"
    assert layout["yaxis"]["title"] == "Diferença para a referência (s)"
    assert layout["xaxis"]["showgrid"] is True
    assert layout["yaxis"]["showgrid"] is True


def test_chart_uses_the_dark_theme():
    result = pace_response([driver_pace("VER", 1, [1.0])])

    chart = build_race_pace_chart(result, year=2021, session_type="Race")

    assert_dark_theme(chart["layout"])
