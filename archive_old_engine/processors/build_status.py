import json
from pathlib import Path
from datetime import datetime

def build_status(symbol: str):
    base = Path(f"data")
    status = {
        "symbol": symbol,
        "checked_at": datetime.utcnow().isoformat(),
        "news": {},
        "prices": {},
        "reports": {}
    }

    # --- NEWS ---
    news_file = base / "cleaned" / symbol / "news" / "raw_news.json"
    if news_file.exists():
        with open(news_file, "r", encoding="utf-8") as f:
            items = json.load(f)
        status["news"] = {
            "available": True,
            "count": len(items),
            "latest": items[0]["published"] if items else None
        }
    else:
        status["news"] = {"available": False}

    # --- DAILY PRICES ---
    price_dir = base / "raw" / symbol / "prices" / "daily"
    if price_dir.exists():
        files = sorted(price_dir.glob("*.csv"))
        status["prices"] = {
            "available": bool(files),
            "latest_file": files[-1].name if files else None
        }
    else:
        status["prices"] = {"available": False}

    # --- REPORTS ---
    for r in ["quarterly", "annual"]:
        path = base / "raw" / symbol / "reports" / r
        status["reports"][r] = path.exists()

    # --- SAVE ---
    outdir = base / "index"
    outdir.mkdir(exist_ok=True)
    with open(outdir / f"{symbol}_status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

    print(f"[{symbol}] status built")


if __name__ == "__main__":
    build_status("TCS")
    build_status("INFY")
