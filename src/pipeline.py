from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
REPORTS = ROOT / "reports"
DASHBOARD_DATA = ROOT / "dashboard" / "public" / "data" / "dashboard_data.json"

SALES_URL = "https://raw.githubusercontent.com/shreyayp/RetailPulse/main/data/raw/retail_sales_ml_apl.csv"
INVENTORY_URL = "https://raw.githubusercontent.com/shreyayp/RetailPulse/main/data/raw/retail_inventory_ml_apl.csv"
PUBLISHER_URL = "https://data.mendeley.com/datasets/27x8mjm8k4/1"
DOI = "10.17632/27x8mjm8k4.1"
LICENSE = "CC BY 4.0"
ATTRIBUTION = "Smith, Jimmy (2026). Retail Transactions and Stocks Data, Version 1. Mendeley Data. https://doi.org/10.17632/27x8mjm8k4.1"
EXPECTED_SALES_SHA256 = "da4763939baed1f46bfca7e893f9512a0294544494b1e794e5b8f2c59efbd2a1"
EXPECTED_INVENTORY_SHA256 = "c765678a26c2d024e8300b8f5b4a67cb2e2bde6e24213f202557d000ce37d".replace("f202557", "f202557")
MIN_REQUIRED_YEAR = 2025

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    headers = {"User-Agent": "VenkatRetailDataQuality/2.0"}
    with requests.get(url, stream=True, timeout=(30, 180), headers=headers) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    handle.write(chunk)
                    digest.update(chunk)
    return digest.hexdigest()


def normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def read_source_files():
    RAW.mkdir(parents=True, exist_ok=True)
    sales_path = RAW / "retail_sales_ml_apl.csv"
    inventory_path = RAW / "retail_inventory_ml_apl.csv"

    print("Downloading Mendeley-derived retail sales file...")
    sales_hash = download(SALES_URL, sales_path)
    print("Downloading Mendeley-derived retail inventory file...")
    inventory_hash = download(INVENTORY_URL, inventory_path)

    if sales_hash != EXPECTED_SALES_SHA256:
        raise RuntimeError(f"Sales source SHA-256 changed: {sales_hash}")
    if inventory_hash != EXPECTED_INVENTORY_SHA256:
        raise RuntimeError(f"Inventory source SHA-256 changed: {inventory_hash}")

    sales = pd.read_csv(sales_path, low_memory=False)
    inventory = pd.read_csv(inventory_path, low_memory=False)
    return sales, inventory, sales_path, inventory_path, sales_hash, inventory_hash


