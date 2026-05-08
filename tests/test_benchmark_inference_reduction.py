"""Benchmark harness: fixed-round majority token budget vs Aegean ``tokens_used`` / refinement depth."""

import pytest

from aegean import (
    AegeanConfig,
    EventBus,
    count_refinement_rounds,
    create_aegean_protocol,
    fixed_round_token_budget,
    inference_reduction_vs_fixed_schedule,
    summarize_for_logging,
)
from aegean_test_utils import MockAgent, create_test_config


def test_fixed_round_token_budget_matches_soln_plus_full_refm_depth():
    n, f, depth = 5, 1, 4
    ts, tr = 30, 10
    b = fixed_round_token_budget(
        n_agents=n,
        failstop_fault_bound=f,
        max_refinement_rounds=depth,
        tokens_per_soln_per_agent=ts,
        tokens_per_refm_per_agent=tr,
    )
    assert b == n * ts + depth * n * tr


def test_fixed_round_token_budget_rejects_paper_invalid_ensemble():
    with pytest.raises(ValueError, match="at least 3 agents"):
        fixed_round_token_budget(
            n_agents=2,
            failstop_fault_bound=0,
            max_refinement_rounds=1,
            tokens_per_soln_per_agent=1,
            tokens_per_refm_per_agent=1,
        )


def test_early_consensus_saves_rounds_and_beats_fixed_schedule_budget():
    """β=1 + stable mocks → one Refm round; baseline still assumes ``max_rounds`` Refm waves."""
    tr = 25
    n = 3
    f = 0
    max_r = 10
    experts = ["a1", "a2", "a3"]
    cfg = create_test_config(experts)
    agents = {e: MockAgent(e, proposal_output="ok", vote_output="ok", refm_output="ok", tokens_used=tr) for e in experts}

    protocol = create_aegean_protocol(
        config=AegeanConfig(
            max_rounds=max_r,
            beta=1,
            alpha=2,
            byzantine_tolerance=f,
            early_termination=True,
        ),
        event_bus=EventBus(),
    )
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    out = r["value"]
    assert out.consensus_reached is True

    ref_n = count_refinement_rounds(out)
    assert ref_n == 1

    # Uniform per-call token accounting (Soln uses the same metadata as Refm in MockAgent).
    budget = fixed_round_token_budget(
        n_agents=n,
        failstop_fault_bound=f,
        max_refinement_rounds=max_r,
        tokens_per_soln_per_agent=tr,
        tokens_per_refm_per_agent=tr,
    )
    assert out.tokens_used < budget

    rep = inference_reduction_vs_fixed_schedule(
        out,
        n_agents=n,
        failstop_fault_bound=f,
        max_refinement_rounds=max_r,
        tokens_per_soln_per_agent=tr,
        tokens_per_refm_per_agent=tr,
    )
    assert rep.aegean_refinement_rounds == 1
    assert rep.baseline_refinement_rounds_budget == max_r
    assert rep.refinement_rounds_saved_vs_budget == max_r - 1
    assert rep.reduction_ratio == pytest.approx(budget / out.tokens_used)
    assert summarize_for_logging(rep)["refinement_rounds_saved_vs_budget"] == max_r - 1


def test_count_refinement_rounds_zero_when_max_rounds_disallows_refm():
    protocol = create_aegean_protocol(
        config=AegeanConfig(max_rounds=0, beta=1, alpha=2, byzantine_tolerance=0),
        event_bus=EventBus(),
    )
    cfg = create_test_config(["a1", "a2", "a3"])
    agents = {e: MockAgent(e, proposal_output="q", refm_output="q") for e in ["a1", "a2", "a3"]}
    r = protocol.execute(cfg, agents)
    assert r["ok"] is True
    out = r["value"]
    assert count_refinement_rounds(out) == 0

