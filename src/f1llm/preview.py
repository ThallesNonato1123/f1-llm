import argparse
import html
import json
import sys
import tempfile
import webbrowser
from dataclasses import dataclass

from f1llm.tools.gap_to_winner import build_gap_to_winner_chart, get_gap_to_winner
from f1llm.tools.lap_times import build_lap_times_by_compound_chart, build_lap_times_chart, get_lap_times
from f1llm.tools.race_pace import build_race_pace_chart, get_race_pace
from f1llm.tools.stints import build_stints_chart, get_stints
from f1llm.tools.telemetry import build_telemetry_chart, get_telemetry_comparison
from f1llm.tools.gap_to_pole import build_gap_to_pole_chart, get_gap_to_pole
from f1llm.tools.best_sectors import build_best_sectors_chart, get_best_sectors
from f1llm.tools.gg_diagram import build_gg_diagram_chart, get_gg_diagram
from f1llm.tools.position_changes import build_position_changes_chart, get_position_changes
from f1llm.tools.qualifying_segments import (
    build_qualifying_pace_evolution_chart,
    build_qualifying_segment_bar_chart,
    get_qualifying_segments,
)
from f1llm.tools.speed_delta_trace import build_speed_delta_trace_chart, get_speed_delta_trace
from f1llm.tools.speed_quadrant import build_speed_quadrant_chart, get_speed_quadrant
from f1llm.tools.top_speeds import build_top_speeds_chart, get_top_speeds
from f1llm.tools.tyre_degradation import build_tyre_degradation_chart, get_tyre_degradation

CHARTS = (
    "lap_times", "telemetry", "stints", "race_pace", "gap_to_winner", "top_speeds", "tyre_degradation",
    "speed_quadrant", "gg_diagram", "speed_delta_trace", "gap_to_pole", "lap_times_by_compound",
    "position_changes", "best_sectors", "qualifying_segments_bar", "qualifying_segments_evolution",
)


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
    elif request.chart == "lap_times_by_compound":
        result = get_lap_times(**common, load_laps=loaders.load_laps)
        build = lambda: build_lap_times_by_compound_chart(result.laps)
    elif request.chart == "telemetry":
        result = get_telemetry_comparison(**common, load_telemetry=loaders.load_telemetry)
        build = lambda: build_telemetry_chart(result.samples)
    elif request.chart == "stints":
        result = get_stints(**all_by_default, load_stint_data=loaders.load_stint_data)
        build = lambda: build_stints_chart(result, **titled)
    elif request.chart == "gap_to_winner":
        result = get_gap_to_winner(**all_by_default, load_race_pace_data=loaders.load_race_pace_data)
        build = lambda: build_gap_to_winner_chart(result, **titled)
    elif request.chart == "top_speeds":
        result = get_top_speeds(**all_by_default, load_top_speeds=loaders.load_top_speeds)
        build = lambda: build_top_speeds_chart(result, **titled)
    elif request.chart == "tyre_degradation":
        # The "drivers" slot doubles as team names for this chart.
        result = get_tyre_degradation(
            year=request.year, event=request.event, session_type=request.session_type,
            teams=request.drivers or None, load_tyre_degradation=loaders.load_tyre_degradation,
        )
        build = lambda: build_tyre_degradation_chart(result, **titled)
    elif request.chart == "speed_quadrant":
        # The "drivers" slot doubles as team names for this chart.
        result = get_speed_quadrant(
            year=request.year, event=request.event, session_type=request.session_type,
            teams=request.drivers or None, load_speed_quadrant=loaders.load_speed_quadrant,
        )
        build = lambda: build_speed_quadrant_chart(result, **titled)
    elif request.chart == "gg_diagram":
        result = get_gg_diagram(**common, load_gg_diagram=loaders.load_gg_diagram)
        build = lambda: build_gg_diagram_chart(result, **titled)
    elif request.chart == "speed_delta_trace":
        result = get_speed_delta_trace(**common, load_speed_delta_trace=loaders.load_speed_delta_trace)
        build = lambda: build_speed_delta_trace_chart(result, **titled)
    elif request.chart == "gap_to_pole":
        result = get_gap_to_pole(**all_by_default, load_gap_to_pole=loaders.load_gap_to_pole)
        build = lambda: build_gap_to_pole_chart(result, **titled)
    elif request.chart == "position_changes":
        result = get_position_changes(**all_by_default, load_position_changes=loaders.load_position_changes)
        build = lambda: build_position_changes_chart(result, **titled)
    elif request.chart == "best_sectors":
        result = get_best_sectors(
            year=request.year, event=request.event, session_type=request.session_type,
            load_best_sectors=loaders.load_best_sectors,
        )
        build = lambda: build_best_sectors_chart(result, **titled)
    elif request.chart == "qualifying_segments_bar":
        result = get_qualifying_segments(
            year=request.year, event=request.event, load_qualifying_segments=loaders.load_qualifying_segments,
        )
        build = lambda: build_qualifying_segment_bar_chart(result, year=request.year, segment="Q3")
    elif request.chart == "qualifying_segments_evolution":
        result = get_qualifying_segments(
            year=request.year, event=request.event, load_qualifying_segments=loaders.load_qualifying_segments,
        )
        build = lambda: build_qualifying_pace_evolution_chart(result, year=request.year)
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
<style>
  /* Mirrors frontend/src/index.css's dark chat theme (.app-shell, .messages,
     .assistant-message, .plot), so this matches what the chart looks like
     embedded in the real app instead of a bare page. */
  body {{
    margin: 0;
    min-height: 100vh;
    background: #121214;
    font-family: "Inter", sans-serif;
    color: #cacace;
  }}
  .messages {{ max-width: 740px; margin: 6vh auto; padding: 0 20px; }}
  .assistant-message {{ display: flex; gap: 13px; font-size: 14px; line-height: 1.65; }}
  .assistant-avatar {{
    display: grid; height: 30px; width: 30px; flex-shrink: 0; place-items: center;
    border-radius: 9px; background: #e10600; color: white;
  }}
  .assistant-message strong {{ color: white; font-size: 13px; }}
  .plot {{
    margin-top: 14px; min-height: 360px;
    border: 1px solid rgba(255, 255, 255, 0.075);
    border-radius: 13px; background: rgba(255, 255, 255, 0.018);
    overflow: hidden;
  }}
