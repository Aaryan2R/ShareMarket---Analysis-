import requests
from pathlib import Path
import json
from datetime import date

INDEX = Path("data/index")
RAW = Path("data/raw")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.nseindia.com"
}

def fetch_nse_pdf(symbol: str, report_type: str, tag: str, outdir: Path) -> bool:
    """
    NSE predictable endpoint (works for many large caps).
    """
    try:
        if report_type == "annual":
            url = f"https://www.nseindia.com/api/corporates-financial-results?symbol={symbol}&period=annual"
        else:
            url = f"https://www.nseindia.com/api/corporates-financial-results?symbol={symbol}&period=quarterly"

        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()

        data = r.json()
        for item in data:
            pdf = item.get("attchmntFile")
            if not pdf:
                continue

            pdf_url = f"https://www.nseindia.com/{pdf}"
            pdf_data = requests.get(pdf_url, headers=HEADERS, timeout=30).content

            outdir.mkdir(parents=True, exist_ok=True)
            outfile = outdir / f"{symbol}_{tag}.pdf"
            outfile.write_bytes(pdf_data)
            return True

    except Exception:
        return False

    return False


def fetch_reports(symbol: str):
    status_file = INDEX / f"{symbol}_status.json"
    if not status_file.exists():
        return

    with open(status_file, "r", encoding="utf-8") as f:
        status = json.load(f)

    # Annual
    for year in status["annual"]["missing"]:
        outdir = RAW / symbol / "reports" / "annual"
        ok = fetch_nse_pdf(symbol, "annual", str(year), outdir)
        if ok:
            print(f"[{symbol}] annual {year} fetched")

    # Quarterly
    for q in status["quarterly"]["missing"]:
        outdir = RAW / symbol / "reports" / "quarterly"
        ok = fetch_nse_pdf(symbol, "quarterly", q, outdir)
        if ok:
            print(f"[{symbol}] quarterly {q} fetched")
