import pandas as pd
from pathlib import Path
from datetime import date
import json

TODAY = date.today().isoformat()

def compute_weekly_price_trend(symbol: str) -> bool:
    price_dir = Path(f"data/raw/{symbol}/prices/daily")
    index_path = Path(f"data/index/{symbol}.json")

    if not price_dir.exists():
        print(f"[{symbol}] no daily prices found")
        return False

    files = sorted(price_dir.glob("*.csv"))
    if len(files) < 3:
        print(f"[{symbol}] not enough data for weekly trend")
        return False

    # take last 5 trading days
    recent = files[-5:]

    closes = []
    for f in recent:
        df = pd.read_csv(f)
        if "Close" in df.columns:
            closes.append(df["Close"].iloc[-1])
        elif "CLOSE" in df.columns:
            closes.append(df["CLOSE"].iloc[-1])

    if len(closes) < 2:
        return False

    start = closes[0]
    end = closes[-1]
    change_pct = round(((end - start) / start) * 100, 2)

    if change_pct > 1:
        trend = "UP"
    elif change_pct < -1:
        trend = "DOWN"
    else:
        trend = "FLAT"

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    index["signals"]["price_trend"] = {
        "weekly_trend": trend,
        "change_pct": change_pct,
        "days_used": len(closes),
        "last_updated": TODAY
    }

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"[{symbol}] weekly trend indexed → {trend}")
    return True


if __name__ == "__main__":
    compute_weekly_price_trend("TCS")
    compute_weekly_price_trend("INFY")