</style>
</head>
<body>
<div class="messages">
  <div class="assistant-message">
    <span class="assistant-avatar">F1</span>
    <div style="flex: 1">
      <strong>F1 LLM</strong>
      <div class="plot" id="chart"></div>
    </div>
  </div>
</div>
<script>
const figure = {figure};
Plotly.newPlot("chart", figure.data, figure.layout, {{ responsive: true }});
</script>
</body>
</html>
"""


def to_html(figure: dict, title: str) -> str:
    return _PAGE.format(title=html.escape(title), figure=json.dumps(figure))


# (session_type, drivers) per chart, tuned for 2022 Brazil (Race + Qualifying
# are both fully cached locally), so the gallery renders instantly and
# offline. "drivers" doubles as team names for speed_quadrant/tyre_degradation;
# an empty list means "every driver/team" via build_preview's own defaulting.
GALLERY_DEFAULTS: dict[str, tuple[str, list[str]]] = {
    "lap_times": ("Race", ["VER", "HAM"]),
    "lap_times_by_compound": ("Race", ["VER"]),
    "telemetry": ("Race", ["VER", "HAM"]),
    "stints": ("Race", []),
    "race_pace": ("Race", ["VER", "HAM"]),
    "gap_to_winner": ("Race", ["VER", "HAM", "RUS"]),
    "top_speeds": ("Race", []),
    "tyre_degradation": ("Race", []),
    "speed_quadrant": ("Race", []),
    "gg_diagram": ("Qualifying", ["VER", "HAM"]),
    "speed_delta_trace": ("Qualifying", ["VER", "HAM"]),
    "gap_to_pole": ("Qualifying", []),
    "position_changes": ("Race", []),
    "best_sectors": ("Qualifying", []),
    "qualifying_segments_bar": ("Qualifying", []),
    "qualifying_segments_evolution": ("Qualifying", []),
}


def build_gallery(year: int, event: str, *, loaders) -> list[tuple[str, PreviewResult]]:
    """Builds every chart in CHARTS for one (year, event), each with sensible
    defaults. A chart that errors or isn't found is kept with its reason
    instead of aborting the whole gallery."""
    results = []
    for chart in CHARTS:
        session_type, drivers = GALLERY_DEFAULTS[chart]
        request = PreviewRequest(
            chart=chart, year=year, event=event, session_type=session_type, drivers=drivers
        )
        try:
            result = build_preview(request, loaders=loaders)
        except ValueError as exc:
            result = PreviewResult(found=False, reason=str(exc))
        results.append((chart, result))
    return results


_GALLERY_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2/plotly.min.js"></script>
<style>
  body {{
    margin: 0;
    min-height: 100vh;
    background: #121214;
    font-family: "Inter", sans-serif;
    color: #cacace;
  }}
  .messages {{ max-width: 740px; margin: 6vh auto 20vh; padding: 0 20px; }}
  .assistant-message {{ display: flex; gap: 13px; font-size: 14px; line-height: 1.65; margin-top: 38px; }}
  .assistant-avatar {{
    display: grid; height: 30px; width: 30px; flex-shrink: 0; place-items: center;
    border-radius: 9px; background: #e10600; color: white;
  }}
  .assistant-message strong {{ color: white; font-size: 13px; }}
  .plot {{
    margin-top: 14px; min-height: 360px;
    border: 1px solid rgba(255, 255, 255, 0.075);
    border-radius: 13px; background: rgba(255, 255, 255, 0.018);
    overflow: hidden;
  }}
  .not-found {{
    margin-top: 14px; padding: 12px 16px;
    border-radius: 13px; background: rgba(240, 145, 142, 0.08);
    color: #f0918e; font-size: 13px;
  }}
</style>
</head>
<body>
<div class="messages">
{entries}
</div>
<script>
const figures = {figures};
for (const [id, figure] of Object.entries(figures)) {{
  Plotly.newPlot(id, figure.data, figure.layout, {{ responsive: true }});
}}
</script>
</body>
</html>
"""


