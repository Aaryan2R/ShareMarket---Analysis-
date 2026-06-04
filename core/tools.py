"""Tool definitions and execution layer for the AI trading agent.

Each tool wraps existing orchestrator / database / RAG functionality so
the agent can call them via structured JSON.  No business logic is
reimplemented here — tools are thin wrappers.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from .company_match import find_all_mentioned, fuzzy_match_one
from .database import IntelligenceDB
from .market_data import read_price_frame, normalize_existing_price_csvs

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

@dataclass
class ToolParam:
    """Single parameter in a tool schema."""
    name: str
    type: str  # "string", "integer", "boolean"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class Tool:
    """A tool the agent can call."""
    name: str
    description: str
    params: list[ToolParam] = field(default_factory=list)
    handler: Callable[..., dict[str, Any]] | None = None

    def schema_text(self) -> str:
        """Human-readable schema for injection into the system prompt."""
        lines = [f"### {self.name}", f"{self.description}"]
        if self.params:
            lines.append("Parameters:")
            for p in self.params:
                req = "required" if p.required else f"optional, default={p.default}"
                lines.append(f"  - {p.name} ({p.type}, {req}): {p.description}")
        else:
            lines.append("Parameters: none")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Holds all tools and executes them by name."""

    def __init__(self, db: IntelligenceDB, orchestrator: Any, rag: Any,
                 chart_callback: Callable[[str], None] | None = None):
        self.db = db
        self.orchestrator = orchestrator
        self.rag = rag
        self._chart_callback = chart_callback
        self._tools: dict[str, Tool] = {}
        self._register_all()

    # ---- public API -------------------------------------------------------

    def descriptions_text(self) -> str:
        """Full tool descriptions block for the system prompt."""
        return "\n\n".join(t.schema_text() for t in self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Unknown tool '{name}'. Available: {', '.join(self.names())}"}
        if tool.handler is None:
            return {"error": f"Tool '{name}' has no handler."}
        try:
            # Validate & apply defaults
            clean_args = self._validate_args(tool, args)
            return tool.handler(**clean_args)
        except Exception as exc:
            LOGGER.exception("Tool %s failed", name)
            return {"error": f"Tool '{name}' failed: {exc}"}

    # ---- registration -----------------------------------------------------

    def _register_all(self) -> None:
        self._register(Tool(
            name="list_companies",
            description="List all companies currently tracked in the database.",
            handler=self._list_companies,
        ))
        self._register(Tool(
            name="add_company",
            description="Add a new company to the database. Optionally supply an NSE ticker symbol.",
            params=[
                ToolParam("name", "string", "Company name to add"),
                ToolParam("nse_symbol", "string", "NSE ticker symbol (e.g. TCS, INFY)", required=False),
            ],
            handler=self._add_company,
        ))
        self._register(Tool(
            name="remove_company",
            description="Remove a company from the database.",
            params=[ToolParam("name", "string", "Company name (or partial/alias) to remove")],
            handler=self._remove_company,
        ))
        self._register(Tool(
            name="set_nse_symbol",
            description="Set or update the NSE ticker symbol for an existing company.",
            params=[
                ToolParam("name", "string", "Company name (or partial/alias)"),
                ToolParam("symbol", "string", "NSE ticker symbol without .NS suffix"),
            ],
            handler=self._set_nse_symbol,
        ))
        self._register(Tool(
            name="get_company_status",
            description=(
                "Get detailed status for a single company: NSE symbol, CSV "
                "availability, row count, latest date, packet availability, "
                "and composite score."
            ),
            params=[ToolParam("name", "string", "Company name (or partial/alias)")],
            handler=self._get_company_status,
        ))
        self._register(Tool(
            name="get_company_analysis",
            description=(
                "Get full intelligence analysis for a company including "
                "latest close, technical/sentiment/risk/fundamental/strategy "
                "scores, volatility, moving averages, RSI, MACD, Bollinger "
                "Bands, support/resistance, trend, and the composite score. "
                "Use this when the user asks about a specific company's "
                "outlook, analysis, or detailed data."
            ),
            params=[ToolParam("name", "string", "Company name (or partial/alias)")],
            handler=self._get_company_analysis,
        ))
        self._register(Tool(
            name="rank_companies",
            description=(
                "Rank all companies by their composite intelligence score. "
                "Returns a sorted list. Use when the user asks which stock "
                "is best, or wants a ranking/leaderboard."
            ),
            handler=self._rank_companies,
        ))
        self._register(Tool(
            name="compare_companies",
            description=(
                "Side-by-side comparison of two or more companies on all "
                "metrics (technical, sentiment, risk, fundamental, strategy, "
                "composite score, latest close)."
            ),
            params=[
                ToolParam("names", "string",
                          "Comma-separated company names or aliases (e.g. 'TCS, Infosys')"),
            ],
            handler=self._compare_companies,
        ))
        self._register(Tool(
            name="compute_win_rate",
            description=(
                "Calculate the win rate (percentage of days where close > open) "
                "over the last N trading days for a company."
            ),
            params=[
                ToolParam("name", "string", "Company name (or partial/alias)"),
                ToolParam("days", "integer", "Number of recent trading days",
                          required=False, default=30),
            ],
            handler=self._compute_win_rate,
        ))
        self._register(Tool(
            name="show_chart",
            description=(
                "Open a price chart window for a company showing close, "
                "MA20, and MA50 lines."
            ),
            params=[ToolParam("name", "string", "Company name (or partial/alias)")],
            handler=self._show_chart,
        ))
        self._register(Tool(
            name="refresh_all",
            description=(
                "Rebuild intelligence packets for all companies. This "
                "fetches live sentiment, fundamentals, and regime data if "
                "enabled. Can take a few minutes."
            ),
            handler=self._refresh_all,
        ))
        self._register(Tool(
            name="normalize_csvs",
            description="Normalize all active daily CSV price files (clean up formatting).",
            handler=self._normalize_csvs,
        ))
        self._register(Tool(
            name="fetch_prices",
            description=(
                "Download the latest 5-year price history from Yahoo Finance "
                "for a company. Requires an NSE symbol to be set."
            ),
            params=[ToolParam("name", "string", "Company name (or partial/alias)")],
            handler=self._fetch_prices,
        ))
        self._register(Tool(
            name="search_knowledge",
            description=(
                "Search the knowledge base for information related to a "
                "question. Returns relevant context from company packets, "
                "price data, and the company universe. Use this for general "
                "market questions or when you need broader context."
            ),
            params=[ToolParam("query", "string", "The search query / question")],
            handler=self._search_knowledge,
        ))

    def _register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    # ---- arg validation ---------------------------------------------------

    def _validate_args(self, tool: Tool, args: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        for p in tool.params:
            value = args.get(p.name)
            if value is None and p.required:
                raise ValueError(f"Missing required parameter '{p.name}'")
            if value is None:
                value = p.default
            if value is not None and p.type == "integer":
                value = int(value)
            clean[p.name] = value
        return clean

    # ---- helpers ----------------------------------------------------------

    def _resolve_company(self, name: str) -> str | None:
        """Fuzzy-match a user-supplied name to a DB company."""
        companies = self.db.list_companies()
        return fuzzy_match_one(name, companies)

    # ---- tool handlers ----------------------------------------------------

    def _list_companies(self) -> dict[str, Any]:
        companies = self.db.list_companies()
        rows = self.db.list_company_rows()
        items = []
        for row in rows:
            items.append({
                "name": row["name"],
                "nse_symbol": row.get("nse_symbol") or "not set",
            })
        return {"companies": items, "count": len(items)}

    def _add_company(self, name: str, nse_symbol: str | None = None) -> dict[str, Any]:
        cid = self.db.add_company(name, nse_symbol)
        result: dict[str, Any] = {"added": name, "company_id": cid}
        if nse_symbol:
            result["nse_symbol"] = nse_symbol.upper().replace(".NS", "")
            result["note"] = "Use fetch_prices to download price data next."
        else:
            result["note"] = "Set an NSE symbol with set_nse_symbol, then use fetch_prices."
        return result

    def _remove_company(self, name: str) -> dict[str, Any]:
        company = self._resolve_company(name)
        if not company:
            return {"error": f"Company '{name}' not found in database."}
        self.db.remove_company(company)
        return {"removed": company}

    def _set_nse_symbol(self, name: str, symbol: str) -> dict[str, Any]:
        company = self._resolve_company(name)
        if not company:
            return {"error": f"Company '{name}' not found. Add it first."}
        clean = symbol.strip().upper().replace(".NS", "")
        self.db.set_nse_symbol(company, clean)
        return {"company": company, "nse_symbol": clean, "note": "Use fetch_prices to download data."}

    def _get_company_status(self, name: str) -> dict[str, Any]:
        company = self._resolve_company(name)
        if not company:
            return {"error": f"Company '{name}' not found."}
        return self.orchestrator.company_status(company)

    def _get_company_analysis(self, name: str) -> dict[str, Any]:
        company = self._resolve_company(name)
        if not company:
            return {"error": f"Company '{name}' not found."}

        status = self.orchestrator.company_status(company)
        company_id = self.db.get_company_id(company)
        packet = self.db.get_packet(company_id) if company_id else None

        analysis: dict[str, Any] = {"company": company, **status}

        if packet:
            analysis.update({
                "composite_score": packet.get("composite_score"),
                "latest_close": packet.get("latest_close"),
                "latest_date": packet.get("latest_date"),
                "volatility_pct": packet.get("volatility_pct"),
                "ma20": packet.get("ma20"),
                "ma50": packet.get("ma50"),
                "technical_score": packet.get("technical_score"),
                "sentiment_score": packet.get("sentiment_score"),
                "sentiment_bias": (packet.get("sentiment") or {}).get("sentiment_bias"),
                "risk_score": packet.get("risk_score"),
                "fundamental_score": packet.get("fundamental_score"),
                "strategy_score": packet.get("strategy_score"),
                "strategy_win_rate": (packet.get("strategy") or {}).get("win_rate_pct"),
                "strategy_trades": (packet.get("strategy") or {}).get("trade_count"),
                "max_drawdown_pct": (packet.get("strategy") or {}).get("max_drawdown_pct"),
                "institutional_holding_pct": packet.get("institutional_holding_pct"),
                "generated_at": packet.get("generated_at"),
            })

            # Add extended technicals if available
            for key in ("rsi_14", "macd_line", "macd_signal", "macd_histogram",
                        "bb_upper", "bb_lower", "bb_width_pct",
                        "support", "resistance", "trend"):
                if key in packet:
                    analysis[key] = packet[key]

            headlines = (packet.get("sentiment") or {}).get("headlines")
            if headlines:
                analysis["recent_headlines"] = headlines[:5]
        else:
            analysis["note"] = "No intelligence packet. Run refresh_all or fetch_prices first."

        return analysis

    def _rank_companies(self) -> dict[str, Any]:
        rankings = self.orchestrator.rank_all_companies()
        if not rankings:
            return {"error": "No packets available. Run refresh_all first."}
        return {"rankings": rankings, "count": len(rankings)}

    def _compare_companies(self, names: str) -> dict[str, Any]:
        raw_names = [n.strip() for n in names.split(",") if n.strip()]
        companies = self.db.list_companies()
        resolved = []
        for raw in raw_names:
            match = fuzzy_match_one(raw, companies)
            if match:
                resolved.append(match)
            else:
                # Also try find_all_mentioned for alias resolution
                mentioned = find_all_mentioned(raw, companies)
                resolved.extend(mentioned)

        resolved = list(dict.fromkeys(resolved))  # dedupe, preserve order
        if len(resolved) < 2:
            return {"error": f"Need at least 2 companies. Resolved: {resolved}. Available: {companies}"}

        comparison = []
        for company in resolved:
            company_id = self.db.get_company_id(company)
            packet = self.db.get_packet(company_id) if company_id else None
            entry: dict[str, Any] = {"company": company}
            if packet:
                entry.update({
                    "composite_score": packet.get("composite_score"),
                    "latest_close": packet.get("latest_close"),
                    "technical_score": packet.get("technical_score"),
                    "sentiment_score": packet.get("sentiment_score"),
                    "sentiment_bias": (packet.get("sentiment") or {}).get("sentiment_bias"),
                    "risk_score": packet.get("risk_score"),
                    "fundamental_score": packet.get("fundamental_score"),
                    "strategy_score": packet.get("strategy_score"),
                    "strategy_win_rate": (packet.get("strategy") or {}).get("win_rate_pct"),
                    "volatility_pct": packet.get("volatility_pct"),
                    "generated_at": packet.get("generated_at"),
                })
            else:
                entry["note"] = "No packet available."
            comparison.append(entry)

        return {"comparison": comparison}

    def _compute_win_rate(self, name: str, days: int = 30) -> dict[str, Any]:
        company = self._resolve_company(name)
        if not company:
            return {"error": f"Company '{name}' not found."}
        result = self.orchestrator.compute_win_rate(company, days)
        if not result:
            return {"error": f"No price data for {company}."}
        return result

    def _show_chart(self, name: str) -> dict[str, Any]:
        company = self._resolve_company(name)
        if not company:
            return {"error": f"Company '{name}' not found."}
        df = read_price_frame(company)
        if df is None or df.empty:
            return {"error": f"No CSV data for {company}."}
        if self._chart_callback:
            self._chart_callback(company)
        return {"chart_opened": company, "rows": len(df)}

    def _refresh_all(self) -> dict[str, Any]:
        packets = self.orchestrator.refresh_all()
        results = []
        for p in packets:
            results.append({
                "company": p["company"],
                "composite_score": p.get("composite_score"),
            })
        return {"refreshed": len(packets), "results": results}

    def _normalize_csvs(self) -> dict[str, Any]:
        changed = normalize_existing_price_csvs()
        return {"normalized": [{"company": name, "rows": rows} for name, rows in changed]}

    def _fetch_prices(self, name: str) -> dict[str, Any]:
        company = self._resolve_company(name)
        if not company:
            return {"error": f"Company '{name}' not found."}
        ok, message = self.orchestrator.fetch_and_store_prices(company)
        if not ok:
            return {"error": message}
        return {"success": True, "message": message, "company": company}

    def _search_knowledge(self, query: str) -> dict[str, Any]:
        context, packets = self.rag.context_for_question(query)
        summary: dict[str, Any] = {"context": context}
        if packets:
            summary["companies_with_packets"] = list(packets.keys())
            # Include key metrics for each matched company
            for name, packet in packets.items():
                summary[f"{name}_score"] = packet.get("composite_score")
                summary[f"{name}_close"] = packet.get("latest_close")
        return summary
