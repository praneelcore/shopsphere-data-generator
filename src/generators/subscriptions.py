"""Generate subscriptions table."""

import numpy as np
import pandas as pd
from datetime import timedelta

from config.settings import SUBSCRIPTION_PLANS, CHURN_RATE_BASE, START_DATE, END_DATE
from src.utils import get_logger, make_uuids, random_dates_array, weighted_choice

logger = get_logger(__name__)


def generate_subscriptions(
    customers: pd.DataFrame,
    support_tickets: pd.DataFrame,
    rng: np.random.Generator,
    dirty: bool = False,
) -> pd.DataFrame:
    logger.info("Generating subscriptions …")

    # ~45% of customers have a subscription
    subscriber_mask = rng.random(len(customers)) < 0.45
    # Whale & Loyal are more likely to subscribe
    whale_mask = customers["customer_segment"].values == "Whale"
    loyal_mask = customers["customer_segment"].values == "Loyal"
    otb_mask   = customers["customer_segment"].values == "One-Time Buyer"

    subscriber_mask[whale_mask] = rng.random(whale_mask.sum()) < 0.90
    subscriber_mask[loyal_mask] = rng.random(loyal_mask.sum()) < 0.70
    subscriber_mask[otb_mask]   = rng.random(otb_mask.sum())   < 0.15

    subscribers = customers[subscriber_mask].copy()
    n = len(subscribers)

    # ── Ticket count per customer (higher = higher churn) ────────────────────
    ticket_counts = support_tickets.groupby("customer_id").size().rename("ticket_count")
    subscribers   = subscribers.merge(ticket_counts, on="customer_id", how="left")
    subscribers["ticket_count"] = subscribers["ticket_count"].fillna(0).astype(int)

    # ── Plans ────────────────────────────────────────────────────────────────
    plans = weighted_choice(rng, SUBSCRIPTION_PLANS, n)
    # Override: Whales lean Enterprise/Premium
    plans[subscribers["customer_segment"].values == "Whale"]  = rng.choice(
        ["Enterprise","Premium"], size=(subscribers["customer_segment"].values == "Whale").sum(),
        p=[0.55, 0.45]
    )

    # ── Start dates ──────────────────────────────────────────────────────────
    start_dates = random_dates_array(rng, START_DATE, END_DATE, n)

    # ── Churn status ─────────────────────────────────────────────────────────
    churn_prob = CHURN_RATE_BASE + (subscribers["ticket_count"].values * 0.05)
    churn_prob = np.clip(churn_prob, 0, 0.80)
    is_churned = rng.random(n) < churn_prob

    # Inactive customers have higher churn
    inactive_sub = ~subscribers["is_active"].values
    is_churned[inactive_sub] = rng.random(inactive_sub.sum()) < 0.70

    # ── End dates ────────────────────────────────────────────────────────────
    end_dates = np.where(
        is_churned,
        [
            str(pd.Timestamp(sd) + pd.Timedelta(days=int(rng.integers(30, 730))))
            for sd in start_dates
        ],
        None,
    )
    # Clamp to END_DATE
    end_dates_final = []
    for ed in end_dates:
        if ed is None:
            end_dates_final.append(None)
        else:
            ts = pd.Timestamp(ed)
            end_dates_final.append(min(ts, pd.Timestamp(END_DATE)).date())

    df = pd.DataFrame({
        "subscription_id": make_uuids(n),
        "customer_id":     subscribers["customer_id"].values,
        "plan_type":       plans,
        "start_date":      pd.to_datetime(start_dates).to_series().dt.date.values,
        "end_date":        end_dates_final,
        "churn_status":    is_churned,
    })

    if dirty:
        from src.utils import inject_nulls
        df = inject_nulls(rng, df, ["plan_type"], rate=0.02)

    logger.info(f"  ↳ subscriptions done. {len(df):,} rows. Churned: {is_churned.sum():,} ({is_churned.mean()*100:.1f}%)")
    return df
