# Code review — map construction audit

**Date:** 2026-05-07
**Reviewer:** Connor Mack (UC San Diego MAS CSP capstone advisor)
**Scope:** `scripts/build_norway_map.py` and the supporting prepare/analysis scripts.

This document summarises a one-pass mentor audit of the map-construction
pipeline. PRs #1–#3 address the highest-leverage findings; the rest are
deferred — captured here so they don't get lost.

---

## What was already good

The architecture is genuinely sound for a capstone:

- Clean separation between **fetch** (`fetch_*.py`), **prepare**
  (`prepare_*_map_layers.py`), **analyse** (`spatial_colocation_analysis.py`,
  `step2_ecosystem_services.py`) and **render** (`build_norway_map.py`).
  Most student projects collapse all four into one notebook.
- Source attribution wired through to the UI as a dynamic per-layer
  panel — more thoughtful than 90% of public maps.
- The co-location classification logic is clearly defined in a config
  dict (`COLOCATION_CLASSES`) rather than scattered through if/else
  branches.
- `SEAGRASS_COORDS` correctly hardcoded with a citation to Gagnon et al.
  2024 Table S1 — the comment makes the provenance auditable.
- HB19 polygon simplification is one-pass and avoids hand-editing the
  generated HTML, which keeps the build reproducible.

---

## What changed (PRs #1–#3)

### PR #1 — `refactor/dedupe-canonical-region`

`canonical_region` was duplicated verbatim in `build_norway_map.py` and
`spatial_colocation_analysis.py`, with subtly different NaN handling.
Sites with NaN latitude could be classified differently by the analysis
CSVs and by the map.

- New `scripts/regions.py` — single source of truth for the four-region
  scheme (`canonical_region`, `CANONICAL_REGIONS`,
  `CANONICAL_REGION_COLORS`, `REGION_CENTROIDS`).
- New `scripts/geo_utils.py` — `clip_to_bbox` helper, replacing five
  inline lat/lon clip blocks.
- Net diff: −81 lines.

### PR #2 — `fix/simplify-in-meters`

`prepare_hb19_map_layers.py` and `prepare_context_map_layers.py`
simplified geometries with a tolerance of 0.001 decimal degrees in
EPSG:4326. At Norwegian latitudes that's a non-uniform tolerance —
~38 km per degree of longitude at 70°N vs. ~111 km of latitude — so
identical-looking polygons in Skagerrak vs. Barents Sea got different
effective simplification.

Reproject to UTM 33N (the same CRS the analysis script uses) before
simplifying, simplify in metres, project back. Per-layer tolerances:
30 m eelgrass, 75 m kelp, 100 m protected areas.

### PR #3 — `refactor/extract-modules-and-tests`

`build_norway_map.py` was 2141 lines. This PR doesn't fully split it
but extracts the easiest-to-isolate pieces and adds the tests that
catch the bug-prone parsing logic:

- New `scripts/mia_map/` package — `parsers.py` (DMS, year, WKT, free-text
  number), `popups.py` (`fmt_row` + a popup chrome helper),
  `templates/layer_panel.js` (the dynamic-legend script, previously a
  130-line escaped Python string).
- New `tests/` directory — 33 unit tests covering DMS edge cases,
  region classification, bbox clipping. `pytest tests/` runs in 0.2 s.
- `build_norway_map.py` shrinks by ~155 lines.

---

## Deferred work (worth doing later)

These came up during the audit but didn't make sense to bundle into the
three PRs above. Listed roughly in priority order.

### Performance and scaling

1. **Per-row `CircleMarker` → `folium.GeoJson` / `MarkerCluster`.**
   `add_point_csv_layer` and friends iterate `df.iterrows()` and emit one
   marker per row. For high-volume layers (aquaculture, dredging,
   sedimentation) this bloats the embedded HTML and slows initial render.
   Two paths:
   - Migrate to `folium.GeoJson(..., marker=folium.CircleMarker(...))` —
     Leaflet handles the markers in JS rather than per-element HTML.
     Loses some popup-formatting flexibility (GeoJsonPopup escapes HTML).
   - Wrap heavy layers in `folium.plugins.MarkerCluster`. Keeps custom
     popups, dramatically improves perf, but changes the visual character
     (clusters at low zoom, pins at high zoom).

   Worth a 30-min experiment before deciding. I deferred this because
   it's a *visible* change and Mia should weigh in on cluster vs. raw
   pins.

