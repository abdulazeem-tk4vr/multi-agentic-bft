from __future__ import annotations

import io
import socketserver
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NM_ROOT = ROOT / "network-monitor"
if str(NM_ROOT) not in sys.path:
    sys.path.insert(0, str(NM_ROOT))

from network_monitor.runner import _parse_spec
from network_monitor.tcp_session import TcpSessionClient, read_frame, write_frame


def _base_spec(transport: str) -> dict[str, object]:
    return {
        "session_id": "tcp-test",
        "n_agents": 3,
        "task_id": "t1",
        "task_description": "x",
        "openrouter_base_port": 18700,
        "transport": transport,
        "max_rounds": 5,
        "alpha": 2,
        "beta": 2,
        "byzantine_tolerance": 0,
        "confidence_threshold": 0.7,
        "round_timeout_ms": 60000,
        "session_trace": False,
        "max_election_attempts": 32,
    }


def test_tcp_frame_roundtrip_memory_buffer():
    buff = io.BytesIO()
    payload = {"msg_id": "abc", "payload": {"ok": True, "value": 1}}
    write_frame(buff, payload)
    buff.seek(0)
    out = read_frame(buff)
    assert out == payload


def test_parse_spec_accepts_tcp_transport():
    experts, task, cfg, base_port, transport = _parse_spec(_base_spec("tcp"))
    assert len(experts) == 3
    assert task["id"] == "t1"
    assert base_port == 18700
    assert cfg.max_rounds == 5
    assert transport == "tcp"


def test_tcp_session_client_request_response():
    class _Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            req = read_frame(self.rfile)
            resp = {
                "session_id": req["session_id"],
                "msg_id": req["msg_id"],
                "type": "execute.result",
                "agent_id": req.get("agent_id", "a1"),
                "term": req.get("term", 0),
                "round": req.get("round", 0),
                "payload": {"ok": True, "value": {"output": "ok", "metadata": {"tokens_used": 1}}},
            }
            write_frame(self.wfile, resp)

    class _Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    server = _Server(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    host, port = server.server_address
    client = TcpSessionClient(host, int(port), session_id="s1", agent_id="a1", timeout_s=5.0)
    try:
        out = client.request(
            message_type="execute",
            term=1,
            round_num=0,
            payload={"task": {"id": "x", "context": {}}},
        )
        assert out["payload"]["ok"] is True
        assert out["payload"]["value"]["output"] == "ok"
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        t.join(timeout=2.0)
