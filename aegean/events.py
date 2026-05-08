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
                "maxRounds": aegean_config["max_rounds"],
                "confidenceThreshold": aegean_config["confidence_threshold"],
                "byzantineTolerance": aegean_config["byzantine_tolerance"],
                "agentCount": agent_count,
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
