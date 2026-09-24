from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyCarPeriod:
    kind: str  # "safety_car" | "virtual_safety_car"
    start_lap: int
    end_lap: int


def safety_car_periods(laps: list[dict]) -> list[SafetyCarPeriod]:
    """Safety car / Virtual safety car periods, counted on the race leader's laps.

    Each lap row needs "Position", "LapNumber" and "TrackStatus" (FastF1 raw values).
    """
    leader_laps = sorted(
        (row for row in laps if row["Position"] == 1),
        key=lambda row: row["LapNumber"],
    )

    periods: list[SafetyCarPeriod] = []
    for row in leader_laps:
        kind = _neutralization_kind(row["TrackStatus"] or "")
        if kind is None:
            continue
        lap_number = int(row["LapNumber"])
        previous = periods[-1] if periods else None
        if previous and previous.kind == kind and previous.end_lap == lap_number - 1:
            periods[-1] = SafetyCarPeriod(kind=kind, start_lap=previous.start_lap, end_lap=lap_number)
        else:
            periods.append(SafetyCarPeriod(kind=kind, start_lap=lap_number, end_lap=lap_number))
    return periods


def _neutralization_kind(track_status: str) -> str | None:
    # FastF1 track status codes: "4" = Safety car, "6"/"7" = Virtual safety car deployed/ending.
    if "4" in track_status:
        return "safety_car"
    if "6" in track_status or "7" in track_status:
        return "virtual_safety_car"
    return None


# Translucent so the chart marks stay readable underneath; neither hue collides
# with a compound color.
SAFETY_CAR_BAND_COLORS = {
    "safety_car": "rgba(255, 135, 0, 0.35)",
    "virtual_safety_car": "rgba(170, 120, 255, 0.35)",
}
_SAFETY_CAR_LEGEND_NAMES = {"safety_car": "SC", "virtual_safety_car": "VSC"}


def safety_car_band_shapes(periods: list[SafetyCarPeriod]) -> list[dict]:
    """Plotly layout shapes shading each period; lap N spans the axis interval [N-1, N]."""
    return [
        {
            "type": "rect",
            "xref": "x",
            "yref": "paper",
            "x0": period.start_lap - 1,
            "x1": period.end_lap,
            "y0": 0,
            "y1": 1,
            "fillcolor": SAFETY_CAR_BAND_COLORS[period.kind],
            "line": {"width": 0},
            "layer": "above",
        }
        for period in periods
    ]


def safety_car_legend_entries(periods: list[SafetyCarPeriod]) -> list[dict]:
    """Legend-only traces, one per band kind present in `periods`."""
    return [
        legend_entry(_SAFETY_CAR_LEGEND_NAMES[kind], {"color": SAFETY_CAR_BAND_COLORS[kind]})
        for kind in _SAFETY_CAR_LEGEND_NAMES
        if any(period.kind == kind for period in periods)
    ]


def legend_entry(name: str, marker: dict) -> dict:
    """An empty bar trace that only draws a swatch in the legend."""
    return {
        "type": "bar",
        "orientation": "h",
        "name": name,
        "showlegend": True,
        "x": [None],
        "y": [None],
        "marker": marker,
    }
