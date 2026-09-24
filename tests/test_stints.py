import pytest
from dark_theme import assert_dark_theme

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.stints import (
    DriverStints,
    SafetyCarPeriod,
    Stint,
    StintsResponse,
    build_stints_chart,
    get_stints,
)


_SAME_AS_LAP_NUMBER = object()


def lap(driver, lap_number, *, stint=1.0, compound="MEDIUM", tyre_life=_SAME_AS_LAP_NUMBER, fresh=True,
        position=1.0, track_status="1"):
    return {
        "Driver": driver,
        "LapNumber": float(lap_number),
        "Position": position,
        "Stint": stint,
        "Compound": compound,
        "TyreLife": float(lap_number) if tyre_life is _SAME_AS_LAP_NUMBER else tyre_life,
        "FreshTyre": fresh,
        "TrackStatus": track_status,
    }


def stint_data(laps, results=None, event_name="Abu Dhabi Grand Prix"):
    return {
        "event_name": event_name,
        "laps": laps,
        "results": results if results is not None else [],
    }


def test_groups_consecutive_laps_on_the_same_stint_into_one_stint():
    data = stint_data(
        laps=[lap("VER", 1), lap("VER", 2), lap("VER", 3)],
        results=[{"Abbreviation": "VER", "Position": 1.0}],
    )

    result = get_stints(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        drivers=["VER"],
        load_stint_data=lambda year, event, session_type: data,
    )

    assert result.found is True
    assert result.event_name == "Abu Dhabi Grand Prix"
    assert result.drivers == [
        DriverStints(
            driver_code="VER",
            position=1,
            stints=[
                Stint(number=1, compound="MEDIUM", start_lap=1, end_lap=3, lap_count=3,
                      fresh=True, tyre_age_at_start=0),
            ],
        )
    ]


def test_starts_a_new_stint_after_a_pit_stop_with_tyre_freshness_and_age():
    data = stint_data(
        laps=[
            lap("VER", 1, stint=1.0, compound="SOFT", tyre_life=1.0, fresh=True),
            lap("VER", 2, stint=1.0, compound="SOFT", tyre_life=2.0, fresh=True),
            lap("VER", 3, stint=2.0, compound="HARD", tyre_life=4.0, fresh=False),
            lap("VER", 4, stint=2.0, compound="HARD", tyre_life=5.0, fresh=False),
        ],
        results=[{"Abbreviation": "VER", "Position": 1.0}],
    )

    result = get_stints(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        drivers=["VER"],
        load_stint_data=lambda year, event, session_type: data,
    )

    assert result.drivers[0].stints == [
        Stint(number=1, compound="SOFT", start_lap=1, end_lap=2, lap_count=2,
              fresh=True, tyre_age_at_start=0),
        Stint(number=2, compound="HARD", start_lap=3, end_lap=4, lap_count=2,
              fresh=False, tyre_age_at_start=3),
    ]


def test_reports_unknown_compound_freshness_and_age_when_data_is_missing():
    data = stint_data(
        laps=[lap("VER", 1, compound=None, tyre_life=None, fresh=None)],
        results=[{"Abbreviation": "VER", "Position": 1.0}],
    )

    result = get_stints(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        drivers=["VER"],
        load_stint_data=lambda year, event, session_type: data,
    )

    assert result.drivers[0].stints == [
        Stint(number=1, compound="UNKNOWN", start_lap=1, end_lap=1, lap_count=1,
              fresh=None, tyre_age_at_start=None),
    ]


def test_rejects_unsupported_session_type():
    with pytest.raises(ValueError, match="session_type"):
        get_stints(year=2021, event="Abu Dhabi", session_type="Practice")


def test_rejects_2018_because_compound_names_were_absolute_that_season():
    # Until 2018 compounds had absolute names (HYPERSOFT..SUPERHARD) with a different color
    # scheme; since 2019 SOFT/MEDIUM/HARD are relative to each Grand Prix.
    with pytest.raises(ValueError, match="year"):
        get_stints(year=2018, event="Abu Dhabi", session_type="Race")


