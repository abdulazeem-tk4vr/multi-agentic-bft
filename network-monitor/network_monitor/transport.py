"""Session transport abstractions for monitor runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .tcp_session import TcpSessionClient


@dataclass(frozen=True)
class ExecuteContext:
    session_id: str
    phase: str
    round_num: int
    term_num: int
    agent_id: str


class SessionAgentTransport(Protocol):
    def execute(self, task_d: dict[str, Any], *, ctx: ExecuteContext) -> dict[str, Any]: ...

    def close(self) -> None: ...


class TcpSessionTransport:
    """Persistent TCP transport for one worker endpoint."""

    def __init__(self, host: str, port: int, *, session_id: str, agent_id: str, timeout_s: float = 120.0) -> None:
        self._client = TcpSessionClient(
            host,
            port,
            session_id=session_id,
            agent_id=agent_id,
            timeout_s=timeout_s,
        )

    def execute(self, task_d: dict[str, Any], *, ctx: ExecuteContext) -> dict[str, Any]:
        out = self._client.request(
            message_type="execute",
            term=ctx.term_num,
            round_num=ctx.round_num,
            payload={"task": task_d, "phase": ctx.phase},
        )
        result = out.get("payload", out)
        if not isinstance(result, dict):
            return {"ok": False, "error": "invalid tcp payload"}
        return result

    def close(self) -> None:
        self._client.close()

