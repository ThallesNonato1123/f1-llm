BACKGROUND_COLOR = "#111111"
TEXT_COLOR = "#E6E6E6"
GRID_COLOR = "#333333"
ZERO_LINE_COLOR = "#666666"


def dark_layout(layout: dict) -> dict:
    """Return `layout` with the app-wide dark theme applied to the figure and every axis."""
    themed = {
        "paper_bgcolor": BACKGROUND_COLOR,
        "plot_bgcolor": BACKGROUND_COLOR,
        "font": {"color": TEXT_COLOR},
        **layout,
    }
    for key, axis in layout.items():
        if key.startswith(("xaxis", "yaxis")):
            themed[key] = {"gridcolor": GRID_COLOR, "zerolinecolor": ZERO_LINE_COLOR, **axis}
    return themed
