import pandas as pd
from pathlib import Path
import json

RAW_BASE = Path("data/raw")
OUT_BASE = Path("data/cleaned")


def load_price_file(company: str, kind: str) -> Path | None:
    """
    Supports BOTH layouts:
    prices/weekly.csv
    prices/weekly/weekly.csv
    """
    direct = RAW_BASE / company / "prices" / f"{kind}.csv"
    nested = RAW_BASE / company / "prices" / kind / f"{kind}.csv"

    if direct.exists():
        return direct
    if nested.exists():
        return nested
    return None


def compute_return(df: pd.DataFrame):
    if len(df) < 2:
        return None

    cols = [c.lower() for c in df.columns]
    if "close" not in cols:
        return None

    close_col = df.columns[cols.index("close")]

    prev = df.iloc[-2][close_col]
    last = df.iloc[-1][close_col]

    if pd.isna(prev) or pd.isna(last) or prev == 0:
        return None

    return round(((last - prev) / prev) * 100, 2)


def generate_price_signal(company: str):
    weekly_path = load_price_file(company, "weekly")
    monthly_path = load_price_file(company, "monthly")

    if not weekly_path or not monthly_path:
        print(f"[{company}] missing weekly or monthly data")
        return

    weekly = pd.read_csv(weekly_path)
    monthly = pd.read_csv(monthly_path)

    weekly_ret = compute_return(weekly)
    monthly_ret = compute_return(monthly)

    if weekly_ret is None or monthly_ret is None:
        signal = "INSUFFICIENT_DATA"
    elif weekly_ret > 0 and monthly_ret > 0:
        signal = "BULLISH"
    elif weekly_ret < 0 and monthly_ret < 0:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    output = {
        "weekly_return_pct": weekly_ret,
        "monthly_return_pct": monthly_ret,
        "price_signal": signal
    }

    outdir = OUT_BASE / company / "signals"
    outdir.mkdir(parents=True, exist_ok=True)

    with open(outdir / "price_signal.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"[{company}] price signal generated: {signal}")


def run_price_signals():
    try:
        df = pd.read_csv("data/companies.csv", dtype=str)
    except FileNotFoundError:
        print("[SYSTEM] companies.csv not found")
        return

    for _, row in df.iterrows():
        company = row.get("company_name", "").strip()
        if company:
            generate_price_signal(company)


if __name__ == "__main__":
    run_price_signals()
