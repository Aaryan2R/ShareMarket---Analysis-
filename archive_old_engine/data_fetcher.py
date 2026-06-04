# core/data_fetcher.py

import yfinance as yf
import pandas as pd
from pathlib import Path


DATA_DIR = Path("data/raw")


def fetch_full_history(nse_symbol):
    df = yf.download(nse_symbol, period="max", auto_adjust=False)
    df.reset_index(inplace=True)
    return df


def save_csv(company_name, df):
    folder = DATA_DIR / company_name
    folder.mkdir(parents=True, exist_ok=True)

    daily_path = folder / "daily.csv"
    df.to_csv(daily_path, index=False)

    # weekly
    df_weekly = df.resample("W-MON", on="Date").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum"
    }).dropna().reset_index()

    df_weekly.to_csv(folder / "weekly.csv", index=False)

    # monthly
    df_monthly = df.resample("M", on="Date").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum"
    }).dropna().reset_index()

    df_monthly.to_csv(folder / "monthly.csv", index=False)