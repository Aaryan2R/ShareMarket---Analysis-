import json
from pathlib import Path
from difflib import SequenceMatcher

TRADES_PATH = Path("data/cleaned/_trades/today.json")
RANK_PATH = Path("data/cleaned/_ranking/today.json")


# ---------- Utility ----------

def load_data():
    trades = []
    ranking = []

    if TRADES_PATH.exists():
        trades = json.loads(TRADES_PATH.read_text(encoding="utf-8"))

    if RANK_PATH.exists():
        ranking = json.loads(RANK_PATH.read_text(encoding="utf-8"))

    return trades, ranking


def normalize(text):
    return text.lower().strip()


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def matches_company(query, company):
    q = normalize(query)
    c = normalize(company)

    if not q:
        return False

    # Exact match
    if q == c:
        return True

    # Partial match
    if q in c:
        return True

    # Acronym match (Tata Consultancy Services → TCS)
    words = [w for w in company.split() if w.isalpha()]
    acronym = "".join(word[0] for word in words).lower()
    if acronym and q == acronym:
        return True

    # Fuzzy similarity (typo tolerance)
    if similarity(q, c) > 0.6:
        return True

    return False


def safest_trade(trades):
    valid = [t for t in trades if t.get("direction") in ("LONG", "SHORT")]
    if not valid:
        return None
    return sorted(valid, key=lambda x: x.get("risk_reward", 0), reverse=True)[0]


# ---------- Main Logic ----------

def handle_query(q):
    trades, ranking = load_data()
    q = normalize(q)

    if not q:
        return "Please type a company name, 'buy', 'sell', 'safest', or 'avoid'."

    if not trades:
        return "No trade data available. Run trade_execution first."

    # BUY → Best LONG
    if "buy" in q:
        longs = [t for t in trades if t.get("direction") == "LONG"]
        if not longs:
            return "No strong LONG setups available today."
        best = sorted(longs, key=lambda x: x.get("confidence", 0), reverse=True)[0]
        return f"Best BUY candidate: {best['company']} (Confidence {best['confidence']})"

    # SELL → Best SHORT
    if "sell" in q:
        shorts = [t for t in trades if t.get("direction") == "SHORT"]
        if not shorts:
            return "No strong SHORT setups available today."
        best = sorted(shorts, key=lambda x: x.get("confidence", 0), reverse=True)[0]
        return f"Best SELL candidate: {best['company']} (Confidence {best['confidence']})"

    # Safest trade
    if "safest" in q:
        trade = safest_trade(trades)
        if not trade:
            return "No valid trade setups available."
        return (
            f"Safest trade: {trade['company']} ({trade.get('direction', 'NA')})\n"
            f"Entry: {trade.get('entry', 'NA')}\n"
            f"Stop-loss: {trade.get('stop_loss', 'NA')}\n"
            f"Target: {trade.get('target', 'NA')}\n"
            f"Risk-Reward: {trade.get('risk_reward', 'NA')}"
        )

    # Avoid list
    if "avoid" in q:
        avoids = [t["company"] for t in trades if t.get("action") == "AVOID"]
        if not avoids:
            return "No stocks marked as avoid today."
        return "Avoid today: " + ", ".join(avoids)

    # Company-specific query
    matched = None
    for t in trades:
        if matches_company(q, t["company"]):
            matched = t
            break

    if matched:
        if matched.get("action") == "AVOID":
            return f"{matched['company']} is marked as AVOID due to low alignment."
        return (
            f"{matched['company']} Trade Plan:\n"
            f"Type: {matched.get('trade_type', 'NA')}\n"
            f"Direction: {matched.get('direction', 'NA')}\n"
            f"Entry: {matched.get('entry', 'NA')}\n"
            f"Stop-loss: {matched.get('stop_loss', 'NA')}\n"
            f"Target: {matched.get('target', 'NA')}\n"
            f"Risk-Reward: {matched.get('risk_reward', 'NA')}\n"
            f"Confidence Score: {matched.get('confidence', 'NA')}"
        )

    return "No matching company found. Try a valid company name."


# ---------- Chat Loop ----------

def chat():
    print("Trade Assistant Ready (type 'exit' to quit)")
    while True:
        try:
            q = input("\nAsk: ")
        except KeyboardInterrupt:
            print("\nExiting.")
            break

        if q.lower() == "exit":
            break

        print("\n", handle_query(q))


if __name__ == "__main__":
    chat()
