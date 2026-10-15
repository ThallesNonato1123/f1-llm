import pytest
from dark_theme import assert_dark_theme

from f1llm.errors import SessionDataUnavailable
from f1llm.tools.standings import (
    DriverStanding,
    TeamStanding,
    build_driver_standings_chart,
    build_team_standings_chart,
    get_driver_standings,
    get_team_standings,
)


def test_rejects_year_before_fastf1_coverage_starts():
    with pytest.raises(ValueError, match="year"):
        get_driver_standings(year=2017)


def test_returns_transformed_standings_for_known_season():
    raw_rows = [
        {
            "position": 1,
            "driverCode": "VER",
            "givenName": "Max",
            "familyName": "Verstappen",
            "constructorNames": ["Red Bull"],
            "points": 437.0,
            "wins": 9,
        },
        {
            "position": 2,
            "driverCode": "PER",
            "givenName": "Sergio",
            "familyName": "Pérez",
            "constructorNames": ["Red Bull", "RB"],
            "points": 285.0,
            "wins": 2,
        },
    ]

    result = get_driver_standings(
        year=2023,
        load_driver_standings=lambda year, event: raw_rows,
    )

    assert result.found is True
    assert result.standings == [
        DriverStanding(
            position=1, driver_code="VER", driver="Max Verstappen",
            team="Red Bull", points=437.0, wins=9,
        ),
        DriverStanding(
            position=2, driver_code="PER", driver="Sergio Pérez",
            team="Red Bull, RB", points=285.0, wins=2,
        ),
    ]


def test_reports_not_found_when_season_has_no_standings_data():
    def raise_not_found(year, event):
        raise SessionDataUnavailable("No standings data for Imaginary Grand Prix 2023")

    result = get_driver_standings(
        year=2023,
        event="Imaginary Grand Prix",
        load_driver_standings=raise_not_found,
    )

    assert result.found is False
    assert result.standings is None
    assert result.reason == "No standings data for Imaginary Grand Prix 2023"


def test_chart_draws_one_bar_per_driver_ordered_by_position():
    standings = [
        DriverStanding(position=1, driver_code="VER", driver="Max Verstappen", team="Red Bull", points=437.0, wins=9),
        DriverStanding(position=2, driver_code="PER", driver="Sergio Pérez", team="Red Bull, RB", points=285.0, wins=2),
    ]

    chart = build_driver_standings_chart(standings)

    assert chart["data"] == [
        {"type": "bar", "x": ["VER", "PER"], "y": [437.0, 285.0]},
    ]
    assert chart["layout"]["xaxis"]["title"] == "Piloto"
    assert chart["layout"]["yaxis"]["title"] == "Pontos"


def test_chart_axes_have_grid_enabled():
    standings = [DriverStanding(position=1, driver_code="VER", driver="Max Verstappen", team="Red Bull", points=437.0, wins=9)]

    chart = build_driver_standings_chart(standings)

    assert chart["layout"]["xaxis"]["showgrid"] is True
    assert chart["layout"]["yaxis"]["showgrid"] is True


def test_chart_uses_the_dark_theme():
    standings = [DriverStanding(position=1, driver_code="VER", driver="Max Verstappen", team="Red Bull", points=437.0, wins=9)]

    chart = build_driver_standings_chart(standings)

    assert_dark_theme(chart["layout"])


def test_rejects_year_before_fastf1_coverage_starts_for_teams():
    with pytest.raises(ValueError, match="year"):
        get_team_standings(year=2017)


def test_returns_transformed_team_standings_for_known_season():
    raw_rows = [
        {"position": 1, "constructorName": "Red Bull", "points": 860.0, "wins": 21},
        {"position": 2, "constructorName": "Mercedes", "points": 409.0, "wins": 0},
    ]

    result = get_team_standings(
        year=2023,
        load_team_standings=lambda year, event: raw_rows,
    )

    assert result.found is True
    assert result.standings == [
        TeamStanding(position=1, team="Red Bull", points=860.0, wins=21),
        TeamStanding(position=2, team="Mercedes", points=409.0, wins=0),
    ]


def test_reports_not_found_when_season_has_no_team_standings_data():
    def raise_not_found(year, event):
        raise SessionDataUnavailable("No standings data for Imaginary Grand Prix 2023")

    result = get_team_standings(
        year=2023,
        event="Imaginary Grand Prix",
        load_team_standings=raise_not_found,
    )

    assert result.found is False
    assert result.standings is None
    assert result.reason == "No standings data for Imaginary Grand Prix 2023"


def test_team_chart_draws_one_bar_per_team_ordered_by_position():
    standings = [
        TeamStanding(position=1, team="Red Bull", points=860.0, wins=21),
        TeamStanding(position=2, team="Mercedes", points=409.0, wins=0),
    ]

    chart = build_team_standings_chart(standings)

    assert chart["data"] == [
        {"type": "bar", "x": ["Red Bull", "Mercedes"], "y": [860.0, 409.0]},
    ]
    assert chart["layout"]["xaxis"]["title"] == "Equipe"
    assert chart["layout"]["yaxis"]["title"] == "Pontos"


def test_team_chart_axes_have_grid_enabled():
    standings = [TeamStanding(position=1, team="Red Bull", points=860.0, wins=21)]

    chart = build_team_standings_chart(standings)

    assert chart["layout"]["xaxis"]["showgrid"] is True
    assert chart["layout"]["yaxis"]["showgrid"] is True


def test_team_chart_uses_the_dark_theme():
    standings = [TeamStanding(position=1, team="Red Bull", points=860.0, wins=21)]

    chart = build_team_standings_chart(standings)

    assert_dark_theme(chart["layout"])
