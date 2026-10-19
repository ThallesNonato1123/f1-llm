import math
from dataclasses import dataclass
from datetime import date

import numpy as np
from scipy.spatial import ConvexHull, QhullError

from f1llm.charts import BACKGROUND_COLOR, dark_layout
from f1llm.errors import SessionDataUnavailable
from f1llm.tools.telemetry import DRIVER_COLORS

SUPPORTED_SESSION_TYPES = {"Race", "Qualifying", "Sprint"}
MIN_SUPPORTED_YEAR = 2018

# ADR 0007: FastF1 doesn't expose acceleration directly, so it's derived from
# speed/position telemetry using a proven smooth-differentiation method,
# instead of plain finite differences (noisier) or something untested.
G = 9.81
OUTLIER_THRESHOLD_G = 7.5


@dataclass(frozen=True)
class AccelerationPoint:
    lateral: float
    longitudinal: float


@dataclass(frozen=True)
class DriverAcceleration:
    driver_code: str
    compound: str
    points: list[AccelerationPoint]
    average_combined_g: float


@dataclass(frozen=True)
class GGDiagramResponse:
    found: bool
    event_name: str | None = None
    drivers: list[DriverAcceleration] | None = None
    reason: str | None = None


def get_gg_diagram(
    *,
    year: int,
    event: str,
    session_type: str,
    drivers: list[str],
    load_gg_diagram=None,
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
        data = load_gg_diagram(year, event, session_type, drivers)
    except SessionDataUnavailable as exc:
        return GGDiagramResponse(found=False, reason=str(exc))

    driver_accelerations = []
    for entry in data["drivers"]:
        rows = entry["telemetry"]
        t = np.array([row["Time"].total_seconds() for row in rows])
        speed_ms = np.array([row["Speed"] for row in rows]) / 3.6
        distance = np.array([row["Distance"] for row in rows])
        x = np.array([row["X"] for row in rows])
        y = np.array([row["Y"] for row in rows])

        lon_acc = _smooth_derivative(t, speed_ms) / G

        dx = _smooth_derivative(distance, x)
        dy = _smooth_derivative(distance, y)
        theta = _unwrap_heading(dx, dy)
        kappa = _smooth_derivative(distance, theta)
        lat_acc = speed_ms * speed_ms * kappa / G

        lon_acc = _clip_outliers(lon_acc)
        lat_acc = _clip_outliers(lat_acc)

        points = [
            AccelerationPoint(lateral=float(lat), longitudinal=float(lon))
            for lat, lon in zip(lat_acc, lon_acc)
        ]
        combined = np.sqrt(lat_acc**2 + lon_acc**2)

        driver_accelerations.append(
            DriverAcceleration(
                driver_code=entry["driver_code"],
                compound=entry["compound"],
                points=points,
                average_combined_g=float(combined.mean()),
            )
        )

    return GGDiagramResponse(found=True, event_name=data["event_name"], drivers=driver_accelerations)


def _smooth_derivative(t: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Holoborodko low-noise differentiator (7-point stencil).

    REF: http://holoborodko.com/pavel/numerical-methods/numerical-derivative/smooth-low-noise-differentiators/
    """
    n = t.size
    dvdt = np.zeros(n)

    dvdt[0] = (v[1] - v[0]) / (t[1] - t[0])
    dvdt[1] = (v[2] - v[0]) / (t[2] - t[0])
    dvdt[2] = (v[3] - v[1]) / (t[3] - t[1])

    dvdt[n - 1] = (v[n - 1] - v[n - 2]) / (t[n - 1] - t[n - 2])
    dvdt[n - 2] = (v[n - 1] - v[n - 3]) / (t[n - 1] - t[n - 3])
    dvdt[n - 3] = (v[n - 2] - v[n - 4]) / (t[n - 2] - t[n - 4])

    stencil_weights = [5.0 / 32.0, 4.0 / 32.0, 1.0 / 32.0]
    for i in range(3, n - 3):
        for j in range(1, 4):
            span = t[i + j] - t[i - j]
            if span == 0:
                continue
            dvdt[i] += 2 * j * stencil_weights[j - 1] * (v[i + j] - v[i - j]) / span

    return dvdt


def _unwrap_heading(dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    """Continuous heading angle (no +-pi jumps) from direction vectors."""
    theta = np.zeros(dx.size)
    theta[0] = math.atan2(dy[0], dx[0])
    for i in range(dx.size):
        theta[i] = theta[i - 1] + _wrap_to_pipi(math.atan2(dy[i], dx[i]) - theta[i - 1])
    return theta


def _wrap_to_pipi(angle: float) -> float:
    pi = math.pi
    p1 = _truncated_remainder(angle + np.sign(angle) * pi, 2 * pi)
    p2 = (
        np.sign(np.sign(angle) + 2 * (np.sign(math.fabs(_truncated_remainder(angle + pi, 2 * pi) / (2 * pi))) - 1))
        * pi
    )
    return p1 - p2


def _truncated_remainder(dividend: float, divisor: float) -> float:
    divided = dividend / divisor
    divided = -int(-divided) if divided < 0 else int(divided)
    return dividend - divisor * divided


def _clip_outliers(values: np.ndarray) -> np.ndarray:
    """Replace physically-implausible samples (telemetry glitches) with the previous value."""
    values = values.copy()
    if abs(values[0]) > OUTLIER_THRESHOLD_G:
        values[0] = 0.0
    for i in range(1, values.size - 1):
        if abs(values[i]) > OUTLIER_THRESHOLD_G:
            values[i] = values[i - 1]
    if abs(values[-1]) > OUTLIER_THRESHOLD_G:
        values[-1] = values[-2]
    return values


def build_gg_diagram_chart(result: GGDiagramResponse, *, year: int, session_type: str) -> dict:
    data = []
    for index, driver in enumerate(result.drivers):
        color = DRIVER_COLORS[index % len(DRIVER_COLORS)]
        data.append({
            "type": "scatter",
            "mode": "markers",
            "name": driver.driver_code,
            "x": [point.lateral for point in driver.points],
            "y": [point.longitudinal for point in driver.points],
            "marker": {"color": color, "size": 4, "opacity": 0.5},
        })

        envelope = _convex_hull_envelope(driver.points)
        if envelope is not None:
            hull_x, hull_y = envelope
            data.append({
                "type": "scatter",
                "mode": "lines",
                "name": driver.driver_code,
                "x": hull_x,
                "y": hull_y,
                "line": {"color": color, "dash": "dash"},
                "showlegend": False,
            })

    all_values = [v for driver in result.drivers for point in driver.points for v in (point.lateral, point.longitudinal)]
    half_width = math.ceil(max((abs(v) for v in all_values), default=1.0))

    layout = dark_layout({
        "title": f"{year} {result.event_name} - {session_type} - Diagrama G-G",
        "xaxis": {"title": "Aceleração lateral (g)", "range": [-half_width, half_width]},
        "yaxis": {
            "title": "Aceleração longitudinal (g)",
            "range": [-half_width, half_width],
            "scaleanchor": "x",
            "scaleratio": 1,
        },
        "shapes": _g_circle_shapes(half_width),
        "annotations": [
            *[_average_accel_annotation(driver, index) for index, driver in enumerate(result.drivers)],
            {
                "text": "Curvas à Direita ← → Curvas à Esquerda",
                "xref": "paper", "yref": "paper", "x": 0.5, "y": 1.1,
                "showarrow": False,
            },
            {
                "text": "Frenagem / Tração",
                "xref": "paper", "yref": "paper", "x": -0.08, "y": 0.5,
                "showarrow": False, "textangle": -90,
            },
            {
                "text": "Pontos distantes do centro indicam alta aderência",
                "xref": "paper", "yref": "paper", "x": 0.5, "y": -0.12,
                "showarrow": False,
            },
        ],
    })

    return {"data": data, "layout": layout}


def _g_circle_shapes(half_width: int) -> list[dict]:
    return [
        {
            "type": "circle",
            "xref": "x", "yref": "y",
            "x0": -radius, "x1": radius, "y0": -radius, "y1": radius,
            "line": {"color": "#555555", "dash": "dot"},
        }
        for radius in range(1, half_width + 1)
    ]


def _average_accel_annotation(driver: DriverAcceleration, index: int) -> dict:
    compound_letter = driver.compound[0] if driver.compound else "?"
    text = f"{driver.driver_code} ({compound_letter}) Average Accel = {driver.average_combined_g:.2f}g"
    return {
        "text": text,
        "xref": "paper", "yref": "paper",
        "x": 0.02, "y": 1.02 + 0.05 * index,
        "showarrow": False,
        "xanchor": "left",
        "font": {"color": DRIVER_COLORS[index % len(DRIVER_COLORS)]},
    }


_MIN_POINTS_FOR_HULL = 3


def _convex_hull_envelope(points: list[AccelerationPoint]) -> tuple[list[float], list[float]] | None:
    if len(points) < _MIN_POINTS_FOR_HULL:
        return None

    coords = np.array([(point.lateral, point.longitudinal) for point in points])
    try:
        hull = ConvexHull(coords)
    except QhullError:
        # All points collinear or coincident: no 2D envelope to draw.
        return None
    vertices = coords[hull.vertices]
    # Close the loop by repeating the first vertex at the end.
    closed = np.vstack([vertices, vertices[0]])
    return closed[:, 0].tolist(), closed[:, 1].tolist()
