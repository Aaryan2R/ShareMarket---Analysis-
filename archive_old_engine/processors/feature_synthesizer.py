import pandas as pd
import json
from pathlib import Path

RAW = Path("data/raw")
BACKTEST_PATH = Path("data/cleaned/_backtest/pullback_summary.json")
REGIME_PATH = Path("data/cleaned/_market_regime.json")
OUT_PATH = Path("data/cleaned/_daily_intelligence.json")

LOOKBACK = 20
VOL_MULT = 1.5

def load_json_safe(path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except:
        pass
    return {}

def compute_intelligence(company, regime, backtest_map):

    price_path = RAW / company / "prices" / "daily" / "daily.csv"
    if not price_path.exists():
        return None

    df = pd.read_csv(price_path)

    for col in ["High", "Low", "Close", "Volume"]:
        if col not in df.columns:
            return None
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df.dropna(inplace=True)
    if len(df) < 250:
        return None

    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()
    df["AVG_VOL"] = df["Volume"].rolling(20).mean()

    latest = df.iloc[-1]

    close = latest["Close"]
    ema50 = latest["EMA50"]
    ema200 = latest["EMA200"]
    volume = latest["Volume"]
    avg_vol = latest["AVG_VOL"]

    if pd.isna(avg_vol):
        return None

    # ----- Trend -----
    if close > ema50 > ema200:
        trend = "Bullish Structure"
    elif close < ema50 < ema200:
        trend = "Bearish Structure"
    else:
        trend = "Mixed Structure"

    # ----- Breakout -----
    highest = df["High"].iloc[-LOOKBACK-1:-1].max()
    lowest = df["Low"].iloc[-LOOKBACK-1:-1].min()

    breakout = "No Breakout"

    if regime == "BULL" and close > highest:
        breakout = "Bullish Breakout"

    elif regime == "BEAR" and close < lowest:
        breakout = "Bearish Breakout"

    # ----- Volume -----
    vol_confirm = volume > (avg_vol * VOL_MULT)

    volume_status = "Confirmed" if vol_confirm else "Not Confirmed"

    # ----- Backtest Edge -----
    expectancy = backtest_map.get(company, 0)

    decision = "WAIT"

    if breakout != "No Breakout" and vol_confirm and expectancy > 0:
        decision = "TRADE"

    return {
        "company": company,
        "market_regime": regime,
        "trend_structure": trend,
        "breakout_status": breakout,
        "volume_confirmation": volume_status,
        "backtest_expectancy": expectancy,
        "decision": decision
    }

def run_synthesizer():

    regime_data = load_json_safe(REGIME_PATH)
    regime = regime_data.get("regime", "UNKNOWN")

    backtest_data = load_json_safe(BACKTEST_PATH)

    backtest_map = {}
    for item in backtest_data:
        backtest_map[item["company"]] = item.get("expectancy_score", 0)

    results = []

    for company_dir in RAW.iterdir():
        if company_dir.is_dir():
            intelligence = compute_intelligence(company_dir.name, regime, backtest_map)
            if intelligence:
                results.append(intelligence)

    OUT_PATH.write_text(
        json.dumps(results, indent=2),
        encoding="utf-8"
    )

    print("[A16] Daily Intelligence Generated")

if __name__ == "__main__":
    run_synthesizer()