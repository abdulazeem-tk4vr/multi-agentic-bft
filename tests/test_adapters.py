import json

from aegean.adapters import HttpAgent, OpenRouterAgent


class _Resp:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


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
