import pandas as pd

from core.market_data import normalize_price_frame


def test_normalize_price_frame_drops_ticker_row():
    raw = pd.DataFrame(
        [
            {"Date": "", "Close": "INFY.NS", "High": "INFY.NS", "Low": "INFY.NS", "Open": "INFY.NS", "Volume": "INFY.NS"},
            {"Date": "2026-01-01", "Close": "100", "High": "105", "Low": "95", "Open": "98", "Volume": "1000"},
            {"Date": "2026-01-02", "Close": "102", "High": "106", "Low": "99", "Open": "101", "Volume": "900"},
        ]
    )

    clean = normalize_price_frame(raw)

    assert len(clean) == 2
    assert clean["Close"].tolist() == [100, 102]
    assert clean["Date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-01-01", "2026-01-02"]

