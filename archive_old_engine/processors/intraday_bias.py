import json
from pathlib import Path
from datetime import date

TODAY = date.today().isoformat()

def compute_intraday_bias(symbol: str) -> bool:
    index_path = Path(f"data/index/{symbol}.json")
    if not index_path.exists():
        print(f"[{symbol}] index not found")
        return False

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    signals = index.get("signals", {})
    score = 0
    reasons = []

    # --- News sentiment ---
    news = signals.get("news_sentiment", {})
    news_label = news.get("overall")

    if news_label == "positive":
        score += 1
        reasons.append("positive news")
    elif news_label == "negative":
        score -= 1
        reasons.append("negative news")

    # --- Weekly trend ---
    trend = signals.get("price_trend", {}).get("weekly_trend")

    if trend == "UP":
        score += 1
        reasons.append("weekly uptrend")
    elif trend == "DOWN":
        score -= 1
        reasons.append("weekly downtrend")

    # --- Final bias ---
    if score >= 1:
        bias = "BULLISH"
    elif score <= -1:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    index["signals"]["intraday_bias"] = {
        "bias": bias,
        "score": score,
        "reasons": reasons,
        "last_updated": TODAY
    }

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"[{symbol}] intraday bias → {bias}")
    return True


if __name__ == "__main__":
    compute_intraday_bias("TCS")
    compute_intraday_bias("INFY")
