import statistics
from dataclasses import asdict, dataclass

from f1llm.tools.lap_times import build_lap_times_by_compound_chart, build_lap_times_chart, get_lap_times
from f1llm.tools.gap_to_winner import build_gap_to_winner_chart, get_gap_to_winner
from f1llm.tools.race_pace import build_race_pace_chart, get_race_pace
from f1llm.tools.session_results import get_session_results
from f1llm.tools.standings import (
    build_driver_standings_chart,
    build_team_standings_chart,
    get_driver_standings,
    get_team_standings,
)
from f1llm.tools.stints import build_stints_chart, get_stints
from f1llm.tools.telemetry import build_telemetry_chart, get_telemetry_comparison
from f1llm.tools.top_speeds import build_top_speeds_chart, get_top_speeds
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
from f1llm.tools.tyre_degradation import build_tyre_degradation_chart, get_tyre_degradation


@dataclass(frozen=True)
class ToolOutcome:
    content: dict
    figure: dict | None = None
    is_error: bool = False


def run_tool(name: str, tool_input: dict, *, loaders) -> ToolOutcome:
    try:
        result, summarize, chart = _HANDLERS[name](tool_input, loaders)
    except ValueError as exc:
        return ToolOutcome(content={"error": str(exc)}, is_error=True)
    if not result.found:
        return ToolOutcome(content={"error": result.reason}, is_error=True)

    figure = chart() if chart is not None and tool_input.get("plot") else None
    return ToolOutcome(content=summarize(), figure=figure)


def _session(tool_input: dict) -> dict:
    return dict(
        year=tool_input["year"],
        event=tool_input["event"],
        session_type=tool_input["session_type"],
    )


def _session_results(tool_input, loaders):
    result = get_session_results(**_session(tool_input), load_results=loaders.load_results)
    return result, lambda: {"results": [asdict(row) for row in result.results]}, None


def _stints(tool_input, loaders):
    result = get_stints(
        **_session(tool_input),
        # The model may send an empty list; the tool wants None for "every driver".
        drivers=tool_input.get("drivers") or None,
        load_stint_data=loaders.load_stint_data,
    )

    def summarize():
        return {
            "event_name": result.event_name,
            "drivers": [asdict(driver) for driver in result.drivers],
            "safety_car_periods": [asdict(period) for period in result.safety_car_periods],
        }

    def chart():
        return build_stints_chart(result, year=tool_input["year"], session_type=tool_input["session_type"])

    return result, summarize, chart


def _lap_times(tool_input, loaders):
    result = get_lap_times(
        **_session(tool_input), drivers=tool_input["drivers"], load_laps=loaders.load_laps
    )

    def summarize():
        laps_by_driver = {}
        for lap in result.laps:
            laps_by_driver.setdefault(lap.driver_code, []).append(lap)
        return {"drivers": [_lap_times_summary(code, laps) for code, laps in laps_by_driver.items()]}

    def chart():
        if tool_input.get("by_compound"):
            return build_lap_times_by_compound_chart(result.laps)
        return build_lap_times_chart(result.laps)

    return result, summarize, chart


def _lap_times_summary(driver_code, laps):
    timed = [lap for lap in laps if lap.seconds is not None]
    best = min(timed, key=lambda lap: lap.seconds, default=None)
    seconds = [lap.seconds for lap in timed]
    return {
        "driver_code": driver_code,
        "best_lap": {"lap": best.lap_number, "seconds": best.seconds} if best else None,
        "mean_seconds": round(statistics.mean(seconds), 3) if seconds else None,
        "median_seconds": round(statistics.median(seconds), 3) if seconds else None,
        "laps": [{"lap": lap.lap_number, "seconds": lap.seconds} for lap in laps],
    }


_GAP_SAMPLE_EVERY = 5


def _race_pace(tool_input, loaders):
    result = get_race_pace(
        **_session(tool_input),
        drivers=tool_input.get("drivers") or None,
        load_race_pace_data=loaders.load_race_pace_data,
    )

    def summarize():
        return {
            "event_name": result.event_name,
            "drivers": [_race_pace_summary(driver) for driver in result.drivers],
            "safety_car_periods": [asdict(period) for period in result.safety_car_periods],
        }

    def chart():
        return build_race_pace_chart(result, year=tool_input["year"], session_type=tool_input["session_type"])

    return result, summarize, chart


