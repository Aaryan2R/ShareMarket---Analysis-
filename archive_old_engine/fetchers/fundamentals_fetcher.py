import yfinance as yf
import json
from pathlib import Path
from datetime import date

TODAY = date.today().isoformat()

def df_to_clean_dict(df):
    """
    Convert DataFrame with Timestamp columns to JSON-safe dict
    """
    if df is None or df.empty:
        return {}

    df = df.copy()
    df.columns = [str(c.date()) if hasattr(c, "date") else str(c) for c in df.columns]
    df.index = [str(i) for i in df.index]
    return df.fillna(0).to_dict()

def fetch_fundamentals(symbol: str) -> bool:
    ticker = yf.Ticker(symbol)

    outdir = Path(f"data/cleaned/{symbol}/fundamentals")
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        # -------- Financials --------
        fin_data = df_to_clean_dict(ticker.financials)
        with open(outdir / "financials.json", "w", encoding="utf-8") as f:
            json.dump(fin_data, f, indent=2)

        # -------- Cashflow --------
        cf_data = df_to_clean_dict(ticker.cashflow)
        with open(outdir / "cashflow.json", "w", encoding="utf-8") as f:
            json.dump(cf_data, f, indent=2)

        # -------- Ratios --------
        info = ticker.info or {}
        ratios = {
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency"),
            "last_updated": TODAY
        }

        with open(outdir / "ratios.json", "w", encoding="utf-8") as f:
            json.dump(ratios, f, indent=2)

        print(f"[{symbol}] fundamentals fetched")
        return True

    except Exception as e:
        print(f"[{symbol}] fundamentals error:", e)
        return False


if __name__ == "__main__":
    fetch_fundamentals("TCS")
    fetch_fundamentals("INFY")
