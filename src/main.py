"""
ShopSphere Data Generator – main entry point.

Usage examples:
    python generate.py                               # defaults
    python generate.py --customers 100000 --orders 1000000 --events 5000000
    python generate.py --seed 123
    python generate.py --dirty                       # inject data quality issues
    python generate.py --customers 50000 --orders 500000 --events 2000000
"""

import time
from pathlib import Path

import click
import numpy as np
import pandas as pd

from config.settings import (
    DEFAULT_CUSTOMERS, DEFAULT_ORDERS, DEFAULT_EVENTS,
    DEFAULT_SEED, OUTPUT_DIR,
)
from src.utils import get_logger, save_parquet
from src.generators.customers     import generate_customers
from src.generators.products      import generate_products
from src.generators.orders        import generate_orders, generate_order_items
from src.generators.payments      import generate_payments, generate_refunds
from src.generators.website_events import generate_website_events
from src.generators.support_tickets import generate_support_tickets
from src.generators.marketing     import generate_marketing_campaigns, generate_campaign_spend
from src.generators.subscriptions import generate_subscriptions
from src.generators.dim_date      import generate_dim_date

logger = get_logger("shopsphere")


@click.command()
@click.option("--customers", default=DEFAULT_CUSTOMERS, show_default=True,
              help="Number of customers to generate")
@click.option("--orders",    default=DEFAULT_ORDERS,    show_default=True,
              help="Target number of orders to generate")
@click.option("--events",    default=DEFAULT_EVENTS,    show_default=True,
              help="Target number of website events to generate")
@click.option("--products",  default=5_000,             show_default=True,
              help="Number of products to generate")
@click.option("--seed",      default=DEFAULT_SEED,      show_default=True,
              help="Random seed for reproducibility")
@click.option("--dirty",     is_flag=True, default=False,
              help="Inject intentional data quality issues")
@click.option("--output",    default=OUTPUT_DIR,        show_default=True,
              help="Output directory for parquet files")
def cli(customers: int, orders: int, events: int, products: int,
        seed: int, dirty: bool, output: str) -> None:
    """ShopSphere Data Generator – produce realistic ecommerce data for analytics."""

    t0      = time.time()
    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng     = np.random.default_rng(seed)

    logger.info("=" * 65)
    logger.info("  ShopSphere Data Generator")
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

    # ── 7. Website Events ─────────────────────────────────────────────────────
    df_events = generate_website_events(df_customers, events, rng, dirty=dirty)
    save_parquet(df_events, out_dir / "website_events.parquet", logger)

    # ── 8. Support Tickets ────────────────────────────────────────────────────
    df_tickets = generate_support_tickets(df_customers, rng, dirty=dirty)
    save_parquet(df_tickets, out_dir / "support_tickets.parquet", logger)

    # ── 9. Marketing Campaigns ────────────────────────────────────────────────
    df_campaigns = generate_marketing_campaigns(rng)
    save_parquet(df_campaigns, out_dir / "marketing_campaigns.parquet", logger)

    # ── 10. Campaign Spend ────────────────────────────────────────────────────
    df_spend = generate_campaign_spend(df_campaigns, rng)
    save_parquet(df_spend, out_dir / "campaign_spend.parquet", logger)

    # ── 11. Subscriptions ─────────────────────────────────────────────────────
    df_subs = generate_subscriptions(df_customers, df_tickets, rng, dirty=dirty)
    save_parquet(df_subs, out_dir / "subscriptions.parquet", logger)

    # ── 12. Date Dimension ────────────────────────────────────────────────────
    df_dim_date = generate_dim_date()
    save_parquet(df_dim_date, out_dir / "dim_date.parquet", logger)

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    logger.info("")
    logger.info("=" * 65)
    logger.info(f"  Generation complete in {elapsed:.1f}s")
    logger.info("")
    logger.info("  Dataset Summary:")
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
        "dim_date":           df_dim_date,
    }
    total_rows = 0
    for name, df in datasets.items():
        path = out_dir / f"{name}.parquet"
        mb   = path.stat().st_size / 1_048_576
        logger.info(f"    {name:<25} {len(df):>10,} rows  {mb:>7.1f} MB")
        total_rows += len(df)
    logger.info(f"    {'TOTAL':<25} {total_rows:>10,} rows")
    logger.info("=" * 65)
