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

def inject_nulls(rng: np.random.Generator, df: pd.DataFrame, columns: list[str], rate: float) -> pd.DataFrame:
    df = df.copy()
    for col in columns:
        mask = rng.random(len(df)) < rate
        df.loc[mask, col] = None
    return df


def inject_duplicates(rng: np.random.Generator, df: pd.DataFrame, rate: float) -> pd.DataFrame:
    n_dupes = max(1, int(len(df) * rate))
    idx     = rng.choice(len(df), size=n_dupes, replace=False)
    dupes   = df.iloc[idx].copy()
    return pd.concat([df, dupes], ignore_index=True)


def inject_invalid_dates(rng: np.random.Generator, df: pd.DataFrame, col: str, rate: float) -> pd.DataFrame:
    df     = df.copy()
    mask   = rng.random(len(df)) < rate
    df.loc[mask, col] = "9999-99-99"   # clearly invalid
    return df
