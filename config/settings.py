"""
Central configuration for ShopSphere Data Generator.
All business rules, proportions, and tunables live here.
"""

from datetime import date

# ─── Time range ───────────────────────────────────────────────────────────────
START_DATE = date(2023, 1, 1)
END_DATE   = date.today()

# ─── Scale (overridable via CLI) ──────────────────────────────────────────────
DEFAULT_CUSTOMERS   = 100_000
DEFAULT_ORDERS      = 1_000_000
DEFAULT_EVENTS      = 5_000_000
DEFAULT_SEED        = 42

# ─── Geography ────────────────────────────────────────────────────────────────
COUNTRIES = {
    "India":          {"weight": 0.30, "cities": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad"]},
    "United States":  {"weight": 0.25, "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego"]},
    "Germany":        {"weight": 0.15, "cities": ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt", "Stuttgart", "Düsseldorf", "Leipzig"]},
    "United Kingdom": {"weight": 0.12, "cities": ["London", "Birmingham", "Manchester", "Glasgow", "Liverpool", "Leeds", "Sheffield", "Edinburgh"]},
    "France":         {"weight": 0.10, "cities": ["Paris", "Lyon", "Marseille", "Toulouse", "Nice", "Nantes", "Strasbourg", "Montpellier"]},
    "Netherlands":    {"weight": 0.08, "cities": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven", "Tilburg", "Groningen", "Almere"]},
}

# ─── Customer segments ────────────────────────────────────────────────────────
CUSTOMER_SEGMENTS = {
    "Whale":          {"weight": 0.05, "order_multiplier": 12.0, "avg_basket_multiplier": 3.5},
    "Loyal":          {"weight": 0.15, "order_multiplier": 5.0,  "avg_basket_multiplier": 1.8},
    "Regular":        {"weight": 0.50, "order_multiplier": 2.0,  "avg_basket_multiplier": 1.0},
    "One-Time Buyer": {"weight": 0.30, "order_multiplier": 0.3,  "avg_basket_multiplier": 0.7},
}

# ─── Acquisition channels ─────────────────────────────────────────────────────
ACQUISITION_CHANNELS = {
    "Google Ads":     0.28,
    "Facebook Ads":   0.18,
    "Organic Search": 0.22,
    "Email":          0.12,
    "Direct":         0.12,
    "LinkedIn Ads":   0.08,
}

# ─── Product categories ───────────────────────────────────────────────────────
PRODUCT_CATEGORIES = {
    "Electronics": {
        "weight": 0.20,
        "refund_rate": 0.12,
        "subcategories": ["Smartphones", "Laptops", "Headphones", "Tablets", "Cameras", "Smart Watches", "Gaming"],
        "price_range": (25, 1500),
        "margin_range": (0.15, 0.35),
    },
    "Fashion": {
        "weight": 0.25,
        "refund_rate": 0.07,
        "subcategories": ["Men's Clothing", "Women's Clothing", "Footwear", "Accessories", "Bags", "Jewelry"],
        "price_range": (10, 300),
        "margin_range": (0.40, 0.65),
    },
    "Home": {
        "weight": 0.20,
        "refund_rate": 0.04,
        "subcategories": ["Furniture", "Kitchen", "Bedding", "Decor", "Lighting", "Storage"],
        "price_range": (15, 800),
        "margin_range": (0.30, 0.55),
    },
    "Beauty": {
        "weight": 0.15,
        "refund_rate": 0.03,
        "subcategories": ["Skincare", "Makeup", "Haircare", "Fragrances", "Men's Grooming"],
        "price_range": (8, 200),
        "margin_range": (0.50, 0.75),
    },
    "Sports": {
        "weight": 0.12,
        "refund_rate": 0.05,
        "subcategories": ["Fitness Equipment", "Outdoor", "Team Sports", "Cycling", "Yoga", "Running"],
        "price_range": (12, 600),
        "margin_range": (0.35, 0.55),
    },
    "Books": {
        "weight": 0.08,
        "refund_rate": 0.02,
        "subcategories": ["Fiction", "Non-Fiction", "Technical", "Children", "Self-Help", "Biography"],
        "price_range": (5, 60),
        "margin_range": (0.20, 0.45),
    },
}

# ─── Order status ─────────────────────────────────────────────────────────────
ORDER_STATUSES = {"Completed": 0.87, "Cancelled": 0.08, "Returned": 0.05}

# ─── Payment methods ─────────────────────────────────────────────────────────
PAYMENT_METHODS = {"Card": 0.45, "UPI": 0.25, "PayPal": 0.20, "Bank Transfer": 0.10}

# ─── Refunds ──────────────────────────────────────────────────────────────────
OVERALL_REFUND_RATE = 0.05
REFUND_REASONS = ["Defective product", "Wrong item delivered", "Changed mind", "Better price elsewhere", "Damaged in transit", "Not as described"]

# ─── Seasonality multipliers (by month) ──────────────────────────────────────
SEASONALITY = {
    1:  1.00,   # January  – normal
    2:  0.75,   # February – slow
    3:  0.95,
    4:  1.00,
    5:  1.05,
    6:  1.00,
    7:  0.95,
    8:  1.00,
    9:  1.05,
    10: 1.10,
    11: 1.60,   # November – Black Friday / Diwali
    12: 1.55,   # December – Christmas
}

# ─── Website funnel conversion rates ─────────────────────────────────────────
FUNNEL_CONVERSION = {
    "page_view":    1.00,
    "product_view": 0.45,
    "add_to_cart":  0.22,
    "checkout":     0.12,
    "purchase":     0.08,
}

DEVICE_TYPES    = {"Mobile": 0.55, "Desktop": 0.35, "Tablet": 0.10}
TRAFFIC_SOURCES = {"Google Ads": 0.28, "Organic Search": 0.22, "Facebook Ads": 0.18, "Direct": 0.14, "Email": 0.12, "LinkedIn Ads": 0.06}

# ─── Support tickets ─────────────────────────────────────────────────────────
ISSUE_TYPES  = {"Delivery": 0.30, "Refund": 0.25, "Product Defect": 0.20, "Payment": 0.15, "Account": 0.10}
PRIORITIES   = {"Low": 0.50, "Medium": 0.35, "High": 0.15}
RESOLUTION_HOURS = {"Low": (24, 120), "Medium": (8, 48), "High": (1, 24)}

# ─── Marketing ───────────────────────────────────────────────────────────────
CAMPAIGN_CHANNELS = {
    "Google Ads":     {"cac": 15,  "conversion_rate": 0.035, "cpm": 8.0},
    "Facebook Ads":   {"cac": 20,  "conversion_rate": 0.022, "cpm": 6.5},
    "LinkedIn Ads":   {"cac": 75,  "conversion_rate": 0.012, "cpm": 22.0},
    "Email":          {"cac": 5,   "conversion_rate": 0.055, "cpm": 1.0},
    "Organic Search": {"cac": 8,   "conversion_rate": 0.045, "cpm": 0.0},
}

# ─── Subscription plans ───────────────────────────────────────────────────────
SUBSCRIPTION_PLANS = {"Basic": 0.50, "Premium": 0.35, "Enterprise": 0.15}
CHURN_RATE_BASE   = 0.05

# ─── Data quality flags ───────────────────────────────────────────────────────
DQ_DUPLICATE_RATE    = 0.02
DQ_NULL_RATE         = 0.03
DQ_INVALID_DATE_RATE = 0.01
DQ_BROKEN_FK_RATE    = 0.005

# ─── Output ───────────────────────────────────────────────────────────────────
OUTPUT_DIR = "data"
