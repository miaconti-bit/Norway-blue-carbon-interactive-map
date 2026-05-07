# Project Plan & Scope

## Overview

UC San Diego MAS CSP capstone (student: Mia Conti). Working title:
**"Roadmap for Norwegian Blue Carbon Ecosystems as Nature-Based Solutions: Science to Policy Pathway Evaluation for Seagrass and Macroalgae Systems."**

A science-to-policy synthesis built around a five-step framework, applied in parallel to seagrass (*Zostera marina*) and macroalgae (*Saccharina latissima* + others) in Norway.

## Five-Step Framework

1. **Ecosystem Characterization** — extent, carbon stocks, environmental drivers, human/climate pressures
2. **Ecosystem Service Assessment** — carbon sequestration potential + uncertainty, co-benefits
3. **Scientific Readiness Assessment** — permanence, climate-change risk, GHG-budget compatibility (IPCC tiers)
4. **Policy Readiness Assessment**
5. **Implementation Pathway**

**Current status (2026-05):** Steps 1–3 drafted for seagrass; Steps 4–5 are headers only. The macroalgae parallel chapter has not been written — the `.xlsm` is the raw material for it.

The `docs/Norway Roadmap RD.docx` is the authoritative source for scope and direction.

## Canonical Regional Scheme

Four regions, used as the deliberate analytical unit throughout the seagrass chapter (per Gagnon et al. 2024). Default to this partition in any cross-ecosystem analysis or figure; finer fjord-level detail is fine as a second axis but should not replace it.

| Canonical | Synonyms in source data |
|---|---|
| **Barents Sea** (North) | Northern Norway, Porsangerfjord, Hammerfest, Near Bodø |
| **Norwegian Sea** (West) | Hardangerfjord, Sognefjord, Mid-Norway coast, North Sea / southwest Norway, Southwest Norway coast |
| **Oslofjord** (South East) | Inner Oslofjord (no kelp sites currently — known data gap) |
| **Skagerrak** (South West) | Skagerrak proper, Outer Oslofjord (Hvaler area, lat < 59°N) |

The macroalgae spreadsheet uses ~15 free-text region strings; `scripts/build_norway_map.py:canonical_region()` is the single source of truth for normalizing them. Update that function rather than maintaining a separate mapping.

## Known Data Gaps (chapter findings, not omissions to fix)

- Spatial sampling bias — Skagerrak has 6 carbon samples / 5 sites; Barents Sea and Norwegian Sea each have 1.
- 27 MPAs (~6,173 km²) but spatial overlap with eelgrass is unquantified.
- No Norway-specific marine-heatwave or storm-frequency data.
- Sequestration estimates are IPCC Tier 1/2 — rely on global/Danish parameterizations, not Norwegian sediment dating.

## Named Case-Study Sites (seagrass)

Worth flagging on maps once coords land:

- **Sørkjosleira & Kobbevågen** — paired Ramsar sites in Balsfjord, divergent eutrophication trajectories
- **Tingsholmen, Rossholmen** — North Sea fixed monitoring stations
- **Frisk Oslofjord** program area — 99 eelgrass meadows re-mapped 2021–22 vs. 2007–11 baseline

## External Datasets (not yet in repo)

Candidate sources for extending maps or analyses:

- **Frigstad et al. 2020 / Nordic Blue Carbon Project** — national eelgrass extent (60 km² measured, 90 km² modeled)
- **Gagnon et al. 2024** — only Norwegian site-level eelgrass carbon-stock paper; defines the four-region scheme
- **EMODnet** — vessel traffic, dredging, offshore installations, seabed erosion, MPAs
- **NINA Nature Index** for coastal waters — biodiversity score 0.766
- **NBFN / NIVA / IMR / GRID-Arendal / SeaBee** — Norwegian Blue Forests Network and partners doing UAV/ML mapping
