from pathlib import Path

import fastf1
import numpy as np
import pandas as pd
from fastf1.ergast import Ergast

from f1llm.errors import SessionDataUnavailable
from f1llm.settings import get_settings

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".fastf1cache"
_cache_enabled = False


def _ensure_cache_enabled() -> None:
    global _cache_enabled
    if not _cache_enabled:
        _CACHE_DIR.mkdir(exist_ok=True)
        fastf1.Cache.enable_cache(str(_CACHE_DIR))
        # F1 now requires an authenticated F1TV account to fetch the livetiming
        # archive (since Oct 2026); reads F1_USERNAME/F1_PASSWORD itself.
        if get_settings().has_f1tv_credentials():
            fastf1.set_auth_method("password")
        _cache_enabled = True


def load_results(year: int, event: str, session_type: str) -> list[dict]:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=False, telemetry=False, weather=False, messages=False)
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    results = session.results
    if results is None or results.empty:
        raise SessionDataUnavailable(
            f"No results found for {event} {year} {session_type}"
        )

    return results.to_dict("records")


def load_laps(
    year: int, event: str, session_type: str, drivers: list[str]
) -> list[dict]:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    laps = laps[laps["Driver"].isin(drivers)]
    if laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for drivers {drivers} in {event} {year} {session_type}"
        )

    return [
        {
            "Driver": row["Driver"],
            "LapNumber": row["LapNumber"],
            "LapTime": None if pd.isna(row["LapTime"]) else row["LapTime"],
            "Compound": None if pd.isna(row["Compound"]) else row["Compound"],
        }
        for row in laps[["Driver", "LapNumber", "LapTime", "Compound"]].to_dict("records")
    ]


def load_telemetry(
    year: int,
    event: str,
    session_type: str,
    drivers: list[str],
    laps: dict[str, int] | None,
) -> list[dict]:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        session_laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    requested_laps = laps or {}
    rows: list[dict] = []

    for driver in drivers:
        driver_laps = session_laps.pick_drivers(driver)
        if driver_laps.empty:
            continue

        requested_lap_number = requested_laps.get(driver)
        if requested_lap_number is not None:
            matching = driver_laps.pick_laps(requested_lap_number)
            if matching.empty:
                continue
            lap = matching.iloc[0]
        else:
            lap = driver_laps.pick_fastest()
            if lap is None:
                continue

        car_data = lap.get_car_data().add_distance()
        for _, sample in car_data.iterrows():
            rows.append(
                {
                    "Driver": driver,
                    "LapNumber": lap["LapNumber"],
                    "Distance": sample["Distance"],
                    "Speed": sample["Speed"],
                    "Throttle": sample["Throttle"],
                    "Brake": sample["Brake"],
                    "nGear": sample["nGear"],
                }
            )

    if not rows:
        raise SessionDataUnavailable(
            f"No telemetry data found for drivers {drivers} in {event} {year} {session_type}"
        )

    return rows


def load_top_speeds(
    year: int, event: str, session_type: str, drivers: list[str] | None = None
) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    driver_codes = drivers if drivers is not None else sorted(laps["Driver"].unique())

    rows: list[dict] = []
    for driver in driver_codes:
        for _, lap in laps.pick_drivers(driver).iterlaps():
            car_data = lap.get_car_data()
            if car_data.empty:
                continue
            rows.append({
                "Driver": driver,
                "LapNumber": lap["LapNumber"],
                "TopSpeed": car_data["Speed"].max(),
            })

    if not rows:
        raise SessionDataUnavailable(
            f"No telemetry-based top speed found for drivers {drivers} in {event} {year} {session_type}"
        )

    return {"event_name": session.event["EventName"], "rows": rows}


def _none_if_missing(value):
    return None if pd.isna(value) else value


def load_stint_data(year: int, event: str, session_type: str) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    lap_columns = [
        "Driver", "LapNumber", "Position", "Stint",
        "Compound", "TyreLife", "FreshTyre", "TrackStatus",
    ]
    return {
        "event_name": session.event["EventName"],
        "laps": [
            {column: _none_if_missing(row[column]) for column in lap_columns}
            for row in laps[lap_columns].to_dict("records")
        ],
        "results": [
            {
                "Abbreviation": row["Abbreviation"],
                "Position": _none_if_missing(row["Position"]),
            }
            for row in session.results[["Abbreviation", "Position"]].to_dict("records")
        ],
    }


