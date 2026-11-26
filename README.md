# Real-World Retail Data Quality & Analytics

A reproducible data-quality and business-analysis project built on the **UCI Online Retail** dataset. It audits real historical transaction records and produces a cleaned analysis copy, quality report, SQLite database, SQL examples and an interactive dashboard.

> **Dataset date range:** 1 December 2010 to 9 December 2011. These are historical source dates, not current 2026 transactions.

## Data source and provenance

- Dataset: [UCI Machine Learning Repository — Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail)
- DOI: `10.24432/C5BW33`
- Citation: Chen, D. (2015). *Online Retail*. UCI Machine Learning Repository.
- Licence: CC BY 4.0.
- Download archive: [online-retail.zip](https://archive.ics.uci.edu/static/public/352/online+retail.zip)

The pipeline downloads the archive, records its SHA-256 hash, extracts the workbook and checks the expected schema and reference row count. A hash confirms file integrity after download; it does not independently prove the underlying business records.

## What the pipeline audits

- Missing values and data types across the transaction fields.
- Exact duplicate rows.
- Non-positive quantities and unit prices.
- Cancellation / credit invoices (invoice numbers beginning with `C`).
- Customer-ID completeness and customer-level analysis coverage.

Rows with missing CustomerID remain available for transaction and revenue analysis, but are excluded from customer-level analysis. Cancellation rows remain identifiable and are not automatically treated as ordinary sales. The raw workbook is preserved; cleaning is applied to a separate analysis copy.

## Outputs

- `reports/source_verification.json` — source URL, archive hash, observed schema and row count.
- `reports/data_quality_audit.csv` — missingness, duplicates and rule checks.
- `reports/kpis.json` — transaction-quality and business KPIs.
- `reports/clean_transactions.csv` — cleaned transaction copy.
- `reports/analysis.sqlite` — SQLite table for SQL practice.
- `reports/dashboard_data.json` and `dashboard/public/data/dashboard_data.json` — dashboard data payload.

## Run locally on Windows

1. Install Python 3.10 or later.
2. Run `RUN_PROJECT.bat` from the project root, or execute `python src/pipeline.py`.
3. In `dashboard/`, run `npm install` and `npm run dev`.

The Vercel deployment uses the `dashboard/` application directory.

## Business definitions

`Revenue = Quantity × UnitPrice`. Negative quantities and cancellation invoices may represent returns or reversals. They are flagged and interpreted separately; they are not silently removed from the raw dataset.

## Attribution

Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. CC BY 4.0.
