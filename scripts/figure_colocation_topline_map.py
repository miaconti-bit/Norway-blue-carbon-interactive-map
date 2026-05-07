"""Create a topline co-location figure for the Norway blue-carbon inventory.

The figure summarizes:
  - mapped HB19 eelgrass and kelp habitat footprints
  - habitat polygons with protection overlap
  - habitat polygons with pressure but low protection
  - study-site coverage / evidence gaps
  - regional protection percentages

Output:
  figures/colocation_topline_map.png
  figures/colocation_topline_map.svg

Run:
  MPLCONFIGDIR=/tmp/mplconfig /opt/anaconda3/envs/ella-capstone/bin/python scripts/figure_colocation_topline_map.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely.geometry import Point


REPO_ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = REPO_ROOT / "figures"

HB19_DIR = REPO_ROOT / "data" / "external" / "naturbase_hb19" / "map_layers"
EELGRASS_PATH = HB19_DIR / "naturbase_hb19_alegras_map.geojson"
KELP_PATH = HB19_DIR / "naturbase_hb19_tare_map.geojson"
METRICS_PATH = REPO_ROOT / "data" / "processed" / "spatial_analysis" / "habitat_colocation_metrics.csv"
REGIONAL_PATH = REPO_ROOT / "data" / "processed" / "spatial_analysis" / "regional_colocation_summary.csv"
MASTER_SITES_PATH = REPO_ROOT / "data" / "processed" / "norway_blue_carbon_master_sites.csv"

PNG_OUT = FIG_DIR / "colocation_topline_map.png"
SVG_OUT = FIG_DIR / "colocation_topline_map.svg"

CRS_WGS84 = "EPSG:4326"

REGION_LABEL_POS = {
    "Barents Sea": (23.0, 70.6),
    "Norwegian Sea": (8.8, 63.5),
    "Skagerrak": (13.3, 58.45),
}


def read_habitat(path: Path, ecosystem: str, habitat_type: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path).to_crs(CRS_WGS84).reset_index(drop=True)
    gdf["ecosystem"] = ecosystem
    gdf["habitat_type"] = habitat_type
    gdf["habitat_id"] = [
        f"{ecosystem}_{habitat_type}_{i}_{str(row.get('marinNaturtypeId', 'na'))}"
        for i, row in gdf.iterrows()
    ]
    return gdf


def read_study_sites() -> gpd.GeoDataFrame:
    df = pd.read_csv(MASTER_SITES_PATH)
    df = df[
        (df["inventory_record_type"] == "true_point_site")
        & df["latitude"].notna()
        & df["longitude"].notna()
    ].copy()
    geometry = [Point(float(lon), float(lat)) for lon, lat in zip(df["longitude"], df["latitude"])]
    return gpd.GeoDataFrame(df, geometry=geometry, crs=CRS_WGS84)


def classify(row: pd.Series) -> str:
    protected = row.get("percent_protected", 0) >= 10
    pressure = row.get("colocation_pressure_index", 0) > 0
    low_protection = row.get("percent_protected", 0) < 1
    studied = row.get("study_sites_within_5km_n", 0) > 0
    if pressure and low_protection:
        return "pressure_low_protection"
    if pressure and protected:
        return "pressure_and_protected"
    if protected:
        return "protected"
    if studied:
        return "study_covered"
    return "mapped_gap"


def region_summary_text(regional: pd.DataFrame, region: str) -> str:
    sub = regional[regional["canonical_region"] == region]
    if sub.empty:
        return region
    lines = [region]
    for ecosystem in ["seagrass", "macroalgae"]:
        row = sub[sub["ecosystem"] == ecosystem]
        if row.empty:
            continue
        row = row.iloc[0]
        label = "eelgrass" if ecosystem == "seagrass" else "kelp"
        lines.append(
            f"{label}: {row['habitat_area_km2']:.0f} km², "
            f"{row['percent_habitat_protected']:.0f}% protected"
        )
    return "\n".join(lines)


def add_summary_panel(fig, regional: pd.DataFrame, metrics: pd.DataFrame) -> None:
    ax = fig.add_axes([0.70, 0.12, 0.26, 0.75])
    ax.axis("off")

    total_area = metrics.groupby("ecosystem")["habitat_area_m2"].sum() / 1_000_000
    protected = metrics.groupby("ecosystem")["protected_area_m2"].sum()
    area = metrics.groupby("ecosystem")["habitat_area_m2"].sum()
    protected_pct = protected / area * 100
    pressure_gap = metrics[metrics["high_pressure_low_protection_flag"]].groupby("ecosystem").size()
    evidence_gap = metrics[metrics["evidence_gap_flag"]].groupby("ecosystem").size()
    total_n = metrics.groupby("ecosystem").size()

    y = 0.98
    ax.text(0, y, "Topline co-location results", fontsize=15, fontweight="bold", va="top")
    y -= 0.08
    for ecosystem, label in [("seagrass", "Eelgrass"), ("macroalgae", "Kelp forests")]:
        ax.text(0, y, label, fontsize=11.5, fontweight="bold", va="top")
        y -= 0.045
        ax.text(
            0.02,
            y,
            f"{total_area.get(ecosystem, 0):,.0f} km² mapped habitat",
            fontsize=10,
            color="#333",
            va="top",
        )
        y -= 0.04
        ax.text(
            0.02,
            y,
            f"{protected_pct.get(ecosystem, 0):.0f}% overlaps protected areas",
            fontsize=10,
            color="#1f78b4",
            va="top",
        )
        y -= 0.04
        ax.text(
            0.02,
            y,
            f"{int(pressure_gap.get(ecosystem, 0)):,} polygons have pressure + <1% protection",
            fontsize=10,
            color="#b2182b",
            va="top",
        )
        y -= 0.04
        ax.text(
            0.02,
            y,
            f"{evidence_gap.get(ecosystem, 0) / total_n.get(ecosystem, 1) * 100:.0f}% lack study sites within 5 km",
            fontsize=10,
            color="#666",
            va="top",
        )
        y -= 0.075

    ax.text(0, y, "Regional signal", fontsize=11.5, fontweight="bold", va="top")
    y -= 0.05
    skag = regional[
        (regional["ecosystem"] == "macroalgae") & (regional["canonical_region"] == "Skagerrak")
    ]
    if not skag.empty:
        ax.text(
            0.02,
            y,
            f"Skagerrak kelp has the highest protection overlap "
            f"({skag.iloc[0]['percent_habitat_protected']:.0f}%).",
            fontsize=10,
            color="#333",
            va="top",
            wrap=True,
        )
        y -= 0.08
    sea_skag = regional[
        (regional["ecosystem"] == "seagrass") & (regional["canonical_region"] == "Skagerrak")
    ]
    if not sea_skag.empty:
        ax.text(
            0.02,
            y,
            f"Most mapped eelgrass polygons are in Skagerrak "
            f"({int(sea_skag.iloc[0]['habitat_polygons_n']):,} polygons), "
            f"but MPA overlap is only {sea_skag.iloc[0]['percent_habitat_in_mpa']:.1f}%.",
            fontsize=10,
            color="#333",
            va="top",
            wrap=True,
        )
        y -= 0.10

    ax.text(
        0,
        0.02,
        "Pressure score is a transparent screening index\n"
        "from dredging, aquaculture, platforms and windfarms.\n"
        "It is not an ecological impact model.",
        fontsize=8.5,
        color="#666",
        va="bottom",
    )


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    eelgrass = read_habitat(EELGRASS_PATH, "seagrass", "eelgrass")
    kelp = read_habitat(KELP_PATH, "macroalgae", "kelp_forest")
    habitat = pd.concat([eelgrass, kelp], ignore_index=True)
    habitat = gpd.GeoDataFrame(habitat, geometry="geometry", crs=CRS_WGS84)

    metrics = pd.read_csv(METRICS_PATH)
    regional = pd.read_csv(REGIONAL_PATH)
    habitat = habitat.merge(
        metrics[
            [
                "habitat_id",
                "percent_protected",
                "percent_mpa",
                "colocation_pressure_index",
                "study_sites_within_5km_n",
                "high_pressure_low_protection_flag",
                "evidence_gap_flag",
            ]
        ],
        on="habitat_id",
        how="left",
    )
    habitat["map_class"] = habitat.apply(classify, axis=1)
    study = read_study_sites()

    colors = {
        "mapped_gap": "#d9d9d9",
        "study_covered": "#9ecae1",
        "protected": "#2b8cbe",
        "pressure_and_protected": "#fdae61",
        "pressure_low_protection": "#b2182b",
    }

    fig = plt.figure(figsize=(14, 9), facecolor="#f7f8f5")
    ax = fig.add_axes([0.04, 0.08, 0.62, 0.84])
    ax.set_facecolor("#edf3f4")

    # Plot quiet base first, then overlays in visual priority order.
    habitat[habitat["map_class"] == "mapped_gap"].plot(
        ax=ax, color=colors["mapped_gap"], edgecolor="none", alpha=0.32
    )
    habitat[habitat["map_class"] == "study_covered"].plot(
        ax=ax, color=colors["study_covered"], edgecolor="none", alpha=0.50
    )
    habitat[habitat["map_class"] == "protected"].plot(
        ax=ax, color=colors["protected"], edgecolor="none", alpha=0.58
    )
    habitat[habitat["map_class"] == "pressure_and_protected"].plot(
        ax=ax, color=colors["pressure_and_protected"], edgecolor="none", alpha=0.75
    )
    habitat[habitat["map_class"] == "pressure_low_protection"].plot(
        ax=ax, color=colors["pressure_low_protection"], edgecolor="#7f0000", linewidth=0.12, alpha=0.78
    )

    # Study sites are the evidence layer.
    study_colors = {"seagrass": "#111111", "macroalgae": "#111111"}
    for ecosystem, marker in [("seagrass", "s"), ("macroalgae", "o")]:
        sub = study[study["ecosystem"] == ecosystem]
        if not sub.empty:
            sub.plot(
                ax=ax,
                marker=marker,
                color=study_colors[ecosystem],
                markersize=18,
                edgecolor="white",
                linewidth=0.35,
                alpha=0.95,
            )

    # Regional callouts.
    for region, (x, y) in REGION_LABEL_POS.items():
        ax.text(
            x,
            y,
            region_summary_text(regional, region),
            fontsize=8.8,
            color="#263238",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#9aa5a8", alpha=0.88),
        )

    ax.set_xlim(4.0, 31.2)
    ax.set_ylim(57.2, 71.5)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        "Norway Blue-Carbon Co-Location Map",
        loc="left",
        fontsize=18,
        fontweight="bold",
        pad=12,
    )
    ax.text(
        4.0,
        71.15,
        "Mapped eelgrass and kelp habitat classified by protection, pressure and evidence coverage",
        fontsize=10.5,
        color="#444",
        ha="left",
    )

    legend_handles = [
        Patch(facecolor=colors["pressure_low_protection"], label="Pressure nearby + <1% protected"),
        Patch(facecolor=colors["pressure_and_protected"], label="Pressure nearby + protected"),
        Patch(facecolor=colors["protected"], label="Protected habitat"),
        Patch(facecolor=colors["study_covered"], label="Study site within 5 km"),
        Patch(facecolor=colors["mapped_gap"], label="Mapped habitat / evidence gap"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#111", markeredgecolor="white", markersize=6, label="Macroalgae study site"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor="#111", markeredgecolor="white", markersize=6, label="Seagrass study site"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(0.01, 0.78),
        frameon=True,
        facecolor="white",
        edgecolor="#cccccc",
        fontsize=8.5,
        title="Map encoding",
        title_fontsize=9,
    )

    add_summary_panel(fig, regional, metrics)

    fig.text(
        0.04,
        0.025,
        "Sources: Naturbase HB19 habitat polygons; Miljødirektoratet protected areas; EMODnet; Fiskeridirektoratet; compiled literature study sites. "
        "Map is for screening and prioritization.",
        fontsize=8.5,
        color="#666",
    )

    fig.savefig(PNG_OUT, dpi=220, bbox_inches="tight")
    fig.savefig(SVG_OUT, bbox_inches="tight")
    print(f"Wrote {PNG_OUT}")
    print(f"Wrote {SVG_OUT}")


if __name__ == "__main__":
    main()