def gallery_to_html(results: list[tuple[str, PreviewResult]], title: str) -> str:
    entries = []
    figures = {}
    for index, (chart, result) in enumerate(results):
        chart_id = f"chart-{index}"
        if result.found:
            body = f'<div class="plot" id="{chart_id}"></div>'
            figures[chart_id] = result.figure
        else:
            body = f'<div class="not-found">Não encontrado: {html.escape(result.reason or "")}</div>'
        entries.append(
            f'<div class="assistant-message">'
            f'<span class="assistant-avatar">F1</span>'
            f'<div style="flex: 1"><strong>{html.escape(chart)}</strong>{body}</div>'
            f"</div>"
        )
    return _GALLERY_PAGE.format(
        title=html.escape(title), entries="\n".join(entries), figures=json.dumps(figures)
    )


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
    print(open_in_browser(result.figure, title=title))


def open_in_browser(figure: dict, title: str) -> str:
    """Writes the chart to a temporary HTML page, opens it and returns its path."""
    with tempfile.NamedTemporaryFile("w", suffix=".html", prefix="f1llm-", delete=False) as page:
        page.write(to_html(figure, title=title))
    webbrowser.open(f"file://{page.name}")
    return page.name


def gallery_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="f1llm-preview-gallery")
    parser.add_argument("year", type=int, nargs="?", default=2022)
    parser.add_argument("event", nargs="?", default="Brazil")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # Imported here so the pure seams above don't pull in FastF1.
    from f1llm import fastf1_client

    results = build_gallery(args.year, args.event, loaders=fastf1_client)
    for chart, result in results:
        if not result.found:
            print(f"f1llm-preview-gallery: {chart} not found: {result.reason}", file=sys.stderr)

    title = f"Galeria de gráficos — {args.year} {args.event}"
    print(open_gallery_in_browser(results, title=title))


def open_gallery_in_browser(results: list[tuple[str, PreviewResult]], title: str) -> str:
    """Writes every chart to one temporary HTML page, opens it and returns its path."""
    with tempfile.NamedTemporaryFile("w", suffix=".html", prefix="f1llm-gallery-", delete=False) as page:
        page.write(gallery_to_html(results, title=title))
    webbrowser.open(f"file://{page.name}")
    return page.name
