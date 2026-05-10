#!/usr/bin/env python3
"""Minimal coordinator entrypoint: same pattern as README "Entry script".

Run from repo root after `pip install -e ".[dev]"`:

    python examples/consensus_entry.py

Swap `agents` for `http_agents_from_endpoints({...})` to hit remote POST /execute workers.
"""

from __future__ import annotations

from aegean import AegeanConfig, EventBus, run_aegean_session
from aegean.mocks import ScriptedAegeanAgent


def main() -> None:
    experts = ["a1", "a2", "a3"]

    agents = {
        "a1": ScriptedAegeanAgent(soln="same", refm="same"),
        "a2": ScriptedAegeanAgent(soln="same", refm="same"),
        "a3": ScriptedAegeanAgent(soln="same", refm="same"),
    }

    session_cfg = {
        "session_id": "run-001",
        "pattern": "aegean",
        "experts": experts,
        "task": {
            "id": "t1",
            "description": "Your question or prompt for all agents.",
            "context": {},
        },
    }

    result = run_aegean_session(
        session_cfg,
        agents,
        config=AegeanConfig(
            max_rounds=5,
            alpha=2,
            beta=2,
            early_termination=True,
        ),
        event_bus=EventBus(),
    )

    print("consensus_reached:", result.consensus_reached)
    print("termination_reason:", result.termination_reason)
    print("consensus_value:", result.consensus_value)
    if result.commit_certificate:
        print("certificate:", result.commit_certificate)


if __name__ == "__main__":
    main()
