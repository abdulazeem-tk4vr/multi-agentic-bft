"""Paper-aligned proof / invariant smoke (Lemma-style).

Coordinator integration checks: refinement **validity** (committed value drawn from prior **R̄**),
**single commit** per successful run, **leader-attributed** certificate, bounded **termination**,
supporting agents vs quorum. Not a substitute for full formal verification.
"""

from __future__ import annotations

from typing import Any

import pytest

from aegean import AegeanConfig, EventBus, create_aegean_protocol
from aegean.helpers_utils import select_leader
from aegean.types import AegeanRound

from aegean_test_utils import MockAgent, create_test_config


def _prior_refinement_set_for_ref_round(rounds: list[AegeanRound], ref_round: int) -> list[Any]:
    """``Proposal.value`` at the start of refinement round ``ref_round`` is **R̄_prev** for that engine step."""
    for ar in rounds:
        if ar.round_number == ref_round and ar.phase in ("refinement", "voting") and ar.proposal is not None:
            v = ar.proposal.value
            return list(v) if isinstance(v, list) else [v]
    return []


def _converged_event_count(bus: EventBus) -> int:
    return sum(
        1
        for e in bus.emitted_events
        if e.get("topic") == "protocol.iteration"
        and e.get("payload", {}).get("status") == "converged"
    )


@pytest.mark.parametrize("beta", [1, 2])
def test_lemma2_committed_value_in_prior_refinement_set(beta: int):
    """Lemma 2-style: committed value is drawn from the prior round's advertised refinement set (R̄)."""
    bus = EventBus()
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=5, beta=beta, alpha=2, early_termination=True),
        event_bus=bus,
    )
    experts = ["a1", "a2", "a3"]
    cfg = create_test_config(experts)
    val = "artifact"
    agents = {e: MockAgent(e, proposal_output=val, refm_output=val) for e in experts}
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    out = r["value"]
    assert out.consensus_reached is True
    cert = out.commit_certificate
    assert cert is not None
    prior = _prior_refinement_set_for_ref_round(out.rounds, cert.refinement_round)
    assert prior, "expected voting round proposal carrying prior R̄"
    assert cert.committed_value in prior


def test_lemma1_at_most_one_converged_and_single_certificate():
    """Lemma 1-style: one refinement decision/commit per execute; coordinator does not double-commit."""
    bus = EventBus()
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=4, beta=2, alpha=2),
        event_bus=bus,
    )
    cfg = create_test_config(["a1", "a2", "a3"])
    val = "one"
    agents = {e: MockAgent(e, proposal_output=val, refm_output=val) for e in ["a1", "a2", "a3"]}
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    out = r["value"]
    assert out.consensus_reached
    assert out.commit_certificate is not None
    assert _converged_event_count(bus) <= 1


def test_lemma1_certificate_leader_matches_all_round_leaders():
    """Committed output is attributed to the session leader (only leader issues certificate metadata)."""
    experts = ["b1", "b2", "b3"]
    cfg = create_test_config(experts)
    leader = select_leader(experts, 0)
    protocol = create_aegean_protocol(AegeanConfig(max_rounds=3, beta=1, alpha=2), event_bus=EventBus())
    v = "L"
    agents = {e: MockAgent(e, proposal_output=v, refm_output=v) for e in experts}
    r = protocol.execute(cfg, agents)
    assert r["ok"] and r["value"].consensus_reached
    cert = r["value"].commit_certificate
    assert cert is not None
    assert cert.leader_id == leader
    for ar in r["value"].rounds:
        assert ar.leader_id == leader
    assert cert.leader_id == leader


def test_lemma3_explicit_termination_reason_under_healthy_mocks():
    """Lemma 3-style smoke: run halts with a known termination label (no silent hang)."""
    protocol = create_aegean_protocol(AegeanConfig(max_rounds=3, beta=1), event_bus=EventBus())
    cfg = create_test_config(["a1", "a2", "a3"])
    agents = {e: MockAgent(e, proposal_output="h", refm_output="h") for e in ["a1", "a2", "a3"]}
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    out = r["value"]
    assert out.termination_reason in (
        "consensus",
        "max_rounds",
        "timeout",
        "error",
        "byzantine_failure",
    )
    assert out.total_duration_ms >= 0


def test_certificate_supporting_agents_subset_and_quorum_size():
    protocol = create_aegean_protocol(AegeanConfig(max_rounds=2, beta=1), event_bus=EventBus())
    cert = protocol.execute(
        create_test_config(["a1", "a2", "a3"]),
        {e: MockAgent(e, proposal_output="q", refm_output="q") for e in ["a1", "a2", "a3"]},
    )["value"].commit_certificate
    assert cert is not None
    experts = {"a1", "a2", "a3"}
    assert set(cert.supporting_refm_agent_ids) <= experts
    assert len(cert.supporting_refm_agent_ids) >= cert.quorum_size_r


def test_recovery_leader_id_on_certificate():
    """After NewTerm recovery, certificate leader matches configured recovery leader."""
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["recovery"] = {
        "leader_id": "a2",
        "acks": [
            {"term": 9, "agent_id": "a1", "refm_set": ["u", "u", "u"], "round_num": 1},
            {"term": 9, "agent_id": "a2", "refm_set": ["u", "u", "u"], "round_num": 1},
        ],
    }
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=3, beta=1, alpha=2, early_termination=True),
        event_bus=EventBus(),
    )
    agents = {
        e: MockAgent(e, proposal_output="u", vote_output="u", refm_output="u")
        for e in ["a1", "a2", "a3"]
    }
    r = protocol.execute(cfg, agents)
    assert r["ok"] and r["value"].consensus_reached
    cert = r["value"].commit_certificate
    assert cert is not None
    assert cert.leader_id == "a2"
    assert cert.term_num == 9
