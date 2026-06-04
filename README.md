# Improved Share Market Analysis

Python desktop/CLI market intelligence assistant for Indian equities. This copy keeps the original data and `assistant.db`, but uses a cleaner app structure, a working virtual environment, normalized price CSVs, RAG retrieval, and an agent-style AI router that can call local tools before answering.

This is research-support software, not financial advice. Verify all signals independently before trading.

## What Changed

- Fresh working `venv` for this copied project.
- Lazy `Orchestrator()` startup: FinBERT, Yahoo fundamentals, and market-regime fetches are not loaded during app construction.
- Unified active SQLite layer around `assistant.db`.
- RAG retrieval over companies, cached packets, price metadata, and the company universe.
- New agent router: the local LLM can request tools such as ranking, company analysis, comparison, win-rate, charting, CSV normalization, and price fetching.
- Tool results are executed locally, then passed back to the LLM for the final answer.
- Data-only fallback when the local AI server is offline.
- Tkinter thread safety via a main-thread queue.
- CSV normalization to remove ticker rows such as `,INFY.NS,INFY.NS,...`.
- Automated tests for matching, DB packet roundtrip, RAG retrieval, tool registry, and CSV normalization.

## Active Structure

```text
ai_trading_assistant_ui.py   Tkinter desktop assistant
main.py                      CLI runner
assistant.db                 Active SQLite DB
core/
  config.py                  Paths and env-driven runtime config
  database.py                Unified assistant.db gateway
  company_match.py           Alias/fuzzy company matching
  market_data.py             CSV discovery and normalization
  orchestrator.py            Packet build/ranking/price fetch logic
  rag_engine.py              Retrieval context builder
  agent_router.py            LLM-driven tool-calling loop
  tools.py                   Local tools exposed to the agent
  prompts.py                 Tool-calling prompts
  llm_client.py              OpenAI-compatible local LLM client
tests/                       Pytest suite
data/raw/                    Local company price data
archive_old_engine/          Old engine kept for reference only
```

## Setup

The improved copy already has a fresh virtual environment. To recreate it:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

Desktop app:

```powershell
.\venv\Scripts\python.exe ai_trading_assistant_ui.py
```

For full natural-language AI chat, start LM Studio or another OpenAI-compatible local server first. The default endpoint is:

```text
http://localhost:1234/v1/chat/completions
```

If LM Studio is not running, the app still opens and gives data-only fallback answers for supported questions such as rankings and company summaries.

CLI cached ranking:

```powershell
.\venv\Scripts\python.exe main.py --rank-only
```

Normalize active daily CSVs:

```powershell
.\venv\Scripts\python.exe main.py --normalize-csvs --rank-only
```

Refresh packets:

```powershell
.\venv\Scripts\python.exe main.py
```

Force strategy rebuild:

```powershell
.\venv\Scripts\python.exe main.py --force-strategy
```

## How Chat Works

1. You ask a normal question, for example `compare TCS and Infosys`.
2. `AgentRouter` checks whether the local LLM endpoint is reachable.
3. If reachable, the model can emit a JSON tool call.
4. The app executes the requested local tool, such as `compare_companies` or `rank_companies`.
5. The tool result is sent back to the model.
6. The model gives the final answer using only the available data.
7. If the model is offline, the app falls back to raw local data where possible.

## Useful Questions

```text
help
rank companies
compare TCS and Infosys
tell me about Reliance
status Asian Paints
last 30 days win rate for Infosys
show chart for TCS
normalize csvs
refresh all
```

## Runtime Config

Environment variables:

```text
SMA_DB_PATH                  default: assistant.db
SMA_LLM_API_URL              default: http://localhost:1234/v1/chat/completions
SMA_LLM_MODEL                default: meta-llama-3.1-8b-instruct
SMA_LLM_TIMEOUT_SECONDS      default: 45
SMA_FINBERT_MODEL            default: ProsusAI/finbert
SMA_ENABLE_LIVE_SENTIMENT    default: 1
SMA_ENABLE_LIVE_FUNDAMENTALS default: 1
SMA_ENABLE_LIVE_REGIME       default: 1
SMA_STRATEGY_CACHE_HOURS     default: 6
```

For fast offline packet smoke tests:

```powershell
$env:SMA_ENABLE_LIVE_SENTIMENT='0'
$env:SMA_ENABLE_LIVE_FUNDAMENTALS='0'
$env:SMA_ENABLE_LIVE_REGIME='0'
```

If console output containing symbols fails on Windows, use:

```powershell
$env:PYTHONIOENCODING='utf-8'
```

## Verification

Verified on 2026-06-05 after the agent-router changes:

```powershell
.\venv\Scripts\python.exe -m compileall -q main.py ai_trading_assistant_ui.py core tests
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -c "import ai_trading_assistant_ui; print('ui import ok')"
.\venv\Scripts\python.exe main.py --rank-only
```

Results:

- Compile passed.
- Tests passed: `6 passed`.
- UI import passed.
- Default local LLM status during testing: offline at `http://localhost:1234/v1/chat/completions`.
- Agent fallback passed with a forced-offline endpoint and returned cached rankings.
- Tool registry `rank_companies` passed and returned 4 cached companies.
- Cached ranking:
  1. Infosys - `54.18`
  2. Tata Consultancy Services - `53.16`
  3. Asian Paints - `52.18`
  4. Reliance Industries Ltd - `43.11`

## Remaining Practical Work

- Add AgentRouter tests with a fake LLM that emits tool-call JSON.
- Add mocked tests for live yfinance/news/Hugging Face refresh.
- Add a settings UI for `SMA_LLM_API_URL` and `SMA_LLM_MODEL`.
- Add a richer company detail view.
- Add transcript export/search.
- Pin dependency versions after settling the Python version.
- Clean up mojibake/Unicode display strings in source comments/UI labels if they appear garbled on Windows.

