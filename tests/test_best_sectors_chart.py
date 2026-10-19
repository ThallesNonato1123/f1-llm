from f1llm.tools.best_sectors import (
    BestSectorsResponse,
    DriverSectors,
    build_best_sectors_chart,
)


def driver(driver_code, s1, s2, s3, team_color="#E8002D"):
    return DriverSectors(driver_code=driver_code, team_color=team_color, sector_1=s1, sector_2=s2, sector_3=s3)


def sectors_response(drivers, event_name="Italian Grand Prix"):
    return BestSectorsResponse(found=True, event_name=event_name, drivers=list(drivers))


def test_chart_draws_3_bars_with_only_the_8_fastest_per_sector():
    # 9 drivers, increasing (slower) sector times, so D8 is slowest in every sector.
    drivers = [driver(f"D{i}", s1=30.0 + i, s2=40.0 + i, s3=25.0 + i) for i in range(9)]
    result = sectors_response(drivers)

    chart = build_best_sectors_chart(result, year=2023, session_type="Qualifying")

    bars = {bar["xaxis"]: bar for bar in chart["data"] if bar["type"] == "bar"}
    assert set(bars) == {"x", "x2", "x3"}
    for bar in bars.values():
        assert len(bar["y"]) == 8
        assert "D8" not in bar["y"]
        assert bar["y"][0] == "D0"  # fastest on top
        assert bar["orientation"] == "h"


def test_chart_titles_and_background():
    result = sectors_response(
        [driver("VER", s1=28.0, s2=35.0, s3=27.0)], event_name="Monza Grand Prix"
    )

    chart = build_best_sectors_chart(result, year=2023, session_type="Qualifying")
    layout = chart["layout"]

    assert layout["title"] == "2023 Monza Grand Prix - Qualifying - Melhores setores"
    assert layout["paper_bgcolor"] == "#ffffff"
    assert layout["plot_bgcolor"] == "#ffffff"
    assert layout["annotations"][0]["text"] == "S1"
    assert layout["annotations"][1]["text"] == "S2"
    assert layout["annotations"][2]["text"] == "S3"
