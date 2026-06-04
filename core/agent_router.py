"""Agent router — the core agentic loop.

Replaces the old regex-based _route() dispatcher.  The LLM decides
which tools to call, we execute them, feed results back, and loop
until the LLM produces a final answer (or we hit the iteration cap).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from .database import IntelligenceDB
from .llm_client import LLMClient
from .prompts import AGENT_SYSTEM_PROMPT, FALLBACK_SYSTEM_PROMPT
from .rag_engine import RagEngine
from .tools import ToolRegistry

LOGGER = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5

# Simple commands that bypass the LLM for instant response
_INSTANT_COMMANDS = {"help", "commands", "?"}


@dataclass
class AgentStep:
    """One step in the agent loop (for UI transparency)."""
    kind: str  # "thinking", "tool_call", "tool_result", "answer", "error"
    content: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None


@dataclass
class AgentResult:
    """Complete result of an agent run."""
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    used_tools: list[str] = field(default_factory=list)


HELP_TEXT = """I'm your AI trading intelligence assistant. I can help you with:

• **Analyse a company** — "Tell me about TCS" or "How is Reliance doing?"
• **Compare companies** — "Compare TCS and Infosys"
• **Rank stocks** — "Which stock is best?" or "Rank all companies"
• **Win rates** — "What's the 30-day win rate for Infosys?"
• **Price charts** — "Show me a chart for Asian Paints"
• **Manage database** — "Add company HDFC Bank HDFCBANK" or "Remove TCS"
• **Set tickers** — "Set NSE symbol for HDFC Bank to HDFCBANK"
• **Refresh data** — "Refresh all packets" or "Download prices for TCS"
• **Normalize CSVs** — "Normalize the CSV data"

You can ask anything in natural language — I'll figure out what data to \
fetch and which tools to use. Follow-up questions work too!\
"""


