"""Generate an interactive study-site map of Norwegian kelp + seagrass sites.

Inputs:
  - data/Norway_Macroalgae_Database.xlsm        (Site_Level sheet)
  - data/Norway_Seagrass_ Master_Database (4).xlsx  (Site level sheet)

Output:
  - maps/norway.html (self-contained Leaflet map via Folium)

Encodings:
  - Marker shape:  ●  kelp (CircleMarker)   ■  seagrass (DivIcon square)
  - Marker size:   per-ecosystem normalized — kelp by Sample_size_n,
                   seagrass by total cores per site.
  - Marker color:  switchable layer — Region (canonical 4 / detailed),
                   Year, Sediment C stock (seagrass-only signal),
                   Source study, Habitat type.
  - Click popup:   full site metadata, source citation, source URL.

Seagrass coordinates are not in the workbook; they were transcribed from
Gagnon et al. 2024, Supplementary Table S1
(https://www.nature.com/articles/s41598-024-74760-3, MOESM2_ESM.docx).

Run:
    python scripts/build_norway_map.py
"""

from __future__ import annotations

import json
import re
import unicodedata
import html as html_lib
from pathlib import Path

import pandas as pd
import folium
from folium.plugins import HeatMap
from branca.colormap import LinearColormap
from branca.element import Template, MacroElement


REPO_ROOT = Path(__file__).resolve().parent.parent

# Bounding box for Norwegian waters (mainland + Svalbard + EEZ)
NORWAY_BBOX = {"lat_min": 56.5, "lat_max": 82.0, "lon_min": -5.0, "lon_max": 35.0}
KELP_PATH = REPO_ROOT / "data" / "Norway_Macroalgae_Database.xlsm"
SEAGRASS_PATH = REPO_ROOT / "data" / "Norway_Seagrass_ Master_Database (4).xlsx"
OUT_PATH = REPO_ROOT / "maps" / "norway.html"
STEP2_REGIONAL_PATH = REPO_ROOT / "data" / "processed" / "step2_seagrass_stocks_by_region.csv"
STEP2_NATIONAL_PATH = REPO_ROOT / "data" / "processed" / "step2_national_sequestration.csv"
STEP2_VALUATION_PATH = REPO_ROOT / "data" / "processed" / "step2_valuation.csv"
STEP2_COBENEFITS_PATH = REPO_ROOT / "data" / "processed" / "step2_cobenefits.csv"
SPATIAL_METRICS_PATH = REPO_ROOT / "data" / "processed" / "spatial_analysis" / "habitat_colocation_metrics.csv"
HB19_MAP_DIR = REPO_ROOT / "data" / "external" / "naturbase_hb19" / "map_layers"
HB19_ALEGRAS_PATH = HB19_MAP_DIR / "naturbase_hb19_alegras_map.geojson"
HB19_TARE_PATH = HB19_MAP_DIR / "naturbase_hb19_tare_map.geojson"
VERN_MAP_DIR = REPO_ROOT / "data" / "external" / "verneomraader" / "map_layers"
VERN_ALL_PATH = VERN_MAP_DIR / "verneomraader_marine_map.geojson"
VERN_MPA_PATH = VERN_MAP_DIR / "verneomraader_mpa_map.geojson"
AKVAKULTUR_PATH = REPO_ROOT / "data" / "external" / "akvakultur" / "akvakultur_marine_sites.csv"
EMODNET_DIR = REPO_ROOT / "data" / "external" / "emodnet"
EMODNET_DREDGING_PATH = EMODNET_DIR / "emodnet_dredging.csv"
EMODNET_PLATFORMS_PATH = EMODNET_DIR / "emodnet_platforms.csv"
EMODNET_WINDFARMS_PATH = EMODNET_DIR / "emodnet_windfarms.csv"
MASSIMAL_MANIFEST_PATH = REPO_ROOT / "data" / "external" / "massimal" / "massimal_manifest.json"
BOTTOM_TRAWLS_PATH = REPO_ROOT / "data" / "Bottom_trawls.csv"
BOTTOM_OTTER_TRAWLS_PATH = REPO_ROOT / "data" / "Bottom otter trawls.csv"
BOTTOM_SEINES_PATH = REPO_ROOT / "data" / "Bottom seines.csv"
OFFSHORE_DRILLING_PATH = REPO_ROOT / "data" / "Offshore_drilling.csv"
PORT_VESSEL_TRAFFIC_PATH = REPO_ROOT / "data" / "Port_vessel_traffic.csv"
SEABED_EROSION_PATH = REPO_ROOT / "data" / "Seabed_erosion.csv"
FISH_HABITAT_PATH = REPO_ROOT / "data" / "CommercialFish_Habitat_projections_climatechange.csv"
SEDIMENTATION_PATH = REPO_ROOT / "data" / "Sedimentation_rates.csv"
COASTAL_RESILIENCE_PATH = REPO_ROOT / "data" / "Coastal_resilience_vulnerability.csv"

# Decimal-degree coordinates from Gagnon et al. 2024 supplementary Table S1.
SEAGRASS_COORDS: dict[str, tuple[float, float]] = {
    "Sømskilen":   (58.404,  8.714),
    "Ærøya":       (58.417,  8.763),
    "Merdø":       (58.428,  8.808),
    "Langerompa":  (58.431,  8.801),
    "Hove":        (58.448,  8.818),
    "Sandspollen": (59.663, 10.590),
    "Kapellkilen": (59.666, 10.587),
    "Røvik":       (67.215, 15.008),
    "Porsanger":   (70.112, 25.232),
}

QUALITATIVE_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
]

CANONICAL_REGIONS = ["Barents Sea", "Norwegian Sea", "Oslofjord", "Skagerrak"]
CANONICAL_REGION_COLORS = {
    "Barents Sea":   "#2c7fb8",
    "Norwegian Sea": "#1b9e77",
    "Oslofjord":     "#d95f02",
    "Skagerrak":     "#e7298a",
}

NO_DATA_GREY = "#bbbbbb"

# Fixed per-ecosystem colors used on the "Ecosystem type" default layer
KELP_ECOSYSTEM_COLOR = "#FF6B35"       # vivid orange
SEAGRASS_ECOSYSTEM_COLOR = "#7B2FBE"   # vivid purple

HB19_STYLE_COLORS = {
    "alegras": {
        "A": "#006d2c",
        "B": "#31a354",
        "C": "#a1d99b",
        "default": "#74c476",
    },
    "tare": {
        "A": "#8c510a",
        "B": "#bf812d",
        "C": "#dfc27d",
        "default": "#bf812d",
    },
}

CONTEXT_POINT_STYLE = {
    "akvakultur": {"color": "#3182bd", "radius": 4, "label": "Aquaculture register sites"},
    "dredging": {"color": "#756bb1", "radius": 4, "label": "EMODnet dredging records"},
    "platforms": {"color": "#636363", "radius": 5, "label": "EMODnet offshore platforms"},
    "windfarms": {"color": "#41b6c4", "radius": 5, "label": "EMODnet windfarms"},
    "massimal": {"color": "#de2d26", "radius": 6, "label": "MASSIMAL remote-sensing field sites"},
    "bottom_trawls": {"color": "#e6550d", "radius": 3, "label": "Bottom trawl effort (ICES grid)"},
    "bottom_otter_trawls": {"color": "#fd8d3c", "radius": 3, "label": "Bottom otter trawl effort (ICES grid)"},
    "bottom_seines": {"color": "#fdae6b", "radius": 3, "label": "Bottom seine effort (ICES grid)"},
    "offshore_drilling": {"color": "#252525", "radius": 4, "label": "Offshore drilling installations"},
    "port_traffic": {"color": "#08519c", "radius": 5, "label": "Port vessel traffic"},
    "sedimentation": {"color": "#74c476", "radius": 4, "label": "Sedimentation rate measurement sites"},
    "coastal_resilience": {"color": "#9ebcda", "radius": 4, "label": "Coastal resilience/vulnerability index"},
    "seabed_erosion": {"color": "#8B4513", "radius": 4, "label": "Seabed erosion areas (EMODnet)"},
    "fish_habitat": {"color": "#20B2AA", "radius": 3, "label": "Fish habitat suitability (climate projection)"},
}

COLOCATION_CLASSES = {
    "pressure_low_protection": {
        "label": "Pressure nearby + <1% protected",
        "color": "#b2182b",
        "description": "Pressure signal within 5 km and almost no protected-area overlap.",
    },
    "pressure_and_protected": {
        "label": "Pressure nearby + protected",
        "color": "#fdae61",
        "description": "Pressure signal within 5 km and at least 10% protected-area overlap.",
    },
    "protected": {
        "label": "Protected habitat",
        "color": "#2b8cbe",
        "description": "At least 10% protected-area overlap and no nearby pressure signal.",
    },
    "study_covered": {
        "label": "Study site within 5 km",
        "color": "#9ecae1",
        "description": "Mapped habitat with a study site within 5 km.",
    },
    "mapped_gap": {
        "label": "Mapped habitat / evidence gap",
        "color": "#d9d9d9",
        "description": "Mapped habitat with no nearby study site, pressure, or strong protection signal.",
    },
}


def canonical_region(region_str: str | None, lat: float | None) -> str:
    """Normalize a free-text region label onto the four canonical Norwegian
    blue-carbon regions used by Gagnon et al. 2024 / the roadmap doc.
    """
    s = (region_str or "").lower()
    if any(k in s for k in ("barents", "porsanger", "hammerfest", "northern norway", "bodø")):
        return "Barents Sea"
    if "norwegian sea" in s:
        return "Norwegian Sea"
    if "outer oslofjord" in s or "skagerrak" in s:
        return "Skagerrak"
    if "oslofjord" in s:
        return "Oslofjord"
    if any(k in s for k in (
        "hardanger", "sognef", "mid-norway", "north sea", "southwest norway", "west norway"
    )):
        return "Norwegian Sea"
    if lat is None:
        return "Unknown"
    if lat >= 67:
        return "Barents Sea"
    if lat >= 60:
        return "Norwegian Sea"
    return "Skagerrak"


def dms_to_dd(value) -> float | None:
    """Parse degrees/minutes/seconds with a hemisphere letter to decimal degrees,
    handling the unicode quote variants used in the kelp workbook.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = unicodedata.normalize("NFKC", str(value)).strip()
    s = (
        s.replace("’", "'").replace("‘", "'")
        .replace("”", '"').replace("“", '"')
        .replace("′", "'").replace("″", '"')
    )
    s = s.replace("''", '"')
    m = re.search(
        r"([0-9]+(?:\.[0-9]+)?)°\s*([0-9]+(?:\.[0-9]+)?)?'?\s*([0-9]+(?:\.[0-9]+)?)?\"?\s*([NSEW])",
        s,
    )
    if not m:
        return None
    deg = float(m.group(1))
    minutes = float(m.group(2) or 0)
    seconds = float(m.group(3) or 0)
    hemi = m.group(4)
    dd = deg + minutes / 60 + seconds / 3600
    return -dd if hemi in ("S", "W") else round(dd, 6)


def extract_year(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    m = re.search(r"(19|20)\d{2}", str(value))
    return int(m.group(0)) if m else None


def parse_point_wkt(geom_str) -> tuple[float, float]:
    """Extract (lat, lon) from a WKT POINT string like 'POINT (lon lat)'."""
    if not geom_str or not isinstance(geom_str, str):
        return (float("nan"), float("nan"))
    m = re.match(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", geom_str.strip())
    if not m:
        return (float("nan"), float("nan"))
    return float(m.group(2)), float(m.group(1))  # lat=y, lon=x


def first_number(value) -> float | None:
    """Return the first numeric token in a free-text cell. Handles values like
    '~30', '4000*', '5–10 m'. Returns None if no numeric token is found.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    m = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    return float(m.group(0)) if m else None


def load_kelp_sites(xlsm_path: Path) -> pd.DataFrame:
    df = pd.read_excel(xlsm_path, sheet_name="Site_Level", header=1, engine="openpyxl")
    df["lat"] = df["Latitude"].apply(dms_to_dd)
    df["lon"] = df["Longitude"].apply(dms_to_dd)
    df["year"] = df["Year"].apply(extract_year)
    df["sample_n"] = df["Sample_size_n"].apply(first_number)
    sites = df.dropna(subset=["lat", "lon"]).reset_index(drop=True).copy()
    sites["region_short"] = sites["Region"].astype(str).str.split("/").str[0].str.strip()
    sites["region_canonical"] = sites.apply(
        lambda r: canonical_region(r.get("Region"), r.get("lat")), axis=1
    )
    sites["ecosystem"] = "Kelp"
    return sites


