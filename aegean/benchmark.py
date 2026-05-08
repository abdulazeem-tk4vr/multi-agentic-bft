"""Paper-facing **P2** comparison: Aegean coordinator vs a **fixed-round majority** schedule.

The baseline models a strawman that **always** spends a full refinement budget (**``max_rounds``**
iterations × **N** Refm invocations) and does not apply α/β early stop. Aegean may terminate after
fewer Refm rounds once the decision engine commits (**α** support in **R̄_prev**, **β** stability),
so token-style totals and round counts are compared for **inference reduction** reporting.

This module is analytic / post-hoc on :class:`~aegean.types.AegeanResult`; it does not execute
agents. Use the same **tokens_per_soln** / **tokens_per_refm** assumptions you use for Monte Carlo
or recorded :attr:`~aegean.types.AegeanResult.tokens_used` accounting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import AegeanResult, calculate_quorum_size, validate_failstop_fault_bound

__all__ = [
    "FixedRoundMajorityBaseline",
    "InferenceReductionReport",
    "count_refinement_rounds",
    "fixed_round_token_budget",
    "inference_reduction_vs_fixed_schedule",
    "summarize_for_logging",
]


def count_refinement_rounds(result: AegeanResult) -> int:
    """Count **refinement** iterations (Refm collection rows), excluding the optional **commit** phase row."""
    return sum(
        1
        for r in result.rounds
        if r.round_number >= 1 and r.phase in ("refinement", "voting")
    )


@dataclass(frozen=True)
class FixedRoundMajorityBaseline:
    """Token proxy for a schedule that runs Soln once per agent then **every** planned Refm slot."""

    n_agents: int
    failstop_fault_bound: int
    #: Matches :attr:`~aegean.types.AegeanConfig.max_rounds` — baseline always burns this many Refm waves.
    max_refinement_rounds: int
    tokens_per_soln_per_agent: int
    tokens_per_refm_per_agent: int

    def quorum_size(self) -> int:
        return calculate_quorum_size(self.n_agents, self.failstop_fault_bound)

    def token_budget(self) -> int:
        return fixed_round_token_budget(
            n_agents=self.n_agents,
            failstop_fault_bound=self.failstop_fault_bound,
            max_refinement_rounds=self.max_refinement_rounds,
            tokens_per_soln_per_agent=self.tokens_per_soln_per_agent,
            tokens_per_refm_per_agent=self.tokens_per_refm_per_agent,
        )


def fixed_round_token_budget(
    *,
    n_agents: int,
    failstop_fault_bound: int,
    max_refinement_rounds: int,
    tokens_per_soln_per_agent: int,
    tokens_per_refm_per_agent: int,
) -> int:
    """Upper-bound inference proxy: **N × Soln** + **max_refinement_rounds × N × Refm**.

    Quorum size **R** is unchanged from Aegean — this is purely a **call-volume** model (every agent
    fires every scheduled phase).     Election traffic is not modeled; strawman is Refm-heavy reduction.
    """
    validate_failstop_fault_bound(n_agents, failstop_fault_bound)
    soln = n_agents * int(tokens_per_soln_per_agent)
    refm = int(max_refinement_rounds) * n_agents * int(tokens_per_refm_per_agent)
    return soln + refm


@dataclass(frozen=True)
class InferenceReductionReport:
    aegean_tokens_used: int
    baseline_token_budget: int
    #: ``baseline / aegean`` when both > 0; ``1.0`` if unavailable.
    reduction_ratio: float
    aegean_refinement_rounds: int
    baseline_refinement_rounds_budget: int
    #: ``baseline_budget − aegean_refinement_rounds`` (informational; can be negative if Aegean hit **max_rounds** without commit).
    refinement_rounds_saved_vs_budget: int

    @property
    def inference_calls_saved_proxy(self) -> int:
        """Δ Refm agent calls vs burning the full baseline Refm depth (**N × Δrounds**)."""
        delta = self.baseline_refinement_rounds_budget - self.aegean_refinement_rounds
        if delta <= 0:
            return 0
        # callers can multiply by agents if they need total parallel dispatch slots
        return delta


def inference_reduction_vs_fixed_schedule(
    result: AegeanResult,
    *,
    n_agents: int,
    failstop_fault_bound: int,
    max_refinement_rounds: int,
    tokens_per_soln_per_agent: int,
    tokens_per_refm_per_agent: int,
) -> InferenceReductionReport:
    """Compare actual :attr:`~aegean.types.AegeanResult.tokens_used` to the fixed-round budget.

    Use the **same** per-agent token knobs as your mock agents so the ratio matches observed totals.
    """
    base = FixedRoundMajorityBaseline(
        n_agents=n_agents,
        failstop_fault_bound=failstop_fault_bound,
        max_refinement_rounds=max_refinement_rounds,
        tokens_per_soln_per_agent=tokens_per_soln_per_agent,
        tokens_per_refm_per_agent=tokens_per_refm_per_agent,
    )
    budget = base.token_budget()
    aeg = int(result.tokens_used)
    ratio = (budget / aeg) if aeg > 0 else 1.0
    ref_done = count_refinement_rounds(result)
    return InferenceReductionReport(
        aegean_tokens_used=aeg,
        baseline_token_budget=budget,
        reduction_ratio=ratio,
        aegean_refinement_rounds=ref_done,
        baseline_refinement_rounds_budget=max_refinement_rounds,
        refinement_rounds_saved_vs_budget=max_refinement_rounds - ref_done,
    )


def summarize_for_logging(report: InferenceReductionReport) -> dict[str, Any]:
    """Stable dict for dashboards / CLI."""
    return {
        "aegean_tokens_used": report.aegean_tokens_used,
        "fixed_schedule_token_budget": report.baseline_token_budget,
        "reduction_ratio_baseline_over_aegean": report.reduction_ratio,
        "aegean_refinement_rounds": report.aegean_refinement_rounds,
        "baseline_refinement_round_budget": report.baseline_refinement_rounds_budget,
        "refinement_rounds_saved_vs_budget": report.refinement_rounds_saved_vs_budget,
    }
