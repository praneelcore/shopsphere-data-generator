# ShopSphere Data Generator

Realistic ecommerce data for a fictional global retailer — built to power an end-to-end analytics engineering portfolio.

Generates **11 production-style datasets** across ~6.3 million rows by default, covering customers, orders, products, payments, refunds, website events, support tickets, marketing campaigns, and subscriptions.

---

## Datasets

| File | Default rows | Description |
|------|-------------|-------------|
| `customers.parquet` | 100,000 | Customer dimension with segments, geo, acquisition channel |
| `products.parquet` | 5,000 | Product catalog with Pareto popularity scores |
| `orders.parquet` | ~1,000,000 | Orders with seasonal distribution |
| `order_items.parquet` | ~2,000,000 | Line items with basket-size realism |
| `payments.parquet` | ~870,000 | One payment per completed order |
| `refunds.parquet` | ~55,000 | Partial & full refunds |
| `website_events.parquet` | 5,000,000 | Full funnel: page_view → purchase |
| `support_tickets.parquet` | ~200,000 | Tickets correlated with churn |
| `marketing_campaigns.parquet` | 80 | Campaign definitions |
| `campaign_spend.parquet` | ~30,000 | Daily spend/impressions/conversions |
| `subscriptions.parquet` | ~45,000 | SaaS subscriptions with churn |

---

## Quick Start

### 1. Install dependencies

```bash
cd fake-company-data-generator
pip install -r requirements.txt
```

### 2. Generate data (default scale)

```bash
python generate.py
```

This writes all parquet files to `data/`.

### 3. Custom scale

```bash
# Smaller for development
python generate.py --customers 10000 --orders 100000 --events 500000

# Full production scale
python generate.py --customers 100000 --orders 1000000 --events 5000000

# With dirty data for DQ projects
python generate.py --dirty

# Fixed seed for reproducibility
python generate.py --seed 42
```

---

## CLI Reference

```
Usage: python generate.py [OPTIONS]

Options:
  --customers  INTEGER  Number of customers          [default: 100000]
  --orders     INTEGER  Target number of orders      [default: 1000000]
  --events     INTEGER  Target number of web events  [default: 5000000]
  --products   INTEGER  Number of products           [default: 5000]
  --seed       INTEGER  Random seed                  [default: 42]
  --dirty               Inject data quality issues
  --output     TEXT     Output directory             [default: data]
```

---

## Business Rules Implemented

| Rule | Implementation |
|------|---------------|
| 80/20 product revenue | Pareto popularity scores on products |
| Seasonal peaks (Nov/Dec) | Monthly multipliers on order date sampling |
| Whale customers | 12× order frequency, 3.5× basket size |
| One-Time Buyers | Capped at 1 order, high churn |
| Funnel conversion | page_view → purchase at real drop-off rates |
| Churn correlation | Support ticket volume → subscription churn |
| Electronics refunds | Higher refund rate for Electronics category |
| Google Ads ROI | Highest conversion rate in campaign spend |
| LinkedIn CAC | Highest cost-per-acquisition |

---

## Loading into PostgreSQL

### Prerequisites

```bash
pip install psycopg2-binary sqlalchemy
```

### Create the database

```sql
-- In psql
CREATE DATABASE shopsphere;
```

### Load all tables

```bash
python load_postgres.py \
  --db-url postgresql://postgres:password@localhost:5432/shopsphere \
  --schema raw
```

This creates a `raw` schema and loads all 11 tables in FK-safe order.

### Load options

```bash
# Load a single table
python load_postgres.py \
  --db-url postgresql://postgres:password@localhost:5432/shopsphere \
  --table customers

# Append instead of replace
python load_postgres.py \
  --db-url postgresql://postgres:password@localhost:5432/shopsphere \
  --if-exists append

# Tune batch size (bigger = faster, more memory)
python load_postgres.py \
  --db-url postgresql://postgres:password@localhost:5432/shopsphere \
  --chunk-size 50000
```

### Verify in psql

```sql
SET search_path TO raw;

-- Row counts
SELECT
  schemaname,
  relname   AS table_name,
  n_live_tup AS row_count
FROM pg_stat_user_tables
WHERE schemaname = 'raw'
ORDER BY n_live_tup DESC;

-- Quick business sanity checks
SELECT customer_segment, COUNT(*) FROM customers GROUP BY 1 ORDER BY 2 DESC;
SELECT status, COUNT(*) FROM orders GROUP BY 1;
SELECT channel, SUM(spend) FROM campaign_spend GROUP BY 1 ORDER BY 2 DESC;
```

---

## Project Structure

```
fake-company-data-generator/
├── generate.py              # Entry point
├── load_postgres.py         # PostgreSQL loader
├── requirements.txt
├── pyproject.toml
├── README.md
├── config/
│   └── settings.py          # All business rules & tunables
├── src/
│   ├── main.py              # CLI orchestrator
│   ├── utils.py             # Shared helpers (UUID, dates, parquet IO)
│   └── generators/
│       ├── customers.py
│       ├── products.py
│       ├── orders.py        # orders + order_items
│       ├── payments.py      # payments + refunds
│       ├── website_events.py
│       ├── support_tickets.py
│       ├── marketing.py     # campaigns + spend
│       └── subscriptions.py
└── data/                    # Generated parquet files (git-ignored)
```

---

## dbt / BigQuery Next Steps

Once data is in PostgreSQL, a typical dbt project layout:

```
models/
  staging/          # 1:1 with raw tables, light type casts
  intermediate/     # Joins, deduplication
  marts/
    core/           # dim_customers, dim_products, fct_orders
    marketing/      # fct_campaign_performance, rpt_attribution
    product/        # fct_funnel, rpt_cohort_retention
    finance/        # fct_revenue, rpt_refunds
```

---

## Data Quality Mode

Run with `--dirty` to inject:

- **Null values** in non-critical columns (~3%)
- **Duplicate rows** (~2%)
- **Invalid date strings** (~0.5%)

Use this for building dbt tests, Great Expectations suites, or Soda checks.
