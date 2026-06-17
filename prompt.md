You are a Staff Data Engineer, Analytics Engineer, and Data Architect.

Build a complete Python project called:

ShopSphere Data Generator

The goal is to generate realistic operational data for a fictional ecommerce company that will be used to build an end-to-end analytics engineering portfolio.

The generated data must resemble real production systems and support the following portfolio projects:

1. Modern Analytics Warehouse
2. Product Analytics Platform
3. Marketing Attribution System
4. Data Quality & Observability Platform
5. Customer 360 Platform

The generated data should support:

- PostgreSQL raw layer
- dbt transformations
- BigQuery analytics warehouse
- Looker Studio dashboards
- Airflow orchestration
- Data quality monitoring

Tech stack:

- Python 3.12+
- Faker
- Pandas
- NumPy
- PyArrow
- SQLAlchemy

---

## PROJECT REQUIREMENTS

Generate realistic historical business data from:

2023-01-01 through today.

The company is an ecommerce retailer called ShopSphere.

The business operates globally.

Countries:

- India
- Germany
- United States
- United Kingdom
- France
- Netherlands

---

## DATASETS

Generate the following datasets.

1. customers

Columns:

customer_id (UUID)
signup_date
country
city
acquisition_channel
customer_segment
email
is_active

Customer segments:

- Whale
- Loyal
- Regular
- One-Time Buyer

Business rules:

- Whale customers represent ~5%
- Loyal customers represent ~15%
- Regular customers represent ~50%
- One-Time Buyers represent ~30%

Whale customers generate significantly more revenue.

---

1. products

Columns:

product_id (UUID)
product_name
category
subcategory
cost
selling_price
margin

Categories:

- Electronics
- Fashion
- Home
- Beauty
- Sports
- Books

Business rule:

Top 20% of products should generate roughly 80% of revenue.

---

1. orders

Columns:

order_id (UUID)
customer_id
order_date
status

Statuses:

- Completed
- Cancelled
- Returned

Business rules:

- Approximately 1,000,000 orders
- Loyal customers order frequently
- Whale customers order most frequently
- One-Time Buyers usually place only one order

---

1. order_items

Columns:

order_item_id (UUID)
order_id
product_id
quantity
unit_price

Business rules:

- Multiple products per order
- Realistic basket sizes

---

1. payments

Columns:

payment_id (UUID)
order_id
payment_method
payment_amount
payment_date

Methods:

- Card
- UPI
- PayPal
- Bank Transfer

---

1. refunds

Columns:

refund_id (UUID)
order_id
refund_amount
refund_reason
refund_date

Business rules:

Overall refund rate ~5%

Electronics should have a higher refund rate.

---

1. website_events

Columns:

event_id (UUID)
session_id (UUID)
customer_id
event_timestamp
event_type
device_type
traffic_source

Event types:

- page_view
- search
- product_view
- add_to_cart
- checkout
- purchase

Device types:

- Desktop
- Mobile
- Tablet

Traffic sources:

- Google Ads
- Facebook Ads
- LinkedIn Ads
- Email
- Organic Search
- Direct

Business rules:

Generate approximately 5,000,000 events.

Create realistic funnel behavior:

page_view > product_view > add_to_cart > checkout > purchase

Conversion rates should decrease at every funnel step.

---

1. support_tickets

Columns:

ticket_id (UUID)
customer_id
created_date
issue_type
priority
resolution_time_hours

Issue types:

- Delivery
- Refund
- Product Defect
- Payment
- Account

Priorities:

- Low
- Medium
- High

Business rule:

Customers with many support tickets should have higher churn probability.

---

1. marketing_campaigns

Columns:

campaign_id (UUID)
campaign_name
channel
start_date
end_date

Channels:

- Google Ads
- Facebook Ads
- LinkedIn Ads
- Email
- Organic Search

---

1. campaign_spend

Columns:

campaign_spend_id (UUID)
campaign_id
date
impressions
clicks
conversions
spend

Business rules:

Google Ads:

- highest conversion rate

LinkedIn:

- highest customer acquisition cost

Organic Search:

- highest ROI

---

1. subscriptions

Columns:

subscription_id (UUID)
customer_id
plan_type
start_date
end_date
churn_status

Plan types:

- Basic
- Premium
- Enterprise

---

## BUSINESS BEHAVIOR

Implement realistic business patterns.

Seasonality:

- November sales increase significantly
- December sales increase significantly
- February sales decrease

Customer Churn:

- Some customers become inactive over time
- Higher support ticket volume increases churn likelihood

Customer Segmentation:

- Whale customers generate most revenue
- Loyal customers have highest retention

Marketing Attribution:

- Marketing channels have different conversion rates

Product Performance:

- Revenue follows Pareto distribution
- Top 20% products generate ~80% revenue

Support Behavior:

- Higher ticket volume correlates with churn

---

## DATA QUALITY CAPABILITIES

Add optional flags that allow generation of intentionally bad data.

Examples:

- duplicate customers
- duplicate orders
- null values
- invalid dates
- broken foreign keys
- missing payments

This will be used later for Data Quality and Observability projects.

---

## OUTPUT

Save all datasets as Parquet files.

Output folder:

data/

Files:

customers.parquet
products.parquet
orders.parquet
order_items.parquet
payments.parquet
refunds.parquet
website_events.parquet
support_tickets.parquet
marketing_campaigns.parquet
campaign_spend.parquet
subscriptions.parquet

---

## PROJECT STRUCTURE

Generate a complete production-style Python project.

Include:

- requirements.txt
- pyproject.toml
- src/
- config/
- logging
- CLI interface
- random seed support
- README.md

CLI examples:

python generate.py --customers 100000
python generate.py --orders 1000000
python generate.py --events 5000000

The generated data should be suitable for:

- PostgreSQL raw layer
- Star schema design
- Fact tables
- Dimension tables
- dbt transformations
- BigQuery analytics warehouse
- Customer 360 modeling
- Product analytics
- Marketing attribution
- Data quality monitoring

Prioritize realistic business behavior over random fake data.