"""Generate product_reviews table."""

import numpy as np
import pandas as pd

from config.settings import PRODUCT_CATEGORIES
from src.utils import get_logger, make_uuids

logger = get_logger(__name__)

# Rating distributions (skewed positive, mean ~3.8)
BASE_RATING_PROBS = np.array([0.05, 0.08, 0.15, 0.32, 0.40])  # 1-5 stars

# Electronics are more polarized
ELECTRONICS_RATING_PROBS = np.array([0.12, 0.08, 0.10, 0.25, 0.45])

# Short review text templates by rating
REVIEW_TEMPLATES = {
    1: [
        "Terrible quality. Would not recommend.",
        "Broke after first use. Very disappointed.",
        "Nothing like the description. Complete waste.",
        "Worst purchase ever. Returning immediately.",
        "Do not buy this. Absolute garbage.",
    ],
    2: [
        "Below expectations. Not worth the price.",
        "Mediocre at best. Expected much better.",
        "Packaging was damaged and product is subpar.",
        "Does the job but barely. Disappointed.",
        "Quality is questionable for this price point.",
    ],
    3: [
        "Decent product. Nothing special.",
        "Average quality. Gets the job done.",
        "It's okay. Not great, not terrible.",
        "Fair for the price. Could be better.",
        "Meets basic expectations, nothing more.",
    ],
    4: [
        "Good product! Would buy again.",
        "Really happy with this purchase.",
        "Great value for money. Recommended.",
        "Solid quality. Works as advertised.",
        "Very satisfied. Fast shipping too.",
    ],
    5: [
        "Absolutely love it! Perfect in every way.",
        "Best purchase I've made this year!",
        "Exceeded all expectations. Amazing quality.",
        "Five stars! Can't recommend enough.",
        "Outstanding product. Will buy more from this brand.",
    ],
}


def generate_reviews(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    products: pd.DataFrame,
    customers: pd.DataFrame,
    rng: np.random.Generator,
    dirty: bool = False,
) -> pd.DataFrame:
    """Generate product reviews tied to completed orders."""
    logger.info("Generating product_reviews …")

    # Only completed orders can have reviews
    completed_orders = orders[orders["status"] == "Completed"].copy()

    # Merge customer segment info
    completed_orders = completed_orders.merge(
        customers[["customer_id", "customer_segment"]],
        on="customer_id",
        how="left",
    )

    # Review probability by segment
    review_prob = completed_orders["customer_segment"].map({
        "Whale": 0.60,
        "Loyal": 0.45,
        "Regular": 0.35,
        "One-Time Buyer": 0.25,
    }).values

    # Determine which orders get reviews
    review_mask = rng.random(len(completed_orders)) < review_prob
    reviewed_orders = completed_orders[review_mask].copy()

    n_reviews = len(reviewed_orders)
    logger.info(f"  ↳ {n_reviews:,} orders will have reviews ({n_reviews/len(completed_orders)*100:.1f}% of completed orders)")

    # Get the order items for reviewed orders to determine which product was reviewed
    reviewed_items = order_items[order_items["order_id"].isin(reviewed_orders["order_id"])].copy()

    # Pick one item per order to review (first item by default for simplicity)
    reviewed_items = reviewed_items.groupby("order_id").first().reset_index()

    # Merge with order info
    review_data = reviewed_orders[["order_id", "customer_id", "order_date"]].merge(
        reviewed_items[["order_id", "product_id"]],
        on="order_id",
        how="inner",
    )

    n = len(review_data)

    # Get product categories for rating distribution
    product_cats = products.set_index("product_id")["category"].to_dict()
    review_data["category"] = review_data["product_id"].map(product_cats)

    # Get product refund rates for rating correlation
    cat_refund_rates = {cat: info["refund_rate"] for cat, info in PRODUCT_CATEGORIES.items()}
    review_data["refund_rate"] = review_data["category"].map(cat_refund_rates).fillna(0.05)

    # ── Generate ratings ─────────────────────────────────────────────────────
    ratings = np.zeros(n, dtype=int)

    # Electronics get polarized distribution
    electronics_mask = review_data["category"].values == "Electronics"
    n_elec = electronics_mask.sum()
    n_other = n - n_elec

    if n_elec > 0:
        ratings[electronics_mask] = rng.choice(
            [1, 2, 3, 4, 5], size=n_elec, p=ELECTRONICS_RATING_PROBS
        )
    if n_other > 0:
        # Adjust base rating by refund rate (higher refund = lower ratings)
        other_refund = review_data["refund_rate"].values[~electronics_mask]
        # Shift probs slightly toward lower ratings for high-refund products
        for i, idx in enumerate(np.where(~electronics_mask)[0]):
            adj = other_refund[i] * 2  # max shift ~0.24 for electronics-like
            probs = BASE_RATING_PROBS.copy()
            probs[0] += adj * 0.5
            probs[1] += adj * 0.3
            probs[4] -= adj * 0.5
            probs[3] -= adj * 0.3
            probs = np.clip(probs, 0.01, None)
            probs /= probs.sum()
            ratings[idx] = rng.choice([1, 2, 3, 4, 5], p=probs)

    # ── Generate review dates (3-30 days after order) ────────────────────────
    days_after = rng.integers(3, 31, size=n)
    order_dates = pd.to_datetime(review_data["order_date"].values)
    review_dates = order_dates + pd.to_timedelta(days_after, unit="D")

    # ── Generate review text ─────────────────────────────────────────────────
    review_texts = np.array([
        rng.choice(REVIEW_TEMPLATES[r]) for r in ratings
    ], dtype=object)

    # ── Build DataFrame ──────────────────────────────────────────────────────
    df = pd.DataFrame({
        "review_id":    make_uuids(n),
        "customer_id":  review_data["customer_id"].values,
        "product_id":   review_data["product_id"].values,
        "order_id":     review_data["order_id"].values,
        "rating":       ratings,
        "review_date":  review_dates.date,
        "review_text":  review_texts,
    })

    if dirty:
        from src.utils import inject_nulls
        df = inject_nulls(rng, df, ["review_text", "rating"], rate=0.02)

    logger.info(
        f"  ↳ product_reviews done. {len(df):,} rows. "
        f"Avg rating: {ratings.mean():.2f}. "
        f"Dist: {dict(zip(*np.unique(ratings, return_counts=True)))}"
    )
    return df
