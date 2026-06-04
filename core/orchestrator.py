from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import yfinance as yf

from .config import (
    ENABLE_LIVE_FUNDAMENTALS,
    ENABLE_LIVE_REGIME,
    ENABLE_LIVE_SENTIMENT,
    FINBERT_MODEL,
    RAW_PATH,
    STRATEGY_CACHE_HOURS,
)
from .database import IntelligenceDB, utc_now
from .market_data import normalize_price_frame, read_price_frame, save_price_frame

LOGGER = logging.getLogger(__name__)

SL_MULT = 1.2
TP_MULT = 2.5
LOOKBACK = 20
MAX_HOLD = 10


class Orchestrator:
    """Builds and ranks market intelligence packets.

    Expensive work is lazy. Constructing this class should be fast enough for UI startup.
    FinBERT, Yahoo fundamentals, and market regime fetches happen only when a refresh/build
    actually needs them.
    """

    def __init__(self, db: IntelligenceDB | None = None):
        self.db = db or IntelligenceDB()
        self._tokenizer = None
        self._sent_model = None
        self._cached_regime: dict[pd.Timestamp, str] | None = None

    def fetch_and_store_prices(self, company: str) -> tuple[bool, str]:
        symbol = self.db.get_nse_symbol(company)
        if not symbol:
            return False, f"No NSE symbol found for {company}. Use: set nse symbol {company} <SYMBOL>"

        clean = symbol.upper().replace(".NS", "")
        try:
            ticker = yf.Ticker(clean + ".NS")
            df = ticker.history(period="5y", auto_adjust=True)
            if df.empty:
                return False, f"Yahoo Finance returned no rows for {clean}.NS."
            df = df.reset_index()
            path = save_price_frame(company, df)
            saved = read_price_frame(company)
            rows = len(saved) if saved is not None else 0
            return True, f"Downloaded {rows} daily rows for {company} into {path}"
        except Exception as exc:
            LOGGER.exception("Price fetch failed for %s", company)
            return False, str(exc)

    def build_packet(self, company: str, force_strategy: bool = False) -> dict[str, Any] | None:
        df = read_price_frame(company)
        if df is None or len(df) < 60:
            LOGGER.warning("Not enough price data for %s", company)
            return None

        df = df.set_index("Date").sort_index()
        latest = df.iloc[-1]
        close = df["Close"]
        volatility = float(close.pct_change().dropna().std() * 100 or 0)
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]

        # Extended technicals
        rsi = self._rsi(close, 14)
        macd_line, macd_signal, macd_hist = self._macd(close)
        bb_upper, bb_lower, bb_width = self._bollinger(close)
        support, resistance = self._support_resistance(df)
        trend = self._classify_trend(latest["Close"], ma20, ma50, rsi, macd_hist)

        technical_score = self._technical_score(
            latest["Close"], ma20, ma50, close, rsi, macd_hist
        )
        sentiment_data = self._sentiment(company) if ENABLE_LIVE_SENTIMENT else self._cached_sentiment(company)
        sentiment_score = sentiment_data["score"]
        risk_score = max(0.0, 100.0 - min(volatility * 10, 60.0))
        fundamental = self._fundamentals(company) if ENABLE_LIVE_FUNDAMENTALS else {}
        fundamental_score = self._fundamental_score(fundamental)
        strategy_metrics = self._strategy_metrics(company, df, force_strategy)
        strategy_score = (strategy_metrics or {}).get("strategy_score", 50)

        composite = round(
            technical_score * 0.25
            + sentiment_score * 0.10
            + risk_score * 0.15
            + fundamental_score * 0.20
            + strategy_score * 0.30,
            2,
        )

        packet = {
            "company": company,
            "latest_close": round(float(latest["Close"]), 2),
            "latest_date": latest.name.date().isoformat(),
            "rows": int(len(df)),
            "volatility_pct": round(volatility, 2),
            "ma20": round(float(ma20), 2) if pd.notna(ma20) else None,
            "ma50": round(float(ma50), 2) if pd.notna(ma50) else None,
            "rsi_14": round(rsi, 2) if pd.notna(rsi) else None,
            "macd_line": round(macd_line, 4) if pd.notna(macd_line) else None,
            "macd_signal": round(macd_signal, 4) if pd.notna(macd_signal) else None,
            "macd_histogram": round(macd_hist, 4) if pd.notna(macd_hist) else None,
            "bb_upper": round(bb_upper, 2) if pd.notna(bb_upper) else None,
            "bb_lower": round(bb_lower, 2) if pd.notna(bb_lower) else None,
            "bb_width_pct": round(bb_width, 2) if pd.notna(bb_width) else None,
            "support": round(support, 2) if support else None,
            "resistance": round(resistance, 2) if resistance else None,
            "trend": trend,
            "technical_score": technical_score,
            "sentiment_score": sentiment_score,
            "risk_score": round(risk_score, 2),
            "fundamental_score": fundamental_score,
            "institutional_holding_pct": fundamental.get("heldPercentInstitutions", 0),
            "strategy": strategy_metrics,
            "strategy_score": strategy_score,
            "composite_score": composite,
            "sentiment": sentiment_data,
            "generated_at": utc_now(),
        }
        return packet

    def refresh_all(self, force_strategy: bool = False) -> list[dict[str, Any]]:
        packets = []
        for company in self.db.list_companies():
            packet = self.build_packet(company, force_strategy=force_strategy)
            if packet:
                company_id = self.db.get_company_id(company)
                if company_id:
                    self.db.save_packet(company_id, packet)
                packets.append(packet)
        return packets

    def rank_all_companies(self) -> list[dict[str, Any]]:
        rankings = []
        for company, packet in self.db.get_all_packets().items():
            rankings.append(
                {
                    "company": company,
                    "composite_score": packet.get("composite_score", 0),
                    "latest_close": packet.get("latest_close"),
                    "generated_at": packet.get("generated_at"),
                }
            )
        rankings.sort(key=lambda item: item["composite_score"], reverse=True)
        return rankings

    def company_status(self, company: str) -> dict[str, Any]:
        df = read_price_frame(company)
        company_id = self.db.get_company_id(company)
        packet = self.db.get_packet(company_id) if company_id else None
        return {
            "company": company,
            "nse_symbol": self.db.get_nse_symbol(company),
            "has_csv": df is not None and not df.empty,
            "rows": len(df) if df is not None else 0,
            "latest_date": df["Date"].iloc[-1].date().isoformat() if df is not None and not df.empty else None,
            "has_packet": packet is not None,
            "packet_generated_at": packet.get("generated_at") if packet else None,
        }

    def compute_win_rate(self, company: str, days: int = 30) -> dict[str, Any] | None:
        df = read_price_frame(company)
        if df is None or df.empty:
            return None
        sample = df.tail(days)
        wins = int((sample["Close"] > sample["Open"]).sum())
        total = int(len(sample))
        return {
            "company": company,
            "days": total,
            "wins": wins,
            "win_rate_pct": round((wins / total) * 100, 2) if total else 0,
            "start_date": sample["Date"].iloc[0].date().isoformat() if total else None,
            "end_date": sample["Date"].iloc[-1].date().isoformat() if total else None,
        }

    def _technical_score(
        self, latest_close: float, ma20: float, ma50: float,
        close: pd.Series,
        rsi: float | None = None,
        macd_hist: float | None = None,
    ) -> int:
        score = 20  # base
        # MA signals (up to +30)
        if pd.notna(ma20) and latest_close > ma20:
            score += 15
        if pd.notna(ma50) and latest_close > ma50:
            score += 15
        # 20-day momentum (+10)
        if len(close) >= 20 and latest_close > close.iloc[-20]:
            score += 10
        # RSI signal (+20)
        if rsi is not None and pd.notna(rsi):
            if 40 <= rsi <= 70:  # healthy range
                score += 20
            elif 30 <= rsi < 40 or 70 < rsi <= 80:
                score += 10
            # Oversold/overbought extremes get no bonus
        # MACD signal (+20)
        if macd_hist is not None and pd.notna(macd_hist):
            if macd_hist > 0:  # bullish
                score += 20
            elif macd_hist > -0.5:  # mildly bearish
                score += 5
        return min(score, 100)

    # ------------------------------------------------------------------ #
    # Extended technical indicators
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rsi(close: pd.Series, period: int = 14) -> float:
        """Relative Strength Index."""
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 100
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _macd(
        close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[float, float, float]:
        """MACD line, signal line, histogram."""
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])

    @staticmethod
    def _bollinger(
        close: pd.Series, period: int = 20, std_dev: float = 2.0
    ) -> tuple[float, float, float]:
        """Bollinger Bands upper, lower, and width %."""
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        width_pct = ((upper.iloc[-1] - lower.iloc[-1]) / sma.iloc[-1]) * 100 if pd.notna(sma.iloc[-1]) and sma.iloc[-1] != 0 else 0
        return float(upper.iloc[-1]), float(lower.iloc[-1]), float(width_pct)

    @staticmethod
    def _support_resistance(
        df: pd.DataFrame, lookback: int = 20
    ) -> tuple[float | None, float | None]:
        """Simple support/resistance from recent highs and lows."""
        if len(df) < lookback:
            return None, None
        recent = df.iloc[-lookback:]
        support = float(recent["Low"].min())
        resistance = float(recent["High"].max())
        return support, resistance

    @staticmethod
    def _classify_trend(
        close: float, ma20: float, ma50: float,
        rsi: float | None, macd_hist: float | None,
    ) -> str:
        """Classify the current trend based on multiple signals."""
        bullish_signals = 0
        bearish_signals = 0

        if pd.notna(ma20) and close > ma20:
            bullish_signals += 1
        elif pd.notna(ma20):
            bearish_signals += 1

        if pd.notna(ma50) and close > ma50:
            bullish_signals += 1
        elif pd.notna(ma50):
            bearish_signals += 1

        if pd.notna(ma20) and pd.notna(ma50) and ma20 > ma50:
            bullish_signals += 1
        elif pd.notna(ma20) and pd.notna(ma50):
            bearish_signals += 1

        if rsi is not None and pd.notna(rsi):
            if rsi > 60:
                bullish_signals += 1
            elif rsi < 40:
                bearish_signals += 1

        if macd_hist is not None and pd.notna(macd_hist):
            if macd_hist > 0:
                bullish_signals += 1
            else:
                bearish_signals += 1

        total = bullish_signals + bearish_signals
        if total == 0:
            return "unknown"
        ratio = bullish_signals / total
        if ratio >= 0.8:
            return "strong uptrend"
        elif ratio >= 0.6:
            return "moderate uptrend"
        elif ratio >= 0.4:
            return "consolidating"
        elif ratio >= 0.2:
            return "moderate downtrend"
        else:
            return "strong downtrend"

    def _fundamentals(self, company: str) -> dict[str, Any]:
        symbol = self.db.get_nse_symbol(company)
        if not symbol:
            return {}
        try:
            return yf.Ticker(symbol.replace(".NS", "") + ".NS").info or {}
        except Exception as exc:
            LOGGER.warning("Fundamentals failed for %s: %s", company, exc)
            return {}

    def _fundamental_score(self, info: dict[str, Any]) -> int:
        roe = info.get("returnOnEquity") or 0
        profit_margin = info.get("profitMargins") or 0
        debt_equity = info.get("debtToEquity") or 0
        institutional_pct = info.get("heldPercentInstitutions") or 0
        return sum(
            [
                25 if roe > 0.15 else 0,
                25 if profit_margin > 0.10 else 0,
                25 if debt_equity < 100 else 0,
                25 if institutional_pct > 0.5 else 0,
            ]
        )

    def _cached_sentiment(self, company: str) -> dict[str, Any]:
        company_id = self.db.get_company_id(company)
        old = self.db.get_packet(company_id) if company_id else None
        if old and old.get("sentiment"):
            return old["sentiment"]
        return {"score": 50, "average_sentiment_score": 0, "sentiment_bias": "neutral", "headlines": []}

    def _sentiment(self, company: str) -> dict[str, Any]:
        try:
            url = f"https://news.google.com/rss/search?q={company}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            headlines = [
                item.find("title").text
                for item in root.findall(".//item")[:20]
                if item.find("title") is not None and item.find("title").text
            ]
            if not headlines:
                return {"score": 50, "average_sentiment_score": 0, "sentiment_bias": "neutral", "headlines": []}

            tokenizer, model = self._finbert()
            import torch
            import torch.nn.functional as F

            inputs = tokenizer(headlines, return_tensors="pt", truncation=True, padding=True)
            with torch.no_grad():
                probs = F.softmax(model(**inputs).logits, dim=1)
            scores = [float(p[2].item() - p[0].item()) for p in probs]
            avg = sum(scores) / len(scores)
            return {
                "score": int(max(0, min(100, (avg + 1) * 50))),
                "average_sentiment_score": round(avg, 3),
                "sentiment_bias": "bullish" if avg > 0.15 else "bearish" if avg < -0.15 else "neutral",
                "headlines": headlines[:5],
            }
        except Exception as exc:
            LOGGER.warning("Sentiment failed for %s: %s", company, exc)
            return self._cached_sentiment(company)

    def _finbert(self):
        if self._tokenizer is None or self._sent_model is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            LOGGER.info("Loading FinBERT model %s", FINBERT_MODEL)
            self._tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
            self._sent_model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL)
            self._sent_model.eval()
        return self._tokenizer, self._sent_model

    def _strategy_metrics(self, company: str, df: pd.DataFrame, force_strategy: bool) -> dict[str, Any] | None:
        old = None
        company_id = self.db.get_company_id(company)
        if company_id:
            old = self.db.get_packet(company_id)
        if old and old.get("strategy") and not force_strategy:
            ts = old["strategy"].get("strategy_last_updated")
            if ts:
                try:
                    age = datetime.now(timezone.utc) - datetime.fromisoformat(ts)
                    if age < timedelta(hours=STRATEGY_CACHE_HOURS):
                        return old["strategy"]
                except Exception:
                    pass
        return self._backtest(df)

    def _regime_series(self) -> dict[pd.Timestamp, str]:
        if self._cached_regime is not None:
            return self._cached_regime
        if not ENABLE_LIVE_REGIME:
            self._cached_regime = {}
            return self._cached_regime
        try:
            idx = yf.download("^NSEI", period="5y", auto_adjust=True, progress=False)
            idx = normalize_price_frame(idx.reset_index())
            if idx.empty:
                self._cached_regime = {}
                return self._cached_regime
            idx = idx.set_index("Date").sort_index()
            idx["EMA50"] = idx["Close"].ewm(span=50).mean()
            idx["EMA200"] = idx["Close"].ewm(span=200).mean()
            self._cached_regime = {
                pd.Timestamp(date).normalize(): "BULL" if row["EMA50"] > row["EMA200"] else "BEAR"
                for date, row in idx.iterrows()
            }
        except Exception as exc:
            LOGGER.warning("Regime fetch failed: %s", exc)
            self._cached_regime = {}
        return self._cached_regime

    def _atr(self, df: pd.DataFrame) -> pd.Series:
        tr = pd.concat(
            [
                df["High"] - df["Low"],
                (df["High"] - df["Close"].shift(1)).abs(),
                (df["Low"] - df["Close"].shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(14).mean()

    def _backtest(self, df: pd.DataFrame) -> dict[str, Any] | None:
        if len(df) < 250:
            return None
        frame = df.copy()
        frame["ATR"] = self._atr(frame)
        frame.index = pd.to_datetime(frame.index).normalize()
        regime_series = self._regime_series()

        trades = wins = losses = 0
        equity = 100_000.0
        peak = equity
        max_dd = 0.0

        for i in range(LOOKBACK, len(frame) - MAX_HOLD):
            date = frame.index[i]
            regime = regime_series.get(date)
            if regime not in {"BULL", "BEAR"}:
                continue
            row = frame.iloc[i]
            if pd.isna(row["ATR"]):
                continue

            highest = frame["High"].iloc[i - LOOKBACK : i].max()
            lowest = frame["Low"].iloc[i - LOOKBACK : i].min()
            direction = None
            if regime == "BULL" and row["Close"] > highest:
                direction = "LONG"
            elif regime == "BEAR" and row["Close"] < lowest:
                direction = "SHORT"
            if not direction:
                continue

            entry = row["Close"]
            atr = row["ATR"]
            sl = entry - atr * SL_MULT if direction == "LONG" else entry + atr * SL_MULT
            tp = entry + atr * TP_MULT if direction == "LONG" else entry - atr * TP_MULT
            trades += 1

            closed = False
            for _, future in frame.iloc[i + 1 : i + MAX_HOLD + 1].iterrows():
                if direction == "LONG":
                    if future["Low"] <= sl:
                        losses += 1
                        equity *= 0.99
                        closed = True
                        break
                    if future["High"] >= tp:
                        wins += 1
                        equity *= 1.02
                        closed = True
                        break
                else:
                    if future["High"] >= sl:
                        losses += 1
                        equity *= 0.99
                        closed = True
                        break
                    if future["Low"] <= tp:
                        wins += 1
                        equity *= 1.02
                        closed = True
                        break
            if not closed:
                equity *= 1.0
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak)

        if trades == 0:
            return None

        win_rate = wins / trades
        expectancy = (win_rate * TP_MULT) - ((1 - win_rate) * SL_MULT)
        return {
            "win_rate_pct": round(win_rate * 100, 2),
            "expectancy_score": round(expectancy, 2),
            "trade_count": trades,
            "wins": wins,
            "losses": losses,
            "max_drawdown_pct": round(max_dd * 100, 2),
            "strategy_score": round(win_rate * 40 + max(0, expectancy) * 30 + (1 - max_dd) * 30, 2),
            "strategy_last_updated": utc_now(),
        }


# Backward-compatible import path for main.py and older snippets.
__all__ = ["Orchestrator", "IntelligenceDB"]
