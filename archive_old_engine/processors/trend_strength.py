import json
from pathlib import Path

BASE = Path("data/cleaned")

def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def compute_trend_strength(company: str):
    signals_dir = BASE / company / "signals"

    price = load_json(signals_dir / "price_signal.json")
    vol = load_json(signals_dir / "volatility_risk.json")
    mom = load_json(signals_dir / "momentum.json")

    if not price or not vol or not mom:
        print(f"[{company}] missing inputs for trend strength")
        return

    score = 50

    # --- price direction ---
    ps = price.get("price_signal")
    if ps in ("BULLISH", "BEARISH"):
        score += 15

    # --- momentum ---
    ms = mom.get("momentum")
    if ms in ("STRONG_BULLISH", "STRONG_BEARISH"):
        score += 25
    elif ms == "WEAK":
        score += 10

    # --- volatility risk ---
    vr = vol.get("risk_level")
    if vr == "LOW":
        score += 10
    elif vr == "HIGH":
        score -= 15

    score = max(0, min(100, score))

    if score >= 70:
        strength = "STRONG_TREND"
    elif score >= 40:
        strength = "WEAK_TREND"
    else:
        strength = "NO_TREND"

    output = {
        "confidence_score": score,
        "trend_strength": strength
    }

    out = signals_dir / "trend_strength.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"[{company}] trend strength -> {strength} ({score})")

def run_trend_strength():
    for c in BASE.iterdir():
        if c.is_dir():
            compute_trend_strength(c.name)

if __name__ == "__main__":
    run_trend_strength()
