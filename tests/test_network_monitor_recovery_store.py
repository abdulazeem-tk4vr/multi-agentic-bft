from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NM_ROOT = ROOT / "network-monitor"
if str(NM_ROOT) not in sys.path:
    sys.path.insert(0, str(NM_ROOT))

from network_monitor.runner import AgentRecoveryStore


def _task_refm(agent_id: str, term_num: int, round_num: int, refm_set: list[str]) -> dict:
    return {
        "id": "t",
        "description": "x",
        "context": {
            "aegean": {
                "phase": "refm",
                "agent_id": agent_id,
                "term_num": term_num,
                "round_num": round_num,
                "refinement_set": refm_set,
            }
        },
    }


def test_ack_rows_default_bottom_for_unknown_agents():
    store = AgentRecoveryStore()
    rows = store.ack_rows(["a1", "a2"], term_num=3)
    assert len(rows) == 2
    assert rows[0]["agent_id"] == "a1"
    assert rows[0]["refm_bottom"] is True
    assert rows[1]["agent_id"] == "a2"
    assert rows[1]["refm_bottom"] is True


def test_observe_task_persists_latest_term_round_snapshot():
    store = AgentRecoveryStore()
    store.observe_task(_task_refm("a1", 1, 1, ["x"]))
    store.observe_task(_task_refm("a1", 1, 2, ["y"]))
    store.observe_task(_task_refm("a1", 1, 1, ["stale"]))
    store.observe_task(_task_refm("a1", 2, 1, ["z"]))
    rows = store.ack_rows(["a1"], term_num=2)
    assert rows[0]["refm_set"] == ["z"]
    assert rows[0]["term"] == 2
    assert rows[0]["round_num"] == 1

