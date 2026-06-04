import pandas as pd
import json
from pathlib import Path
import yfinance as yf

RAW = Path("data/raw")
OUT = Path("data/cleaned/_backtest")
OUT.mkdir(parents=True, exist_ok=True)

SL_MULT = 1.2
TP_MULT = 2.5
MAX_HOLD = 10
LOOKBACK = 20  # breakout window


def compute_regime_series():
    df = yf.download("^NSEI", period="5y", auto_adjust=True, progress=False)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()

    df["REGIME"] = None
    df.loc[df["EMA50"] > df["EMA200"], "REGIME"] = "BULL"
    df.loc[df["EMA50"] < df["EMA200"], "REGIME"] = "BEAR"

    return df["REGIME"]


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


def backtest_company(company, regime_series):
    path = RAW / company / "prices" / "daily" / "daily.csv"
    if not path.exists():
        return None

    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)

    for col in ["High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df.dropna(inplace=True)
    if len(df) < 250:
        return None

    df["ATR"] = compute_atr(df)

    trades = 0
    wins = 0
    losses = 0

    for i in range(LOOKBACK, len(df) - MAX_HOLD):
        date = df.index[i]
        regime = regime_series.get(date, None)

        if regime not in ("BULL", "BEAR"):
            continue

        row = df.iloc[i]
        if pd.isna(row["ATR"]):
            continue

        highest = df["High"].iloc[i - LOOKBACK:i].max()
        lowest = df["Low"].iloc[i - LOOKBACK:i].min()

        direction = None

        if regime == "BULL" and row["Close"] > highest:
            direction = "LONG"

        elif regime == "BEAR" and row["Close"] < lowest:
            direction = "SHORT"

        if direction is None:
            continue

        entry = row["Close"]
        atr = row["ATR"]

        if direction == "LONG":
            sl = entry - atr * SL_MULT
            tp = entry + atr * TP_MULT
        else:
            sl = entry + atr * SL_MULT
            tp = entry - atr * TP_MULT

        rr = abs(tp - entry) / abs(entry - sl)
        if rr < 2.0:
            continue

        trades += 1
        outcome = None

        future = df.iloc[i + 1 : i + MAX_HOLD + 1]

        for _, f in future.iterrows():
            if direction == "LONG":
                if f["Low"] <= sl:
                    outcome = "LOSS"
                    break
                if f["High"] >= tp:
                    outcome = "WIN"
                    break
            else:
                if f["High"] >= sl:
                    outcome = "LOSS"
                    break
                if f["Low"] <= tp:
                    outcome = "WIN"
                    break

        if outcome == "WIN":
            wins += 1
        elif outcome == "LOSS":
            losses += 1

    if trades == 0:
        return None

    win_rate = round((wins / trades) * 100, 2)
    expectancy = round(
        (wins / trades) * TP_MULT - (losses / trades) * SL_MULT,
        2,
    )

    return {
        "company": company,
        "total_trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": win_rate,
        "expectancy_score": expectancy,
    }


def run_backtest():
    regime_series = compute_regime_series()
    results = []

    for company_dir in RAW.iterdir():
        if company_dir.is_dir():
            res = backtest_company(company_dir.name, regime_series)
            if res:
                results.append(res)

    OUT.joinpath("pullback_summary.json").write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )

    print("[FINAL] Breakout Swing Backtest completed")


if __name__ == "__main__":
    run_backtest()