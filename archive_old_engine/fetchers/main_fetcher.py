import pandas as pd
from datetime import date

# IMPORT REAL FETCHERS (NO STUBS)
from price_fetcher import fetch_daily_prices
from news_fetcher import fetch_news

# ---------------- CONFIG ----------------
TODAY = date.today().isoformat()

# --------------- HELPERS ----------------
def due(d):
    return not d or pd.isna(d)

# ---------------- MAIN ------------------
df = pd.read_csv("data/companies.csv", dtype=str)

for i, r in df.iterrows():
    symbol = r["symbol"]
    print(f"\n=== {symbol} ===")

    try:
        # DAILY PRICES
        if due(r["last_price_daily"]):
            success = fetch_daily_prices(symbol)
            if success:
                df.at[i, "last_price_daily"] = TODAY

        # NEWS
        if due(r["last_news"]):
            success = fetch_news(symbol)
            if success:
                df.at[i, "last_news"] = TODAY

        df.at[i, "status"] = "done"

    except Exception as e:
        df.at[i, "status"] = "failed"
        print(f"[{symbol}] ERROR:", e)

df.to_csv("data/companies.csv", index=False)
print("\nMain fetch cycle completed")
