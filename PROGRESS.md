# ShopSphere Data Generator — Progress Notes

## What's Been Done

### Infrastructure / Git
- Renamed project from `fake-company-data-generator` → `shopsphere-data-generator` (README updated)
- Added `prompt.md` and `DATA_DICTIONARY.md` to `.gitignore`, removed from tracking
- Installed `gh` CLI and authenticated
- PRs created: #1 (README rename), #3 (schema enhancements), #4 (ERD diagram)
- Created `ERD.md` with full Mermaid entity relationship diagram

### Generator Enhancements (Implemented & Tested)

1. **dim_date table** (`src/generators/dim_date.py`)
   - Extended range: 2022-01-01 → 2027-12-31 (~2,191 rows)
   - Fiscal year/quarter (starts April 1)
   - ISO week, weekday flags, month start/end
   - Holidays: US (Thanksgiving, Black Friday, July 4th, Memorial Day), India (Diwali, Holi, Republic Day, Independence Day), Germany (Unity Day, Oktoberfest), generic (Easter, Christmas, New Year)

2. **UTM params on website_events** (`src/generators/website_events.py`)
   - `utm_source`, `utm_medium`, `utm_campaign` columns
   - Aligned with `traffic_source` for consistency
   - `utm_campaign` values pulled from actual `marketing_campaigns` table for clean joins

3. **page_url on website_events**
   - Context-aware URLs mapped by event type (checkout → `/checkout/payment`, etc.)

4. **utm_campaign on marketing_campaigns** (`src/generators/marketing.py`)
   - Slug-style identifiers (e.g., `performance_max_2024_q1`)
   - Joinable to `website_events.utm_campaign`

5. **Subscription pricing** (`src/generators/subscriptions.py`)
   - `monthly_price`: Basic=$9.99/$7.99, Premium=$29.99/$23.99, Enterprise=$99.99/$79.99
   - `billing_cycle`: monthly (60%) / annual (40%)
   - `annual_discount`: 0.20 for annual, 0.00 for monthly

6. **Product reviews table** (`src/generators/reviews.py`) — NEW TABLE
   - ~35% of completed orders get reviewed
   - Rating distribution skewed positive (mean ~3.8)
   - Electronics more polarized, high-refund products get lower ratings
   - Whale customers review at 60% rate
   - Review text templates by rating level
   - Linked via `order_id`, `customer_id`, `product_id`

7. **Scale mode** (`--scale dev|staging|prod`)
   - `dev`: 1K customers, 10K orders, 50K events (~100K rows, <1 second)
   - `staging`: 10K customers, 100K orders, 500K events (~900K rows)
   - `prod`: 100K customers, 1M orders, 5M events (~9.2M rows)

8. **Batch mode** (`--mode batch`)
   - Daily incremental generation with `--date`, `--start-date/--end-date`, or `--days`
   - Appends to existing parquet files
   - Respects seasonality multipliers
   - Tracks `last_generated_date` in `generation_metadata.json`
   - Batch functions added: `generate_orders_batch`, `generate_support_tickets_batch`, `generate_campaign_spend_daily`

9. **Enhanced dirty mode** (`--dirty`)
   - Invalid dates (~0.5%) on orders
   - Broken foreign keys (~0.3%) on order_items.product_id
   - Future timestamps (~0.2%) on website_events
   - Negative amounts (~0.1%) on payments
   - Outputs `dirty_manifest.json` — answer key for Project 4 validation
   - Manifest includes table, issue type, column, affected row IDs, count

10. **load_postgres.py updated**
    - Added `dim_date` and `product_reviews` to TABLE_ORDER
    - Added dtype overrides for new columns (monthly_price, annual_discount, rating, dim_date integers/booleans)

### Files Modified
- `config/settings.py` — SCALE_PRESETS, BATCH_DAILY_VOLUMES, SUBSCRIPTION_PRICING (with annual), BILLING_CYCLE_DIST, UTM configs, PAGE_URLS, DIM_DATE_START/END, new DQ rates
- `src/main.py` — Full rewrite with mode/scale CLI, batch mode, post-generation dirty injection
- `src/generators/website_events.py` — UTM + page_url + campaigns linkage
- `src/generators/subscriptions.py` — monthly_price, billing_cycle, annual_discount
- `src/generators/marketing.py` — utm_campaign + `generate_campaign_spend_daily`
- `src/generators/orders.py` — `generate_orders_batch`
- `src/generators/support_tickets.py` — `generate_support_tickets_batch`
- `src/generators/payments.py` — Fixed duplicate-safe refund date lookup
- `src/utils.py` — DirtyManifest class, enhanced injection helpers with table tracking
- `src/generators/dim_date.py` — Full rewrite with extended range + multi-country holidays
- `src/generators/reviews.py` — NEW
- `load_postgres.py` — Added product_reviews, dim_date dtypes
- `ERD.md` — NEW

---

## Where To Resume

### Immediate Next Steps

1. **Regenerate full prod data** — Run `python generate.py --mode full --scale prod`
2. **Load into Postgres** — Schema was dropped; need `CREATE SCHEMA raw;` then run `load_postgres.py`
3. **Test batch mode** — Run a batch after full load: `python generate.py --mode batch --days 7`
4. **Commit all changes to dev** — Everything is unstaged right now
5. **Create PR to main**

### Remaining Items from GENERATOR_CHANGES.md (Not Yet Done)

- **Page URL: `referrer_url`** — The doc mentions a referrer column; we added `page_url` but not referrer
- **Product URL slugs** — page_url currently uses generic paths; could be enriched with actual product slugs from product names
- **Search query terms** — `/search?q={term}` with realistic keywords
- **Late arrivals** — orders/events that are "backdated" (in dirty mode)
- **Schema drift** — occasional extra column or type change (in dirty mode)
- **Subscription batch mode** — new subs + churns per day (skeleton exists in BATCH_DAILY_VOLUMES but not wired up)

### Commands to Resume

```bash
cd /Users/praneelcore/Desktop/shopsphere-data-generator

# Generate prod data
.venv/bin/python generate.py --mode full --scale prod

# Load into Postgres
psql -d shopsphere -c "CREATE SCHEMA IF NOT EXISTS raw;"
.venv/bin/python load_postgres.py --db-url postgresql://praneelcore@localhost:5432/shopsphere --schema raw

# Commit
git add -A
git commit -m "Add scale/batch/dirty modes, product reviews, enhanced dim_date and subscriptions"
git push origin dev

# Create PR
gh pr create --base main --head dev --title "Major generator overhaul: modes, reviews, and attribution" --body "..."
```
