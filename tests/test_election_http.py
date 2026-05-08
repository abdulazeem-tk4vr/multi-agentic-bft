"""HTTP JSON transport for RequestVote / Vote."""

from __future__ import annotations

from aegean import AegeanConfig, create_aegean_protocol
from aegean.election import local_election_states_for_experts, simulate_leader_election
from aegean.election_http import (
    HttpElectionMessenger,
    http_cluster_for_experts,
    shutdown_servers,
)
from aegean.election_transport import InProcessElectionMessenger, run_election_with_messenger

from aegean_test_utils import MockAgent, create_test_config


def test_run_election_http_matches_inprocess():
    experts = ["a1", "a2", "a3"]
    http_m, servers = http_cluster_for_experts(experts)
    try:
        st = local_election_states_for_experts(experts, None)
        in_m = InProcessElectionMessenger(st)
        a = run_election_with_messenger(
            experts, 0, term=2, candidate_id="a2", messenger=in_m
        )
        b = run_election_with_messenger(
            experts, 0, term=2, candidate_id="a2", messenger=http_m
        )
        assert a == b
        sim = simulate_leader_election(experts, 0, term=2, candidate_id="a2")
        assert a == sim
    finally:
        shutdown_servers(servers)


def test_simulate_leader_election_unchanged_with_http_equivalence():
    experts = ["x", "y", "z"]
    http_m, servers = http_cluster_for_experts(experts)
    try:
        direct = simulate_leader_election(experts, 0, term=1, candidate_id="y")
        via = run_election_with_messenger(
            experts, 0, term=1, candidate_id="y", messenger=http_m
        )
        assert direct == via
    finally:
        shutdown_servers(servers)


def test_protocol_execute_with_http_election_messenger():
    experts = ["a1", "a2", "a3"]
    messenger, servers = http_cluster_for_experts(experts)
    try:
        cfg = create_test_config(experts)
        cfg["election_messenger"] = messenger
        proto = create_aegean_protocol(AegeanConfig(max_rounds=2, beta=1))
        agents = {e: MockAgent(e, proposal_output="x", refm_output="x") for e in experts}
        r = proto.execute(cfg, agents)
        assert r["ok"] is True
        assert r["value"].consensus_reached is True
    finally:
        shutdown_servers(servers)


def test_http_messenger_initial_terms_respected():
    experts = ["p", "q", "r"]
    init = {"p": 99, "q": 99, "r": 99}
    http_m, servers = http_cluster_for_experts(experts, initial_local_terms=init)
    try:
        out = run_election_with_messenger(
            experts, 0, term=100, candidate_id="p", messenger=http_m
        )
        assert out.has_request_vote_quorum is True
        assert out.has_vote_quorum is True
    finally:
        shutdown_servers(servers)

