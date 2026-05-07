"""Quantify spatial co-location of Norwegian blue-carbon habitat, protection and pressure.

Inputs:
  - Naturbase HB19 map layers for eelgrass and kelp polygons
  - Miljødirektoratet protected-area map layers
  - EMODnet human-activity points
  - Fiskeridirektoratet aquaculture points
  - compiled master study-site table

Outputs under data/processed/spatial_analysis/:
  - habitat_colocation_metrics.csv
  - habitat_protection_overlaps.csv
  - study_site_habitat_join.csv
  - regional_colocation_summary.csv

This is a first-pass spatial screening. It uses EPSG:32633 for area/distance
calculations, which is a practical Norway-wide approximation for exploration.
For final reporting, consider equal-area projection checks and sensitivity
tests on buffer distances.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "processed" / "spatial_analysis"

HB19_DIR = REPO_ROOT / "data" / "external" / "naturbase_hb19" / "map_layers"
EELGRASS_PATH = HB19_DIR / "naturbase_hb19_alegras_map.geojson"
KELP_PATH = HB19_DIR / "naturbase_hb19_tare_map.geojson"

VERN_DIR = REPO_ROOT / "data" / "external" / "verneomraader" / "map_layers"
PROTECTED_PATH = VERN_DIR / "verneomraader_marine_map.geojson"
MPA_PATH = VERN_DIR / "verneomraader_mpa_map.geojson"

AKVAKULTUR_PATH = REPO_ROOT / "data" / "external" / "akvakultur" / "akvakultur_marine_sites.csv"
EMODNET_DIR = REPO_ROOT / "data" / "external" / "emodnet"
DREDGING_PATH = EMODNET_DIR / "emodnet_dredging.csv"
PLATFORMS_PATH = EMODNET_DIR / "emodnet_platforms.csv"
WINDFARMS_PATH = EMODNET_DIR / "emodnet_windfarms.csv"
MASTER_SITES_PATH = REPO_ROOT / "data" / "processed" / "norway_blue_carbon_master_sites.csv"

OUT_HABITAT_METRICS = OUT_DIR / "habitat_colocation_metrics.csv"
OUT_PROTECTION_OVERLAPS = OUT_DIR / "habitat_protection_overlaps.csv"
OUT_STUDY_JOIN = OUT_DIR / "study_site_habitat_join.csv"
OUT_REGIONAL_SUMMARY = OUT_DIR / "regional_colocation_summary.csv"
OUT_MANIFEST = OUT_DIR / "spatial_colocation_manifest.json"

CRS_WGS84 = "EPSG:4326"
CRS_METERS = "EPSG:32633"
BUFFER_DISTANCES_M = [1000, 5000, 10000]

CANONICAL_REGIONS = ["Barents Sea", "Norwegian Sea", "Oslofjord", "Skagerrak"]


def canonical_region(region_str: str | None, lat: float | None) -> str:
    s = (region_str or "").lower()
    if any(k in s for k in ("barents", "porsanger", "hammerfest", "northern norway", "bodø")):
        return "Barents Sea"
    if "norwegian sea" in s:
        return "Norwegian Sea"
    if "outer oslofjord" in s or "skagerrak" in s:
        return "Skagerrak"
    if "oslofjord" in s:
        return "Oslofjord"
    if any(k in s for k in ("hardanger", "sognef", "mid-norway", "north sea", "southwest norway", "west norway")):
        return "Norwegian Sea"
    if lat is None or pd.isna(lat):
        return "Unknown"
    if lat >= 67:
        return "Barents Sea"
    if lat >= 60:
        return "Norwegian Sea"
    return "Skagerrak"


def read_habitat(path: Path, ecosystem: str, habitat_type: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path).to_crs(CRS_WGS84)
    gdf = gdf.reset_index(drop=True).copy()
    gdf["ecosystem"] = ecosystem
    gdf["habitat_type"] = habitat_type
    gdf["habitat_id"] = [
        f"{ecosystem}_{habitat_type}_{i}_{str(row.get('marinNaturtypeId', 'na'))}"
        for i, row in gdf.iterrows()
    ]
    centroid_lat = gdf.to_crs(CRS_METERS).geometry.centroid.to_crs(CRS_WGS84).y
    gdf["canonical_region"] = centroid_lat.apply(lambda lat: canonical_region(None, lat))
    return gdf


def read_points_csv(
    path: Path,
    layer_name: str,
    lat_col: str = "lat_dd",
    lon_col: str = "lon_dd",
    country_filter: str | None = None,
) -> gpd.GeoDataFrame:
    if not path.exists():
        return gpd.GeoDataFrame(columns=["layer_name", "geometry"], geometry="geometry", crs=CRS_WGS84)
    df = pd.read_csv(path)
    if country_filter and "country" in df.columns:
        df = df[df["country"].astype(str).str.lower() == country_filter.lower()].copy()
    df = df.dropna(subset=[lat_col, lon_col]).copy()
    geometry = [Point(float(lon), float(lat)) for lon, lat in zip(df[lon_col], df[lat_col])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=CRS_WGS84)
    gdf["layer_name"] = layer_name
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


def area_overlap(
    habitat_m: gpd.GeoDataFrame,
    overlay_m: gpd.GeoDataFrame,
    overlay_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if overlay_m.empty:
        empty = pd.DataFrame(columns=["habitat_id", f"{overlay_name}_area_m2"])
        return empty, empty
    inter = gpd.overlay(
        habitat_m[["habitat_id", "geometry"]],
        overlay_m[["geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    if inter.empty:
        summary = pd.DataFrame({"habitat_id": habitat_m["habitat_id"], f"{overlay_name}_area_m2": 0.0})
        return inter, summary
    inter[f"{overlay_name}_area_m2"] = inter.geometry.area
    summary = (
        inter.groupby("habitat_id", as_index=False)[f"{overlay_name}_area_m2"]
        .sum()
    )
    return inter.drop(columns="geometry"), summary


def nearest_distance_m(
    habitat_m: gpd.GeoDataFrame,
    points_m: gpd.GeoDataFrame,
    distance_col: str,
) -> pd.DataFrame:
    if points_m.empty:
        return pd.DataFrame({"habitat_id": habitat_m["habitat_id"], distance_col: pd.NA})
    union = points_m.geometry.union_all()
    return pd.DataFrame(
        {
            "habitat_id": habitat_m["habitat_id"],
            distance_col: habitat_m.geometry.distance(union),
        }
    )


def point_counts_within_buffers(
    habitat_m: gpd.GeoDataFrame,
    points_m: gpd.GeoDataFrame,
    prefix: str,
) -> pd.DataFrame:
    out = pd.DataFrame({"habitat_id": habitat_m["habitat_id"]})
    if points_m.empty:
        for dist in BUFFER_DISTANCES_M:
            out[f"{prefix}_within_{dist // 1000}km_n"] = 0
        return out

    points_sindex = points_m.sindex
    for dist in BUFFER_DISTANCES_M:
        counts = []
        for geom in habitat_m.geometry:
            buffered = geom.buffer(dist)
            candidate_idx = list(points_sindex.query(buffered, predicate="intersects"))
            if not candidate_idx:
                counts.append(0)
                continue
            candidates = points_m.iloc[candidate_idx]
            counts.append(int(candidates.geometry.intersects(buffered).sum()))
        out[f"{prefix}_within_{dist // 1000}km_n"] = counts
    return out


def study_site_habitat_join(study: gpd.GeoDataFrame, habitat: gpd.GeoDataFrame) -> pd.DataFrame:
    if study.empty or habitat.empty:
        return pd.DataFrame()
    joined = gpd.sjoin(
        study[["site_id", "site_name", "ecosystem", "canonical_region", "source_short", "geometry"]],
        habitat[["habitat_id", "ecosystem", "habitat_type", "omraadenavn", "marinNaturtypeId", "verdi", "geometry"]],
        how="left",
        predicate="within",
        lsuffix="study",
        rsuffix="habitat",
    )
    joined = joined.drop(columns=["geometry", "index_habitat"], errors="ignore")
    joined = joined.rename(
        columns={
            "ecosystem_study": "study_ecosystem",
            "ecosystem_habitat": "habitat_ecosystem",
            "omraadenavn": "habitat_name",
            "marinNaturtypeId": "naturbase_habitat_id",
            "verdi": "naturbase_value_code",
        }
    )
    return pd.DataFrame(joined)


def add_cols(base: pd.DataFrame, frames: list[pd.DataFrame]) -> pd.DataFrame:
    out = base.copy()
    for frame in frames:
        out = out.merge(frame, on="habitat_id", how="left")
    for col in out.columns:
        if col.endswith("_n") or col.endswith("_area_m2"):
            out[col] = out[col].fillna(0)
    return out


def build_regional_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    aggregations = [
        "habitat_area_m2",
        "protected_area_m2",
        "mpa_area_m2",
        "dredging_within_1km_n",
        "dredging_within_5km_n",
        "dredging_within_10km_n",
        "akvakultur_within_1km_n",
        "akvakultur_within_5km_n",
        "akvakultur_within_10km_n",
        "platforms_within_10km_n",
        "study_sites_within_1km_n",
        "study_sites_within_5km_n",
    ]
    available = {col: "sum" for col in aggregations if col in metrics.columns}
    summary = (
        metrics.groupby(["ecosystem", "canonical_region"], as_index=False)
        .agg({"habitat_id": "count", **available})
        .rename(columns={"habitat_id": "habitat_polygons_n"})
    )
    summary["habitat_area_km2"] = summary["habitat_area_m2"] / 1_000_000
    summary["protected_area_km2"] = summary["protected_area_m2"] / 1_000_000
    summary["mpa_area_km2"] = summary["mpa_area_m2"] / 1_000_000
    summary["percent_habitat_protected"] = (
        summary["protected_area_m2"] / summary["habitat_area_m2"] * 100
    ).where(summary["habitat_area_m2"] > 0)
    summary["percent_habitat_in_mpa"] = (
        summary["mpa_area_m2"] / summary["habitat_area_m2"] * 100
    ).where(summary["habitat_area_m2"] > 0)
    return summary


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    eelgrass = read_habitat(EELGRASS_PATH, "seagrass", "eelgrass")
    kelp = read_habitat(KELP_PATH, "macroalgae", "kelp_forest")
    habitat = pd.concat([eelgrass, kelp], ignore_index=True)
    habitat = gpd.GeoDataFrame(habitat, geometry="geometry", crs=CRS_WGS84)

    protected = gpd.read_file(PROTECTED_PATH).to_crs(CRS_WGS84)
    mpa = gpd.read_file(MPA_PATH).to_crs(CRS_WGS84)
    dredging = read_points_csv(DREDGING_PATH, "dredging", country_filter="Norway")
    akvakultur = read_points_csv(AKVAKULTUR_PATH, "akvakultur")
    platforms = read_points_csv(PLATFORMS_PATH, "platforms")
    windfarms = read_points_csv(WINDFARMS_PATH, "windfarms")
    study_sites = read_study_sites()

    habitat_m = habitat.to_crs(CRS_METERS)
    protected_m = protected.to_crs(CRS_METERS)
    mpa_m = mpa.to_crs(CRS_METERS)
    dredging_m = dredging.to_crs(CRS_METERS)
    akvakultur_m = akvakultur.to_crs(CRS_METERS)
    platforms_m = platforms.to_crs(CRS_METERS)
    windfarms_m = windfarms.to_crs(CRS_METERS)
    study_sites_m = study_sites.to_crs(CRS_METERS)

    base = pd.DataFrame(
        {
            "habitat_id": habitat["habitat_id"],
            "ecosystem": habitat["ecosystem"],
            "habitat_type": habitat["habitat_type"],
            "naturbase_id": habitat.get("marinNaturtypeId"),
            "habitat_name": habitat.get("omraadenavn"),
            "value_code": habitat.get("verdi"),
            "value_label": habitat.get("verdi_label"),
            "municipality": habitat.get("kommune"),
            "canonical_region": habitat["canonical_region"],
            "habitat_area_m2": habitat_m.geometry.area,
            "centroid_lon": habitat_m.geometry.centroid.to_crs(CRS_WGS84).x,
            "centroid_lat": habitat_m.geometry.centroid.to_crs(CRS_WGS84).y,
        }
    )

    protection_inter, protection_summary = area_overlap(habitat_m, protected_m, "protected")
    mpa_inter, mpa_summary = area_overlap(habitat_m, mpa_m, "mpa")

    metrics = add_cols(
        base,
        [
            protection_summary,
            mpa_summary,
            nearest_distance_m(habitat_m, protected_m, "nearest_protected_distance_m"),
            nearest_distance_m(habitat_m, mpa_m, "nearest_mpa_distance_m"),
            nearest_distance_m(habitat_m, dredging_m, "nearest_dredging_distance_m"),
            nearest_distance_m(habitat_m, akvakultur_m, "nearest_akvakultur_distance_m"),
            nearest_distance_m(habitat_m, platforms_m, "nearest_platform_distance_m"),
            nearest_distance_m(habitat_m, windfarms_m, "nearest_windfarm_distance_m"),
            point_counts_within_buffers(habitat_m, dredging_m, "dredging"),
            point_counts_within_buffers(habitat_m, akvakultur_m, "akvakultur"),
            point_counts_within_buffers(habitat_m, platforms_m, "platforms"),
            point_counts_within_buffers(habitat_m, windfarms_m, "windfarms"),
            point_counts_within_buffers(habitat_m, study_sites_m, "study_sites"),
        ],
    )
    metrics["percent_protected"] = (
        metrics["protected_area_m2"] / metrics["habitat_area_m2"] * 100
    ).clip(upper=100)
    metrics["percent_mpa"] = (
        metrics["mpa_area_m2"] / metrics["habitat_area_m2"] * 100
    ).clip(upper=100)

    # A transparent first-pass pressure/protection index for ranking, not final inference.
    metrics["colocation_pressure_index"] = (
        metrics["dredging_within_1km_n"] * 3
        + metrics["dredging_within_5km_n"]
        + metrics["akvakultur_within_1km_n"] * 3
        + metrics["akvakultur_within_5km_n"]
        + metrics["platforms_within_10km_n"]
        + metrics["windfarms_within_10km_n"]
    )
    metrics["evidence_gap_flag"] = metrics["study_sites_within_5km_n"] == 0
    metrics["high_pressure_low_protection_flag"] = (
        (metrics["colocation_pressure_index"] > 0)
        & (metrics["percent_protected"].fillna(0) < 1)
    )

    protection_overlaps = pd.concat(
        [
            protection_inter.assign(overlap_layer="protected_area"),
            mpa_inter.assign(overlap_layer="mpa"),
        ],
        ignore_index=True,
    )
    study_join = study_site_habitat_join(study_sites, habitat)
    regional = build_regional_summary(metrics)

    metrics.to_csv(OUT_HABITAT_METRICS, index=False)
    protection_overlaps.to_csv(OUT_PROTECTION_OVERLAPS, index=False)
    study_join.to_csv(OUT_STUDY_JOIN, index=False)
    regional.to_csv(OUT_REGIONAL_SUMMARY, index=False)

    manifest = {
        "projection_for_area_distance": CRS_METERS,
        "buffer_distances_m": BUFFER_DISTANCES_M,
        "inputs": {
            "eelgrass": str(EELGRASS_PATH.relative_to(REPO_ROOT)),
            "kelp": str(KELP_PATH.relative_to(REPO_ROOT)),
            "protected": str(PROTECTED_PATH.relative_to(REPO_ROOT)),
            "mpa": str(MPA_PATH.relative_to(REPO_ROOT)),
            "dredging": str(DREDGING_PATH.relative_to(REPO_ROOT)),
            "akvakultur": str(AKVAKULTUR_PATH.relative_to(REPO_ROOT)),
            "platforms": str(PLATFORMS_PATH.relative_to(REPO_ROOT)),
            "windfarms": str(WINDFARMS_PATH.relative_to(REPO_ROOT)),
            "study_sites": str(MASTER_SITES_PATH.relative_to(REPO_ROOT)),
        },
        "outputs": {
            "habitat_colocation_metrics": str(OUT_HABITAT_METRICS.relative_to(REPO_ROOT)),
            "habitat_protection_overlaps": str(OUT_PROTECTION_OVERLAPS.relative_to(REPO_ROOT)),
            "study_site_habitat_join": str(OUT_STUDY_JOIN.relative_to(REPO_ROOT)),
            "regional_colocation_summary": str(OUT_REGIONAL_SUMMARY.relative_to(REPO_ROOT)),
        },
        "notes": [
            "Pressure index is a transparent screening score, not an ecological impact model.",
            "Exact overlap with point pressure data is avoided; buffer counts and nearest distances are more informative.",
            "Canonical regions are approximated from habitat polygon centroid latitude where source region is absent.",
        ],
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Wrote {OUT_HABITAT_METRICS} ({len(metrics)} rows)")
    print(f"Wrote {OUT_PROTECTION_OVERLAPS} ({len(protection_overlaps)} rows)")
    print(f"Wrote {OUT_STUDY_JOIN} ({len(study_join)} rows)")
    print(f"Wrote {OUT_REGIONAL_SUMMARY} ({len(regional)} rows)")
    print(f"Wrote {OUT_MANIFEST}")
    print("\nRegional summary:")
    print(
        regional[
            [
                "ecosystem",
                "canonical_region",
                "habitat_polygons_n",
                "habitat_area_km2",
                "percent_habitat_protected",
                "percent_habitat_in_mpa",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
