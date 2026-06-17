"""
ShopSphere Data Generator – main entry point.

Usage examples:
    python generate.py                                          # defaults (full, prod scale)
    python generate.py --mode full --scale dev                  # small dataset for dev
    python generate.py --mode full --scale staging              # medium for CI/CD
    python generate.py --mode full --scale prod                 # full dataset
    python generate.py --mode full --dirty                      # inject data quality issues
    python generate.py --mode batch --date 2024-03-15           # one day's data
    python generate.py --mode batch --start-date 2024-03-01 --end-date 2024-03-31
    python generate.py --mode batch --days 30                   # N days from last generated
    python generate.py --customers 50000 --orders 500000 --events 2000000  # custom sizes
"""

import json
import time
from datetime import date, timedelta
from pathlib import Path

import click
import numpy as np
import pandas as pd

from config.settings import (
    DEFAULT_CUSTOMERS, DEFAULT_ORDERS, DEFAULT_EVENTS,
    DEFAULT_SEED, OUTPUT_DIR, SCALE_PRESETS,
    BATCH_DAILY_VOLUMES, SEASONALITY, START_DATE, END_DATE,
)
from src.utils import get_logger, save_parquet, dirty_manifest
from src.generators.customers      import generate_customers
from src.generators.products       import generate_products
from src.generators.orders         import generate_orders, generate_order_items
from src.generators.payments       import generate_payments, generate_refunds
from src.generators.website_events import generate_website_events
from src.generators.support_tickets import generate_support_tickets
from src.generators.marketing      import generate_marketing_campaigns, generate_campaign_spend
from src.generators.subscriptions  import generate_subscriptions
from src.generators.dim_date       import generate_dim_date
from src.generators.reviews        import generate_reviews

logger = get_logger("shopsphere")

METADATA_FILE = "generation_metadata.json"


def _load_metadata(out_dir: Path) -> dict:
    meta_path = out_dir / METADATA_FILE
    if meta_path.exists():
        with open(meta_path) as f:
            return json.load(f)
    return {}


def _save_metadata(out_dir: Path, metadata: dict):
    meta_path = out_dir / METADATA_FILE
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)