def test_rejects_empty_drivers_list():
    with pytest.raises(ValueError, match="drivers"):
        get_stints(year=2021, event="Abu Dhabi", session_type="Race", drivers=[])


def test_returns_only_the_requested_drivers():
    data = stint_data(
        laps=[lap("VER", 1), lap("HAM", 1, position=2.0), lap("LEC", 1, position=3.0)],
        results=[
            {"Abbreviation": "VER", "Position": 1.0},
            {"Abbreviation": "HAM", "Position": 2.0},
            {"Abbreviation": "LEC", "Position": 3.0},
        ],
    )

    result = get_stints(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        drivers=["HAM"],
        load_stint_data=lambda year, event, session_type: data,
    )

    assert [d.driver_code for d in result.drivers] == ["HAM"]


def test_returns_every_driver_when_no_drivers_are_requested():
    data = stint_data(
        laps=[lap("VER", 1), lap("HAM", 1, position=2.0)],
        results=[
            {"Abbreviation": "VER", "Position": 1.0},
            {"Abbreviation": "HAM", "Position": 2.0},
        ],
    )

    result = get_stints(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_stint_data=lambda year, event, session_type: data,
    )

    assert [d.driver_code for d in result.drivers] == ["VER", "HAM"]


def test_reports_not_found_when_no_requested_driver_took_part():
    data = stint_data(laps=[lap("VER", 1)], results=[{"Abbreviation": "VER", "Position": 1.0}])

    result = get_stints(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        drivers=["ZZZ"],
        load_stint_data=lambda year, event, session_type: data,
    )

    assert result.found is False
    assert result.drivers is None
    assert "ZZZ" in result.reason


def test_reports_not_found_when_session_has_no_data():
    def raise_not_found(year, event, session_type):
        raise SessionDataUnavailable("No data for Imaginary Grand Prix 2021 Race")

    result = get_stints(
        year=2021,
        event="Imaginary Grand Prix",
        session_type="Race",
        load_stint_data=raise_not_found,
    )

    assert result.found is False
    assert result.drivers is None
    assert result.reason == "No data for Imaginary Grand Prix 2021 Race"


def test_orders_drivers_by_final_position_with_unclassified_drivers_last():
    data = stint_data(
        laps=[lap("LEC", 1, position=1.0), lap("HAM", 1, position=2.0), lap("VER", 1, position=3.0)],
        results=[
            {"Abbreviation": "VER", "Position": 1.0},
            {"Abbreviation": "HAM", "Position": 2.0},
            {"Abbreviation": "LEC", "Position": None},
        ],
    )

    result = get_stints(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_stint_data=lambda year, event, session_type: data,
    )

    assert [(d.driver_code, d.position) for d in result.drivers] == [
        ("VER", 1),
        ("HAM", 2),
        ("LEC", None),
    ]


def test_derives_safety_car_periods_from_the_leaders_laps_even_when_leader_not_requested():
    data = stint_data(
        laps=[
            lap("VER", 1, position=1.0, track_status="1"),
            lap("VER", 2, position=1.0, track_status="4"),
            lap("VER", 3, position=1.0, track_status="4"),
            lap("VER", 4, position=1.0, track_status="1"),
            lap("HAM", 1, position=2.0, track_status="1"),
            lap("HAM", 2, position=2.0, track_status="1"),
            lap("HAM", 3, position=2.0, track_status="4"),
            lap("HAM", 4, position=2.0, track_status="4"),
        ],
        results=[{"Abbreviation": "VER", "Position": 1.0}, {"Abbreviation": "HAM", "Position": 2.0}],
    )

    result = get_stints(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        drivers=["HAM"],
        load_stint_data=lambda year, event, session_type: data,
    )

    assert result.safety_car_periods == [
        SafetyCarPeriod(kind="safety_car", start_lap=2, end_lap=3),
    ]


