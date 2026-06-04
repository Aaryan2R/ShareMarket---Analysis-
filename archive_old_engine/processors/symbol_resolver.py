import json
import requests
from pathlib import Path
from datetime import date

OUT_DIR = Path("data/symbols")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}

def resolve_symbols(company_name: str) -> dict | None:
    """
    Resolve NSE + Yahoo symbols using Yahoo Finance search API
    """
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {
        "q": company_name,
        "quotesCount": 5,
        "newsCount": 0,
        "region": "IN"
    }

    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    data = r.json()

    for q in data.get("quotes", []):
        symbol = q.get("symbol", "")
        exchange = q.get("exchange", "")

        if symbol.endswith(".NS"):
            return {
                "company_name": company_name,
                "symbols": {
                    "nse": symbol.replace(".NS", ""),
                    "yahoo": symbol
                },
                "verified_on": date.today().isoformat()
            }

    return None


def ensure_symbol(company_name: str) -> str | None:
    out = OUT_DIR / f"{company_name}.json"

    if out.exists():
        with open(out, "r", encoding="utf-8") as f:
            return json.load(f)["symbols"]["yahoo"]

    resolved = resolve_symbols(company_name)
    if not resolved:
        print(f"[{company_name}] symbol resolution FAILED")
        return None

    with open(out, "w", encoding="utf-8") as f:
        json.dump(resolved, f, indent=2)

    print(f"[{company_name}] symbols resolved → {resolved['symbols']}")
    return resolved["symbols"]["yahoo"]