2. **Pre-aggregate trawl heatmaps.** The bottom-trawl CSVs are 3.7 MB and
   are shipped to the client at full resolution. Aggregating to coarser
   grid cells (e.g. 0.1° or 5 km) before passing to `HeatMap` would
   shrink the HTML without visibly degrading the heatmap.

### Correctness / safety

3. **Coordinate validation.** `dms_to_dd` will silently return wrong
   values if its regex partially matches a malformed cell. Add a
   `warn_if_outside_bbox(...)` check after `load_kelp_sites` /
   `load_seagrass_sites` and print the offending sites loudly.

4. **HTML escaping in popups.** Currently safe because all dynamic
   strings come from trusted CSVs, but if a free-text "notes" field ever
   ingests user-uploaded data, the popup HTML is an XSS path. Wrap any
   string that flows from CSV into popup HTML in `html.escape()`.

5. **CVI layer filter is regex on `name_closest`.** Fragile — if the
   upstream CSV labelling changes (`"Aunan|Norway"`), the layer silently
   empties. Filter on a stable provider/country column instead.

6. **Country-filter inconsistency.** Dredging uses `"Norway"`, port
   traffic uses `"NO"`, CVI uses regex. A small constants dict mapping
   `layer_key → (column, value)` would make the inconsistency visible.

### Architecture

7. **Excel is re-parsed in two places.** `build_master_inventory.py`
   already produces `data/processed/norway_blue_carbon_master_sites.csv`,
   but `build_norway_map.py` re-reads the raw `.xlsm`. Make the inventory
   CSV the single source of truth so DMS parsing only happens once.

8. **Finish the `mia_map/` split.** PR #3 extracted parsers, popups, and
   the JS template. The layer-add functions (`add_hb19_layer`,
   `add_protected_area_layer`, `add_point_csv_layer`,
   `add_port_traffic_layer`, etc.) are still in `build_norway_map.py`.
   Splitting them into `mia_map/layers/{hb19, protected, points,
   port_traffic, sedimentation, …}.py` would bring the main file down
   to ~150 lines (just `main()` orchestration).

9. **Build CLI / iteration speed.** No `--layers=sites,colocation` mode,
   no `--quick` flag. Iterating on the legend HTML currently requires
   re-reading every CSV. A simple argparse-based filter would speed dev
   loops substantially.

10. **NGU WMS layers fail silently offline.** The README says the HTML
    is self-contained, but the four NGU sediment OC layers are remote
    WMS calls. Either make the legend's "requires internet" note more
    prominent, or bake a static raster snapshot for offline sharing.

### UX

11. **40+ layers in a single non-collapsed `LayerControl`.**
    `folium.plugins.GroupedLayerControl` or splitting into Sites /
    Habitat / Pressures / Carbon categories would help users navigate.

12. **Year colormap is diverging blue→yellow→red.** No semantic midpoint
    exists for "year". Use a sequential palette (Viridis / Plasma) so
    older→newer maps cleanly to dark→light.

13. **Default-on co-location classes** stack visually with HB19 polygons
    on first open. Worth deciding: is the first thing a viewer sees the
    *sites*, or the *carbon assessment*?

---

## Cosmetic / nice-to-have

- Popup widths range from 280 px to 400 px across layers. Pick one and
  reuse the new `popup_html()` helper.
- Diamond markers (kelp) are rotated divs. The bounding box is bigger
  than the visible diamond, which can make click targets feel
  unpredictable. An SVG marker would render more cleanly.
- Tile URLs (Esri Ocean) are hardcoded inline. Consider a `TILE_URLS`
  constants block.

---

## How to use this list

Treat it as a punch list, not a scope expansion. Items 1–3 (perf,
coordinate validation, full module split) are the highest leverage if you
want to keep iterating on the audit. The rest are real but not urgent —
prioritise based on what your advisors and NIVA collaborators actually
ask for.
