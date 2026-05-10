from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
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


def normalize_agent_endpoint(url_or_host: str, *, execute_path: str = "/execute") -> str:
    """Turn a host, ``host:port``, or URL into a full URL for :class:`HttpAgent` POSTs.

    Examples:

    - ``\"192.168.1.10:8080\"`` → ``http://192.168.1.10:8080/execute``
    - ``\"http://10.0.0.5\"`` → ``http://10.0.0.5/execute`` (path was empty)
    - ``\"https://worker.example.com/v1/run\"`` → unchanged (non-root path preserved)

    ``execute_path`` is only applied when the URL path is empty or ``/``.
    """
    raw = url_or_host.strip()
    if not raw:
        raise ValueError("agent endpoint must be non-empty")
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    path = parsed.path or ""
    ep = execute_path if execute_path.startswith("/") else "/" + execute_path
    new_path = ep if path in ("", "/") else path
    return urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))


def http_agents_from_endpoints(
    expert_to_endpoint: Mapping[str, str],
    *,
    execute_path: str = "/execute",
    **http_agent_kwargs: Any,
) -> dict[str, HttpAgent]:
    """Build the ``agents`` dict for :meth:`~aegean.protocol.AegeanProtocol.execute` from remote workers.

    Each *value* is a host/IP, ``host:port``, or full URL; each is normalized with
    :func:`normalize_agent_endpoint`. Remote servers must accept **POST** JSON
    ``{\"task\": <task dict>, \"agent_id\": <id or null>}`` and return the standard
    ``execute`` result shape.

    ``**http_agent_kwargs`` are passed to each :class:`HttpAgent` (e.g. ``timeout_s``, ``headers``).
    """
    return {
        expert_id: HttpAgent(
            endpoint=normalize_agent_endpoint(url_or_host, execute_path=execute_path),
            **http_agent_kwargs,
        )
        for expert_id, url_or_host in expert_to_endpoint.items()
    }
