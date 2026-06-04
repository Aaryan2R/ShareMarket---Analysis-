import json
from pathlib import Path
from datetime import date

TODAY = date.today().isoformat()

def compute_risk_levels(symbol: str) -> bool:
    index_path = Path(f"data/index/{symbol}.json")
    if not index_path.exists():
        print(f"[{symbol}] index not found")
        return False

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    signals = index.get("signals", {})
    bias = signals.get("intraday_bias", {}).get("bias")
    sr = signals.get("support_resistance", {})

    support = sr.get("support")
    resistance = sr.get("resistance")

    if not support or not resistance or not bias:
        print(f"[{symbol}] insufficient data for risk")
        return False

    mid = round((support + resistance) / 2, 2)

    if bias == "BULLISH":
        risk = {
            "direction": "LONG",
            "stop_loss": round(support * 0.995, 2),
            "target_1": mid,
            "target_2": round(resistance * 0.995, 2)
        }

    elif bias == "BEARISH":
        risk = {
            "direction": "SHORT",
            "stop_loss": round(resistance * 1.005, 2),
            "target_1": mid,
            "target_2": round(support * 1.005, 2)
        }

    else:
        risk = {
            "direction": "NO_TRADE",
            "reason": "Neutral bias"
        }

    index["signals"]["risk_management"] = {
        **risk,
        "last_updated": TODAY
    }

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"[{symbol}] risk levels calculated")
    return True


if __name__ == "__main__":
    compute_risk_levels("TCS")
    compute_risk_levels("INFY")
