"""Aegean types and paper-aligned quorum configuration.

Round numbering (Aegean paper, §5.2 / Algorithm 1):
- **Round 0** — Soln bootstrap: task input is broadcast; agents return initial solutions until a
  Soln quorum is formed (same quorum size **R** as refinement).
- **Round ≥ 1** — Refinement: leader broadcasts ``⟨RefmSet, term-num, round-num, R̄⟩``; the first
  such broadcast after Soln uses **round-num = 1**; subsequent refinement iterations increment
  **round-num** until decision or term change.
- After **NewTerm** leader recovery, **round-num** is reset to **1** before the first **RefmSet**
  in the new term.

Fail-stop quorum (paper §5.1): one threshold **R = N − f** for Round 0 and every Refm round, with
**f ≤ ⌈(N − 1) / 2⌉** and **N ≥ 3**.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from .logutil import get_aegean_logger

#: Soln bootstrap → per-round ``RefmSet`` collection (**refinement**) → optional leader **commit** record.
#: ``"voting"`` is a legacy alias for **refinement** (pre–Phase-1/2 graph); new protocol rows use **refinement**.
AegeanPhase = Literal["proposal", "refinement", "voting", "commit", "done"]
AgentVoteStatus = Literal["pending", "accept", "reject", "timeout", "byzantine"]
TerminationReason = Literal["consensus", "max_rounds", "timeout", "byzantine_failure", "cancelled", "error"]

_log = get_aegean_logger("paper")


class BottomSentinel:
    """Paper **⊥** / bottom refinement set (no usable Refm state)."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "Bottom"


REFM_BOTTOM = BottomSentinel()


def is_refm_bottom(value: Any) -> bool:
    return value is REFM_BOTTOM


@dataclass(frozen=True)
class NewTermAckPayload:
    """``NewTermAck`` body: agent **i** reports recovered RefmSet and round index for tie-breaking."""

    term: int
    agent_id: str
    refm_set: Any
    round_num: int


@dataclass(frozen=True)
class RequestVoteMessage:
    term: int
    candidate_id: str


@dataclass(frozen=True)
class VoteMessage:
    term: int
    voter_id: str
    grant: bool
    vote_for: str | None = None


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    round: int
    leader_id: str
    value: Any
    timestamp: int


@dataclass(frozen=True)
class AgentVote:
    agent_id: str
    proposal_id: str
    status: AgentVoteStatus
    confidence: float
    timestamp: int
    reasoning: str | None = None


@dataclass(frozen=True)
class QuorumStatus:
    required: int
    accepts: int
    rejects: int
    pending: int
    has_quorum: bool
    consensus_reached: bool


@dataclass(frozen=True)
class AegeanRound:
    round_number: int
    phase: AegeanPhase
    leader_id: str
    proposal: Proposal | None
    votes: list[AgentVote]
    quorum_status: QuorumStatus
    start_time: int
    end_time: int | None = None
    #: Populated on **refinement** rows after :class:`~aegean.decision_engine.DecisionEngine.step` (Phase 2 graph).
    decision_committed: bool | None = None
    decision_stability: int | None = None
    decision_eligible: Any | None = None
    decision_overturned: bool | None = None


@dataclass(frozen=True)
class CommitCertificate:
    """Leader-issued commit record for audit/replay: term, refinement round, value, and quorum facts."""

    term_num: int
    refinement_round: int
    leader_id: str
    committed_value: Any
    quorum_size_r: int
    alpha: int
    beta: int
    #: Agents whose Refm output counted as an accept (ok response, confidence ≥ threshold) this round.
    supporting_refm_agent_ids: tuple[str, ...]


@dataclass(frozen=True)
class AegeanResult:
    consensus_value: Any
    consensus_reached: bool
    total_rounds: int
    total_duration_ms: int
    tokens_used: int
    rounds: list[AegeanRound]
    termination_reason: TerminationReason
    commit_certificate: CommitCertificate | None = None


@dataclass(frozen=True)
class AegeanConfig:
    max_rounds: int = 3
    round_timeout_ms: int = 60000
    #: Upper bound **f** on fail-stop faults (paper notation). Same field name as older releases;
    # not a Byzantine replica layout assumption — pair with :func:`validate_failstop_fault_bound`.
    byzantine_tolerance: int = 0
    confidence_threshold: float = 0.7
    early_termination: bool = True
    #: Paper **α**: minimum cluster size (within-round equivalence) on Refm outputs.
    alpha: int = 2
    #: Paper **β**: consecutive rounds the β-stable candidate must persist before commit.
    beta: int = 2
    #: Leader election (RequestVote/Vote): max term values to try before abort when stalls persist.
    #: Each failed attempt increments the candidate **term** and retries with the same leader id.
    max_election_attempts: int = 32
    #: Print a human-readable session trace (summary, events, rounds) after a successful run via
    #: :func:`~aegean.protocol.run_aegean_session` / :class:`~aegean.protocol.AegeanRunner`.
    #: Also enabled when env ``AEGEAN_SESSION_TRACE`` is ``1``, ``true``, ``yes``, or ``on``.
    session_trace: bool = False


def max_failstop_faults_allowed(total_agents: int) -> int:
    """Largest **f** permitted by the paper bound **f ≤ ⌈(N − 1) / 2⌉** (for **N ≥ 3**)."""
    if total_agents < 3:
        return 0
    return int(math.ceil((total_agents - 1) / 2))


def validate_failstop_fault_bound(total_agents: int, f: int) -> None:
    """Raise ``ValueError`` if **N** or **f** violate the paper fail-stop assumptions."""
    if total_agents < 3:
        _log.warning("invalid ensemble size N=%s (paper requires N >= 3)", total_agents)
        raise ValueError(f"Paper Aegean requires at least 3 agents (N={total_agents})")
    if f < 0:
        _log.warning("invalid fail-stop bound f=%s (must be non-negative)", f)
        raise ValueError(f"Fail-stop bound f must be non-negative (f={f})")
    max_f = max_failstop_faults_allowed(total_agents)
    if f > max_f:
        _log.warning(
            "fail-stop bound too large: N=%s f=%s (max f=%s per paper)",
            total_agents,
            f,
            max_f,
        )
        raise ValueError(
            f"Fail-stop bound f={f} exceeds paper limit ⌈(N-1)/2⌉={max_f} for N={total_agents}"
        )


def calculate_quorum_size(total_agents: int, failstop_fault_bound: int) -> int:
    """Paper Aegean quorum size **R = N − f** for Round 0 (Soln) and every Refm round."""
    validate_failstop_fault_bound(total_agents, failstop_fault_bound)
    return total_agents - failstop_fault_bound


def has_accept_quorum(quorum: QuorumStatus) -> bool:
    return quorum.accepts >= quorum.required


def is_consensus_failed(quorum: QuorumStatus, total_agents: int) -> bool:
    return quorum.rejects > total_agents - quorum.required
