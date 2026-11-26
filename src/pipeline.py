"""Build a current 2026-updated product-catalogue quality snapshot from Open Food Facts.

This project analyzes catalogue attributes, not sales transactions. A record is included
only when Open Food Facts reports last_modified_t on or after 2026-01-01.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import sqlite3
import time

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
REPORTS = ROOT / "reports"
DASHBOARD_DATA = ROOT / "dashboard" / "public" / "data" / "dashboard_data.json"
API_URL = "https://world.openfoodfacts.org/api/v2/search"
SOURCE_URL = "https://world.openfoodfacts.org/"
RAW_SNAPSHOT_URL = "https://raw.githubusercontent.com/venkat5203/retailrocket-recommender/main/retailrocket-recommender/reports/source_products_2026.json"
DASHBOARD_SNAPSHOT_URL = "https://raw.githubusercontent.com/venkat5203/retailrocket-recommender/main/retailrocket-recommender/data.js"
LICENSE = "Open Database License (ODbL) 1.0"
CUTOFF = datetime(2026, 1, 1, tzinfo=timezone.utc)
CUTOFF_EPOCH = int(CUTOFF.timestamp())
PAGE_SIZE = 100
MAX_PAGES = 3
REQUEST_GAP_SECONDS = 7.5
FIELDS = ",".join([
    "code", "product_name", "brands", "categories_tags_en", "quantity",
    "last_modified_t", "created_t", "ingredients_text", "nutriments",
    "nutrition_grades", "completeness", "image_url", "countries_tags"
])
NUTRIENTS = {
    "energy-kcal_100g": "energy_kcal_100g",
    "fat_100g": "fat_100g",
    "saturated-fat_100g": "saturated_fat_100g",
    "carbohydrates_100g": "carbohydrates_100g",
    "sugars_100g": "sugars_100g",
    "proteins_100g": "proteins_100g",
    "salt_100g": "salt_100g",
    "fiber_100g": "fiber_100g",
}


def as_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def timestamp_iso(value):
    try:
        stamp = int(value)
        if stamp <= 0:
            return ""
        return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def fetch_latest_products():
    """Reuse the recommender project's current Open Food Facts snapshot.

    Prefer the un-deduplicated source response so this pipeline can audit duplicate
    barcodes. Fall back to the recommender dashboard export until the next refresh
    publishes that raw source file.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "VenkatRetailDataQuality/2.2",
        "Accept": "application/json, application/javascript, */*",
    })

    def get_snapshot(url, allow_missing=False):
        for attempt in range(4):
            response = session.get(url, timeout=90)
            if response.status_code == 404 and allow_missing:
                return None
            if response.status_code in (429, 503):
                retry_after = response.headers.get("Retry-After")
                try:
                    wait_seconds = int(retry_after) if retry_after else min(15 * (2 ** attempt), 90)
                except (TypeError, ValueError):
                    wait_seconds = min(15 * (2 ** attempt), 90)
                time.sleep(min(max(wait_seconds, 10), 90))
                continue
            response.raise_for_status()
            return response
        raise RuntimeError("The shared GitHub catalogue snapshot remained unavailable after retries.")

    raw_response = get_snapshot(RAW_SNAPSHOT_URL, allow_missing=True)
    raw_snapshot_available = raw_response is not None
    if raw_snapshot_available:
        try:
            snapshot = raw_response.json()
        except ValueError as exc:
            raise RuntimeError("The shared raw catalogue snapshot is not valid JSON.") from exc
        source_metadata = snapshot.get("metadata") or {}
        raw_products = snapshot.get("products") or []
        page_info = dict(snapshot.get("page_info") or {})
    else:
        response = get_snapshot(DASHBOARD_SNAPSHOT_URL)
        body = response.text.strip()
        prefix = "window.DASHBOARD_DATA = "
        if body.startswith(prefix):
            body = body[len(prefix):].rstrip()
            if body.endswith(";"):
                body = body[:-1]
        try:
            dashboard = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("The shared recommender dashboard file is not valid JSON.") from exc

        source_metadata = dashboard.get("metadata") or {}
        raw_products = []
        for product in dashboard.get("products") or []:
            categories = product.get("categories") or []
            if not isinstance(categories, list):
                categories = [str(categories)]
            if not categories and product.get("category") not in (None, "", "Uncategorized"):
                categories = [str(product.get("category"))]
            nutriments = {
                "energy-kcal_100g": product.get("energy_kcal_100g"),
                "fat_100g": product.get("fat_100g"),
                "saturated-fat_100g": product.get("saturated_fat_100g"),
                "carbohydrates_100g": product.get("carbohydrates_100g"),
                "sugars_100g": product.get("sugars_100g"),
                "proteins_100g": product.get("proteins_100g"),
                "salt_100g": product.get("salt_100g"),
                "fiber_100g": product.get("fiber_100g"),
            }
            raw_products.append({
                "code": product.get("barcode"),
                "product_name": product.get("name"),
                "brands": product.get("brands") or product.get("brand"),
                "categories_tags_en": categories,
                "quantity": product.get("quantity"),
                "last_modified_t": product.get("last_modified_t"),
                "created_t": product.get("created_t"),
                "ingredients_text": product.get("ingredients"),
                "nutriments": nutriments,
                "nutrition_grades": product.get("nutrition_grade"),
                "image_url": product.get("image_url"),
                "countries_tags": product.get("countries_tags") or [],
            })
        page_info = dict(source_metadata.get("page_info") or {})

    if not isinstance(raw_products, list) or not raw_products:
        raise RuntimeError("The shared catalogue snapshot contains no product records.")

    recent = [
        product for product in raw_products
        if int(product.get("last_modified_t") or 0) >= CUTOFF_EPOCH
    ]
    if not recent:
        raise RuntimeError(
            "The shared catalogue contains no products last modified since 2026-01-01 UTC. "
            "No historical records were substituted."
        )

    page_info.update({
        "shared_raw_snapshot_url": RAW_SNAPSHOT_URL if raw_snapshot_available else None,
        "shared_dashboard_snapshot_url": DASHBOARD_SNAPSHOT_URL,
        "snapshot_mode": "un-deduplicated source records" if raw_snapshot_available else "dashboard export (already deduplicated)",
        "duplicate_audit_available": raw_snapshot_available,
        "records_received_from_shared_snapshot": len(raw_products),
        "records_after_2026_filter": len(recent),
    })
    return recent, page_info, source_metadata, raw_snapshot_available