def load_seagrass_sites(xlsx_path: Path) -> pd.DataFrame:
    if not xlsx_path.exists():
        return pd.DataFrame()
    df = pd.read_excel(xlsx_path, sheet_name="Site level", header=1, engine="openpyxl")
    df = df.dropna(subset=["Site Name"]).copy()
    df["c_stock"] = df["Sediment C stock (g/m2)"].apply(first_number)
    df["sample_n"] = pd.to_numeric(df["Sample size (n)"], errors="coerce")
    df["depth"] = pd.to_numeric(df["Water depth (m)"], errors="coerce")
    df["temp"] = pd.to_numeric(df["Temperature mean C"], errors="coerce")
    df["wave_exp"] = pd.to_numeric(df["Wave exposure index"], errors="coerce")
    df["year_int"] = pd.to_numeric(df["Year"], errors="coerce")
    df["ag_biomass"] = pd.to_numeric(df["Aboveground biomass g m2"], errors="coerce")
    df["bg_biomass"] = pd.to_numeric(df["Belowground biomass g m2"], errors="coerce")

    agg = df.groupby("Site Name", as_index=False).agg(
        n_records=("ID", "count"),
        cores_total=("sample_n", "sum"),
        c_stock_mean=("c_stock", "mean"),
        c_stock_min=("c_stock", "min"),
        c_stock_max=("c_stock", "max"),
        ag_biomass_mean=("ag_biomass", "mean"),
        bg_biomass_mean=("bg_biomass", "mean"),
        depth_min=("depth", "min"),
        depth_max=("depth", "max"),
        temp_mean=("temp", "mean"),
        wave_exp=("wave_exp", "mean"),
        sediment=("Sediment type", lambda s: ", ".join(sorted({x for x in s.dropna()}))),
        region_orig=("Region", "first"),
        year_min=("year_int", "min"),
        year_max=("year_int", "max"),
        source=("Source:", "first"),
    )
    agg["lat"] = agg["Site Name"].map(lambda s: SEAGRASS_COORDS.get(s, (None, None))[0])
    agg["lon"] = agg["Site Name"].map(lambda s: SEAGRASS_COORDS.get(s, (None, None))[1])
    missing = agg[agg["lat"].isna()]["Site Name"].tolist()
    if missing:
        print(f"  warning: no coordinates for seagrass site(s): {missing}")
    agg = agg.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    agg["region_canonical"] = agg.apply(
        lambda r: canonical_region(r["region_orig"], r["lat"]), axis=1
    )
    agg["ecosystem"] = "Seagrass"
    return agg


def categorical_colors(values) -> dict[str, str]:
    uniq = sorted({v for v in pd.Series(values).dropna()}, key=str)
    return {v: QUALITATIVE_PALETTE[i % len(QUALITATIVE_PALETTE)] for i, v in enumerate(uniq)}


def radius_for_n(n: float | None, n_min: float, n_max: float) -> float:
    if n is None or pd.isna(n):
        return 4.0
    if n_max is None or pd.isna(n_max) or n_max <= n_min:
        return 5.0
    frac = ((n - n_min) / (n_max - n_min)) ** 0.5
    return 3.5 + 5.5 * frac


