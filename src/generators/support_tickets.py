"""Generate support_tickets table."""

import numpy as np
import pandas as pd

from config.settings import (
    ISSUE_TYPES, PRIORITIES, RESOLUTION_HOURS,
    START_DATE, END_DATE,
)
from src.utils import get_logger, make_uuids, random_dates_array, weighted_choice

logger = get_logger(__name__)


def generate_support_tickets(
    customers: pd.DataFrame,
    rng: np.random.Generator,
    dirty: bool = False,
) -> pd.DataFrame:
    logger.info("Generating support_tickets …")

    n_customers = len(customers)

    # ── Ticket count per customer ─────────────────────────────────────────────
    # Most customers have 0 tickets; churned / inactive have more
    is_inactive = ~customers["is_active"].values
    # Base: ~20% of customers have at least 1 ticket
    has_ticket = rng.random(n_customers) < 0.20
    # Inactive customers are 2x as likely to have tickets
    has_ticket[is_inactive] = rng.random(is_inactive.sum()) < 0.40

    # Ticket count: Poisson(1.5) for those who have tickets
    ticket_counts = np.where(
        has_ticket,
        rng.poisson(lam=1.5, size=n_customers) + 1,
        0,
    )

    total_tickets = int(ticket_counts.sum())
    logger.info(f"  ↳ {total_tickets:,} tickets across {has_ticket.sum():,} customers")

    # ── Expand customer_ids ───────────────────────────────────────────────────
    cust_ids_rep = customers["customer_id"].values.repeat(ticket_counts)

    # ── Dates ────────────────────────────────────────────────────────────────
    ticket_dates = random_dates_array(rng, START_DATE, END_DATE, total_tickets)

    # ── Issue types & priorities ─────────────────────────────────────────────
    issue_types = weighted_choice(rng, ISSUE_TYPES, total_tickets)
    priorities  = weighted_choice(rng, PRIORITIES, total_tickets)

    # ── Resolution times ─────────────────────────────────────────────────────
    res_hours = np.array([
        rng.uniform(*RESOLUTION_HOURS[p])
        for p in priorities
    ])
    res_hours = np.round(res_hours, 1)

    df = pd.DataFrame({
        "ticket_id":             make_uuids(total_tickets),
        "customer_id":           cust_ids_rep,
        "created_date":          pd.to_datetime(ticket_dates).to_series().dt.date.values,
        "issue_type":            issue_types,
        "priority":              priorities,
        "resolution_time_hours": res_hours,
    })

    if dirty:
        from src.utils import inject_nulls
        df = inject_nulls(rng, df, ["resolution_time_hours"], rate=0.05)

    logger.info(f"  ↳ support_tickets done. {len(df):,} rows.")
    return df


def generate_support_tickets_batch(
    customers: pd.DataFrame,
    n_tickets: int,
    target_date,
    rng: np.random.Generator,
    dirty: bool = False,
) -> pd.DataFrame:
    """Generate support tickets for a single day (batch mode)."""
    logger.info(f"Generating {n_tickets} support tickets for {target_date} …")

    # Sample from all customers (weighted toward inactive ones)
    is_inactive = ~customers["is_active"].values
    weights = np.where(is_inactive, 3.0, 1.0)
    weights /= weights.sum()

    cust_idx = rng.choice(len(customers), size=n_tickets, replace=True, p=weights)
    cust_ids = customers["customer_id"].values[cust_idx]

    issue_types = weighted_choice(rng, ISSUE_TYPES, n_tickets)
    priorities  = weighted_choice(rng, PRIORITIES, n_tickets)
    res_hours   = np.array([
        round(rng.uniform(*RESOLUTION_HOURS[p]), 1)
        for p in priorities
    ])

    df = pd.DataFrame({
        "ticket_id":             make_uuids(n_tickets),
        "customer_id":           cust_ids,
        "created_date":          target_date,
        "issue_type":            issue_types,
        "priority":              priorities,
        "resolution_time_hours": res_hours,
    })

    if dirty:
        from src.utils import inject_nulls
        df = inject_nulls(rng, df, ["resolution_time_hours"], rate=0.05, table_name="support_tickets")

    logger.info(f"  ↳ batch support_tickets done. {len(df)} rows.")
    return df