def run_full_generation(
    customers: int, orders: int, events: int, products: int,
    seed: int, dirty: bool, out_dir: Path,
) -> None:
    """Generate all tables from scratch (full mode)."""
    rng = np.random.default_rng(seed)

    logger.info("=" * 65)
    logger.info("  ShopSphere Data Generator — FULL mode")
    logger.info(f"  customers={customers:,}  orders={orders:,}  events={events:,}")
    logger.info(f"  seed={seed}  dirty={dirty}  output={out_dir}")
    logger.info("=" * 65)

    # ── 1. Customers ──────────────────────────────────────────────────────────
    df_customers = generate_customers(customers, rng, dirty=dirty)
    save_parquet(df_customers, out_dir / "customers.parquet", logger)

    # ── 2. Products ───────────────────────────────────────────────────────────
    df_products = generate_products(products, rng, dirty=dirty)
    save_parquet(df_products, out_dir / "products.parquet", logger)

    # ── 3. Orders ─────────────────────────────────────────────────────────────
    df_orders = generate_orders(df_customers, orders, rng, dirty=dirty)
    save_parquet(df_orders, out_dir / "orders.parquet", logger)

    # ── 4. Order Items ────────────────────────────────────────────────────────
    df_order_items = generate_order_items(df_orders, df_products, rng, dirty=dirty)
    save_parquet(df_order_items, out_dir / "order_items.parquet", logger)

    # ── 5. Payments ───────────────────────────────────────────────────────────
    df_payments = generate_payments(df_orders, df_order_items, rng, dirty=dirty)
    save_parquet(df_payments, out_dir / "payments.parquet", logger)

    # ── 6. Refunds ────────────────────────────────────────────────────────────
    df_refunds = generate_refunds(df_orders, df_order_items, df_products, rng, dirty=dirty)
    save_parquet(df_refunds, out_dir / "refunds.parquet", logger)

    # ── 7. Marketing Campaigns ────────────────────────────────────────────────
    df_campaigns = generate_marketing_campaigns(rng)
    save_parquet(df_campaigns, out_dir / "marketing_campaigns.parquet", logger)

    # ── 8. Website Events ─────────────────────────────────────────────────────
    df_events = generate_website_events(df_customers, events, rng, campaigns=df_campaigns, dirty=dirty)
    save_parquet(df_events, out_dir / "website_events.parquet", logger)

    # ── 9. Support Tickets ────────────────────────────────────────────────────
    df_tickets = generate_support_tickets(df_customers, rng, dirty=dirty)
    save_parquet(df_tickets, out_dir / "support_tickets.parquet", logger)

    # ── 10. Campaign Spend ────────────────────────────────────────────────────
    df_spend = generate_campaign_spend(df_campaigns, rng)
    save_parquet(df_spend, out_dir / "campaign_spend.parquet", logger)

    # ── 11. Subscriptions ─────────────────────────────────────────────────────
    df_subs = generate_subscriptions(df_customers, df_tickets, rng, dirty=dirty)
    save_parquet(df_subs, out_dir / "subscriptions.parquet", logger)

    # ── 12. Product Reviews ───────────────────────────────────────────────────
    df_reviews = generate_reviews(df_orders, df_order_items, df_products, df_customers, rng, dirty=dirty)
    save_parquet(df_reviews, out_dir / "product_reviews.parquet", logger)

    # ── 13. Date Dimension ────────────────────────────────────────────────────
    df_dim_date = generate_dim_date()
    save_parquet(df_dim_date, out_dir / "dim_date.parquet", logger)

    # ── Save dirty manifest ───────────────────────────────────────────────────
    if dirty:
        from src.utils import (inject_invalid_dates, inject_broken_fks,
                               inject_future_timestamps, inject_negative_amounts)

        # Post-generation dirty injection (after all FK dependencies are resolved)
        # Invalid dates on orders
        df_orders["order_date"] = df_orders["order_date"].astype(str)
        df_orders = inject_invalid_dates(rng, df_orders, "order_date", rate=0.005, table_name="orders")
        save_parquet(df_orders, out_dir / "orders.parquet", logger)

        # Broken FKs on order_items
        df_order_items = inject_broken_fks(rng, df_order_items, "product_id", rate=0.003, table_name="order_items")
        save_parquet(df_order_items, out_dir / "order_items.parquet", logger)

        # Future timestamps on website_events
        df_events = inject_future_timestamps(rng, df_events, "event_timestamp", rate=0.002, table_name="website_events")
        save_parquet(df_events, out_dir / "website_events.parquet", logger)

        # Negative amounts on payments
        df_payments = inject_negative_amounts(rng, df_payments, "payment_amount", rate=0.001, table_name="payments")
        save_parquet(df_payments, out_dir / "payments.parquet", logger)

        dirty_manifest.save(out_dir / "dirty_manifest.json")
        logger.info(f"  ↳ Dirty manifest saved: {len(dirty_manifest.issues)} issue types logged")

    # ── Save metadata ─────────────────────────────────────────────────────────
    _save_metadata(out_dir, {
        "mode": "full",
        "last_generated_date": str(END_DATE),
        "seed": seed,
        "dirty": dirty,
        "customers": customers,
        "orders": orders,
        "events": events,
    })

    # ── Summary ───────────────────────────────────────────────────────────────
    datasets = {
        "customers":          df_customers,
        "products":           df_products,
        "orders":             df_orders,
        "order_items":        df_order_items,
        "payments":           df_payments,
        "refunds":            df_refunds,
        "website_events":     df_events,
        "support_tickets":    df_tickets,
        "marketing_campaigns":df_campaigns,
        "campaign_spend":     df_spend,
        "subscriptions":      df_subs,
        "product_reviews":    df_reviews,
        "dim_date":           df_dim_date,
    }
    return datasets


