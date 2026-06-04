# migrate_news_to_tinydb.py
from pathlib import Path
import json
try:
    from tinydb import TinyDB
    TINYDB_OK = True
except Exception:
    TINYDB_OK = False

ROOT = Path(".")
NEWS_JSON_PATH = ROOT / "data" / "cleaned" / "_news.json"
TINYDB_PATH = ROOT / "data" / "cleaned" / "news_db.json"

if not TINYDB_OK:
    print("tinydb not installed. Install via `pip install tinydb` to run migration.")
    raise SystemExit(1)

if not NEWS_JSON_PATH.exists():
    print("No legacy news file found at", NEWS_JSON_PATH)
    raise SystemExit(0)

with open(NEWS_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

db = TinyDB(str(TINYDB_PATH))
table = db.table("news")
# clear existing
table.truncate()

for company, items in data.items():
    for it in items:
        rec = {"company": company, "title": it.get("title"), "link": it.get("link"), "pubDate": it.get("pubDate")}
        table.insert(rec)

db.close()
print("Migration complete. TinyDB at", TINYDB_PATH)