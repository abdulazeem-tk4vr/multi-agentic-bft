"""Execute one dashboard session from POST spec."""

from __future__ import annotations

import dataclasses
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable

from aegean import AegeanConfig, AegeanRunner, http_agents_from_endpoints
from aegean.adapters import OpenRouterAgent
from aegean.types import calculate_quorum_size, validate_failstop_fault_bound


def load_dotenv(repo_root: Path) -> None:
    import os

    path = repo_root / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def _text_preview(text: Any, max_chars: int = 200) -> tuple[str, int]:
    if text is None:
        return "(none)", 0
    s = text if isinstance(text, str) else repr(text)
    n = len(s)
    one = s.replace("\r", "").replace("\n", " ")
    if len(one) > max_chars:
        return one[: max_chars - 3] + "...", n
    return one, n


def _trace_worker(viz: Any, task: dict[str, Any], result: dict[str, Any]) -> None:
    bag = (task.get("context") or {}).get("aegean") or {}
    phase = str(bag.get("phase", "?"))
    agent = str(bag.get("agent_id", task.get("id", "?")))
    rnum = bag.get("round_num", "-")
    if result.get("ok"):
        out = (result.get("value") or {}).get("output")
        prev, _ = _text_preview(out, 200)
        tok = (result.get("value") or {}).get("metadata", {}).get("tokens_used", "?")
    else:
        prev, _ = _text_preview(result.get("error", ""), 200)
        tok = "—"
    viz.worker_trace(agent_id=agent, phase=phase, round_num=rnum, preview=prev, tokens=tok, ok=bool(result.get("ok")))


def _parse_spec(data: dict[str, Any]) -> tuple[list[str], dict[str, Any], AegeanConfig, int]:
    n = int(data.get("n_agents", 3))
    if n < 3 or n > 32:
        raise ValueError("n_agents must be between 3 and 32")

    raw_ids = (data.get("expert_ids") or "").strip()
    if raw_ids:
        experts = [x.strip() for x in raw_ids.split(",") if x.strip()]
        if len(experts) != n:
            raise ValueError(f"expert_ids must list exactly {n} ids (comma-separated)")
        if len(set(experts)) != len(experts):
            raise ValueError("expert_ids must be unique")
    else:
        experts = [f"a{i}" for i in range(1, n + 1)]

    desc = (data.get("task_description") or "").strip()
    if not desc:
        raise ValueError("task_description is required")

    task_id = (data.get("task_id") or "t1").strip() or "t1"
    task: dict[str, Any] = {"id": task_id, "description": desc, "context": {}}

    f = int(data.get("byzantine_tolerance", 0))
    validate_failstop_fault_bound(n, f)
    alpha = int(data.get("alpha", 2))
    beta = int(data.get("beta", 2))
    if alpha > n:
        alpha = n

    cfg = AegeanConfig(
        max_rounds=int(data.get("max_rounds", 5)),
        alpha=alpha,
        beta=beta,
        byzantine_tolerance=f,
        confidence_threshold=float(data.get("confidence_threshold", 0.7)),
        round_timeout_ms=int(data.get("round_timeout_ms", 60_000)),
        early_termination=bool(data.get("early_termination", True)),
        session_trace=bool(data.get("session_trace", False)),
        max_election_attempts=int(data.get("max_election_attempts", 32)),
    )
    if cfg.alpha > n:
        cfg = dataclasses.replace(cfg, alpha=n)

    base_port = int(data.get("openrouter_base_port", 18_700))
    if base_port < 1024 or base_port > 65500:
        raise ValueError("openrouter_base_port out of range")
    return experts, task, cfg, base_port


def validate_spec_for_submit(spec: dict[str, Any], repo_root: Path) -> str | None:
    import os

    try:
        _parse_spec(spec)
    except ValueError as e:
        return str(e)
    load_dotenv(repo_root)
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        return "OPENROUTER_API_KEY not set (configure .env or environment)"
    return None


def run_dashboard_session(
    viz: Any,
    spec: dict[str, Any],
    *,
    repo_root: Path,
    on_cancel_ready: Callable[[Callable[[], None]], None] | None = None,
) -> None:
    import os

    load_dotenv(repo_root)
    experts, task, aegean_cfg, base_port = _parse_spec(spec)
    session_id = (spec.get("session_id") or "dashboard").strip() or "dashboard"
    quorum_r = calculate_quorum_size(len(experts), aegean_cfg.byzantine_tolerance)
    viz.configure(experts=experts, session_id=session_id, quorum_r=quorum_r)
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        raise ValueError("OPENROUTER_API_KEY not set (add to .env or environment)")
    _run_openrouter(viz, experts, session_id, task, aegean_cfg, base_port, on_cancel_ready=on_cancel_ready)


def _run_openrouter(
    viz: Any,
    experts: list[str],
    session_id: str,
    task: dict[str, Any],
    aegean_cfg: AegeanConfig,
    base_port: int,
    *,
    on_cancel_ready: Callable[[Callable[[], None]], None] | None = None,
) -> None:
    import os

    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip() or "openai/gpt-4o-mini"
    llm = OpenRouterAgent(model=model, timeout_s=120.0)

    class Ctx:
        viz: Any
        llm: OpenRouterAgent

    ctx = Ctx()
    ctx.viz = viz
    ctx.llm = llm

    def execute(task_d: dict[str, Any]) -> dict[str, Any]:
        return ctx.llm.execute(task_d)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802
            if self.path.rstrip("/") != "/execute":
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(n) if n else b"{}"
                body = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, ValueError):
                self.send_error(400)
                return
            t = body.get("task")
            if not isinstance(t, dict):
                out: dict[str, Any] = {"ok": False, "error": "bad task"}
            else:
                out = execute(t)
                _trace_worker(ctx.viz, t, out)
            b = json.dumps(out).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    servers: list[HTTPServer] = []
    threads: list[threading.Thread] = []
    for i, _eid in enumerate(experts):
        port = base_port + i
        httpd = HTTPServer(("127.0.0.1", port), Handler)
        servers.append(httpd)
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        threads.append(th)
        th.start()
    time.sleep(0.2)

    endpoints = {eid: f"127.0.0.1:{base_port + i}" for i, eid in enumerate(experts)}
    agents = http_agents_from_endpoints(endpoints, execute_path="/execute", timeout_s=120.0)
    runner = AegeanRunner(config=aegean_cfg, event_bus=viz.bus)
    cancelled = threading.Event()

    def cancel_run() -> None:
        if cancelled.is_set():
            return
        cancelled.set()
        runner.cancel("cancelled by dashboard user")
        for httpd in servers:
            try:
                httpd.shutdown()
            except Exception:
                pass

    if on_cancel_ready is not None:
        on_cancel_ready(cancel_run)
    try:
        result = runner.run(
            {"session_id": session_id, "pattern": "aegean", "experts": experts, "task": task},
            agents,
        )
        viz.finalize(result)
    finally:
        for httpd in servers:
            httpd.shutdown()
        for th in threads:
            th.join(timeout=5.0)