class AgentRouter:
    """Routes user messages through an LLM-driven tool-calling loop."""

    def __init__(
        self,
        db: IntelligenceDB,
        orchestrator: Any,
        rag: RagEngine,
        llm: LLMClient,
        *,
        chart_callback: Callable[[str], None] | None = None,
        on_step: Callable[[AgentStep], None] | None = None,
    ):
        self.db = db
        self.orchestrator = orchestrator
        self.rag = rag
        self.llm = llm
        self.on_step = on_step

        self.tools = ToolRegistry(
            db=db,
            orchestrator=orchestrator,
            rag=rag,
            chart_callback=chart_callback,
        )

    def run(self, question: str) -> AgentResult:
        """Process a user question through the agent loop.

        Returns an AgentResult with the final answer and all intermediate steps.
        """
        lower = question.lower().strip()

        # Fast-path: help
        if lower in _INSTANT_COMMANDS:
            return AgentResult(answer=HELP_TEXT)

        # Fast-path: trivial greetings
        if lower.rstrip("!?. ") in {"hi", "hello", "hey", "howdy"}:
            companies = self.db.list_companies()
            greeting = "Hello! I'm your AI trading assistant. "
            if companies:
                greeting += f"I have data on {len(companies)} companies: {', '.join(companies)}. "
            greeting += "What would you like to know?"
            return AgentResult(answer=greeting)

        # Check if LLM is reachable — if not, fall back to data-only mode
        if not self.llm.is_reachable():
            return self._fallback_data_only(question)

        # Main agent loop
        return self._agent_loop(question)

    def _agent_loop(self, question: str) -> AgentResult:
        """The core agentic loop: LLM → tool call → result → LLM → ... → answer."""
        result = AgentResult(answer="")
        history = self.db.recent_messages(10)

        # Build system prompt with tool descriptions
        system = AGENT_SYSTEM_PROMPT.format(
            tool_descriptions=self.tools.descriptions_text()
        )

        # Build the initial user message
        user_msg = question

        # Accumulate tool call/result pairs for multi-turn context
        tool_context_parts: list[str] = []

        for iteration in range(MAX_TOOL_ITERATIONS):
            self._emit_step(result, AgentStep(kind="thinking", content="Analysing your question..."))

            # Build the full user message with any accumulated tool results
            if tool_context_parts:
                full_user = (
                    f"Original question: {question}\n\n"
                    + "\n\n".join(tool_context_parts)
                    + "\n\nNow answer the original question using the tool results above, "
                    "or call another tool if you need more data."
                )
            else:
                full_user = question

            # Call LLM
            tool_name, tool_args, raw_text = self.llm.chat_for_tool_call(
                system, full_user, history=history
            )

            # If no tool call detected → this is the final answer
            if tool_name is None:
                result.answer = raw_text
                self._emit_step(result, AgentStep(kind="answer", content=raw_text))
                return result

            # Tool call detected
            LOGGER.info("Agent tool call [%d]: %s(%s)", iteration, tool_name, tool_args)
            self._emit_step(result, AgentStep(
                kind="tool_call",
                content=f"Calling {tool_name}...",
                tool_name=tool_name,
                tool_args=tool_args,
            ))

            # Execute the tool
            tool_result = self.tools.execute(tool_name, tool_args or {})
            result.used_tools.append(tool_name)

            self._emit_step(result, AgentStep(
                kind="tool_result",
                content=f"{tool_name} returned data",
                tool_name=tool_name,
                tool_result=tool_result,
            ))

            # Format result as a string for the next LLM call
            result_text = json.dumps(tool_result, indent=2, default=str)
            # Truncate very long results to stay within context window
            if len(result_text) > 4000:
                result_text = result_text[:4000] + "\n... (truncated)"

            tool_context_parts.append(
                f"Tool call: {tool_name}({json.dumps(tool_args, default=str)})\n"
                f"Result:\n{result_text}"
            )

        # Exhausted iterations — ask LLM for best-effort answer from what we have
        final_user = (
            f"Original question: {question}\n\n"
            + "\n\n".join(tool_context_parts)
            + "\n\nPlease give your best answer now using the data above."
        )
        answer = self.llm.chat(system, final_user, history=history)
        result.answer = answer
        self._emit_step(result, AgentStep(kind="answer", content=answer))
        return result

    def _fallback_data_only(self, question: str) -> AgentResult:
        """When LLM is unreachable, provide data-only responses."""
        result = AgentResult(answer="")
        self._emit_step(result, AgentStep(
            kind="error",
            content="AI model not reachable. Showing available data instead."
        ))

        # Try to provide useful data without the LLM
        from .company_match import find_all_mentioned
        companies = self.db.list_companies()
        mentioned = find_all_mentioned(question, companies)
        lower = question.lower()

        parts: list[str] = [
            "⚠️ **AI model not reachable** — showing raw data:\n"
        ]

        # If ranking-related
        if "rank" in lower or "best" in lower or "top" in lower:
            rankings = self.orchestrator.rank_all_companies()
            if rankings:
                parts.append("**Rankings:**")
                for i, r in enumerate(rankings, 1):
                    parts.append(
                        f"{i}. {r['company']} — score {r['composite_score']}, "
                        f"close {r.get('latest_close', 'n/a')}"
                    )

        # If specific companies mentioned
        elif mentioned:
            for company in mentioned:
                cid = self.db.get_company_id(company)
                packet = self.db.get_packet(cid) if cid else None
                if packet:
                    parts.append(f"**{company}:**")
                    parts.append(f"- Composite: {packet.get('composite_score')}")
                    parts.append(f"- Close: {packet.get('latest_close')}")
                    parts.append(f"- Technical: {packet.get('technical_score')}")
                    parts.append(f"- Risk: {packet.get('risk_score')}")
                    parts.append(f"- Generated: {packet.get('generated_at')}")
                else:
                    parts.append(f"**{company}:** No packet data available.")

        # Fallback: show all companies
        else:
            if companies:
                parts.append("**Tracked companies:** " + ", ".join(companies))
            else:
                parts.append("No companies in database.")

        parts.append(f"\n_LLM endpoint: {self.llm.api_url}_")

        result.answer = "\n".join(parts)
        return result

    def _emit_step(self, result: AgentResult, step: AgentStep) -> None:
        """Record a step and notify the UI callback."""
        result.steps.append(step)
        if self.on_step:
            try:
                self.on_step(step)
            except Exception:
                LOGGER.exception("on_step callback failed")
