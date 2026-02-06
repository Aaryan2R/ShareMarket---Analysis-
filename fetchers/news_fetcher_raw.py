import feedparser
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import quote


def fetch_raw_news(symbol: str) -> bool:
    query = quote(f"{symbol} stock")  # FIX: URL encode
    rss_url = (
        f"https://news.google.com/rss/search?"
        f"q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    )

    feed = feedparser.parse(rss_url)
    if not feed.entries:
        print(f"[{symbol}] no news found")
        return False

    items = []
    for e in feed.entries[:10]:
        items.append({
            "title": e.get("title"),
            "source": e.get("source", {}).get("title"),
            "published": e.get("published"),
            "link": e.get("link"),
            "fetched_at": datetime.utcnow().isoformat()
        })

    outdir = Path(f"data/cleaned/{symbol}/news")
    outdir.mkdir(parents=True, exist_ok=True)

    with open(outdir / "raw_news.json", "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

    print(f"[{symbol}] raw news fetched")
    return True


if __name__ == "__main__":
    fetch_raw_news("TCS")
    fetch_raw_news("INFY")
