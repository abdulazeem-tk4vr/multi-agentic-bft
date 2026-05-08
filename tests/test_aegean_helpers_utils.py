from aegean.helpers_utils import (
    create_leader_vote,
    create_proposal,
    create_proposal_task,
    create_timeout_vote,
    create_vote_from_output,
    create_vote_task,
    evaluate_quorum_status,
    extract_reasoning,
    parse_vote_status,
    select_leader,
    EvaluateQuorumOptions,
)
from aegean.types import AgentVote


def test_parse_vote_status_accept_reject_pending():
    assert parse_vote_status("I accept this proposal")["status"] == "accept"
    assert parse_vote_status("I reject this proposal")["status"] == "reject"
    assert parse_vote_status("need more information")["status"] == "pending"


def test_extract_reasoning_truncates():
    assert len(extract_reasoning("x" * 600, 500)) == 500


def test_create_votes():
    timeout_vote = create_timeout_vote("a1", "p1")
    assert timeout_vote.status == "timeout"
    leader_vote = create_leader_vote("leader", "p1")
    assert leader_vote.status == "accept"
    vote_result = create_vote_from_output("a2", "p1", "I ACCEPT", 50)
    assert vote_result["vote"].status == "accept"
    assert vote_result["tokens_used"] == 50


def test_task_builders():
    task = {"id": "task-1", "description": "Solve", "context": {}}
    proposal_task = create_proposal_task(task, 1)
    assert proposal_task["id"] == "task-1-proposal-1"
    proposal = create_proposal(1, "leader", {"answer": 42})
    vote_task = create_vote_task(proposal, "agent")
    assert "ACCEPT or REJECT" in vote_task["description"]


def test_select_leader_round_robin_behavior():
    experts = ["alice", "bob", "charlie"]
    assert select_leader(experts, 0) == "alice"
    assert select_leader(experts, 1) == "bob"
    assert select_leader(experts, 2) == "charlie"


def test_evaluate_quorum_status():
    votes = [
        AgentVote("a1", "p", "accept", 0.8, 1),
        AgentVote("a2", "p", "accept", 0.8, 2),
        AgentVote("a3", "p", "reject", 0.8, 3),
    ]
    result = evaluate_quorum_status(
        EvaluateQuorumOptions(votes=votes, total_agents=3, byzantine_tolerance=0)
    )
    assert result["has_quorum"] is True
    assert result["accepts"] == 2
