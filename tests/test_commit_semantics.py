"""Commit semantics, monotonic certificate chains, and JSON-safe certificate (de)serialization."""

from __future__ import annotations

import pytest

from aegean import (
    AegeanConfig,
    EventBus,
    MonotonicityViolation,
    assert_certificate_chain_monotonic,
    commit_certificate_from_mapping,
    commit_certificate_to_mapping,
    create_aegean_protocol,
    validate_aegean_result_replay,
)

from aegean_test_utils import MockAgent, create_test_config


def test_validate_replay_passes_on_successful_consensus():
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=4, beta=1, alpha=2, byzantine_tolerance=0),
        event_bus=EventBus(),
    )
    cfg = create_test_config(["a1", "a2", "a3"])
    agents = {e: MockAgent(e, proposal_output="x", refm_output="x") for e in ["a1", "a2", "a3"]}
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    out = r["value"]
    validate_aegean_result_replay(out)
    phases = [x.phase for x in out.rounds]
    assert phases[0] == "proposal"
    assert "refinement" in phases
    assert phases[-1] == "commit"


def test_certificate_chain_monotonic_accepts_term_reset():
    from aegean.types import CommitCertificate

    a = CommitCertificate(
        term_num=1,
        refinement_round=3,
        leader_id="L",
        committed_value="v",
        quorum_size_r=2,
        alpha=2,
        beta=2,
        supporting_refm_agent_ids=("a", "b"),
    )
    b = CommitCertificate(
        term_num=2,
        refinement_round=1,
        leader_id="L",
        committed_value="w",
        quorum_size_r=2,
        alpha=2,
        beta=2,
        supporting_refm_agent_ids=("a", "b"),
    )
    assert_certificate_chain_monotonic((a, b))


def test_certificate_chain_rejects_same_term_non_increasing_refinement():
    from aegean.types import CommitCertificate

    a = CommitCertificate(
        term_num=5,
        refinement_round=2,
        leader_id="L",
        committed_value="v",
        quorum_size_r=2,
        alpha=2,
        beta=2,
        supporting_refm_agent_ids=("a", "b"),
    )
    b = CommitCertificate(
        term_num=5,
        refinement_round=2,
        leader_id="L",
        committed_value="w",
        quorum_size_r=2,
        alpha=2,
        beta=2,
        supporting_refm_agent_ids=("a", "b"),
    )
    with pytest.raises(MonotonicityViolation):
        assert_certificate_chain_monotonic((a, b))


def test_commit_certificate_mapping_roundtrip():
    from aegean.types import CommitCertificate

    c = CommitCertificate(
        term_num=9,
        refinement_round=1,
        leader_id="lead",
        committed_value={"k": 1},
        quorum_size_r=2,
        alpha=2,
        beta=1,
        supporting_refm_agent_ids=("u", "v", "w"),
    )
    d = commit_certificate_to_mapping(c)
    c2 = commit_certificate_from_mapping(d)
    assert c == c2
