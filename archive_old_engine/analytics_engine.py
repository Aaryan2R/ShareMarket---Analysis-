# core/analytics_engine.py

import pandas as pd
import numpy as np


class AnalyticsEngine:

    @staticmethod
    def compute_win_rate(df, days=30):
        sample = df.tail(days)
        wins = (sample["Close"] > sample["Open"]).sum()
        return round((wins / len(sample)) * 100, 2) if len(sample) > 0 else None

    @staticmethod
    def compute_volatility(df, days=30):
        returns = df["Close"].pct_change().dropna()
        return round(returns.tail(days).std() * 100, 2)

    @staticmethod
    def compute_atr(df, period=14):
        high_low = df["High"] - df["Low"]
        high_close = np.abs(df["High"] - df["Close"].shift())
        low_close = np.abs(df["Low"] - df["Close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        return round(atr.iloc[-1], 2)

    @staticmethod
    def compute_drawdown(df):
        roll_max = df["Close"].cummax()
        drawdown = df["Close"] / roll_max - 1
        return round(drawdown.min() * 100, 2)

    @staticmethod
    def regime(df):
        ma20 = df["Close"].rolling(20).mean()
        ma50 = df["Close"].rolling(50).mean()
        if ma20.iloc[-1] > ma50.iloc[-1]:
            return "Bull"
        return "Bear"

    @staticmethod
    def structure(df):
        if df["Close"].iloc[-1] > df["Close"].iloc[-5]:
            return "Strong"
        return "Weak"