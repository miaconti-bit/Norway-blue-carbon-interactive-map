"""HTML row / popup helpers used across layer-add functions.

`fmt_row` was previously defined inline in build_norway_map.py and called
roughly 80 times. Centralising it lets future popup tweaks (e.g. styling,
escaping) happen in one place.
"""

from __future__ import annotations

import pandas as pd


def fmt_row(label: str, val) -> str:
    """Render a single label/value row in a popup table.

    Returns an empty string when the value is missing or empty so callers
    can join rows unconditionally without producing blank rows.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
        return ""
    return (
        f"<tr><td style='padding-right:10px;color:#555;vertical-align:top'>{label}</td>"
        f"<td>{val}</td></tr>"
    )


def popup_html(title: str, rows: list[str], max_width: int = 340) -> str:
    """Wrap a sequence of fmt_row() outputs in the standard popup chrome."""
    body = "".join(r for r in rows if r)
    return (
        f"<div style='font-family:system-ui,sans-serif;font-size:12.5px;max-width:{max_width}px'>"
        f"<div style='font-weight:600;font-size:13.5px;margin-bottom:4px'>{title}</div>"
        f"<table style='border-collapse:collapse'>{body}</table></div>"
    )
