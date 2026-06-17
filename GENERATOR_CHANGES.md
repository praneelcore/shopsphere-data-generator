# ShopSphere Data Generator — Required Changes

> Changes needed to make the generator portfolio-ready and support all 5 projects properly.

---

## Priority 1: Batch Mode (Enables Incremental dbt Models)

### Problem
All 9.2M rows are generated in one shot. No way to test incremental loads.

### Solution
Add a `--batch` mode that simulates daily data arrivals.

### CLI Interface

```bash
# Full initial load (existing behavior)
python generate.py --mode full

# Generate one day's worth of new data (appends to existing tables)
python generate.py --mode batch --date 2024-03-15

# Generate a range of days (useful for backfilling)
python generate.py --mode batch --start-date 2024-03-01 --end-date 2024-03-31

# Generate N days from where the data left off
python generate.py --mode batch --days 30
```

### What `--batch` generates per day

| Table | Rows/Day | Logic |
|-------|----------|-------|
| orders | ~800 (baseline), ~1,300 (Nov/Dec) | Respect seasonality |
| order_items | ~1,600 | 2.07× orders |
| payments | ~700 | 87% of orders (completed only) |
| refunds | ~55 | 5% return rate |
| website_events | ~14,000 | Funnel ratios preserved |
| support_tickets | ~50 | Correlated with order volume |
| campaign_spend | 1 row per active campaign | Daily granularity already exists |
| subscriptions | ~30 new, ~6 churns | Net growth with churn |
| customers | ~50-100 new signups | Acquisition rate |

### Implementation Notes

- INSERT into existing tables (never truncate in batch mode)
- Maintain all business rules (Pareto, seasonality, segment distribution)
- New customers get assigned segments based on existing ratios
- New orders reference existing customers (weighted toward active ones)
- Track `last_generated_date` in a metadata file or table to know where to resume
- Print summary after each batch: "Generated 823 orders, 1,641 items, 14,221 events for 2024-03-15"

---

## Priority 2: Dirty Mode (Enables Project 4 — Data Quality)

### Problem
Current data is perfectly clean. Project 4 needs realistic data quality issues to detect.

### CLI Interface

```bash
# Generate with injected quality issues
python generate.py --mode full --dirty

# Also works with batch mode
python generate.py --mode batch --date 2024-03-15 --dirty
```

### What `--dirty` injects

| Issue Type | Rate | Where | Example |
|-----------|------|-------|---------|
| NULL values | ~3% | Non-key columns | `orders.status = NULL` |
| Duplicate rows | ~2% | order_items, events | Exact duplicate rows |
| Invalid dates | ~0.5% | order_date, payment_date | `'2024-13-45'`, `'not-a-date'` |
| Broken foreign keys | ~0.3% | order_items.product_id | References non-existent product |
| Future timestamps | ~0.2% | website_events.event_timestamp | Events "from tomorrow" |
| Negative amounts | ~0.1% | payments.payment_amount | `-50.00` |
| Schema drift | occasional | Any table | Extra column, changed type |
| Late arrivals | ~1% | orders, events | `order_date` = 3 weeks ago but inserted today |

### Implementation Notes

- Use a `--dirty-seed` flag for reproducible corruption (same seed = same issues)
- Log all injected issues to `dirty_manifest.json` so Project 4 can validate detection
- Example manifest entry:
  ```json
  {
    "table": "orders",
    "issue": "null_value",
    "column": "status",
    "row_ids": ["uuid-1", "uuid-2", "uuid-3"],
    "count": 3
  }
  ```
- This manifest becomes your "answer key" — your quality framework should catch everything in it

---

## Priority 3: Scale Mode (Dev/Staging/Prod Sizes)

### Problem
Full dataset (9.2M rows) is slow for development iteration. Need smaller sizes for testing dbt models.

### CLI Interface

```bash
# Dev — fast iteration (seconds to generate)
python generate.py --mode full --scale dev

# Staging — medium, for integration testing
python generate.py --mode full --scale staging

# Prod — full dataset (current behavior)
python generate.py --mode full --scale prod
```

