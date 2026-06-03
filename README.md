# Share Market Analysis

> **Disclaimer:** This is not financial advice software. Treat all output as research assistance only. Verify all signals independently before making any trading decisions.

A Python desktop and CLI market intelligence assistant for Indian equities. Combines local OHLCV data, live Yahoo Finance feeds, Google News RSS, FinBERT sentiment analysis, and a local LLM to generate scored intelligence packets and ranked company insights — all from your own machine, no cloud dependency.

---

## What it does

- Fetches and stores historical OHLCV price data locally for NSE-listed companies
- Computes technical indicators, risk scores, fundamental scores, and strategy signals
- Pulls Google News RSS headlines and runs them through **FinBERT** for financial sentiment scoring
- Fetches fundamentals and live data via **Yahoo Finance**
- Ranks tracked companies by a composite intelligence score
- Answers natural-language questions about companies via a **local LLM** (OpenAI-compatible endpoint)
- Runs as either a **Tkinter desktop terminal** or a headless **CLI engine**

---

## Current tracked companies

| Company | NSE Symbol | Daily CSV rows |
|---|---|---:|
| Infosys | `INFY` | 1,238 |
| Tata Consultancy Services | `TCS` | 1,238 |
| Asian Paints | `ASIANPAINT` | 1,237 |
| Reliance Industries Ltd | `RELIANCE` | 1,238 |

**Cached ranking (last observed):**
1. Infosys — `54.18`
2. Tata Consultancy Services — `53.16`
3. Asian Paints — `52.18`
4. Reliance Industries Ltd — `43.11`

---

## Architecture

```
ai_trading_assistant_ui.py          Tkinter desktop terminal (primary UI)
main.py                             CLI refresh and ranking entrypoint
core/
  orchestrator.py                   Active intelligence pipeline
  analytics_engine.py               Win rate, volatility, ATR, drawdown, regime
  risk_engine.py                    Risk scoring
  sentiment_engine.py               Standalone FinBERT sentiment helper
  data_fetcher.py                   CSV fetch/save helper
  database.py                       DB abstraction layer
  symbol_resolver.py                NSE symbol resolution
data/raw/<Company>/prices/daily/    Local OHLCV CSVs
assistant.db                        Active SQLite database
```

**External services:**
- `ProsusAI/finbert` via Hugging Face — financial sentiment model
- Yahoo Finance via `yfinance` — price and fundamental data
- Google News RSS — headline feed
- Local LLM: `http://localhost:1234/v1/chat/completions` (e.g. LM Studio with `meta-llama-3.1-8b-instruct`)

---

## Tech stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat&logo=pytorch&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=flat&logo=pandas&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?style=flat&logo=huggingface&logoColor=black)

---

## Setup

> The committed `venv` is broken — it points to a missing Python path. Always recreate it fresh.

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m pip install plotly
```

**Requirements:** Python 3.10+, a local LLM server on port 1234 for Q&A, internet for Yahoo Finance and Google News, ~4GB RAM for FinBERT.

---

## Run

```powershell
# Desktop assistant (recommended)
.\venv\Scripts\python.exe ai_trading_assistant_ui.py

# CLI refresh and ranking
.\venv\Scripts\python.exe main.py

# Force strategy backtest rebuild
.\venv\Scripts\python.exe main.py --force-strategy
```

---

## UI commands

```
list companies                         List all tracked companies
add company <name> [NSE_SYMBOL]        Add a company to track
set nse symbol <name> <SYMBOL>         Update NSE symbol
remove company <name>                  Remove a company
show chart <name>                      Display price chart
rank companies                         Show composite intelligence ranking
refresh all                            Refresh all data and recompute scores
last <N> days win rate for <name>      Win rate over last N trading days
help                                   Show all commands
```

Natural-language questions also work. Answered from intelligence packets if available, otherwise routed to the local LLM with full DB context.

---

## Known issues

1. `core/orchestrator.py` defines `fetch_and_store_prices` twice — second definition silently overrides the first
2. `Orchestrator()` startup takes ~86 seconds due to eager FinBERT loading — lazy loading planned
3. INFY, RELIANCE, TCS CSVs contain a duplicate ticker row after the header — normalisation pending
4. `core/database.py` uses `trading_system.db` while active pipeline uses `assistant.db` — consolidation needed
5. LLM URL and model name are hardcoded — moving to `.env` config
6. UI background threads call Tkinter methods directly — needs `root.after()` routing

---

## Roadmap

- [ ] Lazy-load FinBERT on first sentiment request (faster startup)
- [ ] Normalize CSV files (remove ticker row)
- [ ] Consolidate DB to single `assistant.db` abstraction
- [ ] Move hardcoded config to `.env` file
- [ ] Add pytest coverage for CSV parsing, scoring, ranking, command parsing
- [ ] Add more NSE companies
- [ ] Export ranked intelligence reports to PDF or Excel

---

## Contributing

Contributions welcome. Open an issue to discuss what you want to change before submitting a PR.

---

*Built as a personal learning project — exploring financial data pipelines, NLP applied to markets, and local AI inference.*
