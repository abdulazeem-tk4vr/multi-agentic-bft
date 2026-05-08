from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
import math

AegeanPhase = Literal["proposal", "voting", "commit", "done"]
AgentVoteStatus = Literal["pending", "accept", "reject", "timeout", "byzantine"]
TerminationReason = Literal["consensus", "max_rounds", "timeout", "byzantine_failure", "error"]


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


@dataclass(frozen=True)
class AegeanResult:
    consensus_value: Any
    consensus_reached: bool
    total_rounds: int
    total_duration_ms: int
    tokens_used: int
    rounds: list[AegeanRound]
    termination_reason: TerminationReason


@dataclass(frozen=True)
class AegeanConfig:
    max_rounds: int = 3
    round_timeout_ms: int = 60000
    byzantine_tolerance: int = 0
    confidence_threshold: float = 0.7
    early_termination: bool = True


def calculate_quorum_size(total_agents: int, byzantine_tolerance: int) -> int:
    return int(math.ceil((total_agents + byzantine_tolerance + 1) / 2))


def has_accept_quorum(quorum: QuorumStatus) -> bool:
    return quorum.accepts >= quorum.required


def is_consensus_failed(quorum: QuorumStatus, total_agents: int) -> bool:
    return quorum.rejects > total_agents - quorum.required
