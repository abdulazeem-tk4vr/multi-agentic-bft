from aegean import AegeanConfig, EventBus, create_aegean_protocol
from aegean_test_utils import MockAgent, create_test_config


def test_soln_plus_one_refinement_when_beta_one():
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=3, beta=1, early_termination=True), event_bus=EventBus()
    )
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent(
            "agent1",
            proposal_output="Single round proposal",
            vote_output="ACCEPT",
            refm_output="Single round proposal",
        ),
        "agent2": MockAgent(
            "agent2",
            proposal_output="Single round proposal",
            vote_output="ACCEPT",
            refm_output="Single round proposal",
        ),
        "agent3": MockAgent(
            "agent3",
            proposal_output="Single round proposal",
            vote_output="ACCEPT",
            refm_output="Single round proposal",
        ),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert result["value"].consensus_reached is True
    # Round 0 (Soln) + one Refm refinement row + commit phase row (β=1).
    assert result["value"].total_rounds == 3


def test_respects_max_refinement_rounds_without_commit():
    max_refm = 2
    protocol = create_aegean_protocol(
        config=AegeanConfig(
            max_rounds=max_refm,
            early_termination=False,
            alpha=3,
            beta=2,
        ),
        event_bus=EventBus(),
    )
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent("agent1", proposal_output="p", vote_output="p", refm_output="a"),
        "agent2": MockAgent("agent2", proposal_output="p", vote_output="p", refm_output="b"),
        "agent3": MockAgent("agent3", proposal_output="p", vote_output="p", refm_output="c"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert result["value"].consensus_reached is False
    assert result["value"].total_rounds == 1 + max_refm


def test_tracks_token_usage():
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=2, early_termination=False, beta=1), event_bus=EventBus()
    )
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent("agent1", proposal_output="p", vote_output="p", refm_output="p", tokens_used=100),
        "agent2": MockAgent("agent2", proposal_output="p", vote_output="p", refm_output="p", tokens_used=100),
        "agent3": MockAgent("agent3", proposal_output="p", vote_output="p", refm_output="p", tokens_used=100),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert result["value"].tokens_used > 0


def test_emits_expected_event_topics():
    bus = EventBus()
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=2, early_termination=False, alpha=3, beta=2),
        event_bus=bus,
    )
    config = create_test_config(["a1", "a2", "a3"], session_id="event-tracking-session")
    agents = {
        "a1": MockAgent("a1", proposal_output="z", vote_output="z", refm_output="z"),
        "a2": MockAgent("a2", proposal_output="z", vote_output="z", refm_output="z"),
        "a3": MockAgent("a3", proposal_output="z", vote_output="z", refm_output="z"),
    }
    protocol.execute(config, agents)
    topics = [e["topic"] for e in bus.emitted_events]
    assert "protocol.started" in topics
    assert "protocol.aegean.round_started" in topics
    assert "protocol.aegean.vote_collected" in topics
    assert "protocol.iteration" in topics
    assert "protocol.completed" in topics


def test_cancel_execution_gracefully():
    protocol = create_aegean_protocol(config=AegeanConfig(max_rounds=10), event_bus=EventBus())
    protocol.cancel("Test cancellation")
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent("agent1", delay_ms=500),
        "agent2": MockAgent("agent2"),
        "agent3": MockAgent("agent3"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert result["value"].consensus_reached is False
    assert result["value"].termination_reason == "cancelled"


def test_leader_stays_constant_within_term():
    bus = EventBus()
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=3, early_termination=False, alpha=2, beta=2),
        event_bus=bus,
    )
    config = create_test_config(["a1", "a2", "a3"], session_id="leader-term-stability")
    agents = {
        "a1": MockAgent("a1", proposal_output="x", vote_output="x", refm_output="x"),
        "a2": MockAgent("a2", proposal_output="x", vote_output="x", refm_output="x"),
        "a3": MockAgent("a3", proposal_output="x", vote_output="x", refm_output="x"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    rounds = [e for e in bus.emitted_events if e["topic"] == "protocol.aegean.round_started"]
    assert rounds, "expected round_started events"
    leaders = {str(e["payload"].get("leaderId", "")) for e in rounds}
    assert len(leaders) == 1
