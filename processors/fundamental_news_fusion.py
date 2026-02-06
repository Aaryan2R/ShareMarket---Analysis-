import json
from pathlib import Path

BASE = Path("data/cleaned")

def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def fuse_company(company: str):
    signals = BASE / company / "signals"

    trend = load_json(signals / "trend_strength.json")
    news = load_json(signals / "news_sentiment.json")
    inventory = load_json(BASE / company / "inventory.json")

    if not trend:
        print(f"[{company}] missing trend strength")
        return

    score = trend["confidence_score"]

    # --- news bias ---
    news_bias = "NEUTRAL"
    if news:
        sentiment = news.get("overall_label")
        if sentiment == "positive":
            score += 10
            news_bias = "POSITIVE"
        elif sentiment == "negative":
            score -= 10
            news_bias = "NEGATIVE"

    # --- fundamentals ---
    fundamental_strength = "WEAK"
    if inventory:
        annual = inventory.get("annual_reports", 0)
        quarterly = inventory.get("quarterly_reports", 0)

        if annual > 0 and quarterly > 0:
            score += 10
            fundamental_strength = "STRONG"
        elif annual > 0 or quarterly > 0:
            fundamental_strength = "MODERATE"
        else:
            score -= 15

    score = max(0, min(100, score))

    if score >= 75:
        trade_bias = "HIGH_CONVICTION"
    elif score >= 55:
        trade_bias = "TRADEABLE"
    elif score >= 40:
        trade_bias = "LOW_CONFIDENCE"
    else:
        trade_bias = "AVOID"

    output = {
        "final_confidence_score": score,
        "news_bias": news_bias,
        "fundamental_strength": fundamental_strength,
        "final_trade_bias": trade_bias
    }

    out = signals / "final_fusion.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"[{company}] final bias -> {trade_bias} ({score})")

def run_fusion():
    for c in BASE.iterdir():
        if c.is_dir():
            fuse_company(c.name)

if __name__ == "__main__":
    run_fusion()