def load_race_pace_data(year: int, event: str, session_type: str) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    lap_columns = ["Driver", "LapNumber", "Time", "Stint", "Position", "TrackStatus"]
    result_columns = ["Abbreviation", "Position", "TeamName", "TeamColor"]
    return {
        "event_name": session.event["EventName"],
        # Every driver's first lap starts at the same instant: the race start.
        "race_start": laps[laps["LapNumber"] == 1]["LapStartTime"].min(),
        "laps": [
            {column: _none_if_missing(row[column]) for column in lap_columns}
            for row in laps[lap_columns].to_dict("records")
        ],
        "results": [
            {column: _none_if_missing(row[column]) for column in result_columns}
            for row in session.results[result_columns].to_dict("records")
        ],
    }


def load_tyre_degradation(year: int, event: str, session_type: str) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        # ADR 0005: FastF1's own outlier filter, reused instead of a homemade threshold.
        laps = session.laps.pick_quicklaps()
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    result_columns = ["Abbreviation", "Position", "TeamName", "TeamColor"]
    results = [
        {column: _none_if_missing(row[column]) for column in result_columns}
        for row in session.results[result_columns].to_dict("records")
    ]
    team_by_driver = {row["Abbreviation"]: row["TeamName"] for row in results}

    lap_columns = [
        "Driver", "Compound", "LapNumber", "TyreLife", "LapTime",
        "TrackStatus", "PitInTime", "PitOutTime",
    ]
    return {
        "event_name": session.event["EventName"],
        "laps": [
            {
                "Team": team_by_driver.get(row["Driver"]),
                "Compound": row["Compound"],
                "LapNumber": row["LapNumber"],
                "TyreLife": _none_if_missing(row["TyreLife"]),
                "LapTime": row["LapTime"],
                "TrackStatus": row["TrackStatus"],
                "PitInTime": _none_if_missing(row["PitInTime"]),
                "PitOutTime": _none_if_missing(row["PitOutTime"]),
            }
            for row in laps[lap_columns].to_dict("records")
        ],
        "results": [
            {
                "Abbreviation": row["Abbreviation"],
                "Position": row["Position"],
                "Team": row["TeamName"],
                "TeamColor": row["TeamColor"],
            }
            for row in results
        ],
    }


def load_speed_quadrant(year: int, event: str, session_type: str) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    result_columns = ["Abbreviation", "TeamName", "TeamColor"]
    team_by_driver = {
        row["Abbreviation"]: (row["TeamName"], row["TeamColor"])
        for row in session.results[result_columns].to_dict("records")
    }

    rows: list[dict] = []
    for driver in sorted(laps["Driver"].unique()):
        fastest = laps.pick_drivers(driver).pick_fastest()
        if fastest is None or pd.isna(fastest["LapTime"]):
            continue

        car_data = fastest.get_car_data().add_distance()
        if car_data.empty:
            continue

        team, team_color = team_by_driver.get(driver, (None, None))
        rows.append({
            "Team": team,
            "TeamColor": team_color,
            "LapTime": fastest["LapTime"],
            "TopSpeed": car_data["Speed"].max(),
            "LapDistance": car_data["Distance"].iloc[-1],
        })

    if not rows:
        raise SessionDataUnavailable(
            f"No telemetry-based lap data found for {event} {year} {session_type}"
        )

    return {"event_name": session.event["EventName"], "laps": rows}


def load_gg_diagram(year: int, event: str, session_type: str, drivers: list[str]) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    telemetry_columns = ["Speed", "Distance", "Time", "X", "Y"]
    driver_entries = []
    for driver in drivers:
        fastest = laps.pick_drivers(driver).pick_fastest()
        if fastest is None:
            continue

        # ADR 0007: merged car + position data, with the distance channel the
        # acceleration model differentiates X/Y against.
        telemetry = fastest.get_telemetry().add_distance()
        if telemetry.empty:
            continue

        driver_entries.append({
            "driver_code": driver,
            "compound": fastest["Compound"] or "UNKNOWN",
            "telemetry": [
                {column: row[column] for column in telemetry_columns}
                for row in telemetry[telemetry_columns].to_dict("records")
            ],
        })

    if not driver_entries:
        raise SessionDataUnavailable(
            f"No telemetry found for drivers {drivers} in {event} {year} {session_type}"
        )

    return {"event_name": session.event["EventName"], "drivers": driver_entries}


