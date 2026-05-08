"""Election stall: bump term and retry RequestVote/Vote until quorum or ``max_election_attempts``."""

from __future__ import annotations

from aegean import AegeanConfig, EventBus, create_aegean_protocol

from aegean_test_utils import MockAgent, create_test_config


def test_election_stall_bumps_term_until_rv_vote_quorum():
    """Persisted local terms at 2 deny RequestVote at term 1; term 3 succeeds (strictly higher)."""
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=2, beta=1, alpha=2, max_election_attempts=16),
        event_bus=EventBus(),
    )
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["election_initial_terms"] = {"a1": 2, "a2": 2, "a3": 2}
    val = "ok"
    agents = {e: MockAgent(e, proposal_output=val, refm_output=val) for e in ("a1", "a2", "a3")}
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    out = r["value"]
    assert out.consensus_reached is True
    cert = out.commit_certificate
    assert cert is not None
    assert cert.term_num == 3


def test_election_exhausts_attempts_without_quorum():
    """Local terms stay at 100; candidate never reaches a winning term within attempt budget."""
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_election_attempts=5),
        event_bus=EventBus(),
    )
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["election_initial_terms"] = {"a1": 100, "a2": 100, "a3": 100}
    cfg["max_election_attempts"] = 4
    agents = {e: MockAgent(e, proposal_output="x", refm_output="x") for e in ("a1", "a2", "a3")}
    r = protocol.execute(cfg, agents)
    assert r["ok"] is False
    assert "election" in r["error"].lower() or "term" in r["error"].lower()
    assert "4" in r["error"] or "attempt" in r["error"].lower()
