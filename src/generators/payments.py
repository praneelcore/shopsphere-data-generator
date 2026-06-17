"""Generate payments and refunds tables."""

import numpy as np
import pandas as pd
from datetime import timedelta

from config.settings import (
    PAYMENT_METHODS, OVERALL_REFUND_RATE, REFUND_REASONS,
    PRODUCT_CATEGORIES,
)
from src.utils import get_logger, make_uuids, weighted_choice

logger = get_logger(__name__)


def generate_payments(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    rng: np.random.Generator,
    dirty: bool = False,
) -> pd.DataFrame:
    logger.info("Generating payments …")

    # Only Completed orders have payments
    completed = orders[orders["status"] == "Completed"].copy()

    # ── Total per order ────────────────────────────────────────────────────────
    order_totals = (
        order_items.assign(line_total=order_items["unit_price"] * order_items["quantity"])
        .groupby("order_id")["line_total"]
        .sum()
        .reset_index()
        .rename(columns={"line_total": "payment_amount"})
    )
    completed = completed.merge(order_totals, on="order_id", how="left")
    completed["payment_amount"] = completed["payment_amount"].fillna(0).round(2)

    # ── Payment method ─────────────────────────────────────────────────────────
    methods = weighted_choice(rng, PAYMENT_METHODS, len(completed))

    # ── Payment date: 0-3 days after order ────────────────────────────────────
    delay_days = rng.integers(0, 4, size=len(completed))
    pay_dates  = pd.to_datetime(completed["order_date"].values) + pd.to_timedelta(delay_days, unit="D")

    df = pd.DataFrame({
        "payment_id":     make_uuids(len(completed)),
        "order_id":       completed["order_id"].values,
        "payment_method": methods,
        "payment_amount": completed["payment_amount"].values,
        "payment_date":   pd.to_datetime(pay_dates).to_series().dt.date.values,
    })

    if dirty:
        # Missing payments for ~0.5% of completed orders
        from src.utils import inject_nulls
        df = inject_nulls(rng, df, ["payment_method", "payment_amount"], rate=0.005)

    logger.info(f"  ↳ payments done. {len(df):,} rows. Total revenue: ${df['payment_amount'].sum():,.2f}")
    return df


def generate_refunds(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    products: pd.DataFrame,
    rng: np.random.Generator,
    dirty: bool = False,
) -> pd.DataFrame:
    logger.info("Generating refunds …")

    # Returned + some Completed orders get refunds
    returned   = orders[orders["status"] == "Returned"]["order_id"].values
    completed  = orders[orders["status"] == "Completed"]["order_id"].values

    # ~5% of completed also get partial refunds (complaints, partial returns)
    extra_refund_n = int(len(completed) * (OVERALL_REFUND_RATE - 0.02))  # adjust since returned already ~5%
    extra_refund_n = max(0, extra_refund_n)
    extra_ids      = rng.choice(completed, size=extra_refund_n, replace=False) if extra_refund_n > 0 else np.array([])

    refund_order_ids = np.concatenate([returned, extra_ids])

    if len(refund_order_ids) == 0:
        return pd.DataFrame(columns=["refund_id","order_id","refund_amount","refund_reason","refund_date"])

    # ── Calculate refund amounts ───────────────────────────────────────────────
    order_totals = (
        order_items.assign(line_total=order_items["unit_price"] * order_items["quantity"])
        .groupby("order_id")["line_total"]
        .sum()
    )

    # Electronics have higher refund rates (already captured in which orders are chosen)
    # Refund amount: full for "Returned", partial (50-100%) for "Completed" refunds
    refund_amounts = []
    for oid in refund_order_ids:
        total = order_totals.get(oid, 50.0)
        if oid in returned:
            pct = rng.uniform(0.85, 1.0)    # near-full refund
        else:
            pct = rng.uniform(0.30, 0.80)   # partial
        refund_amounts.append(round(float(total) * pct, 2))

    refund_amounts = np.array(refund_amounts)

    # ── Refund reasons ────────────────────────────────────────────────────────
    reasons = rng.choice(REFUND_REASONS, size=len(refund_order_ids))

    # ── Dates: refunds happen 1-21 days after order date ─────────────────────
    order_date_map = orders.drop_duplicates("order_id").set_index("order_id")["order_date"]
    order_dates_ref = pd.to_datetime([order_date_map.get(oid, orders["order_date"].iloc[0]) for oid in refund_order_ids])
    delay = rng.integers(1, 22, size=len(refund_order_ids))
    refund_dates_arr = (order_dates_ref + pd.to_timedelta(delay, unit="D"))
    refund_dates = pd.Series(refund_dates_arr).dt.date.values

    df = pd.DataFrame({
        "refund_id":     make_uuids(len(refund_order_ids)),
        "order_id":      refund_order_ids,
        "refund_amount": refund_amounts,
        "refund_reason": reasons,
        "refund_date":   refund_dates,
    })

    logger.info(f"  ↳ refunds done. {len(df):,} refunds. Total refunded: ${df['refund_amount'].sum():,.2f}")
    return df