def _race_pace_summary(driver):
    last_lap = len(driver.gaps_to_reference)
    sampled_laps = [lap for lap in range(1, last_lap + 1) if lap % _GAP_SAMPLE_EVERY == 0 or lap == last_lap]
    return {
        "driver_code": driver.driver_code,
        "position": driver.position,
        "team_name": driver.team_name,
        "pit_out_laps": driver.pit_out_laps,
        "gaps_to_reference": [
            {"lap": lap, "seconds": round(driver.gaps_to_reference[lap - 1], 3)} for lap in sampled_laps
        ],
    }


def _gap_to_winner(tool_input, loaders):
    result = get_gap_to_winner(
        **_session(tool_input),
        drivers=tool_input.get("drivers") or None,
        load_race_pace_data=loaders.load_race_pace_data,
    )

    def summarize():
        return {
            "event_name": result.event_name,
            "drivers": [_gap_to_winner_summary(driver) for driver in result.drivers],
            "safety_car_periods": [asdict(period) for period in result.safety_car_periods],
        }

    def chart():
        return build_gap_to_winner_chart(result, year=tool_input["year"], session_type=tool_input["session_type"])

    return result, summarize, chart


def _gap_to_winner_summary(driver):
    last_lap = len(driver.gaps_to_winner)
    sampled_laps = [lap for lap in range(1, last_lap + 1) if lap % _GAP_SAMPLE_EVERY == 0 or lap == last_lap]
    return {
        "driver_code": driver.driver_code,
        "position": driver.position,
        "team_name": driver.team_name,
        "pit_out_laps": driver.pit_out_laps,
        "gaps_to_winner": [
            {"lap": lap, "seconds": round(driver.gaps_to_winner[lap - 1], 3)} for lap in sampled_laps
        ],
    }


def _top_speeds(tool_input, loaders):
    result = get_top_speeds(
        **_session(tool_input),
        drivers=tool_input.get("drivers") or None,
        load_top_speeds=loaders.load_top_speeds,
    )

    def summarize():
        return {
            "event_name": result.event_name,
            "session_max": result.session_max,
            "drivers": [
                {"driver_code": driver.driver_code, "top_speed": driver.top_speeds[0], "average": driver.average}
                for driver in result.drivers
            ],
        }

    def chart():
        return build_top_speeds_chart(result, year=tool_input["year"], session_type=tool_input["session_type"])

    return result, summarize, chart


FULL_THROTTLE_PCT = 99.0


def _telemetry(tool_input, loaders):
    laps = tool_input.get("laps")
    result = get_telemetry_comparison(
        **_session(tool_input),
        drivers=tool_input["drivers"],
        laps={entry["driver"]: entry["lap"] for entry in laps} if laps else None,
        load_telemetry=loaders.load_telemetry,
    )

    def summarize():
        samples_by_driver = {}
        for sample in result.samples:
            samples_by_driver.setdefault(sample.driver_code, []).append(sample)
        return {"drivers": [_telemetry_summary(code, samples) for code, samples in samples_by_driver.items()]}

    return result, summarize, lambda: build_telemetry_chart(result.samples)


def _telemetry_summary(driver_code, samples):
    # A sample's state holds until the next sample, so each one covers the distance up to it.
    segments = [(sample, following.distance - sample.distance) for sample, following in zip(samples, samples[1:])]
    lap_distance = sum(length for _, length in segments)

    def pct_of_distance(condition):
        covered = sum(length for sample, length in segments if condition(sample))
        return round(100 * covered / lap_distance, 1) if lap_distance else None

    return {
        "driver_code": driver_code,
        "lap": samples[0].lap_number,
        "top_speed_kmh": max(sample.speed for sample in samples),
        "min_speed_kmh": min(sample.speed for sample in samples),
        "full_throttle_pct_of_distance": pct_of_distance(lambda s: s.throttle >= FULL_THROTTLE_PCT),
        "braking_pct_of_distance": pct_of_distance(lambda s: s.brake),
        "min_gear": min(sample.gear for sample in samples),
        "max_gear": max(sample.gear for sample in samples),
    }


