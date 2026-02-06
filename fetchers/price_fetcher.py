import yfinance as yf
from datetime import date
from pathlib import Path

TODAY = date.today().isoformat()

def fetch_daily_prices(symbol: str) -> bool:
    print(f"[{symbol}] attempting daily price fetch (Yahoo)")

    ticker = yf.Ticker(f"{symbol}.NS")
    df = ticker.history(period="1d")

    if df.empty:
        print(f"[{symbol}] no price data found")
        return False

    outdir = Path(f"data/raw/{symbol}/prices/daily")
    outdir.mkdir(parents=True, exist_ok=True)

    outfile = outdir / f"{symbol}_DAILY_{TODAY}.csv"
    df.reset_index().to_csv(outfile, index=False)

    print(f"[{symbol}] daily prices saved → {outfile}")
    return True
