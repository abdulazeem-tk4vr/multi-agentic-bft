from aegean import AegeanConfig, EventBus, create_aegean_protocol
from aegean_test_utils import AlternatingVoteAgent, MockAgent, create_test_config, was_consensus_reached


def test_requires_minimum_3f_plus_1_agents():
    protocol = create_aegean_protocol(config=AegeanConfig(byzantine_tolerance=1), event_bus=EventBus())
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent("agent1", vote_output="ACCEPT"),
        "agent2": MockAgent("agent2", vote_output="ACCEPT"),
        "agent3": MockAgent("agent3", vote_output="ACCEPT"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is False


def test_reaches_consensus_with_one_byzantine_agent():
    protocol = create_aegean_protocol(config=AegeanConfig(byzantine_tolerance=1), event_bus=EventBus())
    config = create_test_config(["agent1", "agent2", "agent3", "byzantine"])
    agents = {
        "agent1": MockAgent("agent1", proposal_output="Honest proposal", vote_output="ACCEPT"),
        "agent2": MockAgent("agent2", vote_output="ACCEPT"),
        "agent3": MockAgent("agent3", vote_output="ACCEPT"),
        "byzantine": MockAgent("byzantine", vote_output="REJECT"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert was_consensus_reached(result) is True


def test_handles_inconsistent_byzantine_votes():
    protocol = create_aegean_protocol(
        config=AegeanConfig(byzantine_tolerance=1, max_rounds=2), event_bus=EventBus()
    )
    config = create_test_config(["leader", "honest1", "honest2", "byzantine"])
    agents = {
        "leader": MockAgent("leader", vote_output="ACCEPT"),
        "honest1": MockAgent("honest1", vote_output="ACCEPT"),
        "honest2": MockAgent("honest2", vote_output="ACCEPT"),
        "byzantine": AlternatingVoteAgent(id="byzantine"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True


def test_fails_consensus_when_too_many_byzantines():
    protocol = create_aegean_protocol(
        config=AegeanConfig(byzantine_tolerance=1, max_rounds=1, early_termination=True), event_bus=EventBus()
    )
    config = create_test_config(["leader", "honest", "byz1", "byz2"])
    agents = {
        "leader": MockAgent("leader", vote_output="ACCEPT"),
        "honest": MockAgent("honest", vote_output="ACCEPT"),
        "byz1": MockAgent("byz1", vote_output="REJECT"),
        "byz2": MockAgent("byz2", vote_output="REJECT"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert was_consensus_reached(result) is False
