# Norwegian Nature Index — Coastal Waters

Source: https://www.naturindeks.no/
Dataset DOI (indicators): https://doi.org/10.21345/y790-v762
Dataset DOI (index values): https://doi.org/10.21345/gfbt-pr39
License: CC-BY 4.0

## Key Value Already Cited in Roadmap
Coastal water NI (2024): **0.766** (SD = 0.011)

## How to Download
The full dataset (NI2025_IndicatorData.zip, ~33 MB) requires authentication
to download via the NVA API. Access it manually:

1. Go to https://www.naturindeks.no/DownloadData
2. Click the DOI link for "Indicator Data"
3. Log in or proceed as guest to download NI2025_IndicatorData.zip
4. Unzip into this directory — you want:
   - Indikator_Dataset.csv         (raw indicator observations)
   - Indikator_Average.csv         (area-weighted averages by year)
   - Indikator_DataScaled_Simulated.csv  (0–1 scaled values)

Alternatively, install the R package NIcalc:
  remotes::install_github("NINAnor/NIcalc")
Then access data with credentials from NINA.

## Relevant Filters
- ecosystem: "Kystvann" (Coast)
- years of interest: 2000, 2010, 2014, 2019, 2024
- indicators relevant to blue carbon / seagrass: look for ålegras, tang,
  makroalger, bunnfauna, fiskeyngel i ålegraseng

## Files (once downloaded)
Place CSV files here; scripts/step2_ecosystem_services.py will read
Indikator_Average.csv filtered to ecosystem="Kystvann".
