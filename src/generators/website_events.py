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
    UTM_SOURCES, UTM_MEDIUMS, PAGE_URLS,
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

# Map event types to realistic page URLs
EVENT_PAGE_MAP = {
    "page_view": ["/", "/products", "/deals", "/about", "/help"],
    "product_view": ["/product/detail"],
    "add_to_cart": ["/product/detail", "/cart"],
    "checkout": ["/checkout", "/checkout/payment"],
    "purchase": ["/checkout/payment"],
    "search": ["/search", "/products"],
}


def _assign_utm_campaign(sources: np.ndarray, rng: np.random.Generator, campaigns_df=None) -> np.ndarray:
    """Assign utm_campaign values from actual marketing_campaigns when available."""
    n = len(sources)
    campaigns = np.empty(n, dtype=object)

    if campaigns_df is not None and "utm_campaign" in campaigns_df.columns:
        # Use actual campaign utm values grouped by channel
        for channel_name in campaigns_df["channel"].unique():
            channel_campaigns = campaigns_df[campaigns_df["channel"] == channel_name]["utm_campaign"].values
            # Map channel names to traffic source names
            channel_to_source = {
                "Google Ads": "Google Ads",
                "Facebook Ads": "Facebook Ads",
                "LinkedIn Ads": "LinkedIn Ads",
                "Email": "Email",
                "Organic Search": "Organic Search",
            }
            source_name = channel_to_source.get(channel_name)
            if source_name and len(channel_campaigns) > 0:
                mask = sources == source_name
                count = mask.sum()
                if count > 0:
                    campaigns[mask] = rng.choice(channel_campaigns, size=count)

        # Direct traffic gets no campaign
        direct_mask = sources == "Direct"
        campaigns[direct_mask] = None
    else:
        # Fallback: generate generic campaign names
        campaign_map = {
            "Google Ads": ["search_brand", "shopping_catalog", "performance_max", "remarketing_all", "competitor_terms"],
            "Facebook Ads": ["awareness_broad", "retargeting_site", "lookalike_ltv", "video_engagement", "dynamic_products"],
            "LinkedIn Ads": ["b2b_outreach", "lead_gen_form", "sponsored_content", "inmail_blast", "brand_lift"],
            "Email": ["welcome_series", "cart_abandonment", "win_back", "vip_loyalty", "newsletter_weekly"],
            "Organic Search": [None],
            "Direct": [None],
        }

        for source_name, campaign_list in campaign_map.items():
            mask = sources == source_name
            count = mask.sum()
            if count > 0:
                campaigns[mask] = rng.choice(campaign_list, size=count)

    return campaigns


def generate_website_events(
    customers: pd.DataFrame,
    target_events: int,
    rng: np.random.Generator,
    campaigns: pd.DataFrame = None,
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

    # ── UTM parameters (session-level) ────────────────────────────────────────
    utm_sources = weighted_choice(rng, UTM_SOURCES, n_sessions)
    utm_mediums = weighted_choice(rng, UTM_MEDIUMS, n_sessions)
    utm_campaigns = _assign_utm_campaign(sources, rng, campaigns_df=campaigns)

    # Align utm_source with traffic_source for consistency
    source_to_utm = {
        "Google Ads": "google",
        "Facebook Ads": "facebook",
        "LinkedIn Ads": "linkedin",
        "Email": "email",
        "Direct": "direct",
        "Organic Search": "organic",
    }
    for ts_name, utm_name in source_to_utm.items():
        mask = sources == ts_name
        utm_sources[mask] = utm_name

    # Align utm_medium with traffic_source
    medium_map = {
        "Google Ads": "cpc",
        "Facebook Ads": "social",
        "LinkedIn Ads": "cpc",
        "Email": "email",
        "Direct": "none",
        "Organic Search": "organic",
    }
    for ts_name, med_name in medium_map.items():
        mask = sources == ts_name
        utm_mediums[mask] = med_name

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

        # Assign page_url based on event type
        page_options = EVENT_PAGE_MAP.get(step_name, ["/"])
        page_urls = rng.choice(page_options, size=n)

        chunks.append(pd.DataFrame({
            "session_id":      s_ids[mask],
            "customer_id":     session_customers[mask],
            "event_timestamp": ts.astype("datetime64[ms]"),
            "event_type":      step_name,
            "device_type":     devices[mask],
            "traffic_source":  sources[mask],
            "page_url":        page_urls,
            "utm_source":      utm_sources[mask],
            "utm_medium":      utm_mediums[mask],
            "utm_campaign":    utm_campaigns[mask],
        }))

    # ── Extra page_view / search events per session ───────────────────────────
    extra_counts = rng.integers(0, 5, n_sessions)   # 0-4 extra per session
    total_extra  = int(extra_counts.sum())

    if total_extra > 0:
        rep_idx  = np.repeat(np.arange(n_sessions), extra_counts)
        extra_ts = base_ts[rep_idx] + rng.integers(5, 600, total_extra).astype("timedelta64[s]")
        extra_types = rng.choice(["page_view", "search"], size=total_extra, p=[0.6, 0.4])

        # Assign page_url for extra events
        extra_pages = np.empty(total_extra, dtype=object)
        for evt_type in ["page_view", "search"]:
            evt_mask = extra_types == evt_type
            count = evt_mask.sum()
            if count > 0:
                page_options = EVENT_PAGE_MAP.get(evt_type, ["/"])
                extra_pages[evt_mask] = rng.choice(page_options, size=count)

        chunks.append(pd.DataFrame({
            "session_id":      s_ids[rep_idx],
            "customer_id":     session_customers[rep_idx],
            "event_timestamp": extra_ts.astype("datetime64[ms]"),
            "event_type":      extra_types,
            "device_type":     devices[rep_idx],
            "traffic_source":  sources[rep_idx],
            "page_url":        extra_pages,
            "utm_source":      utm_sources[rep_idx],
            "utm_medium":      utm_mediums[rep_idx],
            "utm_campaign":    utm_campaigns[rep_idx],
        }))

    # ── Combine & trim ────────────────────────────────────────────────────────
    df = pd.concat(chunks, ignore_index=True)
    df = df.sample(frac=1, random_state=int(rng.integers(0, 99999))).reset_index(drop=True)
    df = df.iloc[:target_events].copy()

    df.insert(0, "event_id", make_uuids(len(df)))

    # Replace empty string back to None for customer_id
    df["customer_id"] = df["customer_id"].replace("", None)

    # Replace None string in utm_campaign with actual None
    df["utm_campaign"] = df["utm_campaign"].where(df["utm_campaign"].notna() & (df["utm_campaign"] != "None"), None)

    if dirty:
        from src.utils import inject_nulls
        df = inject_nulls(rng, df, ["customer_id", "traffic_source", "utm_source", "utm_medium", "utm_campaign"], rate=0.03)

    logger.info(
        f"  ↳ website_events done. {len(df):,} events. "
        f"Event dist: { df['event_type'].value_counts().to_dict() }"
    )
    return df
