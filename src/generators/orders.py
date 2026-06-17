"""Generate orders + order_items tables."""

import numpy as np
import pandas as pd

from config.settings import (
    ORDER_STATUSES, CUSTOMER_SEGMENTS, SEASONALITY,
    START_DATE, END_DATE, PRODUCT_CATEGORIES,
)
from src.utils import get_logger, make_uuids, random_dates_array, seasonal_weights, weighted_choice

logger = get_logger(__name__)


def _segment_order_counts(
    customers: pd.DataFrame,
    target_orders: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Assign each customer a number of orders proportional to their segment multiplier.
    Total is scaled to hit target_orders approximately.
    """
    seg_mult = {s: CUSTOMER_SEGMENTS[s]["order_multiplier"] for s in CUSTOMER_SEGMENTS}
    raw = np.array([seg_mult[s] for s in customers["customer_segment"]], dtype=float)

    # Add random noise per customer
    noise = rng.exponential(scale=1.0, size=len(customers))
    raw   = raw * noise

    # Scale so sum ≈ target_orders
    scale = target_orders / raw.sum()
    counts = np.round(raw * scale).astype(int)
    counts = np.maximum(counts, 0)

    # One-Time Buyers: cap at 1
    otb_mask = customers["customer_segment"].values == "One-Time Buyer"
    counts[otb_mask] = np.minimum(counts[otb_mask], 1)

    # Fix small rounding drift
    diff = target_orders - counts.sum()
    if diff != 0:
        # add/subtract from regular customers
        regular_idx = np.where(customers["customer_segment"].values == "Regular")[0]
        adjust_idx  = rng.choice(regular_idx, size=abs(diff), replace=True)
        np.add.at(counts, adjust_idx, 1 if diff > 0 else -1)
        counts = np.maximum(counts, 0)

    return counts


def generate_orders(
    customers: pd.DataFrame,
    target_orders: int,
    rng: np.random.Generator,
    dirty: bool = False,
) -> pd.DataFrame:
    logger.info(f"Generating ≈{target_orders:,} orders …")

    counts = _segment_order_counts(customers, target_orders, rng)
    total  = int(counts.sum())
    logger.info(f"  ↳ actual order count after segment distribution: {total:,}")

    # ── Repeat each customer_id by their count ────────────────────────────────
    customer_ids_rep = customers["customer_id"].values.repeat(counts)

    # ── Order dates: seasonal distribution ────────────────────────────────────
    # First draw uniform dates, then resample with seasonal weights
    all_dates      = random_dates_array(rng, START_DATE, END_DATE, total)
    s_weights      = seasonal_weights(all_dates, SEASONALITY)
    resampled_idx  = rng.choice(total, size=total, replace=True, p=s_weights)
    order_dates    = all_dates[resampled_idx]
    customer_ids_rep = customer_ids_rep[resampled_idx]

    # ── Status ────────────────────────────────────────────────────────────────
    statuses = weighted_choice(rng, ORDER_STATUSES, total)

    df = pd.DataFrame({
        "order_id":    make_uuids(total),
        "customer_id": customer_ids_rep,
        "order_date":  pd.to_datetime(order_dates).to_series().dt.date.values,
        "status":      statuses,
    })

    if dirty:
        from src.utils import inject_nulls, inject_duplicates, inject_invalid_dates
        df = inject_duplicates(rng, df, rate=0.01)
        df = inject_invalid_dates(rng, df, "order_date", rate=0.005)

    logger.info(f"  ↳ orders done. Status dist: { df['status'].value_counts().to_dict() }")
    return df


def generate_order_items(
    orders: pd.DataFrame,
    products: pd.DataFrame,
    rng: np.random.Generator,
    dirty: bool = False,
) -> pd.DataFrame:
    logger.info(f"Generating order_items for {len(orders):,} orders …")

    # Basket size: log-normal → realistic 1-8 items, most orders 1-3 items
    basket_sizes = np.round(np.exp(rng.normal(0.6, 0.5, len(orders)))).astype(int)
    basket_sizes = np.clip(basket_sizes, 1, 8)
    total_items  = int(basket_sizes.sum())

    # ── Repeat order_ids ───────────────────────────────────────────────────────
    order_ids_rep = orders["order_id"].values.repeat(basket_sizes)

    # ── Sample products by popularity (Pareto 80/20) ─────────────────────────
    pop   = products["popularity_score"].values.astype(float)
    pop  /= pop.sum()
    prod_idx = rng.choice(len(products), size=total_items, replace=True, p=pop)

    product_ids = products["product_id"].values[prod_idx]
    unit_prices = products["selling_price"].values[prod_idx]

    # ── Quantities: mostly 1, occasionally 2-4 ───────────────────────────────
    qty_probs = [0.65, 0.20, 0.10, 0.05]
    quantities = rng.choice([1, 2, 3, 4], size=total_items, p=qty_probs)

    # ── Minor price variation (discounts, dynamic pricing) ───────────────────
    discount = rng.uniform(0.85, 1.05, total_items)
    unit_prices_final = np.round(unit_prices * discount, 2)

    df = pd.DataFrame({
        "order_item_id": make_uuids(total_items),
        "order_id":      order_ids_rep,
        "product_id":    product_ids,
        "quantity":      quantities,
        "unit_price":    unit_prices_final,
    })

    if dirty:
        from src.utils import inject_nulls
        df = inject_nulls(rng, df, ["quantity"], rate=0.01)

    logger.info(f"  ↳ order_items done. {total_items:,} line items. Avg basket: {basket_sizes.mean():.2f}")
    return df