def _driver_standings(tool_input, loaders):
    result = get_driver_standings(
        year=tool_input["year"],
        event=tool_input.get("event"),
        load_driver_standings=loaders.load_driver_standings,
    )

    def summarize():
        return {"standings": [asdict(standing) for standing in result.standings]}

    def chart():
        return build_driver_standings_chart(result.standings)

    return result, summarize, chart


def _team_standings(tool_input, loaders):
    result = get_team_standings(
        year=tool_input["year"],
        event=tool_input.get("event"),
        load_team_standings=loaders.load_team_standings,
    )

    def summarize():
        return {"standings": [asdict(standing) for standing in result.standings]}

    def chart():
        return build_team_standings_chart(result.standings)

    return result, summarize, chart


def _tyre_degradation(tool_input, loaders):
    result = get_tyre_degradation(
        **_session(tool_input),
        teams=tool_input.get("teams") or None,
        load_tyre_degradation=loaders.load_tyre_degradation,
    )

    def summarize():
        return {
            "event_name": result.event_name,
            "entries": [asdict(entry) for entry in result.entries],
        }

    def chart():
        return build_tyre_degradation_chart(
            result, year=tool_input["year"], session_type=tool_input["session_type"]
        )

    return result, summarize, chart


def _speed_quadrant(tool_input, loaders):
    result = get_speed_quadrant(
        **_session(tool_input),
        teams=tool_input.get("teams") or None,
        load_speed_quadrant=loaders.load_speed_quadrant,
    )

    def summarize():
        return {
            "event_name": result.event_name,
            "teams": [asdict(team) for team in result.teams],
        }

    def chart():
        return build_speed_quadrant_chart(
            result, year=tool_input["year"], session_type=tool_input["session_type"]
        )

    return result, summarize, chart


def _gg_diagram(tool_input, loaders):
    result = get_gg_diagram(
        **_session(tool_input),
        drivers=tool_input["drivers"],
        load_gg_diagram=loaders.load_gg_diagram,
    )

    def summarize():
        return {
            "event_name": result.event_name,
            "drivers": [
                {
                    "driver_code": driver.driver_code,
                    "compound": driver.compound,
                    "average_combined_g": round(driver.average_combined_g, 2),
                }
                for driver in result.drivers
            ],
        }

    def chart():
        return build_gg_diagram_chart(result, year=tool_input["year"], session_type=tool_input["session_type"])

    return result, summarize, chart


def _speed_delta_trace(tool_input, loaders):
    laps = tool_input.get("laps")
    result = get_speed_delta_trace(
        **_session(tool_input),
        drivers=tool_input["drivers"],
        laps={entry["driver"]: entry["lap"] for entry in laps} if laps else None,
        load_speed_delta_trace=loaders.load_speed_delta_trace,
    )

    def summarize():
        return {
            "event_name": result.event_name,
            "drivers": [
                {
                    "driver_code": driver.driver_code,
                    "top_speed_kmh": max(point.speed for point in driver.points),
                    "min_speed_kmh": min(point.speed for point in driver.points),
                }
                for driver in result.drivers
            ],
            # Positive = the second driver is ahead of the first at that point.
            "final_delta_seconds": round(result.delta[-1].seconds, 3) if result.delta else None,
            "corners": [asdict(corner) for corner in result.corners],
        }

    def chart():
        return build_speed_delta_trace_chart(
            result, year=tool_input["year"], session_type=tool_input["session_type"]
        )

    return result, summarize, chart


def _gap_to_pole(tool_input, loaders):
    result = get_gap_to_pole(
        **_session(tool_input),
        drivers=tool_input.get("drivers") or None,
        load_gap_to_pole=loaders.load_gap_to_pole,
    )

    def summarize():
        return {
            "event_name": result.event_name,
            "drivers": [asdict(driver) for driver in result.drivers],
        }

    def chart():
        return build_gap_to_pole_chart(result, year=tool_input["year"], session_type=tool_input["session_type"])

    return result, summarize, chart


