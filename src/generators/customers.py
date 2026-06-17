"""Generate the customers dimension table."""

import numpy as np
import pandas as pd
from faker import Faker

from config.settings import (
    COUNTRIES, CUSTOMER_SEGMENTS, ACQUISITION_CHANNELS,
    START_DATE, END_DATE,
)
from src.utils import get_logger, make_uuids, random_dates_array, weighted_choice

log = Faker()  # used only for email generation
logger = get_logger(__name__)


def generate_customers(
    n: int,
    rng: np.random.Generator,
    dirty: bool = False,
) -> pd.DataFrame:
    logger.info(f"Generating {n:,} customers …")

    # ── IDs & signup dates ────────────────────────────────────────────────────
    customer_ids = make_uuids(n)
    dates        = random_dates_array(rng, START_DATE, END_DATE, n)

    # ── Geography ─────────────────────────────────────────────────────────────
    country_names   = list(COUNTRIES.keys())
    country_weights = np.array([v["weight"] for v in COUNTRIES.values()], dtype=float)
    country_weights /= country_weights.sum()
    countries = rng.choice(country_names, size=n, p=country_weights)

    cities = np.array([
        rng.choice(COUNTRIES[c]["cities"])
        for c in countries
    ], dtype=object)

    # ── Segments ─────────────────────────────────────────────────────────────
    seg_names   = list(CUSTOMER_SEGMENTS.keys())
    seg_weights = np.array([v["weight"] for v in CUSTOMER_SEGMENTS.values()], dtype=float)
    seg_weights /= seg_weights.sum()
    segments = rng.choice(seg_names, size=n, p=seg_weights)

    # ── Acquisition channels ──────────────────────────────────────────────────
    channels = weighted_choice(rng, ACQUISITION_CHANNELS, n)

    # ── Emails (fast vectorised faker) ────────────────────────────────────────
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "proton.me", "icloud.com"]
    dom_choice = rng.choice(domains, size=n)

    fake = Faker()
    Faker.seed(int(rng.integers(0, 99999)))
    usernames = np.array([fake.user_name() for _ in range(n)], dtype=object)
    # make unique by appending a short numeric suffix where needed
    uname_unique, counts = np.unique(usernames, return_counts=True)
    for uname in uname_unique[counts > 1]:
        idx = np.where(usernames == uname)[0]
        for j, i in enumerate(idx[1:], start=1):
            usernames[i] = f"{uname}{j}"
    emails = np.array([f"{u}@{d}" for u, d in zip(usernames, dom_choice)], dtype=object)

    # ── is_active (churn model: older customers more likely inactive) ─────────
    # Probability of still being active decreases with tenure
    signup_days_ago = np.array([(END_DATE - pd.Timestamp(d).date()).days for d in dates])
    churn_prob = np.clip(signup_days_ago / 1000 * 0.35, 0.0, 0.40)
    is_active = (rng.random(n) > churn_prob).astype(bool)
    # Whale & Loyal are stickier
    whale_mask = segments == "Whale"
    loyal_mask = segments == "Loyal"
    is_active[whale_mask] = (rng.random(whale_mask.sum()) > 0.05)
    is_active[loyal_mask] = (rng.random(loyal_mask.sum()) > 0.10)
    # One-Time Buyers churn fast
    otb_mask = segments == "One-Time Buyer"
    is_active[otb_mask] = (rng.random(otb_mask.sum()) > 0.55)

    df = pd.DataFrame({
        "customer_id":         customer_ids,
        "signup_date":         pd.to_datetime(dates).to_series().dt.date.values,
        "country":             countries,
        "city":                cities,
        "acquisition_channel": channels,
        "customer_segment":    segments,
        "email":               emails,
        "is_active":           is_active,
    })

    # ── Optional dirty data ───────────────────────────────────────────────────
    if dirty:
        from src.utils import inject_nulls, inject_duplicates
        df = inject_nulls(rng, df, ["city", "acquisition_channel"], rate=0.03)
        df = inject_duplicates(rng, df, rate=0.02)
        logger.info("  ↳ dirty mode: nulls & duplicates injected")

    logger.info(f"  ↳ customers done. Segments: { {s: (segments == s).sum() for s in seg_names} }")
    return df
