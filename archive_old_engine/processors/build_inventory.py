import json
from pathlib import Path
from datetime import date

INDEX_DIR = Path("data/index")

inventory = {
    "generated_on": date.today().isoformat(),
    "companies": []
}

for f in INDEX_DIR.glob("*.json"):
    if f.name.startswith("_"):
        continue

    with open(f, "r", encoding="utf-8") as file:
        data = json.load(file)

    inventory["companies"].append({
        "symbol": data["meta"]["symbol"],
        "company_name": data["meta"]["company_name"],
        "last_updated": data["knowledge"].get("last_updated"),
        "has_news_sentiment": bool(data["signals"].get("news_sentiment")),
        "has_price_trend": bool(data["signals"].get("price_trend"))
    })

with open(INDEX_DIR / "_inventory.json", "w", encoding="utf-8") as f:
    json.dump(inventory, f, indent=2)

print("Inventory built")
