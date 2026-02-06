import json
import requests
from pathlib import Path

LMSTUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "meta-llama-3.1-8b-instruct"

# ---------------- LOADERS ----------------

def load_index(symbol: str) -> str:
    path = Path(f"data/index/{symbol}.json")
    if not path.exists():
        return "NO_INDEX_FOUND"
    with open(path, "r", encoding="utf-8") as f:
        return json.dumps(json.load(f), indent=2)

def load_inventory() -> str:
    path = Path("data/index/_inventory.json")
    if not path.exists():
        return "NO_INVENTORY_FOUND"
    with open(path, "r", encoding="utf-8") as f:
        return json.dumps(json.load(f), indent=2)

# ---------------- SYSTEM PROMPT ----------------

system_prompt = (
    "You are a local intraday trading assistant.\n"
    "You ONLY know data explicitly provided to you.\n"
    "You MUST NOT mention any company unless it exists in the inventory.\n"
    "If asked what data you have, answer strictly from the inventory.\n"
    "If data is missing, incomplete, or outdated, say so clearly.\n"
    "If the user greets, respond briefly and ask how you can help.\n"
    "Never use training knowledge for company availability.\n"
    "If unsure, say: 'I don’t have that data.'"
)

# ---------------- CORE CHAT ----------------

def ask(symbol: str, question: str):
    q = question.strip().lower()

    # --- greeting handling ---
    if q in ["hi", "hello", "hey", "hii", "yo"]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]

    # --- inventory questions ---
    elif any(k in q for k in [
        "what company", "which company", "what data",
        "companies do you have", "data available",
        "is data missing", "how old is the data"
    ]):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"System inventory:\n{load_inventory()}"},
            {"role": "user", "content": question}
        ]

    # --- trading / analysis questions ---
    else:
        needs_data = any(k in q for k in [
            "trade", "buy", "sell", "long", "short",
            "price", "support", "resistance",
            "risk", "bias", "sentiment"
        ])

        messages = [{"role": "system", "content": system_prompt}]

        if needs_data:
            context = load_index(symbol)
            if context == "NO_INDEX_FOUND":
                messages.append({
                    "role": "user",
                    "content": f"No indexed data exists for {symbol}."
                })
            else:
                messages.append({
                    "role": "user",
                    "content": f"Company index data:\n{context}"
                })

        messages.append({"role": "user", "content": question})

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 350
    }

    r = requests.post(LMSTUDIO_URL, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ---------------- RUN LOOP ----------------

if __name__ == "__main__":
    while True:
        q = input("\nAsk (or 'exit'): ")
        if q.lower() == "exit":
            break
        print("\n", ask("TCS", q))
