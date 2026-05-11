"""Phase 1/2 **commit semantics**: certificate ordering for replay audits and JSON (de)serialization.

Validates **monotonicity** of an append-only certificate stream by **(term_num, refinement_round)**,
and cross-checks a completed :class:`~aegean.types.AegeanResult` against its optional
:class:`~aegean.types.CommitCertificate` (Lemma 2-style **R̄_prev** membership, **commit** row).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .types import AegeanResult, AegeanRound, CommitCertificate

__all__ = [
    "MonotonicityViolation",
    "assert_certificate_chain_monotonic",
    "commit_certificate_from_mapping",
    "commit_certificate_to_mapping",
    "validate_aegean_result_replay",
]


class MonotonicityViolation(ValueError):
    """Raised when a certificate sequence violates term/round monotonic ordering."""


def assert_certificate_chain_monotonic(certificates: Sequence[CommitCertificate]) -> None:
    """Require strictly increasing **(term_num, refinement_round)** lexicographic order.

    Same-term commits must advance **refinement_round**. New terms may reset refinement index.
    Single-certificate chains always pass.
    """
    prev: CommitCertificate | None = None
    for c in certificates:
        if prev is None:
            prev = c
            continue
        if c.term_num < prev.term_num:
            raise MonotonicityViolation(
                f"certificate term regression {prev.term_num} -> {c.term_num}"
            )
        if c.term_num == prev.term_num:
            if c.refinement_round <= prev.refinement_round:
                raise MonotonicityViolation(
                    f"same term {c.term_num} refinement must increase "
                    f"({prev.refinement_round} -> {c.refinement_round})"
                )
        prev = c


def _prior_bar_list(ar: AegeanRound) -> list[Any]:
    if ar.proposal is None:
        return []
    v = ar.proposal.value
    return list(v) if isinstance(v, list) else [v]


def validate_aegean_result_replay(result: AegeanResult) -> None:
    """Structural + certificate checks for a finished coordinator run (deterministic replay helper).

    - Round **0** must be **proposal** (Soln bootstrap).
    - **Commit** rows (if any) must immediately follow a **refinement** row with the same
      ``round_number`` (Phase 2 graph).
    - When ``commit_certificate`` is set, that row’s refinement record must show
      ``decision_committed is True``, leader ids align, and ``committed_value ∈ R̄_prev`` on that
      refinement **Proposal** (engine precondition).
    """
    rs = result.rounds
    if not rs:
        raise ValueError("AegeanResult.rounds must be non-empty")
    z = rs[0]
    if z.phase != "proposal" or z.round_number != 0:
        raise ValueError("run must open with round 0 proposal (Soln bootstrap)")

    i = 1
    while i < len(rs):
        cur = rs[i]
        if cur.phase in ("refinement", "voting"):
            if cur.round_number < 1:
                raise ValueError("refinement rows require round_number >= 1")
            i += 1
            continue
        if cur.phase == "commit":
            if i == 0:
                raise ValueError("commit row cannot be first")
            prev = rs[i - 1]
            if prev.phase not in ("refinement", "voting"):
                raise ValueError("commit row must follow refinement")
            if prev.round_number != cur.round_number:
                raise ValueError("commit round_number must match preceding refinement")
            i += 1
            continue
        raise ValueError(f"unsupported phase in replay validation: {cur.phase!r}")

    cert = result.commit_certificate
    if cert is None:
        if any(r.phase == "commit" for r in rs):
            raise ValueError("commit phase rows present but no commit_certificate on result")
        return

    if not result.consensus_reached:
        raise ValueError("commit_certificate set but consensus_reached is false")

    refs = [
        r
        for r in rs
        if r.round_number == cert.refinement_round and r.phase in ("refinement", "voting")
    ]
    if not refs:
        raise ValueError("no refinement row for certificate.refinement_round")
    last_ref = refs[-1]
    if last_ref.decision_committed is not True:
        raise ValueError("refinement row must record decision_committed=True when certificate present")
    if last_ref.leader_id != cert.leader_id:
        raise ValueError("certificate.leader_id must match refinement leader")
    bar = _prior_bar_list(last_ref)
    if cert.committed_value not in bar:
        raise ValueError("committed_value must appear in refinement proposal R̄_prev (Lemma 2 gate)")

    commits = [r for r in rs if r.phase == "commit" and r.round_number == cert.refinement_round]
    if len(commits) != 1:
        raise ValueError("expected exactly one commit-phase row for the committing refinement round")
    cp = commits[0].proposal
    if cp is None:
        raise ValueError("commit row must carry a proposal with the committed value")
    cv = cp.value
    exposed = cv[0] if isinstance(cv, list) and len(cv) == 1 else cv
    if exposed != cert.committed_value and cv != cert.committed_value:
        raise ValueError("commit proposal must record certificate.committed_value")


def commit_certificate_to_mapping(cert: CommitCertificate) -> dict[str, Any]:
    """JSON-friendly dict (tuples → lists)."""
    d: dict[str, Any] = {
        "term_num": cert.term_num,
        "refinement_round": cert.refinement_round,
        "leader_id": cert.leader_id,
        "committed_value": cert.committed_value,
        "quorum_size_r": cert.quorum_size_r,
        "alpha": cert.alpha,
        "beta": cert.beta,
        "supporting_refm_agent_ids": list(cert.supporting_refm_agent_ids),
        "stability_mode": cert.stability_mode,
        "stability_score_at_commit": cert.stability_score_at_commit,
    }
    return d


def commit_certificate_from_mapping(payload: Mapping[str, Any]) -> CommitCertificate:
    """Inverse of :func:`commit_certificate_to_mapping`."""
    sup = payload["supporting_refm_agent_ids"]
    tup = tuple(sup) if isinstance(sup, list) else tuple(sup)
    mode = payload.get("stability_mode", "count")
    if mode not in ("count", "weighted_score"):
        mode = "count"
    score = payload.get("stability_score_at_commit")
    return CommitCertificate(
        term_num=int(payload["term_num"]),
        refinement_round=int(payload["refinement_round"]),
        leader_id=str(payload["leader_id"]),
        committed_value=payload["committed_value"],
        quorum_size_r=int(payload["quorum_size_r"]),
        alpha=int(payload["alpha"]),
        beta=int(payload["beta"]),
        supporting_refm_agent_ids=tup,
        stability_mode=mode,  # type: ignore[arg-type]
        stability_score_at_commit=float(score) if score is not None else None,
    )
