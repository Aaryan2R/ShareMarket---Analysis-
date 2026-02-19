from processors.symbol_resolver import ensure_symbol
import yfinance as yf
from pathlib import Path


def fetch_daily_prices(company_name: str) -> bool:
    yahoo_symbol = ensure_symbol(company_name)
    if not yahoo_symbol:
        print(f"[{company_name}] no Yahoo symbol resolved")
        return False

    try:
        df = yf.download(
            yahoo_symbol,
            period="5y",   # 🔥 upgraded from 6mo → 5 years
            auto_adjust=True,
            progress=False
        )
    except Exception as e:
        print(f"[{company_name}] Yahoo fetch error: {e}")
        return False

    if df.empty:
        print(f"[{company_name}] no price data returned")
        return False

    outdir = Path(f"data/raw/{company_name}/prices/daily")
    outdir.mkdir(parents=True, exist_ok=True)

    outfile = outdir / "daily.csv"

    # Avoid duplicate appends → overwrite fully
    df.reset_index().to_csv(outfile, index=False)

    print(f"[{company_name}] daily prices saved (5Y) to {outfile}")
    return True
