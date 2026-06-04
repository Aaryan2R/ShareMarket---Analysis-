import json
from pathlib import Path
from processors.regime_filter import compute_regime
from processors.live_signal_engine import run_live_engine

REGIME_FILE = Path("data/cleaned/_market_regime.json")
LIVE_FILE = Path("data/live_signals/today.json")
APPROVED_FILE = Path("data/cleaned/_approved_universe.json")


def print_header():
    print("\n=== DAILY RUN STARTED ===\n")


def print_footer():
    print("\n=== DAILY RUN COMPLETE ===\n")


def explain_day():
    if not REGIME_FILE.exists():
        print("Market regime not found.")
        return

    regime = json.loads(REGIME_FILE.read_text()).get("regime")

    print(f"Market Regime: {regime}")

    if not APPROVED_FILE.exists():
        print("No approved universe found.")
        return

    approved = json.loads(APPROVED_FILE.read_text())

    if not LIVE_FILE.exists():
        print("No live signals generated.")
        return

    signals = json.loads(LIVE_FILE.read_text())

    if not signals:
        print("\nDecision Summary:")
        print("No trades today.")
        print("Reason: Breakout + Volume conditions not satisfied.")
        return

    print("\nTrade Setups:\n")

    for s in signals:
        print(f"Stock: {s['company']}")
        print(f"Direction: {s['direction']}")
        print(f"Entry: {s['entry']}")
        print(f"Stop Loss: {s['stop_loss']}")
        print(f"Target: {s['target']}")
        print(f"Risk-Reward: {s['risk_reward']}")
        print("-" * 30)


def main():
    print_header()

    # Step 1: Compute regime
    compute_regime()

    # Step 2: Run live engine
    run_live_engine()

    # Step 3: Explain results
    explain_day()

    print_footer()


if __name__ == "__main__":
    main()