### Scale Definitions

| Scale | Customers | Orders | Events | Total Rows | Use Case |
|-------|-----------|--------|--------|------------|----------|
| `dev` | 1,000 | 10,000 | 50,000 | ~100K | dbt model development, quick iteration |
| `staging` | 10,000 | 100,000 | 500,000 | ~900K | Integration testing, CI/CD pipelines |
| `prod` | 100,000 | 1,000,000 | 5,000,000 | ~9.2M | Full portfolio demo, dashboards |

### Implementation Notes

- All ratios and business rules remain the same at every scale
- Pareto distribution still holds (top 20% products = 80% revenue)
- Segment proportions stay constant (5% Whale, 15% Loyal, etc.)
- Use a multiplier approach: `base_orders = scale_factor * 1_000_000`

---

## Priority 4: New Table — `dim_date`

### Problem
No date dimension table. Every serious warehouse needs one for time-based analysis.

### What to Generate

| Column | Type | Example |
|--------|------|---------|
| date_key | DATE | 2024-03-15 |
| year | INT | 2024 |
| quarter | INT | 1 |
| month | INT | 3 |
| month_name | VARCHAR | March |
| week_of_year | INT | 11 |
| day_of_week | INT | 5 (Friday) |
| day_name | VARCHAR | Friday |
| is_weekend | BOOLEAN | false |
| is_holiday | BOOLEAN | false |
| holiday_name | VARCHAR | NULL |
| fiscal_quarter | INT | 4 (if fiscal year starts April) |
| fiscal_year | INT | 2024 |

### Date Range
- 2022-01-01 → 2027-12-31 (buffer on both sides of data range)
- ~2,192 rows total

### Holidays to Include
- India: Diwali, Holi, Republic Day, Independence Day
- US: Thanksgiving, Black Friday, July 4th, Memorial Day
- Germany: Christmas Markets, Oktoberfest, Reunification Day
- Generic: New Year, Christmas, Easter

### Implementation Notes

- Generate as a CSV seed file (dbt can load it via `dbt seed`)
- OR generate into PostgreSQL with everything else
- Holidays drive seasonality — orders spike around holidays
- This table is used in every project for time-based joins

---

## Priority 5: UTM Parameters on `website_events`

### Problem
No link between marketing campaigns and website sessions. Attribution (Project 3) requires fuzzy matching.

### New Columns on `website_events`

| Column | Type | Example |
|--------|------|---------|
| utm_source | VARCHAR | google, facebook, linkedin, email, (NULL for direct/organic) |
| utm_medium | VARCHAR | cpc, social, email, organic |
| utm_campaign | VARCHAR | spring_sale_2024, brand_awareness_q1 |

### Logic

- ~28% of events from Google Ads → `utm_source='google', utm_medium='cpc'`
- ~18% from Facebook Ads → `utm_source='facebook', utm_medium='social'`
- ~6% from LinkedIn Ads → `utm_source='linkedin', utm_medium='cpc'`
- ~12% from Email → `utm_source='email', utm_medium='email'`
- ~22% Organic Search → `utm_source='google', utm_medium='organic'`, utm_campaign=NULL
- ~14% Direct → All UTM fields NULL

### Tie to `marketing_campaigns`
- `utm_campaign` value should match `marketing_campaigns.campaign_name` (slugified)
- Only campaigns active on that date should appear
- This creates a clean join path: `events.utm_campaign → campaigns.campaign_name`

---

## Priority 6: Subscription Pricing

### Problem
`subscriptions` has `plan_type` but no price. Can't calculate MRR/ARR.

### New Columns on `subscriptions`

| Column | Type | Example |
|--------|------|---------|
| monthly_price | NUMERIC | 9.99, 29.99, 99.99 |
| billing_cycle | VARCHAR | monthly, annual |
| annual_discount | NUMERIC | 0.20 (20% off for annual) |

### Pricing

| Plan | Monthly | Annual (per month) |
|------|---------|-------------------|
| Basic | $9.99 | $7.99 |
| Premium | $29.99 | $23.99 |
| Enterprise | $99.99 | $79.99 |

