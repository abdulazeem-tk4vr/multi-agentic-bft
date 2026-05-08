from aegean import (
    AegeanConfig,
    EventBus,
    calculate_quorum_size,
    create_aegean_protocol,
    has_accept_quorum,
    is_consensus_failed,
)
from aegean.types import QuorumStatus
from aegean.task_routing import PHASE_REFM, aegean_task_phase


class MockAgent:
    def __init__(self, proposal_output: str, vote_output: str, tokens: int = 50):
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
        "session_id": "test-session",
        "pattern": "aegean",
        "experts": experts,
        "task": {"id": "test-task", "description": "Test task", "context": {}},
    }


def test_rejects_failstop_f_above_paper_limit():
    """Paper bound f ≤ ⌈(N−1)/2⌉: N=3 allows at most f=1."""
    protocol = create_aegean_protocol(config=AegeanConfig(byzantine_tolerance=2))
    result = protocol.execute(
        make_config(["a1", "a2", "a3"]),
        {f"a{i}": MockAgent("p", "ACCEPT") for i in (1, 2, 3)},
    )
    assert result["ok"] is False
    assert "f=2" in result["error"] or "exceeds" in result["error"].lower()


def test_validation_min_agents():
    protocol = create_aegean_protocol()
    result = protocol.execute(
        make_config(["a1", "a2"]),
        {"a1": MockAgent("proposal", "ACCEPT"), "a2": MockAgent("proposal", "ACCEPT")},
    )
    assert result["ok"] is False


def test_rejects_when_request_vote_quorum_not_reached():
    protocol = create_aegean_protocol()
    cfg = make_config(["a1", "a2", "a3"])
    cfg["election_initial_terms"] = {"a1": 50, "a2": 50, "a3": 50}
    result = protocol.execute(
        cfg,
        {f"a{i}": MockAgent("proposal", "ACCEPT") for i in (1, 2, 3)},
    )
    assert result["ok"] is False
    assert "election" in result["error"].lower() or "term" in result["error"].lower()


def test_consensus_reached_when_majority_accepts():
    # β=1 → one refinement round after Soln can commit when α is met.
    protocol = create_aegean_protocol(config=AegeanConfig(max_rounds=3, beta=1))
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
    assert calculate_quorum_size(3, 0) == 3
    quorum = QuorumStatus(2, 2, 0, 1, True, True)
    assert has_accept_quorum(quorum) is True
    failed = QuorumStatus(2, 0, 2, 1, False, False)
    assert is_consensus_failed(failed, 3) is True


def test_recorded_rounds_cover_soln_zero_then_refinement():
    protocol = create_aegean_protocol(AegeanConfig(max_rounds=2, beta=1))
    config = make_config(["a1", "a2", "a3"])
    agents = {f"a{i}": MockAgent("agree", "agree") for i in (1, 2, 3)}
    result = protocol.execute(config, agents)
    assert result["ok"] is True
    nums = [r.round_number for r in result["value"].rounds]
    assert nums[0] == 0
    assert nums[-1] >= 1


def test_custom_config_applies():
    protocol = create_aegean_protocol(AegeanConfig(max_rounds=1, early_termination=True))
    assert protocol.config.max_rounds == 1
