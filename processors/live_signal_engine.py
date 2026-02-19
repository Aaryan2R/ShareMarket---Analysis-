import json
import pandas as pd
from pathlib import Path
import yfinance as yf

RAW = Path("data/raw")
APPROVED = Path("data/cleaned/_approved_universe.json")
OUT_DIR = Path("data/live_signals")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SL_MULT = 1.2
TP_MULT = 2.5


def compute_atr(df, period=14):
    high = df["High"]
    low = df["Low"]
    close_prev = df["Close"].shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - close_prev).abs(),
            (low - close_prev).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(period).mean()


def generate_signal(company):
    path = RAW / company / "prices" / "daily" / "daily.csv"
    if not path.exists():
        return None

    df = pd.read_csv(path)

    for col in ["High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna()

    df["ATR"] = compute_atr(df)
    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    atr_val = latest["ATR"]
    if pd.isna(atr_val):
        return None

    ema20 = latest["EMA20"]
    ema50 = latest["EMA50"]
    ema200 = latest["EMA200"]
    close = latest["Close"]

    # Trend
    if ema50 > ema200:
        trend = "UP"
    elif ema50 < ema200:
        trend = "DOWN"
    else:
        return None

    # Pullback
    if abs(close - ema20) > atr_val:
        return None

    # Momentum
    if trend == "UP" and close > prev["Close"]:
        direction = "LONG"
    elif trend == "DOWN" and close < prev["Close"]:
        direction = "SHORT"
    else:
        return None

    if direction == "LONG":
        sl = close - atr_val * SL_MULT
        tp = close + atr_val * TP_MULT
    else:
        sl = close + atr_val * SL_MULT
        tp = close - atr_val * TP_MULT

    rr = abs(tp - close) / abs(close - sl)

    return {
        "company": company,
        "direction": direction,
        "entry": round(close, 2),
        "stop_loss": round(sl, 2),
        "target": round(tp, 2),
        "risk_reward": round(rr, 2),
    }


def run_live_engine():
    if not APPROVED.exists():
        print("No approved universe found.")
        return

    approved = json.loads(APPROVED.read_text())

    signals = []

    for stock in approved:
        company = stock["company"]
        print(f"Checking {company}")
        signal = generate_signal(company)
        if signal:
            signals.append(signal)

    OUT_DIR.joinpath("today.json").write_text(
        json.dumps(signals, indent=2),
        encoding="utf-8"
    )

    print("[A11] Live signals generated")


if __name__ == "__main__":
    run_live_engine()
