from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import time

from aegean.task_routing import PHASE_REFM, aegean_task_phase


class MockAgent:
    def __init__(
        self,
        agent_id: str,
        proposal_output: Any = "Proposal",
        vote_output: str = "ACCEPT",
        *,
        refm_output: Any | None = None,
        delay_ms: int = 0,
        fail: bool = False,
        tokens_used: int = 50,
        confidence: float | None = None,
    ):
        self.id = agent_id
        self.proposal_output = proposal_output
        self.vote_output = vote_output
        self.refm_output = vote_output if refm_output is None else refm_output
        self.delay_ms = delay_ms
        self.fail = fail
        self.tokens_used = tokens_used
        self.confidence = confidence
        self.execute_calls = 0

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        self.execute_calls += 1
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)
        if self.fail:
            return {"ok": False, "error": "Agent execution failed"}
        if aegean_task_phase(task) == PHASE_REFM:
            output: Any = self.refm_output
        elif str(task.get("id", "")).startswith("vote-"):
            output = self.vote_output
        else:
            output = self.proposal_output
        meta: dict[str, Any] = {"tokens_used": self.tokens_used}
        if self.confidence is not None:
            meta["confidence"] = self.confidence
        return {"ok": True, "value": {"output": output, "metadata": meta}}


def create_test_config(experts: list[str], session_id: str = "aegean-e2e") -> dict[str, Any]:
    return {
        "session_id": session_id,
        "pattern": "aegean",
        "experts": experts,
        "task": {"id": "task-1", "description": "E2E test task for Aegean consensus", "context": {}},
    }


def was_consensus_reached(result: dict[str, Any]) -> bool:
    if not result.get("ok", False):
        return False
    return bool(result["value"].consensus_reached)


@dataclass
class AlternatingVoteAgent:
    id: str
    proposal_output: Any = "Byzantine proposal"
    tokens_used: int = 25
    call_count: int = 0

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        if aegean_task_phase(task) == PHASE_REFM:
            vote = "ACCEPT" if self.call_count % 2 == 0 else "REJECT"
            return {"ok": True, "value": {"output": vote, "metadata": {"tokens_used": self.tokens_used}}}
        if str(task.get("id", "")).startswith("vote-"):
            vote = "ACCEPT" if self.call_count % 2 == 0 else "REJECT"
            return {"ok": True, "value": {"output": vote, "metadata": {"tokens_used": self.tokens_used}}}
        return {
            "ok": True,
            "value": {"output": self.proposal_output, "metadata": {"tokens_used": self.tokens_used}},
        }