def normalize(product):
    nutriments = product.get("nutriments") or {}
    categories = product.get("categories_tags_en") or []
    if not isinstance(categories, list):
        categories = [str(categories)]
    brand_text = str(product.get("brands") or "").strip()
    first_brand = brand_text.split(",")[0].strip() if brand_text else ""
    first_category = str(categories[0]).replace("-", " ").title() if categories else ""
    numeric = {target: as_number(nutriments.get(source)) for source, target in NUTRIENTS.items()}
    name = str(product.get("product_name") or "").strip()
    ingredients = str(product.get("ingredients_text") or "").strip()
    quantity = str(product.get("quantity") or "").strip()
    completeness_fields = [name, brand_text, first_category, quantity, ingredients, any(v is not None for v in numeric.values())]
    completeness = round(100 * sum(bool(v) for v in completeness_fields) / len(completeness_fields), 1)
    invalid_nutrients = sum(v is not None and v < 0 for v in numeric.values())
    barcode = str(product.get("code") or "").strip()
    countries = product.get("countries_tags") or []
    return {
        "barcode": barcode,
        "product_name": name,
        "brands": brand_text,
        "primary_brand": first_brand,
        "categories": " | ".join(str(x) for x in categories),
        "primary_category": first_category or "Uncategorized",
        "quantity": quantity,
        "ingredients_text": ingredients,
        "nutrition_grade": str(product.get("nutrition_grades") or ""),
        "completeness_pct": completeness,
        "last_modified_epoch": int(product.get("last_modified_t") or 0),
        "last_modified_at_utc": timestamp_iso(product.get("last_modified_t")),
        "created_at_utc": timestamp_iso(product.get("created_t")),
        "image_url": str(product.get("image_url") or ""),
        "countries_tags": ", ".join(countries) if isinstance(countries, list) else str(countries),
        "invalid_nutrient_values": int(invalid_nutrients),
        **numeric,
    }


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    print("Fetching the most recently modified Open Food Facts product records...")
    raw_products, page_info, source_metadata, duplicate_audit_available = fetch_latest_products()
    records = [normalize(p) for p in raw_products]
    raw_frame = pd.DataFrame(records).sort_values("last_modified_epoch", ascending=False).reset_index(drop=True)
    raw_frame = raw_frame[raw_frame["last_modified_epoch"] >= CUTOFF_EPOCH].copy()
    if raw_frame.empty:
        raise RuntimeError("No 2026-updated products remain after normalization; stopping.")
    if duplicate_audit_available:
        nonblank_codes = raw_frame.loc[raw_frame["barcode"].ne(""), "barcode"]
        duplicate_rows = int(nonblank_codes.duplicated(keep="first").sum())
    else:
        duplicate_rows = None
    with_codes = raw_frame.loc[raw_frame["barcode"].ne("")].drop_duplicates(subset=["barcode"], keep="first")
    without_codes = raw_frame.loc[raw_frame["barcode"].eq("")]
    frame = pd.concat([with_codes, without_codes], ignore_index=True)
    frame["last_modified_month"] = pd.to_datetime(frame["last_modified_epoch"], unit="s", utc=True).dt.strftime("%Y-%m")

    raw_path = RAW / "open_food_facts_2026_snapshot.json"
    raw_payload = {
        "source": API_URL,
        "shared_snapshot_url": RAW_SNAPSHOT_URL if duplicate_audit_available else DASHBOARD_SNAPSHOT_URL,
        "retrieved_at_utc": source_metadata.get("retrieved_at_utc") or datetime.now(timezone.utc).isoformat(),
        "cutoff_utc": CUTOFF.isoformat(),
        "page_info": page_info,
        "products": raw_products,
    }
    raw_text = json.dumps(raw_payload, ensure_ascii=False, sort_keys=True)
    raw_path.write_text(raw_text, encoding="utf-8")
    raw_sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    audit_specs = [
        ("product_name", "Product name", frame["product_name"].eq("")),
        ("brands", "Brand", frame["brands"].eq("")),
        ("categories", "Category", frame["categories"].eq("")),
        ("quantity", "Quantity / pack size", frame["quantity"].eq("")),
        ("ingredients_text", "Ingredients text", frame["ingredients_text"].eq("")),
        ("nutrition", "Nutrition values", frame[list(NUTRIENTS.values())].isna().all(axis=1)),
        ("barcode_format", "Barcode format (8–14 digits)", ~frame["barcode"].str.fullmatch(r"\d{8,14}", na=False)),
        ("invalid_nutrients", "Negative nutrient values", frame["invalid_nutrient_values"].gt(0)),
        ("updated_in_2026", "Last modified on/after 2026-01-01", pd.Series(False, index=frame.index)),
    ]
    audit = []
    for field, label, mask in audit_specs:
        count = int(mask.sum())
        distinct_column = field if field in frame.columns else "barcode"
        audit.append({
            "field": label,
            "rule": field,
            "flagged_count": count,
            "flagged_pct": round(100 * count / len(frame), 2),
            "distinct_values": int(frame.loc[~mask, distinct_column].nunique()),
        })
    audit.append({
        "field": "Duplicate barcodes",
        "rule": "duplicate_barcodes",
        "flagged_count": duplicate_rows,
        "flagged_pct": round(100 * duplicate_rows / max(len(raw_frame), 1), 2) if duplicate_rows is not None else None,
        "distinct_values": int(frame.loc[frame["barcode"].ne(""), "barcode"].nunique()),
        "status": "assessed" if duplicate_audit_available else "not_testable_from_deduplicated_input",
        "note": "" if duplicate_audit_available else "The shared dashboard export is already deduplicated; this check becomes available after the source-record export is published.",
    })

    missing_brand = int(frame["brands"].eq("").sum())
    missing_category = int(frame["categories"].eq("").sum())
    missing_ingredients = int(frame["ingredients_text"].eq("").sum())
    missing_nutrition = int(frame[list(NUTRIENTS.values())].isna().all(axis=1).sum())
    invalid_nutrients = int(frame["invalid_nutrient_values"].gt(0).sum())
    updates = frame.groupby("last_modified_month").size().reset_index(name="products_updated")
    updates = updates.rename(columns={"last_modified_month": "month"}).to_dict(orient="records")
    categories = frame.groupby("primary_category").size().sort_values(ascending=False).head(12)
    category_rows = [{"category": str(k), "product_count": int(v)} for k, v in categories.items()]
    brands = frame.loc[frame["primary_brand"].ne("")].groupby("primary_brand").size().sort_values(ascending=False).head(12)
    brand_rows = [{"brand": str(k), "product_count": int(v)} for k, v in brands.items()]

    first_update = timestamp_iso(int(frame["last_modified_epoch"].min()))
    latest_update = timestamp_iso(int(frame["last_modified_epoch"].max()))
    kpis = {
        "products_in_snapshot": int(len(frame)),
        "average_selected_field_completeness_pct": round(float(frame["completeness_pct"].mean()), 2),
        "missing_brand_rows": missing_brand,
        "missing_category_rows": missing_category,
        "missing_ingredients_rows": missing_ingredients,
        "missing_nutrition_rows": missing_nutrition,
        "invalid_nutrient_rows": invalid_nutrients,
        "duplicate_barcode_rows": duplicate_rows,
        "products_updated_in_2026": int((frame["last_modified_epoch"] >= CUTOFF_EPOCH).sum()),
        "unique_categories": int(frame["primary_category"].nunique()),
        "unique_brands": int(frame.loc[frame["primary_brand"].ne(""), "primary_brand"].nunique()),
        "earliest_product_update_utc": first_update,
        "latest_product_update_utc": latest_update,
    }
    manifest = {
        "dataset": "Open Food Facts product catalogue snapshot",
        "api_endpoint": API_URL,
        "shared_snapshot_url": RAW_SNAPSHOT_URL if duplicate_audit_available else DASHBOARD_SNAPSHOT_URL,
        "source_url": SOURCE_URL,
        "license": LICENSE,
        "attribution": "Open Food Facts contributors",
        "retrieved_at_utc": raw_payload["retrieved_at_utc"],
        "required_last_modified_from_utc": CUTOFF.isoformat(),
        "earliest_included_product_update_utc": first_update,
        "latest_included_product_update_utc": latest_update,
        "raw_snapshot_file": raw_path.name,
        "raw_snapshot_sha256": raw_sha,
        "page_info": page_info,
        "data_note": "This is a product-catalogue snapshot, not sales, orders, customer purchases, or clickstream data.",
    }
    (REPORTS / "source_verification.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (REPORTS / "kpis.json").write_text(json.dumps(kpis, indent=2), encoding="utf-8")
    pd.DataFrame(audit).to_csv(REPORTS / "data_quality_audit.csv", index=False)
    frame.to_csv(REPORTS / "products_current_2026.csv", index=False)

    with sqlite3.connect(REPORTS / "analysis.sqlite") as connection:
        frame.to_sql("products_current_2026", connection, if_exists="replace", index=False)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products_current_2026(barcode)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products_current_2026(primary_category)")

    dashboard = {
        "status": "ready",
        "metadata": {
            "source": "Open Food Facts",
            "source_url": SOURCE_URL,
            "api_endpoint": API_URL,
            "shared_snapshot_url": RAW_SNAPSHOT_URL if duplicate_audit_available else DASHBOARD_SNAPSHOT_URL,
            "license": LICENSE,
            "attribution": "Open Food Facts contributors",
            "retrieved_at_utc": raw_payload["retrieved_at_utc"],
            "last_modified_window_utc": {"from": first_update, "to": latest_update},
            "data_note": "The records are product-catalogue entries last modified in 2026. No sales or purchase behaviour is included.",
        },
        "kpis": kpis,
        "monthly_updates": updates,
        "categories": category_rows,
        "brands": brand_rows,
        "products": frame.head(40).to_dict(orient="records"),
        "audit": audit,
    }
    data_text = json.dumps(dashboard, indent=2, ensure_ascii=False, default=str)
    (REPORTS / "dashboard_data.json").write_text(data_text, encoding="utf-8")
    DASHBOARD_DATA.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DATA.write_text(data_text, encoding="utf-8")

    print("Completed current product-catalogue quality audit.")
    print(json.dumps({"kpis": kpis, "manifest": manifest}, indent=2))
    print("Dashboard data:", DASHBOARD_DATA)


if __name__ == "__main__":
    main()
