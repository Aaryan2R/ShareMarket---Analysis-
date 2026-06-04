import pandas as pd
from pathlib import Path
import json

BASE = Path("data/raw")
OUT_BASE = Path("data/cleaned")


def compute_slope(series: pd.Series):
    if len(series) < 3:
        return None
    x = range(len(series))
    return round(pd.Series(series).reset_index(drop=True).corr(pd.Series(x)), 3)


def momentum_label(weekly_slope, monthly_slope):
    if weekly_slope is None or monthly_slope is None:
        return "INSUFFICIENT_DATA"

    if weekly_slope > 0.3 and monthly_slope > 0.3:
        return "STRONG_BULLISH"
    if weekly_slope > 0 and monthly_slope > 0:
        return "WEAK_BULLISH"
    if weekly_slope < -0.3 and monthly_slope < -0.3:
        return "STRONG_BEARISH"
    if weekly_slope < 0 and monthly_slope < 0:
        return "WEAK_BEARISH"

    return "NEUTRAL"


def generate_momentum(company: str):
    weekly_path = BASE / company / "prices" / "weekly.csv"
    monthly_path = BASE / company / "prices" / "monthly.csv"

    if not weekly_path.exists() or not monthly_path.exists():
        print(f"[{company}] missing weekly or monthly data")
        return

    weekly = pd.read_csv(weekly_path)
    monthly = pd.read_csv(monthly_path)

    if "Close" not in weekly or "Close" not in monthly:
        print(f"[{company}] Close column missing")
        return

    weekly_slope = compute_slope(weekly["Close"].tail(12))
    monthly_slope = compute_slope(monthly["Close"].tail(6))

    signal = momentum_label(weekly_slope, monthly_slope)

    output = {
        "weekly_slope": weekly_slope,
        "monthly_slope": monthly_slope,
        "momentum": signal
    }

    outdir = OUT_BASE / company / "signals"
    outdir.mkdir(parents=True, exist_ok=True)

    with open(outdir / "momentum.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"[{company}] momentum confirmed -> {signal}")


def run_momentum():
    for company_dir in BASE.iterdir():
        if company_dir.is_dir():
            generate_momentum(company_dir.name)


if __name__ == "__main__":
    run_momentum()
