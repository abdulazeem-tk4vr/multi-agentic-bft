from aegean import AegeanConfig, EventBus, create_aegean_protocol
from aegean_test_utils import MockAgent, create_test_config


def test_single_round_consensus_when_unanimous():
    protocol = create_aegean_protocol(config=AegeanConfig(max_rounds=3), event_bus=EventBus())
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent("agent1", proposal_output="Single round proposal", vote_output="ACCEPT"),
        "agent2": MockAgent("agent2", vote_output="ACCEPT"),
        "agent3": MockAgent("agent3", vote_output="ACCEPT"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert result["value"].total_rounds == 1


def test_respects_max_rounds():
    max_rounds = 2
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=max_rounds, early_termination=False), event_bus=EventBus()
    )
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent("agent1", vote_output="REJECT"),
        "agent2": MockAgent("agent2", vote_output="REJECT"),
        "agent3": MockAgent("agent3", vote_output="REJECT"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert result["value"].total_rounds == max_rounds


def test_tracks_token_usage():
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=2, early_termination=False), event_bus=EventBus()
    )
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent("agent1", vote_output="ACCEPT", tokens_used=100),
        "agent2": MockAgent("agent2", vote_output="REJECT", tokens_used=100),
        "agent3": MockAgent("agent3", vote_output="ACCEPT", tokens_used=100),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert result["value"].tokens_used > 0


def test_emits_expected_event_topics():
    bus = EventBus()
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=2, early_termination=False), event_bus=bus
    )
    config = create_test_config(["a1", "a2", "a3"], session_id="event-tracking-session")
    agents = {
        "a1": MockAgent("a1", vote_output="REJECT"),
        "a2": MockAgent("a2", vote_output="REJECT"),
        "a3": MockAgent("a3", vote_output="REJECT"),
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
