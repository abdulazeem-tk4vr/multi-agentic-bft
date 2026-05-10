import json

from aegean import build_refm_task
from aegean.adapters import (
    HttpAgent,
    OpenRouterAgent,
    http_agents_from_endpoints,
    normalize_agent_endpoint,
)


class _Resp:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_normalize_agent_endpoint_host_port():
    assert normalize_agent_endpoint("10.0.0.5:9000") == "http://10.0.0.5:9000/execute"
    assert normalize_agent_endpoint("http://192.168.1.1") == "http://192.168.1.1/execute"


def test_normalize_agent_endpoint_preserves_custom_path():
    assert (
        normalize_agent_endpoint("https://worker.example.com/v1/aegean")
        == "https://worker.example.com/v1/aegean"
    )


def test_http_agents_from_endpoints_builds_map():
    m = http_agents_from_endpoints({"a1": "127.0.0.1:1", "a2": "http://127.0.0.1:2/custom"}, execute_path="/run")
    assert m["a1"].endpoint == "http://127.0.0.1:1/run"
    assert m["a2"].endpoint == "http://127.0.0.1:2/custom"


def test_http_agent_happy_path(monkeypatch):
    def _fake_urlopen(req, timeout):
        assert req.full_url == "http://agent.local/execute"
        assert timeout == 5.0
        return _Resp({"ok": True, "value": {"output": "hello", "metadata": {"tokens_used": 3}}})

    monkeypatch.setattr("aegean.adapters.http_agent.urlopen", _fake_urlopen)

    agent = HttpAgent(endpoint="http://agent.local/execute", timeout_s=5.0)
    out = agent.execute({"id": "t1", "description": "x", "context": {}})
    assert out["ok"] is True
    assert out["value"]["output"] == "hello"


def test_openrouter_agent_happy_path(monkeypatch):
    def _fake_urlopen(req, timeout):
        assert timeout == 12.0
        body = json.loads(req.data.decode("utf-8"))
        assert body["model"] == "openrouter/test-model"
        return _Resp(
            {
                "choices": [{"message": {"content": "final-answer"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            }
        )

    monkeypatch.setattr("aegean.adapters.openrouter_agent.urlopen", _fake_urlopen)

    agent = OpenRouterAgent(model="openrouter/test-model", api_key="k", timeout_s=12.0)
    out = agent.execute({"id": "t1", "description": "Solve this", "context": {}})
    assert out["ok"] is True
    assert out["value"]["output"] == "final-answer"
    assert out["value"]["metadata"]["tokens_used"] == 20


def test_openrouter_agent_requires_api_key():
    agent = OpenRouterAgent(model="openrouter/test-model", api_key="")
    out = agent.execute({"id": "t1", "description": "x", "context": {}})
    assert out["ok"] is False
    assert "API_KEY" in out["error"]


def test_openrouter_refm_user_message_does_not_duplicate_refinement_set(monkeypatch):
    """R̄ must appear once in the chat user text — not in ``description`` and again as a peer block."""

    marker = "UNIQUE_RBAR_TOKEN_FOR_DEDUPE_TEST"

    def _fake_urlopen(req, timeout):
        body = json.loads(req.data.decode("utf-8"))
        user = body["messages"][1]["content"]
        assert user.count(marker) == 1, f"expected single R̄ copy in user message, got {user.count(marker)}"
        return _Resp(
            {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"total_tokens": 1},
            }
        )

    monkeypatch.setattr("aegean.adapters.openrouter_agent.urlopen", _fake_urlopen)
    base = {"id": "root", "description": "Original question", "context": {}}
    task = build_refm_task(
        base,
        refinement_set=[marker, {"k": "v"}],
        term_num=1,
        round_num=2,
        agent_id="a1",
    )
    agent = OpenRouterAgent(model="openrouter/test-model", api_key="k")
    out = agent.execute(task)
    assert out["ok"] is True
