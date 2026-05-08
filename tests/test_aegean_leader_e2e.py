from aegean import AegeanConfig, EventBus, create_aegean_protocol
from aegean_test_utils import MockAgent, create_test_config


def test_leader_selected_in_first_round():
    bus = EventBus()
    protocol = create_aegean_protocol(event_bus=bus)
    config = create_test_config(["leader1", "voter2", "voter3"])
    agents = {
        "leader1": MockAgent("leader1", proposal_output="Leader 1 proposal", vote_output="ACCEPT"),
        "voter2": MockAgent("voter2", proposal_output="unused", vote_output="ACCEPT"),
        "voter3": MockAgent("voter3", proposal_output="unused", vote_output="ACCEPT"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    round_started = [e for e in bus.emitted_events if e["topic"] == "protocol.aegean.round_started"][0]
    assert round_started["payload"]["leaderId"] == "leader1"


def test_leader_rotates_when_no_consensus():
    bus = EventBus()
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=3, early_termination=False), event_bus=bus
    )
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent("agent1", proposal_output="p1", vote_output="REJECT"),
        "agent2": MockAgent("agent2", proposal_output="p2", vote_output="REJECT"),
        "agent3": MockAgent("agent3", proposal_output="p3", vote_output="REJECT"),
    }
    protocol.execute(config, agents)
    leaders = [e["payload"]["leaderId"] for e in bus.emitted_events if e["topic"] == "protocol.aegean.round_started"]
    assert len(leaders) >= 2
    assert leaders[0] == "agent1"
    assert leaders[1] == "agent2"


def test_failing_leader_returns_error():
    protocol = create_aegean_protocol(config=AegeanConfig(max_rounds=2))
    config = create_test_config(["failing_leader", "voter2", "voter3"])
    agents = {
        "failing_leader": MockAgent("failing_leader", fail=True),
        "voter2": MockAgent("voter2", vote_output="ACCEPT"),
        "voter3": MockAgent("voter3", vote_output="ACCEPT"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is False
