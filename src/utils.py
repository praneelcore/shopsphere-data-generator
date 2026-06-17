"""Shared utility helpers used across all generators."""

import logging
import sys
from pathlib import Path
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd


# ─── Logging ──────────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                              datefmt="%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ─── Date helpers ─────────────────────────────────────────────────────────────

def random_date(rng: np.random.Generator, start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=int(rng.integers(0, delta + 1)))


def random_dates_array(rng: np.random.Generator, start: date, end: date, n: int) -> np.ndarray:
    """Return an array of n random dates between start and end (as date objects)."""
    delta = (end - start).days
    offsets = rng.integers(0, delta + 1, size=n)
    base = np.datetime64(start)
    return base + offsets.astype("timedelta64[D]")


def seasonal_weights(dates: np.ndarray, seasonality: dict[int, float]) -> np.ndarray:
    """Convert an array of np.datetime64 dates into per-date seasonal weights."""
    months = dates.astype("datetime64[M]").astype(int) % 12 + 1
    w = np.vectorize(seasonality.get)(months, 1.0)
    return w / w.sum()


# ─── Weighted sampling ────────────────────────────────────────────────────────

def weighted_choice(rng: np.random.Generator, choices: dict, n: int = 1) -> np.ndarray:
    """Sample from a {value: weight} dict."""
    keys   = list(choices.keys())
    probs  = np.array(list(choices.values()), dtype=float)
    probs /= probs.sum()
    return rng.choice(keys, size=n, p=probs)


# ─── UUID generation ──────────────────────────────────────────────────────────

def make_uuids(n: int) -> np.ndarray:
    """Generate n UUIDs as strings using numpy for speed."""
    import uuid
    return np.array([str(uuid.uuid4()) for _ in range(n)], dtype=object)


# ─── Parquet IO ───────────────────────────────────────────────────────────────

def save_parquet(df: pd.DataFrame, path: Path, logger: logging.Logger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
    mb = path.stat().st_size / 1_048_576
    logger.info(f"Saved {len(df):,} rows → {path}  ({mb:.1f} MB)")


# ─── Data-quality corruption helpers ─────────────────────────────────────────

class DirtyManifest:
    """Tracks all injected data quality issues for validation."""

    def __init__(self):
        self.issues: list[dict] = []

    def record(self, table: str, issue: str, column: str = None,
               row_ids: list = None, count: int = 0):
        entry = {"table": table, "issue": issue, "count": count}
        if column:
            entry["column"] = column
        if row_ids:
            entry["row_ids"] = row_ids[:50]  # Cap stored IDs
        self.issues.append(entry)

    def save(self, path):
        import json
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"total_issues": len(self.issues), "issues": self.issues}, f, indent=2, default=str)


# Global manifest instance (reset per run)
dirty_manifest = DirtyManifest()


def inject_nulls(rng: np.random.Generator, df: pd.DataFrame, columns: list[str],
                 rate: float, table_name: str = None) -> pd.DataFrame:
    df = df.copy()
    for col in columns:
        mask = rng.random(len(df)) < rate
        count = mask.sum()
        if count > 0:
            df.loc[mask, col] = None
            if table_name:
                id_col = df.columns[0]
                dirty_manifest.record(table_name, "null_value", column=col,
                                      row_ids=df.loc[mask, id_col].tolist(), count=int(count))
    return df


def inject_duplicates(rng: np.random.Generator, df: pd.DataFrame, rate: float,
                      table_name: str = None) -> pd.DataFrame:
    n_dupes = max(1, int(len(df) * rate))
    idx     = rng.choice(len(df), size=n_dupes, replace=False)
    dupes   = df.iloc[idx].copy()
    if table_name:
        id_col = df.columns[0]
        dirty_manifest.record(table_name, "duplicate_rows",
                              row_ids=dupes[id_col].tolist(), count=n_dupes)
    return pd.concat([df, dupes], ignore_index=True)


def inject_invalid_dates(rng: np.random.Generator, df: pd.DataFrame, col: str,
                         rate: float, table_name: str = None) -> pd.DataFrame:
    df     = df.copy()
    mask   = rng.random(len(df)) < rate
    count  = mask.sum()
    if count > 0:
        invalid_values = rng.choice(["9999-99-99", "not-a-date", "2024-13-45", ""], size=count)
        df.loc[mask, col] = invalid_values
        if table_name:
            id_col = df.columns[0]
            dirty_manifest.record(table_name, "invalid_date", column=col,
                                  row_ids=df.loc[mask, id_col].tolist(), count=int(count))
    return df


def inject_broken_fks(rng: np.random.Generator, df: pd.DataFrame, fk_col: str,
                      rate: float, table_name: str = None) -> pd.DataFrame:
    """Replace FK values with non-existent UUIDs."""
    df   = df.copy()
    mask = rng.random(len(df)) < rate
    count = mask.sum()
    if count > 0:
        fake_ids = make_uuids(count)
        df.loc[mask, fk_col] = fake_ids
        if table_name:
            id_col = df.columns[0]
            dirty_manifest.record(table_name, "broken_foreign_key", column=fk_col,
                                  row_ids=df.loc[mask, id_col].tolist(), count=int(count))
    return df


def inject_future_timestamps(rng: np.random.Generator, df: pd.DataFrame, col: str,
                             rate: float, table_name: str = None) -> pd.DataFrame:
    """Inject timestamps in the future."""
    df   = df.copy()
    mask = rng.random(len(df)) < rate
    count = mask.sum()
    if count > 0:
        # Match the resolution of the existing column
        future_offset = pd.to_timedelta(rng.integers(1, 365, size=count), unit="D")
        future_ts = pd.Timestamp.now() + future_offset
        # Convert to match the existing dtype
        col_dtype = df[col].dtype
        if hasattr(col_dtype, 'unit'):
            future_ts = future_ts.as_unit(col_dtype.unit)
        df[col] = df[col].astype(object)
        df.loc[mask, col] = future_ts.values
        df[col] = pd.to_datetime(df[col])
        if table_name:
            id_col = df.columns[0]
            dirty_manifest.record(table_name, "future_timestamp", column=col,
                                  row_ids=df.loc[mask, id_col].tolist(), count=int(count))
    return df


def inject_negative_amounts(rng: np.random.Generator, df: pd.DataFrame, col: str,
                            rate: float, table_name: str = None) -> pd.DataFrame:
    """Make some numeric values negative."""
    df   = df.copy()
    mask = rng.random(len(df)) < rate
    count = mask.sum()
    if count > 0:
        df.loc[mask, col] = -abs(df.loc[mask, col])
        if table_name:
            id_col = df.columns[0]
            dirty_manifest.record(table_name, "negative_amount", column=col,
                                  row_ids=df.loc[mask, id_col].tolist(), count=int(count))
    return df
