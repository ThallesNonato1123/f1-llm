from dataclasses import dataclass
from datetime import date

from f1llm.errors import SessionDataUnavailable

SUPPORTED_SESSION_TYPES = {"Race", "Qualifying", "Sprint"}
MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class DriverResult:
    position: int
    driver: str
    driver_code: str
    team: str
    time: str | None
    points: float


@dataclass(frozen=True)
class SessionResultsResponse:
    found: bool
    results: list[DriverResult] | None = None
    reason: str | None = None


def get_session_results(*, year: int, event: str, session_type: str, load_results=None):
    if session_type not in SUPPORTED_SESSION_TYPES:
        raise ValueError(
            f"Unsupported session_type {session_type!r}; "
            f"expected one of {sorted(SUPPORTED_SESSION_TYPES)}"
        )

    current_year = date.today().year
    if not (MIN_SUPPORTED_YEAR <= year <= current_year):
        raise ValueError(
            f"Unsupported year {year!r}; "
            f"expected between {MIN_SUPPORTED_YEAR} and {current_year}"
        )

    try:
        raw_rows = load_results(year, event, session_type)
    except SessionDataUnavailable as exc:
        return SessionResultsResponse(found=False, reason=str(exc))

    results = [
        DriverResult(
            position=int(row["Position"]),
            driver=row["FullName"],
            driver_code=row["Abbreviation"],
            team=row["TeamName"],
            time=str(row["Time"]) if row["Time"] is not None else None,
            points=row["Points"],
        )
        for row in raw_rows
    ]
    return SessionResultsResponse(found=True, results=results)
