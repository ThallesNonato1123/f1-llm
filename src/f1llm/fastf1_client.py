from pathlib import Path

import fastf1
import pandas as pd
from fastf1.ergast import Ergast

from f1llm.errors import SessionDataUnavailable

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".fastf1cache"
_cache_enabled = False


def _ensure_cache_enabled() -> None:
    global _cache_enabled
    if not _cache_enabled:
        _CACHE_DIR.mkdir(exist_ok=True)
        fastf1.Cache.enable_cache(str(_CACHE_DIR))
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
        }
        for row in laps[["Driver", "LapNumber", "LapTime"]].to_dict("records")
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
