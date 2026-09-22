from pathlib import Path

import fastf1
import pandas as pd

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
    except Exception as exc:
        raise SessionDataUnavailable(str(exc)) from exc

    laps = session.laps
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
