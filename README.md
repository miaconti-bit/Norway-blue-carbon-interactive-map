# Norway Blue Carbon Map

An interactive study-site map of **Norwegian seagrass (*Zostera marina*) and kelp (*Saccharina latissima* and others)** sampling locations, overlaid with habitat polygons, marine protected areas, environmental drivers, carbon stock/ accumulation, and human-pressure layers.

Built as part of the UC San Diego MAS CSP capstone project:
> *"Roadmap for Norwegian Blue Carbon Ecosystems as Nature-Based Solutions: Science-to-Policy Pathway Evaluation for Seagrass and Macroalgae Systems"* — Mia Conti (2025–26), in collaboration with the [C-BLUES project](https://www.c-blues.eu/) / NIVA (https://www.niva.no/en).

**Live map → [view on GitHub Pages](https://miaconti-bit.github.io/Norway-blue-carbon-interactive-map/)**

---

## What the map shows

| Symbol | Meaning |
|---|---|
| ■ diamond (orange) | Kelp site (size ∝ sample size *n*) |
| ■ square (purple) | Seagrass site (size ∝ number of cores) |

**Co-location classes** (spatial analysis layer):
| Class | Meaning |
|---|---|
| Pressure nearby + <1 % protected | Pressure signal within 5 km and almost no MPA overlap |
| Pressure nearby + protected | Pressure within 5 km with ≥10 % MPA overlap |
| Protected habitat | ≥10 % MPA overlap, no nearby pressure |
| Study site within 5 km | Mapped habitat near an existing study site |
| Mapped habitat / evidence gap | No pressure, study site, or strong protection signal |

### UI features

- **Grouped layer control** (top-right) — overlays are organised into 8 collapsible categories rather than one flat list. Click a category header to fold/unfold; click a checkbox to toggle a layer.
- **🔍 Zoom to region dropdown** (bottom-right) — jumps to one of the four canonical regions (Barents Sea, Norwegian Sea, Oslofjord, Skagerrak) and *auto-enables* the habitat, study-site, and carbon-data layers in one click.
- **Auto-enable on zoom** — the same auto-enable also fires once when you manually zoom past zoom level 7, so the relevant layers come on as you drill in.
- **Dynamic legend + source-links panel** (bottom-left) — updates as you toggle layers; "(Source)" links open the underlying dataset / publication.

### Toggleable layers (grouped)

| Group | Layer | Source |
|---|---|---|
| **Study Sites** | Study sites (kelp + seagrass) | Gagnon et al. 2024 + Gundersen et al. 2021 |
| **Habitats** | Naturbase HB19: mapped eelgrass areas (WMS) | Miljødirektoratet (live WMS) |
| **Habitats** | Naturbase HB19: mapped kelp forest occurrences (WMS) | Miljødirektoratet (live WMS) |
| **Research Networks** | MASSIMAL remote-sensing field sites | MASSIMAL GitHub catalogue |
| **Marine Protection** | Protected areas: marine relevant | Miljødirektoratet / Naturbase |
| **Marine Protection** | Protected areas: MPA subset | Miljødirektoratet / Naturbase |
| **Carbon Data** | Sedimentation rates: Norway | EMODnet Geology |
| **Carbon Data** | Carbon stocks in seagrass by region | Canonical regions per Gagnon et al. 2024 |
| **NGU Carbon (WMS)** | NGU: Sediment OC stocks — North Sea / Skagerrak | Norges geologiske undersøkelse (NGU) |
| **NGU Carbon (WMS)** | NGU: Sediment OC stocks — Norwegian shelf | Norges geologiske undersøkelse (NGU) |
| **NGU Carbon (WMS)** | NGU: OC accumulation rates — North Sea / Skagerrak | Norges geologiske undersøkelse (NGU) |
| **NGU Carbon (WMS)** | NGU: OC accumulation rates — Norwegian shelf | Norges geologiske undersøkelse (NGU) |
| **Co-location Analysis** | Five spatial-overlap classes (see table above) | Custom analysis, EPSG:32633 |
| **Human Pressures** | Aquaculture register: marine/saltwater sites | Fiskeridirektoratet (Barentswatch API) |
| **Human Pressures** | EMODnet dredging: Norway | EMODnet Human Activities |
| **Human Pressures** | EMODnet offshore platforms: Norway | EMODnet Human Activities |
| **Human Pressures** | Bottom trawl / otter trawl / seine effort (heatmaps) | EMODnet — subsampled to 5K each |
| **Human Pressures** | Offshore drilling: Norway | Norwegian Offshore Directorate |
| **Human Pressures** | Port vessel traffic: Norway | EMODnet / Barentswatch |
| **Human Pressures** | Norwegian fishing effort: ERS 2019–2023 (heatmap) | Fiskeridirektoratet ERS — subsampled to 10K |
| **Human Pressures** | Ocean darkening (Kd_490, latest 4 km NRT) | [Copernicus Marine](https://data.marine.copernicus.eu/product/OCEANCOLOUR_GLO_BGC_L3_NRT_009_101/description) WMTS |
| **Environmental Drivers** | Sea surface temperature (NASA MUR, daily) | NASA GIBS — JPL MUR L4 SST |
| **Environmental Drivers** | Sea surface salinity (NASA SMAP, 8-day) | NASA GIBS — JPL SMAP L3 CAP SSS |
| **Ecosystem Health & Condition** | Coastal resilience/vulnerability index | EMODnet Geology |
| **Ecosystem Health & Condition** | Seabed erosion areas | EMODnet Geology |
| **Ecosystem Health & Condition** | Fish habitat suitability (heatmap) | EMODnet Biology |

By default the auto-enable target groups are **Study Sites**, **Habitats**, and **Carbon Data**. The NGU carbon WMS layers, pressures, drivers, and ecosystem-health layers stay off until you opt in.

---

## Repository layout

```
norway-blue-carbon-map/
├── scripts/                        ← Python pipeline (run in order below)
│   ├── build_master_inventory.py   ← Step 1 — normalise raw workbooks → CSVs
│   ├── step2_ecosystem_services.py ← Step 2 — carbon stocks & sequestration tables
│   ├── prepare_hb19_map_layers.py  ← Prepare Naturbase HB19 GeoJSON layers
│   ├── prepare_context_map_layers.py ← Prepare pressure/context layers
│   ├── spatial_colocation_analysis.py ← Step 4 — pressure × protection overlap
│   ├── build_norway_map.py         ← Generate maps/norway.html (Folium map)
│   ├── figure_colocation_topline_map.py ← Generate figures/colocation_topline_map.*
│   └── fetch_*.py                  ← Data fetchers (re-run only when upstream changes)
├── data/
│   ├── processed/                  ← Derived CSVs (committed)
│   └── external/                   ← Fetched external datasets
│       ├── naturbase_hb19/map_layers/  ← HB19 habitat polygons (committed)
│       ├── verneomraader/map_layers/   ← MPA polygons (committed)
│       ├── emodnet/                    ← EMODnet point layers (committed)
│       ├── akvakultur/                 ← Aquaculture sites (committed)
│       ├── massimal/                   ← MASSIMAL catalogue (committed)
│       ├── seabee/                     ← SeaBee catalogue (committed)
│       ├── gundersen2021/              ← Extracted Gundersen 2021 tables (committed)
│       └── nature_index/              ← NINA Nature Index averages (committed)
├── maps/
│   └── norway.html                 ← local build output (not tracked in git)
├── figures/
│   ├── colocation_topline_map.png
│   └── colocation_topline_map.svg
├── docs/                           ← served by GitHub Pages
│   ├── index.html                  ← landing page (links to ./norway.html)
│   └── norway.html                 ← published map — auto-mirrored from maps/ at build time
├── requirements.txt
└── README.md
```

> **Large files not in git:** Raw Excel workbooks (`data/*.xlsx`, `data/*.xlsm`), `.tif` rasters, and several oversized CSVs are excluded (see `.gitignore`). See [Data sources](#data-sources) for download links.

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/miaconti-bit/Norway-blue-carbon-interactive-map.git
cd Norway-blue-carbon-interactive-map
pip install -r requirements.txt
```

### 2. Add the raw data workbooks

The raw Excel databases are not committed (licensing / size). Place them in `data/`:

| Filename | Description |
|---|---|
| `Norway_Seagrass_ Master_Database (4).xlsx` | Seagrass core-level carbon data (Gagnon et al. 2024) |
| `Norway_Macroalgae_Database.xlsm` | Kelp site-level data |

### 3. Run the pipeline

All scripts should be run from the `project/` root (the repo root):

```bash
# Build the master site inventory
python scripts/build_master_inventory.py

# Compute ecosystem-service tables (carbon stocks, sequestration, valuation)
python scripts/step2_ecosystem_services.py

# Prepare map layers (HB19 habitat polygons, context/pressure layers)
python scripts/prepare_hb19_map_layers.py
python scripts/prepare_context_map_layers.py

# Run spatial co-location analysis (pressure × MPA overlap)
python scripts/spatial_colocation_analysis.py

# Generate the interactive map → maps/norway.html
python scripts/build_norway_map.py

# Generate the static co-location figure
python scripts/figure_colocation_topline_map.py
```

Open `maps/norway.html` in any browser — no server needed.

### 4. Re-fetch external data (optional)

The `fetch_*.py` scripts pull upstream datasets and write a `*_manifest.json` to record what was downloaded. Re-run them only when upstream data changes:

```bash
python scripts/fetch_emodnet.py
python scripts/fetch_akvakultur.py
python scripts/fetch_verneomraader.py
python scripts/fetch_massimal.py
python scripts/fetch_seabee_catalog.py
python scripts/download_marine_naturtyper_hb19.py

# Requires: copernicusmarine login
python scripts/fetch_copernicus.py

# Requires: WDPA_API_KEY environment variable
python scripts/fetch_wdpa.py
```

---

## Data sources

| Dataset | Source | Notes |
|---|---|---|
| Seagrass carbon stocks | Gagnon et al. 2024, *Sci Rep* — [doi:10.1038/s41598-024-74760-3](https://doi.org/10.1038/s41598-024-74760-3) | Coordinates from Supplementary Table S1 |
| Kelp carbon stocks | Gundersen et al. 2021, *Front Mar Sci* — [doi:10.3389/fmars.2021.578629](https://doi.org/10.3389/fmars.2021.578629) | |
| Kelp/seagrass habitat polygons | [Naturbase HB19](https://kartkatalog.miljodirektoratet.no/) — Norwegian Environment Agency | Fetched via ArcGIS REST |
| Marine protected areas | [Miljødirektoratet Naturbase](https://www.miljodirektoratet.no/ansvarsomrader/naturmangfold/naturvernomrader/) | |
| Aquaculture register | [Fiskeridirektoratet / Barentswatch](https://www.barentswatch.no/) | |
| Human pressures (dredging, platforms, trawling, etc.) | [EMODnet Human Activities](https://emodnet.ec.europa.eu/en/human-activities) | |
| MASSIMAL remote-sensing sites | [MASSIMAL GitHub](https://github.com/Norwegian-Coastal-Kelp-Survey) | UAV/ML kelp mapping |
| SeaBee aerial surveys | [SeaBee NIVA](https://seabee.niva.no/) | |
| NINA Nature Index | [naturindeks.no](https://www.naturindeks.no/) | Coastal waters score |

---

## Known data gaps and caveats

- **Spatial sampling bias** — Skagerrak has 6 carbon samples / 5 sites; Barents Sea and Norwegian Sea each have 1.
- **Seagrass coordinates** are from Gagnon et al. 2024 (Supplementary Table S1), not in the workbook itself.
- **27 MPAs (~6,173 km²)** identified but spatial overlap with eelgrass meadows is unquantified.
- **Sequestration estimates** are IPCC Tier 1/2 — rely on global/Danish parameterizations, not Norwegian sediment dating.
- **Spatial CRS:** co-location analysis uses EPSG:32633 (UTM 33N). Sensitivity-check with an equal-area projection before final reporting.
- **Macroalgae coordinates** are DMS strings with mixed Unicode quotes; 22/29 rows parse to point locations; 7 are aggregate sites with no precise coordinate.

---

## Sharing the map

`maps/norway.html` and `docs/norway.html` are identical, fully self-contained files (all data embedded — only the WMS / WMTS tile layers fetch from external servers, which works in any browser online). You can share the map via:

1. **The live GitHub Pages site** — [https://miaconti-bit.github.io/Norway-blue-carbon-interactive-map/](https://miaconti-bit.github.io/Norway-blue-carbon-interactive-map/). `build_norway_map.py` automatically mirrors the build output into `docs/norway.html`; commit + push and the new map is live within ~1 minute.
2. **Direct file transfer** — send `maps/norway.html` (~94 MB) by email or cloud share; recipients open it in any browser, no server needed.
3. **GitHub Releases** — attach `norway.html` to a tagged release for version-pinned sharing.

> **Heads up:** the rendered map is ~94 MB. That's just under GitHub's 100 MB hard file limit, so `git push` will warn but succeed. If file size creeps past 100 MB in future builds, the simplest knobs are in `add_fishing_heatmap_layer(..., max_pts=...)` and the geometry-simplification tolerance in `add_colocation_layers`.

---

## Citation

If you use this map or pipeline in your work, please cite:

> Conti, M. (2026). *Norway Blue Carbon Map — interactive study-site map of Norwegian seagrass and kelp ecosystems*. GitHub. https://github.com/miaconti-bit/Norway-blue-carbon-interactive-map

And the primary data sources listed above.

---

## License

Code: [MIT License](LICENSE)

Data derived from third-party sources (EMODnet, Naturbase, Gagnon et al., Gundersen et al.) remains subject to the original data providers' terms. See individual `README.md` files in `data/external/` subdirectories.

---

## Contact

Mia Conti — mlconti@ucsd.edu | UC San Diego MAS CSP Capstone 2025–26
C-BLUES project: [niva.no/en/projectweb/c-blues](https://www.niva.no/en/projectweb/c-blues)