def test_derives_virtual_safety_car_periods_separately_with_safety_car_taking_precedence():
    data = stint_data(
        laps=[
            lap("VER", 1, track_status="6"),
            lap("VER", 2, track_status="67"),
            lap("VER", 3, track_status="1"),
            lap("VER", 4, track_status="64"),
            lap("VER", 5, track_status="4"),
        ],
        results=[{"Abbreviation": "VER", "Position": 1.0}],
    )

    result = get_stints(
        year=2021,
        event="Abu Dhabi",
        session_type="Race",
        load_stint_data=lambda year, event, session_type: data,
    )

    assert result.safety_car_periods == [
        SafetyCarPeriod(kind="virtual_safety_car", start_lap=1, end_lap=2),
        SafetyCarPeriod(kind="safety_car", start_lap=4, end_lap=5),
    ]


def stint(number, compound, start_lap, end_lap, *, fresh=True, tyre_age_at_start=0):
    return Stint(number=number, compound=compound, start_lap=start_lap, end_lap=end_lap,
                 lap_count=end_lap - start_lap + 1, fresh=fresh, tyre_age_at_start=tyre_age_at_start)


def stints_response(drivers, safety_car_periods=(), event_name="Abu Dhabi Grand Prix"):
    return StintsResponse(found=True, event_name=event_name, drivers=drivers,
                          safety_car_periods=list(safety_car_periods))


def stint_segments(chart):
    """(driver, first lap, last lap, color) for every stint bar drawn in the chart."""
    return [
        (trace["y"][0], trace["base"][0] + 1, trace["base"][0] + trace["x"][0], trace["marker"]["color"])
        for trace in stint_bars(chart)
    ]


def stint_bars(chart):
    return [trace for trace in chart["data"] if trace["type"] == "bar" and trace.get("showlegend") is False]


def legend_entries(chart):
    return [trace["name"] for trace in chart["data"] if trace.get("showlegend") is True]


def test_chart_draws_one_bar_segment_per_stint_colored_by_compound():
    result = stints_response([
        DriverStints("VER", 1, [stint(1, "SOFT", 1, 10), stint(2, "HARD", 11, 30)]),
        DriverStints("HAM", 2, [stint(1, "MEDIUM", 1, 14), stint(2, "INTERMEDIATE", 15, 20),
                                stint(3, "WET", 21, 25), stint(4, "UNKNOWN", 26, 30)]),
    ])

    chart = build_stints_chart(result, year=2021, session_type="Race")

    assert stint_segments(chart) == [
        ("VER", 1, 10, "#DA291C"),
        ("VER", 11, 30, "#F0F0EC"),
        ("HAM", 1, 14, "#FFD12E"),
        ("HAM", 15, 20, "#43B02A"),
        ("HAM", 21, 25, "#0067AD"),
        ("HAM", 26, 30, "#808080"),
    ]


def test_chart_hatches_used_tyres_and_dots_tyres_of_unknown_freshness():
    result = stints_response([
        DriverStints("VER", 1, [
            stint(1, "SOFT", 1, 10, fresh=True),
            stint(2, "HARD", 11, 20, fresh=False),
            stint(3, "HARD", 21, 30, fresh=None),
        ]),
    ])

    chart = build_stints_chart(result, year=2021, session_type="Race")

    assert [bar["marker"]["pattern"]["shape"] for bar in stint_bars(chart)] == ["", "/", "."]


def test_chart_shades_safety_car_and_virtual_safety_car_laps_in_different_colors():
    result = stints_response(
        [DriverStints("VER", 1, [stint(1, "HARD", 1, 58)])],
        safety_car_periods=[
            SafetyCarPeriod(kind="virtual_safety_car", start_lap=36, end_lap=38),
            SafetyCarPeriod(kind="safety_car", start_lap=53, end_lap=57),
        ],
    )

    chart = build_stints_chart(result, year=2021, session_type="Race")

    vsc_band, sc_band = chart["layout"]["shapes"]
    # A band covers whole laps: lap N spans the axis interval [N-1, N].
    assert (vsc_band["x0"], vsc_band["x1"]) == (35, 38)
    assert (sc_band["x0"], sc_band["x1"]) == (52, 57)
    assert vsc_band["yref"] == sc_band["yref"] == "paper"
    assert vsc_band["fillcolor"] != sc_band["fillcolor"]


