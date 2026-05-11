"""Adversarial / persisted **RefmSet** broadcast-round integration tests.

Uses optional ``config["refm_round_track_init"]`` to seed :class:`~aegean.refinement_state.PerAgentRefmRoundTrack`
as if each agent recovered persisted state from a prior term or run, then validates stale lower
**RefmSet** rounds are ignored (fail-stop / delivery-order robustness).
"""

from __future__ import annotations

from aegean import AegeanConfig, EventBus, create_aegean_protocol

from aegean_test_utils import MockAgent, create_test_config


def test_persisted_high_water_rejects_stale_round_one():
    """Agents already accepted RefmSet broadcast round 4; leader starts at round 1 → no Refm accept."""
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=2, beta=1, early_termination=False),
        event_bus=EventBus(),
    )
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["refm_round_track_init"] = {"a1": 4, "a2": 4, "a3": 4}
    agents = {
        "a1": MockAgent("a1", proposal_output="z", refm_output="z"),
        "a2": MockAgent("a2", proposal_output="z", refm_output="z"),
        "a3": MockAgent("a3", proposal_output="z", refm_output="z"),
    }
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    out = r["value"]
    assert out.consensus_reached is False
    assert out.termination_reason == "max_rounds"
    ref_rounds = [x.round_number for x in out.rounds if x.round_number >= 1]
    assert len(ref_rounds) >= 1
    for rnd in out.rounds:
        if rnd.round_number >= 1:
            assert rnd.quorum_status.accepts == 0


def test_mixed_persistence_partial_accepts_below_quorum():
    """One agent never passed round 0 high-water; others did → < R accepts, never commits."""
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=2, beta=1, early_termination=False),
        event_bus=EventBus(),
    )
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["refm_round_track_init"] = {"a1": 5, "a2": 5, "a3": 0}
    agents = {
        "a1": MockAgent("a1", proposal_output="p", refm_output="p"),
        "a2": MockAgent("a2", proposal_output="p", refm_output="p"),
        "a3": MockAgent("a3", proposal_output="p", refm_output="p"),
    }
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    assert r["value"].consensus_reached is False


def test_seed_matching_round_one_refines_normally():
    """Explicit init 1 matches first leader Refm broadcast (round 1); quorum and consensus hold with β=1."""
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=3, beta=1, alpha=2),
        event_bus=EventBus(),
    )
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["refm_round_track_init"] = {"a1": 1, "a2": 1, "a3": 1}
    val = "same"
    agents = {e: MockAgent(e, proposal_output=val, refm_output=val) for e in ["a1", "a2", "a3"]}
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    assert r["value"].consensus_reached is True


def test_recovery_plus_stale_track_blocks_refinement():
    """Recovery skips Soln but first RefmSet is round 1 while persisted tracks say 9 — all refuse."""
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=2, beta=1, early_termination=False),
        event_bus=EventBus(),
    )
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["new_term_ack_provider"] = (
        lambda experts, term_num, leader_id: [
            {"term": 6, "agent_id": "a1", "refm_set": ["x", "x", "x"], "round_num": 2},
            {"term": 6, "agent_id": "a2", "refm_set": ["x", "x", "x"], "round_num": 2},
        ]
    )
    cfg["refm_round_track_init"] = {"a1": 9, "a2": 9, "a3": 9}
    agents = {
        "a1": MockAgent("a1", proposal_output="x", refm_output="x"),
        "a2": MockAgent("a2", proposal_output="x", refm_output="x"),
        "a3": MockAgent("a3", proposal_output="x", refm_output="x"),
    }
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    assert r["value"].consensus_reached is False
