import pandas as pd
from pathlib import Path
from datetime import date
import json

TODAY = date.today().isoformat()

def compute_support_resistance(symbol: str) -> bool:
    price_dir = Path(f"data/raw/{symbol}/prices/daily")
    index_path = Path(f"data/index/{symbol}.json")

    if not price_dir.exists():
        print(f"[{symbol}] no daily prices")
        return False

    files = sorted(price_dir.glob("*.csv"))
    if len(files) < 5:
        print(f"[{symbol}] not enough data for S/R")
        return False

    recent = files[-10:]  # last ~2 weeks
    lows = []
    highs = []

    for f in recent:
        df = pd.read_csv(f)

        if "Low" in df.columns:
            lows.append(df["Low"].iloc[-1])
        elif "LOW" in df.columns:
            lows.append(df["LOW"].iloc[-1])

        if "High" in df.columns:
            highs.append(df["High"].iloc[-1])
        elif "HIGH" in df.columns:
            highs.append(df["HIGH"].iloc[-1])

    if not lows or not highs:
        return False

    support = round(min(lows), 2)
    resistance = round(max(highs), 2)

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    index["signals"]["support_resistance"] = {
        "support": support,
        "resistance": resistance,
        "days_used": len(lows),
        "last_updated": TODAY
    }

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"[{symbol}] support={support}, resistance={resistance}")
    return True


if __name__ == "__main__":
    compute_support_resistance("TCS")
    compute_support_resistance("INFY")
