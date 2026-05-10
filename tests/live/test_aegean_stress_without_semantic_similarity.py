"""Live stress tests **without** semantic similarity (no SAS / embedding-based ``alpha_same``).

These are **live** integration-style runs: real coordinator, election, Soln/Refm rounds, threading,
and ``EventBus`` — not static fixtures or single-function unit tests. Mocks stand in for model I/O
but the full session graph executes. Heavier cases also carry ``stress`` (``pytest -m "live and stress"``).

Runs are skipped by default (``addopts`` excludes ``live``). Execute with ``pytest -m live`` (optionally
``tests/live``). For a single command that runs unit + live tests, use ``pytest --override-ini addopts=``.
"""

from __future__ import annotations

import concurrent.futures

import pytest

from aegean import AegeanConfig, EventBus, create_aegean_protocol, max_failstop_faults_allowed
from aegean_test_utils import MockAgent, create_test_config

pytestmark = pytest.mark.live


def _happy_agents(experts: list[str], *, tokens: int = 1) -> dict[str, MockAgent]:
    return {
        e: MockAgent(e, proposal_output="ok", vote_output="ok", refm_output="ok", tokens_used=tokens)
        for e in experts
    }


def _run_happy_session(
    *,
    session_id: str,
    experts: list[str],
    f: int = 0,
    max_rounds: int = 6,
    beta: int = 1,
    alpha: int = 2,
) -> None:
    protocol = create_aegean_protocol(
        config=AegeanConfig(
            max_rounds=max_rounds,
            beta=beta,
            alpha=alpha,
            byzantine_tolerance=f,
            early_termination=True,
        ),
        event_bus=EventBus(),
    )
    cfg = create_test_config(experts, session_id=session_id)
    r = protocol.execute(cfg, _happy_agents(experts))
    assert r["ok"] is True, r.get("error")
    assert r["value"].consensus_reached is True


def test_stress_without_semantic_similarity_sequential_happy_burst():
    """Many back-to-back commits with fresh protocol instances (no shared state)."""
    for i in range(24):
        experts = [f"s{i}-a{j}" for j in range(3)]
        _run_happy_session(session_id=f"burst-{i}", experts=experts, f=0, max_rounds=5, beta=1)


def test_stress_without_semantic_similarity_concurrent_isolated_sessions():
    """Parallel sessions each with its own bus/protocol/agents — catches accidental globals."""

    def worker(worker_id: int) -> None:
        n = 5
        f = 1
        experts = [f"w{worker_id}-e{k}" for k in range(n)]
        _run_happy_session(
            session_id=f"conc-{worker_id}",
            experts=experts,
            f=f,
            max_rounds=5,
            beta=1,
            alpha=3,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(worker, range(6)))


def test_stress_without_semantic_similarity_large_ensemble_max_f():
    """Large N with largest legal f; single happy-path commit."""
    n = 17
    f = max_failstop_faults_allowed(n)
    experts = [f"L-{k}" for k in range(n)]
    _run_happy_session(session_id="large-ensemble", experts=experts, f=f, max_rounds=8, beta=1)


def test_stress_without_semantic_similarity_max_rounds_exhaustion_no_commit():
    """Deep refinement without early commit — must terminate cleanly via max_rounds."""
    max_refm = 22
    protocol = create_aegean_protocol(
        config=AegeanConfig(
            max_rounds=max_refm,
            early_termination=False,
            alpha=3,
            beta=2,
        ),
        event_bus=EventBus(),
    )
    experts = [f"d{k}" for k in range(3)]
    agents = {
        "d0": MockAgent("d0", proposal_output="p", vote_output="p", refm_output="a"),
        "d1": MockAgent("d1", proposal_output="p", vote_output="p", refm_output="b"),
        "d2": MockAgent("d2", proposal_output="p", vote_output="p", refm_output="c"),
    }
    r = protocol.execute(create_test_config(experts, session_id="deep-cap"), agents)
    assert r["ok"] is True
    out = r["value"]
    assert out.consensus_reached is False
    assert out.termination_reason == "max_rounds"
    assert out.total_rounds == 1 + max_refm


@pytest.mark.stress
def test_stress_without_semantic_similarity_heavy_sequential_burst():
    for i in range(120):
        experts = [f"H{i}-x{j}" for j in range(3)]
        _run_happy_session(session_id=f"heavy-{i}", experts=experts, f=0, max_rounds=5, beta=1)


@pytest.mark.stress
def test_stress_without_semantic_similarity_heavy_concurrent_sessions():
    def worker(worker_id: int) -> None:
        n = 7
        f = 2
        experts = [f"HW{worker_id}-{k}" for k in range(n)]
        _run_happy_session(
            session_id=f"heavy-conc-{worker_id}",
            experts=experts,
            f=f,
            max_rounds=6,
            beta=1,
            alpha=4,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=14) as pool:
        list(pool.map(worker, range(14)))


@pytest.mark.stress
def test_stress_without_semantic_similarity_very_large_ensemble():
    n = 25
    f = max_failstop_faults_allowed(n)
    experts = [f"V-{k}" for k in range(n)]
    _run_happy_session(session_id="very-large", experts=experts, f=f, max_rounds=10, beta=1)
