import pytest

from aegean.election import (
    LocalElectionState,
    as_refinement_list,
    local_election_states_for_experts,
    new_term_ack_from_mapping,
    recovery_acks_all_bottom,
    refm_set_update_allowed,
    request_vote_granted,
    request_vote_quorum_reached,
    select_recovery_ack,
    simulate_leader_election,
)
from aegean.types import (
    REFM_BOTTOM,
    NewTermAckPayload,
    RequestVoteMessage,
    VoteMessage,
    calculate_quorum_size,
    is_refm_bottom,
)


def test_grant_request_vote_bumps_term():
    st = LocalElectionState(term=0)
    assert st.grant_request_vote(RequestVoteMessage(4, "leader")) is True
    assert st.term == 4
    assert st.grant_request_vote(RequestVoteMessage(4, "other")) is False


def test_simulate_leader_election_rv_and_vote_match_healthy_cluster():
    experts = ["a1", "a2", "a3"]
    out = simulate_leader_election(experts, 0, term=2, candidate_id="a2")
    assert out.has_request_vote_quorum and out.has_vote_quorum
    assert set(out.request_vote_granted_by) == set(experts)
    assert set(out.votes_for_candidate) == set(experts)


def test_simulate_leader_election_missing_state_key_raises():
    with pytest.raises(ValueError, match="missing experts"):
        simulate_leader_election(
            ["a", "b", "c"],
            0,
            term=1,
            candidate_id="a",
            states={"a": LocalElectionState(), "b": LocalElectionState()},
        )


def test_local_election_states_for_experts_partial_terms():
    m = local_election_states_for_experts(["x", "y"], {"x": 7})
    assert m["x"].term == 7 and m["y"].term == 0


def test_request_vote_requires_strictly_higher_term():
    assert request_vote_granted(local_term=1, candidate_term=2) is True
    assert request_vote_granted(local_term=2, candidate_term=2) is False


def test_recovery_tiebreak_term_then_round_then_agent():
    acks = [
        NewTermAckPayload(1, "a", ["x"], 1),
        NewTermAckPayload(2, "b", ["y"], 3),
        NewTermAckPayload(2, "c", ["z"], 5),
    ]
    best = select_recovery_ack(acks)
    assert best is not None
    assert best.agent_id == "c"
    assert best.round_num == 5


def test_recovery_all_bottom_returns_none():
    acks = [
        NewTermAckPayload(2, "a", REFM_BOTTOM, 1),
        NewTermAckPayload(2, "b", REFM_BOTTOM, 9),
    ]
    assert recovery_acks_all_bottom(acks) is True
    assert select_recovery_ack(acks) is None


def test_new_term_ack_mapping_bottom_flag():
    a = new_term_ack_from_mapping({"term": 1, "agent_id": "p", "round_num": 0, "refm_bottom": True})
    assert is_refm_bottom(a.refm_set)


def test_as_refinement_list():
    assert as_refinement_list(REFM_BOTTOM) == []
    assert as_refinement_list(["a", "b"]) == ["a", "b"]
    assert as_refinement_list(3) == [3]


def test_one_vote_per_term_enforced():
    st = LocalElectionState(term=1)
    st.record_vote(VoteMessage(term=1, voter_id="self", grant=True, vote_for="cand"))
    with pytest.raises(ValueError, match="at most one vote"):
        st.record_vote(VoteMessage(term=1, voter_id="self", grant=True, vote_for="cand"))


def test_refm_set_round_guard():
    assert refm_set_update_allowed(local_round=3, incoming_round=3) is True
    assert refm_set_update_allowed(local_round=3, incoming_round=2) is False


def test_request_vote_quorum_all_grant_when_terms_zero():
    experts = ["a1", "a2", "a3"]
    assert request_vote_quorum_reached(experts, 0, election_term=1, candidate_id="a1") is True


def test_request_vote_quorum_fails_when_terms_stale_vs_candidate():
    experts = ["a1", "a2", "a3"]
    init = {e: 99 for e in experts}
    assert (
        request_vote_quorum_reached(
            experts, 0, election_term=1, candidate_id="a1", initial_local_terms=init
        )
        is False
    )


def test_request_vote_quorum_needs_r_grants_under_failstop_f():
    experts = ["a1", "a2", "a3", "a4", "a5"]
    f = 2
    assert calculate_quorum_size(len(experts), f) == 3
    high = {"a1": 10, "a2": 10}
    assert (
        request_vote_quorum_reached(
            experts, f, election_term=3, candidate_id="a3", initial_local_terms=high
        )
        is True
    )
    high_bad = {e: 10 for e in experts}
    assert (
        request_vote_quorum_reached(
            experts, f, election_term=3, candidate_id="a3", initial_local_terms=high_bad
        )
        is False
    )
