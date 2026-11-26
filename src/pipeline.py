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


def request_page(session, page):
    params = {
        "page": page,
        "page_size": PAGE_SIZE,
        "sort_by": "last_modified_t",
        "fields": FIELDS,
    }
    for attempt in range(4):
        response = session.get(API_URL, params=params, timeout=45)
        if response.status_code in (429, 503):
            wait = int(response.headers.get("Retry-After", "30"))
            time.sleep(min(max(wait, 15), 120))
            continue
        response.raise_for_status()
        payload = response.json()
        if "products" not in payload:
            raise RuntimeError("Open Food Facts response did not contain a products list.")
        return payload
    raise RuntimeError("Open Food Facts rate limit persisted after retries.")


def fetch_latest_products():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "VenkatRetailDataQuality/2.0 (venkata.nemani99@gmail.com)",
        "Accept": "application/json",
    })
    first = request_page(session, 1)
    count = int(first.get("count") or 0)
    total_pages = max(1, math.ceil(count / PAGE_SIZE))
    first_products = first.get("products", [])
    stamps = [int(p.get("last_modified_t") or 0) for p in first_products]
    descending = not stamps or stamps[0] >= stamps[-1]

    if descending:
        pages = list(range(1, min(MAX_PAGES, total_pages) + 1))
    else:
        first_page = max(1, total_pages - MAX_PAGES + 1)
        pages = list(range(first_page, total_pages + 1))

    responses = []
    for page in pages:
        if page == 1:
            payload = first
        else:
            time.sleep(REQUEST_GAP_SECONDS)
            payload = request_page(session, page)
        responses.append({"page": page, "count": payload.get("count"), "products": payload.get("products", [])})

    raw_products = [p for response in responses for p in response["products"]]
    recent = [p for p in raw_products if int(p.get("last_modified_t") or 0) >= CUTOFF_EPOCH]
    unique_codes = {str(p.get("code") or "").strip() for p in recent if str(p.get("code") or "").strip()}

    if not recent:
        latest = max(stamps, default=0)
        latest_text = timestamp_iso(latest) or "unavailable"
        raise RuntimeError(
            "The API query returned no products updated since 2026-01-01. "
            f"First page latest timestamp: {latest_text}. No old records were substituted."
        )

    return recent, {
        "total_matching_products_reported_by_api": count,
        "pages_requested": pages,
        "page_size": PAGE_SIZE,
        "records_received_before_2026_filter": len(raw_products),
        "records_after_2026_filter_before_deduplication": len(recent),
        "unique_barcodes_after_2026_filter": len(unique_codes),
        "sort_direction_detected": "descending" if descending else "ascending",
    }


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
    raw_products, page_info = fetch_latest_products()
    records = [normalize(p) for p in raw_products]
    raw_frame = pd.DataFrame(records).sort_values("last_modified_epoch", ascending=False).reset_index(drop=True)
    raw_frame = raw_frame[raw_frame["last_modified_epoch"] >= CUTOFF_EPOCH].copy()
    if raw_frame.empty:
        raise RuntimeError("No 2026-updated products remain after normalization; stopping.")
    duplicate_rows = int(raw_frame["barcode"].duplicated(keep="first").sum())
    frame = raw_frame.drop_duplicates(subset=["barcode"], keep="first").copy()
    frame["last_modified_month"] = pd.to_datetime(frame["last_modified_epoch"], unit="s", utc=True).dt.strftime("%Y-%m")

    raw_path = RAW / "open_food_facts_2026_snapshot.json"
    raw_payload = {
        "source": API_URL,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
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
        "flagged_pct": round(100 * duplicate_rows / max(len(raw_frame), 1), 2),
        "distinct_values": int(frame["barcode"].nunique()),
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
