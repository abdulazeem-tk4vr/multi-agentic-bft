import pytest

from aegean import (
    AegeanConfig,
    AegeanRunner,
    AegeanSessionError,
    EventBus,
    calculate_quorum_size,
    create_aegean_protocol,
    has_accept_quorum,
    is_consensus_failed,
    run_aegean_session,
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


def test_rejects_duplicate_expert_ids():
    protocol = create_aegean_protocol()
    result = protocol.execute(
        make_config(["a1", "a1", "a2"]),
        {
            "a1": MockAgent("p", "ACCEPT"),
            "a2": MockAgent("p", "ACCEPT"),
        },
    )
    assert result["ok"] is False
    assert "duplicate" in result["error"].lower()


def test_rejects_agents_experts_set_mismatch_extra_agent():
    protocol = create_aegean_protocol()
    result = protocol.execute(
        make_config(["a1", "a2", "a3"]),
        {f"a{i}": MockAgent("p", "ACCEPT") for i in (1, 2, 3, 4)},
    )
    assert result["ok"] is False
    assert "a4" in result["error"] or "not listed" in result["error"]


def test_rejects_agents_experts_set_mismatch_missing_agent():
    protocol = create_aegean_protocol()
    result = protocol.execute(
        make_config(["a1", "a2", "a3"]),
        {f"a{i}": MockAgent("p", "ACCEPT") for i in (1, 2)},
    )
    assert result["ok"] is False
    assert "a3" in result["error"] or "no agent" in result["error"]


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


def test_run_aegean_session_returns_aegean_result():
    config = make_config(["a1", "a2", "a3"])
    agents = {
        "a1": MockAgent("proposal", "ACCEPT"),
        "a2": MockAgent("proposal", "ACCEPT"),
        "a3": MockAgent("proposal", "ACCEPT"),
    }
    result = run_aegean_session(
        config,
        agents,
        config=AegeanConfig(max_rounds=3, beta=1),
        event_bus=EventBus(),
    )
    assert result.consensus_reached is True


def test_run_aegean_session_session_trace_writes_stderr(capsys):
    config = make_config(["a1", "a2", "a3"])
    agents = {
        "a1": MockAgent("proposal", "ACCEPT"),
        "a2": MockAgent("proposal", "ACCEPT"),
        "a3": MockAgent("proposal", "ACCEPT"),
    }
    run_aegean_session(
        config,
        agents,
        config=AegeanConfig(max_rounds=3, beta=1, session_trace=True),
        event_bus=EventBus(),
    )
    captured = capsys.readouterr()
    assert "OUTCOME" in captured.err
    assert "ROUNDS" in captured.err


def test_run_aegean_session_raises_on_invalid_config():
    with pytest.raises(AegeanSessionError):
        run_aegean_session(
            make_config(["a1", "a2"]),
            {"a1": MockAgent("p", "ACCEPT"), "a2": MockAgent("p", "ACCEPT")},
        )


def test_aegean_runner_runs_multiple_sessions():
    runner = AegeanRunner(config=AegeanConfig(max_rounds=3, beta=1), event_bus=EventBus())
    agents = {
        "a1": MockAgent("proposal", "ACCEPT"),
        "a2": MockAgent("proposal", "ACCEPT"),
        "a3": MockAgent("proposal", "ACCEPT"),
    }
    r1 = runner.run(make_config(["a1", "a2", "a3"]), agents)
    assert r1.consensus_reached is True
    cfg2 = dict(make_config(["a1", "a2", "a3"]))
    cfg2["session_id"] = "second-session"
    r2 = runner.run(cfg2, agents)
    assert r2.consensus_reached is True


def test_aegean_runner_cancel_sticks():
    runner = AegeanRunner(config=AegeanConfig(max_rounds=3, beta=1), event_bus=EventBus())
    runner.cancel("stop")
    agents = {
        "a1": MockAgent("proposal", "ACCEPT"),
        "a2": MockAgent("proposal", "ACCEPT"),
        "a3": MockAgent("proposal", "ACCEPT"),
    }
    r = runner.run(make_config(["a1", "a2", "a3"]), agents)
    assert r.consensus_reached is False
    assert r.termination_reason == "cancelled"


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