def test_chart_title_names_the_season_grand_prix_and_session():
    result = stints_response([DriverStints("RUS", 1, [stint(1, "MEDIUM", 1, 19)])],
                             event_name="Chinese Grand Prix")

    chart = build_stints_chart(result, year=2026, session_type="Sprint")

    assert chart["layout"]["title"] == "2026 Chinese Grand Prix - Sprint"


def test_chart_lists_drivers_top_to_bottom_in_finishing_order():
    result = stints_response([
        DriverStints("VER", 1, [stint(1, "HARD", 1, 58)]),
        DriverStints("HAM", 2, [stint(1, "HARD", 1, 58)]),
        DriverStints("MAZ", None, [stint(1, "HARD", 1, 3)]),
    ])

    chart = build_stints_chart(result, year=2021, session_type="Race")

    yaxis = chart["layout"]["yaxis"]
    assert yaxis["categoryarray"] == ["VER", "HAM", "MAZ"]
    assert yaxis["autorange"] == "reversed"  # Plotly draws the first category at the bottom otherwise


def test_chart_axes_are_titled_and_have_grid_enabled():
    result = stints_response([DriverStints("VER", 1, [stint(1, "HARD", 1, 58)])])

    chart = build_stints_chart(result, year=2021, session_type="Race")

    assert chart["layout"]["xaxis"]["title"] == "Volta"
    assert chart["layout"]["xaxis"]["showgrid"] is True
    assert chart["layout"]["yaxis"]["showgrid"] is True


def test_chart_legend_explains_only_the_bands_and_tyre_styles_present():
    result = stints_response(
        [DriverStints("VER", 1, [stint(1, "SOFT", 1, 10, fresh=True), stint(2, "HARD", 11, 58, fresh=False)])],
        safety_car_periods=[SafetyCarPeriod(kind="safety_car", start_lap=53, end_lap=57)],
    )

    chart = build_stints_chart(result, year=2021, session_type="Race")

    assert legend_entries(chart) == ["SC", "Pneu novo", "Pneu usado"]


def test_chart_hover_describes_driver_compound_laps_and_tyre_age():
    result = stints_response([
        DriverStints("VER", 1, [
            stint(1, "HARD", 11, 30, fresh=False, tyre_age_at_start=3),
            stint(2, "UNKNOWN", 31, 31, fresh=None, tyre_age_at_start=None),
        ]),
    ])

    chart = build_stints_chart(result, year=2021, session_type="Race")

    assert [bar["hovertemplate"] for bar in stint_bars(chart)] == [
        "VER<br>Duro · Pneu usado<br>Voltas 11–30 (20 voltas)<br>Idade no início: 3 voltas<extra></extra>",
        "VER<br>Desconhecido · Desconhecido<br>Volta 31 (1 volta)<br>Idade no início: desconhecida<extra></extra>",
    ]


def test_chart_uses_the_dark_theme():
    result = stints_response([DriverStints("VER", 1, [stint(1, "HARD", 1, 58)])])

    chart = build_stints_chart(result, year=2021, session_type="Race")

    assert_dark_theme(chart["layout"])


def test_chart_draws_every_stint_of_a_driver_on_the_same_row():
    result = stints_response([DriverStints("VER", 1, [stint(1, "SOFT", 1, 10), stint(2, "HARD", 11, 58)])])

    chart = build_stints_chart(result, year=2021, session_type="Race")

    # Each stint is its own trace; Plotly's default "group" mode would split the row between them.
    assert chart["layout"]["barmode"] == "overlay"
