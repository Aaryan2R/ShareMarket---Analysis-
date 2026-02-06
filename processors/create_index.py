import json
from pathlib import Path
from datetime import date

def create_company_index(company_name, symbol, exchange=("NSE", "BSE")):
    index_dir = Path("data/index")
    index_dir.mkdir(parents=True, exist_ok=True)

    index_path = index_dir / f"{symbol}.json"

    if index_path.exists():
        print(f"[{symbol}] index already exists")
        return

    index = {
        "meta": {
            "company_name": company_name,
            "symbol": symbol,
            "exchange": list(exchange),
            "created_on": date.today().isoformat(),
            "status": "active"
        },
        "knowledge": {
            "sections": {},
            "semantic_sections": {},
            "last_updated": None
        },
        "signals": {
            "news_sentiment": {},
            "price_trend": {}
        }
    }

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"[{symbol}] unified index created")

if __name__ == "__main__":
    create_company_index("Tata Consultancy Services Ltd", "TCS")
    create_company_index("Infosys Ltd", "INFY")
