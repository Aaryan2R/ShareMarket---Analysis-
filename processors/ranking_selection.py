import json
from pathlib import Path
from datetime import date

BASE = Path("data/cleaned")
OUTDIR = BASE / "_ranking"
OUTDIR.mkdir(parents=True, exist_ok=True)


def safe_load(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def score_company(company: str):
    signals = BASE / company / "signals"

    final_bias = safe_load(signals / "final_bias.json")
    price_signal = safe_load(signals / "price_signal.json")
    volatility = safe_load(signals / "volatility_risk.json")
    momentum = safe_load(signals / "momentum_confirmation.json")

    if not final_bias:
        return None

    score = final_bias.get("score", 0)
    reasons = []

    # --- Momentum ---
    if momentum:
        m = momentum.get("momentum")
        if m == "STRONG_BULLISH":
            score += 10
            reasons.append("strong momentum")
        elif m == "STRONG_BEARISH":
            score -= 10

    # --- Volatility ---
    if volatility:
        v = volatility.get("risk")
        if v == "HIGH":
            score -= 10
            reasons.append("high volatility")
        elif v == "LOW":
            score += 5

    # --- Price signal ---
    if price_signal:
        p = price_signal.get("price_signal")
        if p == "BULLISH":
            score += 5
        elif p == "BEARISH":
            score -= 5
            reasons.append("bearish price")

    # --- Verdict ---
    if score >= 85:
        verdict = "INTRADAY + SWING BUY"
    elif score >= 70:
        verdict = "SWING BUY"
    elif score >= 55:
        verdict = "WATCH"
    else:
        verdict = "AVOID"

    return {
        "company": company,
        "score": score,
        "verdict": verdict,
        "reason": ", ".join(reasons) if reasons else "mixed signals"
    }


def run_ranking():
    results = []

    for company_dir in BASE.iterdir():
        if company_dir.is_dir() and not company_dir.name.startswith("_"):
            res = score_company(company_dir.name)
            if res:
                results.append(res)

    results.sort(key=lambda x: x["score"], reverse=True)

    output = {
        "date": date.today().isoformat(),
        "ranking": results,
        "top_picks": [r for r in results if r["verdict"] in ("INTRADAY + SWING BUY", "SWING BUY")],
        "avoid": [r for r in results if r["verdict"] == "AVOID"]
    }

    with open(OUTDIR / "today.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("[A5] Ranking & selection generated")


if __name__ == "__main__":
    run_ranking()
