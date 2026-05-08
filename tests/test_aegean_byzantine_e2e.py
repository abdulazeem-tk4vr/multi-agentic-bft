from aegean import AegeanConfig, EventBus, create_aegean_protocol
from aegean_test_utils import AlternatingVoteAgent, MockAgent, create_test_config, was_consensus_reached


def test_rejects_when_f_exceeds_paper_failstop_bound():
    protocol = create_aegean_protocol(config=AegeanConfig(byzantine_tolerance=2), event_bus=EventBus())
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent("agent1", proposal_output="x", vote_output="x", refm_output="x"),
        "agent2": MockAgent("agent2", proposal_output="x", vote_output="x", refm_output="x"),
        "agent3": MockAgent("agent3", proposal_output="x", vote_output="x", refm_output="x"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is False
    assert "2" in result["error"]


def test_three_agents_f_one_is_allowed_under_paper_bound():
    """Legacy 3f+1 gate rejected N=3 with f=1; paper fail-stop allows it (R = N − f = 2)."""
    protocol = create_aegean_protocol(
        config=AegeanConfig(byzantine_tolerance=1, max_rounds=4, beta=2), event_bus=EventBus()
    )
    config = create_test_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": MockAgent("agent1", proposal_output="h", vote_output="h", refm_output="h"),
        "agent2": MockAgent("agent2", proposal_output="h", vote_output="h", refm_output="h"),
        "agent3": MockAgent("agent3", proposal_output="h", vote_output="h", refm_output="h"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert was_consensus_reached(result) is True


def test_reaches_consensus_with_one_byzantine_agent():
    hp = "Honest proposal"
    protocol = create_aegean_protocol(
        config=AegeanConfig(byzantine_tolerance=1, max_rounds=4, beta=2), event_bus=EventBus()
    )
    config = create_test_config(["agent1", "agent2", "agent3", "byzantine"])
    agents = {
        "agent1": MockAgent("agent1", proposal_output=hp, vote_output=hp, refm_output=hp),
        "agent2": MockAgent("agent2", proposal_output=hp, vote_output=hp, refm_output=hp),
        "agent3": MockAgent("agent3", proposal_output=hp, vote_output=hp, refm_output=hp),
        "byzantine": MockAgent("byzantine", proposal_output=hp, vote_output="REJECT", refm_output="BAD"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert was_consensus_reached(result) is True


def test_handles_inconsistent_byzantine_votes():
    protocol = create_aegean_protocol(
        config=AegeanConfig(byzantine_tolerance=1, max_rounds=2, beta=2), event_bus=EventBus()
    )
    config = create_test_config(["leader", "honest1", "honest2", "byzantine"])
    agents = {
        "leader": MockAgent("leader", proposal_output="p", vote_output="p", refm_output="p"),
        "honest1": MockAgent("honest1", proposal_output="p", vote_output="p", refm_output="p"),
        "honest2": MockAgent("honest2", proposal_output="p", vote_output="p", refm_output="p"),
        "byzantine": AlternatingVoteAgent(id="byzantine", proposal_output="p"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True


def test_fails_consensus_when_too_many_byzantines():
    protocol = create_aegean_protocol(
        config=AegeanConfig(
            byzantine_tolerance=1,
            max_rounds=4,
            early_termination=True,
            alpha=3,
            beta=2,
        ),
        event_bus=EventBus(),
    )
    config = create_test_config(["leader", "honest", "byz1", "byz2"])
    agents = {
        "leader": MockAgent("leader", proposal_output="h", vote_output="h", refm_output="h"),
        "honest": MockAgent("honest", proposal_output="h", vote_output="h", refm_output="h"),
        "byz1": MockAgent("byz1", proposal_output="h", vote_output="h", refm_output="x"),
        "byz2": MockAgent("byz2", proposal_output="h", vote_output="h", refm_output="x"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert was_consensus_reached(result) is False