def _delta_time(reference_lap, compare_lap) -> tuple[pd.Series, "fastf1.core.Telemetry", "fastf1.core.Telemetry"]:
    """Port of fastf1.utils.delta_time(), removed upstream in 3.9.0a0."""
    ref = reference_lap.get_car_data(interpolate_edges=True).add_distance()
    comp = compare_lap.get_car_data(interpolate_edges=True).add_distance()

    def mini_pro(stream):
        dstream_start = stream[1] - stream[0]
        dstream_end = stream[-1] - stream[-2]
        return np.concatenate([[stream[0] - dstream_start], stream, [stream[-1] + dstream_end]])

    ltime = mini_pro(comp["Time"].dt.total_seconds().to_numpy())
    multiplier = ref.Distance.iat[-1] / comp.Distance.iat[-1]
    ldistance = mini_pro(comp["Distance"].to_numpy()) * multiplier
    lap_time = np.interp(ref["Distance"], ldistance, ltime)

    delta = lap_time - ref["Time"].dt.total_seconds()

    return delta, ref, comp


def load_speed_delta_trace(
    year: int, event: str, session_type: str, drivers: list[str], laps: dict[str, int] | None
) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        session_laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if session_laps is None or session_laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    requested_laps = laps or {}
    picked_laps = []
    for driver in drivers:
        driver_laps = session_laps.pick_drivers(driver)
        lap_number = requested_laps.get(driver)
        if lap_number is not None:
            matching = driver_laps.pick_laps(lap_number)
            lap = matching.iloc[0] if not matching.empty else None
        else:
            lap = driver_laps.pick_fastest()
        if lap is None:
            raise SessionDataUnavailable(
                f"No valid lap found for driver {driver!r} in {event} {year} {session_type}"
            )
        picked_laps.append(lap)

    reference_lap, compare_lap = picked_laps
    # fastf1.utils.delta_time() was removed upstream in 3.9.0a0 (it had been
    # deprecated since 3.0.0), so this ports its last implementation here.
    # Its own ref/compare telemetry (not a separate get_telemetry() call) is
    # what the delta was actually computed against, so the speed traces stay
    # on a consistent distance axis with the delta line.
    delta, ref_telemetry, compare_telemetry = _delta_time(reference_lap, compare_lap)

    def driver_speed_trace(driver_code: str, telemetry) -> dict:
        return {
            "driver_code": driver_code,
            "distance": telemetry["Distance"].tolist(),
            "speed": telemetry["Speed"].tolist(),
        }

    circuit_info = session.get_circuit_info()
    corners = (
        [
            {"number": int(row["Number"]), "distance": float(row["Distance"])}
            for row in circuit_info.corners[["Number", "Distance"]].to_dict("records")
        ]
        if circuit_info is not None
        else []
    )

    return {
        "event_name": session.event["EventName"],
        "drivers": [
            driver_speed_trace(drivers[0], ref_telemetry),
            driver_speed_trace(drivers[1], compare_telemetry),
        ],
        "delta": {
            "distance": ref_telemetry["Distance"].tolist(),
            "seconds": delta.tolist(),
        },
        "corners": corners,
    }


def load_gap_to_pole(year: int, event: str, session_type: str, drivers: list[str] | None) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    team_colors = {
        row["Abbreviation"]: row["TeamColor"]
        for row in session.results[["Abbreviation", "TeamColor"]].to_dict("records")
    }

    driver_codes = drivers if drivers is not None else sorted(laps["Driver"].unique())
    rows = []
    for driver in driver_codes:
        fastest = laps.pick_drivers(driver).pick_fastest()
        if fastest is None or pd.isna(fastest["LapTime"]):
            continue
        rows.append({
            "driver_code": driver,
            "team_color": team_colors.get(driver),
            "lap_time": fastest["LapTime"],
        })

    if not rows:
        raise SessionDataUnavailable(
            f"No valid lap found for drivers {drivers} in {event} {year} {session_type}"
        )

    return {"event_name": session.event["EventName"], "drivers": rows}


