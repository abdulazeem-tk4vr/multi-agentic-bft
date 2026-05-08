from aegean import create_aegean_protocol, calculate_quorum_size, has_accept_quorum, is_consensus_failed
from aegean.types import QuorumStatus
from aegean.events import EventBus


from aegean.task_routing import PHASE_REFM, aegean_task_phase


class ConfigurableAgent:
    def __init__(self, proposal_output: str, vote_output: str, tokens: int = 25):
        self.proposal_output = proposal_output
        self.vote_output = vote_output
        self.tokens = tokens

    def execute(self, task):
        if aegean_task_phase(task) == PHASE_REFM:
            output = self.proposal_output
        elif str(task.get("id", "")).startswith("vote-"):
            output = self.vote_output
        else:
            output = self.proposal_output
        return {"ok": True, "value": {"output": output, "metadata": {"tokens_used": self.tokens}}}


def make_config(experts):
    return {
        "session_id": "e2e-session",
        "pattern": "aegean",
        "experts": experts,
        "task": {"id": "test-task", "description": "Consensus task", "context": {}},
    }


def test_quorum_formation_e2e():
    bus = EventBus()
    protocol = create_aegean_protocol(event_bus=bus)
    config = make_config(["agent1", "agent2", "agent3"])
    agents = {
        "agent1": ConfigurableAgent("P", "ACCEPT"),
        "agent2": ConfigurableAgent("P", "ACCEPT"),
        "agent3": ConfigurableAgent("P", "ACCEPT"),
    }
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    assert any(e["topic"] == "protocol.aegean.quorum_detected" for e in bus.emitted_events)


def test_quorum_math():
    # Fail-stop paper quorum R = N - f (not ⌈(N+f+1)/2⌉).
    assert calculate_quorum_size(3, 0) == 3
    assert calculate_quorum_size(5, 0) == 5
    assert calculate_quorum_size(4, 1) == 3


def test_has_accept_quorum_and_failure():
    quorum_ok = QuorumStatus(2, 2, 1, 0, True, True)
    assert has_accept_quorum(quorum_ok) is True
    failed = QuorumStatus(2, 1, 2, 0, False, False)
    assert is_consensus_failed(failed, 3) is True
