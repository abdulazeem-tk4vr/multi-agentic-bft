from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventBus:
    emitted_events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, topic: str, payload: dict[str, Any], session_id: str | None = None) -> None:
        event = {"topic": topic, "payload": payload}
        if session_id is not None:
            event["session_id"] = session_id
        self.emitted_events.append(event)


def emit_protocol_started(
    bus: EventBus, session_id: str, agent_count: int, aegean_config: dict[str, Any]
) -> None:
    bus.emit(
        "protocol.started",
        {
            "protocolType": "aegean",
            "config": {
                "maxRounds": aegean_config.get("max_rounds", 3),
                "confidenceThreshold": aegean_config.get("confidence_threshold", 0.7),
                "byzantineTolerance": aegean_config.get("byzantine_tolerance", 0),
                "agentCount": agent_count,
                "alphaQuorum": aegean_config.get("alpha", 2),
                "betaStability": aegean_config.get("beta", 2),
            },
        },
        session_id=session_id,
    )


def emit_protocol_iteration(
    bus: EventBus, round_number: int, max_rounds: int, status: str, session_id: str
) -> None:
    bus.emit(
        "protocol.iteration",
        {"round": round_number + 1, "maxRounds": max_rounds, "status": status},
        session_id=session_id,
    )


def emit_protocol_completed(
    bus: EventBus, success: bool, iterations: int, duration_ms: int, session_id: str
) -> None:
    bus.emit(
        "protocol.completed",
        {"success": success, "iterations": iterations, "durationMs": duration_ms},
        session_id=session_id,
    )


def emit_aegean_round_started(
    bus: EventBus, round_number: int, max_rounds: int, leader_id: str, session_id: str
) -> None:
    bus.emit(
        "protocol.aegean.round_started",
        {"round": round_number, "maxRounds": max_rounds, "leaderId": leader_id},
        session_id=session_id,
    )


def emit_aegean_vote_collected(
    bus: EventBus,
    round_number: int,
    voter_id: str,
    vote_count: int,
    required_quorum: int,
    session_id: str,
) -> None:
    bus.emit(
        "protocol.aegean.vote_collected",
        {
            "round": round_number,
            "voterId": voter_id,
            "voteCount": vote_count,
            "requiredQuorum": required_quorum,
        },
        session_id=session_id,
    )


def emit_aegean_quorum_detected(
    bus: EventBus, round_number: int, quorum_size: int, early_termination: bool, session_id: str
) -> None:
    bus.emit(
        "protocol.aegean.quorum_detected",
        {"round": round_number, "quorumSize": quorum_size, "earlyTermination": early_termination},
        session_id=session_id,
    )


def emit_aegean_request_vote_sent(
    bus: EventBus, *, term_num: int, candidate_id: str, attempt: int, max_attempts: int, session_id: str
) -> None:
    bus.emit(
        "protocol.aegean.request_vote_sent",
        {
            "termNum": term_num,
            "candidateId": candidate_id,
            "attempt": attempt,
            "maxAttempts": max_attempts,
        },
        session_id=session_id,
    )


def emit_aegean_vote_quorum_result(
    bus: EventBus,
    *,
    term_num: int,
    candidate_id: str,
    has_quorum: bool,
    try_num: int,
    max_attempts: int,
    session_id: str,
) -> None:
    bus.emit(
        "protocol.aegean.vote_quorum_result",
        {
            "termNum": term_num,
            "candidateId": candidate_id,
            "hasQuorum": has_quorum,
            "attempt": try_num,
            "maxAttempts": max_attempts,
        },
        session_id=session_id,
    )


def emit_aegean_recovery_selected(
    bus: EventBus,
    *,
    term_num: int,
    leader_id: str,
    round_num: int,
    refm_set_size: int,
    session_id: str,
) -> None:
    bus.emit(
        "protocol.aegean.recovery_selected",
        {
            "termNum": term_num,
            "leaderId": leader_id,
            "roundNum": round_num,
            "refmSetSize": refm_set_size,
        },
        session_id=session_id,
    )


def emit_aegean_new_term_started(
    bus: EventBus, *, term_num: int, leader_id: str, session_id: str
) -> None:
    bus.emit(
        "protocol.aegean.new_term_started",
        {"termNum": term_num, "leaderId": leader_id},
        session_id=session_id,
    )


def emit_aegean_new_term_ack_received(
    bus: EventBus,
    *,
    term_num: int,
    from_agent_id: str,
    ack_term: int,
    ack_round_num: int,
    has_refm_set: bool,
    session_id: str,
) -> None:
    bus.emit(
        "protocol.aegean.new_term_ack_received",
        {
            "termNum": term_num,
            "fromAgentId": from_agent_id,
            "ackTerm": ack_term,
            "ackRoundNum": ack_round_num,
            "hasRefmSet": has_refm_set,
        },
        session_id=session_id,
    )
