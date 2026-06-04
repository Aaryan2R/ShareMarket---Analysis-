import argparse
from pathlib import Path
from core.orchestrator import Orchestrator, IntelligenceDB
from core.market_data import normalize_existing_price_csvs

ROOT = Path(".")


def auto_register_companies(db: IntelligenceDB):
    """
    Auto-detect companies from data/raw folder
    and insert into DB if not present.
    """
    raw_path = ROOT / "data" / "raw"

    if not raw_path.exists():
        print("[SYSTEM] data/raw folder not found.")
        return

    for company_dir in raw_path.iterdir():
        if company_dir.is_dir():
            name = company_dir.name.strip()
            if not db.get_company_id(name):
                db.add_company(name)
                print(f"[SYSTEM] Registered company: {name}")


def print_ranking(ranking):
    print("\n==============================")
    print("   MARKET INTELLIGENCE RANK   ")
    print("==============================\n")

    for i, r in enumerate(ranking, 1):
        print(f"{i}. {r['company']}  |  Score: {r['composite_score']}")

    print("\n==============================\n")


def main():

    parser = argparse.ArgumentParser(description="Market Intelligence Engine")
    parser.add_argument(
        "--force-strategy",
        action="store_true",
        help="Force rebuild of strategy backtests (ignore 6h cache)"
    )
    parser.add_argument(
        "--normalize-csvs",
        action="store_true",
        help="Normalize active daily CSV files before refreshing"
    )
    parser.add_argument(
        "--rank-only",
        action="store_true",
        help="Print cached rankings without rebuilding packets"
    )
    args = parser.parse_args()

    print("\n=== MARKET INTELLIGENCE ENGINE STARTING ===\n")

    orchestrator = Orchestrator()

    # Step 1: Auto-register companies from raw data
    auto_register_companies(orchestrator.db)

    if args.normalize_csvs:
        print("[SYSTEM] Normalizing active daily CSV files...")
        for company, rows in normalize_existing_price_csvs():
            print(f"[SYSTEM] {company}: {rows} rows")

    if args.rank_only:
        print("[SYSTEM] Using cached rankings.")
        print_ranking(orchestrator.rank_all_companies())
        return

    # Step 2: Refresh all intelligence
    print("[SYSTEM] Refreshing intelligence...")
    packets = orchestrator.refresh_all(force_strategy=args.force_strategy)
    print(f"[SYSTEM] Built {len(packets)} packets.")

    # Step 3: Ranking
    ranking = orchestrator.rank_all_companies()
    print_ranking(ranking)

    print("=== SYSTEM RUN COMPLETE ===\n")


if __name__ == "__main__":
    main()
