# Real-World Retail Data Quality & Analytics

A reproducible data-quality and business-intelligence project using the **Retail Transactions and Stocks Data** dataset. The published source contains real store/SKU sales and inventory observations. The pipeline downloads both source files, checks their SHA-256 hashes, validates required fields and date coverage, audits data-quality issues, and generates an SQLite analytical warehouse plus an interactive dashboard.

> **Verified observation window:** 1 June 2025 to 24 April 2026 for sales transactions. Inventory start dates cover the same window. These dates are measured from the source CSV fields; they are not created by changing older timestamps.

## Data source and provenance

- Dataset: [Retail Transactions and Stocks Data — Mendeley Data](https://data.mendeley.com/datasets/27x8mjm8k4/1)
- DOI: `10.17632/27x8mjm8k4.1`
- Author: Jimmy Smith
- Version: 1, published 27 April 2026
- Licence: CC BY 4.0
- Attribution: Smith, Jimmy (2026). *Retail Transactions and Stocks Data*, Version 1. Mendeley Data. https://doi.org/10.17632/27x8mjm8k4.1

The source contains daily transaction-level sales and on-hand stock across 40 retail storefronts and 2,326 SKUs. The public CSV mirror is used as the distribution endpoint for the automated pipeline; the Mendeley DOI remains the canonical dataset citation. The pipeline records the exact hashes of the downloaded files and the observed date range.

## What the pipeline audits

- Missing required dates, store IDs, SKU IDs and sales amounts.
- Exact duplicate rows.
- Invalid date values and numeric fields.
- Negative quantities and negative sales amounts, which are flagged for review rather than automatically treated as errors because returns may be present.
- Return rows based on the source return flag and sales-type field.
- Inventory date coverage, missing stock fields and negative on-hand values.

Returns and negative values are preserved in the analysis dataset and reported separately. The pipeline does not silently convert return activity into ordinary sales.

## Dashboard

The dark dashboard retains the same layout and includes:
- Executive KPIs for sales rows, reported transactions, returns, sales amount, stores and SKUs.
- Monthly sales amount trend.
- Sales by store.
- Top products by sales amount and units.
- Sales by channel.
- Latest inventory snapshot summary.
- Source verification and data-quality audit findings.

Sales amounts are displayed in source units because the source dataset description does not establish a currency denomination that this project can safely assume.

## Outputs

- `reports/source_verification.json` — dataset DOI, source URLs, file hashes, row counts and actual observation dates.
- `reports/data_quality_audit.csv` — field missingness and rule checks.
- `reports/kpis.json` — sales and inventory KPIs.
- `reports/dashboard_data.json` and `dashboard/public/data/dashboard_data.json` — compact dashboard payload.
- `reports/analysis.sqlite` — local SQLite tables `clean_transactions` and `clean_inventory`.
- `queries/analysis.sql` — example business and quality queries.

Raw source files and the SQLite database are not committed to GitHub.

## Run locally on Windows

1. Install Python 3.10 or later.
2. Run `RUN_PROJECT.bat` from the repository root, or execute `python src/pipeline.py`.
3. In `dashboard/`, run `npm install` and `npm run dev`.

The Vercel project builds the Vite dashboard from the `dashboard/` directory.

## Data integrity controls

- The pipeline verifies the exact SHA-256 of both source files before using them.
- It rejects sales data whose minimum observation year is before 2025.
- It calculates the displayed start/end dates from the actual transaction date values.
- Source files are never modified; duplicates are excluded only from the cleaned analysis copy.
- An inventory snapshot is selected by the maximum observed inventory start date.

## Licence and attribution

Dataset licence: CC BY 4.0. Please attribute the original Mendeley Data record using the author, title, version, DOI and licence above. The public GitHub mirror is a transport source, not the original publisher.
