"""AI Trading Intelligence Terminal — Tkinter desktop assistant.

Uses the AgentRouter for LLM-driven tool calling instead of hardcoded
regex command dispatch.  Background work is routed through a main-thread
queue for Tkinter thread safety.
"""
from __future__ import annotations

import queue
import re
import threading
import tkinter as tk
from tkinter import messagebox

import pandas as pd

from core.company_match import find_all_mentioned, fuzzy_match_one
from core.config import DIAG_DIR
from core.database import IntelligenceDB
from core.llm_client import LLMClient
from core.market_data import read_price_frame
from core.orchestrator import Orchestrator
from core.rag_engine import RagEngine
from core.agent_router import AgentRouter, AgentStep

try:
    import plotly.graph_objects as go
    from plotly.offline import plot as plotly_plot

    PLOTLY_AVAILABLE = True
except Exception:
    PLOTLY_AVAILABLE = False

try:
    import matplotlib

    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False


BG = "#0f1115"
CARD = "#1a1d23"
TEXT = "#e5e7eb"
MUTED = "#9ca3af"
ACCENT = "#3b82f6"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
TOOL_COLOR = "#a78bfa"  # purple for tool-call visibility
FONT = ("Segoe UI", 12)


class TradingUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.queue: queue.Queue[tuple[str, tuple]] = queue.Queue()
        self.db = IntelligenceDB()
        self.orchestrator = Orchestrator(self.db)
        self.rag = RagEngine(self.db)
        self.llm = LLMClient()

        # Agent router replaces the old regex _route method
        self.agent = AgentRouter(
            db=self.db,
            orchestrator=self.orchestrator,
            rag=self.rag,
            llm=self.llm,
            chart_callback=self._enqueue_chart,
            on_step=self._on_agent_step,
        )

        root.title("AI Trading Intelligence Terminal")
        root.geometry("1180x760")
        root.configure(bg=BG)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        header = tk.Frame(root, bg=CARD)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 0))
        tk.Label(
            header,
            text="AI Trading Intelligence Terminal",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left", padx=10)

        # Connection indicator
        self.conn_label = tk.Label(
            header, text="", bg=CARD, fg=SUCCESS, font=("Segoe UI", 10)
        )
        self.conn_label.pack(side="right", padx=(0, 10))

        self.meta_label = tk.Label(header, text=self._meta_text(), bg=CARD, fg=MUTED, font=("Segoe UI", 10))
        self.meta_label.pack(side="right", padx=10)

        self.output = tk.Text(root, bg=BG, fg=TEXT, font=FONT, wrap="word", relief="flat")
        self.output.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)
        self.output.tag_config("user", foreground=ACCENT, font=("Segoe UI", 11, "bold"))
        self.output.tag_config("ai", foreground=TEXT, font=FONT)
        self.output.tag_config("success", foreground=SUCCESS, font=FONT)
        self.output.tag_config("warning", foreground=WARNING, font=FONT)
        self.output.tag_config("muted", foreground=MUTED, font=("Segoe UI", 10))
        self.output.tag_config("tool", foreground=TOOL_COLOR, font=("Segoe UI", 10, "italic"))

        bottom = tk.Frame(root, bg=CARD)
        bottom.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 6))
        bottom.grid_columnconfigure(0, weight=1)
        self.entry = tk.Entry(bottom, font=FONT, bg="#111318", fg=TEXT, insertbackground=TEXT, relief="flat")
        self.entry.grid(row=0, column=0, sticky="ew", padx=(6, 6), pady=10)
        self.entry.bind("<Return>", self.ask)
        tk.Button(bottom, text="Ask", bg=ACCENT, fg="white", command=self.ask, width=10).grid(row=0, column=1, padx=(0, 6))

        self.status = tk.Label(root, text="Ready", bg=CARD, fg=MUTED, font=("Segoe UI", 10))
        self.status.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 6))

        self.entry.focus_set()
        self._write("AI", "Ready. Ask me anything about your stocks, or type help.")
        self._check_llm_connection()
        self.root.after(80, self._drain_queue)

    def _meta_text(self) -> str:
        companies = self.db.list_companies()
        if not companies:
            return "DB: empty"
        preview = ", ".join(companies[:3])
        if len(companies) > 3:
            preview += "..."
        return f"DB: {len(companies)} | {preview}"

    def _check_llm_connection(self) -> None:
        """Check LLM connectivity and update the indicator."""
        def _check():
            reachable = self.llm.is_reachable()
            self.queue.put(("conn_status", (reachable,)))
        threading.Thread(target=_check, daemon=True).start()

    def _write(self, role: str, text: str, tag: str | None = None) -> None:
        chosen = "user" if role == "You" else (tag or "ai")
        self.output.insert("end", f"\n{role}:\n", chosen)
        self.output.insert("end", f"{text}\n", chosen)
        self.output.see("end")

    def _reply(self, text: str, tag: str | None = None) -> None:
        self._write("AI", text, tag)
        self.db.log_message("ai", text)
        self.meta_label.config(text=self._meta_text())

    def _set_status(self, text: str) -> None:
        self.status.config(text=text)

    def _drain_queue(self) -> None:
        while True:
            try:
                action, args = self.queue.get_nowait()
            except queue.Empty:
                break
            if action == "reply":
                self._reply(*args)
            elif action == "status":
                self._set_status(*args)
            elif action == "chart":
                self._show_chart_window(*args)
            elif action == "tool_step":
                self._show_tool_step(*args)
            elif action == "conn_status":
                reachable = args[0]
                if reachable:
                    self.conn_label.config(text="● AI Connected", fg=SUCCESS)
                else:
                    self.conn_label.config(text="● AI Offline", fg=WARNING)
        self.root.after(80, self._drain_queue)

    def _enqueue_reply(self, text: str, tag: str | None = None) -> None:
        self.queue.put(("reply", (text, tag)))

    def _enqueue_status(self, text: str) -> None:
        self.queue.put(("status", (text,)))

    def _enqueue_chart(self, company: str) -> None:
        self.queue.put(("chart", (company,)))

    def _on_agent_step(self, step: AgentStep) -> None:
        """Called from background thread when agent progresses."""
        if step.kind == "thinking":
            self._enqueue_status(f"🤔 {step.content}")
        elif step.kind == "tool_call":
            self._enqueue_status(f"🔧 {step.content}")
            self.queue.put(("tool_step", (step,)))
        elif step.kind == "tool_result":
            self._enqueue_status(f"📊 Processing {step.tool_name} results...")
        elif step.kind == "error":
            self._enqueue_status(f"⚠️ {step.content}")

    def _show_tool_step(self, step: AgentStep) -> None:
        """Show a tool call in the chat output for transparency."""
        tool_text = f"  🔧 {step.tool_name}"
        if step.tool_args:
            args_str = ", ".join(f"{k}={v}" for k, v in step.tool_args.items())
            tool_text += f"({args_str})"
        self.output.insert("end", f"{tool_text}\n", "tool")
        self.output.see("end")

    def ask(self, event=None) -> None:
        question = self.entry.get().strip()
        if not question:
            return
        self.entry.delete(0, "end")
        self._write("You", question)
        self.db.log_message("user", question)
        threading.Thread(target=self._process, args=(question,), daemon=True).start()

    def _process(self, question: str) -> None:
        """Process a user question through the agent router."""
        try:
            self._enqueue_status("🤔 Thinking...")
            result = self.agent.run(question)
            if result.answer:
                self._enqueue_reply(result.answer)
        except Exception as exc:
            self._enqueue_reply(f"Internal error: {exc}", "warning")
        finally:
            self._enqueue_status("Ready")
            # Refresh connection indicator after each interaction
            self._check_llm_connection()

    def _show_chart_window(self, company: str) -> None:
        df = read_price_frame(company)
        if df is None or df.empty:
            messagebox.showinfo("No data", f"No CSV found for {company}.")
            return
        if PLOTLY_AVAILABLE:
            DIAG_DIR.mkdir(parents=True, exist_ok=True)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], mode="lines", name="Close"))
            if len(df) >= 20:
                fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"].rolling(20).mean(), mode="lines", name="MA20"))
            if len(df) >= 50:
                fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"].rolling(50).mean(), mode="lines", name="MA50"))
            fig.update_layout(title=f"{company} close price", xaxis=dict(rangeslider=dict(visible=True)), template="plotly_dark")
            out = DIAG_DIR / f"{company.replace(' ', '_')}_chart.html"
            plotly_plot(fig, filename=str(out), auto_open=True)
            self._reply(f"Chart written to {out}", "success")
            return
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showinfo("No chart library", "Install plotly or matplotlib.")
            return
        figure = Figure(figsize=(10, 4), dpi=100)
        axis = figure.add_subplot(111)
        axis.plot(df["Date"], df["Close"], linewidth=1, label="Close")
        if len(df) >= 20:
            axis.plot(df["Date"], df["Close"].rolling(20).mean(), linewidth=1, label="MA20")
        if len(df) >= 50:
            axis.plot(df["Date"], df["Close"].rolling(50).mean(), linewidth=1, label="MA50")
        axis.set_title(f"{company} close")
        axis.legend()
        figure.autofmt_xdate()
        win = tk.Toplevel()
        win.title(f"{company} chart")
        FigureCanvasTkAgg(figure, master=win).get_tk_widget().pack(fill="both", expand=True)


if __name__ == "__main__":
    root = tk.Tk()
    TradingUI(root)
    root.mainloop()
