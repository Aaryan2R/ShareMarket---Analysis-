"""Enhanced RAG engine with TF-IDF scoring, recency weighting, and better context.

The deterministic_answer method is removed — all answers now flow through
the agent router and LLM.  This module focuses purely on retrieval.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .company_match import find_all_mentioned
from .database import IntelligenceDB
from .market_data import read_price_frame

TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")

# Common stop-words to down-weight in scoring
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "about",
    "and", "or", "but", "not", "no", "if", "then", "else", "when",
    "up", "out", "it", "its", "this", "that", "what", "which", "who",
    "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "than", "too", "very", "just", "also",
    "me", "my", "i", "you", "your", "we", "our", "they", "their",
})


@dataclass
class RagDocument:
    title: str
    company: str | None
    text: str
    payload: dict[str, Any]
    freshness_hours: float = 0.0  # hours since generation


class RagEngine:
    def __init__(self, db: IntelligenceDB | None = None):
        self.db = db or IntelligenceDB()

    def build_documents(self) -> list[RagDocument]:
        """Build retrieval documents from DB state."""
        documents: list[RagDocument] = []
        packets = self.db.get_all_packets()
        rows = self.db.list_company_rows()
        companies = [row["name"] for row in rows]

        now = datetime.now(timezone.utc)

        for row in rows:
            name = row["name"]
            status_bits = [
                f"Company: {name}",
                f"NSE symbol: {row.get('nse_symbol') or 'not set'}",
            ]
            packet = packets.get(name)
            freshness = 0.0

            if packet:
                status_bits.extend(self._packet_lines(packet))
                gen_at = packet.get("generated_at")
                if gen_at:
                    try:
                        gen_dt = datetime.fromisoformat(gen_at)
                        freshness = (now - gen_dt).total_seconds() / 3600
                    except Exception:
                        pass

            df = read_price_frame(name)
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                status_bits.extend([
                    f"Price rows: {len(df)}",
                    f"Latest date: {latest['Date'].date()}",
                    f"Latest close: {round(float(latest['Close']), 2)}",
                ])

            documents.append(RagDocument(
                title=f"{name} company intelligence",
                company=name,
                text="\n".join(status_bits),
                payload={"packet": packet},
                freshness_hours=freshness,
            ))

        if companies:
            documents.append(RagDocument(
                title="Company universe",
                company=None,
                text="Companies in database: " + ", ".join(companies),
                payload={"companies": companies},
            ))
        return documents

    def retrieve(self, question: str, limit: int = 5) -> list[RagDocument]:
        """Retrieve the most relevant documents for a question.

        Uses TF-IDF-style scoring with company mention boosting and
        recency weighting.
        """
        documents = self.build_documents()
        mentioned = set(find_all_mentioned(question, self.db.list_companies()))
        q_tokens = self._tokens(question)

        if not q_tokens:
            return documents[:limit]

        # Build document-frequency counts for IDF
        doc_count = len(documents) or 1
        df_counter: Counter[str] = Counter()
        doc_token_sets: list[set[str]] = []
        for doc in documents:
            tokens = self._tokens(doc.title + " " + doc.text)
            doc_token_sets.append(tokens)
            for token in tokens:
                df_counter[token] += 1

        # Detect broad queries that implicitly need all company data
        _BROAD_TERMS = {"rank", "ranking", "compare", "comparison", "best",
                        "worst", "top", "bottom", "all", "stocks", "companies",
                        "overview", "summary", "portfolio"}
        is_broad = bool(q_tokens & _BROAD_TERMS)

        scored: list[tuple[float, RagDocument]] = []
        for idx, doc in enumerate(documents):
            doc_tokens = doc_token_sets[idx]
            # TF-IDF score: sum of IDF for matching non-stop tokens
            score = 0.0
            for token in q_tokens:
                if token in doc_tokens and token not in _STOP_WORDS:
                    idf = math.log(doc_count / (1 + df_counter.get(token, 0)))
                    score += max(idf, 0.1)

            # Company mention boost (+5)
            if doc.company in mentioned:
                score += 5.0

            # Broad query boost: include all company docs for ranking/comparison
            if is_broad and doc.company is not None:
                score += 2.0

            # Recency boost: fresh docs score higher (up to +1.0 for <1h old)
            if doc.freshness_hours > 0:
                recency = max(0.0, 1.0 - doc.freshness_hours / 168)  # decay over 1 week
                score += recency

            if score > 0:
                scored.append((score, doc))

        # If no matches at all, return top docs by default
        if not scored and documents:
            scored = [(0.1, doc) for doc in documents[:limit]]

        return [doc for _, doc in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]

    def context_for_question(self, question: str, limit: int = 5) -> tuple[str, dict[str, dict[str, Any]]]:
        """Build formatted context + packets for a question.

        Returns (context_markdown, {company_name: packet}).
        """
        docs = self.retrieve(question, limit=limit)
        packets: dict[str, dict[str, Any]] = {}
        sections: list[str] = []

        for doc in docs:
            sections.append(f"### {doc.title}\n{doc.text}")
            packet = doc.payload.get("packet")
            if doc.company and packet:
                packets[doc.company] = packet

        return "\n\n".join(sections), packets

    def _packet_lines(self, packet: dict[str, Any]) -> list[str]:
        """Format packet data as readable lines."""
        strategy = packet.get("strategy") or {}
        sentiment = packet.get("sentiment") or {}
        lines = [
            f"Composite score: {packet.get('composite_score')}",
            f"Latest close: {packet.get('latest_close')}",
            f"Technical score: {packet.get('technical_score')}",
            f"Sentiment score: {packet.get('sentiment_score')} ({sentiment.get('sentiment_bias', 'unknown')})",
            f"Risk score: {packet.get('risk_score')}",
            f"Fundamental score: {packet.get('fundamental_score')}",
            f"Strategy score: {packet.get('strategy_score')}",
            f"Strategy win rate: {strategy.get('win_rate_pct')}",
            f"Trade count: {strategy.get('trade_count')}",
            f"Volatility: {packet.get('volatility_pct')}%",
            f"MA20: {packet.get('ma20')}",
            f"MA50: {packet.get('ma50')}",
            f"Generated at: {packet.get('generated_at')}",
        ]

        # Add extended technicals if present
        for key, label in [
            ("rsi_14", "RSI(14)"),
            ("macd_line", "MACD line"),
            ("macd_signal", "MACD signal"),
            ("bb_upper", "Bollinger upper"),
            ("bb_lower", "Bollinger lower"),
            ("bb_width_pct", "Bollinger width %"),
            ("support", "Support"),
            ("resistance", "Resistance"),
            ("trend", "Trend"),
        ]:
            val = packet.get(key)
            if val is not None:
                lines.append(f"{label}: {val}")

        headlines = sentiment.get("headlines")
        if headlines:
            lines.append("Recent headlines: " + " | ".join(headlines[:3]))

        return lines

    def _tokens(self, text: str) -> set[str]:
        return {match.group(0).lower() for match in TOKEN_RE.finditer(text)}
