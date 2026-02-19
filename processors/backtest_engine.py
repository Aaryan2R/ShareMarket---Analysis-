import json
import pandas as pd
from pathlib import Path

RAW = Path("data/raw")
OUT = Path("data/cleaned/_backtest")
OUT.mkdir(parents=True, exist_ok=True)

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


def run_backtest_company(company):
    path = RAW / company / "prices" / "daily" / "daily.csv"
    if not path.exists():
        return None

    df = pd.read_csv(path)

    for col in ["High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["High", "Low", "Close"])

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

        # --- Trend filter ---
        if ema50 > ema200:
            trend = "UP"
        elif ema50 < ema200:
            trend = "DOWN"
        else:
            continue

        # --- Pullback condition ---
        distance = abs(close - ema20)

        if distance > atr_val:
            continue

        # --- Momentum confirmation ---
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

    win_rate = round((wins / total) * 100, 2)
    expectancy = round((wins * TP_MULT - losses * SL_MULT) / total, 2)

    return {
        "company": company,
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": win_rate,
        "expectancy_score": expectancy
    }


def run_backtest():
    results = []

    for company_dir in RAW.iterdir():
        if company_dir.is_dir():
            res = run_backtest_company(company_dir.name)
            if res:
                results.append(res)

    OUT.joinpath("pullback_summary.json").write_text(
        json.dumps(results, indent=2),
        encoding="utf-8"
    )

    print("[A9.3] Pullback Backtest completed")


if __name__ == "__main__":
    run_backtest()
