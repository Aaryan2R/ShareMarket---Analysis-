import json
import pandas as pd
from pathlib import Path

RAW = Path("data/raw")
CLEAN = Path("data/cleaned")
OUT = Path("data/cleaned/_trades")
OUT.mkdir(parents=True, exist_ok=True)


def atr(df: pd.DataFrame, period: int = 14):
    if len(df) < period + 1:
        return None

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

    val = tr.rolling(period).mean().iloc[-1]
    return None if pd.isna(val) else float(val)


def load_json_safe(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def generate_trade(company: str):
    sig_dir = CLEAN / company / "signals"
    daily_path = RAW / company / "prices" / "daily" / "daily.csv"

    if not daily_path.exists():
        return None

    # ---- Load & clean price data ----
    daily = pd.read_csv(daily_path)

    for col in ["High", "Low", "Close"]:
        if col not in daily.columns:
            return None
        daily[col] = pd.to_numeric(daily[col], errors="coerce")

    daily = daily.dropna(subset=["High", "Low", "Close"])
    if daily.empty:
        return None

    last_close = float(daily.iloc[-1]["Close"])
    atr_val = atr(daily)

    if atr_val is None:
        return None

    # ---- Load signals safely ----
    price_signal = load_json_safe(sig_dir / "price_signal.json")
    final_bias = load_json_safe(sig_dir / "final_fusion.json")
    volatility = load_json_safe(sig_dir / "volatility_risk.json")

    bias_value = final_bias.get("final_trade_bias")
    score_value = final_bias.get("final_confidence_score")

    price_sig_value = price_signal.get("price_signal")
    risk_value = volatility.get("risk")

    # ---- Direction logic ----
    direction = "AVOID"

    if bias_value == "HIGH_CONVICTION":
        if price_sig_value == "BULLISH":
            direction = "LONG"
        elif price_sig_value == "BEARISH":
            direction = "SHORT"

    trade_type = {
        "LOW": "POSITIONAL",
        "MEDIUM": "SWING",
        "HIGH": "INTRADAY",
    }.get(risk_value, "INTRADAY")

    if direction == "LONG":
        sl = last_close - atr_val * 1.2
        target = last_close + atr_val * 2.5

    elif direction == "SHORT":
        sl = last_close + atr_val * 1.2
        target = last_close - atr_val * 2.5

    else:
        return {
            "company": company,
            "action": "AVOID",
            "reason": "No aligned conviction",
            "confidence": score_value,
        }

    rr = abs(target - last_close) / abs(last_close - sl)

    return {
        "company": company,
        "trade_type": trade_type,
        "direction": direction,
        "entry": round(last_close, 2),
        "stop_loss": round(sl, 2),
        "target": round(target, 2),
        "risk_reward": round(rr, 2),
        "confidence": score_value,
    }


def run_trades():
    results = []

    for company_dir in RAW.iterdir():
        if company_dir.is_dir():
            trade = generate_trade(company_dir.name)
            if trade is not None:
                results.append(trade)

    OUT.joinpath("today.json").write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )

    print("[A7] trade execution plans generated")


if __name__ == "__main__":
    run_trades()
