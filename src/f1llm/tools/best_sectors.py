from dataclasses import dataclass
from datetime import date

from f1llm.charts import dark_layout
from f1llm.errors import SessionDataUnavailable

SUPPORTED_SESSION_TYPES = {"Race", "Qualifying", "Sprint"}
MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class DriverSectors:
    driver_code: str
    team_color: str | None
    sector_1: float | None
    sector_2: float | None
    sector_3: float | None


@dataclass(frozen=True)
class BestSectorsResponse:
    found: bool
    event_name: str | None = None
    drivers: list[DriverSectors] | None = None
    reason: str | None = None


def get_best_sectors(
    *,
    year: int,
    event: str,
    session_type: str,
    load_best_sectors=None,
):
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
        data = load_best_sectors(year, event, session_type)
    except SessionDataUnavailable as exc:
        return BestSectorsResponse(found=False, reason=str(exc))

    best_by_driver: dict[str, dict] = {}
    for row in data["laps"]:
        driver = row["driver_code"]
        best = best_by_driver.setdefault(
            driver, {"team_color": row["team_color"], "sector_1": None, "sector_2": None, "sector_3": None}
        )
        for sector in ("sector_1", "sector_2", "sector_3"):
            value = row[sector]
            if value is None:
                continue
            if best[sector] is None or value < best[sector]:
                best[sector] = value

    drivers = [
        DriverSectors(
            driver_code=driver,
            team_color=f"#{best['team_color']}" if best["team_color"] else None,
            sector_1=best["sector_1"].total_seconds() if best["sector_1"] is not None else None,
            sector_2=best["sector_2"].total_seconds() if best["sector_2"] is not None else None,
            sector_3=best["sector_3"].total_seconds() if best["sector_3"] is not None else None,
        )
        for driver, best in best_by_driver.items()
    ]

    return BestSectorsResponse(found=True, event_name=data["event_name"], drivers=drivers)


_TOP_N = 8
_SECTOR_AXES = [
    ("sector_1", "S1", "x", "y"),
    ("sector_2", "S2", "x2", "y2"),
    ("sector_3", "S3", "x3", "y3"),
]
_DOMAINS = [[0.0, 0.3], [0.35, 0.65], [0.7, 1.0]]


def build_best_sectors_chart(result: BestSectorsResponse, *, year: int, session_type: str) -> dict:
    data = []
    layout = {
        "title": f"{year} {result.event_name} - {session_type} - Melhores setores",
        "annotations": [],
    }

    for (attr, label, xaxis, yaxis), domain in zip(_SECTOR_AXES, _DOMAINS):
        timed = [driver for driver in result.drivers if getattr(driver, attr) is not None]
        fastest = sorted(timed, key=lambda driver: getattr(driver, attr))[:_TOP_N]

        data.append({
            "type": "bar",
            "orientation": "h",
            "xaxis": xaxis,
            "yaxis": yaxis,
            "x": [getattr(driver, attr) for driver in fastest],
            "y": [driver.driver_code for driver in fastest],
            "marker": {"color": [driver.team_color for driver in fastest]},
        })
        layout[f"xaxis{xaxis[1:]}"] = {"domain": domain, "title": f"{label} (s)", "showgrid": True}
        # Without an explicit anchor, a secondary y-axis (y2, y3) defaults to
        # anchoring on the primary x-axis instead of its own subplot, so all
        # three axes' tick labels stack on top of each other in the left
        # margin instead of each sitting under its own bars.
        layout[f"yaxis{yaxis[1:]}" if yaxis != "y" else "yaxis"] = {"autorange": "reversed", "anchor": xaxis}
        layout["annotations"].append({
            "text": label,
            "xref": f"{xaxis} domain", "yref": "paper",
            "x": 0.5, "y": 1.05,
            "showarrow": False,
        })

    return {"data": data, "layout": dark_layout(layout)}
