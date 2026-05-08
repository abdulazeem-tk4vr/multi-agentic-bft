"""Pluggable election messaging for **RequestVote** / **Vote**.

Default path uses :class:`InProcessElectionMessenger` (shared ``dict`` of
:class:`~aegean.election.LocalElectionState`). Multi-process deployments can supply a custom
:class:`ElectionMessenger` (e.g. :class:`~aegean.election_http.HttpElectionMessenger`) via
``config["election_messenger"]`` on :meth:`~aegean.protocol.AegeanProtocol.execute`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .logutil import get_aegean_logger
from .types import RequestVoteMessage, VoteMessage, calculate_quorum_size, validate_failstop_fault_bound

if TYPE_CHECKING:
    from .election import ElectionSimulationResult, LocalElectionState

_log = get_aegean_logger("election_transport")

# Lazy import ElectionSimulationResult inside run_election_with_messenger to avoid import cycles


class ElectionMessenger(Protocol):
    """Routes **RequestVote** / **Vote** to the peer identified by ``peer_id`` (paper node id)."""

    def request_vote(self, peer_id: str, msg: RequestVoteMessage) -> bool:
        """Deliver **RequestVote**; return whether the peer granted (and adopted term when true)."""

    def record_vote(self, peer_id: str, msg: VoteMessage) -> None:
        """Deliver **Vote** for an agent that already granted **RequestVote** (may raise **ValueError**)."""


def run_election_with_messenger(
    experts: list[str],
    f: int,
    *,
    term: int,
    candidate_id: str,
    messenger: ElectionMessenger,
) -> ElectionSimulationResult:
    """One **RequestVote** broadcast (sequential RPC to each expert) then **Vote** collection.

    Mirrors the in-process simulation ordering in :func:`~aegean.election.simulate_leader_election`.
    """
    from .election import ElectionSimulationResult

    n = len(experts)
    validate_failstop_fault_bound(n, f)
    need = calculate_quorum_size(n, f)

    rv_msg = RequestVoteMessage(term, candidate_id)
    rv_granted: list[str] = []
    for eid in experts:
        try:
            ok = messenger.request_vote(eid, rv_msg)
        except Exception as exc:
            _log.warning("election RPC request_vote %s failed: %s", eid, exc)
            ok = False
        if ok:
            rv_granted.append(eid)

    has_rv = len(rv_granted) >= need

    votes: list[str] = []
    for eid in rv_granted:
        vm = VoteMessage(term=term, voter_id=eid, grant=True, vote_for=candidate_id)
        try:
            messenger.record_vote(eid, vm)
        except ValueError as exc:
            _log.warning("sim election: could not record vote from %s: %s", eid, exc)
        else:
            votes.append(eid)

    has_votes = len(votes) >= need

    return ElectionSimulationResult(
        term=term,
        candidate_id=candidate_id,
        request_vote_granted_by=tuple(rv_granted),
        votes_for_candidate=tuple(votes),
        has_request_vote_quorum=has_rv,
        has_vote_quorum=has_votes,
    )


class InProcessElectionMessenger:
    """Deliver messages via in-memory :class:`~aegean.election.LocalElectionState` (single process)."""

    __slots__ = ("_states",)

    def __init__(self, states: dict[str, LocalElectionState]) -> None:
        self._states = states

    def request_vote(self, peer_id: str, msg: RequestVoteMessage) -> bool:
        st = self._states[peer_id]
        return st.grant_request_vote(msg)

    def record_vote(self, peer_id: str, msg: VoteMessage) -> None:
        self._states[peer_id].record_vote(msg)
