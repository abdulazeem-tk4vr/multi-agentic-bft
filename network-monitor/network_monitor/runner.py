"""Execute one dashboard session from POST spec."""

from __future__ import annotations

import dataclasses
import json
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable

from aegean import AegeanConfig, AegeanRunner, http_agents_from_endpoints
from aegean.adapters import OpenRouterAgent
from aegean.types import calculate_quorum_size, validate_failstop_fault_bound

from .tcp_session import read_frame, write_frame
from .transport import ExecuteContext, SessionAgentTransport, TcpSessionTransport


class AgentRecoveryStore:
    """Thread-safe per-agent RefmSet snapshot store for NewTermAck provider."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_agent: dict[str, tuple[int, int, list[Any]]] = {}

    def observe_task(self, task_d: dict[str, Any]) -> None:
        bag = (task_d.get("context") or {}).get("aegean") or {}
        if str(bag.get("phase", "")).strip().lower() != "refm":
            return
        agent_id = str(bag.get("agent_id", "")).strip()
        if not agent_id:
            return
        raw_refm = bag.get("refinement_set")
        if not isinstance(raw_refm, list):
            return
        try:
            term_num = int(bag.get("term_num", 0))
            round_num = int(bag.get("round_num", 0))
        except (TypeError, ValueError):
            return
        snap = list(raw_refm)
        with self._lock:
            cur = self._by_agent.get(agent_id)
            if cur is None or (term_num, round_num) >= (cur[0], cur[1]):
                self._by_agent[agent_id] = (term_num, round_num, snap)

    def ack_rows(self, experts: list[str], term_num: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._lock:
            for eid in experts:
                cur = self._by_agent.get(eid)
                if cur is None:
                    rows.append(
                        {
                            "term": int(term_num),
                            "agent_id": eid,
                            "round_num": 0,
                            "refm_bottom": True,
                        }
                    )
                    continue
                rows.append(
                    {
                        "term": int(cur[0]),
                        "agent_id": eid,
                        "round_num": int(cur[1]),
                        "refm_set": list(cur[2]),
                    }
                )
        return rows


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


def _parse_spec(data: dict[str, Any]) -> tuple[list[str], dict[str, Any], AegeanConfig, int, str]:
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
    transport = str(data.get("transport", "http")).strip().lower() or "http"
    if transport not in {"http", "tcp"}:
        raise ValueError("transport must be 'http' or 'tcp'")
    return experts, task, cfg, base_port, transport


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
    experts, task, aegean_cfg, base_port, transport = _parse_spec(spec)
    session_id = (spec.get("session_id") or "dashboard").strip() or "dashboard"
    quorum_r = calculate_quorum_size(len(experts), aegean_cfg.byzantine_tolerance)
    viz.configure(experts=experts, session_id=session_id, quorum_r=quorum_r)
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        raise ValueError("OPENROUTER_API_KEY not set (add to .env or environment)")
    _run_openrouter(
        viz,
        experts,
        session_id,
        task,
        aegean_cfg,
        base_port,
        transport=transport,
        on_cancel_ready=on_cancel_ready,
    )


def _run_openrouter(
    viz: Any,
    experts: list[str],
    session_id: str,
    task: dict[str, Any],
    aegean_cfg: AegeanConfig,
    base_port: int,
    *,
    transport: str,
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
    recovery_store = AgentRecoveryStore()

    def execute(task_d: dict[str, Any]) -> dict[str, Any]:
        return ctx.llm.execute(task_d)

    def execute_traced(task_d: dict[str, Any]) -> dict[str, Any]:
        recovery_store.observe_task(task_d)
        out = execute(task_d)
        _trace_worker(ctx.viz, task_d, out)
        return out

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
                out = execute_traced(t)
            b = json.dumps(out).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    class TcpHandler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            while True:
                try:
                    req = read_frame(self.rfile)
                except EOFError:
                    return
                except Exception:
                    return
                msg_id = str(req.get("msg_id", ""))
                payload = req.get("payload")
                if not isinstance(payload, dict):
                    resp_payload: dict[str, Any] = {"ok": False, "error": "bad payload"}
                else:
                    task_obj = payload.get("task")
                    if not isinstance(task_obj, dict):
                        resp_payload = {"ok": False, "error": "bad task"}
                    else:
                        resp_payload = execute_traced(task_obj)
                resp = {
                    "session_id": req.get("session_id", session_id),
                    "msg_id": msg_id,
                    "type": "execute.result",
                    "agent_id": req.get("agent_id", ""),
                    "term": req.get("term", 0),
                    "round": req.get("round", 0),
                    "payload": resp_payload,
                }
                try:
                    write_frame(self.wfile, resp)
                except Exception:
                    return

    class ThreadedTcpServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    servers: list[HTTPServer] = []
    threads: list[threading.Thread] = []
    tcp_servers: list[ThreadedTcpServer] = []
    tcp_threads: list[threading.Thread] = []
    tcp_clients: list[TcpSessionTransport] = []
    for i, _eid in enumerate(experts):
        port = base_port + i
        httpd = HTTPServer(("127.0.0.1", port), Handler)
        servers.append(httpd)
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        threads.append(th)
        th.start()
        tcpd = ThreadedTcpServer(("127.0.0.1", port + 1000), TcpHandler)
        tcp_servers.append(tcpd)
        tth = threading.Thread(target=tcpd.serve_forever, daemon=True)
        tcp_threads.append(tth)
        tth.start()
    time.sleep(0.2)

    endpoints = {eid: f"127.0.0.1:{base_port + i}" for i, eid in enumerate(experts)}
    if transport == "http":
        agents = http_agents_from_endpoints(endpoints, execute_path="/execute", timeout_s=120.0)
    else:
        class _TcpAgent:
            def __init__(self, eid: str, client: SessionAgentTransport) -> None:
                self._eid = eid
                self._client = client

            def execute(self, task_d: dict[str, Any]) -> dict[str, Any]:
                bag = (task_d.get("context") or {}).get("aegean") or {}
                phase = str(bag.get("phase", "?"))
                round_num = int(bag.get("round_num", 0))
                term_num = int(bag.get("term_num", 0))
                try:
                    return self._client.execute(
                        task_d,
                        ctx=ExecuteContext(
                            session_id=session_id,
                            phase=phase,
                            round_num=round_num,
                            term_num=term_num,
                            agent_id=self._eid,
                        ),
                    )
                except Exception as exc:  # noqa: BLE001
                    viz.bus.emit(
                        "transport.error",
                        {
                            "transport": "tcp",
                            "agent_id": self._eid,
                            "phase": phase,
                            "round": round_num,
                            "error": str(exc),
                        },
                        session_id=session_id,
                    )
                    return {"ok": False, "error": f"tcp transport error: {exc}"}

        agents = {}
        for i, eid in enumerate(experts):
            client = TcpSessionTransport("127.0.0.1", base_port + i + 1000, session_id=session_id, agent_id=eid)
            tcp_clients.append(client)
            agents[eid] = _TcpAgent(eid, client)
    viz.bus.emit(
        "transport.started",
        {"transport": transport, "worker_count": len(experts)},
        session_id=session_id,
    )
    runner = AegeanRunner(config=aegean_cfg, event_bus=viz.bus)
    cancelled = threading.Event()

    def cancel_run() -> None:
        if cancelled.is_set():
            return
        cancelled.set()
        runner.cancel("cancelled by dashboard user")
        for client in tcp_clients:
            try:
                client.close()
            except Exception:
                pass
        for httpd in servers:
            try:
                httpd.shutdown()
            except Exception:
                pass
        for tcpd in tcp_servers:
            try:
                tcpd.shutdown()
            except Exception:
                pass

    if on_cancel_ready is not None:
        on_cancel_ready(cancel_run)
    try:
        def _new_term_ack_provider(experts_in: list[str], term_num: int, _leader_id: str) -> list[dict[str, Any]]:
            return recovery_store.ack_rows(experts_in, term_num)

        result = runner.run(
            {
                "session_id": session_id,
                "pattern": "aegean",
                "experts": experts,
                "task": task,
                "new_term_ack_provider": _new_term_ack_provider,
            },
            agents,
        )
        viz.finalize(result)
    finally:
        for client in tcp_clients:
            client.close()
        for httpd in servers:
            httpd.shutdown()
        for tcpd in tcp_servers:
            tcpd.shutdown()
        for th in threads:
            th.join(timeout=5.0)
        for tth in tcp_threads:
            tth.join(timeout=5.0)
        viz.bus.emit(
            "transport.stopped",
            {"transport": transport, "cancelled": cancelled.is_set()},
            session_id=session_id,
        )