### Implementation Notes
- ~60% monthly, ~40% annual billing
- This enables: MRR, ARR, net revenue retention, expansion revenue
- Churned subscriptions stop contributing to MRR from `end_date`

---

## Priority 7: Product Reviews Table (New)

### Problem
No customer feedback data. Limits Customer 360 and product analytics.

### Schema

| Column | Type | Description |
|--------|------|-------------|
| review_id | UUID | Primary key |
| customer_id | UUID | FK → customers |
| product_id | UUID | FK → products |
| order_id | UUID | FK → orders (review tied to purchase) |
| rating | INT | 1-5 stars |
| review_date | DATE | 3-30 days after order_date |
| review_text | VARCHAR | Short Faker-generated text (optional) |

### Business Rules

- ~35% of completed orders get a review
- Rating distribution: skewed positive (mean ~3.8)
- Electronics: more polarized (more 1s and 5s)
- Whale customers review more often (~60%)
- Products with high refund rates have lower avg ratings
- Generate ~300K reviews total

### Join Path
```
customers → orders → order_items → products
                  ↘ product_reviews ↗
```

---

## Priority 8: Page URL on `website_events`

### Problem
Can't do path analysis or session reconstruction without knowing which pages were viewed.

### New Columns on `website_events`

| Column | Type | Example |
|--------|------|---------|
| page_url | VARCHAR | /products/electronics/headphones-pro |
| referrer_url | VARCHAR | /search?q=headphones |

### URL Patterns by Event Type

| Event Type | Page URL Pattern |
|-----------|-----------------|
| page_view | `/`, `/products`, `/products/{category}`, `/about`, `/deals` |
| search | `/search?q={term}` |
| product_view | `/products/{category}/{product-slug}` |
| add_to_cart | `/products/{category}/{product-slug}` (same as product_view) |
| checkout | `/checkout` |
| purchase | `/checkout/confirmation` |

### Implementation Notes
- Product slugs derived from `products.product_name` (slugified)
- Search terms: realistic product-related keywords
- Referrer follows logical flow (search referrer for product_view, product referrer for add_to_cart)
- Enables: path analysis, landing page analysis, exit page analysis

---

## Summary: Implementation Order

| # | Change | Effort | Unlocks |
|---|--------|--------|---------|
| 1 | Batch mode | Medium | Incremental dbt testing (all projects) |
| 2 | Dirty mode | Medium | Project 4 (Data Quality) |
| 3 | Scale mode | Low | Faster dev iteration |
| 4 | dim_date | Low | Time-based analysis (all projects) |
| 5 | UTM params | Low | Project 3 (Attribution) — clean joins |
| 6 | Subscription pricing | Low | MRR/ARR metrics in Project 5 |
| 7 | Product reviews table | Medium | Customer 360, Product Analytics |
| 8 | Page URLs | Medium | Session/path analysis in Project 2 |

### Recommended Order of Implementation
1. **Scale mode** (quick win, makes dev faster immediately)
2. **dim_date** (CSV seed, 30 minutes of work)
3. **UTM params** (small change, big impact on Project 3)
4. **Subscription pricing** (3 columns, straightforward)
5. **Batch mode** (most important, but needs more design thought)
6. **Page URLs** (enriches events significantly)
7. **Product reviews** (new table, medium effort)
8. **Dirty mode** (save for when you start Project 4)

---

## Quick Validation Checklist

After implementing changes, verify:

- [ ] `--scale dev` generates in under 30 seconds
- [ ] `--batch --date X` appends without duplicating existing data
- [ ] `--dirty` issues are logged to `dirty_manifest.json`
- [ ] UTM values match active campaigns on that date
- [ ] dim_date covers full data range with correct holidays
- [ ] Product reviews reference only completed orders
- [ ] Page URLs follow logical funnel sequence
- [ ] All FK relationships still hold (except in dirty mode)
- [ ] Business rules (Pareto, seasonality, segments) hold at all scales