def _position_changes(tool_input, loaders):
    result = get_position_changes(
        **_session(tool_input),
        drivers=tool_input.get("drivers") or None,
        load_position_changes=loaders.load_position_changes,
    )

    def summarize():
        return {
            "event_name": result.event_name,
            "drivers": [
                {
                    "driver_code": driver.driver_code,
                    "positions": [{"lap": point.lap_number, "position": point.position} for point in driver.points],
                }
                for driver in result.drivers
            ],
        }

    def chart():
        return build_position_changes_chart(
            result, year=tool_input["year"], session_type=tool_input["session_type"]
        )

    return result, summarize, chart


def _best_sectors(tool_input, loaders):
    result = get_best_sectors(**_session(tool_input), load_best_sectors=loaders.load_best_sectors)

    def summarize():
        return {
            "event_name": result.event_name,
            "drivers": [asdict(driver) for driver in result.drivers],
        }

    def chart():
        return build_best_sectors_chart(result, year=tool_input["year"], session_type=tool_input["session_type"])

    return result, summarize, chart


def _qualifying_segments(tool_input, loaders):
    result = get_qualifying_segments(
        year=tool_input["year"],
        event=tool_input["event"],
        load_qualifying_segments=loaders.load_qualifying_segments,
    )

    def summarize():
        return {"event_name": result.event_name, "teams": [asdict(team) for team in result.teams]}

    def chart():
        if tool_input.get("chart_type") == "evolution":
            return build_qualifying_pace_evolution_chart(result, year=tool_input["year"])
        return build_qualifying_segment_bar_chart(
            result, year=tool_input["year"], segment=tool_input.get("segment") or "Q3"
        )

    return result, summarize, chart


_HANDLERS = {
    "get_telemetry_comparison": _telemetry,
    "get_race_pace": _race_pace,
    "get_gap_to_winner": _gap_to_winner,
    "get_lap_times": _lap_times,
    "get_session_results": _session_results,
    "get_stints": _stints,
    "get_driver_standings": _driver_standings,
    "get_team_standings": _team_standings,
    "get_top_speeds": _top_speeds,
    "get_tyre_degradation": _tyre_degradation,
    "get_speed_quadrant": _speed_quadrant,
    "get_gg_diagram": _gg_diagram,
    "get_speed_delta_trace": _speed_delta_trace,
    "get_gap_to_pole": _gap_to_pole,
    "get_position_changes": _position_changes,
    "get_best_sectors": _best_sectors,
    "get_qualifying_segments": _qualifying_segments,
}


def _session_properties(session_types: list[str]) -> dict:
    return {
        "year": {"type": "integer", "description": "Season year, 2018 or later."},
        "event": {
            "type": "string",
            "description": 'Grand Prix name, country or circuit in English, e.g. "Monza", "Brazil", "Abu Dhabi".',
        },
        "session_type": {"type": "string", "enum": session_types},
    }


_DRIVERS = {
    "type": "array",
    "items": {"type": "string"},
    "description": 'Three-letter driver codes, e.g. ["VER", "HAM"].',
}
_PLOT = {
    "type": "boolean",
    "description": "True to also show the user a chart. Use it when the user asks for a chart or comparison "
    "that is easier to see than to read; false for a plain factual question.",
}
_TEAMS = {
    "type": "array",
    "items": {"type": "string"},
    "description": 'Team names to compare, e.g. ["Ferrari", "Red Bull Racing"]. Omit for the top 4 '
    "finishing teams.",
}
_STANDINGS_PROPERTIES = {
    "year": {"type": "integer", "description": "Season year, 2018 or later."},
    "event": {
        "type": "string",
        "description": 'Grand Prix name, country or circuit in English, e.g. "Monza", "Brazil", "Abu Dhabi". '
        "Omit for the latest standings in the season.",
    },
}


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


