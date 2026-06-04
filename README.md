# Share Market Analysis

> ⚠️ **Not financial advice.** This is a personal research and learning project. All output is for study purposes only — verify every signal independently before making any trading decisions.

A local-first, AI-powered market intelligence assistant for Indian equities. Runs entirely on your own machine — no cloud, no subscriptions, no data sent anywhere.

Combines live Yahoo Finance data, Google News sentiment via FinBERT, technical and risk scoring, and a local LLM agent that can call real tools before answering your questions.

---

## What makes this interesting

Most stock analysis tools are either basic chart viewers or expensive SaaS. This one runs a full intelligence pipeline locally:

- Pulls historical OHLCV data and live fundamentals from **Yahoo Finance**
- Scrapes **Google News RSS** for each company and scores headlines with **FinBERT** (a finance-specific sentiment model from Hugging Face)
- Computes technical indicators, volatility, ATR, drawdown, win rate, and market regime
- Builds scored **intelligence packets** per company combining all signals
- Ranks companies by a composite score across technical, risk, fundamental, and strategy dimensions
- Routes natural-language questions through a **local LLM agent** (via LM Studio) that can call real tools — ranking, comparison, win-rate, chart generation, CSV normalization — before forming its answer
- Falls back gracefully to cached local data when the LLM is offline

---

## Architecture

```
ai_trading_assistant_ui.py      Tkinter desktop terminal (primary UI)
main.py                         CLI runner — refresh, rank, normalize
core/
  config.py                     Env-driven runtime config
  database.py                   SQLite gateway (assistant.db)
  orchestrator.py               Intelligence pipeline — packets, ranking, price fetch
  agent_router.py               LLM tool-calling loop
  tools.py                      Local tools exposed to the agent
  rag_engine.py                 Retrieval context builder for LLM prompts
  company_match.py              Fuzzy/alias company name matching
  market_data.py                CSV discovery and normalization
  llm_client.py                 OpenAI-compatible local LLM client
  prompts.py                    Tool-calling system prompts
data/raw/<Company>/prices/      Local OHLCV CSVs
assistant.db                    Active SQLite database
tests/                          Pytest suite (6 passing)
```

---

## How the AI agent works

```
You ask:  "compare TCS and Infosys"
    ↓
AgentRouter checks if local LLM is reachable
    ↓
LLM emits a JSON tool call → { "tool": "compare_companies", "args": [...] }
    ↓
App executes the tool locally against real data
    ↓
Tool result is sent back to LLM as context
    ↓
LLM forms final answer grounded in your actual local data
    ↓
If LLM is offline → falls back to direct local data answer
```

---

## Tech stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat&logo=pytorch&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=flat&logo=pandas&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?style=flat&logo=huggingface&logoColor=black)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?style=flat&logo=plotly&logoColor=white)
![Yahoo Finance](https://img.shields.io/badge/Yahoo%20Finance-6001D2?style=flat&logo=yahoo&logoColor=white)

**Models & services:**
- [`ProsusAI/finbert`](https://huggingface.co/ProsusAI/finbert) — finance sentiment model
- Yahoo Finance via `yfinance`
- Google News RSS
- Local LLM via [LM Studio](https://lmstudio.ai) — tested with `meta-llama-3.1-8b-instruct`

---

## Currently tracked companies

| Company | NSE Symbol | Price rows |
|---|---|---:|
| Infosys | `INFY` | 1,238 |
| Tata Consultancy Services | `TCS` | 1,238 |
| Asian Paints | `ASIANPAINT` | 1,237 |
| Reliance Industries Ltd | `RELIANCE` | 1,238 |

**Latest composite ranking:**

| Rank | Company | Score |
|---|---|---|
| 1 | Infosys | 54.18 |
| 2 | Tata Consultancy Services | 53.16 |
| 3 | Asian Paints | 52.18 |
| 4 | Reliance Industries Ltd | 43.11 |

---

## Setup

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

**For AI chat features:** install [LM Studio](https://lmstudio.ai), load any OpenAI-compatible model, and start the local server on port 1234. The app works without it — you just get data-only answers.

**Requirements:** Python 3.10+, ~4GB RAM for FinBERT, internet for Yahoo Finance and Google News feeds.

---

## Run

```powershell
# Desktop assistant (recommended)
.\venv\Scripts\python.exe ai_trading_assistant_ui.py

# CLI — refresh all packets and show ranking
.\venv\Scripts\python.exe main.py

# CLI — show cached ranking only (fast, no network)
.\venv\Scripts\python.exe main.py --rank-only

# Normalize CSVs and rank
.\venv\Scripts\python.exe main.py --normalize-csvs --rank-only

# Force strategy backtest rebuild
.\venv\Scripts\python.exe main.py --force-strategy
```

---

## Commands

```
rank companies                         Composite intelligence ranking
compare TCS and Infosys                Side-by-side company comparison
tell me about Reliance                 Full company intelligence summary
status Asian Paints                    Quick status snapshot
last 30 days win rate for Infosys      Win rate over N trading days
show chart for TCS                     Price chart
refresh all                            Refresh all data and recompute
normalize csvs                         Clean up CSV ticker rows
add company <name> [NSE_SYMBOL]        Add a new company to track
remove company <name>                  Remove a company
list companies                         List all tracked companies
help                                   Show all commands
```

---

## Runtime config

All config is driven by environment variables with sensible defaults:

| Variable | Default |
|---|---|
| `SMA_DB_PATH` | `assistant.db` |
| `SMA_LLM_API_URL` | `http://localhost:1234/v1/chat/completions` |
| `SMA_LLM_MODEL` | `meta-llama-3.1-8b-instruct` |
| `SMA_LLM_TIMEOUT_SECONDS` | `45` |
| `SMA_FINBERT_MODEL` | `ProsusAI/finbert` |
| `SMA_ENABLE_LIVE_SENTIMENT` | `1` |
| `SMA_ENABLE_LIVE_FUNDAMENTALS` | `1` |
| `SMA_ENABLE_LIVE_REGIME` | `1` |

**For fast offline testing (skips all network calls):**
```powershell
$env:SMA_ENABLE_LIVE_SENTIMENT='0'
$env:SMA_ENABLE_LIVE_FUNDAMENTALS='0'
$env:SMA_ENABLE_LIVE_REGIME='0'
.\venv\Scripts\python.exe -m pytest -q
```

---

## Tests

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

6 tests passing covering company matching, DB packet roundtrip, RAG retrieval, tool registry, and CSV normalization.

---

## Roadmap

- [ ] Add more NSE companies
- [ ] AgentRouter tests with mocked LLM tool-call JSON
- [ ] Mocked tests for live yfinance/news/Hugging Face refresh
- [ ] Settings UI for LLM endpoint and model
- [ ] Richer company detail view with charts inline
- [ ] Transcript export and search
- [ ] Pin dependency versions

---

## Contributing

Contributions welcome — open an issue first to discuss what you want to change.

---

*Personal project exploring financial data pipelines, NLP applied to markets, and local AI inference.*
