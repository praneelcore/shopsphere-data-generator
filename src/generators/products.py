"""Generate the products dimension table."""

import numpy as np
import pandas as pd
from faker import Faker

from config.settings import PRODUCT_CATEGORIES
from src.utils import get_logger, make_uuids

logger = get_logger(__name__)

# Product name templates per subcategory (sampled for realism)
PRODUCT_ADJECTIVES = ["Pro", "Ultra", "Lite", "Max", "Elite", "Plus", "Smart", "Classic", "Premium", "Essential"]
PRODUCT_SUFFIXES   = ["Series", "Edition", "Collection", "Pack", "Kit", "Bundle", "Set", "Model", "Version", "Line"]


def _product_name(fake: Faker, subcat: str, rng: np.random.Generator) -> str:
    brand    = fake.company().split()[0]
    adj      = rng.choice(PRODUCT_ADJECTIVES)
    suffix   = rng.choice(PRODUCT_SUFFIXES)
    number   = rng.integers(100, 9999)
    return f"{brand} {subcat} {adj} {number} {suffix}"


def generate_products(
    n: int = 5_000,
    rng: np.random.Generator = None,
    dirty: bool = False,
) -> pd.DataFrame:
    if rng is None:
        rng = np.random.default_rng(42)

    logger.info(f"Generating {n:,} products …")
    fake = Faker()
    Faker.seed(int(rng.integers(0, 99999)))

    # ── Category / subcategory assignment ─────────────────────────────────────
    cat_names   = list(PRODUCT_CATEGORIES.keys())
    cat_weights = np.array([v["weight"] for v in PRODUCT_CATEGORIES.values()], dtype=float)
    cat_weights /= cat_weights.sum()
    categories  = rng.choice(cat_names, size=n, p=cat_weights)

    subcategories = np.array([
        rng.choice(PRODUCT_CATEGORIES[c]["subcategories"])
        for c in categories
    ], dtype=object)

    # ── Names ─────────────────────────────────────────────────────────────────
    names = np.array([
        _product_name(fake, subcategories[i], rng)
        for i in range(n)
    ], dtype=object)

    # ── Prices (Pareto: top 20% products are premium) ─────────────────────────
    costs  = np.empty(n)
    prices = np.empty(n)
    margins = np.empty(n)

    for cat in cat_names:
        mask = categories == cat
        cfg  = PRODUCT_CATEGORIES[cat]
        lo, hi = cfg["price_range"]
        mlo, mhi = cfg["margin_range"]

        # Log-normal so there's a long tail of expensive products
        mid  = (lo + hi) / 2
        p    = np.exp(rng.normal(np.log(mid), 0.6, mask.sum()))
        p    = np.clip(p, lo, hi)

        m    = rng.uniform(mlo, mhi, mask.sum())
        c    = np.round(p * (1 - m), 2)
        p    = np.round(p, 2)
        m    = np.round(m, 4)

        prices[mask]  = p
        costs[mask]   = c
        margins[mask] = m

    # ── Pareto product weight (for later order_items sampling) ─────────────────
    # Top 20% products get ~80% of demand. We encode this as a popularity_score.
    rank          = np.argsort(np.argsort(-prices))   # high price ≠ popular, so we shuffle
    popularity    = rng.pareto(1.16, n)                # Pareto(a≈1.16) gives 80/20 naturally
    popularity    = popularity / popularity.sum()

    df = pd.DataFrame({
        "product_id":       make_uuids(n),
        "product_name":     names,
        "category":         categories,
        "subcategory":      subcategories,
        "cost":             costs,
        "selling_price":    prices,
        "margin":           margins,
        "popularity_score": np.round(popularity, 8),   # internal use for sampling
    })

    if dirty:
        from src.utils import inject_nulls
        df = inject_nulls(rng, df, ["subcategory"], rate=0.02)

    logger.info(f"  ↳ products done. Avg price: ${df['selling_price'].mean():.2f}")
    return df
