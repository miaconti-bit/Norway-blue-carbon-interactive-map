"""
Environmental drivers of seagrass carbon storage — 4-panel scatter figure.

Key finding: dry bulk density (DBD) is the dominant predictor of sediment
carbon stock across Norwegian eelgrass sites (R² ≈ 0.92, p < 0.001).
Fine-grained, low-density sediments accumulate and retain far more carbon
than coarser, high-density sediments.

Panels:
  A  Carbon stock vs Dry Bulk Density  (per sediment core; N = 20)
  B  Carbon stock vs Aboveground Biomass  (site means; N = 9)
  C  Carbon stock vs Water Depth  (per sediment core; N = 20)
  D  Carbon stock vs Mean Temperature  (site means; N = 9)

DBD panel uses per-core data because DBD varies between cores from the same
site, capturing within-site sediment heterogeneity. Biomass and temperature
are site-level properties, so those panels use one mean per site.

Input:
  data/Norway_Seagrass_ Master_Database (4).xlsx  — "Site level" sheet

Output:
  figures/figure_environmental_drivers.png / .pdf
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "Norway_Seagrass_ Master_Database (4).xlsx"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)

REGION_COLOR = {
    "Barents Sea":    "#3b6e8f",
    "Norwegian Sea":  "#5fa3a3",
    "Oslofjord":      "#c08457",
    "Skagerrak":      "#d97a4a",
}
REGION_ORDER = ["Barents Sea", "Norwegian Sea", "Oslofjord", "Skagerrak"]


def region_label(raw: str) -> str:
    r = str(raw).lower()
    if "barents" in r or "north" in r:
        return "Barents Sea"
    if "norwegian" in r or "west" in r:
        return "Norwegian Sea"
    if "oslofjord" in r or "south east" in r:
        return "Oslofjord"
    if "skagerrak" in r or "south west" in r:
        return "Skagerrak"
    return "Unknown"


def load_data() -> pd.DataFrame:
    df = pd.read_excel(DB_PATH, sheet_name="Site level", header=1)
    df = df[df["Site Name"].notna() & (df["Site Name"] != "NaN")].copy()

    df["carbon_g_m2"] = pd.to_numeric(
        df["Sediment C stock (g/m2)"].astype(str).str.replace("*", "", regex=False).str.strip(),
        errors="coerce",
    )
    df["dbd"] = pd.to_numeric(df["Dry bulk density (g/cm3)"], errors="coerce")
    df["depth_m"] = pd.to_numeric(df["Water depth (m)"], errors="coerce")
    df["temp_c"] = pd.to_numeric(df["Temperature mean C"], errors="coerce")
    df["ag_biomass"] = pd.to_numeric(df["Aboveground biomass g m2"], errors="coerce")
    df["region"] = df["Region"].apply(region_label)

    return df.dropna(subset=["carbon_g_m2"]).reset_index(drop=True)


def site_means(df: pd.DataFrame, driver: str) -> pd.DataFrame:
    """One row per site, averaging carbon and the named driver."""
    return (
        df.dropna(subset=[driver])
        .groupby("Site Name", as_index=False)
        .agg(carbon_g_m2=("carbon_g_m2", "mean"),
             driver_val=(driver, "mean"),
             region=("region", "first"))
    )


def annotate_regression(ax, x, y, *, color="#c0392b",
                        stats_x=0.97, stats_y=0.97, stats_ha="right", stats_va="top"):
    """Fit OLS, draw regression line, annotate R²/p as a text box."""
    mask = np.isfinite(x) & np.isfinite(y)
    x_, y_ = x[mask], y[mask]
    if len(x_) < 3:
        return
    slope, intercept, r, p, _ = stats.linregress(x_, y_)
    x_line = np.linspace(x_.min(), x_.max(), 200)
    ax.plot(x_line, slope * x_line + intercept, color=color, linewidth=1.8,
            linestyle="--", zorder=5)
    p_str = "<0.001" if p < 0.001 else f"= {p:.3f}"
    ax.text(stats_x, stats_y,
            f"R² = {r**2:.2f}\np {p_str}",
            transform=ax.transAxes, ha=stats_ha, va=stats_va,
            fontsize=9, color=color, fontweight="bold",
            bbox=dict(facecolor="white", edgecolor="#ddd",
                      boxstyle="round,pad=0.3", linewidth=0.6))


def scatter_panel(ax, x, y, regions, *, xlabel, title_letter, title_text,
                  note=None, jitter=False,
                  stats_x=0.97, stats_y=0.97, stats_ha="right", stats_va="top"):
    """Shared scatter style for all four panels."""
    rng = np.random.default_rng(42)
    for region in REGION_ORDER:
        mask = np.array(regions) == region
        xi = x[mask] + (rng.uniform(-0.005, 0.005, mask.sum()) if jitter else 0)
        ax.scatter(xi, y[mask], color=REGION_COLOR[region],
                   s=90, edgecolor="black", linewidth=0.7, zorder=4,
                   alpha=0.9)

    annotate_regression(ax, x, y,
                        stats_x=stats_x, stats_y=stats_y,
                        stats_ha=stats_ha, stats_va=stats_va)

    ax.set_xlabel(xlabel, fontsize=9.5)
    ax.set_ylabel("Sediment carbon stock (g C m⁻²)", fontsize=9.5)
    ax.set_title(f"{title_letter}.  {title_text}", loc="left",
                 fontweight="bold", fontsize=11)
    if note:
        # Place N count below the x-axis label to avoid overlapping data points
        ax.text(0.5, -0.22, note, transform=ax.transAxes,
                fontsize=7.5, color="#666", style="italic",
                ha="center", va="top")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))


def render(df: pd.DataFrame) -> Path:
    fig = plt.figure(figsize=(13, 10))
    gs = GridSpec(2, 2, figure=fig, hspace=0.62, wspace=0.35,
                  left=0.09, right=0.97, top=0.88, bottom=0.14)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    # Panel A: DBD vs carbon — per core (R² stays top right)
    core_data = df.dropna(subset=["dbd", "carbon_g_m2"])
    scatter_panel(ax_a,
                  core_data["dbd"].values,
                  core_data["carbon_g_m2"].values,
                  core_data["region"].values,
                  xlabel="Dry bulk density (g cm⁻³)",
                  title_letter="A",
                  title_text="Dry Bulk Density",
                  note=f"Per sediment core, N = {len(core_data)}")

    # Panel B: Aboveground biomass vs carbon — site means (R² bottom right)
    bm = site_means(df, "ag_biomass")
    scatter_panel(ax_b,
                  bm["driver_val"].values,
                  bm["carbon_g_m2"].values,
                  bm["region"].values,
                  xlabel="Aboveground biomass (g m⁻²)",
                  title_letter="B",
                  title_text="Aboveground Biomass",
                  note=f"Site means, N = {len(bm)}",
                  stats_x=0.97, stats_y=0.05, stats_ha="right", stats_va="bottom")

    # Panel C: Water depth vs carbon — per core (R² stays top right)
    dep = df.dropna(subset=["depth_m", "carbon_g_m2"])
    scatter_panel(ax_c,
                  dep["depth_m"].values,
                  dep["carbon_g_m2"].values,
                  dep["region"].values,
                  xlabel="Water depth (m)",
                  title_letter="C",
                  title_text="Water Depth",
                  note=f"Per sediment core, N = {len(dep)}")

    # Panel D: Temperature vs carbon — site means (R² top left)
    tm = site_means(df, "temp_c")
    scatter_panel(ax_d,
                  tm["driver_val"].values,
                  tm["carbon_g_m2"].values,
                  tm["region"].values,
                  xlabel="Mean water temperature (°C)",
                  title_letter="D",
                  title_text="Mean Temperature",
                  note=f"Site means, N = {len(tm)}",
                  stats_x=0.03, stats_y=0.97, stats_ha="left", stats_va="top")

    # Shared legend (region colors)
    handles = [
        plt.scatter([], [], color=REGION_COLOR[r], s=80, edgecolor="black",
                    linewidth=0.6, label=r)
        for r in REGION_ORDER
    ]
    fig.legend(handles=handles, loc="upper center",
               bbox_to_anchor=(0.54, 0.965), ncol=4, frameon=False,
               fontsize=9, title="Region", title_fontsize=9)

    fig.suptitle("Environmental Drivers of Eelgrass Carbon Storage in Norway",
                 fontsize=14, fontweight="bold", y=0.998)
    fig.text(0.09, 0.022,
             "Data: Gagnon et al. (2024); Rohr et al. (2018) [Røvik]. "
             "Panels A and C use per-core data; panels B and D use site means. "
             "Dashed line = OLS regression; R² and p-value shown per panel.",
             fontsize=7.5, color="#666", ha="left", style="italic")

    out_png = FIG_DIR / "figure_environmental_drivers.png"
    out_pdf = FIG_DIR / "figure_environmental_drivers.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)
    return out_png


def main() -> None:
    df = load_data()
    print(f"Loaded {len(df)} core rows, {df['Site Name'].nunique()} unique sites")
    out = render(df)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