def run_batch_generation(
    target_date: date, seed: int, dirty: bool, out_dir: Path,
) -> None:
    """Generate one day's worth of incremental data (batch mode)."""
    rng = np.random.default_rng(seed + int(target_date.toordinal()))

    month = target_date.month
    seasonality_mult = SEASONALITY.get(month, 1.0)

    # Scale daily volumes by seasonality
    n_orders   = int(BATCH_DAILY_VOLUMES["orders"] * seasonality_mult)
    n_events   = int(BATCH_DAILY_VOLUMES["website_events"] * seasonality_mult)
    n_customers = int(BATCH_DAILY_VOLUMES["customers"] * seasonality_mult)
    n_tickets  = int(BATCH_DAILY_VOLUMES["support_tickets"] * seasonality_mult)
    n_new_subs = int(BATCH_DAILY_VOLUMES["subscriptions_new"] * seasonality_mult)

    logger.info("=" * 65)
    logger.info(f"  ShopSphere Data Generator — BATCH mode for {target_date}")
    logger.info(f"  orders={n_orders}  events={n_events}  customers={n_customers}")
    logger.info(f"  seasonality_mult={seasonality_mult:.2f}  dirty={dirty}")
    logger.info("=" * 65)

    # Load existing data for FK references
    existing_customers = pd.read_parquet(out_dir / "customers.parquet")
    existing_products  = pd.read_parquet(out_dir / "products.parquet")
    existing_campaigns = pd.read_parquet(out_dir / "marketing_campaigns.parquet")

    # ── New customers for the day ─────────────────────────────────────────────
    df_new_customers = generate_customers(n_customers, rng, dirty=dirty)
    # Append to existing
    _append_parquet(df_new_customers, out_dir / "customers.parquet")
    all_customers = pd.concat([existing_customers, df_new_customers], ignore_index=True)

    # ── Orders for the day (using all customers, weighted toward active) ──────
    from src.generators.orders import generate_orders_batch, generate_order_items
    df_orders = generate_orders_batch(all_customers, n_orders, target_date, rng, dirty=dirty)
    _append_parquet(df_orders, out_dir / "orders.parquet")

    # ── Order Items ───────────────────────────────────────────────────────────
    df_order_items = generate_order_items(df_orders, existing_products, rng, dirty=dirty)
    _append_parquet(df_order_items, out_dir / "order_items.parquet")

    # ── Payments ──────────────────────────────────────────────────────────────
    from src.generators.payments import generate_payments, generate_refunds
    df_payments = generate_payments(df_orders, df_order_items, rng, dirty=dirty)
    _append_parquet(df_payments, out_dir / "payments.parquet")

    # ── Refunds ───────────────────────────────────────────────────────────────
    df_refunds = generate_refunds(df_orders, df_order_items, existing_products, rng, dirty=dirty)
    _append_parquet(df_refunds, out_dir / "refunds.parquet")

    # ── Website Events ────────────────────────────────────────────────────────
    df_events = generate_website_events(all_customers, n_events, rng, campaigns=existing_campaigns, dirty=dirty)
    _append_parquet(df_events, out_dir / "website_events.parquet")

    # ── Support Tickets ───────────────────────────────────────────────────────
    from src.generators.support_tickets import generate_support_tickets_batch
    df_tickets = generate_support_tickets_batch(all_customers, n_tickets, target_date, rng, dirty=dirty)
    _append_parquet(df_tickets, out_dir / "support_tickets.parquet")

    # ── Campaign Spend (one row per active campaign) ──────────────────────────
    from src.generators.marketing import generate_campaign_spend_daily
    df_spend = generate_campaign_spend_daily(existing_campaigns, target_date, rng)
    _append_parquet(df_spend, out_dir / "campaign_spend.parquet")

    # ── Save dirty manifest ───────────────────────────────────────────────────
    if dirty:
        dirty_manifest.save(out_dir / f"dirty_manifest_{target_date}.json")

    # ── Update metadata ───────────────────────────────────────────────────────
    metadata = _load_metadata(out_dir)
    metadata["last_generated_date"] = str(target_date)
    metadata["mode"] = "batch"
    _save_metadata(out_dir, metadata)

    logger.info(f"\n  ✓ Batch complete for {target_date}: "
                f"{n_orders} orders, {len(df_order_items):,} items, "
                f"{n_events:,} events, {n_customers} new customers")


