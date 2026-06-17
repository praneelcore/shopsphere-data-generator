"""Generate dim_date — a date dimension spine for the warehouse."""

import numpy as np
import pandas as pd
from datetime import date, timedelta

from config.settings import DIM_DATE_START, DIM_DATE_END
from src.utils import get_logger

logger = get_logger(__name__)

# ─── Holiday definitions by country/category ──────────────────────────────────

# Fixed-date holidays (month, day) → name
FIXED_HOLIDAYS = {
    (1, 1):   "New Year's Day",
    (1, 26):  "Republic Day (India)",
    (7, 4):   "Independence Day (US)",
    (8, 15):  "Independence Day (India)",
    (10, 3):  "German Unity Day",
    (12, 25): "Christmas Day",
    (12, 26): "Boxing Day",
    (12, 31): "New Year's Eve",
}

# Ecommerce-relevant holidays (approximate fixed dates)
ECOMMERCE_HOLIDAYS = {
    (11, 11): "Singles Day",
    (11, 24): "Black Friday (approx)",
    (11, 27): "Cyber Monday (approx)",
}

# Variable holidays by year (computed or approximated)
def _get_variable_holidays(year: int) -> dict[date, str]:
    """Return variable-date holidays for a given year."""
    holidays = {}

    # Easter (using anonymous Gregorian algorithm)
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter = date(year, month, day)
    holidays[easter] = "Easter Sunday"
    holidays[easter - timedelta(days=2)] = "Good Friday"

    # US Memorial Day (last Monday of May)
    may_31 = date(year, 5, 31)
    memorial = may_31 - timedelta(days=(may_31.weekday()))  # Last Monday
    holidays[memorial] = "Memorial Day (US)"

    # US Thanksgiving (4th Thursday of November)
    nov_1 = date(year, 11, 1)
    first_thu = nov_1 + timedelta(days=(3 - nov_1.weekday()) % 7)
    thanksgiving = first_thu + timedelta(weeks=3)
    holidays[thanksgiving] = "Thanksgiving (US)"
    holidays[thanksgiving + timedelta(days=1)] = "Black Friday"

    # Diwali (approximate — varies each year, using known dates)
    diwali_dates = {
        2022: date(2022, 10, 24),
        2023: date(2023, 11, 12),
        2024: date(2024, 11, 1),
        2025: date(2025, 10, 20),
        2026: date(2026, 11, 8),
        2027: date(2027, 10, 29),
    }
    if year in diwali_dates:
        holidays[diwali_dates[year]] = "Diwali (India)"

    # Holi (approximate)
    holi_dates = {
        2022: date(2022, 3, 18),
        2023: date(2023, 3, 8),
        2024: date(2024, 3, 25),
        2025: date(2025, 3, 14),
        2026: date(2026, 3, 4),
        2027: date(2027, 3, 22),
    }
    if year in holi_dates:
        holidays[holi_dates[year]] = "Holi (India)"

    # Oktoberfest start (third Saturday of September, approx)
    sep_1 = date(year, 9, 1)
    first_sat = sep_1 + timedelta(days=(5 - sep_1.weekday()) % 7)
    oktoberfest = first_sat + timedelta(weeks=2)
    holidays[oktoberfest] = "Oktoberfest Start (Germany)"

    return holidays


def generate_dim_date() -> pd.DataFrame:
    """Generate a comprehensive date dimension table from DIM_DATE_START to DIM_DATE_END."""
    logger.info("Generating dim_date …")

    dates = pd.date_range(start=DIM_DATE_START, end=DIM_DATE_END, freq="D")
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

    # Fiscal calendar (fiscal year starts April 1)
    df["fiscal_year"] = df["date"].apply(
        lambda d: d.year if d.month >= 4 else d.year - 1
    )
    df["fiscal_quarter"] = df["month"].apply(
        lambda m: ((m - 4) % 12) // 3 + 1
    )

    # Month start/end flags
    df["is_month_start"] = df["date"].dt.is_month_start
    df["is_month_end"] = df["date"].dt.is_month_end

    # ── Build holiday lookup ──────────────────────────────────────────────────
    all_holidays: dict[date, str] = {}

    # Fixed holidays for all years in range
    for year in range(DIM_DATE_START.year, DIM_DATE_END.year + 1):
        for (m, d), name in FIXED_HOLIDAYS.items():
            try:
                all_holidays[date(year, m, d)] = name
            except ValueError:
                pass
        for (m, d), name in ECOMMERCE_HOLIDAYS.items():
            try:
                if date(year, m, d) not in all_holidays:
                    all_holidays[date(year, m, d)] = name
            except ValueError:
                pass
        # Variable holidays
        for hdate, hname in _get_variable_holidays(year).items():
            if hdate not in all_holidays:
                all_holidays[hdate] = hname

    # Map holidays to dataframe
    df["holiday_name"] = df["date"].dt.date.map(all_holidays)
    df["is_holiday"] = df["holiday_name"].notna()

    # Convert date to plain date (no time component)
    df["date"] = df["date"].dt.date

    # Add a surrogate key (YYYYMMDD integer)
    df.insert(0, "date_key", pd.to_datetime(df["date"]).dt.strftime("%Y%m%d").astype(int))

    logger.info(f"  ↳ dim_date done. {len(df):,} rows ({DIM_DATE_START} → {DIM_DATE_END})")
    return df
