# core/symbol_resolver.py

import yfinance as yf
import requests


def resolve_symbol(company_name):
    """
    Hybrid resolution:
    1. Try Yahoo search
    2. Extract NSE symbol if exists
    """

    try:
        search = yf.Ticker(company_name)
        info = search.info
        symbol = info.get("symbol")

        if symbol:
            return {
                "nse_symbol": symbol,
                "bse_code": None
            }

    except Exception:
        pass

    # fallback simple guess
    guess = company_name.split()[0].upper() + ".NS"
    return {
        "nse_symbol": guess,
        "bse_code": None
    }