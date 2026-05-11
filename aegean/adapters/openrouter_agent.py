from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..task_routing import aegean_task_phase
from .base import error_result, ok_result

# Maximum number of retry attempts on HTTP 429 / 503.
_MAX_RETRIES = 5
# Initial backoff in seconds; doubles each retry (capped at 60 s).
_RETRY_BACKOFF_BASE = 4.0


class OpenRouterAgent:
    """OpenRouter-backed production adapter implementing the protocol `execute(task)` contract.

    The protocol only calls ``agent.execute(task)``.
    This adapter hides provider-specific API calls internally and returns the
    standard Aegean result shape.

    Retries automatically on HTTP 429 (rate-limited) and 503 (overloaded) with
    exponential backoff so free-tier concurrent workers do not fail immediately.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        timeout_s: float = 45.0,
        base_url: str = "https://openrouter.ai/api/v1/chat/completions",
        system_prompt: str | None = None,
        app_name: str | None = None,
        site_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        max_retries: int = _MAX_RETRIES,
        retry_backoff_base: float = _RETRY_BACKOFF_BASE,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.timeout_s = float(timeout_s)
        self.base_url = base_url
        self.system_prompt = system_prompt or "You are a careful reasoning assistant."
        self.app_name = app_name or os.getenv("OPENROUTER_APP_NAME")
        self.site_url = site_url or os.getenv("OPENROUTER_SITE_URL")
        self.temperature = float(temperature)
        self.max_tokens = max_tokens
        self.max_retries = int(max_retries)
        self.retry_backoff_base = float(retry_backoff_base)

    def _build_messages(self, task: dict[str, Any]) -> list[dict[str, str]]:
        phase = aegean_task_phase(task)
        prompt = str(task.get("description", ""))
        parts = [f"Task ID: {task.get('id')}", f"Phase: {phase}", f"Task:\n{prompt}"]
        # Refm: ``description`` already embeds R̄ from :func:`~aegean.task_routing.build_refm_task`;
        # do not append ``refinement_set`` again (same bytes, wasted tokens).
        user_text = "\n\n".join(parts)
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_text},
        ]

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            return error_result("OPENROUTER_API_KEY is missing")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(task),
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = int(self.max_tokens)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.app_name:
            headers["X-Title"] = self.app_name
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url

        req = Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        raw: str = ""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(req, timeout=self.timeout_s) as resp:
                    raw = resp.read().decode("utf-8")
                last_exc = None
                break
            except HTTPError as exc:
                if exc.code in (429, 503) and attempt < self.max_retries:
                    wait = min(self.retry_backoff_base * (2 ** attempt), 60.0)
                    time.sleep(wait)
                    last_exc = exc
                    continue
                return error_result(f"openrouter request failed: {exc}")
            except (URLError, TimeoutError) as exc:
                return error_result(f"openrouter request failed: {exc}")
        if last_exc is not None:
            return error_result(f"openrouter request failed after {self.max_retries} retries: {last_exc}")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return error_result("openrouter response is not valid JSON")

        try:
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):
                # Some providers return list blocks; keep text fragments.
                content = "".join(str(block.get("text", "")) for block in content if isinstance(block, dict))
            text = str(content).strip()
        except Exception:
            return error_result("openrouter response missing choices[0].message.content")

        usage = data.get("usage") or {}
        tokens = int(
            usage.get("total_tokens")
            or (int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0)))
        )

        return ok_result(text, tokens_used=tokens, provider="openrouter", model=self.model)
