from dataclasses import dataclass
from datetime import date

from f1llm.errors import SessionDataUnavailable

SUPPORTED_SESSION_TYPES = {"Race", "Qualifying", "Sprint"}
MIN_SUPPORTED_YEAR = 2018


@dataclass(frozen=True)
class TelemetrySample:
    driver_code: str
    lap_number: int
    distance: float
    speed: float
    throttle: float
    brake: bool
    gear: int


@dataclass(frozen=True)
class TelemetryResponse:
    found: bool
    samples: list[TelemetrySample] | None = None
    reason: str | None = None


def get_telemetry_comparison(
    *,
    year: int,
    event: str,
    session_type: str,
    drivers: list[str],
    laps: dict[str, int] | None = None,
    load_telemetry=None,
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

    if not drivers:
        raise ValueError("drivers must contain at least one driver code")

    try:
        raw_rows = load_telemetry(year, event, session_type, drivers, laps)
    except SessionDataUnavailable as exc:
        return TelemetryResponse(found=False, reason=str(exc))

    samples = [
        TelemetrySample(
            driver_code=row["Driver"],
            lap_number=int(row["LapNumber"]),
            distance=row["Distance"],
            speed=row["Speed"],
            throttle=row["Throttle"],
            brake=row["Brake"],
            gear=int(row["nGear"]),
        )
        for row in raw_rows
    ]
    return TelemetryResponse(found=True, samples=samples)


_CHANNELS = [
    ("speed", "y", "Velocidade (km/h)", [0.78, 1.0]),
    ("throttle", "y2", "Throttle (%)", [0.53, 0.73]),
    ("brake", "y3", "Freio", [0.28, 0.48]),
    ("gear", "y4", "Marcha", [0.0, 0.2]),
]


def build_telemetry_chart(samples: list[TelemetrySample]) -> dict:
    samples_by_driver: dict[str, list[TelemetrySample]] = {}
    for sample in samples:
        samples_by_driver.setdefault(sample.driver_code, []).append(sample)

    data = []
    for driver_code, driver_samples in samples_by_driver.items():
        distances = [sample.distance for sample in driver_samples]
        for attr, yaxis, _title, _domain in _CHANNELS:
            data.append(
                {
                    "type": "scatter",
                    "mode": "lines",
                    "name": driver_code,
                    "x": distances,
                    "y": [getattr(sample, attr) for sample in driver_samples],
                    "xaxis": "x",
                    "yaxis": yaxis,
                }
            )

    layout = {"xaxis": {"title": "Distância (m)", "showgrid": True}}
    for _attr, yaxis, title, domain in _CHANNELS:
        layout_key = "yaxis" if yaxis == "y" else f"yaxis{yaxis[1:]}"
        layout[layout_key] = {"title": title, "domain": domain, "showgrid": True}

    return {"data": data, "layout": layout}
