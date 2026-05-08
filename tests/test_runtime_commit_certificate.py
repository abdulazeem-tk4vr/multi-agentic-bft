"""Runtime: ``round_timeout_ms``, ``confidence_threshold``, and ``CommitCertificate`` on consensus."""

from __future__ import annotations

from aegean import AegeanConfig, EventBus, create_aegean_protocol

from aegean_test_utils import MockAgent, create_test_config


def test_round_timeout_sets_termination_timeout_when_no_consensus():
    experts = ["a1", "a2", "a3"]
    cfg = create_test_config(experts)
    # Wall-clock Soln round budget is 30ms; stragglers exceed it while leader finishes.
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=2, beta=1, round_timeout_ms=30),
        event_bus=EventBus(),
    )
    agents = {
        "a1": MockAgent("a1", proposal_output="p", delay_ms=0),
        "a2": MockAgent("a2", proposal_output="p", delay_ms=200),
        "a3": MockAgent("a3", proposal_output="p", delay_ms=200),
    }
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    v = r["value"]
    assert v.consensus_reached is False
    assert v.termination_reason == "timeout"
    assert v.commit_certificate is None


def test_commit_certificate_on_success():
    experts = ["a1", "a2", "a3"]
    cfg = create_test_config(experts)
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=4, beta=2, alpha=2, confidence_threshold=0.5),
        event_bus=EventBus(),
    )
    same = "final-answer"
    agents = {e: MockAgent(e, proposal_output=same, refm_output=same) for e in experts}
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    out = r["value"]
    assert out.consensus_reached is True
    assert out.termination_reason == "consensus"
    cert = out.commit_certificate
    assert cert is not None
    assert cert.term_num == 1
    assert cert.refinement_round >= 1
    assert cert.leader_id == "a1"
    assert cert.committed_value == same
    assert cert.quorum_size_r == 3
    assert cert.alpha == 2 and cert.beta == 2
    assert set(cert.supporting_refm_agent_ids) == set(experts)


def test_low_confidence_excludes_slots_from_quorum():
    """Below-threshold confidence yields non-accept rows; R=3 cannot form."""
    experts = ["a1", "a2", "a3"]
    cfg = create_test_config(experts)
    protocol = create_aegean_protocol(
        config=AegeanConfig(
            max_rounds=2,
            beta=1,
            confidence_threshold=0.99,
            round_timeout_ms=60000,
        ),
        event_bus=EventBus(),
    )
    agents = {
        "a1": MockAgent("a1", proposal_output="x", refm_output="x", confidence=1.0),
        "a2": MockAgent("a2", proposal_output="x", refm_output="x", confidence=0.5),
        "a3": MockAgent("a3", proposal_output="x", refm_output="x", confidence=0.5),
    }
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    v = r["value"]
    assert v.consensus_reached is False
    assert v.commit_certificate is None