TOOL_DEFINITIONS = [
    _tool(
        "get_session_results",
        "Final classification of a session: position, driver, team, time or gap, points.",
        _session_properties(["Race", "Qualifying", "Sprint"]),
        ["year", "event", "session_type"],
    ),
    _tool(
        "get_lap_times",
        "Every lap time of the given drivers in a session, with each driver's best lap, mean and median.",
        {
            **_session_properties(["Race", "Qualifying", "Sprint"]),
            "drivers": _DRIVERS,
            "by_compound": {
                "type": "boolean",
                "description": "When plotting, color each lap by tyre compound instead of one line per "
                "driver — best for seeing degradation/pit stops within a single driver's laps.",
            },
            "plot": _PLOT,
        },
        ["year", "event", "session_type", "drivers", "by_compound", "plot"],
    ),
    _tool(
        "get_telemetry_comparison",
        "Car telemetry (speed, throttle, brake, gear) over one lap per driver: top and minimum speed, "
        "share of the lap flat out and braking, gear range. Uses each driver's fastest lap unless laps is given.",
        {
            **_session_properties(["Race", "Qualifying", "Sprint"]),
            "drivers": _DRIVERS,
            "laps": {
                "type": "array",
                "description": "Specific lap per driver; omit to use each driver's fastest lap.",
                "items": {
                    "type": "object",
                    "properties": {"driver": {"type": "string"}, "lap": {"type": "integer"}},
                    "required": ["driver", "lap"],
                    "additionalProperties": False,
                },
            },
            "plot": _PLOT,
        },
        ["year", "event", "session_type", "drivers", "plot"],
    ),
    _tool(
        "get_stints",
        "Tyre strategy: each driver's stints with compound, laps, whether the set was new, and the "
        "Safety car / Virtual safety car periods. 2019 onwards. Omit drivers for the whole field.",
        {**_session_properties(["Race", "Sprint", "Qualifying"]), "drivers": _DRIVERS, "plot": _PLOT},
        ["year", "event", "session_type", "plot"],
    ),
    _tool(
        "get_race_pace",
        "Race pace: each driver's cumulative gap to a reference driver who laps at the average pace of the "
        "lead-lap drivers (positive = ahead, i.e. faster), sampled every 5 laps and at the flag, plus pit-out "
        "laps and Safety car / Virtual safety car periods. Omit drivers for the whole field.",
        {**_session_properties(["Race", "Sprint"]), "drivers": _DRIVERS, "plot": _PLOT},
        ["year", "event", "session_type", "plot"],
    ),
    _tool(
        "get_gap_to_winner",
        "Each driver's cumulative time gap to the race winner, lap by lap (negative = behind), plus "
        "pit-out laps and Safety car / Virtual safety car periods. Defaults to the top 6 finishers "
        "when drivers is omitted.",
        {**_session_properties(["Race", "Sprint"]), "drivers": _DRIVERS, "plot": _PLOT},
        ["year", "event", "session_type", "plot"],
    ),
    _tool(
        "get_driver_standings",
        "Drivers' championship standings: position, driver, team, points, wins. Omit event for the latest "
        "standings in the season; give a Grand Prix to see the standings through that round.",
        {**_STANDINGS_PROPERTIES, "plot": _PLOT},
        ["year", "plot"],
    ),
    _tool(
        "get_team_standings",
        "Teams' (constructors') championship standings: position, team, points, wins. Omit event for the "
        "latest standings in the season; give a Grand Prix to see the standings through that round.",
        {**_STANDINGS_PROPERTIES, "plot": _PLOT},
        ["year", "plot"],
    ),
    _tool(
        "get_top_speeds",
        "Each driver's own 15 fastest laps by true top speed (km/h, from telemetry) in the session, sorted "
        "descending, with their average and the single fastest speed of the whole session. Omit drivers for "
        "the whole field.",
        {**_session_properties(["Race", "Qualifying", "Sprint"]), "drivers": _DRIVERS, "plot": _PLOT},
        ["year", "event", "session_type", "plot"],
    ),
    _tool(
        "get_tyre_degradation",
        "How each team's dry tyre compounds (SOFT/MEDIUM/HARD) degrade with tyre age: fuel-corrected "
        "lap time per clean lap, plus the fitted slope (seconds per lap of tyre age) and R^2 when "
        "there are at least 3 clean laps. 2019 onwards; Race and Sprint only (no single-lap "
        "Qualifying stints). Omit teams for the top 4 finishing teams.",
        {**_session_properties(["Race", "Sprint"]), "teams": _TEAMS, "plot": _PLOT},
        ["year", "event", "session_type", "plot"],
    ),
    _tool(
        "get_speed_quadrant",
        "Each team's mean speed (lap distance / lap time) vs true top speed (telemetry peak), from its "
        "fastest lap of the session — shows which teams trade top speed for cornering/acceleration speed "
        "and vice versa. One point per team. Omit teams for the whole field.",
        {**_session_properties(["Race", "Qualifying", "Sprint"]), "teams": _TEAMS, "plot": _PLOT},
        ["year", "event", "session_type", "plot"],
    ),
    _tool(
        "get_gg_diagram",
        "Lateral vs longitudinal acceleration (in g) throughout each driver's fastest lap, derived from "
        "speed and position telemetry — shows how hard the car brakes, accelerates and corners, and each "
        "driver's average combined (magnitude) acceleration. Best with 2-3 drivers.",
        {**_session_properties(["Race", "Qualifying", "Sprint"]), "drivers": _DRIVERS, "plot": _PLOT},
        ["year", "event", "session_type", "drivers", "plot"],
    ),
    _tool(
        "get_speed_delta_trace",
        "Speed (km/h) over lap distance for exactly 2 drivers' fastest laps (or a specific lap each), with "
        "the accumulated time delta between them and each corner's position. Shows exactly where on track "
        "one driver gains or loses time to the other. Requires exactly 2 drivers.",
        {
            **_session_properties(["Race", "Qualifying", "Sprint"]),
            "drivers": _DRIVERS,
            "laps": {
                "type": "array",
                "description": "Specific lap per driver; omit to use each driver's fastest lap.",
                "items": {
                    "type": "object",
                    "properties": {"driver": {"type": "string"}, "lap": {"type": "integer"}},
                    "required": ["driver", "lap"],
                    "additionalProperties": False,
                },
            },
            "plot": _PLOT,
        },
        ["year", "event", "session_type", "drivers", "plot"],
    ),
    _tool(
        "get_gap_to_pole",
        "Each driver's gap (seconds) to the fastest lap of the session, sorted fastest to slowest. "
        "Omit drivers for the whole field.",
        {**_session_properties(["Race", "Qualifying", "Sprint"]), "drivers": _DRIVERS, "plot": _PLOT},
        ["year", "event", "session_type", "plot"],
    ),
    _tool(
        "get_position_changes",
        "Each driver's race position lap by lap, to see overtakes and position changes through the race. "
        "Omit drivers for the whole field.",
        {**_session_properties(["Race", "Sprint"]), "drivers": _DRIVERS, "plot": _PLOT},
        ["year", "event", "session_type", "plot"],
    ),
    _tool(
        "get_best_sectors",
        "Each driver's best Sector 1/2/3 time in the session (each sector's best may come from a "
        "different lap). The chart shows the 8 fastest drivers per sector.",
        {**_session_properties(["Race", "Qualifying", "Sprint"]), "plot": _PLOT},
        ["year", "event", "session_type", "plot"],
    ),
    _tool(
        "get_qualifying_segments",
        "Each team's best lap time in Q1, Q2 and Q3 (null for a segment a team didn't reach). "
        "chart_type 'bar' (default) shows the gap to the fastest in one segment; 'evolution' shows each "
        "team's time across the segments it reached.",
        {
            "year": {"type": "integer", "description": "Season year, 2018 or later."},
            "event": {
                "type": "string",
                "description": 'Grand Prix name, country or circuit in English, e.g. "Monza", "Brazil".',
            },
            "chart_type": {"type": "string", "enum": ["bar", "evolution"]},
            "segment": {
                "type": "string",
                "enum": ["Q1", "Q2", "Q3"],
                "description": "Which segment to plot when chart_type is 'bar'. Defaults to Q3.",
            },
            "plot": _PLOT,
        },
        ["year", "event", "plot"],
    ),
]
