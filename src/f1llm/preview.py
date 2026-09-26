import argparse
import html
import json
import sys
import tempfile
import webbrowser
from dataclasses import dataclass

from f1llm.tools.lap_times import build_lap_times_chart, get_lap_times
from f1llm.tools.race_pace import build_race_pace_chart, get_race_pace
from f1llm.tools.stints import build_stints_chart, get_stints
from f1llm.tools.telemetry import build_telemetry_chart, get_telemetry_comparison

CHARTS = ("lap_times", "telemetry", "stints", "race_pace")


@dataclass(frozen=True)
class PreviewRequest:
    chart: str
    year: int
    event: str
    session_type: str
    drivers: list[str]


def parse_args(argv: list[str]) -> PreviewRequest:
    parser = argparse.ArgumentParser(prog="f1llm-preview")
    parser.add_argument("chart", choices=CHARTS)
    parser.add_argument("year", type=int)
    parser.add_argument("event")
    parser.add_argument("session_type")
    parser.add_argument("drivers", nargs="*")
    args = parser.parse_args(argv)
    return PreviewRequest(
        chart=args.chart,
        year=args.year,
        event=args.event,
        session_type=args.session_type,
        drivers=args.drivers,
    )


@dataclass(frozen=True)
class PreviewResult:
    found: bool
    figure: dict | None = None
    reason: str | None = None


def build_preview(request: PreviewRequest, *, loaders) -> PreviewResult:
    common = dict(
        year=request.year,
        event=request.event,
        session_type=request.session_type,
        drivers=request.drivers,
    )
    # stints and race_pace take None, not an empty list, to mean every driver.
    all_by_default = {**common, "drivers": request.drivers or None}
    titled = dict(year=request.year, session_type=request.session_type)

    if request.chart == "lap_times":
        result = get_lap_times(**common, load_laps=loaders.load_laps)
        build = lambda: build_lap_times_chart(result.laps)
    elif request.chart == "telemetry":
        result = get_telemetry_comparison(**common, load_telemetry=loaders.load_telemetry)
        build = lambda: build_telemetry_chart(result.samples)
    elif request.chart == "stints":
        result = get_stints(**all_by_default, load_stint_data=loaders.load_stint_data)
        build = lambda: build_stints_chart(result, **titled)
    else:
        result = get_race_pace(**all_by_default, load_race_pace_data=loaders.load_race_pace_data)
        build = lambda: build_race_pace_chart(result, **titled)

    if not result.found:
        return PreviewResult(found=False, reason=result.reason)
    return PreviewResult(found=True, figure=build())


_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2/plotly.min.js"></script>
<style>body {{ margin: 0; }} #chart {{ width: 100vw; height: 100vh; }}</style>
</head>
<body>
<div id="chart"></div>
<script>
const figure = {figure};
Plotly.newPlot("chart", figure.data, figure.layout, {{ responsive: true }});
</script>
</body>
</html>
"""


def to_html(figure: dict, title: str) -> str:
    return _PAGE.format(title=html.escape(title), figure=json.dumps(figure))


def main(argv: list[str] | None = None) -> None:
    request = parse_args(sys.argv[1:] if argv is None else argv)

    # Imported here so the pure seams above don't pull in FastF1.
    from f1llm import fastf1_client

    try:
        result = build_preview(request, loaders=fastf1_client)
    except ValueError as exc:
        sys.exit(f"f1llm-preview: {exc}")
    if not result.found:
        sys.exit(f"f1llm-preview: {result.reason}")

    title = f"{request.chart} {request.year} {request.event} {request.session_type}"
    with tempfile.NamedTemporaryFile("w", suffix=".html", prefix="f1llm-preview-", delete=False) as page:
        page.write(to_html(result.figure, title=title))
    print(page.name)
    webbrowser.open(f"file://{page.name}")
