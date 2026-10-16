from datetime import timedelta

import pytest
from dark_theme import assert_dark_theme

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.gap_to_winner import DriverGap, GapToWinnerResponse, build_gap_to_winner_chart, get_gap_to_winner
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
    # VER (winner) laps: 90, 90, 90 s. HAM laps: 92, 91, 89 s.
    # VER cumulative: 90, 180, 270. HAM cumulative: 92, 183, 272.
    return pace_data(
        laps=[
            lap("VER", 1, 90), lap("VER", 2, 180), lap("VER", 3, 270),
            lap("HAM", 1, 92, position=2.0), lap("HAM", 2, 183, position=2.0), lap("HAM", 3, 272, position=2.0),
        ],
        results=[result_row("VER", 1.0), result_row("HAM", 2.0)],
    )


def test_gap_to_winner_is_the_cumulative_difference_to_the_winners_own_time():
    data = two_driver_race()

    result = get_gap_to_winner(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    assert result.found is True
    gaps = {driver.driver_code: driver.gaps_to_winner for driver in result.drivers}
    assert gaps["VER"] == pytest.approx([0.0, 0.0, 0.0])
    assert gaps["HAM"] == pytest.approx([-2.0, -3.0, -2.0])


def test_returns_only_the_requested_drivers():
    data = two_driver_race()

    result = get_gap_to_winner(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        drivers=["HAM"],
        load_race_pace_data=lambda year, event, session_type: data,
    )

    assert [driver.driver_code for driver in result.drivers] == ["HAM"]


def test_defaults_to_the_top_6_finishers_when_no_drivers_are_requested():
    codes = ["VER", "HAM", "LEC", "SAI", "NOR", "PIA", "RUS", "ALO"]  # 8 drivers
    data = pace_data(
        laps=[lap(code, 1, 90 + position) for position, code in enumerate(codes)],
        results=[result_row(code, position + 1.0) for position, code in enumerate(codes)],
    )

    result = get_gap_to_winner(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    assert [driver.driver_code for driver in result.drivers] == codes[:6]


def test_pit_out_laps_mark_where_a_driver_starts_a_new_stint():
    data = pace_data(
        laps=[
            lap("VER", 1, 90), lap("VER", 2, 180), lap("VER", 3, 270),
            lap("HAM", 1, 92, position=2.0, stint=1.0),
            lap("HAM", 2, 183, position=2.0, stint=2.0),  # pitted after lap 1
            lap("HAM", 3, 274, position=2.0, stint=2.0),
        ],
        results=[result_row("VER", 1.0), result_row("HAM", 2.0)],
    )

    result = get_gap_to_winner(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    ham = next(driver for driver in result.drivers if driver.driver_code == "HAM")
    assert ham.pit_out_laps == [2]


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2023 Race")

    result = get_gap_to_winner(
        year=2023,
        event="Imaginary Grand Prix",
        session_type="Race",
        load_race_pace_data=raise_not_found,
    )

    assert result.found is False
    assert result.drivers is None
    assert result.reason == "No data for Imaginary Grand Prix 2023 Race"


def test_reports_not_found_when_no_driver_is_classified_as_the_winner():
    data = pace_data(
        laps=[lap("VER", 1, 90), lap("HAM", 1, 92, position=2.0)],
        results=[result_row("VER", None), result_row("HAM", 2.0)],
    )

    result = get_gap_to_winner(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_race_pace_data=lambda year, event, session_type: data,
    )

    assert result.found is False
    assert result.drivers is None
    assert "winner" in result.reason.lower()


def driver_gap(code, position, gaps, *, team="Team", color="#123456", pit_out_laps=()):
    return DriverGap(driver_code=code, position=position, team_name=team, team_color=color,
                      gaps_to_winner=gaps, pit_out_laps=list(pit_out_laps))


def gap_response(drivers, safety_car_periods=(), event_name="Abu Dhabi Grand Prix"):
    return GapToWinnerResponse(found=True, event_name=event_name, drivers=drivers,
                               safety_car_periods=list(safety_car_periods))


def driver_lines(chart):
    return [trace for trace in chart["data"] if trace["type"] == "scatter"]


def test_chart_draws_one_line_with_markers_per_driver_in_team_color_starting_at_zero():
    result = gap_response([
        driver_gap("VER", 1, [0.0, 0.0, 0.0], color="#0600EF"),
        driver_gap("HAM", 2, [-2.0, -3.0], color="#00D2BE"),
    ])

    chart = build_gap_to_winner_chart(result, year=2021, session_type="Race")

    lines = driver_lines(chart)
    assert [(line["name"], line["mode"], line["line"]["color"]) for line in lines] == [
        ("VER", "lines+markers", "#0600EF"),
        ("HAM", "lines+markers", "#00D2BE"),
    ]
    assert (lines[0]["x"], lines[0]["y"]) == ([0, 1, 2, 3], [0.0, 0.0, 0.0, 0.0])
    assert (lines[1]["x"], lines[1]["y"]) == ([0, 1, 2], [0.0, -2.0, -3.0])


def test_chart_dashes_the_line_of_the_teammate_who_finished_behind():
    result = gap_response([
        driver_gap("VER", 1, [0.0], team="Red Bull Racing"),
        driver_gap("HAM", 2, [-0.5], team="Mercedes"),
        driver_gap("BOT", 6, [-1.0], team="Mercedes"),
        driver_gap("PER", None, [-2.0], team="Red Bull Racing"),
    ])

    chart = build_gap_to_winner_chart(result, year=2021, session_type="Race")

    dashes = {line["name"]: line["line"]["dash"] for line in driver_lines(chart)}
    assert dashes == {"VER": "solid", "HAM": "solid", "BOT": "dash", "PER": "dash"}


def test_chart_draws_drivers_without_team_data_as_solid_gray_lines():
    result = gap_response([
        driver_gap("AAA", 1, [0.0], team=None, color=None),
        driver_gap("BBB", 2, [-1.0], team=None, color=None),
    ])

    chart = build_gap_to_winner_chart(result, year=2021, session_type="Race")

    assert [(line["line"]["color"], line["line"]["dash"]) for line in driver_lines(chart)] == [
        ("#808080", "solid"),
        ("#808080", "solid"),
    ]


def test_chart_marks_pit_out_laps_with_a_larger_open_marker():
    result = gap_response([driver_gap("HAM", 1, [-0.5, -18.0, -17.0], pit_out_laps=[2])])

    chart = build_gap_to_winner_chart(result, year=2021, session_type="Race")

    marker = driver_lines(chart)[0]["marker"]
    # Points are lap 0 (start), 1, 2, 3.
    assert marker["symbol"] == ["circle", "circle", "circle-open", "circle"]
    regular, pit = marker["size"][1], marker["size"][2]
    assert pit > regular
    assert marker["size"][0] == marker["size"][1] == marker["size"][3]


def test_chart_shades_safety_car_periods_and_explains_them_in_the_legend():
    result = gap_response(
        [driver_gap("VER", 1, [0.0] * 58)],
        safety_car_periods=[
            SafetyCarPeriod(kind="virtual_safety_car", start_lap=36, end_lap=38),
            SafetyCarPeriod(kind="safety_car", start_lap=53, end_lap=57),
        ],
    )

    chart = build_gap_to_winner_chart(result, year=2021, session_type="Race")

    vsc_band, sc_band = chart["layout"]["shapes"]
    assert (vsc_band["x0"], vsc_band["x1"]) == (35, 38)
    assert (sc_band["x0"], sc_band["x1"]) == (52, 57)
    assert vsc_band["fillcolor"] != sc_band["fillcolor"]
    legend_only = [trace["name"] for trace in chart["data"] if trace["type"] == "bar"]
    assert legend_only == ["SC", "VSC"]


def test_chart_marks_the_winners_pit_stops_with_a_dashed_line_and_label():
    result = gap_response([
        driver_gap("VER", 1, [0.0, 0.0, 0.0], pit_out_laps=[2]),
        driver_gap("HAM", 2, [-1.0, -18.0, -17.0], pit_out_laps=[3]),
    ])

    chart = build_gap_to_winner_chart(result, year=2021, session_type="Race")

    lines = [shape for shape in chart["layout"]["shapes"] if shape["type"] == "line"]
    assert len(lines) == 1
    assert lines[0]["x0"] == lines[0]["x1"] == 2
    assert lines[0]["line"]["dash"] == "dash"

    labels = [a for a in chart["layout"]["annotations"] if a["text"] == "VER pits"]
    assert len(labels) == 1
    assert labels[0]["x"] == 2


def test_chart_title_axes_and_legend_position():
    result = gap_response([driver_gap("VER", 1, [0.0])], event_name="Belgian Grand Prix")

    chart = build_gap_to_winner_chart(result, year=2023, session_type="Sprint")

    layout = chart["layout"]
    assert layout["title"] == "2023 Belgian Grand Prix - Sprint"
    assert layout["xaxis"]["title"] == "Volta"
    assert layout["yaxis"]["title"] == "Gap para o vencedor (s)"
    assert layout["xaxis"]["showgrid"] is True
    assert layout["yaxis"]["showgrid"] is True
    assert layout["legend"]["x"] == 0
    assert layout["legend"]["y"] == 0
    assert layout["legend"]["xanchor"] == "left"
    assert layout["legend"]["yanchor"] == "bottom"


def test_chart_uses_the_dark_theme():
    result = gap_response([driver_gap("VER", 1, [0.0])])

    chart = build_gap_to_winner_chart(result, year=2021, session_type="Race")

    assert_dark_theme(chart["layout"])


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_gap_to_winner(year=2023, event="Bahrain", session_type="Qualifying")


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_gap_to_winner(year=2017, event="Bahrain", session_type="Race")
