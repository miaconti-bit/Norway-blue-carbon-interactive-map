"""
Hero figure: integrated risk x stock x co-benefit priority quadrant for
Norwegian blue carbon (kelp + seagrass).

Layout:
  A   Regional carbon stock (GgC), kelp + seagrass stacked
  B   Regional pressure decomposition (z-scored components)
  C   Regional co-benefit fingerprint
  D   Priority quadrant scatter — INDIVIDUAL SITES, two stacked panels:
        x = composite risk score (z, within ecosystem)
        y = composite co-benefit score (z, within ecosystem)
        marker size = site carbon stock (seagrass only; kelp uniform)
        quadrant lines = within-habitat medians

Composite indices are equal-weight z-score means of named components, computed
within ecosystem (kelp / seagrass) so kelp is compared to kelp and seagrass to
seagrass. Components and weights are listed in the figure caption.

Inputs (already produced by upstream scripts):
  data/processed/spatial_analysis/regional_colocation_summary.csv
  data/processed/step2_seagrass_stocks_by_region.csv
  data/processed/step2_national_sequestration.csv
  data/processed/per_site_priority_metrics.csv  (from per_site_priority_metrics.py)

Outputs:
  figures/priority_quadrant_hero.png
  figures/priority_quadrant_hero.pdf
  data/processed/regional_priority_metrics.csv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
SPATIAL = PROC / "spatial_analysis"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

REGION_COLOR = {
    "Barents Sea": "#3b6e8f",
    "Norwegian Sea": "#5fa3a3",
    "Oslofjord": "#c08457",
    "Skagerrak": "#d97a4a",
    "Skagerrak (incl. Oslofjord)": "#d97a4a",
}

HABITAT_LABEL = {"macroalgae": "Kelp", "seagrass": "Seagrass"}


# ---------- Stocks per region per habitat ----------
def regional_stocks() -> pd.DataFrame:
    """Total carbon stock (GgC) per region per habitat.

    Seagrass: regional mean density (step2_seagrass_stocks_by_region) x
              regional habitat area (regional_colocation_summary). Oslofjord
              and Skagerrak sites are weighted-mean combined and applied to
              the Skagerrak habitat polygon.
    Kelp:     national mean stock density (from step2_national_sequestration,
              Tier 2 from Gundersen 2021) applied to each region's habitat
              area. Equal density is a known limitation flagged with hatching.
    """
    coloc = pd.read_csv(SPATIAL / "regional_colocation_summary.csv")
    sg_dens = pd.read_csv(PROC / "step2_seagrass_stocks_by_region.csv")
    nat = pd.read_csv(PROC / "step2_national_sequestration.csv")

    # Seagrass: combine Oslofjord + Skagerrak as weighted mean
    sg_dens = sg_dens.set_index("canonical_region")
    osl = sg_dens.loc["Oslofjord"]
    sk = sg_dens.loc["Skagerrak"]
    sk_combined_mean = (
        osl["n_sites"] * osl["mean_stock_g_m2"]
        + sk["n_sites"] * sk["mean_stock_g_m2"]
    ) / (osl["n_sites"] + sk["n_sites"])
    sg_density = {
        "Barents Sea": sg_dens.loc["Barents Sea", "mean_stock_g_m2"],
        "Norwegian Sea": sg_dens.loc["Norwegian Sea", "mean_stock_g_m2"],
        "Skagerrak": sk_combined_mean,
    }
    sg_n_sites = {
        "Barents Sea": int(sg_dens.loc["Barents Sea", "n_sites"]),
        "Norwegian Sea": int(sg_dens.loc["Norwegian Sea", "n_sites"]),
        "Skagerrak": int(osl["n_sites"] + sk["n_sites"]),
    }

    # Kelp national mean density (g/m2) from step2 sequestration table
    kelp_nat = nat[nat["ecosystem"] == "macroalgae"].iloc[0]
    kelp_density_g_m2 = kelp_nat["stock_gg_c"] * 1e9 / (kelp_nat["extent_km2"] * 1e6)

    rows = []
    for _, r in coloc.iterrows():
        eco = r["ecosystem"]
        region = r["canonical_region"]
        area_m2 = r["habitat_area_m2"]
        if eco == "seagrass":
            density = sg_density.get(region, np.nan)
            n_sites = sg_n_sites.get(region, 0)
            confidence = "high" if n_sites >= 5 else "low"
        else:  # macroalgae
            density = kelp_density_g_m2
            n_sites = int(kelp_nat["n_transects"])  # 630 transects nationally
            confidence = "medium"  # national mean applied
        stock_ggC = density * area_m2 / 1e9 if not np.isnan(density) else np.nan
        rows.append(
            {
                "ecosystem": eco,
                "canonical_region": region,
                "habitat_area_km2": r["habitat_area_km2"],
                "stock_density_g_m2": density,
                "n_stock_sites": n_sites,
                "stock_GgC": stock_ggC,
                "stock_confidence": confidence,
                # carry pressure / protection forward for the next step
                "percent_habitat_in_mpa": r["percent_habitat_in_mpa"],
                "percent_habitat_protected": r["percent_habitat_protected"],
                "dredging_5km": r["dredging_within_5km_n"],
                "akvakultur_5km": r["akvakultur_within_5km_n"],
                "platforms_10km": r["platforms_within_10km_n"],
                "study_sites_5km": r["study_sites_within_5km_n"],
            }
        )
    return pd.DataFrame(rows)


# ---------- Composite risk and co-benefit scores ----------
def add_composites(df: pd.DataFrame) -> pd.DataFrame:
    """Add z-scored composite risk and co-benefit scores per habitat group.

    Risk components (higher = more risky):
      - dredging density per km2 of habitat
      - aquaculture density per km2 of habitat
      - platforms within 10 km (raw count; sparse)
      - lack of protection (1 - %protected/100)

    Co-benefit components (higher = more co-benefit):
      - %habitat in MPA (governance / biodiversity protection)
      - log10 habitat area (more area => more wave attenuation, nursery)
      - study site density per km2 (proxy for monitoring infrastructure)
    """
    df = df.copy()
    df["dredging_per_km2"] = df["dredging_5km"] / df["habitat_area_km2"]
    df["akvakultur_per_km2"] = df["akvakultur_5km"] / df["habitat_area_km2"]
    df["lack_of_protection"] = 1 - df["percent_habitat_protected"] / 100
    df["log_habitat_km2"] = np.log10(df["habitat_area_km2"])
    df["study_per_km2"] = df["study_sites_5km"] / df["habitat_area_km2"]

    risk_cols = [
        "dredging_per_km2",
        "akvakultur_per_km2",
        "platforms_10km",
        "lack_of_protection",
    ]
    cobenefit_cols = ["percent_habitat_in_mpa", "log_habitat_km2", "study_per_km2"]

    def z(group, cols):
        out = group.copy()
        for c in cols:
            mu, sd = out[c].mean(), out[c].std(ddof=0)
            out[f"{c}_z"] = (out[c] - mu) / sd if sd > 0 else 0.0
        return out

    parts = []
    for eco, sub in df.groupby("ecosystem"):
        sub = z(sub, risk_cols + cobenefit_cols)
        sub["risk_score"] = sub[[f"{c}_z" for c in risk_cols]].mean(axis=1)
        sub["cobenefit_score"] = sub[[f"{c}_z" for c in cobenefit_cols]].mean(axis=1)
        parts.append(sub)
    return pd.concat(parts, ignore_index=True)


# ---------- Plotting ----------
def label_region(r: str) -> str:
    return "Skagerrak (incl. Oslofjord)" if r == "Skagerrak" else r


def panel_a_stocks(ax, df):
    pivot = (
        df.pivot(index="canonical_region", columns="ecosystem", values="stock_GgC")
        .reindex(["Barents Sea", "Norwegian Sea", "Skagerrak"])
    )
    x = np.arange(len(pivot))
    kelp_vals = pivot["macroalgae"].values
    sg_vals = pivot["seagrass"].values
    bw = 0.6
    ax.bar(x, kelp_vals, bw, label="Kelp", color="#2c7a51", edgecolor="black",
           linewidth=0.6, hatch="//")
    ax.bar(x, sg_vals, bw, bottom=kelp_vals, label="Seagrass",
           color="#7fbf7b", edgecolor="black", linewidth=0.6)
    short = {"Barents Sea": "Barents", "Norwegian Sea": "Norwegian Sea",
             "Skagerrak": "Skagerrak\n(+ Oslofjord)"}
    ax.set_xticks(x)
    ax.set_xticklabels([short[r] for r in pivot.index], fontsize=9)
    ax.set_ylabel("Carbon stock (GgC)")
    ax.set_title("A. Where the carbon is", loc="left", fontweight="bold", fontsize=11)
    ax.legend(loc="upper right", frameon=False, fontsize=8)
    ymax = (kelp_vals + sg_vals).max()
    for xi, kv, sv in zip(x, kelp_vals, sg_vals):
        ax.text(xi, kv + sv + ymax * 0.03, f"{kv + sv:.0f}",
                ha="center", fontsize=9, fontweight="bold")
        if sv > ymax * 0.04:  # only label inner segment if visible
            ax.text(xi, kv + sv / 2, f"{sv:.0f}", ha="center", va="center",
                    fontsize=8, color="white")
    ax.set_ylim(0, ymax * 1.18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def panel_b_pressure(ax, df):
    components = [
        ("dredging_per_km2_z", "Dredging /km²"),
        ("akvakultur_per_km2_z", "Aquaculture /km²"),
        ("platforms_10km_z", "Platforms (10 km)"),
        ("lack_of_protection_z", "Unprotected share"),
    ]
    regions = ["Barents Sea", "Norwegian Sea", "Skagerrak"]
    ecos = ["macroalgae", "seagrass"]
    bar_h = 0.36
    component_palette = ["#4292c6", "#fd8d3c", "#74c476", "#9e9ac8"]

    y_positions = []
    y_labels = []
    pos = 0
    short = {"Barents Sea": "Barents", "Norwegian Sea": "Norwegian",
             "Skagerrak": "Skagerrak"}
    for region in regions:
        for eco in ecos:
            row = df[(df["canonical_region"] == region) & (df["ecosystem"] == eco)]
            if row.empty:
                continue
            row = row.iloc[0]
            pos_left, neg_left = 0, 0
            for (col, _label), color in zip(components, component_palette):
                v = row[col]
                if v >= 0:
                    ax.barh(pos, v, height=bar_h, left=pos_left, color=color,
                            edgecolor="black", linewidth=0.4)
                    pos_left += v
                else:
                    ax.barh(pos, v, height=bar_h, left=neg_left, color=color,
                            edgecolor="black", linewidth=0.4, alpha=0.6)
                    neg_left += v
            y_positions.append(pos)
            y_labels.append(f"{short[region]} · {HABITAT_LABEL[eco]}")
            pos += 1
        pos += 0.5

    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels, fontsize=8)
    ax.invert_yaxis()
    ax.axvline(0, color="black", linewidth=0.7)
    ax.set_xlabel("Pressure z-score (signed sum)", fontsize=9)
    ax.set_title("B. Where the pressure is", loc="left", fontweight="bold", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    legend_handles = [Patch(color=c, label=lbl)
                      for (_, lbl), c in zip(components, component_palette)]
    ax.legend(handles=legend_handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.22), ncol=2, frameon=False, fontsize=8)


def panel_c_cobenefit(ax, df):
    components = [
        ("percent_habitat_in_mpa", "MPA share"),
        ("log_habitat_km2", "log₁₀ extent"),
        ("study_per_km2", "Study density"),
    ]
    regions = ["Barents Sea", "Norwegian Sea", "Skagerrak"]
    ecos = ["macroalgae", "seagrass"]
    bar_w = 0.27
    palette = ["#6a3d9a", "#cab2d6", "#fb9a99"]
    short = {"Barents Sea": "Barents", "Norwegian Sea": "Norweg.",
             "Skagerrak": "Skagerrak"}

    df = df.copy()
    for col, _ in components:
        for eco in ecos:
            mask = df["ecosystem"] == eco
            vals = df.loc[mask, col]
            vmin, vmax = vals.min(), vals.max()
            df.loc[mask, f"{col}_n"] = (vals - vmin) / (vmax - vmin) if vmax > vmin else 0.5

    n_groups = len(regions) * len(ecos)
    x = np.arange(n_groups)
    cols_norm = [f"{c}_n" for c, _ in components]
    for i, col in enumerate(cols_norm):
        offsets = (i - 1) * bar_w
        ys = []
        for region in regions:
            for eco in ecos:
                row = df[(df["canonical_region"] == region) & (df["ecosystem"] == eco)]
                ys.append(row.iloc[0][col] if not row.empty else 0)
        ax.bar(x + offsets, ys, bar_w, color=palette[i],
               label=components[i][1], edgecolor="black", linewidth=0.4)

    labels = []
    for region in regions:
        for eco in ecos:
            labels.append(f"{short[region]}\n{HABITAT_LABEL[eco]}")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Normalized (0–1)", fontsize=9)
    ax.set_ylim(0, 1.15)
    ax.set_title("C. Co-benefit fingerprint", loc="left", fontweight="bold", fontsize=11)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3,
              frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _jitter(values: np.ndarray, scale: float, seed: int = 7) -> np.ndarray:
    """Deterministic small jitter so stacked points are visible."""
    rng = np.random.default_rng(seed)
    return values + rng.uniform(-scale, scale, size=len(values))


def panel_d_quadrant(axes, sites_df, regional_df):
    """Per-site scatter on Risk × Co-benefit axes, two stacked subpanels.

    sites_df: per-site composites (per_site_priority_metrics.csv loaded)
    regional_df: regional aggregates (still used for the kelp regional median crosshair)
    """
    ax_kelp, ax_sg = axes

    def draw(ax, eco, title, show_xlabel=False, label_top_n=None):
        sub = sites_df[sites_df["ecosystem"] == eco].copy().reset_index(drop=True)
        if sub.empty:
            ax.set_title(title + " (no data)", loc="left", fontweight="bold", fontsize=11)
            return

        # Light deterministic jitter so stacked sites are visible
        x_raw = sub["risk_z"].values
        y_raw = sub["cobenefit_z"].values
        x_jit_scale = 0.08 if eco == "macroalgae" else 0.04
        y_jit_scale = 0.08 if eco == "macroalgae" else 0.04
        x = _jitter(x_raw, x_jit_scale)
        y = _jitter(y_raw, y_jit_scale)

        # Marker size: stock g/m2 for seagrass, uniform for kelp (no per-site stock data)
        if eco == "seagrass" and sub["carbon_stock_g_m2"].notna().any():
            stock = sub["carbon_stock_g_m2"].fillna(sub["carbon_stock_g_m2"].mean()).values
            s_min, s_max = stock.min(), stock.max()
            sizes = 100 + (stock - s_min) / (s_max - s_min) * 600 if s_max > s_min else np.full_like(stock, 200)
        else:
            sizes = np.full(len(sub), 160.0)

        colors = [REGION_COLOR.get(r, "#888") for r in sub["canonical_region"]]

        # Padded axis limits using raw (un-jittered) extents
        x_pad = max((x_raw.max() - x_raw.min()) * 0.35, 0.4)
        y_pad = max((y_raw.max() - y_raw.min()) * 0.40, 0.4)
        ax.set_xlim(x_raw.min() - x_pad, x_raw.max() + x_pad)
        ax.set_ylim(y_raw.min() - y_pad, y_raw.max() + y_pad)
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()

        # Quadrant medians (within-habitat)
        x_med = float(np.median(x_raw))
        y_med = float(np.median(y_raw))
        ax.axvline(x_med, color="grey", linestyle=":", linewidth=0.9, zorder=1)
        ax.axhline(y_med, color="grey", linestyle=":", linewidth=0.9, zorder=1)

        # Shaded quadrant tints
        x_med_frac = (x_med - xmin) / (xmax - xmin)
        y_med_frac = (y_med - ymin) / (ymax - ymin)
        ax.axhspan(y_med, ymax, xmin=0, xmax=x_med_frac,
                   color="#d1fae5", alpha=0.35, zorder=0)  # SAFEGUARD (low risk + high co-benefit)
        ax.axhspan(y_med, ymax, xmin=x_med_frac, xmax=1,
                   color="#fecaca", alpha=0.45, zorder=0)  # URGENT PROTECT
        ax.axhspan(ymin, y_med, xmin=0, xmax=x_med_frac,
                   color="#e5e7eb", alpha=0.35, zorder=0)  # MONITOR
        ax.axhspan(ymin, y_med, xmin=x_med_frac, xmax=1,
                   color="#fef3c7", alpha=0.45, zorder=0)  # TRIAGE

        # Quadrant labels in corners
        label_kw = dict(fontsize=8, color="#444", fontweight="bold")
        ax.text(xmin + (xmax - xmin) * 0.03, ymax - (ymax - ymin) * 0.04,
                "SAFEGUARD", ha="left", va="top", **label_kw)
        ax.text(xmax - (xmax - xmin) * 0.03, ymax - (ymax - ymin) * 0.04,
                "URGENT PROTECT", ha="right", va="top", **label_kw)
        ax.text(xmin + (xmax - xmin) * 0.03, ymin + (ymax - ymin) * 0.05,
                "MONITOR", ha="left", va="bottom", **label_kw)
        ax.text(xmax - (xmax - xmin) * 0.03, ymin + (ymax - ymin) * 0.05,
                "TRIAGE", ha="right", va="bottom", **label_kw)

        # Site scatter
        ax.scatter(x, y, s=sizes, c=colors, edgecolor="black", linewidth=0.9,
                   zorder=3, alpha=0.85)

        # Selective labelling: top-N by absolute distance from origin (most extreme sites)
        if label_top_n:
            extremity = np.sqrt(x_raw ** 2 + y_raw ** 2)
            top = np.argsort(extremity)[-label_top_n:]
            for i in top:
                name = str(sub.iloc[i]["site_name"])[:18]
                ax.annotate(name, (x[i], y[i]),
                            xytext=(6, 6), textcoords="offset points",
                            fontsize=7.5, fontweight="bold", zorder=4,
                            bbox=dict(boxstyle="round,pad=0.18", facecolor="white",
                                      edgecolor="#bbb", alpha=0.9, linewidth=0.4))

        # Site count annotation (bottom right of quadrant area)
        ax.text(xmax - (xmax - xmin) * 0.02, ymin + (ymax - ymin) * 0.13,
                f"n = {len(sub)} sites",
                ha="right", va="bottom", fontsize=8, style="italic", color="#555")

        ax.set_xlabel("Risk score (z)" if show_xlabel else "", fontsize=9)
        ax.set_ylabel("Co-benefit score (z)", fontsize=9)
        ax.set_title(title, loc="left", fontweight="bold", fontsize=11)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    draw(ax_kelp, "macroalgae", "D. Priority quadrant — Kelp sites", label_top_n=3)
    draw(ax_sg, "seagrass", "     Priority quadrant — Seagrass sites",
         show_xlabel=True, label_top_n=4)

    # Legends
    region_keys = ["Barents Sea", "Norwegian Sea", "Oslofjord", "Skagerrak"]
    color_handles = [Patch(color=REGION_COLOR[r], label=r) for r in region_keys]
    ax_kelp.legend(handles=color_handles, loc="upper center",
                   bbox_to_anchor=(0.5, 1.20), fontsize=8, ncol=4, frameon=False,
                   title=None, handletextpad=0.4, columnspacing=1.0)

    size_handles = [
        plt.scatter([], [], s=120, c="lightgrey", edgecolor="black", label="low"),
        plt.scatter([], [], s=380, c="lightgrey", edgecolor="black", label="med"),
        plt.scatter([], [], s=680, c="lightgrey", edgecolor="black", label="high"),
    ]
    leg_size = ax_sg.legend(handles=size_handles, loc="upper center",
                            bbox_to_anchor=(0.5, -0.30), fontsize=8, ncol=3,
                            frameon=False, title="Marker size = stock g C/m² (seagrass only)",
                            title_fontsize=8, handletextpad=0.3, columnspacing=1.0)
    ax_sg.add_artist(leg_size)


def render(df: pd.DataFrame, sites_df: pd.DataFrame) -> Path:
    # Layout: left column (A, B, C stacked), right column (D-kelp, D-seagrass stacked).
    # The hero (D) gets ~half the canvas width and full height.
    fig = plt.figure(figsize=(16, 11))
    gs = GridSpec(
        3, 2, figure=fig,
        width_ratios=[1.0, 1.15],
        height_ratios=[1.0, 1.0, 1.0],
        hspace=0.85, wspace=0.32,
        left=0.07, right=0.97, top=0.88, bottom=0.10,
    )
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[1, 0])
    ax_c = fig.add_subplot(gs[2, 0])

    # Right column = D, split into two stacked subplots with their own gridspec
    gs_d = gs[:, 1].subgridspec(2, 1, hspace=0.45)
    ax_d_kelp = fig.add_subplot(gs_d[0, 0])
    ax_d_sg = fig.add_subplot(gs_d[1, 0])

    panel_a_stocks(ax_a, df)
    panel_b_pressure(ax_b, df)
    panel_c_cobenefit(ax_c, df)
    panel_d_quadrant((ax_d_kelp, ax_d_sg), sites_df, df)

    fig.suptitle(
        "Norway blue carbon — integrated priority synthesis",
        fontsize=16, fontweight="bold", x=0.07, ha="left", y=0.965,
    )
    fig.text(0.07, 0.935,
             "Stock × Risk × Co-benefit, three canonical regions × two habitats",
             fontsize=10.5, color="#555", ha="left")

    fig.text(0.07, 0.025,
             "Panels A–C are regional aggregates (3-region cut: Skagerrak absorbs Oslofjord).  "
             "Panel D plots individual study sites (n = 31): risk = dredging + akvakultur + platforms within 5 km (haversine), "
             "co-benefit = regional MPA share + within-5 km research density + log regional habitat extent. "
             "z-scored within ecosystem; small jitter applied so stacked sites are visible.  "
             "Kelp site stock data unavailable (Ribeiro 2022 pop-genetics) — markers uniform.  "
             "Seagrass marker size = site carbon stock g C/m² (Gagnon 2024).",
             fontsize=8, color="#444", ha="left")

    out_png = FIG / "priority_quadrant_hero.png"
    out_pdf = FIG / "priority_quadrant_hero.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)
    return out_png


def main():
    df = regional_stocks()
    df = add_composites(df)
    df.to_csv(PROC / "regional_priority_metrics.csv", index=False)

    sites_path = PROC / "per_site_priority_metrics.csv"
    if not sites_path.exists():
        raise FileNotFoundError(
            f"missing {sites_path} — run scripts/per_site_priority_metrics.py first"
        )
    sites_df = pd.read_csv(sites_path)

    out = render(df, sites_df)
    print(f"wrote {out}")
    print(f"wrote {PROC / 'regional_priority_metrics.csv'}")
    print()
    print(df[["ecosystem", "canonical_region", "stock_GgC",
              "risk_score", "cobenefit_score"]].to_string(index=False))
    print()
    print("per-site panel D:", sites_df.groupby("ecosystem").size().to_dict())


if __name__ == "__main__":
    main()
