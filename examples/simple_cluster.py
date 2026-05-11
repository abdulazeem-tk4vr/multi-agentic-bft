#!/usr/bin/env python3
"""Local HTTP cluster: one ``/execute`` server per expert, then Aegean runs.

Workers call **OpenRouter** (same stack as ``aegean.adapters.OpenRouterAgent``). Set
``OPENROUTER_API_KEY`` in the environment **or** in ``multi-agentic-bft/.env`` (loaded at
startup; existing env vars are not overwritten). Optional: ``OPENROUTER_MODEL`` (default
``openai/gpt-4o-mini``).

Session trace (summary, events, rounds) is printed by the library when
``AegeanConfig(session_trace=True)`` or env ``AEGEAN_SESSION_TRACE=1`` (to stderr).

Run: ``python examples/simple_cluster.py``

Quick env check (same ``.env`` rules as the network monitor): ``python examples/simple_cluster.py --check-env``
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from aegean import AegeanConfig, EventBus, http_agents_from_endpoints, run_aegean_session
from aegean.adapters import OpenRouterAgent

# --- USER: experts (>=3), ports, session task, logging --------------------------------------

EXPERT_IDS = ["a1", "a2", "a3"]
BASE_PORT = 18_700

# Enables ``AegeanConfig(session_trace=...)`` plus per-worker lines below.
VERBOSE = True

# Underspecified on purpose: experts often disagree, so you can watch quorum, refinement,
# and early termination in the session trace. Tightening the task increases agreement.
SESSION_TASK: dict[str, Any] = {
    "id": "t1",
    "description": (
        "WHo is more handsome? Shahrukh Khan or Brad Pitt One word only, pick a side, a man from India or USA, dont give vague answer and give reasoning in 5 words"
    ),
    "context": {},
}

# One client shared across worker threads (each HTTP call is independent).
_llm: OpenRouterAgent | None = None


def execute(task: dict[str, Any]) -> dict[str, Any]:
    """Protocol ``execute`` — forwards to OpenRouter (real chat completion per task)."""
    if _llm is None:
        return {"ok": False, "error": "OpenRouter client not initialized"}
    return _llm.execute(task)


def _text_preview(text: Any, max_chars: int = 140) -> tuple[str, int]:
    if text is None:
        return "(none)", 0
    s = text if isinstance(text, str) else repr(text)
    n = len(s)
    one = s.replace("\r", "").replace("\n", " ")
    if len(one) > max_chars:
        return one[: max_chars - 3] + "...", n
    return one, n


def _log_worker_response(task: dict[str, Any], result: dict[str, Any]) -> None:
    if not VERBOSE:
        return
    bag = (task.get("context") or {}).get("aegean") or {}
    phase = bag.get("phase", "?")
    agent = str(bag.get("agent_id", task.get("id", "?")))
    rnum = bag.get("round_num", "-")
    step = "soln" if phase == "soln" else f"r{rnum}"
    if result.get("ok"):
        out = (result.get("value") or {}).get("output")
        meta = (result.get("value") or {}).get("metadata") or {}
        tok = meta.get("tokens_used", "?")
        prev, nchars = _text_preview(out, 120)
        tail = f"  (+{nchars - 120} more chars)" if nchars > 120 else ""
        print(f"  WORKER  {step:>4}  {agent:>4}  tok={str(tok):>5}  {prev}{tail}", flush=True)
    else:
        print(f"  WORKER  {step:>4}  {agent:>4}  ERROR  {result.get('error', result)!r}", flush=True)


# --- framework -----------------------------------------------------------------------------


class ClusterRequestHandler(BaseHTTPRequestHandler):
    """POST /execute → :func:`execute` → OpenRouter."""

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
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
        task = body.get("task")
        if not isinstance(task, dict):
            out: dict[str, Any] = {"ok": False, "error": "bad task"}
        else:
            out = execute(task)
            _log_worker_response(task, out)
        b = json.dumps(out).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load ``.env`` files the same way as ``network_monitor.runner.load_dotenv`` (first wins per key)."""
    root = _repo_root()
    candidates = [
        root / ".env",
        root / "network-monitor" / ".env",
        Path.cwd() / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for raw in text.splitlines():
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


def check_env() -> int:
    """Print diagnostics for the same prerequisites the network monitor needs."""
    _load_dotenv()
    root = _repo_root()
    print("simple_cluster — env check (same .env search order as network monitor)", flush=True)
    print(f"  repo root: {root}", flush=True)
    print(f"  cwd:       {Path.cwd()}", flush=True)
    for label, p in (
        ("repo/.env", root / ".env"),
        ("network-monitor/.env", root / "network-monitor" / ".env"),
        ("cwd/.env", Path.cwd() / ".env"),
    ):
        print(f"  {label}: {'found' if p.is_file() else 'missing'}  ({p})", flush=True)

    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if key:
        tail = key[-4:] if len(key) > 4 else "****"
        print(f"  OPENROUTER_API_KEY: set (len={len(key)}, ends with …{tail})", flush=True)
    else:
        print("  OPENROUTER_API_KEY: NOT set for this process", flush=True)

    model = os.getenv("OPENROUTER_MODEL", "").strip() or "(default openai/gpt-4o-mini)"
    print(f"  OPENROUTER_MODEL: {model}", flush=True)

    n = len(EXPERT_IDS)
    print(f"  experts: {EXPERT_IDS}  (N={n})", flush=True)
    for i in range(n):
        p = BASE_PORT + i
        print(f"  worker port would be: 127.0.0.1:{p} ({EXPERT_IDS[i]})", flush=True)

    try:
        import hdbscan  # noqa: F401
        import numpy  # noqa: F401
        from sentence_transformers import SentenceTransformer  # noqa: F401

        print("  semantic extras [semantic]: OK (hdbscan, numpy, sentence-transformers importable)", flush=True)
    except ImportError as e:
        print(f"  semantic extras [semantic]: NOT importable ({e})", flush=True)
        print("    (Only needed if you enable semantic equivalence on the dashboard.)", flush=True)

    if not key:
        print("", flush=True)
        print(
            "Fix: add OPENROUTER_API_KEY to one of the .env paths above, or export it in this shell, "
            "then re-run. Restart the network monitor after editing .env.",
            file=sys.stderr,
            flush=True,
        )
        return 1
    return 0


def main() -> None:
    global _llm

    parser = argparse.ArgumentParser(description="Aegean simple_cluster (HTTP workers + OpenRouter)")
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="Print OpenRouter / .env / port diagnostics (no LLM run) and exit",
    )
    args = parser.parse_args()
    if args.check_env:
        raise SystemExit(check_env())

    _load_dotenv()

    if len(EXPERT_IDS) < 3:
        raise SystemExit("Aegean needs at least 3 experts.")
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        print(
            "OPENROUTER_API_KEY not visible to this process. Put it in multi-agentic-bft/.env, "
            "or export it in the same terminal/IDE session (restart after changing system env). "
            "See https://openrouter.ai/",
            file=sys.stderr,
        )
        print("Tip: run  python examples/simple_cluster.py --check-env  for file paths.", file=sys.stderr)
        sys.exit(1)

    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip() or "openai/gpt-4o-mini"
    _llm = OpenRouterAgent(model=model, timeout_s=120.0)

    aegean_cfg = AegeanConfig(
        max_rounds=8,
        alpha=2,
        beta=2,
        early_termination=True,
        session_trace=VERBOSE,
    )
    session_id = "simple-cluster"
    bus = EventBus()

    servers: list[HTTPServer] = []
    threads: list[threading.Thread] = []

    for i, _eid in enumerate(EXPERT_IDS):
        port = BASE_PORT + i
        httpd = HTTPServer(("127.0.0.1", port), ClusterRequestHandler)
        servers.append(httpd)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        threads.append(t)
        t.start()

    time.sleep(0.2)

    endpoints = {eid: f"127.0.0.1:{BASE_PORT + i}" for i, eid in enumerate(EXPERT_IDS)}
    agents = http_agents_from_endpoints(endpoints, execute_path="/execute", timeout_s=120.0)

    if VERBOSE:
        print("", flush=True)
        print("  " + "=" * 60, flush=True)
        print("  simple_cluster  |  model:", model, flush=True)
        print("  experts:", ", ".join(EXPERT_IDS), " ports:", f"{BASE_PORT}+", flush=True)
        prev, tn = _text_preview(SESSION_TASK.get("description", ""), 200)
        print(f"  task ({tn} chars): {prev!r}", flush=True)
        print("  " + "=" * 60, flush=True)
        print("", flush=True)

    try:
        result = run_aegean_session(
            {
                "session_id": session_id,
                "pattern": "aegean",
                "experts": list(EXPERT_IDS),
                "task": SESSION_TASK,
            },
            agents,
            config=aegean_cfg,
            event_bus=bus,
        )
        print(
            f"  DONE  consensus={result.consensus_reached}  {result.termination_reason!r}  {result.consensus_value!r}",
            flush=True,
        )
    finally:
        for httpd in servers:
            httpd.shutdown()
        for t in threads:
            t.join(timeout=5.0)


if __name__ == "__main__":
    main()
