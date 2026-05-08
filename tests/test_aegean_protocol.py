from aegean import (
    AegeanConfig,
    EventBus,
    calculate_quorum_size,
    create_aegean_protocol,
    has_accept_quorum,
    is_consensus_failed,
)
from aegean.types import QuorumStatus


class MockAgent:
    def __init__(self, proposal_output: str, vote_output: str, tokens: int = 50):
        self.proposal_output = proposal_output
        self.vote_output = vote_output
        self.tokens = tokens

    def execute(self, task):
        is_vote = str(task.get("id", "")).startswith("vote-")
        output = self.vote_output if is_vote else self.proposal_output
        return {"ok": True, "value": {"output": output, "metadata": {"tokens_used": self.tokens}}}


def make_config(experts):
    return {
        "session_id": "test-session",
        "pattern": "aegean",
        "experts": experts,
        "task": {"id": "test-task", "description": "Test task", "context": {}},
    }


def test_validation_min_agents():
    protocol = create_aegean_protocol()
    result = protocol.execute(
        make_config(["a1", "a2"]),
        {"a1": MockAgent("proposal", "ACCEPT"), "a2": MockAgent("proposal", "ACCEPT")},
    )
    assert result["ok"] is False


def test_consensus_reached_when_majority_accepts():
    protocol = create_aegean_protocol()
    config = make_config(["a1", "a2", "a3"])
    agents = {
        "a1": MockAgent("proposal", "ACCEPT"),
        "a2": MockAgent("proposal", "I ACCEPT"),
        "a3": MockAgent("proposal", "Yes, I agree"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert result["value"].consensus_reached is True


def test_eventbus_emits_started_and_completed():
    bus = EventBus()
    protocol = create_aegean_protocol(event_bus=bus)
    config = make_config(["a1", "a2", "a3"])
    agents = {
        "a1": MockAgent("proposal", "ACCEPT"),
        "a2": MockAgent("proposal", "ACCEPT"),
        "a3": MockAgent("proposal", "ACCEPT"),
    }
    protocol.execute(config, agents)
    topics = [e["topic"] for e in bus.emitted_events]
    assert "protocol.started" in topics
    assert "protocol.completed" in topics


def test_helper_functions():
    assert calculate_quorum_size(3, 0) == 2
    quorum = QuorumStatus(2, 2, 0, 1, True, True)
    assert has_accept_quorum(quorum) is True
    failed = QuorumStatus(2, 0, 2, 1, False, False)
    assert is_consensus_failed(failed, 3) is True


def test_custom_config_applies():
    protocol = create_aegean_protocol(AegeanConfig(max_rounds=1, early_termination=True))
    assert protocol.config.max_rounds == 1
