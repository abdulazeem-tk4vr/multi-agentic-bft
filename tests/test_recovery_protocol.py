"""Coordinator recovery via runtime ``new_term_ack_provider`` NewTermAck feed."""

from aegean import AegeanConfig, EventBus, create_aegean_protocol
from aegean_test_utils import MockAgent, create_test_config


def test_recovery_skips_soln_and_starts_at_refinement_round_one():
    bus = EventBus()
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=3, beta=1, early_termination=True),
        event_bus=bus,
    )
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg_with_rec = dict(cfg)
    cfg_with_rec["new_term_ack_provider"] = (
        lambda experts, term_num, leader_id: [
            {"term": 4, "agent_id": "a1", "refm_set": ["s", "s", "s"], "round_num": 2},
            {"term": 4, "agent_id": "a2", "refm_set": ["s", "s", "s"], "round_num": 5},
        ]
    )
    agents = {
        "a1": MockAgent("a1", proposal_output="s", vote_output="s", refm_output="s"),
        "a2": MockAgent("a2", proposal_output="s", vote_output="s", refm_output="s"),
        "a3": MockAgent("a3", proposal_output="s", vote_output="s", refm_output="s"),
    }
    result = protocol.execute(cfg_with_rec, agents)
    assert result["ok"] is True
    assert result["value"].consensus_reached is True
    nums = [r.round_number for r in result["value"].rounds]
    assert 0 not in nums
    assert nums[0] == 1


def test_all_bottom_acks_fall_back_to_soln_round_zero():
    protocol = create_aegean_protocol(config=AegeanConfig(max_rounds=2, beta=1), event_bus=EventBus())
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["new_term_ack_provider"] = (
        lambda experts, term_num, leader_id: [
            {"term": 2, "agent_id": "a1", "round_num": 0, "refm_bottom": True},
        ]
    )
    agents = {
        "a1": MockAgent("a1", proposal_output="u", vote_output="u", refm_output="u"),
        "a2": MockAgent("a2", proposal_output="u", vote_output="u", refm_output="u"),
        "a3": MockAgent("a3", proposal_output="u", vote_output="u", refm_output="u"),
    }
    result = protocol.execute(cfg, agents)
    assert result["ok"] is True
    assert result["value"].rounds[0].round_number == 0


def test_recovery_bar_too_short_exits():
    protocol = create_aegean_protocol(config=AegeanConfig(byzantine_tolerance=0), event_bus=EventBus())
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["new_term_ack_provider"] = (
        lambda experts, term_num, leader_id: [
            {"term": 1, "agent_id": "a1", "refm_set": ["only-one"], "round_num": 0},
        ]
    )
    agents = {
        "a1": MockAgent("a1", proposal_output="x", vote_output="x", refm_output="x"),
        "a2": MockAgent("a2", proposal_output="x", vote_output="x", refm_output="x"),
        "a3": MockAgent("a3", proposal_output="x", vote_output="x", refm_output="x"),
    }
    result = protocol.execute(cfg, agents)
    assert result["ok"] is True
    assert result["value"].consensus_reached is False
    assert result["value"].total_rounds == 0


def test_runtime_new_term_ack_provider_emits_ack_events():
    bus = EventBus()
    protocol = create_aegean_protocol(config=AegeanConfig(max_rounds=2, beta=1), event_bus=bus)
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["new_term_ack_provider"] = (
        lambda experts, term_num, leader_id: [
            {"term": term_num, "agent_id": experts[0], "refm_set": ["z", "z", "z"], "round_num": 1},
            {"term": term_num, "agent_id": experts[1], "refm_set": ["z", "z", "z"], "round_num": 1},
        ]
    )
    agents = {
        "a1": MockAgent("a1", proposal_output="z", vote_output="z", refm_output="z"),
        "a2": MockAgent("a2", proposal_output="z", vote_output="z", refm_output="z"),
        "a3": MockAgent("a3", proposal_output="z", vote_output="z", refm_output="z"),
    }
    result = protocol.execute(cfg, agents)
    assert result["ok"] is True
    topics = [e["topic"] for e in bus.emitted_events]
    assert "protocol.aegean.new_term_started" in topics
    assert "protocol.aegean.new_term_ack_received" in topics


def test_legacy_recovery_config_is_rejected():
    protocol = create_aegean_protocol(config=AegeanConfig(max_rounds=2, beta=1), event_bus=EventBus())
    cfg = create_test_config(["a1", "a2", "a3"])
    cfg["recovery"] = {"leader_id": "a1", "acks": []}
    agents = {
        "a1": MockAgent("a1", proposal_output="z", vote_output="z", refm_output="z"),
        "a2": MockAgent("a2", proposal_output="z", vote_output="z", refm_output="z"),
        "a3": MockAgent("a3", proposal_output="z", vote_output="z", refm_output="z"),
    }
    result = protocol.execute(cfg, agents)
    assert result["ok"] is False
    assert "new_term_ack_provider" in result["error"]
