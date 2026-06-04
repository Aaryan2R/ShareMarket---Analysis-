import pandas as pd
from pathlib import Path
import json
import numpy as np

RAW = Path("data/raw")
OUT = Path("data/cleaned")


def compute_volatility(df: pd.DataFrame) -> float | None:
    if len(df) < 5:
        return None

    prices = df["Close"].astype(float)
    returns = np.log(prices / prices.shift(1)).dropna()

    if returns.empty:
        return None

    return round(returns.std() * 100, 2)


def classify_risk(vol: float | None) -> str:
    if vol is None:
        return "INSUFFICIENT_DATA"
    if vol < 1.5:
        return "LOW"
    if vol < 3.5:
        return "MEDIUM"
    return "HIGH"


def trading_suitability(risk: str) -> str:
    return {
        "LOW": "SWING",
        "MEDIUM": "INTRADAY + SWING",
        "HIGH": "INTRADAY ONLY",
        "INSUFFICIENT_DATA": "UNKNOWN"
    }[risk]


def generate_volatility_risk(company: str):
    weekly_path = RAW / company / "prices" / "weekly.csv"
    monthly_path = RAW / company / "prices" / "monthly.csv"

    if not weekly_path.exists() or not monthly_path.exists():
        print(f"[{company}] missing weekly or monthly price data")
        return

    weekly = pd.read_csv(weekly_path)
    monthly = pd.read_csv(monthly_path)

    weekly_vol = compute_volatility(weekly)
    monthly_vol = compute_volatility(monthly)

    risk = classify_risk(monthly_vol)
    suitability = trading_suitability(risk)

    output = {
        "weekly_volatility_pct": weekly_vol,
        "monthly_volatility_pct": monthly_vol,
        "risk_regime": risk,
        "trading_suitability": suitability
    }

    outdir = OUT / company / "signals"
    outdir.mkdir(parents=True, exist_ok=True)

    with open(outdir / "volatility_risk.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"[{company}] volatility risk generated -> {risk}")


def run_volatility_risk():
    for company_dir in RAW.iterdir():
        if company_dir.is_dir():
            generate_volatility_risk(company_dir.name)


if __name__ == "__main__":
    run_volatility_risk()
