#!/usr/bin/env python3
"""
load_postgres.py – Load all ShopSphere parquet files into PostgreSQL.

Usage:
    python load_postgres.py --db-url postgresql://user:password@localhost:5432/shopsphere
    python load_postgres.py --db-url postgresql://user:password@localhost:5432/shopsphere --schema raw
    python load_postgres.py --db-url postgresql://user:password@localhost:5432/shopsphere --table customers
"""

import time
from pathlib import Path

import click
import pandas as pd
from sqlalchemy import create_engine, text

# ── Table load order respects FK constraints ──────────────────────────────────
TABLE_ORDER = [
    "dim_date",
    "customers",
    "products",
    "marketing_campaigns",
    "orders",
    "order_items",
    "payments",
    "refunds",
    "website_events",
    "support_tickets",
    "campaign_spend",
    "subscriptions",
    "product_reviews",
]

# ── Explicit dtypes for PostgreSQL type mapping ───────────────────────────────
DTYPE_OVERRIDES: dict[str, dict] = {
    "customers": {
        "is_active": "boolean",
    },
    "products": {
        "cost":             "numeric(10,2)",
        "selling_price":    "numeric(10,2)",
        "margin":           "numeric(6,4)",
        "popularity_score": "numeric(14,8)",
    },
    "order_items": {
        "unit_price": "numeric(10,2)",
        "quantity":   "integer",
    },
    "payments": {
        "payment_amount": "numeric(12,2)",
    },
    "refunds": {
        "refund_amount": "numeric(12,2)",
    },
    "campaign_spend": {
        "spend":       "numeric(12,2)",
        "impressions": "integer",
        "clicks":      "integer",
        "conversions": "integer",
    },
    "subscriptions": {
        "churn_status":    "boolean",
        "monthly_price":   "numeric(6,2)",
        "annual_discount": "numeric(4,2)",
    },
    "product_reviews": {
        "rating": "integer",
    },
    "dim_date": {
        "date_key":        "integer",
        "year":            "integer",
        "quarter":         "integer",
        "month":           "integer",
        "week_of_year":    "integer",
        "day_of_month":    "integer",
        "day_of_week":     "integer",
        "is_weekend":      "boolean",
        "iso_year":        "integer",
        "iso_week":        "integer",
        "fiscal_year":     "integer",
        "fiscal_quarter":  "integer",
        "is_month_start":  "boolean",
        "is_month_end":    "boolean",
        "is_holiday":      "boolean",
    },
}


def load_table(
    engine,
    table_name: str,
    parquet_path: Path,
    schema: str,
    if_exists: str,
    chunk_size: int,
) -> None:
    df = pd.read_parquet(parquet_path)
    rows = len(df)
    print(f"  Loading {table_name:<25} {rows:>10,} rows …", end="", flush=True)

    t0 = time.time()
    df.to_sql(
        name=table_name,
        con=engine,
        schema=schema,
        if_exists=if_exists,
        index=False,
        chunksize=chunk_size,
        method="multi",
    )
    elapsed = time.time() - t0
    print(f"  done in {elapsed:.1f}s")


@click.command()
@click.option("--db-url",   required=True,
              help="SQLAlchemy connection URL, e.g. postgresql://user:pass@host:5432/dbname")
@click.option("--data-dir", default="data", show_default=True,
              help="Directory containing parquet files")
@click.option("--schema",   default="raw", show_default=True,
              help="PostgreSQL schema to load into")
@click.option("--table",    default=None,
              help="Load only this table (default: all)")
@click.option("--if-exists", default="replace", show_default=True,
              type=click.Choice(["fail", "replace", "append"]),
              help="What to do if table already exists")
@click.option("--chunk-size", default=10_000, show_default=True,
              help="Rows per INSERT batch")
def main(db_url: str, data_dir: str, schema: str, table: str,
         if_exists: str, chunk_size: int) -> None:
    """Load ShopSphere parquet files into PostgreSQL."""

    data_path = Path(data_dir)
    engine    = create_engine(db_url, future=True)

    # Ensure schema exists
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    print(f"Schema '{schema}' ready.")

    tables_to_load = [table] if table else TABLE_ORDER

    t_total = time.time()
    for tname in tables_to_load:
        ppath = data_path / f"{tname}.parquet"
        if not ppath.exists():
            print(f"  WARN: {ppath} not found – skipping")
            continue
        load_table(engine, tname, ppath, schema, if_exists, chunk_size)

    elapsed = time.time() - t_total
    print(f"\nAll done in {elapsed:.1f}s")
    print(f"\nConnect and explore:")
    print(f"  psql {db_url}")
    print(f"  SET search_path TO {schema};")
    print(f"  \\dt")


if __name__ == "__main__":
    main()
