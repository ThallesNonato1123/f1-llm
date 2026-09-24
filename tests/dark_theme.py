def relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance of a #RRGGBB color (0 = black, 1 = white)."""
    channels = [int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def assert_dark_theme(layout: dict) -> None:
    assert relative_luminance(layout["paper_bgcolor"]) < 0.02
    assert relative_luminance(layout["plot_bgcolor"]) < 0.02
    assert relative_luminance(layout["font"]["color"]) > 0.6
    for axis_key in [key for key in layout if key.startswith(("xaxis", "yaxis"))]:
        grid = relative_luminance(layout[axis_key]["gridcolor"])
        assert 0.02 < grid < 0.2, f"{axis_key} grid should be visible but recessive"