def load_position_changes(year: int, event: str, session_type: str, drivers: list[str] | None) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    if drivers is not None:
        laps = laps[laps["Driver"].isin(drivers)]
        if laps.empty:
            raise SessionDataUnavailable(
                f"No lap data found for drivers {drivers} in {event} {year} {session_type}"
            )

    team_colors = {
        row["Abbreviation"]: row["TeamColor"]
        for row in session.results[["Abbreviation", "TeamColor"]].to_dict("records")
    }

    rows = [
        {
            "Driver": row["Driver"],
            "TeamColor": team_colors.get(row["Driver"]),
            "LapNumber": row["LapNumber"],
            "Position": row["Position"],
        }
        for row in laps[["Driver", "LapNumber", "Position"]].to_dict("records")
        if not pd.isna(row["Position"])
    ]

    return {"event_name": session.event["EventName"], "laps": rows}


def load_best_sectors(year: int, event: str, session_type: str) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} {session_type}"
        )

    team_colors = {
        row["Abbreviation"]: row["TeamColor"]
        for row in session.results[["Abbreviation", "TeamColor"]].to_dict("records")
    }

    sector_columns = ["Driver", "Sector1Time", "Sector2Time", "Sector3Time"]
    rows = [
        {
            "driver_code": row["Driver"],
            "team_color": team_colors.get(row["Driver"]),
            "sector_1": None if pd.isna(row["Sector1Time"]) else row["Sector1Time"],
            "sector_2": None if pd.isna(row["Sector2Time"]) else row["Sector2Time"],
            "sector_3": None if pd.isna(row["Sector3Time"]) else row["Sector3Time"],
        }
        for row in laps[sector_columns].to_dict("records")
    ]

    return {"event_name": session.event["EventName"], "laps": rows}


def load_qualifying_segments(year: int, event: str) -> dict:
    _ensure_cache_enabled()

    try:
        session = fastf1.get_session(year, event, "Qualifying")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if laps is None or laps.empty:
        raise SessionDataUnavailable(
            f"No lap data found for {event} {year} Qualifying"
        )

    team_colors = {
        row["Abbreviation"]: row["TeamColor"]
        for row in session.results[["Abbreviation", "TeamColor"]].to_dict("records")
    }
    driver_teams = {row["Driver"]: row["Team"] for row in laps[["Driver", "Team"]].to_dict("records")}
    team_color_by_team = {
        team: team_colors.get(driver)
        for driver, team in driver_teams.items()
        if team_colors.get(driver)
    }

    segments = laps.split_qualifying_sessions()
    best_by_team_segment: dict[str, list] = {}
    for index, segment_laps in enumerate(segments):
        if segment_laps is None or segment_laps.empty:
            continue
        for team, lap_time in segment_laps.groupby("Team")["LapTime"].min().items():
            if pd.isna(lap_time):
                continue
            best_by_team_segment.setdefault(team, [None, None, None])[index] = lap_time

    teams = [
        {
            "team": team,
            "team_color": team_color_by_team.get(team),
            "q1": times[0],
            "q2": times[1],
            "q3": times[2],
        }
        for team, times in best_by_team_segment.items()
    ]

    return {"event_name": session.event["EventName"], "teams": teams}


def load_driver_standings(year: int, event: str | None) -> list[dict]:
    _ensure_cache_enabled()

    round_number = None
    if event is not None:
        try:
            round_number = fastf1.get_event(year, event)["RoundNumber"]
        except Exception as exc:
            raise SessionDataUnavailable(str(exc)) from exc

    try:
        response = Ergast().get_driver_standings(season=year, round=round_number)
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if not response.content or response.content[0].empty:
        raise SessionDataUnavailable(f"No driver standings found for {year}")

    return response.content[0].to_dict("records")


def load_team_standings(year: int, event: str | None) -> list[dict]:
    _ensure_cache_enabled()

    round_number = None
    if event is not None:
        try:
            round_number = fastf1.get_event(year, event)["RoundNumber"]
        except Exception as exc:
            raise SessionDataUnavailable(str(exc)) from exc

    try:
        response = Ergast().get_constructor_standings(season=year, round=round_number)
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    if not response.content or response.content[0].empty:
        raise SessionDataUnavailable(f"No team standings found for {year}")

    return response.content[0].to_dict("records")
