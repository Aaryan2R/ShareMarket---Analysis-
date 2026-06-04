from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_PATH = DATA_DIR / "raw"
DB_PATH = ROOT / os.getenv("SMA_DB_PATH", "assistant.db")
DIAG_DIR = ROOT / "diagnostics"
LOG_DIR = ROOT / "logs"

LLM_API_URL = os.getenv("SMA_LLM_API_URL", "http://localhost:1234/v1/chat/completions")
LLM_MODEL = os.getenv("SMA_LLM_MODEL", "meta-llama-3.1-8b-instruct")
LLM_TIMEOUT_SECONDS = int(os.getenv("SMA_LLM_TIMEOUT_SECONDS", "45"))

FINBERT_MODEL = os.getenv("SMA_FINBERT_MODEL", "ProsusAI/finbert")
ENABLE_LIVE_SENTIMENT = os.getenv("SMA_ENABLE_LIVE_SENTIMENT", "1") not in {"0", "false", "False"}
ENABLE_LIVE_FUNDAMENTALS = os.getenv("SMA_ENABLE_LIVE_FUNDAMENTALS", "1") not in {"0", "false", "False"}
ENABLE_LIVE_REGIME = os.getenv("SMA_ENABLE_LIVE_REGIME", "1") not in {"0", "false", "False"}

STRATEGY_CACHE_HOURS = int(os.getenv("SMA_STRATEGY_CACHE_HOURS", "6"))

