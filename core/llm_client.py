"""LLM client for the AI trading agent.

Supports:
- Standard chat completion
- Structured JSON output with retry on malformed responses
- Streaming responses (token-by-token callback)
- Retry with exponential backoff
- Connection health check
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable, Iterator

import requests

from .config import LLM_API_URL, LLM_MODEL, LLM_TIMEOUT_SECONDS

LOGGER = logging.getLogger(__name__)

# Regex to extract JSON from a ```json ... ``` code fence
_JSON_FENCE_RE = re.compile(
    r"```json\s*\n?(.*?)\n?\s*```",
    re.DOTALL,
)

# Fallback: bare JSON object in the response
_BARE_JSON_RE = re.compile(
    r'\{\s*"tool"\s*:.*?\}',
    re.DOTALL,
)


class LLMClient:
    """OpenAI-compatible local LLM client with retry and streaming."""

    def __init__(self, api_url: str = LLM_API_URL, model: str = LLM_MODEL):
        self.api_url = api_url
        self.model = model
        self._base_url = api_url.rsplit("/chat/completions", 1)[0]

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def is_reachable(self) -> bool:
        """Quick connectivity check against the LLM endpoint."""
        try:
            url = self._base_url + "/models"
            resp = requests.get(url, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Core chat (with retry)
    # ------------------------------------------------------------------

    def chat(
        self,
        system: str,
        user: str,
        history: list[dict[str, str]] | None = None,
        *,
        temperature: float = 0.25,
        max_tokens: int = 1200,
        retries: int = 2,
    ) -> str:
        """Send a chat completion request with retry on failure."""
        messages = self._build_messages(system, user, history)

        last_error: Exception | None = None
        for attempt in range(1 + retries):
            if attempt > 0:
                delay = min(2 ** attempt, 8)
                LOGGER.info("LLM retry %d after %ds", attempt, delay)
                time.sleep(delay)
            try:
                response = requests.post(
                    self.api_url,
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "top_p": 0.9,
                        "max_tokens": max_tokens,
                    },
                    timeout=LLM_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as exc:
                last_error = exc
                LOGGER.warning("LLM call attempt %d failed: %s", attempt + 1, exc)

        return (
            "The local AI model is not reachable right now. "
            f"Endpoint: {self.api_url}. Error: {last_error}"
        )

    # ------------------------------------------------------------------
    # Structured output (parse JSON tool call from LLM response)
    # ------------------------------------------------------------------

    def chat_for_tool_call(
        self,
        system: str,
        user: str,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str | None, dict[str, Any] | None, str]:
        """Chat and attempt to parse a tool call from the response.

        Returns (tool_name, tool_args, raw_text).
        If the response contains a valid tool call, tool_name and tool_args
        are populated.  Otherwise they are None and raw_text is the full
        LLM response (which is the final answer).
        """
        raw = self.chat(system, user, history, max_tokens=1200)
        tool_name, tool_args = self._parse_tool_call(raw)
        return tool_name, tool_args, raw

    def _parse_tool_call(self, text: str) -> tuple[str | None, dict[str, Any] | None]:
        """Try to extract a tool call JSON from LLM output."""
        # Strategy 1: look for ```json ... ``` fence
        match = _JSON_FENCE_RE.search(text)
        if match:
            return self._try_parse_json(match.group(1))

        # Strategy 2: bare JSON with "tool" key
        match = _BARE_JSON_RE.search(text)
        if match:
            return self._try_parse_json(match.group(0))

        return None, None

    def _try_parse_json(self, raw: str) -> tuple[str | None, dict[str, Any] | None]:
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and "tool" in obj:
                return obj["tool"], obj.get("args", {})
        except json.JSONDecodeError:
            # Try to fix common LLM JSON issues
            fixed = raw.strip().rstrip(",")
            try:
                obj = json.loads(fixed)
                if isinstance(obj, dict) and "tool" in obj:
                    return obj["tool"], obj.get("args", {})
            except json.JSONDecodeError:
                pass
        return None, None

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def chat_stream(
        self,
        system: str,
        user: str,
        history: list[dict[str, str]] | None = None,
        *,
        on_token: Callable[[str], None] | None = None,
        temperature: float = 0.25,
        max_tokens: int = 1200,
    ) -> str:
        """Streaming chat — calls on_token(chunk) as tokens arrive.

        Returns the full assembled response text.
        Falls back to non-streaming if the server doesn't support SSE.
        """
        messages = self._build_messages(system, user, history)
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
                timeout=LLM_TIMEOUT_SECONDS,
                stream=True,
            )
            response.raise_for_status()

            full_text = ""
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_text += content
                        if on_token:
                            on_token(content)
                except json.JSONDecodeError:
                    continue
            return full_text.strip()

        except Exception as exc:
            LOGGER.warning("Streaming failed, falling back to non-stream: %s", exc)
            return self.chat(system, user, history,
                             temperature=temperature, max_tokens=max_tokens)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        system: str,
        user: str,
        history: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for item in history or []:
            role = item.get("role", "user")
            if role == "ai":
                role = "assistant"
            if role in {"user", "assistant"}:
                messages.append({"role": role, "content": item.get("message", "")})
        messages.append({"role": "user", "content": user})
        return messages
