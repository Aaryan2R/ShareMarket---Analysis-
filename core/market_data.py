from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import RAW_PATH


PRICE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]


def price_csv_path(company: str) -> Path:
    return RAW_PATH / company / "prices" / "daily" / "daily.csv"


def find_price_csv(company: str) -> Path | None:
    canonical = price_csv_path(company)
    if canonical.exists():
        return canonical
    needle = company.lower().replace(" ", "")
    for path in RAW_PATH.rglob("*.csv"):
        candidate = str(path).lower().replace(" ", "")
        if needle in candidate:
            return path
    return None


def normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [str(col[0]) for col in frame.columns]

    frame = frame.rename(columns={col: str(col).strip() for col in frame.columns})
    if "Date" not in frame.columns and frame.index.name:
        frame = frame.reset_index()
    if "Date" not in frame.columns:
        first = frame.columns[0]
        frame = frame.rename(columns={first: "Date"})

    keep = [col for col in PRICE_COLUMNS if col in frame.columns]
    frame = frame[keep]
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in frame.columns:
            frame[col] = (
                frame[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("Rs.", "", regex=False)
                .str.replace("INR", "", regex=False)
                .str.strip()
            )
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    required = [col for col in ["Date", "Open", "High", "Low", "Close"] if col in frame.columns]
    frame = frame.dropna(subset=required).sort_values("Date").drop_duplicates("Date", keep="last")
    return frame.reset_index(drop=True)


def read_price_frame(company: str) -> pd.DataFrame | None:
    path = find_price_csv(company)
    if not path:
        return None
    return normalize_price_frame(pd.read_csv(path))


def save_price_frame(company: str, df: pd.DataFrame) -> Path:
    frame = normalize_price_frame(df)
    path = price_csv_path(company)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)
    return path


def normalize_existing_price_csvs() -> list[tuple[str, int]]:
    changed: list[tuple[str, int]] = []
    for path in RAW_PATH.glob("*/prices/daily/daily.csv"):
        before = pd.read_csv(path)
        after = normalize_price_frame(before)
        out = after.copy()
        out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
        out.to_csv(path, index=False)
        changed.append((path.parent.parent.parent.name, len(out)))
    return changed

