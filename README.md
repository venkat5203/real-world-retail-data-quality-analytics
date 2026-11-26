# Real-World Retail Data Quality & Analytics

Portfolio project using the UCI Online Retail dataset. Dataset records are real historical transactions **as documented by UCI**, not independently audited. The project downloads the source, hashes the archive, checks the expected schema and row count, preserves the raw workbook, and creates audit outputs.


## Quick start (Windows)
1. Install Python 3.10+.
2. Extract this project folder.
3. Double-click `RUN_PROJECT.bat` (or run it in PowerShell). It creates a venv, installs requirements, downloads the UCI dataset, and runs the audit.
4. Dashboard: run `npm install`, then `npm run dev` in the `dashboard` folder. After the audit, generated data is available to the dashboard.


## Source and verification
- Dataset: UCI Machine Learning Repository, Online Retail, DOI `10.24432/C5BW33`, CC BY 4.0.
- Official page: https://archive.ics.uci.edu/dataset/352/online+retail
- Download URL used: https://archive.ics.uci.edu/static/public/352/online+retail.zip
- The script stores SHA-256 of the downloaded archive in `reports/source_verification.json`. Hash proves file integrity after download, not the truth of the underlying business records.
- Expected columns: InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country. Row count check is informational and does not stop analysis if UCI updates the file.

## Outputs
- `reports/source_verification.json` – source URL, file hash, bytes, schema checks, expected/observed rows
- `reports/data_quality_audit.csv` – missingness, duplicate count, data types, value checks
- `reports/kpis.json` – metrics calculated from the downloaded source
- `reports/clean_transactions.csv` – cleaned transaction copy (raw source untouched)
- `reports/analysis.sqlite` – database for SQL practice
- `reports/dashboard_data.json` – dashboard payload generated from observed data


## Quality rules
- Exact duplicate rows are flagged and excluded from the clean copy.
- Rows with missing `CustomerID` are retained for transaction/revenue analysis but excluded from customer-level analyses.
- Invoice numbers beginning with `C` are cancellations/credit transactions and are kept separate; not automatically called bad data.
- Quantity <= 0, UnitPrice <= 0, and missing key fields are flagged; policy is documented and the raw file is preserved.
- `Revenue = Quantity * UnitPrice`; negative revenue may represent reversals/cancellations and must be interpreted with context.

## Attribution
Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. License: CC BY 4.0.
