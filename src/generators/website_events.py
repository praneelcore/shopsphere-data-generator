"""
Generate website_events table — fully vectorised, no Python loops over sessions.

Strategy:
  1. Generate N sessions with base timestamps, device, source, customer.
  2. For each funnel step, decide which sessions reach it via a random draw.
  3. Assign timestamps per step = base_ts + cumulative offsets.
  4. Stack all step arrays and add random extra page_view / search events.
"""

import numpy as np
import pandas as pd

from config.settings import (
    FUNNEL_CONVERSION, DEVICE_TYPES, TRAFFIC_SOURCES,
    START_DATE, END_DATE, SEASONALITY,
)
from src.utils import get_logger, make_uuids, random_dates_array, seasonal_weights, weighted_choice

logger = get_logger(__name__)

FUNNEL_STEPS = ["page_view", "product_view", "add_to_cart", "checkout", "purchase"]
# Probability of *reaching* each step given user started a session
REACH_PROBS = [
    FUNNEL_CONVERSION["page_view"],
    FUNNEL_CONVERSION["product_view"],
    FUNNEL_CONVERSION["add_to_cart"],
    FUNNEL_CONVERSION["checkout"],
    FUNNEL_CONVERSION["purchase"],
]


def generate_website_events(
    customers: pd.DataFrame,
    target_events: int,
    rng: np.random.Generator,
    dirty: bool = False,
) -> pd.DataFrame:
    logger.info(f"Generating ≈{target_events:,} website events (vectorised) …")

    # ── Estimate sessions needed ───────────────────────────────────────────────
    # avg events per session ≈ sum of reach probs + ~1.5 extra page/search events
    avg_eps = sum(REACH_PROBS) + 1.5
    n_sessions = int(target_events / avg_eps * 1.05)  # small buffer

    # ── Session-level attributes ──────────────────────────────────────────────
    base_dates  = random_dates_array(rng, START_DATE, END_DATE, n_sessions)
    s_w         = seasonal_weights(base_dates, SEASONALITY)
    idx         = rng.choice(n_sessions, size=n_sessions, replace=True, p=s_w)
    base_dates  = base_dates[idx]

    hours   = rng.integers(0, 24, n_sessions).astype("timedelta64[h]")
    minutes = rng.integers(0, 60, n_sessions).astype("timedelta64[m]")
    base_ts = base_dates.astype("datetime64[ns]") + hours + minutes

    # customer_id: 60% known, 40% anonymous (None stored as empty string for parquet)
    n_known = int(n_sessions * 0.60)
    cust_vals = customers["customer_id"].values
    chosen = rng.choice(cust_vals, size=n_known, replace=True)
    anon   = np.full(n_sessions - n_known, "", dtype=object)
    session_customers = np.concatenate([chosen, anon])
    rng.shuffle(session_customers)

    devices = weighted_choice(rng, DEVICE_TYPES,    n_sessions)
    sources = weighted_choice(rng, TRAFFIC_SOURCES, n_sessions)
    s_ids   = make_uuids(n_sessions)

    # ── Build funnel events vectorised ────────────────────────────────────────
    chunks: list[pd.DataFrame] = []

    # Time offsets between funnel steps (seconds): uniform 30-480
    offsets = np.cumsum(
        rng.integers(30, 480, size=(n_sessions, len(FUNNEL_STEPS))).astype("timedelta64[s]"),
        axis=1,
    )

    for step_idx, step_name in enumerate(FUNNEL_STEPS):
        reach_p = REACH_PROBS[step_idx]
        if step_idx == 0:
            # Every session has a page_view
            mask = np.ones(n_sessions, dtype=bool)
        else:
            mask = rng.random(n_sessions) < reach_p

        n = mask.sum()
        if n == 0:
            continue

        ts = base_ts[mask] + offsets[mask, step_idx]

        chunks.append(pd.DataFrame({
            "session_id":      s_ids[mask],
            "customer_id":     session_customers[mask],
            "event_timestamp": ts.astype("datetime64[ms]"),
            "event_type":      step_name,
            "device_type":     devices[mask],
            "traffic_source":  sources[mask],
        }))

    # ── Extra page_view / search events per session ───────────────────────────
    extra_counts = rng.integers(0, 5, n_sessions)   # 0-4 extra per session
    total_extra  = int(extra_counts.sum())

    if total_extra > 0:
        rep_idx  = np.repeat(np.arange(n_sessions), extra_counts)
        extra_ts = base_ts[rep_idx] + rng.integers(5, 600, total_extra).astype("timedelta64[s]")
        extra_types = rng.choice(["page_view", "search"], size=total_extra, p=[0.6, 0.4])

        chunks.append(pd.DataFrame({
            "session_id":      s_ids[rep_idx],
            "customer_id":     session_customers[rep_idx],
            "event_timestamp": extra_ts.astype("datetime64[ms]"),
            "event_type":      extra_types,
            "device_type":     devices[rep_idx],
            "traffic_source":  sources[rep_idx],
        }))

    # ── Combine & trim ────────────────────────────────────────────────────────
    df = pd.concat(chunks, ignore_index=True)
    df = df.sample(frac=1, random_state=int(rng.integers(0, 99999))).reset_index(drop=True)
    df = df.iloc[:target_events].copy()

    df.insert(0, "event_id", make_uuids(len(df)))

    # Replace empty string back to None for customer_id
    df["customer_id"] = df["customer_id"].replace("", None)

    if dirty:
        from src.utils import inject_nulls
        df = inject_nulls(rng, df, ["customer_id", "traffic_source"], rate=0.03)

    logger.info(
        f"  ↳ website_events done. {len(df):,} events. "
        f"Event dist: { df['event_type'].value_counts().to_dict() }"
    )
    return df
