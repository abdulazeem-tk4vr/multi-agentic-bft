from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..logutil import get_aegean_logger
from ..task_routing import PHASE_REFM, aegean_task_phase

_log = get_aegean_logger("scripted_agent_mock")


class ScriptedAegeanAgent:
    """Deterministic mock agent for demos and tests.

    It returns fixed values (or callable-derived values) for soln/refm phases
    and follows the exact ``execute(task)`` result shape expected by protocol.
    """

    __slots__ = ("_refm", "_soln", "_tokens_refm", "_tokens_soln")

    def __init__(
        self,
        *,
        soln: Any | Callable[[dict[str, Any]], Any] = "mock-soln",
        refm: Any | Callable[[dict[str, Any]], Any] = "mock-refm",
        tokens_soln: int = 1,
        tokens_refm: int = 1,
    ) -> None:
        self._soln = soln
        self._refm = refm
        self._tokens_soln = int(tokens_soln)
        self._tokens_refm = int(tokens_refm)

    def _resolve(self, fn_or_val: Any | Callable[[dict[str, Any]], Any], task: dict[str, Any]) -> Any:
        return fn_or_val(task) if callable(fn_or_val) else fn_or_val

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        phase = aegean_task_phase(task)
        if phase == PHASE_REFM:
            out = self._resolve(self._refm, task)
            tokens = self._tokens_refm
        else:
            out = self._resolve(self._soln, task)
            tokens = self._tokens_soln
        _log.debug("scripted mock agent task_id=%s phase=%s", task.get("id"), phase)
        return {"ok": True, "value": {"output": out, "metadata": {"tokens_used": tokens}}}
