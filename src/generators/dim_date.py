"""Generate dim_date — a date dimension spine for the warehouse."""

import numpy as np
import pandas as pd

from config.settings import START_DATE, END_DATE
from src.utils import get_logger

logger = get_logger(__name__)

# US federal holidays (static dates — not exhaustive but covers the big ones)
US_HOLIDAYS = {
    (1, 1): "New Year's Day",
    (7, 4): "Independence Day",
    (12, 25): "Christmas Day",
    (12, 31): "New Year's Eve",
}

# Major retail / ecommerce holidays by approximate date
ECOMMERCE_HOLIDAYS = {
    (11, 11): "Singles Day",
    (11, 24): "Black Friday (approx)",
    (11, 27): "Cyber Monday (approx)",
    (12, 26): "Boxing Day",
}


def generate_dim_date() -> pd.DataFrame:
    """Generate a comprehensive date dimension table from START_DATE to END_DATE."""
    logger.info("Generating dim_date …")

    dates = pd.date_range(start=START_DATE, end=END_DATE, freq="D")
    df = pd.DataFrame({"date": dates})

    # Calendar attributes
    df["year"] = df["date"].dt.year
    df["quarter"] = df["date"].dt.quarter
    df["month"] = df["date"].dt.month
    df["month_name"] = df["date"].dt.month_name()
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["day_of_month"] = df["date"].dt.day
    df["day_of_week"] = df["date"].dt.dayofweek  # 0=Monday, 6=Sunday
    df["day_name"] = df["date"].dt.day_name()
    df["is_weekend"] = df["day_of_week"].isin([5, 6])

    # ISO week attributes
    df["iso_year"] = df["date"].dt.isocalendar().year.astype(int)
    df["iso_week"] = df["date"].dt.isocalendar().week.astype(int)

    # Fiscal calendar (assuming fiscal year starts April 1)
    df["fiscal_year"] = df["date"].apply(
        lambda d: d.year if d.month >= 4 else d.year - 1
    )
    df["fiscal_quarter"] = df["month"].apply(
        lambda m: ((m - 4) % 12) // 3 + 1
    )

    # Month start/end flags
    df["is_month_start"] = df["date"].dt.is_month_start
    df["is_month_end"] = df["date"].dt.is_month_end

    # Holiday flags
    def _get_holiday(row):
        key = (row["month"], row["day_of_month"])
        if key in US_HOLIDAYS:
            return US_HOLIDAYS[key]
        if key in ECOMMERCE_HOLIDAYS:
            return ECOMMERCE_HOLIDAYS[key]
        return None

    df["holiday_name"] = df.apply(_get_holiday, axis=1)
    df["is_holiday"] = df["holiday_name"].notna()

    # Convert date to plain date (no time component)
    df["date"] = df["date"].dt.date

    # Add a surrogate key (YYYYMMDD integer)
    df.insert(0, "date_key", pd.to_datetime(df["date"]).dt.strftime("%Y%m%d").astype(int))

    logger.info(f"  ↳ dim_date done. {len(df):,} rows ({START_DATE} → {END_DATE})")
    return df
