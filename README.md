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

**Toggable layers overview** (right side bar layer control):

- **Ecosystem type** — kelp (orange) vs seagrass (purple); default view
- **Canonical region** — Barents Sea / Norwegian Sea / Oslofjord / Skagerrak (Gagnon et al. 2024 scheme)
- **Detailed region** — finer free-text region labels from source data
- **Year sampled**
- **Sediment C stock** — seagrass-only signal (mg C cm⁻³)
- **Source study** — colour by citation
- **Habitat type**

**Specific toggleable layers:**

| Layer | Source |
|---|---|
| Eelgrass polygons (Naturbase HB19) | Norwegian Environment Agency via ArcGIS REST |
| Kelp polygons (Naturbase HB19) | Norwegian Environment Agency via ArcGIS REST |
| Marine protected areas | Miljødirektoratet / Naturbase |
| Aquaculture register sites | Fiskeridirektoratet (Barentswatch API) |
| EMODnet dredging records | EMODnet Human Activities |
| EMODnet offshore platforms | EMODnet Human Activities |
| MASSIMAL remote-sensing field sites | MASSIMAL GitHub catalogue |
| Bottom trawl / otter trawl / seine effort | ICES fishing effort grid |
| Offshore drilling installations | Norwegian Offshore Directorate |
| Port vessel traffic | EMODnet / Barentswatch |
| Sedimentation rates | EMODnet Geology |
| Coastal resilience/vulnerability index | EMODnet Geology|
| Seabed erosion areas | EMODnet Geology|
| Fish habitat suitability (climate projection) | EMODnet Biology|
| Step 2: Carbon stocks by region | Canonical regions per Gagnon et al 2024 |
| NGU: Sediment OC stocks – North Sea / Skagerrak | Norges geologiske undersøkelse (NGU) |
| NGU: Sediment OC stocks – Norwegian shelf | Norges geologiske undersøkelse (NGU) |
| NGU: OC accumulation rates – North Sea / Skagerrak | Norges geologiske undersøkelse (NGU) |
| NGU: OC accumulation rates – Norwegian shelf | Norges geologiske undersøkelse (NGU) |

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
│   └── norway.html                 ← OUTPUT — generated locally (not in git; see below)
├── figures/
│   ├── colocation_topline_map.png
│   └── colocation_topline_map.svg
├── docs/
│   └── index.html                  ← GitHub Pages landing page
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

`maps/norway.html` is a fully self-contained file (all tiles and data are embedded). You can share it by:

1. **Email / file transfer** — send the `.html` file directly; recipients open it in any browser.
2. **GitHub Releases** — upload `norway.html` as a release asset for version-controlled sharing.
3. **GitHub Pages** — copy `norway.html` to `docs/norway.html`, commit, and enable Pages in repo settings. The `docs/index.html` in this repo provides a landing page that links to it.

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
