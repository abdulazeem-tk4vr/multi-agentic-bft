"""Paper Aegean leader election / **NewTerm** recovery helpers (fail-stop).

RequestVote / Vote / NewTermAck semantics used by the coordinator and unit-tested here so message
guards stay exact before RPC wiring.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .logutil import get_aegean_logger
from .election_transport import InProcessElectionMessenger, run_election_with_messenger
from .types import (
    REFM_BOTTOM,
    NewTermAckPayload,
    RequestVoteMessage,
    VoteMessage,
    calculate_quorum_size,
    is_refm_bottom,
    validate_failstop_fault_bound,
)

_log = get_aegean_logger("election")


def request_vote_granted(*, local_term: int, candidate_term: int) -> bool:
    """Accept **RequestVote** only when the candidate’s **term** is strictly higher (paper guard)."""
    return candidate_term > local_term


def as_refinement_list(refm_set: object) -> list[object]:
    """Normalise stored **RefmSet** payload to a list (``REFM_BOTTOM`` → empty)."""
    if is_refm_bottom(refm_set):
        return []
    if isinstance(refm_set, list):
        return list(refm_set)
    return [refm_set]


def new_term_ack_from_mapping(row: Mapping[str, object]) -> NewTermAckPayload:
    if row.get("refm_bottom"):
        refm: object = REFM_BOTTOM
    else:
        refm = row["refm_set"]
    return NewTermAckPayload(
        term=int(row["term"]),
        agent_id=str(row["agent_id"]),
        refm_set=refm,
        round_num=int(row["round_num"]),
    )


def recovery_acks_all_bottom(acks: Sequence[NewTermAckPayload]) -> bool:
    """True iff every ack is **bottom** — coordinator should run fresh Round 0 Soln (extension)."""
    if not acks:
        return True
    return all(is_refm_bottom(a.refm_set) for a in acks)


def select_recovery_ack(acks: Sequence[NewTermAckPayload]) -> NewTermAckPayload | None:
    """Pick ack maximizing **(term, round_num, agent_id)** among non-bottom **refm_set** entries."""
    if not acks or recovery_acks_all_bottom(acks):
        return None
    alive = [a for a in acks if not is_refm_bottom(a.refm_set)]
    chosen = max(alive, key=lambda a: (a.term, a.round_num, a.agent_id))
    _log.debug("recovery pick term=%s round=%s agent=%s", chosen.term, chosen.round_num, chosen.agent_id)
    return chosen


@dataclass(frozen=True)
class ElectionSimulationResult:
    """Outcome of an in-process **RequestVote** → **Vote** pass (fail-stop simulation)."""

    term: int
    candidate_id: str
    request_vote_granted_by: tuple[str, ...]
    votes_for_candidate: tuple[str, ...]
    has_request_vote_quorum: bool
    has_vote_quorum: bool


@dataclass
class LocalElectionState:
    """Per-agent election memory: current term and at-most-one vote per term."""

    term: int = 0
    voted_in_term: int | None = None
    last_vote_for: str | None = field(default=None, repr=False)

    def try_grant_request_vote(self, msg: RequestVoteMessage) -> bool:
        return request_vote_granted(local_term=self.term, candidate_term=msg.term)

    def grant_request_vote(self, msg: RequestVoteMessage) -> bool:
        """Adopt **msg.term** when the RequestVote guard passes (Raft-style monotonic term)."""
        if not self.try_grant_request_vote(msg):
            return False
        self.bump_term(msg.term)
        return True

    def bump_term(self, new_term: int) -> None:
        if new_term > self.term:
            self.term = new_term

    def record_vote(self, msg: VoteMessage) -> None:
        if msg.term != self.term:
            raise ValueError(f"vote term {msg.term} does not match local term {self.term}")
        if self.voted_in_term == msg.term:
            raise ValueError(f"at most one vote per term (term={msg.term})")
        self.voted_in_term = msg.term
        self.last_vote_for = msg.vote_for


def refm_set_update_allowed(*, local_round: int, incoming_round: int) -> bool:
    """Per-agent **RefmSet** guard: store only when ``incoming_round >= local_round``."""
    return incoming_round >= local_round


def local_election_states_for_experts(
    experts: list[str],
    initial_local_terms: dict[str, int] | None = None,
) -> dict[str, LocalElectionState]:
    """Fresh :class:`LocalElectionState` map: optional ``agent_id → persisted term``."""
    init = initial_local_terms or {}
    return {e: LocalElectionState(term=int(init.get(e, 0))) for e in experts}


def simulate_leader_election(
    experts: list[str],
    f: int,
    *,
    term: int,
    candidate_id: str,
    states: dict[str, LocalElectionState] | None = None,
) -> ElectionSimulationResult:
    """Run one **RequestVote** broadcast then **Vote** collection (in-memory, deterministic order).

    Mutates ``states`` in place when provided; otherwise builds zero-initialised states.
    Each granting agent adopts ``term`` then records a single :class:`VoteMessage` for
    ``candidate_id`` if :meth:`LocalElectionState.record_vote` accepts it.
    """
    n = len(experts)
    validate_failstop_fault_bound(n, f)
    if states is None:
        election_states = local_election_states_for_experts(experts, None)
    else:
        election_states = states
        missing = [e for e in experts if e not in election_states]
        if missing:
            raise ValueError(f"election states missing experts: {missing}")

    messenger = InProcessElectionMessenger(election_states)
    return run_election_with_messenger(
        experts, f, term=term, candidate_id=candidate_id, messenger=messenger
    )


def request_vote_quorum_reached(
    experts: list[str],
    f: int,
    election_term: int,
    candidate_id: str,
    *,
    initial_local_terms: dict[str, int] | None = None,
) -> bool:
    """True iff ≥ **R** experts would grant **RequestVote** at ``election_term`` (no Vote phase).

    .. note::
        For the full **RequestVote** + **Vote** simulation, use :func:`simulate_leader_election`.
    """
    states = local_election_states_for_experts(experts, initial_local_terms)
    msg = RequestVoteMessage(election_term, candidate_id)
    n = len(experts)
    validate_failstop_fault_bound(n, f)
    need = calculate_quorum_size(n, f)
    grants = sum(1 for eid in experts if states[eid].try_grant_request_vote(msg))
    return grants >= need
