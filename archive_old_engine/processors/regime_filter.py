import pandas as pd
import yfinance as yf
import json
from pathlib import Path

REGIME_FILE = Path("data/cleaned/_market_regime.json")
REGIME_FILE.parent.mkdir(parents=True, exist_ok=True)


def compute_regime():
    df = yf.download("^NSEI", period="5y", auto_adjust=True, progress=False)

    if df.empty:
        print("Failed to fetch NIFTY data")
        return

    # Flatten multi-index columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()

    latest = df.iloc[-1]

    ema50 = float(latest["EMA50"])
    ema200 = float(latest["EMA200"])

    if ema50 > ema200:
        regime = "BULL"
    elif ema50 < ema200:
        regime = "BEAR"
    else:
        regime = "SIDEWAYS"

    REGIME_FILE.write_text(json.dumps({"regime": regime}))
    print(f"[A14] Market Regime: {regime}")


if __name__ == "__main__":
    compute_regime()