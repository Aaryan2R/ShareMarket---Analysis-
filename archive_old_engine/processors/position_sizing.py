import json
from pathlib import Path

SIGNALS_PATH = Path("data/live_signals/today.json")
OUT_PATH = Path("data/live_signals/execution_plan.json")

# ---- CONFIG ----
TOTAL_CAPITAL = 500000        # change anytime
RISK_PER_TRADE_PCT = 0.01     # 1% risk per trade
# ----------------


def calculate_position(signal):
    entry = signal["entry"]
    sl = signal["stop_loss"]

    risk_per_share = abs(entry - sl)
    if risk_per_share == 0:
        return None

    capital_risk = TOTAL_CAPITAL * RISK_PER_TRADE_PCT
    quantity = int(capital_risk / risk_per_share)

    if quantity <= 0:
        return None

    position_value = quantity * entry

    return {
        "company": signal["company"],
        "direction": signal["direction"],
        "entry": entry,
        "stop_loss": sl,
        "target": signal["target"],
        "risk_reward": signal["risk_reward"],
        "quantity": quantity,
        "capital_required": round(position_value, 2),
        "risk_amount": round(quantity * risk_per_share, 2)
    }


def run_position_sizing():
    if not SIGNALS_PATH.exists():
        print("No live signals found.")
        return

    signals = json.loads(SIGNALS_PATH.read_text())
    if not signals:
        print("No trades today.")
        OUT_PATH.write_text("[]")
        return

    plans = []

    for signal in signals:
        plan = calculate_position(signal)
        if plan:
            plans.append(plan)

    OUT_PATH.write_text(json.dumps(plans, indent=2))
    print("[A12] Execution plan generated")


if __name__ == "__main__":
    run_position_sizing()