def fmt_row(label: str, val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
        return ""
    return f"<tr><td style='padding-right:10px;color:#555;vertical-align:top'>{label}</td><td>{val}</td></tr>"


def kelp_popup_html(row: pd.Series) -> str:
    url = row.get("Source_URL")
    src = row.get("Source_short", "")
    if isinstance(url, str) and url.startswith("http"):
        src_html = f"<a href='{url}' target='_blank'>{src}</a>"
    else:
        src_html = str(src) if pd.notna(src) else ""

    notes = row.get("Notes")
    if isinstance(notes, str) and len(notes) > 280:
        notes = notes[:280] + "&hellip;"

    rows = [
        fmt_row("Ecosystem", "Kelp / macroalgae"),
        fmt_row("Region (canonical)", row.get("region_canonical")),
        fmt_row("Region (source label)", row.get("Region")),
        fmt_row("Year", row.get("Year")),
        fmt_row("Species", row.get("Species")),
        fmt_row("Habitat", row.get("Habitat_type")),
        fmt_row("Depth range", row.get("Depth_range_m")),
        fmt_row("Sample size (n)", row.get("Sample_size_n")),
        fmt_row("Lat / Lon", f"{row['lat']:.4f}, {row['lon']:.4f}"),
        fmt_row("Source", src_html),
        fmt_row("Notes", notes),
    ]
    body = "".join(r for r in rows if r)
    return (
        f"<div style='font-family:system-ui,sans-serif;font-size:12.5px;max-width:340px'>"
        f"<div style='font-weight:600;font-size:13.5px;margin-bottom:4px'>{row['Site']}</div>"
        f"<table style='border-collapse:collapse'>{body}</table></div>"
    )


def seagrass_popup_html(row: pd.Series) -> str:
    if pd.notna(row["year_min"]) and pd.notna(row["year_max"]):
        if row["year_min"] == row["year_max"]:
            yr = f"{int(row['year_min'])}"
        else:
            yr = f"{int(row['year_min'])}–{int(row['year_max'])}"
    else:
        yr = ""
    if pd.notna(row["depth_min"]) and pd.notna(row["depth_max"]):
        if row["depth_min"] == row["depth_max"]:
            depth = f"{row['depth_min']:.1f} m"
        else:
            depth = f"{row['depth_min']:.1f}–{row['depth_max']:.1f} m"
    else:
        depth = ""
    if pd.notna(row["c_stock_mean"]):
        cstk = (
            f"{row['c_stock_mean']:,.0f} "
            f"(range {row['c_stock_min']:,.0f}–{row['c_stock_max']:,.0f})"
        )
    else:
        cstk = ""

    def num(v, decimals=1, fmt="{:.1f}"):
        return fmt.format(v) if pd.notna(v) else ""

    rows = [
        fmt_row("Ecosystem", "Seagrass (<i>Zostera marina</i>)"),
        fmt_row("Region (canonical)", row["region_canonical"]),
        fmt_row("Region (source label)", row["region_orig"]),
        fmt_row("Sampling year", yr),
        fmt_row("Cores in DB", int(row["n_records"]) if pd.notna(row["n_records"]) else ""),
        fmt_row("Water depth", depth),
        fmt_row("Sediment type", row["sediment"]),
        fmt_row("Sediment C stock (g/m²)", cstk),
        fmt_row("Aboveground biomass (g/m²)", num(row["ag_biomass_mean"])),
        fmt_row("Belowground biomass (g/m²)", num(row["bg_biomass_mean"])),
        fmt_row("Mean temperature (°C)", num(row["temp_mean"])),
        fmt_row("Wave exposure index", num(row["wave_exp"], fmt="{:,.0f}")),
        fmt_row("Lat / Lon", f"{row['lat']:.4f}, {row['lon']:.4f}"),
        fmt_row("Source", row["source"]),
    ]
    body = "".join(r for r in rows if r)
    return (
        f"<div style='font-family:system-ui,sans-serif;font-size:12.5px;max-width:340px'>"
        f"<div style='font-weight:600;font-size:13.5px;margin-bottom:4px'>{row['Site Name']}</div>"
        f"<table style='border-collapse:collapse'>{body}</table></div>"
    )


def add_kelp_marker(fg, row, color, n_min, n_max):
    side = max(7.0, 1.8 * radius_for_n(row.get("sample_n"), n_min, n_max))
    side_i = int(round(side))
    inner = (
        f"<div style='width:{side_i}px;height:{side_i}px;"
        f"background:{color};opacity:0.82;"
        f"border:1.5px solid #111;box-sizing:border-box;"
        f"transform:rotate(45deg);'></div>"
    )
    icon = folium.DivIcon(
        html=inner, icon_size=(side_i, side_i), icon_anchor=(side_i // 2, side_i // 2)
    )
    folium.Marker(
        location=(row["lat"], row["lon"]),
        icon=icon,
        tooltip=f"{row['Site']} — kelp (n={row.get('Sample_size_n')})",
        popup=folium.Popup(kelp_popup_html(row), max_width=380),
    ).add_to(fg)


def add_seagrass_marker(fg, row, color, n_min, n_max):
    side = max(7.0, 1.8 * radius_for_n(row.get("cores_total"), n_min, n_max))
    side_i = int(round(side))
    inner = (
        f"<div style='width:{side_i}px;height:{side_i}px;"
        f"background:{color};opacity:0.82;"
        f"border:1.5px solid #111;box-sizing:border-box;'></div>"
    )
    icon = folium.DivIcon(
        html=inner, icon_size=(side_i, side_i), icon_anchor=(side_i // 2, side_i // 2)
    )
    folium.Marker(
        location=(row["lat"], row["lon"]),
        icon=icon,
        tooltip=f"{row['Site Name']} — seagrass (cores={int(row['n_records'])})",
        popup=folium.Popup(seagrass_popup_html(row), max_width=380),
    ).add_to(fg)


def add_color_layer(
    fmap, name, kelp, seagrass,
    kelp_color_fn, seagrass_color_fn,
    kelp_n_min, kelp_n_max, sea_n_min, sea_n_max,
    show=False,
):
    fg = folium.FeatureGroup(name=name, show=show)
    for _, row in kelp.iterrows():
        add_kelp_marker(fg, row, kelp_color_fn(row), kelp_n_min, kelp_n_max)
    for _, row in seagrass.iterrows():
        add_seagrass_marker(fg, row, seagrass_color_fn(row), sea_n_min, sea_n_max)
    fg.add_to(fmap)
    return fg


def hb19_style(layer_key: str):
    colors = HB19_STYLE_COLORS[layer_key]

    def style(feature):
        verdi = (feature.get("properties") or {}).get("verdi")
        color = colors.get(verdi, colors["default"])
        return {
            "color": color,
            "weight": 0.8,
            "fillColor": color,
            "fillOpacity": 0.25,
        }

    return style


def hb19_highlight(_feature):
    return {
        "weight": 2.2,
        "fillOpacity": 0.45,
    }


def add_hb19_layer(fmap: folium.Map, path: Path, layer_key: str, name: str) -> int:
    if not path.exists():
        print(f"  warning: HB19 map layer not found: {path}")
        return 0

    data = json.loads(path.read_text(encoding="utf-8"))
    feature_count = len(data.get("features", []))
    folium.GeoJson(
        data,
        name=f"Naturbase HB19: {name} ({feature_count:,})",
        show=False,
        style_function=hb19_style(layer_key),
        highlight_function=hb19_highlight,
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "omraadenavn",
                "naturtype_label",
                "verdi_label",
                "kommune",
                "marinNaturtypeId",
            ],
            aliases=["Name", "Nature type", "Value", "Municipality", "Naturbase ID"],
            localize=True,
            sticky=False,
        ),
        popup=folium.GeoJsonPopup(
            fields=[
                "omraadenavn",
                "naturtype_label",
                "verdi_label",
                "kommune",
                "faktaark",
                "area_m2",
            ],
            aliases=["Name", "Nature type", "Value", "Municipality", "Fact sheet", "Area m²"],
            localize=True,
            labels=True,
            max_width=360,
        ),
    ).add_to(fmap)
    return feature_count


def protected_area_style(feature):
    is_mpa = bool((feature.get("properties") or {}).get("is_mpa"))
    color = "#08519c" if is_mpa else "#6baed6"
    return {
        "color": color,
        "weight": 1.0 if is_mpa else 0.7,
        "fillColor": color,
        "fillOpacity": 0.20 if is_mpa else 0.12,
    }


def add_protected_area_layer(fmap: folium.Map, path: Path, name: str) -> int:
    if not path.exists():
        print(f"  warning: protected-area map layer not found: {path}")
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    feature_count = len(data.get("features", []))
    folium.GeoJson(
        data,
        name=f"Protected areas: {name} ({feature_count:,})",
        show=False,
        style_function=protected_area_style,
        highlight_function=hb19_highlight,
        tooltip=folium.GeoJsonTooltip(
            fields=["navn", "verneform", "iucn", "kommune", "naturvernId"],
            aliases=["Name", "Protection type", "IUCN", "Municipality", "ID"],
            localize=True,
            sticky=False,
        ),
        popup=folium.GeoJsonPopup(
            fields=["offisieltNavn", "verneform", "iucn", "kommune", "faktaark", "area_m2"],
            aliases=["Official name", "Protection type", "IUCN", "Municipality", "Fact sheet", "Area m²"],
            localize=True,
            labels=True,
            max_width=360,
        ),
    ).add_to(fmap)
    return feature_count


def colocation_class(row: pd.Series | dict) -> str:
    protected = float(row.get("percent_protected") or 0) >= 10
    pressure = float(row.get("colocation_pressure_index") or 0) > 0
    low_protection = float(row.get("percent_protected") or 0) < 1
    studied = float(row.get("study_sites_within_5km_n") or 0) > 0
    if pressure and low_protection:
        return "pressure_low_protection"
    if pressure and protected:
        return "pressure_and_protected"
    if protected:
        return "protected"
    if studied:
        return "study_covered"
    return "mapped_gap"


def read_hb19_features_with_ids(path: Path, ecosystem: str, habitat_type: str) -> list[dict]:
    if not path.exists():
        print(f"  warning: co-location HB19 layer not found: {path}")
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    for idx, feature in enumerate(features):
        props = feature.setdefault("properties", {})
        naturbase_id = str(props.get("marinNaturtypeId", "na"))
        props["habitat_id"] = f"{ecosystem}_{habitat_type}_{idx}_{naturbase_id}"
        props["ecosystem"] = ecosystem
        props["habitat_group"] = habitat_type
    return features


def add_colocation_layers(fmap: folium.Map) -> dict[str, int]:
    if not SPATIAL_METRICS_PATH.exists():
        print(f"  warning: co-location metrics not found: {SPATIAL_METRICS_PATH}")
        return {}

    metrics = pd.read_csv(SPATIAL_METRICS_PATH)
    metrics["map_class"] = metrics.apply(colocation_class, axis=1)
    metrics_by_id = metrics.set_index("habitat_id").to_dict(orient="index")
    metric_fields = [
        "habitat_area_m2",
        "percent_protected",
        "percent_mpa",
        "colocation_pressure_index",
        "study_sites_within_5km_n",
        "akvakultur_within_5km_n",
        "dredging_within_5km_n",
        "nearest_study_site_km",
        "nearest_akvakultur_km",
        "nearest_dredging_km",
        "high_pressure_low_protection_flag",
        "evidence_gap_flag",
        "canonical_region",
        "map_class",
    ]

    features = []
    features.extend(read_hb19_features_with_ids(HB19_ALEGRAS_PATH, "seagrass", "eelgrass"))
    features.extend(read_hb19_features_with_ids(HB19_TARE_PATH, "macroalgae", "kelp_forest"))

    by_class: dict[str, list[dict]] = {key: [] for key in COLOCATION_CLASSES}
    for feature in features:
        props = feature.setdefault("properties", {})
        metric = metrics_by_id.get(props.get("habitat_id"), {})
        for field in metric_fields:
            value = metric.get(field)
            if pd.isna(value):
                value = None
            props[field] = value
        cls = props.get("map_class") or colocation_class(props)
        props["map_class"] = cls
        props["class_label"] = COLOCATION_CLASSES[cls]["label"]
        props["class_description"] = COLOCATION_CLASSES[cls]["description"]
        props["protection_summary"] = f"{float(props.get('percent_protected') or 0):.1f}% protected"
        props["pressure_summary"] = f"{int(float(props.get('colocation_pressure_index') or 0))} pressure signals"
        props["study_summary"] = f"{int(float(props.get('study_sites_within_5km_n') or 0))} study sites within 5 km"
        by_class[cls].append(feature)

    counts = {key: len(value) for key, value in by_class.items()}
    for cls, class_features in by_class.items():
        if not class_features:
            continue
        meta = COLOCATION_CLASSES[cls]

        def style_function(_feature, color=meta["color"], cls=cls):
            fill_opacity = 0.42 if cls != "mapped_gap" else 0.24
            weight = 0.8 if cls in ("pressure_low_protection", "pressure_and_protected") else 0.45
            return {
                "color": color,
                "weight": weight,
                "fillColor": color,
                "fillOpacity": fill_opacity,
            }

        folium.GeoJson(
            {"type": "FeatureCollection", "features": class_features},
            name=f"Co-location: {meta['label']} ({len(class_features):,})",
            show=cls in ("pressure_low_protection", "pressure_and_protected"),
            style_function=style_function,
            highlight_function=hb19_highlight,
            tooltip=folium.GeoJsonTooltip(
                fields=[
                    "omraadenavn",
                    "naturtype_label",
                    "class_label",
                    "protection_summary",
                    "pressure_summary",
                    "study_summary",
                ],
                aliases=["Name", "Habitat", "Co-location class", "Protection", "Pressure", "Study coverage"],
                localize=True,
                sticky=False,
            ),
            popup=folium.GeoJsonPopup(
                fields=[
                    "omraadenavn",
                    "naturtype_label",
                    "canonical_region",
                    "class_label",
                    "class_description",
                    "protection_summary",
                    "pressure_summary",
                    "study_summary",
                    "percent_mpa",
                    "nearest_study_site_km",
                    "nearest_akvakultur_km",
                    "nearest_dredging_km",
                ],
                aliases=[
                    "Name",
                    "Habitat",
                    "Region",
                    "Co-location class",
                    "Meaning",
                    "Protection",
                    "Pressure",
                    "Study coverage",
                    "MPA overlap %",
                    "Nearest study km",
                    "Nearest aquaculture km",
                    "Nearest dredging km",
                ],
                localize=True,
                labels=True,
                max_width=400,
            ),
        ).add_to(fmap)
    return counts


def add_point_csv_layer(
    fmap: folium.Map,
    path: Path,
    layer_key: str,
    name: str,
    lat_col: str = "lat_dd",
    lon_col: str = "lon_dd",
    country_filter: str | None = None,
    max_rows: int | None = None,
    geom_col: str | None = None,
    bbox: dict | None = None,
) -> int:
    if not path.exists():
        print(f"  warning: point layer CSV not found: {path}")
        return 0
    df = pd.read_csv(path)
    if geom_col and geom_col in df.columns:
        parsed = df[geom_col].apply(lambda g: pd.Series(parse_point_wkt(g), index=["_lat", "_lon"]))
        df["_lat"] = parsed["_lat"]
        df["_lon"] = parsed["_lon"]
        lat_col, lon_col = "_lat", "_lon"
    if country_filter and "country" in df.columns:
        df = df[df["country"].astype(str).str.lower() == country_filter.lower()].copy()
    df = df.dropna(subset=[lat_col, lon_col]).copy()
    if bbox:
        df = df[
            (df[lat_col] >= bbox["lat_min"]) & (df[lat_col] <= bbox["lat_max"]) &
            (df[lon_col] >= bbox["lon_min"]) & (df[lon_col] <= bbox["lon_max"])
        ].copy()
    if max_rows is not None and len(df) > max_rows:
        df = df.head(max_rows).copy()

    style = CONTEXT_POINT_STYLE[layer_key]
    fg = folium.FeatureGroup(name=f"{name} ({len(df):,})", show=False)

    for _, row in df.iterrows():
        if layer_key == "akvakultur":
            title = row.get("LOK_NAVN", "Aquaculture site")
            rows = [
                fmt_row("Site", row.get("LOK_NAVN")),
                fmt_row("Species", row.get("ART")),
                fmt_row("Production form", row.get("PRODUKSJONSFORM")),
                fmt_row("Operator", row.get("NAVN")),
                fmt_row("Municipality", row.get("LOK_KOM")),
                fmt_row("Water environment", row.get("VANNMILJØ")),
            ]
        elif layer_key == "dredging":
            title = row.get("extraction_area", "Dredging")
            rows = [
                fmt_row("Area", row.get("extraction_area")),
                fmt_row("Country", row.get("country")),
                fmt_row("Year", row.get("year_")),
                fmt_row("Purpose", row.get("purpose")),
                fmt_row("Material", row.get("material")),
                fmt_row("Extracted t", row.get("extracted_amount_t")),
            ]
        elif layer_key == "platforms":
            title = row.get("name", "Platform")
            rows = [
                fmt_row("Name", row.get("name")),
                fmt_row("Status", row.get("current_status")),
                fmt_row("Function", row.get("function")),
                fmt_row("Operator", row.get("operator")),
                fmt_row("Water depth", row.get("water_depth")),
            ]
        elif layer_key in ("bottom_trawls", "bottom_otter_trawls", "bottom_seines"):
            label_map = {
                "bottom_trawls": "Bottom trawl",
                "bottom_otter_trawls": "Bottom otter trawl",
                "bottom_seines": "Bottom seine",
            }
            title = f"{label_map[layer_key]} ({row.get('c_squar', '')})"
            rows = [
                fmt_row("ICES rectangle", row.get("c_squar")),
                fmt_row("Ecoregion", row.get("ecoregn")),
                fmt_row("Avg years", row.get("avgyears")),
                fmt_row("Fishing hours", row.get("fsh__fo")),
                fmt_row("Mean fishing kW", row.get("mw_fshn")),
                fmt_row("Valid from", row.get("validfrom")),
                fmt_row("Valid to", row.get("validto")),
            ]
        elif layer_key == "offshore_drilling":
            title = row.get("name", layer_key.replace("_", " ").title())
            rows = [
                fmt_row("Name", row.get("name")),
                fmt_row("Country", row.get("country")),
                fmt_row("Status", row.get("current_status")),
                fmt_row("Category", row.get("category")),
                fmt_row("Function", row.get("function")),
                fmt_row("Operator", row.get("operator")),
                fmt_row("Water depth (m)", row.get("water_depth")),
                fmt_row("Production start", row.get("production_start")),
            ]
        elif layer_key == "port_traffic":
            title = row.get("port", "Port")
            rows = [
                fmt_row("Port", row.get("port")),
                fmt_row("Country", row.get("country")),
                fmt_row("Year", row.get("year")),
                fmt_row("Vessel count", row.get("nofvessels")),
                fmt_row("Gross tonnage (kt)", row.get("gross_tonnage__gt_thousand")),
                fmt_row("Tonnage size class", row.get("tonnagesize")),
            ]
        elif layer_key == "sedimentation":
            title = row.get("site", "Sedimentation site")
            rows = [
                fmt_row("Site", row.get("site")),
                fmt_row("Country", row.get("country")),
                fmt_row("Sea area", row.get("sea_area")),
                fmt_row("Depth (m)", row.get("depth")),
                fmt_row("Sedimentation rate", row.get("sedimentation_rate")),
                fmt_row("Dating method", row.get("dating_method")),
                fmt_row("Substrate", row.get("substrate")),
                fmt_row("Reference", row.get("reference")),
            ]
        elif layer_key == "coastal_resilience":
            title = f"CVI: {row.get('name_closest', row.get('id', ''))}"
            rows = [
                fmt_row("Location", row.get("name_closest")),
                fmt_row("CVI score", row.get("cvi")),
                fmt_row("Notes", row.get("notes_closest")),
            ]
        else:
            title = row.get("name", "Windfarm")
            rows = [
                fmt_row("Name", row.get("name")),
                fmt_row("Country", row.get("country")),
                fmt_row("Status", row.get("status")),
                fmt_row("Power MW", row.get("power_mw")),
                fmt_row("Year", row.get("year")),
            ]

        body = "".join(r for r in rows if r)
        popup = (
            f"<div style='font-family:system-ui,sans-serif;font-size:12.5px;max-width:320px'>"
            f"<div style='font-weight:600;font-size:13.5px;margin-bottom:4px'>{title}</div>"
            f"<table style='border-collapse:collapse'>{body}</table></div>"
        )
        folium.CircleMarker(
            location=(float(row[lat_col]), float(row[lon_col])),
            radius=style["radius"],
            color=style["color"],
            weight=1,
            fill=True,
            fill_color=style["color"],
            fill_opacity=0.75,
            tooltip=str(title),
            popup=folium.Popup(popup, max_width=360),
        ).add_to(fg)

    fg.add_to(fmap)
    return len(df)


def add_massimal_layer(fmap: folium.Map, path: Path) -> int:
    if not path.exists():
        print(f"  warning: MASSIMAL manifest not found: {path}")
        return 0
    manifest = json.loads(path.read_text(encoding="utf-8"))
    sites = manifest.get("known_field_sites") or {}
    if not sites:
        return 0

    style = CONTEXT_POINT_STYLE["massimal"]
    fg = folium.FeatureGroup(name=f"MASSIMAL remote-sensing field sites ({len(sites):,})", show=False)
    for name, coords in sorted(sites.items()):
        if not coords or len(coords) < 2:
            continue
        lat, lon = float(coords[0]), float(coords[1])
        rows = [
            fmt_row("Project", "MASSIMAL"),
            fmt_row("Field site", name),
            fmt_row("Focus", "Drone hyperspectral mapping of algae/seagrass habitats"),
            fmt_row("Source", "MASSIMAL GitHub/project metadata"),
        ]
        popup = (
            f"<div style='font-family:system-ui,sans-serif;font-size:12.5px;max-width:320px'>"
            f"<div style='font-weight:600;font-size:13.5px;margin-bottom:4px'>{name}</div>"
            f"<table style='border-collapse:collapse'>{''.join(rows)}</table></div>"
        )
        folium.CircleMarker(
            location=(lat, lon),
            radius=style["radius"],
            color=style["color"],
            weight=1.5,
            fill=True,
            fill_color=style["color"],
            fill_opacity=0.82,
            tooltip=f"MASSIMAL field site: {name}",
            popup=folium.Popup(popup, max_width=360),
        ).add_to(fg)
    fg.add_to(fmap)
    return len(sites)


def add_fishing_heatmap_layer(
    fmap: folium.Map,
    path: Path,
    layer_key: str,
    name: str,
    lat_col: str = "lat",
    lon_col: str = "lon",
    weight_col: str | None = "mw_fshn",
    bbox: dict | None = None,
) -> int:
    if not path.exists():
        print(f"  warning: fishing heatmap CSV not found: {path}")
        return 0
    df = pd.read_csv(path)
    df = df.dropna(subset=[lat_col, lon_col]).copy()
    if bbox:
        df = df[
            (df[lat_col] >= bbox["lat_min"]) & (df[lat_col] <= bbox["lat_max"]) &
            (df[lon_col] >= bbox["lon_min"]) & (df[lon_col] <= bbox["lon_max"])
        ].copy()
    if weight_col and weight_col in df.columns:
        w = pd.to_numeric(df[weight_col], errors="coerce").fillna(0).clip(lower=0)
        cap = w.quantile(0.95) or 1.0
        weights = (w / cap).clip(upper=1.0).tolist()
        data = list(zip(df[lat_col].astype(float), df[lon_col].astype(float), weights))
    else:
        data = list(zip(df[lat_col].astype(float), df[lon_col].astype(float)))
    fg = folium.FeatureGroup(name=f"{name} ({len(df):,})", show=False)
    HeatMap(
        data,
        min_opacity=0.2,
        radius=20,
        blur=18,
        gradient={0.35: "#fed976", 0.6: "#fd8d3c", 0.8: "#f03b20", 1.0: "#bd0026"},
    ).add_to(fg)
    fg.add_to(fmap)
    return len(df)


def add_port_traffic_layer(
    fmap: folium.Map,
    path: Path,
    country_filter: str = "NO",
    bbox: dict | None = None,
) -> int:
    if not path.exists():
        print(f"  warning: port traffic CSV not found: {path}")
        return 0
    df = pd.read_csv(path)
    parsed = df["the_geom"].apply(lambda g: pd.Series(parse_point_wkt(g), index=["_lat", "_lon"]))
    df["_lat"] = parsed["_lat"]
    df["_lon"] = parsed["_lon"]
    if country_filter and "country" in df.columns:
        df = df[df["country"].astype(str).str.upper() == country_filter.upper()].copy()
    df = df.dropna(subset=["_lat", "_lon"]).copy()
    if bbox:
        df = df[
            (df["_lat"] >= bbox["lat_min"]) & (df["_lat"] <= bbox["lat_max"]) &
            (df["_lon"] >= bbox["lon_min"]) & (df["_lon"] <= bbox["lon_max"])
        ].copy()
    if df.empty:
        return 0
    df["nofvessels"] = pd.to_numeric(df["nofvessels"], errors="coerce").fillna(0)
    df["gross_tonnage__gt_thousand"] = pd.to_numeric(df["gross_tonnage__gt_thousand"], errors="coerce").fillna(0)
    agg = df.groupby(["port", "_lat", "_lon"], as_index=False).agg(
        total_vessels=("nofvessels", "sum"),
        total_gt=("gross_tonnage__gt_thousand", "sum"),
        year_min=("year", "min"),
        year_max=("year", "max"),
    )
    cap = agg["total_vessels"].quantile(0.9) or 1.0
    style_color = CONTEXT_POINT_STYLE["port_traffic"]["color"]
    fg = folium.FeatureGroup(name=f"Port vessel traffic: Norway ({len(agg):,} ports)", show=False)
    for _, row in agg.iterrows():
        radius = 5 + 14 * min(float(row["total_vessels"]) / cap, 1.0)
        years = (f"{int(row['year_min'])}–{int(row['year_max'])}"
                 if row["year_min"] != row["year_max"] else str(int(row["year_min"])))
        vessels_str = f"{int(row['total_vessels']):,}"
        gt_str = f"{row['total_gt']:.0f}"
        popup_html = (
            f"<div style='font-family:system-ui,sans-serif;font-size:12.5px;max-width:300px'>"
            f"<div style='font-weight:600;font-size:13.5px;margin-bottom:4px'>{row['port']}</div>"
            f"<table style='border-collapse:collapse'>"
            f"{fmt_row('Total vessels', vessels_str)}"
            f"{fmt_row('Total GT (kt)', gt_str)}"
            f"{fmt_row('Years covered', years)}"
            f"</table></div>"
        )
        folium.CircleMarker(
            location=(float(row["_lat"]), float(row["_lon"])),
            radius=radius,
            color=style_color,
            weight=1.5,
            fill=True,
            fill_color=style_color,
            fill_opacity=0.65,
            tooltip=f"{row['port']}: {int(row['total_vessels']):,} vessels",
            popup=folium.Popup(popup_html, max_width=340),
        ).add_to(fg)
    fg.add_to(fmap)
    return len(agg)


def add_sedimentation_layer(fmap: folium.Map, path: Path, bbox: dict | None = None) -> int:
    if not path.exists():
        print(f"  warning: sedimentation CSV not found: {path}")
        return 0
    df = pd.read_csv(path)
    df = df[df["country"].astype(str).str.lower() == "norway"].copy()
    df = df.dropna(subset=["latitude", "longitude"]).copy()
    if bbox:
        df = df[
            (df["latitude"] >= bbox["lat_min"]) & (df["latitude"] <= bbox["lat_max"]) &
            (df["longitude"] >= bbox["lon_min"]) & (df["longitude"] <= bbox["lon_max"])
        ].copy()
    if df.empty:
        return 0
    df["sed_rate"] = pd.to_numeric(df["sedimentation_rate"], errors="coerce")
    vmin = df["sed_rate"].quantile(0.05)
    vmax = df["sed_rate"].quantile(0.95)
    cmap = LinearColormap(["#ffffcc", "#a1dab4", "#41b6c4", "#225ea8"], vmin=vmin or 0, vmax=vmax or 1)
    fg = folium.FeatureGroup(name=f"Sedimentation rates: Norway ({len(df):,})", show=False)
    for _, row in df.iterrows():
        rate = row.get("sed_rate")
        color = cmap(float(rate)) if pd.notna(rate) else NO_DATA_GREY
        popup_html = (
            f"<div style='font-family:system-ui,sans-serif;font-size:12.5px;max-width:300px'>"
            f"<div style='font-weight:600;font-size:13.5px;margin-bottom:4px'>"
            f"{row.get('site', 'Sedimentation site')}</div>"
            f"<table style='border-collapse:collapse'>"
            f"{fmt_row('Sea area', row.get('sea_area'))}"
            f"{fmt_row('Depth (m)', row.get('depth'))}"
            f"{fmt_row('Sedimentation rate', row.get('sedimentation_rate'))}"
            f"{fmt_row('Dating method', row.get('dating_method'))}"
            f"{fmt_row('Substrate', row.get('substrate'))}"
            f"{fmt_row('Reference', row.get('reference'))}"
            f"</table></div>"
        )
        folium.CircleMarker(
            location=(float(row["latitude"]), float(row["longitude"])),
            radius=6,
            color=color,
            weight=1.5,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            tooltip=f"Sedimentation: {row.get('sedimentation_rate', 'N/A')} ({row.get('site', '')})",
            popup=folium.Popup(popup_html, max_width=340),
        ).add_to(fg)
    fg.add_to(fmap)
    return len(df)


CVI_COLORS = {
    "Lower":        "#1a9850",
    "Intermediate": "#fd8d3c",
    "Higher":       "#d73027",
    "No data":      NO_DATA_GREY,
}


def add_cvi_layer(fmap: folium.Map, path: Path, bbox: dict | None = None) -> int:
    if not path.exists():
        print(f"  warning: coastal resilience CSV not found: {path}")
        return 0
    df = pd.read_csv(path)
    parsed = df["geom"].apply(lambda g: pd.Series(parse_point_wkt(g), index=["_lat", "_lon"]))
    df["_lat"] = parsed["_lat"]
    df["_lon"] = parsed["_lon"]
    df = df.dropna(subset=["_lat", "_lon"]).copy()
    # Keep only Norway-sourced rows (Aunan & Romstad 2008 Norway study); drop No data and foreign datasets
    df = df[
        (df["cvi"] != "No data") &
        df["name_closest"].str.contains("Aunan|Norway", case=False, na=False)
    ].copy()
    # Tight Norwegian mainland coast bbox
    df = df[
        (df["_lat"] >= 57.0) & (df["_lat"] <= 72.0) &
        (df["_lon"] >= 4.0) & (df["_lon"] <= 32.0)
    ].copy()
    if df.empty:
        return 0
    fg = folium.FeatureGroup(name=f"Coastal resilience/vulnerability index ({len(df):,})", show=False)
    for _, row in df.iterrows():
        cvi_label = str(row.get("cvi", "")).strip()
        color = CVI_COLORS.get(cvi_label, NO_DATA_GREY)
        popup_html = (
            f"<div style='font-family:system-ui,sans-serif;font-size:12.5px;max-width:280px'>"
            f"<div style='font-weight:600;font-size:13.5px;margin-bottom:4px'>"
            f"CVI: {cvi_label}</div>"
            f"<table style='border-collapse:collapse'>"
            f"{fmt_row('Location', row.get('name_closest'))}"
            f"{fmt_row('Notes', row.get('notes_closest'))}"
            f"</table></div>"
        )
        folium.CircleMarker(
            location=(float(row["_lat"]), float(row["_lon"])),
            radius=5,
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            tooltip=f"CVI: {cvi_label} — {row.get('name_closest', '')}",
            popup=folium.Popup(popup_html, max_width=320),
        ).add_to(fg)
    fg.add_to(fmap)
    return len(df)


def add_seabed_erosion_layer(fmap: folium.Map, path: Path, bbox: dict | None = None) -> int:
    """Add seabed erosion multipolygons parsed from WKT."""
    if not path.exists():
        print(f"  warning: seabed erosion CSV not found: {path}")
        return 0
    try:
        from shapely import wkt as shapely_wkt
        from shapely.geometry import mapping
        HAS_SHAPELY = True
    except ImportError:
        HAS_SHAPELY = False

    df = pd.read_csv(path)
    features = []
    for _, row in df.iterrows():
        geom_str = row.get("geom")
        if not isinstance(geom_str, str):
            continue
        # Filter by bbox keyword in sea_area
        sea_area = str(row.get("sea_area", "")).lower()
        if bbox and "atlantic" not in sea_area and "norwegian" not in sea_area and "barents" not in sea_area:
            if "baltic" in sea_area:
                continue  # skip purely Baltic entries

        props = {
            "sea_area": row.get("sea_area"),
            "seabed_dynamics": row.get("seabed_dynamics"),
            "substrate_type": row.get("substrate_type"),
            "description": row.get("description"),
            "water_depth_range": row.get("water_depth_range"),
            "erosion_continuity": row.get("erosion_continuity"),
        }

        if HAS_SHAPELY:
            try:
                geom = shapely_wkt.loads(geom_str)
                features.append({"type": "Feature", "geometry": mapping(geom), "properties": props})
            except Exception:
                continue
        else:
            # Fallback: skip if shapely not available
            continue

    if not features:
        print("  warning: no seabed erosion features parsed (install shapely if missing)")
        return 0

    geojson = {"type": "FeatureCollection", "features": features}
    fg = folium.FeatureGroup(name=f"Seabed erosion areas ({len(features):,})", show=False)
    folium.GeoJson(
        geojson,
        style_function=lambda _: {
            "fillColor": "#8B4513",
            "color": "#5C2D0A",
            "weight": 1.2,
            "fillOpacity": 0.25,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["sea_area", "seabed_dynamics", "substrate_type", "water_depth_range"],
            aliases=["Sea area", "Seabed dynamics", "Substrate", "Depth range"],
            sticky=False,
        ),
        popup=folium.GeoJsonPopup(
            fields=["sea_area", "seabed_dynamics", "substrate_type", "description", "water_depth_range"],
            aliases=["Sea area", "Seabed dynamics", "Substrate", "Description", "Depth range"],
            max_width=360,
        ),
    ).add_to(fg)
    fg.add_to(fmap)
    return len(features)


def add_fish_habitat_layer(fmap: folium.Map, path: Path, bbox: dict | None = None) -> int:
    """Add fish habitat suitability as a HeatMap (mean probability across species)."""
    if not path.exists():
        print(f"  warning: fish habitat CSV not found: {path}")
        return 0
    df = pd.read_csv(path, low_memory=False)
    # Drop header row (first row has column-name strings as values)
    df = df[df["latitude"].apply(lambda v: str(v).replace('.','',1).lstrip('-').isdigit())].copy()
    df["_lat"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["_lon"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["_prob"] = pd.to_numeric(df["probability_of_occurrence"], errors="coerce")
    df = df.dropna(subset=["_lat", "_lon", "_prob"]).copy()
    if bbox:
        df = df[
            (df["_lat"] >= bbox["lat_min"]) & (df["_lat"] <= bbox["lat_max"]) &
            (df["_lon"] >= bbox["lon_min"]) & (df["_lon"] <= bbox["lon_max"])
        ].copy()
    if df.empty:
        return 0
    # Aggregate: mean probability per grid cell across all species
    agg = df.groupby(["_lat", "_lon"])["_prob"].mean().reset_index()
    heat_data = agg[["_lat", "_lon", "_prob"]].values.tolist()
    fg = folium.FeatureGroup(name=f"Fish habitat suitability: Norwegian waters (heatmap, {len(agg):,} cells)", show=False)
    HeatMap(
        heat_data,
        min_opacity=0.3,
        radius=14,
        blur=18,
        gradient={0.2: "#ffffb2", 0.5: "#fecc5c", 0.75: "#fd8d3c", 1.0: "#e31a1c"},
    ).add_to(fg)
    fg.add_to(fmap)
    return len(agg)


def attach_layer_panels(
    fmap: folium.Map,
    html_inner: str,
    source_links_by_layer: dict[str, list[dict[str, str]]],
    color_layer_names: list[str],
) -> None:
    source_links_json = json.dumps(source_links_by_layer, ensure_ascii=False)
    color_layer_names_json = json.dumps(color_layer_names, ensure_ascii=False)
    template = (
        "{% macro html(this, kwargs) %}\n"
        '<div id="dynamic-legend" style="position: fixed; bottom: 20px; left: 20px; z-index: 9999;'
        ' background: rgba(255,255,255,0.96); padding: 10px 12px;'
        ' border: 1px solid #888; border-radius: 6px;'
        ' font-family: system-ui, -apple-system, sans-serif; font-size: 12px;'
        ' max-width: 300px; max-height: calc(100vh - 70px); overflow-y: auto;'
        ' box-shadow: 0 1px 4px rgba(0,0,0,0.15);">'
        + html_inner +
        "</div>\n"
        '<div id="source-panel" style="position: fixed; bottom: 20px; right: 12px; z-index: 9998;'
        ' background: rgba(255,255,255,0.97); padding: 9px 11px;'
        ' border: 1px solid #888; border-radius: 6px;'
        ' font-family: system-ui, -apple-system, sans-serif; font-size: 12px;'
        ' width: 300px; max-height: 45vh; overflow-y: auto;'
        ' box-shadow: 0 1px 4px rgba(0,0,0,0.15); display:none;"></div>\n'
        "<script>\n"
        "(function() {\n"
        f"  const sourceLinksByLayer = {source_links_json};\n"
        f"  const colorLayerSet = new Set({color_layer_names_json});\n"
        "  const activeLayers = new Set();\n"
        "  let suppressMutex = false;\n"
        "  function esc(value) {\n"
        "    return String(value == null ? '' : value)\n"
        "      .replace(/&/g, '&amp;').replace(/</g, '&lt;')\n"
        "      .replace(/>/g, '&gt;').replace(/\"/g, '&quot;')\n"
        "      .replace(/'/g, '&#39;');\n"
        "  }\n"
        "  function nameOfInput(input) {\n"
        "    const label = input.parentElement;\n"
        "    if (label && label.dataset && label.dataset.fullName) return label.dataset.fullName;\n"
        "    const span = label && label.querySelector('span');\n"
        "    return span ? span.textContent.replace(/^\\s+|\\s+$/g, '') : '';\n"
        "  }\n"
        "  function renderPanels() {\n"
        "    const legend = document.getElementById('dynamic-legend');\n"
        "    const sourcePanel = document.getElementById('source-panel');\n"
        "    if (!legend || !sourcePanel) return;\n"
        "    const entries = Array.prototype.slice.call(legend.querySelectorAll('[data-layer]'));\n"
        "    let visibleCount = 0;\n"
        "    entries.forEach(function(entry) {\n"
        "      const show = activeLayers.has(entry.getAttribute('data-layer'));\n"
        "      entry.style.display = show ? '' : 'none';\n"
        "      if (show) visibleCount += 1;\n"
        "    });\n"
        "    const empty = legend.querySelector('[data-empty-legend]');\n"
        "    if (empty) empty.style.display = visibleCount ? 'none' : '';\n"
        "    const orderedActive = Array.from(activeLayers).filter(function(name) {\n"
        "      return (sourceLinksByLayer[name] || []).length > 0;\n"
        "    });\n"
        "    if (!orderedActive.length) {\n"
        "      sourcePanel.style.display = 'none';\n"
        "      sourcePanel.innerHTML = '';\n"
        "      return;\n"
        "    }\n"
        "    sourcePanel.style.display = '';\n"
        "    const blocks = orderedActive.map(function(layerName) {\n"
        "      const links = sourceLinksByLayer[layerName] || [];\n"
        "      if (!links.length) return '';\n"
        "      const primary = links[0];\n"
        "      const extras = links.slice(1);\n"
        "      let html = '<div style=\"margin:8px 0 4px;border-top:1px solid #eee;padding-top:6px\">' +\n"
        "        '<div style=\"font-weight:700;font-size:11px;color:#0a58ca;text-transform:uppercase;letter-spacing:.02em;line-height:1.3\">' + esc(layerName) + '</div>' +\n"
        "        '<div style=\"font-size:11.5px;line-height:1.45;margin-top:3px\">' +\n"
        "        esc(primary.label) +\n"
        "        ' <a href=\"' + esc(primary.url) + '\" target=\"_blank\" rel=\"noopener noreferrer\"' +\n"
        "        ' style=\"color:#0a58ca;text-decoration:none;font-weight:700;white-space:nowrap;margin-left:4px\">(Source)</a>' +\n"
        "        '</div>';\n"
        "      if (primary.note) {\n"
        "        html += '<div style=\"font-size:11px;color:#666;line-height:1.35\">' + esc(primary.note) + '</div>';\n"
        "      }\n"
        "      if (extras.length) {\n"
        "        html += '<div style=\"font-size:11px;color:#666;margin-top:3px\">Also: ' +\n"
        "          extras.map(function(link) {\n"
        "            return '<a href=\"' + esc(link.url) + '\" target=\"_blank\" rel=\"noopener noreferrer\"' +\n"
        "              ' style=\"color:#0a58ca;text-decoration:none\">' + esc(link.label) + '</a>';\n"
        "          }).join(' &middot; ') + '</div>';\n"
        "      }\n"
        "      html += '</div>';\n"
        "      return html;\n"
        "    }).filter(Boolean).join('');\n"
        "    sourcePanel.innerHTML = '<div style=\"font-weight:700;font-size:13px;margin-bottom:2px\">Sources for active layers</div>' +\n"
        "      '<div style=\"font-size:10.5px;color:#888;margin-bottom:4px\">Click <b>(Source)</b> to open the dataset / publication.</div>' +\n"
        "      blocks;\n"
        "  }\n"
        "  function findOverlayInputs() {\n"
        "    const overlayContainer = document.querySelector('.leaflet-control-layers-overlays');\n"
        "    if (!overlayContainer) return [];\n"
        "    return Array.prototype.slice.call(overlayContainer.querySelectorAll('input[type=\"checkbox\"]'));\n"
        "  }\n"
        "  function syncFromInputs(inputs) {\n"
        "    activeLayers.clear();\n"
        "    inputs.forEach(function(input) {\n"
        "      if (input.checked) activeLayers.add(nameOfInput(input));\n"
        "    });\n"
        "  }\n"
        "  function enforceColorMutex(triggeredInput, inputs) {\n"
        "    if (suppressMutex) return;\n"
        "    const triggeredName = nameOfInput(triggeredInput);\n"
        "    if (!colorLayerSet.has(triggeredName)) return;\n"
        "    if (!triggeredInput.checked) return;\n"
        "    suppressMutex = true;\n"
        "    inputs.forEach(function(other) {\n"
        "      if (other === triggeredInput) return;\n"
        "      if (!other.checked) return;\n"
        "      const otherName = nameOfInput(other);\n"
        "      if (colorLayerSet.has(otherName)) {\n"
        "        other.click();\n"
        "      }\n"
        "    });\n"
        "    suppressMutex = false;\n"
        "  }\n"
        "  function injectGroupCSS() {\n"
        "    if (document.getElementById('overlay-group-style')) return;\n"
        "    const style = document.createElement('style');\n"
        "    style.id = 'overlay-group-style';\n"
        "    style.textContent =\n"
        "      '.leaflet-control-layers-overlays div.overlay-group { margin: 2px 0; }' +\n"
        "      '.leaflet-control-layers-overlays div.overlay-group > .overlay-group-header {' +\n"
        "      ' cursor: pointer; padding: 3px 4px; font-weight: 600; color: #0a58ca;' +\n"
        "      ' user-select: none; border-top: 1px solid #e5e5e5; line-height:1.3; }' +\n"
        "      '.leaflet-control-layers-overlays div.overlay-group > .overlay-group-header::before {' +\n"
        "      ' content: \"\\\\25B8\"; display: inline-block; margin-right: 5px; transition: transform .15s;' +\n"
        "      ' transform-origin: center; }' +\n"
        "      '.leaflet-control-layers-overlays div.overlay-group[data-open=\"true\"] > .overlay-group-header::before { transform: rotate(90deg); }' +\n"
        "      '.leaflet-control-layers-overlays div.overlay-group > label { display: block; padding-left: 18px; }' +\n"
        "      '.leaflet-control-layers-overlays div.overlay-group > .overlay-group-hint {' +\n"
        "      ' font-size: 10.5px; color: #888; padding: 0 4px 3px 18px; line-height: 1.3; }' +\n"
        "      '.leaflet-control-layers-overlays div.overlay-group:not([data-open=\"true\"]) > label,' +\n"
        "      ' .leaflet-control-layers-overlays div.overlay-group:not([data-open=\"true\"]) > .overlay-group-hint { display: none; }';\n"
        "    document.head.appendChild(style);\n"
        "  }\n"
        "  function buildOverlayGroups(overlayContainer) {\n"
        "    const groups = [\n"
        "      { prefix: 'Color: ', title: 'Color (marker color)',\n"
        "        hint: 'Choose how site markers are colored. Only one Color layer can be on at a time.' },\n"
        "      { prefix: 'Co-location: ', title: 'Co-location classification',\n"
        "        hint: 'Mapped HB19 polygons classified by pressure / protection / study coverage.' }\n"
        "    ];\n"
        "    groups.forEach(function(group) {\n"
        "      const childLabels = Array.prototype.slice.call(overlayContainer.children)\n"
        "        .filter(function(child) {\n"
        "          if (child.tagName !== 'LABEL') return false;\n"
        "          const span = child.querySelector('span');\n"
        "          const text = span ? span.textContent.replace(/^\\s+|\\s+$/g, '') : '';\n"
        "          return text.indexOf(group.prefix) === 0;\n"
        "        });\n"
        "      if (!childLabels.length) return;\n"
        "      const wrap = document.createElement('div');\n"
        "      wrap.className = 'overlay-group';\n"
        "      const anyChecked = childLabels.some(function(l) {\n"
        "        const inp = l.querySelector('input[type=\"checkbox\"]');\n"
        "        return inp && inp.checked;\n"
        "      });\n"
        "      wrap.setAttribute('data-open', anyChecked ? 'true' : 'false');\n"
        "      const header = document.createElement('div');\n"
        "      header.className = 'overlay-group-header';\n"
        "      header.setAttribute('role', 'button');\n"
        "      header.setAttribute('tabindex', '0');\n"
        "      header.textContent = group.title + ' (' + childLabels.length + ')';\n"
        "      function toggleOpen(e) {\n"
        "        if (e) { e.preventDefault(); e.stopPropagation(); }\n"
        "        const isOpen = wrap.getAttribute('data-open') === 'true';\n"
        "        wrap.setAttribute('data-open', isOpen ? 'false' : 'true');\n"
        "      }\n"
        "      header.addEventListener('click', toggleOpen);\n"
        "      header.addEventListener('keydown', function(e) {\n"
        "        if (e.key === 'Enter' || e.key === ' ') { toggleOpen(e); }\n"
        "      });\n"
        "      wrap.appendChild(header);\n"
        "      if (group.hint) {\n"
        "        const hintEl = document.createElement('div');\n"
        "        hintEl.className = 'overlay-group-hint';\n"
        "        hintEl.textContent = group.hint;\n"
        "        wrap.appendChild(hintEl);\n"
        "      }\n"
        "      overlayContainer.insertBefore(wrap, childLabels[0]);\n"
        "      childLabels.forEach(function(label) {\n"
        "        const span = label.querySelector('span');\n"
        "        if (span) {\n"
        "          const fullName = span.textContent.replace(/^\\s+|\\s+$/g, '');\n"
        "          if (!label.dataset.fullName) label.dataset.fullName = fullName;\n"
        "          if (fullName.indexOf(group.prefix) === 0) {\n"
        "            span.textContent = ' ' + fullName.substring(group.prefix.length);\n"
        "          }\n"
        "        }\n"
        "        wrap.appendChild(label);\n"
        "      });\n"
        "    });\n"
        "  }\n"
        "  function init() {\n"
        "    const overlayContainer = document.querySelector('.leaflet-control-layers-overlays');\n"
        "    const inputs = findOverlayInputs();\n"
        "    if (!overlayContainer || !inputs.length) { setTimeout(init, 100); return; }\n"
        "    injectGroupCSS();\n"
        "    buildOverlayGroups(overlayContainer);\n"
        "    inputs.forEach(function(input) {\n"
        "      input.addEventListener('change', function() {\n"
        "        enforceColorMutex(input, inputs);\n"
        "        syncFromInputs(inputs);\n"
        "        renderPanels();\n"
        "      });\n"
        "    });\n"
        "    syncFromInputs(inputs);\n"
        "    renderPanels();\n"
        "  }\n"
        "  if (document.readyState === 'complete') {\n"
        "    init();\n"
        "  } else {\n"
        "    window.addEventListener('load', init);\n"
        "  }\n"
        "})();\n"
        "</script>\n"
        "{% endmacro %}"
    )
    macro = MacroElement()
    macro._template = Template(template)
    fmap.add_child(macro)


def legend_entry(layer_name: str, html_inner: str) -> str:
    layer_attr = html_lib.escape(layer_name, quote=True)
    layer_text = html_lib.escape(layer_name)
    title = (
        f"<div style='font-size:10.5px;font-weight:700;color:#0a58ca;"
        f"text-transform:uppercase;letter-spacing:.02em;margin:8px 0 3px;"
        f"border-top:1px solid #eee;padding-top:6px;line-height:1.3'>"
        f"{layer_text}</div>"
    )
    return (
        f"<div class='legend-entry' data-layer='{layer_attr}' style='display:none'>"
        f"{title}{html_inner}</div>"
    )


def shape_legend_html() -> str:
    return (
        "<div style='font-weight:600;margin-bottom:4px'>Marker shape = ecosystem</div>"
        "<div style='display:flex;align-items:center;margin:2px 0'>"
        "<span style='display:inline-block;width:13px;height:13px;border-radius:50%;"
        "background:#888;margin-right:6px;border:1px solid #333'></span>"
        "<span>Kelp / macroalgae (●)</span></div>"
        "<div style='display:flex;align-items:center;margin:2px 0'>"
        "<span style='display:inline-block;width:13px;height:13px;"
        "background:#888;margin-right:6px;border:1px solid #333'></span>"
        "<span>Seagrass (■)</span></div>"
    )


def color_region_legend_html(kelp_counts: dict, sea_counts: dict) -> str:
    return region_count_panel(kelp_counts, sea_counts) + "<div style='margin-top:8px'>" + shape_legend_html() + "</div>"


def simple_gradient_legend_html(title: str, colors: list[str], min_label: str, max_label: str, note: str = "") -> str:
    gradient = ", ".join(colors)
    note_html = f"<div style='font-size:11px;color:#777;line-height:1.35'>{note}</div>" if note else ""
    return (
        f"<div style='font-weight:600;margin-bottom:4px'>{title}</div>"
        f"<div style='height:10px;border:1px solid #777;background:linear-gradient(to right,{gradient});"
        f"margin:4px 0'></div>"
        f"<div style='display:flex;justify-content:space-between;font-size:11px;color:#555'>"
        f"<span>{min_label}</span><span>{max_label}</span></div>"
        + note_html
    )


def generic_site_layer_legend_html(title: str, note: str = "") -> str:
    note_html = f"<div style='font-size:11px;color:#777;line-height:1.35'>{note}</div>" if note else ""
    return (
        f"<div style='font-weight:600;margin-bottom:4px'>{title}</div>"
        + shape_legend_html()
        + note_html
    )


def hb19_legend_html(alegras_count: int, tare_count: int) -> str:
    if not alegras_count and not tare_count:
        return ""
    rows = []
    if alegras_count:
        rows.append(
            f"<div style='display:flex;align-items:center;margin:2px 0'>"
            f"<span style='display:inline-block;width:14px;height:9px;background:#31a354;"
            f"opacity:.45;margin-right:6px;border:1px solid #006d2c'></span>"
            f"<span>Eelgrass areas: {alegras_count:,}</span></div>"
        )
    if tare_count:
        rows.append(
            f"<div style='display:flex;align-items:center;margin:2px 0'>"
            f"<span style='display:inline-block;width:14px;height:9px;background:#bf812d;"
            f"opacity:.45;margin-right:6px;border:1px solid #8c510a'></span>"
            f"<span>Kelp forest occurrences: {tare_count:,}</span></div>"
        )
    return (
        "<div style='font-weight:600;margin:8px 0 4px'>Naturbase HB19 polygons</div>"
        + "".join(rows)
        + "<div style='font-size:11px;color:#777;line-height:1.35'>"
        "Fill shade follows Naturbase value class A/B/C."
        "</div>"
    )


def context_legend_html(counts: dict[str, int]) -> str:
    if not any(counts.values()):
        return ""
    rows = []
    for key in (
        "protected_all", "protected_mpa", "akvakultur", "dredging", "platforms", "massimal",
        "bottom_trawls", "bottom_otter_trawls", "bottom_seines",
        "offshore_drilling", "port_traffic",
        "sedimentation", "coastal_resilience", "seabed_erosion", "fish_habitat",
    ):
        count = counts.get(key, 0)
        if not count:
            continue
        if key == "protected_all":
            swatch = "background:#6baed6;opacity:.35;border:1px solid #08519c"
            label = "Marine-relevant protected areas"
        elif key == "protected_mpa":
            swatch = "background:#08519c;opacity:.35;border:1px solid #08306b"
            label = "MPA subset"
        else:
            style = CONTEXT_POINT_STYLE[key]
            swatch = f"background:{style['color']};border-radius:50%;border:1px solid #333"
            label = style["label"]
        rows.append(
            f"<div style='display:flex;align-items:center;margin:2px 0'>"
            f"<span style='display:inline-block;width:12px;height:12px;{swatch};"
            f"margin-right:6px'></span><span>{label}: {count:,}</span></div>"
        )
    return (
        "<div style='font-weight:600;margin:8px 0 4px'>Context / pressure layers</div>"
        + "".join(rows)
        + "<div style='font-size:11px;color:#777;line-height:1.35'>"
          "Point and polygon context layers used as screening covariates."
          "</div>"
    )


def colocation_legend_html(counts: dict[str, int]) -> str:
    if not counts or not any(counts.values()):
        return ""
    rows = []
    for key, meta in COLOCATION_CLASSES.items():
        count = counts.get(key, 0)
        if not count:
            continue
        rows.append(
            f"<div style='display:flex;align-items:flex-start;margin:3px 0;gap:6px'>"
            f"<span style='display:inline-block;flex:0 0 auto;width:14px;height:9px;"
            f"background:{meta['color']};opacity:.65;border:1px solid #555;margin-top:3px'></span>"
            f"<span><b>{meta['label']}</b>: {count:,}<br>"
            f"<span style='color:#666'>{meta['description']}</span></span></div>"
        )
    return (
        "<div style='font-weight:600;margin:8px 0 4px'>Co-location result layers</div>"
        + "".join(rows)
        + "<div style='font-size:11px;color:#777;line-height:1.35'>"
          "These layers classify each mapped HB19 habitat polygon using the spatial join. "
          "Toggle the “Co-location:” layers in the layer control."
          "</div>"
    )


def step2_summary_html() -> str:
    """Text block for the main legend panel summarising Step 2 key numbers."""
    if not STEP2_NATIONAL_PATH.exists() and not STEP2_COBENEFITS_PATH.exists():
        return ""
    rows = []
    if STEP2_NATIONAL_PATH.exists():
        seq = pd.read_csv(STEP2_NATIONAL_PATH)
        for _, r in seq.iterrows():
            ecosystem = str(r.get("ecosystem", "")).title()
            # seagrass: seq_mt_co2_yr; macroalgae: seq_mt_co2_yr (same col)
            co2 = r.get("seq_mt_co2_yr")
            tier = r.get("ipcc_tier", "")
            val_row = None
            if STEP2_VALUATION_PATH.exists():
                val = pd.read_csv(STEP2_VALUATION_PATH)
                eu = val[(val["ecosystem"] == r.get("ecosystem", "")) &
                         (val["price_scenario"] == "EU_ETS_2024_EUR_tCO2")]
                val_row = eu.iloc[0] if not eu.empty else None
            if pd.notna(co2):
                val_str = f" ≈ €{val_row['annual_value_million_usd']:.0f}M/yr (EU ETS)" if val_row is not None else ""
                rows.append(f"<b>{ecosystem}:</b> {float(co2):.4g} Mt CO₂/yr{val_str} [{tier}]")
    if STEP2_COBENEFITS_PATH.exists():
        cob = pd.read_csv(STEP2_COBENEFITS_PATH)
        ni_headline = cob[cob["metric"].astype(str).str.contains(
            "Norwegian Nature Index.*coastal", case=False, na=False
        )]
        if not ni_headline.empty:
            rows.append(f"<b>Coastal NI 2024:</b> {float(ni_headline.iloc[0]['value']):.3f} (0–1 scale)")
        # Highlight the two blue-carbon relevant NI indicators
        alge = cob[cob["metric"].astype(str).str.contains("algeindeks", case=False, na=False)]
        vgr  = cob[cob["metric"].astype(str).str.contains("voksegrense", case=False, na=False)]
        if not alge.empty:
            rows.append(f"NI: Hardbunn algae index = {float(alge.iloc[0]['value']):.3f}")
        if not vgr.empty:
            rows.append(f"NI: Kelp lower growth limit = {float(vgr.iloc[0]['value']):.3f}")
    if not rows:
        return ""
    return (
        "<div style='font-weight:600;margin:8px 0 4px'>Step 2 — Ecosystem services</div>"
        + "".join(f"<div style='font-size:11px;color:#555;line-height:1.5'>{r}</div>" for r in rows)
    )


# Region centroids for Step 2 bubble layer (approximate geographic centres of each
# canonical region as used in the roadmap, placed in open water to avoid overlap
# with site markers).
REGION_CENTROIDS = {
    "Barents Sea":   (71.0, 27.0),
    "Norwegian Sea": (64.5,  7.5),
    "Oslofjord":     (59.5, 10.6),
    "Skagerrak":     (58.1,  7.8),
}


def add_step2_regional_layer(fmap: folium.Map) -> bool:
    """
    Adds a FeatureGroup with one bubble per canonical region showing
    seagrass sediment C-stock statistics from step2_seagrass_stocks_by_region.csv,
    plus a single national-level macroalgae marker from step2_national_sequestration.csv.
    Returns True if the layer was added, False if data files are missing.
    """
    if not STEP2_REGIONAL_PATH.exists() and not STEP2_NATIONAL_PATH.exists():
        return False

    fg = folium.FeatureGroup(name="Step 2: Carbon stocks by region", show=False)

    # ── Seagrass regional bubbles ────────────────────────────────────────
    if STEP2_REGIONAL_PATH.exists():
        regional = pd.read_csv(STEP2_REGIONAL_PATH)
        all_stocks = regional["mean_stock_g_m2"].dropna()
        s_min = all_stocks.min() if not all_stocks.empty else 1
        s_max = all_stocks.max() if not all_stocks.empty else 10000

        for _, row in regional.iterrows():
            region = row["canonical_region"]
            centroid = REGION_CENTROIDS.get(region)
            if centroid is None:
                continue
            mean = row.get("mean_stock_g_m2")
            sd   = row.get("sd_stock_g_m2")
            n    = int(row.get("n_sites", 0))
            rmin = row.get("min_stock_g_m2")
            rmax = row.get("max_stock_g_m2")
            color = CANONICAL_REGION_COLORS.get(region, "#888888")

            # Bubble radius proportional to mean stock (log-scaled)
            if pd.notna(mean) and s_max > s_min:
                import math
                frac = (math.log1p(mean) - math.log1p(s_min)) / (math.log1p(s_max) - math.log1p(s_min))
                radius = 10 + 22 * frac
            else:
                radius = 10

            sd_str  = f"± {sd:,.0f}" if pd.notna(sd) else "n/a"
            rng_str = (f"{rmin:,.0f}–{rmax:,.0f}" if pd.notna(rmin) and pd.notna(rmax) else "n/a")
            popup_html = (
                f"<div style='font-family:system-ui,sans-serif;font-size:12.5px;max-width:300px'>"
                f"<div style='font-weight:600;font-size:13px;margin-bottom:4px'>{region}</div>"
                f"<table style='border-collapse:collapse'>"
                f"{fmt_row('Ecosystem', 'Seagrass (Zostera marina)')}"
                f"{fmt_row('Sites (n)', n)}"
                f"{fmt_row('Mean sediment C stock', f'{mean:,.0f} {sd_str} g C/m²' if pd.notna(mean) else 'n/a')}"
                f"{fmt_row('Range', f'{rng_str} g C/m²')}"
                f"{fmt_row('Source', 'Gagnon et al. 2024 / Gundersen et al. 2021')}"
                f"{fmt_row('IPCC tier', 'Tier 2')}"
                f"</table>"
                f"<div style='font-size:11px;color:#777;margin-top:4px'>"
                f"Bubble size ∝ log(mean C stock). National extent: 90 km² (modeled)."
                f"</div></div>"
            )
            folium.CircleMarker(
                location=centroid,
                radius=radius,
                color=color, weight=2,
                fill=True, fill_color=color, fill_opacity=0.35,
                tooltip=f"{region} — seagrass mean C stock: {mean:,.0f} g C/m²" if pd.notna(mean) else region,
                popup=folium.Popup(popup_html, max_width=340),
            ).add_to(fg)

    # ── Macroalgae national marker (Gundersen 2021) ──────────────────────
    if STEP2_NATIONAL_PATH.exists():
        national = pd.read_csv(STEP2_NATIONAL_PATH)
        ma = national[national["ecosystem"] == "macroalgae"]
        if not ma.empty:
            r = ma.iloc[0]
            # Place in Norwegian Sea (covers most of the kelp range)
            lat, lon = 63.8, 6.5
            stock_gg = r.get("stock_gg_c", "")
            seq_mt   = r.get("seq_mt_c_yr", "")
            seq_lo   = r.get("seq_mt_c_yr_ci_low", "")
            seq_hi   = r.get("seq_mt_c_yr_ci_high", "")
            area_km2 = r.get("extent_km2", "")
            popup_html = (
                f"<div style='font-family:system-ui,sans-serif;font-size:12.5px;max-width:320px'>"
                f"<div style='font-weight:600;font-size:13px;margin-bottom:4px'>"
                f"Norwegian kelp forests — national estimate</div>"
                f"<table style='border-collapse:collapse'>"
                f"{fmt_row('Ecosystem', 'Macroalgae (Saccharina latissima + L. hyperborea)')}"
                f"{fmt_row('Forest area', f'{area_km2:,.0f} km² (0–20 m depth, urchin-adjusted)')}"
                f"{fmt_row('Carbon standing stock', f'{stock_gg:,.0f} Gg C (= {float(stock_gg)/1000:.1f} Mt C)')}"
                f"{fmt_row('Annual sequestration', f'{seq_mt} Mt C/yr (CI: {seq_lo}–{seq_hi})')}"
                f"{fmt_row('CO₂ equivalent', f'{float(seq_mt)*44/12:.2f} Mt CO₂/yr')}"
                f"{fmt_row('IPCC tier', r.get('ipcc_tier', 'Tier 2'))}"
                f"{fmt_row('Source', 'Gundersen et al. 2021 (630 scuba transects)')}"
                f"</table>"
                f"<div style='font-size:11px;color:#777;margin-top:4px'>"
                f"Marker placed in Norwegian Sea (covers most kelp range). "
                f"Wide CI reflects uncertainty in sequestration fraction (Krause-Jensen &amp; Duarte 2016)."
                f"</div></div>"
            )
            folium.CircleMarker(
                location=(lat, lon),
                radius=28,
                color="#8c510a", weight=2,
                fill=True, fill_color="#bf812d", fill_opacity=0.30,
                tooltip="Norwegian kelp — national carbon estimate (Gundersen 2021)",
                popup=folium.Popup(popup_html, max_width=360),
            ).add_to(fg)
            # Star-of-David style inner dot to distinguish from site markers
            folium.CircleMarker(
                location=(lat, lon),
                radius=5,
                color="#8c510a", weight=1.5,
                fill=True, fill_color="#8c510a", fill_opacity=0.85,
            ).add_to(fg)

    fg.add_to(fmap)
    return True


def region_count_panel(kelp_counts: dict, sea_counts: dict) -> str:
    header = (
        "<div style='font-weight:600;margin-bottom:4px'>"
        "Sites per canonical region</div>"
        "<div style='display:grid;grid-template-columns:auto auto auto;column-gap:10px;"
        "row-gap:2px;align-items:center'>"
        "<div></div>"
        "<div style='font-size:11px;color:#666;text-align:right'>kelp</div>"
        "<div style='font-size:11px;color:#666;text-align:right'>seagr.</div>"
    )
    rows = []
    for r in CANONICAL_REGIONS:
        k = kelp_counts.get(r, 0)
        s = sea_counts.get(r, 0)
        is_gap = (k == 0 and s == 0)
        opacity = "opacity:0.55" if is_gap else ""
        gap_tag = " (gap)" if is_gap else ""
        rows.append(
            f"<div style='display:flex;align-items:center;{opacity}'>"
            f"<span style='display:inline-block;width:11px;height:11px;border-radius:50%;"
            f"background:{CANONICAL_REGION_COLORS[r]};margin-right:6px;"
            f"border:1px solid #333'></span><span>{r}{gap_tag}</span></div>"
            f"<div style='text-align:right;font-variant-numeric:tabular-nums;{opacity}'>{k}</div>"
            f"<div style='text-align:right;font-variant-numeric:tabular-nums;{opacity}'>{s}</div>"
        )
    return header + "".join(rows) + "</div>"


def source_link(label: str, url: str, note: str = "") -> dict[str, str]:
    item = {"label": label, "url": url}
    if note:
        item["note"] = note
    return item


def study_source_links(include_all_articles: bool = False) -> list[dict[str, str]]:
    links = [
        source_link(
            "Gagnon et al. 2024, Norwegian eelgrass carbon stocks",
            "https://www.nature.com/articles/s41598-024-74760-3",
            "Seagrass site coordinates and carbon-stock observations.",
        ),
        source_link(
            "Gundersen et al. 2021, Norwegian kelp biomass and ecosystem services",
            "https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2021.578629/full",
            "Kelp regional/national synthesis and transect context.",
        ),
    ]
    if include_all_articles:
        sources_path = REPO_ROOT / "data" / "processed" / "norway_blue_carbon_sources.csv"
        if sources_path.exists():
            sources = pd.read_csv(sources_path)
            for _, row in sources.dropna(subset=["source_url"]).iterrows():
                url = str(row.get("source_url", ""))
                label = str(row.get("source_short", "Source"))
                if url.startswith("http"):
                    links.append(source_link(label, url))
    unique = {}
    for link in links:
        unique[(link["label"], link["url"])] = link
    return list(unique.values())


def base_source_links() -> dict[str, list[dict[str, str]]]:
    study = study_source_links()
    all_study = study_source_links(include_all_articles=True)
    hb19 = [
        source_link(
            "Naturbase / Marine naturtyper HB19",
            "https://register.geonorge.no/mottaksordning-innsamling-geodata/marine-naturtyper-hb19",
            "Mapped eelgrass and kelp forest habitat polygons.",
        ),
    ]
    protected = [
        source_link(
            "Geonorge",
            "https://www.geonorge.no/",
            "Catalogue entry point for Norwegian protected-area geodata.",
        ),
        source_link(
            "Miljødirektoratet Naturbase",
            "https://faktaark.naturbase.no/",
            "Protected-area and habitat fact sheets.",
        ),
    ]
    akvakultur = [
        source_link(
            "Fiskeridirektoratet Akvakulturregisteret",
            "https://www.fiskeridir.no/",
            "Norwegian aquaculture register source.",
        ),
        source_link(
            "Akvakulturregisteret API dump",
            "https://api.fiskeridir.no/pub-aqua/api/v1/dump/new-legacy-csv-file",
            "Programmatic CSV endpoint used by the fetch script.",
        ),
    ]
    emodnet = [
        source_link(
            "EMODnet Human Activities",
            "https://emodnet.ec.europa.eu/human-activities",
            "Human-use pressure layers including dredging, platforms, and windfarms.",
        ),
        source_link(
            "EMODnet Human Activities WFS",
            "https://ows.emodnet-humanactivities.eu/geoserver/emodnet/ows",
            "Programmatic service used by the fetch script.",
        ),
    ]
    massimal = [
        source_link(
            "MASSIMAL project",
            "https://en.uit.no/project/massimal",
            "Remote-sensing field-site context.",
        ),
    ]
    step2 = study + [
        source_link(
            "Nordic Blue Carbon Project / TemaNord 2020:541",
            "https://www.norden.org/en/publication/blue-carbon-climate-adaptation-co2-uptake-and-sequestration-carbon-nordic-blue-forests",
            "National and regional blue-carbon synthesis values.",
        ),
        source_link(
            "Norwegian Nature Index data download",
            "https://www.naturindeks.no/DownloadData",
            "Co-benefit and ecological-condition indicators.",
        ),
    ]
    colocation = hb19 + protected + akvakultur + emodnet + study
    return {
        "study": study,
        "all_study": all_study,
        "hb19": hb19,
        "protected": protected,
        "akvakultur": akvakultur,
        "emodnet": emodnet,
        "massimal": massimal,
        "step2": step2,
        "colocation": colocation,
    }


def main() -> None:
    if not KELP_PATH.exists():
        raise SystemExit(f"Input not found: {KELP_PATH}")
    kelp = load_kelp_sites(KELP_PATH)
    sea = load_seagrass_sites(SEAGRASS_PATH)
    if kelp.empty and sea.empty:
        raise SystemExit("No plottable sites for either ecosystem.")

    kelp_n_min, kelp_n_max = (kelp["sample_n"].min(), kelp["sample_n"].max()) if not kelp.empty else (1, 1)
    sea_n_min, sea_n_max = (sea["cores_total"].min(), sea["cores_total"].max()) if not sea.empty else (1, 1)

    canonical_colors = {r: CANONICAL_REGION_COLORS[r] for r in CANONICAL_REGIONS}
    detailed_kelp = categorical_colors(kelp["region_short"]) if not kelp.empty else {}
    source_colors_kelp = categorical_colors(kelp["Source_short"]) if not kelp.empty else {}
    habitat_colors_kelp = categorical_colors(kelp["Habitat_type"]) if not kelp.empty else {}
    detailed_sea = categorical_colors(sea["region_orig"]) if not sea.empty else {}
    source_colors_sea = categorical_colors(sea["source"]) if not sea.empty else {}

    kelp_counts = kelp["region_canonical"].value_counts().to_dict() if not kelp.empty else {}
    sea_counts = sea["region_canonical"].value_counts().to_dict() if not sea.empty else {}

    year_vals = pd.concat(
        [kelp["year"].dropna() if not kelp.empty else pd.Series(dtype=float),
         sea["year_min"].dropna() if not sea.empty else pd.Series(dtype=float)]
    )
    year_min = int(year_vals.min()) if not year_vals.empty else 2010
    year_max = int(year_vals.max()) if not year_vals.empty else 2024
    year_cmap = LinearColormap(
        ["#2c7fb8", "#7fcdbb", "#edf8b1", "#feb24c", "#f03b20"],
        vmin=year_min, vmax=max(year_max, year_min + 1),
        caption=f"Year ({year_min}–{year_max})",
    )

    # Carbon stock colormap calibrated on seagrass values; kelp shown grey on this layer.
    cstock_max = int(sea["c_stock_mean"].max()) if not sea.empty else 10000
    cstock_cmap = LinearColormap(
        ["#fff7bc", "#fec44f", "#d95f0e", "#7f0000"],
        vmin=0, vmax=max(cstock_max, 1000),
        caption="Mean sediment C stock, g C/m² (seagrass only)",
    )

    all_lats = pd.concat([
        kelp["lat"] if not kelp.empty else pd.Series(dtype=float),
        sea["lat"] if not sea.empty else pd.Series(dtype=float),
    ])
    all_lons = pd.concat([
        kelp["lon"] if not kelp.empty else pd.Series(dtype=float),
        sea["lon"] if not sea.empty else pd.Series(dtype=float),
    ])

    fmap = folium.Map(
        location=[all_lats.mean(), all_lons.mean()],
        zoom_start=5, tiles=None, control_scale=True,
    )
    folium.TileLayer(
        tiles="https://services.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
        attr=(
            'Tiles &copy; Esri &mdash; Sources: GEBCO, NOAA, CHS, OSU, UNH, '
            'CSUMB, National Geographic, DeLorme, NAVTEQ, and Esri'
        ),
        name="Ocean",
        control=False,
    ).add_to(fmap)
    folium.TileLayer(
        tiles="https://services.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Reference/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Ocean Reference",
        name="Ocean labels",
        control=False,
        opacity=0.85,
    ).add_to(fmap)

    hb19_alegras_count = add_hb19_layer(
        fmap,
        HB19_ALEGRAS_PATH,
        "alegras",
        "mapped eelgrass areas",
    )
    hb19_tare_count = add_hb19_layer(
        fmap,
        HB19_TARE_PATH,
        "tare",
        "mapped kelp forest occurrences",
    )
    context_counts = {
        "protected_all": add_protected_area_layer(
            fmap, VERN_ALL_PATH, "marine relevant"
        ),
        "protected_mpa": add_protected_area_layer(
            fmap, VERN_MPA_PATH, "MPA subset"
        ),
        "akvakultur": add_point_csv_layer(
            fmap, AKVAKULTUR_PATH, "akvakultur", "Aquaculture register: marine/saltwater sites"
        ),
        "dredging": add_point_csv_layer(
            fmap, EMODNET_DREDGING_PATH, "dredging", "EMODnet dredging: Norway", country_filter="Norway"
        ),
        "platforms": add_point_csv_layer(
            fmap, EMODNET_PLATFORMS_PATH, "platforms", "EMODnet offshore platforms: Norway"
        ),
        "massimal": add_massimal_layer(fmap, MASSIMAL_MANIFEST_PATH),
        "bottom_trawls": add_fishing_heatmap_layer(
            fmap, BOTTOM_TRAWLS_PATH, "bottom_trawls",
            "Bottom trawl effort: Norwegian waters (heatmap)", bbox=NORWAY_BBOX,
        ),
        "bottom_otter_trawls": add_fishing_heatmap_layer(
            fmap, BOTTOM_OTTER_TRAWLS_PATH, "bottom_otter_trawls",
            "Bottom otter trawl effort: Norwegian waters (heatmap)", bbox=NORWAY_BBOX,
        ),
        "bottom_seines": add_fishing_heatmap_layer(
            fmap, BOTTOM_SEINES_PATH, "bottom_seines",
            "Bottom seine effort: Norwegian waters (heatmap)", bbox=NORWAY_BBOX,
        ),
        "offshore_drilling": add_point_csv_layer(
            fmap, OFFSHORE_DRILLING_PATH, "offshore_drilling",
            "Offshore drilling: Norway", geom_col="the_geom", country_filter="Norway",
        ),
        "port_traffic": add_port_traffic_layer(fmap, PORT_VESSEL_TRAFFIC_PATH, bbox=NORWAY_BBOX),
        "sedimentation": add_sedimentation_layer(fmap, SEDIMENTATION_PATH, bbox=NORWAY_BBOX),
        "coastal_resilience": add_cvi_layer(fmap, COASTAL_RESILIENCE_PATH, bbox=NORWAY_BBOX),
        "seabed_erosion": add_seabed_erosion_layer(fmap, SEABED_EROSION_PATH, bbox=NORWAY_BBOX),
        "fish_habitat": add_fish_habitat_layer(fmap, FISH_HABITAT_PATH, bbox=NORWAY_BBOX),
    }
    colocation_counts = add_colocation_layers(fmap)
    step2_layer_added = add_step2_regional_layer(fmap)

    # NGU modelled organic carbon WMS layers (MapServer, EPSG:4326 supported)
    _NGU_OC_WMS = "https://geo.ngu.no/mapserver/ModellertHavbunnsgeologiWMS"
    for _lyr, _name in [
        ("Karbonlager_OK_NS",            "NGU: Sediment OC stocks – North Sea / Skagerrak"),
        ("Karbonlager_OK_sokkel",        "NGU: Sediment OC stocks – Norwegian shelf"),
        ("OrganiskKarbon_akkumulasjonsrate", "NGU: OC accumulation rates – North Sea / Skagerrak"),
        ("OrganiskKarbon_akkumulasjonsrate_sokkel", "NGU: OC accumulation rates – Norwegian shelf"),
    ]:
        folium.WmsTileLayer(
            url=_NGU_OC_WMS,
            name=_name,
            layers=_lyr,
            fmt="image/png",
            transparent=True,
            version="1.3.0",
            show=False,
            attr="© NGU – Norges geologiske undersøkelse",
            opacity=0.7,
        ).add_to(fmap)

    color_layer_names: list[str] = [
        "Color: Ecosystem type",
        "Color: Region (canonical 4)",
        "Color: Region (detailed)",
        "Color: Year",
        "Color: Sediment C stock (seagrass)",
        "Color: Source study",
        "Color: Habitat type",
    ]

    # Default layer: fixed per-ecosystem color (kelp=orange diamond, seagrass=purple square)
    add_color_layer(
        fmap, "Color: Ecosystem type", kelp, sea,
        kelp_color_fn=lambda r: KELP_ECOSYSTEM_COLOR,
        seagrass_color_fn=lambda r: SEAGRASS_ECOSYSTEM_COLOR,
        kelp_n_min=kelp_n_min, kelp_n_max=kelp_n_max,
        sea_n_min=sea_n_min, sea_n_max=sea_n_max, show=True,
    )
    add_color_layer(
        fmap, "Color: Region (canonical 4)", kelp, sea,
        kelp_color_fn=lambda r: canonical_colors.get(r["region_canonical"], NO_DATA_GREY),
        seagrass_color_fn=lambda r: canonical_colors.get(r["region_canonical"], NO_DATA_GREY),
        kelp_n_min=kelp_n_min, kelp_n_max=kelp_n_max,
        sea_n_min=sea_n_min, sea_n_max=sea_n_max, show=False,
    )
    add_color_layer(
        fmap, "Color: Region (detailed)", kelp, sea,
        kelp_color_fn=lambda r: detailed_kelp.get(r["region_short"], NO_DATA_GREY),
        seagrass_color_fn=lambda r: detailed_sea.get(r["region_orig"], NO_DATA_GREY),
        kelp_n_min=kelp_n_min, kelp_n_max=kelp_n_max,
        sea_n_min=sea_n_min, sea_n_max=sea_n_max, show=False,
    )
    add_color_layer(
        fmap, "Color: Year", kelp, sea,
        kelp_color_fn=lambda r: year_cmap(r["year"]) if pd.notna(r.get("year")) else NO_DATA_GREY,
        seagrass_color_fn=lambda r: year_cmap(r["year_min"]) if pd.notna(r.get("year_min")) else NO_DATA_GREY,
        kelp_n_min=kelp_n_min, kelp_n_max=kelp_n_max,
        sea_n_min=sea_n_min, sea_n_max=sea_n_max, show=False,
    )
    add_color_layer(
        fmap, "Color: Sediment C stock (seagrass)", kelp, sea,
        kelp_color_fn=lambda r: NO_DATA_GREY,
        seagrass_color_fn=lambda r: cstock_cmap(r["c_stock_mean"]) if pd.notna(r.get("c_stock_mean")) else NO_DATA_GREY,
        kelp_n_min=kelp_n_min, kelp_n_max=kelp_n_max,
        sea_n_min=sea_n_min, sea_n_max=sea_n_max, show=False,
    )
    add_color_layer(
        fmap, "Color: Source study", kelp, sea,
        kelp_color_fn=lambda r: source_colors_kelp.get(r["Source_short"], NO_DATA_GREY),
        seagrass_color_fn=lambda r: source_colors_sea.get(r["source"], NO_DATA_GREY),
        kelp_n_min=kelp_n_min, kelp_n_max=kelp_n_max,
        sea_n_min=sea_n_min, sea_n_max=sea_n_max, show=False,
    )
    add_color_layer(
        fmap, "Color: Habitat type", kelp, sea,
        kelp_color_fn=lambda r: habitat_colors_kelp.get(r["Habitat_type"], NO_DATA_GREY),
        seagrass_color_fn=lambda r: NO_DATA_GREY,
        kelp_n_min=kelp_n_min, kelp_n_max=kelp_n_max,
        sea_n_min=sea_n_min, sea_n_max=sea_n_max, show=False,
    )

    fmap.fit_bounds([[all_lats.min(), all_lons.min()], [all_lats.max(), all_lons.max()]])
    folium.LayerControl(collapsed=False, position="topright").add_to(fmap)

    source_groups = base_source_links()
    layer_sources: dict[str, list[dict[str, str]]] = {}
    legend_entries: list[str] = []

    def add_layer_metadata(layer_name: str, legend_html: str, source_links: list[dict[str, str]], active: bool = False) -> None:
        legend_entries.append(legend_entry(layer_name, legend_html))
        layer_sources[layer_name] = source_links
        _ = active  # active flag only matters for initial Folium show=True; kept for API compat

    add_layer_metadata(
        "Color: Ecosystem type",
        (
            f"<div style='font-size:11.5px;margin-bottom:4px;font-weight:600'>Ecosystem type</div>"
            f"<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px'>"
            f"<div style='width:13px;height:13px;background:{KELP_ECOSYSTEM_COLOR};"
            f"border:1.5px solid #111;transform:rotate(45deg);flex-shrink:0'></div>"
            f"<span>Kelp / macroalgae ({len(kelp)} sites)</span></div>"
            f"<div style='display:flex;align-items:center;gap:6px'>"
            f"<div style='width:13px;height:13px;background:{SEAGRASS_ECOSYSTEM_COLOR};"
            f"border:1.5px solid #111;flex-shrink:0'></div>"
            f"<span>Seagrass / eelgrass ({len(sea)} sites)</span></div>"
        ),
        source_groups["study"],
        active=True,
    )
    add_layer_metadata(
        "Color: Region (canonical 4)",
        color_region_legend_html(kelp_counts, sea_counts),
        source_groups["study"],
    )
    add_layer_metadata(
        "Color: Region (detailed)",
        generic_site_layer_legend_html(
            "Detailed source regions",
            "Marker color follows the original region labels before four-region normalization.",
        ),
        source_groups["study"],
    )
    add_layer_metadata(
        "Color: Year",
        simple_gradient_legend_html(
            f"Sampling / source year ({year_min}-{year_max})",
            ["#2c7fb8", "#7fcdbb", "#edf8b1", "#feb24c", "#f03b20"],
            str(year_min),
            str(year_max),
            "Kelp uses source year where available; seagrass uses the minimum sampled year.",
        ) + "<div style='margin-top:8px'>" + shape_legend_html() + "</div>",
        source_groups["study"],
    )
    add_layer_metadata(
        "Color: Sediment C stock (seagrass)",
        simple_gradient_legend_html(
            "Mean sediment C stock, g C/m²",
            ["#fff7bc", "#fec44f", "#d95f0e", "#7f0000"],
            "0",
            f"{cstock_max:,}",
            "Seagrass signal only; kelp markers are grey on this layer.",
        ) + "<div style='margin-top:8px'>" + shape_legend_html() + "</div>",
        source_groups["study"],
    )
    add_layer_metadata(
        "Color: Source study",
        generic_site_layer_legend_html(
            "Source study",
            "Marker color distinguishes the source publication or workbook source row.",
        ),
        source_groups["all_study"],
    )
    add_layer_metadata(
        "Color: Habitat type",
        generic_site_layer_legend_html(
            "Habitat type",
            "Kelp marker color follows habitat/substrate class; seagrass is grey here.",
        ),
        source_groups["study"],
    )

    add_layer_metadata(
        f"Naturbase HB19: mapped eelgrass areas ({hb19_alegras_count:,})",
        hb19_legend_html(hb19_alegras_count, 0),
        source_groups["hb19"],
    )
    add_layer_metadata(
        f"Naturbase HB19: mapped kelp forest occurrences ({hb19_tare_count:,})",
        hb19_legend_html(0, hb19_tare_count),
        source_groups["hb19"],
    )

    protected_layer_name = f"Protected areas: marine relevant ({context_counts.get('protected_all', 0):,})"
    mpa_layer_name = f"Protected areas: MPA subset ({context_counts.get('protected_mpa', 0):,})"
    add_layer_metadata(protected_layer_name, context_legend_html({"protected_all": context_counts.get("protected_all", 0)}), source_groups["protected"])
    add_layer_metadata(mpa_layer_name, context_legend_html({"protected_mpa": context_counts.get("protected_mpa", 0)}), source_groups["protected"])

    context_layer_info = [
        ("akvakultur", f"Aquaculture register: marine/saltwater sites ({context_counts.get('akvakultur', 0):,})", source_groups["akvakultur"]),
        ("dredging", f"EMODnet dredging: Norway ({context_counts.get('dredging', 0):,})", source_groups["emodnet"]),
        ("platforms", f"EMODnet offshore platforms: Norway ({context_counts.get('platforms', 0):,})", source_groups["emodnet"]),
        ("massimal", f"MASSIMAL remote-sensing field sites ({context_counts.get('massimal', 0):,})", source_groups["massimal"]),
        ("bottom_trawls", f"Bottom trawl effort: Norwegian waters (heatmap) ({context_counts.get('bottom_trawls', 0):,})", source_groups["emodnet"]),
        ("bottom_otter_trawls", f"Bottom otter trawl effort: Norwegian waters (heatmap) ({context_counts.get('bottom_otter_trawls', 0):,})", source_groups["emodnet"]),
        ("bottom_seines", f"Bottom seine effort: Norwegian waters (heatmap) ({context_counts.get('bottom_seines', 0):,})", source_groups["emodnet"]),
        ("offshore_drilling", f"Offshore drilling: Norway ({context_counts.get('offshore_drilling', 0):,})", source_groups["emodnet"]),
        ("port_traffic", f"Port vessel traffic: Norway ({context_counts.get('port_traffic', 0):,} ports)", source_groups["emodnet"]),
        ("sedimentation", f"Sedimentation rates: Norway ({context_counts.get('sedimentation', 0):,})", source_groups["emodnet"]),
        ("coastal_resilience", f"Coastal resilience/vulnerability index ({context_counts.get('coastal_resilience', 0):,})", source_groups["emodnet"]),
        ("seabed_erosion", f"Seabed erosion areas ({context_counts.get('seabed_erosion', 0):,})", source_groups["emodnet"]),
        ("fish_habitat", f"Fish habitat suitability: Norwegian waters (heatmap, {context_counts.get('fish_habitat', 0):,} cells)", source_groups["emodnet"]),
    ]
    for key, layer_name, sources in context_layer_info:
        add_layer_metadata(layer_name, context_legend_html({key: context_counts.get(key, 0)}), sources)

    for key, meta in COLOCATION_CLASSES.items():
        count = colocation_counts.get(key, 0)
        if not count:
            continue
        layer_name = f"Co-location: {meta['label']} ({count:,})"
        active = key in ("pressure_low_protection", "pressure_and_protected")
        add_layer_metadata(layer_name, colocation_legend_html({key: count}), source_groups["colocation"], active=active)

    if step2_layer_added:
        add_layer_metadata("Step 2: Carbon stocks by region", step2_summary_html(), source_groups["step2"])

    _ngu_sources = [{"label": "NGU ModellertHavbunnsgeologi WMS", "url": _NGU_OC_WMS}]
    _ngu_legend_base = (
        "https://geo.ngu.no/mapserver/ModellertHavbunnsgeologiWMS"
        "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic"
        "&SLD_VERSION=1.1.0&FORMAT=image/png&LAYER="
    )
    _ngu_layer_meta = [
        (
            "Karbonlager_OK_NS",
            "NGU: Sediment OC stocks – North Sea / Skagerrak",
            "Modelled organic carbon (OC) stock in surface sediments — North Sea and Skagerrak.",
            "Units: g C m⁻²",
        ),
        (
            "Karbonlager_OK_sokkel",
            "NGU: Sediment OC stocks – Norwegian shelf",
            "Modelled organic carbon (OC) stock in surface sediments — Norwegian continental shelf.",
            "Units: g C m⁻²",
        ),
        (
            "OrganiskKarbon_akkumulasjonsrate",
            "NGU: OC accumulation rates – North Sea / Skagerrak",
            "Modelled organic carbon accumulation rate in sediments — North Sea and Skagerrak.",
            "Units: g C m⁻² yr⁻¹",
        ),
        (
            "OrganiskKarbon_akkumulasjonsrate_sokkel",
            "NGU: OC accumulation rates – Norwegian shelf",
            "Modelled organic carbon accumulation rate in sediments — Norwegian continental shelf.",
            "Units: g C m⁻² yr⁻¹",
        ),
    ]
    for _lyr, _name, _desc, _units in _ngu_layer_meta:
        _legend_url = _ngu_legend_base + _lyr
        _html = (
            f"<div style='font-size:11.5px;font-weight:600;margin-bottom:3px'>{_name}</div>"
            f"<div style='font-size:11px;color:#444;margin-bottom:6px;line-height:1.4'>"
            f"{_desc}<br><strong>{_units}</strong></div>"
            f"<img src='{_legend_url}' alt='NGU legend' "
            f"style='max-width:160px;border:1px solid #ddd;border-radius:3px' "
            f"onerror=\"this.replaceWith(document.createTextNode('Legend unavailable (requires internet)'))\">"
            f"<div style='font-size:10.5px;color:#777;margin-top:4px;line-height:1.3'>"
            f"Source: Norges geologiske undersøkelse (NGU). "
            f"Tiles and legend load from NGU server — requires internet access.</div>"
        )
        add_layer_metadata(_name, _html, _ngu_sources)

    legend_inner = (
        f"<div style='font-weight:700;font-size:13px;margin-bottom:4px'>"
        f"Norway blue-carbon study sites</div>"
        f"<div style='color:#444;margin-bottom:8px;font-size:11.5px'>"
        f"Kelp: {len(kelp)} sites · Seagrass: {len(sea)} sites · "
        f"Click any marker for details. Legend and sources follow active layers."
        f"</div>"
        + "<div data-empty-legend style='font-size:11px;color:#777;line-height:1.35'>"
          "Turn on one or more overlay layers in the top-right control to show the relevant legend."
          "</div>"
        + "".join(legend_entries)
        + "<div style='color:#888;font-size:11px;margin-top:8px;line-height:1.4'>"
          "Canonical regions per Gagnon et al. 2024.<br>"
          "Source links update in the bottom-right Sources panel.</div>"
    )
    attach_layer_panels(fmap, legend_inner, layer_sources, color_layer_names)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(OUT_PATH))
    print(
        f"Wrote {OUT_PATH}\n"
        f"  Kelp sites:     {len(kelp)}\n"
        f"  Seagrass sites: {len(sea)}\n"
        f"  HB19 eelgrass polygons: {hb19_alegras_count}\n"
        f"  HB19 kelp polygons:     {hb19_tare_count}\n"
        f"  Context layers: {context_counts}\n"
        f"  Co-location layers: {colocation_counts}\n"
        f"  Step 2 regional layer: {'added' if step2_layer_added else 'skipped (data missing)'}\n"
        f"  Region counts (kelp / seagrass):"
    )
    for r in CANONICAL_REGIONS:
        print(f"    {r:<14} {kelp_counts.get(r, 0):>3} / {sea_counts.get(r, 0):>3}")


if __name__ == "__main__":
    main()
