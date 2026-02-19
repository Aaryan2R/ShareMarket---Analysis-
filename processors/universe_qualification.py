import json
import pandas as pd
from pathlib import Path
import yfinance as yf

RAW = Path("data/raw")
CLEAN = Path("data/cleaned")
UNIVERSE = Path("data/universe.csv")
OUT = CLEAN / "_approved_universe.json"

SL_MULT = 1.2
TP_MULT = 2.5
LOOKAHEAD = 15


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


def simulate_trade(df, i, direction, atr_val):
    entry = df.iloc[i]["Close"]

    if direction == "LONG":
        sl = entry - atr_val * SL_MULT
        tp = entry + atr_val * TP_MULT
    else:
        sl = entry + atr_val * SL_MULT
        tp = entry - atr_val * TP_MULT

    for j in range(i + 1, min(i + LOOKAHEAD, len(df))):
        high = df.iloc[j]["High"]
        low = df.iloc[j]["Low"]

        if direction == "LONG":
            if low <= sl:
                return "LOSS"
            if high >= tp:
                return "WIN"
        else:
            if high >= sl:
                return "LOSS"
            if low <= tp:
                return "WIN"

    return None


def ensure_price_data(company, symbol):
    path = RAW / company / "prices" / "daily" / "daily.csv"
    if path.exists():
        return

    df = yf.download(symbol, period="5y", auto_adjust=True, progress=False)
    if df.empty:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    df.reset_index().to_csv(path, index=False)


def backtest_company(company):
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

    wins = 0
    losses = 0
    total = 0

    for i in range(200, len(df) - LOOKAHEAD):
        atr_val = df.iloc[i]["ATR"]
        if pd.isna(atr_val):
            continue

        ema20 = df.iloc[i]["EMA20"]
        ema50 = df.iloc[i]["EMA50"]
        ema200 = df.iloc[i]["EMA200"]
        close = df.iloc[i]["Close"]

        if ema50 > ema200:
            trend = "UP"
        elif ema50 < ema200:
            trend = "DOWN"
        else:
            continue

        if abs(close - ema20) > atr_val:
            continue

        prev_close = df.iloc[i - 1]["Close"]

        if trend == "UP" and close > prev_close:
            direction = "LONG"
        elif trend == "DOWN" and close < prev_close:
            direction = "SHORT"
        else:
            continue

        result = simulate_trade(df, i, direction, atr_val)

        if result == "WIN":
            wins += 1
            total += 1
        elif result == "LOSS":
            losses += 1
            total += 1

    if total == 0:
        return None

    win_rate = (wins / total) * 100
    expectancy = (wins * TP_MULT - losses * SL_MULT) / total

    return {
        "win_rate": round(win_rate, 2),
        "expectancy": round(expectancy, 2)
    }


def run_universe():
    df = pd.read_csv(UNIVERSE)
    approved = []

    for _, row in df.iterrows():
        company = row["company_name"]
        symbol = row["yahoo_symbol"]

        print(f"Testing {company}")

        ensure_price_data(company, symbol)
        result = backtest_company(company)

        if result and result["expectancy"] > 0 and result["win_rate"] >= 35:
            approved.append({
                "company": company,
                "win_rate": result["win_rate"],
                "expectancy": result["expectancy"]
            })

    OUT.write_text(json.dumps(approved, indent=2))
    print("[A10] Approved universe generated")


if __name__ == "__main__":
    run_universe()
