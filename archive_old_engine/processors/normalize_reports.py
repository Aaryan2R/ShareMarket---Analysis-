import re
from pathlib import Path

BASE = Path("data/raw")

def detect_quarter(name: str):
    m = re.search(r"\bq([1-4])\b", name)
    return f"Q{m.group(1)}" if m else None

def detect_fy_from_range(name: str):
    """
    Detect Indian FY like 2025-26 -> FY2026
    """
    m = re.search(r"(20\d{2})\s*-\s*(\d{2})", name)
    if not m:
        return None

    start_year = int(m.group(1))
    end_suffix = int(m.group(2))
    end_year = (start_year // 100) * 100 + end_suffix
    return end_year

def detect_single_year(name: str):
    m = re.search(r"(20\d{2})", name)
    return int(m.group(1)) if m else None

def normalize_company(company_name: str):
    misc = BASE / company_name / "reports" / "misc"
    if not misc.exists():
        return

    annual_dir = BASE / company_name / "reports" / "annual"
    quarterly_dir = BASE / company_name / "reports" / "quarterly"

    annual_dir.mkdir(parents=True, exist_ok=True)
    quarterly_dir.mkdir(parents=True, exist_ok=True)

    for pdf in misc.glob("*.pdf"):
        name = pdf.name.lower()

        quarter = detect_quarter(name)
        fy = detect_fy_from_range(name)

        # Annual
        if "annual" in name or "integrated" in name:
            year = detect_single_year(name)
            if year:
                target = annual_dir / f"{year}.pdf"
                if not target.exists():
                    pdf.rename(target)
                    print(f"[{company_name}] annual normalized to {target.name}")
                continue

        # Quarterly
        if quarter and fy:
            target = quarterly_dir / f"FY{fy}_{quarter}.pdf"
            if not target.exists():
                pdf.rename(target)
                print(f"[{company_name}] quarterly normalized to {target.name}")
            continue

        # Keep misc
        print(f"[{company_name}] kept misc {pdf.name}")

def run_normalize():
    for company_dir in BASE.iterdir():
        if company_dir.is_dir():
            normalize_company(company_dir.name)

if __name__ == "__main__":
    run_normalize()
