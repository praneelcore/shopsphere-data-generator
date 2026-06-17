"""Generate marketing_campaigns and campaign_spend tables."""

import numpy as np
import pandas as pd
from datetime import timedelta

from config.settings import CAMPAIGN_CHANNELS, SEASONALITY, START_DATE, END_DATE
from src.utils import get_logger, make_uuids, seasonal_weights

logger = get_logger(__name__)

CAMPAIGN_NAME_TEMPLATES = {
    "Google Ads":     ["Search Brand",   "Shopping Catalog", "Performance Max", "Remarketing",     "Competitor"],
    "Facebook Ads":   ["Awareness Q1",   "Retargeting",      "Lookalike LTV",   "Video Engagement","Dynamic Ads"],
    "LinkedIn Ads":   ["B2B Outreach",   "Lead Gen Form",    "Sponsored Content","InMail Blast",   "Brand Lift"],
    "Email":          ["Welcome Series", "Cart Abandonment", "Win-Back",         "VIP Loyalty",    "Newsletter"],
    "Organic Search": ["SEO Blog Posts", "Product Pages",    "Category Landing", "FAQ Content",    "Comparison Pages"],
}


def generate_marketing_campaigns(
    rng: np.random.Generator,
    n_campaigns: int = 80,
) -> pd.DataFrame:
    logger.info(f"Generating {n_campaigns} marketing campaigns …")

    channels = list(CAMPAIGN_CHANNELS.keys())
    rows = []

    for _ in range(n_campaigns):
        channel = rng.choice(channels)
        names   = CAMPAIGN_NAME_TEMPLATES[channel]
        name_base = rng.choice(names)
        year   = rng.choice([2023, 2024, 2025])
        quarter = rng.choice([1, 2, 3, 4])
        start_m = (quarter - 1) * 3 + 1
        end_m   = start_m + rng.integers(1, 4)

        from datetime import date
        start = date(year, start_m, 1)
        try:
            end = date(year, min(end_m, 12), 28)
        except ValueError:
            end = date(year, 12, 28)

        rows.append({
            "campaign_id":   str(make_uuids(1)[0]),
            "campaign_name": f"{name_base} – {channel} {year} Q{quarter}",
            "channel":       channel,
            "start_date":    start,
            "end_date":      end,
        })

    df = pd.DataFrame(rows)
    logger.info(f"  ↳ campaigns done. {len(df)} rows.")
    return df


def generate_campaign_spend(
    campaigns: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    logger.info("Generating campaign_spend …")

    rows = []
    for _, camp in campaigns.iterrows():
        cfg     = CAMPAIGN_CHANNELS[camp["channel"]]
        ctr     = cfg["conversion_rate"]
        cpm     = cfg["cpm"]
        cac     = cfg["cac"]

        # Day-by-day spend for each campaign
        start = pd.Timestamp(camp["start_date"])
        end   = pd.Timestamp(camp["end_date"])
        dates = pd.date_range(start, end, freq="D")

        # Base daily budget: random between 200-5000 USD depending on channel
        daily_budget = rng.uniform(200, 5000)
        if camp["channel"] == "LinkedIn Ads":
            daily_budget = rng.uniform(500, 3000)   # LinkedIn is expensive
        elif camp["channel"] == "Organic Search":
            daily_budget = rng.uniform(0, 50)        # near-zero cost

        for d in dates:
            month = d.month
            mult  = SEASONALITY.get(month, 1.0)
            spend = round(daily_budget * mult * rng.uniform(0.85, 1.15), 2)

            if cpm > 0:
                impressions = int(spend / cpm * 1000 * rng.uniform(0.9, 1.1))
            else:
                impressions = int(rng.uniform(5000, 50000) * mult)

            clicks      = int(impressions * rng.uniform(0.01, 0.05))
            conversions = int(clicks * ctr * rng.uniform(0.85, 1.15))

            rows.append({
                "campaign_spend_id": str(make_uuids(1)[0]),
                "campaign_id":       camp["campaign_id"],
                "date":              d.date(),
                "impressions":       impressions,
                "clicks":            clicks,
                "conversions":       conversions,
                "spend":             spend,
            })

    df = pd.DataFrame(rows)
    logger.info(f"  ↳ campaign_spend done. {len(df):,} rows. Total spend: ${df['spend'].sum():,.2f}")
    return df
