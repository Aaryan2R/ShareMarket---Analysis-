from pathlib import Path
import pandas as pd

RAW = Path("data/raw")


def aggregate_prices(company: str):
    daily_path = RAW / company / "prices" / "daily" / "daily.csv"
    if not daily_path.exists():
        print(f"[{company}] no daily price file found")
        return

    df = pd.read_csv(daily_path)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")

    ohlc = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum"
    }

    weekly = df.resample("W-FRI").agg(ohlc).dropna()
    monthly = df.resample("ME").agg(ohlc).dropna()

    out_base = RAW / company / "prices"
    out_base.mkdir(parents=True, exist_ok=True)

    weekly.to_csv(out_base / "weekly.csv")
    monthly.to_csv(out_base / "monthly.csv")

    print(f"[{company}] weekly + monthly prices saved")
