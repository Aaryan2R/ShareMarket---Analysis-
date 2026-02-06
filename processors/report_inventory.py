import pandas as pd
import json
from pathlib import Path
from datetime import date

TODAY = date.today().isoformat()

def run_inventory():
    df = pd.read_csv("data/companies.csv", dtype=str)

    for i, r in df.iterrows():
        company = str(r.get("company_name", "")).strip()
        if not company:
            continue

        safe_name = company.replace(" ", "_").upper()
        base = Path(f"data/raw/{safe_name}")

        status = "pending"
        reports_complete = True

        # ---- check reports ----
        reports_path = base / "reports"
        if not reports_path.exists() or not any(reports_path.rglob("*.pdf")):
            reports_complete = False

        # ---- check prices ----
        prices_path = base / "prices" / "daily"
        if not prices_path.exists() or not any(prices_path.glob("*.csv")):
            reports_complete = False

        # ---- check news ----
        news_path = base / "news"
        if not news_path.exists() or not any(news_path.glob("*.json")):
            reports_complete = False

        status = "done" if reports_complete else "failed"

        df.at[i, "status"] = status
        df.at[i, "reports_complete"] = "True" if reports_complete else "False"

        print(f"[{company}] inventory updated")

    df.to_csv("data/companies.csv", index=False)