def _bool_series(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    return values.isin({"1", "true", "yes", "y", "t", "return", "returned"})


def prepare_sales(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict, list[dict]]:
    original = raw.copy()
    df = raw.copy()
    df.columns = [normalise(c) for c in df.columns]

    required = [
        "transaction_date", "store", "product_no",
        "qty_sold", "sales_amount",
    ]
    missing_columns = [column for column in required if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Sales CSV missing required fields {missing_columns}; found {list(df.columns)}")

    rename = {
        "transaction_date": "date",
        "store": "store_id",
        "product_no": "sku_id",
        "product_description": "product_description",
        "product_division": "division",
        "product_category": "category",
        "product_subcategory": "subcategory",
        "product_segment": "segment",
        "qty_sold": "quantity",
        "sales_amount": "sales_amount",
        "cogs": "cogs",
        "number_of_transactions": "number_of_transactions",
        "sales_type": "sales_type",
        "is_return": "is_return",
        "reason_of_return": "return_reason",
        "supplier": "supplier",
        "sales_channel": "sales_channel",
    }
    df = df.rename(columns={key: value for key, value in rename.items() if key in df.columns})

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for column in ["quantity", "sales_amount", "cogs", "number_of_transactions"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    for column in ["store_id", "sku_id", "product_description", "sales_type", "return_reason",
                   "supplier", "sales_channel", "division", "category", "subcategory", "segment"]:
        if column in df.columns:
            df[column] = df[column].astype("string").str.strip()

    for column in ["product_description", "sales_type", "return_reason", "supplier",
                   "sales_channel", "division", "category", "subcategory", "segment"]:
        if column not in df.columns:
            df[column] = pd.NA

    df["is_return_flag"] = _bool_series(df["is_return"]) if "is_return" in df.columns else False
    df["is_return_flag"] = df["is_return_flag"] | df["sales_type"].astype("string").str.contains(
        "return|refund|credit", case=False, na=False
    )

    duplicate_rows = int(df.duplicated().sum())
    invalid_date_rows = int(df["date"].isna().sum())
    missing_store_rows = int(df["store_id"].isna().sum() | (df["store_id"] == "").fillna(False).sum())
    missing_sku_rows = int(df["sku_id"].isna().sum() | (df["sku_id"] == "").fillna(False).sum())
    invalid_sales_rows = int(df["sales_amount"].isna().sum())
    negative_quantity_rows = int((df["quantity"] < 0).sum())
    negative_sales_rows = int((df["sales_amount"] < 0).sum())

    audit = []
    for column in df.columns:
        if column in {"is_return_flag"}:
            continue
        series = df[column]
        missing = int(series.isna().sum())
        audit.append({
            "field": column,
            "dtype": str(series.dtype),
            "missing_count": missing,
            "missing_pct": round(missing / len(df) * 100, 2) if len(df) else 0.0,
            "distinct_values": int(series.nunique(dropna=True)),
        })
    rules = [
        ("Exact duplicate rows", duplicate_rows, "assessed"),
        ("Invalid transaction dates", invalid_date_rows, "assessed"),
        ("Missing store identifiers", missing_store_rows, "assessed"),
        ("Missing SKU identifiers", missing_sku_rows, "assessed"),
        ("Missing sales amounts", invalid_sales_rows, "assessed"),
        ("Negative quantity rows (review returns)", negative_quantity_rows, "review"),
        ("Negative sales rows (review returns)", negative_sales_rows, "review"),
        ("Rows flagged as returns", int(df["is_return_flag"].sum()), "informational"),
    ]
    for name, count, status in rules:
        audit.append({
            "field": name,
            "dtype": "rule",
            "missing_count": 0,
            "missing_pct": 0.0,
            "distinct_values": count,
            "status": status,
        })

    # Retain source returns and negative values; remove exact duplicate rows only
    # from the analysis table. Invalid required keys/dates are excluded from charts.
    clean = df.drop_duplicates().copy()
    clean = clean.dropna(subset=["date", "store_id", "sku_id", "sales_amount"])
    clean = clean[
        (clean["store_id"].astype("string").str.len() > 0)
        & (clean["sku_id"].astype("string").str.len() > 0)
    ].copy()
    clean["year_month"] = clean["date"].dt.to_period("M").astype(str)
    clean["year"] = clean["date"].dt.year
    clean["gross_profit"] = clean["sales_amount"] - clean["cogs"] if "cogs" in clean.columns else pd.NA
    clean["gross_margin_pct"] = (
        clean["gross_profit"] / clean["sales_amount"].replace(0, pd.NA) * 100
        if "cogs" in clean.columns else pd.NA
    )

    if clean.empty:
        raise RuntimeError("No usable sales rows remain after validation.")
    if int(clean["date"].dt.year.min()) < MIN_REQUIRED_YEAR:
        raise RuntimeError("Sales data contains dates before 2025; refusing to label this a current dataset.")
    if clean["date"].dt.year.max() < MIN_REQUIRED_YEAR:
        raise RuntimeError("No sales observations from 2025 or 2026 were found.")

    quality = {
        "source_rows": int(len(df)),
        "clean_rows": int(len(clean)),
        "duplicate_rows": duplicate_rows,
        "invalid_date_rows": invalid_date_rows,
        "missing_store_rows": missing_store_rows,
        "missing_sku_rows": missing_sku_rows,
        "missing_sales_amount_rows": invalid_sales_rows,
        "negative_quantity_rows": negative_quantity_rows,
        "negative_sales_rows": negative_sales_rows,
        "return_rows": int(clean["is_return_flag"].sum()),
    }
    return clean, quality, audit


def prepare_inventory(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict, list[dict]]:
    df = raw.copy()
    df.columns = [normalise(c) for c in df.columns]
    required = ["start_date", "store", "product_no", "qty_on_hand"]
    missing_columns = [column for column in required if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Inventory CSV missing required fields {missing_columns}; found {list(df.columns)}")

    df = df.rename(columns={
        "start_date": "date",
        "store": "store_id",
        "product_no": "sku_id",
        "qty_on_hand": "on_hand",
        "product_description": "product_description",
        "product_division": "division",
        "product_category": "category",
        "product_subcategory": "subcategory",
        "product_segment": "segment",
        "stocks_selling_amount": "stock_selling_amount",
        "cost_of_stocks": "cost_of_stocks",
        "stock_unit_selling_price": "stock_unit_selling_price",
        "stock_unit_cost_price": "stock_unit_cost_price",
        "stock_status": "stock_status",
        "end_date": "end_date",
        "supplier": "supplier",
        "sales_channel": "sales_channel",
    })
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["on_hand"] = pd.to_numeric(df["on_hand"], errors="coerce")
    for column in ["store_id", "sku_id", "product_description", "division", "category",
                   "subcategory", "segment", "stock_status", "supplier", "sales_channel"]:
        if column in df.columns:
            df[column] = df[column].astype("string").str.strip()
        else:
            df[column] = pd.NA

    quality = {
        "source_rows": int(len(df)),
        "invalid_start_dates": int(df["date"].isna().sum()),
        "missing_store_rows": int(df["store_id"].isna().sum()),
        "missing_sku_rows": int(df["sku_id"].isna().sum()),
        "missing_on_hand_rows": int(df["on_hand"].isna().sum()),
        "negative_on_hand_rows": int((df["on_hand"] < 0).sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "latest_snapshot_date": str(df["date"].max()),
    }
    df = df.dropna(subset=["date", "store_id", "sku_id", "on_hand"])
    if df.empty or int(df["date"].dt.year.max()) < MIN_REQUIRED_YEAR:
        raise RuntimeError("Inventory data does not contain verified 2025/2026 observations.")

    audit = [
        {"field": column, "dtype": str(df[column].dtype),
         "missing_count": int(df[column].isna().sum()),
         "missing_pct": round(float(df[column].isna().mean() * 100), 2),
         "distinct_values": int(df[column].nunique(dropna=True))}
        for column in df.columns
    ]
    return df, quality, audit


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    sales_raw, inventory_raw, sales_path, inventory_path, sales_hash, inventory_hash = read_source_files()
    sales, sales_quality, sales_audit = prepare_sales(sales_raw)
    inventory, inventory_quality, inventory_audit = prepare_inventory(inventory_raw)

    start_date = sales["date"].min()
    end_date = sales["date"].max()
    latest_inventory_date = inventory["date"].max()
    latest_inventory = inventory[inventory["date"] == latest_inventory_date].copy()

    monthly = (
        sales.groupby("year_month", as_index=False)
        .agg(sales=("sales_amount", "sum"), units_sold=("quantity", "sum"),
             source_rows=("sku_id", "size"))
        .rename(columns={"year_month": "month"})
    )
    stores = (
        sales.groupby("store_id", as_index=False)
        .agg(sales=("sales_amount", "sum"), units_sold=("quantity", "sum"),
             source_rows=("sku_id", "size"))
        .sort_values("sales", ascending=False).head(12)
        .to_dict(orient="records")
    )
    products = (
        sales.groupby(["sku_id", "product_description"], dropna=False, as_index=False)
        .agg(units=("quantity", "sum"), sales=("sales_amount", "sum"),
             source_rows=("sku_id", "size"))
        .sort_values("sales", ascending=False).head(15)
        .to_dict(orient="records")
    )
    channels = (
        sales.groupby("sales_channel", dropna=False, as_index=False)
        .agg(sales=("sales_amount", "sum"), rows=("sku_id", "size"))
        .sort_values("sales", ascending=False)
        .to_dict(orient="records")
    )

    transaction_count = (
        float(sales["number_of_transactions"].fillna(0).sum())
        if "number_of_transactions" in sales.columns else None
    )
    sales_total = float(sales["sales_amount"].sum())
    units_total = float(sales["quantity"].sum())
    return_rows = int(sales["is_return_flag"].sum())
    kpis = {
        "source_rows": int(len(sales_raw)),
        "clean_sales_rows": int(len(sales)),
        "exact_duplicate_rows": sales_quality["duplicate_rows"],
        "reported_transaction_count": transaction_count,
        "total_units_sold": round(units_total, 2),
        "sales_amount_total": round(sales_total, 2),
        "return_rows": return_rows,
        "return_sales_amount": round(float(sales.loc[sales["is_return_flag"], "sales_amount"].sum()), 2),
        "store_count": int(sales["store_id"].nunique()),
        "sku_count": int(sales["sku_id"].nunique()),
        "sales_channel_count": int(sales["sales_channel"].nunique(dropna=True)),
        "sales_start_date": start_date.strftime("%Y-%m-%d"),
        "sales_end_date": end_date.strftime("%Y-%m-%d"),
        "inventory_rows": int(len(inventory_raw)),
        "latest_inventory_date": latest_inventory_date.strftime("%Y-%m-%d"),
        "latest_inventory_units": round(float(latest_inventory["on_hand"].sum()), 2),
        "inventory_store_count": int(latest_inventory["store_id"].nunique()),
        "inventory_sku_count": int(latest_inventory["sku_id"].nunique()),
    }

    verification = {
        "dataset": "Retail Transactions and Stocks Data",
        "publisher": "Mendeley Data",
        "dataset_doi": DOI,
        "publisher_url": PUBLISHER_URL,
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "distribution_note": "The files were inspected and retrieved from a public GitHub mirror of the Mendeley dataset. The Mendeley DOI is the canonical dataset citation.",
        "sales_source_url": SALES_URL,
        "inventory_source_url": INVENTORY_URL,
        "sales_archive_sha256": sales_hash,
        "inventory_archive_sha256": inventory_hash,
        "sales_observed_rows": int(len(sales_raw)),
        "inventory_observed_rows": int(len(inventory_raw)),
        "sales_date_min": kpis["sales_start_date"],
        "sales_date_max": kpis["sales_end_date"],
        "inventory_start_date_min": str(inventory["date"].min().date()),
        "inventory_start_date_max": str(inventory["date"].max().date()),
        "inventory_latest_snapshot_date": kpis["latest_inventory_date"],
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "date_note": "Calendar range is measured directly from Transaction Date and inventory Start Date fields; dataset publication year is not used as a substitute.",
    }

    audit = sales_audit + inventory_audit + [
        {"field": "Sales duplicate rows", "dtype": "rule", "missing_count": 0,
         "missing_pct": 0.0, "distinct_values": sales_quality["duplicate_rows"], "status": "assessed"},
        {"field": "Inventory duplicate rows", "dtype": "rule", "missing_count": 0,
         "missing_pct": 0.0, "distinct_values": inventory_quality["duplicate_rows"], "status": "assessed"},
    ]

    dashboard = {
        "kpis": kpis,
        "monthly": monthly.to_dict(orient="records"),
        "stores": stores,
        "products": products,
        "channels": channels,
        "audit": audit,
        "source": verification,
    }

    (REPORTS / "kpis.json").write_text(json.dumps(kpis, indent=2), encoding="utf-8")
    (REPORTS / "source_verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    pd.DataFrame(audit).to_csv(REPORTS / "data_quality_audit.csv", index=False)
    (REPORTS / "dashboard_data.json").write_text(json.dumps(dashboard, indent=2, default=str), encoding="utf-8")
    DASHBOARD_DATA.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DATA.write_text(json.dumps(dashboard, indent=2, default=str), encoding="utf-8")

    # Local SQL practice database; the raw source files are never modified.
    db_path = REPORTS / "analysis.sqlite"
    with sqlite3.connect(db_path) as connection:
        sales.to_sql("clean_transactions", connection, if_exists="replace", index=False)
        inventory.to_sql("clean_inventory", connection, if_exists="replace", index=False)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_month ON clean_transactions(year_month)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sales_store ON clean_transactions(store_id)")
    print(json.dumps({"kpis": kpis, "sales_quality": sales_quality, "inventory_quality": inventory_quality}, indent=2))


if __name__ == "__main__":
    main()
