import statistics
from dataclasses import asdict, dataclass

from f1llm.tools.lap_times import build_lap_times_chart, get_lap_times
from f1llm.tools.race_pace import build_race_pace_chart, get_race_pace
from f1llm.tools.session_results import get_session_results
from f1llm.tools.stints import build_stints_chart, get_stints
from f1llm.tools.telemetry import build_telemetry_chart, get_telemetry_comparison


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

    return result, summarize, lambda: build_lap_times_chart(result.laps)


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


_HANDLERS = {
    "get_telemetry_comparison": _telemetry,
    "get_race_pace": _race_pace,
    "get_lap_times": _lap_times,
    "get_session_results": _session_results,
    "get_stints": _stints,
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


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
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
        {**_session_properties(["Race", "Qualifying", "Sprint"]), "drivers": _DRIVERS, "plot": _PLOT},
        ["year", "event", "session_type", "drivers", "plot"],
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
]
