"""Shared styling for the Norway manuscript figures.

Two jobs, applied consistently across every figure_*.py:

  use_min_font()  - floor every default font role at >=9 pt so nothing
                    renders smaller than the journal minimum.
  add_caption()   - render the explanatory footnote as a proper figure
                    caption: dark, >=9 pt, wrapped so the text block never
                    exceeds the width of the figure itself.

Explicit per-element font sizes are bumped to >=9 in each script; this
module is the safety net for everything left at matplotlib defaults.
"""

from __future__ import annotations

import textwrap

import matplotlib as mpl

MIN_FONT_PT = 9
CAPTION_COLOR = "#222222"  # near-black: high contrast, reads as dark grey


def use_min_font(min_pt: int = MIN_FONT_PT) -> None:
    """Raise any default font role below ``min_pt`` up to it."""
    roles = ("font.size", "axes.titlesize", "axes.labelsize",
             "xtick.labelsize", "ytick.labelsize", "legend.fontsize",
             "legend.title_fontsize", "figure.titlesize")
    for key in roles:
        val = mpl.rcParams.get(key)
        if isinstance(val, (int, float)) and val < min_pt:
            mpl.rcParams[key] = min_pt


def add_caption(fig, text, *, x=0.5, y=0.012, ha="center",
                fontsize=MIN_FONT_PT, color=CAPTION_COLOR,
                width_frac=0.96, box=None):
    """Place ``text`` as a figure caption that never exceeds the figure width.

    The text is wrapped to as many lines as needed so its rendered block fits
    within the available horizontal span (set by ``ha``/``x`` and capped by
    ``width_frac``). Returns the Text artist.
    """
    fontsize = max(fontsize, MIN_FONT_PT)

    if ha == "left":
        avail = 0.98 - x
    elif ha == "right":
        avail = x - 0.02
    else:  # center
        avail = 2 * min(x, 1 - x) - 0.04
    avail = max(0.2, min(avail, width_frac))

    fig.canvas.draw()  # realise a renderer for width measurement
    renderer = fig.canvas.get_renderer()
    max_w_px = fig.get_figwidth() * fig.dpi * avail

    t = fig.text(x, y, text, fontsize=fontsize, color=color, ha=ha,
                 va="bottom", bbox=box)

    wrap = len(text)
    while True:
        t.set_text(textwrap.fill(text, width=wrap))
        if t.get_window_extent(renderer).width <= max_w_px or wrap <= 12:
            break
        wrap -= 4
    return t
