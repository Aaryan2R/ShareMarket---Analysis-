import feedparser
from datetime import datetime
from pathlib import Path
import json

def fetch_news(symbol: str) -> bool:
    print(f"[{symbol}] attempting news fetch")

    query = f"{symbol}+stock"
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    feed = feedparser.parse(rss_url)

    if not feed.entries:
        print(f"[{symbol}] no news found")
        return False

    items = []
    for e in feed.entries[:5]:
        items.append({
            "title": e.get("title"),
            "source": e.get("source", {}).get("title"),
            "published": e.get("published"),
            "link": e.get("link"),
            "fetched_at": datetime.utcnow().isoformat()
        })

    outdir = Path(f"data/raw/{symbol}/news")
    outdir.mkdir(parents=True, exist_ok=True)

    outfile = outdir / "latest_news.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

    print(f"[{symbol}] news saved → {outfile}")
    return True
