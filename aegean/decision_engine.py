"""Paper-style decision engine: **α** (within-round equivalence quorum on Refm outputs), **β**
(consecutive-round stability on the candidate). The committed output may only be a value present
in the caller-supplied previous refinement set **R̄_prev** (paper “output from previous round’s set”
when interpreting evidence at round **i+1**).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .logutil import get_aegean_logger

_log = get_aegean_logger("decision_engine")


def _sort_key(x: Any) -> tuple[str, str]:
    return (str(type(x).__name__), str(x))


@dataclass(frozen=True)
class DecisionEngineConfig:
    alpha: int
    beta: int


@dataclass(frozen=True)
class DecisionStepResult:
    committed: bool
    value: Any | None
    stability: int
    eligible_candidate: Any | None
    overturned: bool


def cluster_by_alpha_equivalence(
    outputs: Sequence[Any],
    same: Callable[[Any, Any], bool],
) -> list[list[Any]]:
    """Partition ``outputs`` into disjoint clusters under reflexive/symmetric ``same`` (transitive hull per seed)."""
    clusters: list[list[Any]] = []
    for o in outputs:
        for c in clusters:
            if same(o, c[0]):
                c.append(o)
                break
        else:
            clusters.append([o])
    return clusters


class DecisionEngine:
    """Stateful α/β tracker; call :meth:`on_new_term` when the paper **term-num** changes."""

    __slots__ = ("_alpha_same", "_beta_same", "_candidate", "_config", "_stability", "_term_num")

    def __init__(
        self,
        config: DecisionEngineConfig,
        *,
        alpha_same: Callable[[Any, Any], bool] | None = None,
        beta_same: Callable[[Any, Any], bool] | None = None,
    ) -> None:
        if config.alpha < 1 or config.beta < 1:
            raise ValueError("alpha and beta must be >= 1")
        self._config = config
        self._alpha_same = alpha_same or (lambda a, b: a == b)
        self._beta_same = beta_same or (lambda a, b: a == b)
        self._candidate: Any | None = None
        self._stability = 0
        self._term_num: int | None = None

    def on_new_term(self, term_num: int) -> None:
        """Clear cross-round stability for a new **term-num** (β state does not cross term boundaries)."""
        t = int(term_num)
        if self._term_num is None:
            self._term_num = t
            return
        if t != self._term_num:
            _log.info("decision engine β state reset (term %s -> %s)", self._term_num, t)
            self._term_num = t
            self._candidate = None
            self._stability = 0

    def step(
        self,
        *,
        r_bar_prev: Sequence[Any],
        current_round_outputs: Sequence[Any],
    ) -> DecisionStepResult:
        """Consume Refm outputs for the current round; ``r_bar_prev`` is **R̄_i** when interpreting round **i+1**."""
        alpha = self._config.alpha
        prev = set(r_bar_prev)
        clusters = cluster_by_alpha_equivalence(current_round_outputs, self._alpha_same)
        eligible_vals: list[Any] = []
        for cluster in clusters:
            if len(cluster) < alpha:
                continue
            if any(x in prev for x in cluster):
                pick = min((x for x in cluster if x in prev), key=_sort_key)
                eligible_vals.append(pick)

        if not eligible_vals:
            self._candidate = None
            self._stability = 0
            # No α-quorum cluster intersecting R̄_prev: treat as ⊥ / no admissible candidate (paper §5.2).
            return DecisionStepResult(
                committed=False,
                value=None,
                stability=0,
                eligible_candidate=None,
                overturned=False,
            )

        chosen = min(eligible_vals, key=_sort_key)

        overturned = False
        if self._candidate is None:
            self._stability = 1
        elif not self._beta_same(self._candidate, chosen):
            overturned = True
            self._stability = 1
        else:
            self._stability += 1

        self._candidate = chosen
        committed = self._stability >= self._config.beta
        return DecisionStepResult(
            committed=committed,
            value=chosen if committed else None,
            stability=self._stability,
            eligible_candidate=chosen,
            overturned=overturned,
        )
