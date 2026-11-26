# Current Retail Product Catalogue Data Quality Analytics

A reproducible Python, SQL and React analytics project auditing an Open Food Facts product-catalogue snapshot.

## Data freshness and scope
The recommender project collects the current Open Food Facts catalogue. This project reuses that shared snapshot instead of making a second burst of API requests. It prefers the un-deduplicated source export at `retailrocket-recommender/reports/source_products_2026.json`; until that export is available, it uses the recommender dashboard export. Only records whose reported last-modified timestamp is on or after 2026-01-01 UTC are kept. It stops instead of silently substituting older records when no qualifying records are returned.

This is a product-catalogue quality project, not a sales dataset. It does not contain retailer orders, sales revenue, customer purchases or clickstream behaviour. Do not interpret product modification dates as transaction dates.

## Source, attribution and licence
- Source: Open Food Facts, https://world.openfoodfacts.org/
- Upstream API used by the recommender collector: https://world.openfoodfacts.org/api/v2/search
- Shared snapshot: https://github.com/venkat5203/retailrocket-recommender
- Data licence: Open Database License (ODbL) 1.0. Attribute Open Food Facts contributors and share alike under the applicable ODbL terms.
- API documentation: https://openfoodfacts.github.io/documentation/docs/Product-Opener/v2/search/get-search/
- Structured search and sorting by last_modified_t are documented in API v2; the collector uses a descriptive User-Agent and spaces requests to respect published usage limits.

## Run on Windows
1. Install Python 3.10 or newer.
2. Run RUN_PROJECT.bat, or use PowerShell:
   - python -m venv .venv
   - .venv\Scripts\activate
   - pip install -r requirements.txt
   - python src\pipeline.py
3. Run the dashboard from the dashboard folder:
   - npm install
   - npm run dev
4. Production build: npm run build

## Outputs
- data/raw/open_food_facts_2026_snapshot.json — downloaded API response (kept local and ignored by Git)
- reports/source_verification.json — source, retrieval time, date window, request details and SHA-256 of raw snapshot
- reports/data_quality_audit.csv — missingness, barcode, nutrient and date checks
- reports/kpis.json — snapshot-level quality metrics
- reports/products_current_2026.csv — normalized product snapshot
- reports/analysis.sqlite — products_current_2026 table for SQL analysis
- reports/dashboard_data.json and dashboard/public/data/dashboard_data.json — dashboard payload

## Quality rules
- Include only products with last_modified_t on or after 2026-01-01 UTC.
- Identify missing product names, brands, categories, quantity, ingredients and nutrition values.
- Check barcode shape (8–14 digits) and negative nutrient values.
- Check duplicate barcodes only when the un-deduplicated source export is present. The dashboard fallback is already deduplicated, so the duplicate check is explicitly marked not testable rather than reporting a misleading zero.
- Completeness is a project-defined score over six selected fields; it is not an official Open Food Facts score.

## Interpretation
The API is community-contributed. The snapshot timestamp and source hash help reproduce which response was used; they do not independently prove every product claim is true.