def _append_parquet(df: pd.DataFrame, path: Path):
    """Append rows to an existing parquet file."""
    if path.exists():
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, df], ignore_index=True)
        combined.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
    else:
        df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")


@click.command()
@click.option("--mode", type=click.Choice(["full", "batch"]), default="full",
              show_default=True, help="Generation mode: full (all data) or batch (daily incremental)")
@click.option("--scale", type=click.Choice(["dev", "staging", "prod"]), default=None,
              help="Scale preset: dev (~100K rows), staging (~900K), prod (~9.2M)")
@click.option("--customers", default=None, type=int,
              help="Number of customers (overrides scale preset)")
@click.option("--orders", default=None, type=int,
              help="Target number of orders (overrides scale preset)")
@click.option("--events", default=None, type=int,
              help="Target number of website events (overrides scale preset)")
@click.option("--products", default=None, type=int,
              help="Number of products (overrides scale preset)")
@click.option("--seed", default=DEFAULT_SEED, show_default=True,
              help="Random seed for reproducibility")
@click.option("--dirty", is_flag=True, default=False,
              help="Inject intentional data quality issues")
@click.option("--output", default=OUTPUT_DIR, show_default=True,
              help="Output directory for parquet files")
@click.option("--date", "batch_date", default=None,
              help="[batch mode] Generate data for this date (YYYY-MM-DD)")
@click.option("--start-date", default=None,
              help="[batch mode] Start date for range generation (YYYY-MM-DD)")
@click.option("--end-date", default=None,
              help="[batch mode] End date for range generation (YYYY-MM-DD)")
@click.option("--days", default=None, type=int,
              help="[batch mode] Generate N days from last generated date")
def cli(mode: str, scale: str, customers: int, orders: int, events: int,
        products: int, seed: int, dirty: bool, output: str,
        batch_date: str, start_date: str, end_date: str, days: int) -> None:
    """ShopSphere Data Generator – produce realistic ecommerce data for analytics."""

    t0      = time.time()
    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if mode == "full":
        # Resolve scale
        if scale:
            preset = SCALE_PRESETS[scale]
            n_customers = customers or preset["customers"]
            n_orders    = orders or preset["orders"]
            n_events    = events or preset["events"]
            n_products  = products or preset["products"]
        else:
            n_customers = customers or DEFAULT_CUSTOMERS
            n_orders    = orders or DEFAULT_ORDERS
            n_events    = events or DEFAULT_EVENTS
            n_products  = products or 5_000

        datasets = run_full_generation(
            n_customers, n_orders, n_events, n_products,
            seed, dirty, out_dir,
        )

        # Print summary
        elapsed = time.time() - t0
        logger.info("")
        logger.info("=" * 65)
        logger.info(f"  Generation complete in {elapsed:.1f}s")
        logger.info("")
        logger.info("  Dataset Summary:")
        total_rows = 0
        for name, df in datasets.items():
            path = out_dir / f"{name}.parquet"
            mb   = path.stat().st_size / 1_048_576
            logger.info(f"    {name:<25} {len(df):>10,} rows  {mb:>7.1f} MB")
            total_rows += len(df)
        logger.info(f"    {'TOTAL':<25} {total_rows:>10,} rows")
        logger.info("=" * 65)

    elif mode == "batch":
        # Determine dates to generate
        if batch_date:
            dates_to_gen = [date.fromisoformat(batch_date)]
        elif start_date and end_date:
            s = date.fromisoformat(start_date)
            e = date.fromisoformat(end_date)
            dates_to_gen = [s + timedelta(days=i) for i in range((e - s).days + 1)]
        elif days:
            metadata = _load_metadata(out_dir)
            last = date.fromisoformat(metadata.get("last_generated_date", str(END_DATE)))
            dates_to_gen = [last + timedelta(days=i+1) for i in range(days)]
        else:
            click.echo("Error: batch mode requires --date, --start-date/--end-date, or --days")
            return

        logger.info(f"Batch mode: generating {len(dates_to_gen)} day(s)")
        for d in dates_to_gen:
            run_batch_generation(d, seed, dirty, out_dir)

        elapsed = time.time() - t0
        logger.info(f"\n  All batches complete in {elapsed:.1f}s")
