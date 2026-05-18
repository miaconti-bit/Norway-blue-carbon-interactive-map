"""
Seagrass carbon stocks — two-panel figure.

Panel A: Site-level sediment carbon stocks across Norwegian eelgrass sites,
         showing each site's mean (circle) and individual core measurements
         (smaller dots), grouped and coloured by region.

Panel B: Eelgrass vs unvegetated sediment carbon comparison using per-core
         Gagnon 2024 data, demonstrating that eelgrass sediments consistently
         store more carbon than adjacent bare sediments.

Inputs:
  data/Norway_Seagrass_ Master_Database (4).xlsx  — "Site level"
  data/Gagnon 2024 s1 carbon.xlsx                 — "Data-cores"

Output:
  figures/figure_site_carbon.png / .pdf
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "Norway_Seagrass_ Master_Database (4).xlsx"
CARBON_PATH = ROOT / "data" / "carbon stocks norway paper data.xlsx"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)

REGION_COLOR = {
    "Barents Sea":   "#3b6e8f",
    "Norwegian Sea": "#5fa3a3",
    "Oslofjord":     "#c08457",
    "Skagerrak":     "#d97a4a",
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


def load_site_data() -> pd.DataFrame:
    df = pd.read_excel(DB_PATH, sheet_name="Site level", header=1)
    df = df[df["Site Name"].notna()].copy()
    df["carbon"] = pd.to_numeric(
        df["Sediment C stock (g/m2)"].astype(str)
        .str.replace("*", "", regex=False).str.strip(),
        errors="coerce",
    )
    df["region"] = df["Region"].apply(region_label)
    return df.dropna(subset=["carbon"]).reset_index(drop=True)


def load_comparison_data() -> pd.DataFrame:
    """Per-core seagrass vs unvegetated stocks from Gagnon 2024."""
    df = pd.read_excel(CARBON_PATH, sheet_name="Data-cores", header=0)
    treat_col = "Treatment (seagrass or control)"
    stock_col = " C. stock in 50 cm core (gC per m2)"
    if treat_col not in df.columns or stock_col not in df.columns:
        return pd.DataFrame()
    df = df[[treat_col, stock_col]].copy()
    df.columns = ["treatment", "carbon"]
    df["carbon"] = pd.to_numeric(df["carbon"], errors="coerce")
    df = df.dropna(subset=["carbon"])
    df["treatment"] = df["treatment"].str.strip().str.lower()
    df = df[df["treatment"].isin(["seagrass", "unvegetated"])].copy()
    df["label"] = df["treatment"].map({"seagrass": "Eelgrass", "unvegetated": "Unvegetated"})
    return df


def panel_a_site_stocks(ax, df: pd.DataFrame) -> None:
    """Strip-plot style: one column per site, cores as dots, mean as larger marker."""
    sites_in_order = []
    for region in REGION_ORDER:
        region_sites = (
            df[df["region"] == region]
            .groupby("Site Name")["carbon"]
            .mean()
            .sort_values(ascending=False)
            .index.tolist()
        )
        sites_in_order.extend(region_sites)

    x_pos = {site: i for i, site in enumerate(sites_in_order)}
    rng = np.random.default_rng(7)

    for _, row in df.iterrows():
        site = row["Site Name"]
        color = REGION_COLOR.get(row["region"], "#888")
        jitter = rng.uniform(-0.18, 0.18)
        ax.scatter(x_pos[site] + jitter, row["carbon"],
                   color=color, s=55, edgecolor="white", linewidth=0.5,
                   zorder=3, alpha=0.75)

    # Site means as larger filled circles
    site_means = df.groupby("Site Name")["carbon"].mean()
    for site, mean_val in site_means.items():
        region = df.loc[df["Site Name"] == site, "region"].iloc[0]
        color = REGION_COLOR.get(region, "#888")
        ax.scatter(x_pos[site], mean_val, color=color, s=160,
                   edgecolor="black", linewidth=1.2, zorder=5)

    # National pooled mean line
    pool_mean = df["carbon"].mean()
    ax.axhline(pool_mean, color="#333", linewidth=1.4, linestyle="--", zorder=4)
    ax.text(len(sites_in_order) - 0.3, pool_mean * 1.04,
            f"Pooled mean\n{pool_mean:,.0f} g C m⁻²",
            ha="right", fontsize=8, color="#333")

    # Region band labels below x-axis
    region_spans = {}
    for site, xi in x_pos.items():
        region = df.loc[df["Site Name"] == site, "region"].iloc[0]
        region_spans.setdefault(region, []).append(xi)

    for region, positions in region_spans.items():
        mid = np.mean(positions)
        ax.text(mid, -1250, region, ha="center", va="top", fontsize=8,
                color=REGION_COLOR[region], fontweight="bold")
        ax.plot([min(positions) - 0.4, max(positions) + 0.4],
                [-950, -950], color=REGION_COLOR[region], linewidth=2)

    # Site name labels (rotated)
    ax.set_xticks(list(x_pos.values()))
    ax.set_xticklabels(list(x_pos.keys()), rotation=35, ha="right", fontsize=8.5)
    ax.tick_params(axis="x", length=0)
    ax.set_xlim(-0.7, len(sites_in_order) - 0.3)
    ax.set_ylim(-1700, df["carbon"].max() * 1.15)
    ax.set_ylabel("Sediment carbon stock (g C m⁻²)", fontsize=9.5)
    ax.set_title("A.  Site-level Sediment Carbon Stocks", loc="left",
                 fontweight="bold", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))

    # Legend: small = core, large = site mean
    handles = [
        plt.scatter([], [], s=55, color="#aaa", edgecolor="white", label="Individual core"),
        plt.scatter([], [], s=160, color="#aaa", edgecolor="black", linewidth=1.2,
                    label="Site mean"),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=8, loc="upper right")


def panel_b_comparison(ax, df: pd.DataFrame) -> None:
    """Box plot comparing eelgrass vs unvegetated per-core carbon stocks."""
    if df.empty:
        ax.text(0.5, 0.5, "Data not found", ha="center", va="center",
                transform=ax.transAxes)
        return

    groups = ["Eelgrass", "Unvegetated"]
    colors = ["#7fbf7b", "#bdbdbd"]
    data_by_group = [df.loc[df["label"] == g, "carbon"].values for g in groups]

    bp = ax.boxplot(
        data_by_group,
        patch_artist=True,
        widths=0.5,
        medianprops=dict(color="black", linewidth=2),
        whiskerprops=dict(linewidth=1.2),
        capprops=dict(linewidth=1.2),
        flierprops=dict(marker="o", markersize=4, markerfacecolor="#888",
                        markeredgecolor="none", alpha=0.7),
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.85)
        patch.set_edgecolor("black")
        patch.set_linewidth(1.2)

    # Overlay jittered points
    rng = np.random.default_rng(12)
    for i, (group, data) in enumerate(zip(groups, data_by_group), start=1):
        jitter = rng.uniform(-0.15, 0.15, len(data))
        ax.scatter(i + jitter, data, color=colors[i - 1], s=40,
                   edgecolor="black", linewidth=0.5, zorder=4, alpha=0.8)

    # Means + annotations
    for i, data in enumerate(data_by_group, start=1):
        mean_val = np.mean(data)
        ax.scatter(i, mean_val, color="white", s=90, edgecolor="black",
                   linewidth=1.4, zorder=6, marker="D")
        # Eelgrass (i=1) label on left; Unvegetated (i=2) on right
        if i == 1:
            ax.text(i - 0.35, mean_val, f"mean\n{mean_val:,.0f}",
                    va="center", ha="right", fontsize=8)
        else:
            ax.text(i + 0.32, mean_val, f"mean\n{mean_val:,.0f}",
                    va="center", ha="left", fontsize=8)

    y_max = max(df["carbon"])

    # Difference annotation — show % uplift rather than a stat bracket
    mean_sg  = np.mean(data_by_group[0])
    mean_uv  = np.mean(data_by_group[1])
    pct_more = (mean_sg - mean_uv) / mean_uv * 100
    ax.annotate(
        f"+{pct_more:.0f}% higher\nmean stock",
        xy=(1.5, (mean_sg + mean_uv) / 2),
        xytext=(2.55, (mean_sg + mean_uv) / 2),
        ha="left", va="center", fontsize=9, color="#333",
        arrowprops=dict(arrowstyle="-[,widthB=2.5,lengthB=0.4",
                        color="#888", lw=1.0),
    )

    n_labels = [f"n = {len(d)} cores" for d in data_by_group]
    for i, lbl in enumerate(n_labels, start=1):
        ax.text(i, -650, lbl, ha="center", va="top", fontsize=8, color="#555")

    ax.set_xticks([1, 2])
    ax.set_xticklabels(groups, fontsize=11)
    ax.set_xlim(0.4, 3.1)
    ax.set_ylim(-950, y_max * 1.18)
    ax.set_ylabel("Sediment carbon stock (g C m⁻²)", fontsize=9.5)
    ax.set_title("B.  Eelgrass vs. Unvegetated Sediments", loc="left",
                 fontweight="bold", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))

    # Explicit legend to avoid duplication from boxplot patch_artist
    leg_handles = [
        mpatches.Patch(facecolor=colors[0], edgecolor="black", linewidth=1.2,
                       label="Eelgrass"),
        mpatches.Patch(facecolor=colors[1], edgecolor="black", linewidth=1.2,
                       label="Unvegetated"),
        plt.scatter([], [], color="white", s=90, edgecolor="black", linewidth=1.4,
                    marker="D", label="Group mean"),
    ]
    ax.legend(handles=leg_handles, frameon=False, fontsize=8, loc="upper right")


def render(site_df: pd.DataFrame, comp_df: pd.DataFrame) -> Path:
    fig = plt.figure(figsize=(14, 7))
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1.6, 1.0],
                  wspace=0.32, left=0.07, right=0.97, top=0.88, bottom=0.23)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])

    panel_a_site_stocks(ax_a, site_df)
    panel_b_comparison(ax_b, comp_df)

    fig.suptitle("Norwegian Eelgrass Sediment Carbon Stocks",
                 fontsize=14, fontweight="bold", y=0.98)
    fig.text(0.5, 0.02,
             "Panel A: 9 eelgrass sites (Gagnon et al. 2024; Rohr et al. 2018). "
             "Large markers = site means; small markers = individual cores. "
             "Panel B: per-core seagrass vs. unvegetated comparison (Gagnon 2024); ◆ = group mean.",
             fontsize=7.5, color="#666", ha="center", style="italic")

    out_png = FIG_DIR / "figure_site_carbon.png"
    out_pdf = FIG_DIR / "figure_site_carbon.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)
    return out_png


def main() -> None:
    site_df = load_site_data()
    comp_df = load_comparison_data()
    print(f"Site data: {len(site_df)} cores, {site_df['Site Name'].nunique()} sites")
    print(f"Comparison data: {len(comp_df)} cores ({comp_df['label'].value_counts().to_dict()})")
    out = render(site_df, comp_df)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
