"""
Main entry point for Intraday Helper system

Execution order (LOCKED):
1. Inventory (truth check)
2. IR report fetch (best source)
3. Exchange report fetch (fallback)
4. Daily price fetch (independent)
5. Price aggregation (weekly + monthly)
6. Normalize reports (organize + rename)
7. Inventory re-check (truth update)
"""

import pandas as pd
import sys

from processors.report_inventory import run_inventory
from processors.normalize_reports import run_normalize
from processors.price_aggregate import aggregate_prices

from fetchers.ir_report_fetcher import fetch_ir_reports
from fetchers.report_fetcher import fetch_reports
from fetchers.price_daily_fetcher import fetch_daily_prices

sys.stdout.reconfigure(encoding="utf-8")


def main():
    print("\n=== Starting Intraday Helper ===\n")

    # 1️⃣ Inventory first (truth layer)
    print("[SYSTEM] Running inventory check")
    run_inventory()

    # 2️⃣ Load companies.csv safely
    try:
        df = pd.read_csv("data/companies.csv", dtype=str)
    except FileNotFoundError:
        print("[ERROR] data/companies.csv not found")
        return

    if df.empty or "company_name" not in df.columns:
        print("[SYSTEM] No valid companies found in CSV")
        return

    # 3️⃣ Per-company pipeline
    for _, row in df.iterrows():
        company = str(row["company_name"]).strip()

        if not company:
            continue

        print(f"\n[SYSTEM] Processing {company}")

        # --- IR reports (priority source) ---
        try:
            print(f"[{company}] IR fetch attempt")
            fetch_ir_reports(company)
        except Exception as e:
            print(f"[{company}] IR fetch failed:", e)

        # --- NSE/BSE fallback ---
        try:
            print(f"[{company}] Exchange fetch attempt")
            fetch_reports(company)
        except Exception as e:
            print(f"[{company}] Exchange fetch failed:", e)

        # --- Daily prices ---
        try:
            print(f"[{company}] Daily price fetch")
            fetch_daily_prices(company)
        except Exception as e:
            print(f"[{company}] Daily price fetch failed:", e)

        # --- Weekly + Monthly aggregation ---
        try:
            print(f"[{company}] Aggregating prices")
            aggregate_prices(company)
        except Exception as e:
            print(f"[{company}] Price aggregation failed:", e)

    # 4️⃣ Normalize reports
    print("\n[SYSTEM] Normalizing reports")
    try:
        run_normalize()
    except Exception as e:
        print("[SYSTEM] Normalization failed:", e)

    # 5️⃣ Final inventory refresh
    print("\n[SYSTEM] Re-checking inventory")
    run_inventory()

    print("\n=== System run completed ===\n")


if __name__ == "__main__":
    main()
