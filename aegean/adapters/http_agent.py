from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import error_result


class HttpAgent:
    """Generic HTTP-backed agent adapter.

    Expects remote endpoint to return protocol-compatible payload shape:
    ``{"ok": bool, "value": {"output": ..., "metadata": {...}}}``.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        timeout_s: float = 30.0,
        headers: dict[str, str] | None = None,
        include_agent_id_in_body: bool = True,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_s = float(timeout_s)
        self.headers = dict(headers or {})
        self.include_agent_id_in_body = bool(include_agent_id_in_body)

    def _build_payload(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = {"task": task}
        if self.include_agent_id_in_body:
            bag = ((task.get("context") or {}).get("aegean") or {})
            payload["agent_id"] = bag.get("agent_id")
        return payload

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = self._build_payload(task)
        body = json.dumps(payload).encode("utf-8")
        req_headers = {"Content-Type": "application/json", **self.headers}
        req = Request(self.endpoint, data=body, headers=req_headers, method="POST")
        try:
            with urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            return error_result(f"http agent request failed: {exc}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return error_result("http agent response is not valid JSON")
        if not isinstance(parsed, dict):
            return error_result("http agent response must be a JSON object")
        return parsed
