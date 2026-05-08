from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Any, Protocol
import time

from .events import (
    EventBus,
    emit_aegean_quorum_detected,
    emit_aegean_round_started,
    emit_aegean_vote_collected,
    emit_protocol_completed,
    emit_protocol_iteration,
    emit_protocol_started,
)
from .helpers_utils import (
    EvaluateQuorumOptions,
    create_leader_vote,
    create_proposal,
    create_proposal_task,
    create_timeout_vote,
    create_vote_from_output,
    create_vote_task,
    evaluate_quorum_status,
    now_ms,
    select_leader,
)
from .types import AegeanConfig, AegeanResult, AegeanRound, AgentVote, QuorumStatus, is_consensus_failed


class Agent(Protocol):
    def execute(self, task: dict[str, Any]) -> dict[str, Any]: ...


class AegeanProtocol:
    pattern = "aegean"

    def __init__(self, config: AegeanConfig | None = None, event_bus: EventBus | None = None):
        self.config = config or AegeanConfig()
        self.event_bus = event_bus or EventBus()
        self.cancelled = False

    def cancel(self, _reason: str) -> None:
        self.cancelled = True

    def execute(self, config: dict[str, Any], agents: dict[str, Agent]) -> dict[str, Any]:
        experts: list[str] = config["experts"]
        # 3f+1 gives 1 for f=0, but 3 is the structural minimum for meaningful quorum
        min_agents = max(3, 3 * self.config.byzantine_tolerance + 1)
        if len(experts) < min_agents:
            return {"ok": False, "error": f"Aegean requires at least {min_agents} agents"}
        for expert in experts:
            if expert not in agents:
                return {"ok": False, "error": f"Agent not found: {expert}"}

        start = now_ms()
        emit_protocol_started(
            self.event_bus,
            session_id=config["session_id"],
            agent_count=len(experts),
            aegean_config=asdict(self.config),
        )

        rounds: list[AegeanRound] = []
        total_tokens = 0
        consensus_value: Any = None
        reason: str = "max_rounds"

        for round_number in range(self.config.max_rounds):
            if self.cancelled:
                reason = "error"
                break

            result = self._execute_round(round_number, config, agents)
            if not result["ok"]:
                return result
            round_data: AegeanRound = result["round_data"]
            tokens_used: int = result["tokens_used"]

            rounds.append(round_data)
            total_tokens += tokens_used

            if round_data.quorum_status.consensus_reached:
                consensus_value = round_data.proposal.value if round_data.proposal else None
                reason = "consensus"
                emit_protocol_iteration(
                    self.event_bus, round_number, self.config.max_rounds, "converged", config["session_id"]
                )
                break

            if self.config.early_termination and is_consensus_failed(round_data.quorum_status, len(experts)):
                reason = "max_rounds"
                emit_protocol_iteration(
                    self.event_bus, round_number, self.config.max_rounds, "max_reached", config["session_id"]
                )
                break

            emit_protocol_iteration(
                self.event_bus, round_number, self.config.max_rounds, "in_progress", config["session_id"]
            )

        aegean_result = AegeanResult(
            consensus_value=consensus_value,
            consensus_reached=reason == "consensus",
            total_rounds=len(rounds),
            total_duration_ms=now_ms() - start,
            tokens_used=total_tokens,
            rounds=rounds,
            termination_reason=reason,  # type: ignore[arg-type]
        )
        emit_protocol_completed(
            self.event_bus,
            success=aegean_result.consensus_reached,
            iterations=aegean_result.total_rounds,
            duration_ms=aegean_result.total_duration_ms,
            session_id=config["session_id"],
        )
        return {"ok": True, "value": aegean_result}

    def _execute_round(self, round_number: int, config: dict[str, Any], agents: dict[str, Agent]) -> dict[str, Any]:
        round_start = now_ms()
        experts: list[str] = config["experts"]
        leader_id = select_leader(experts, round_number)
        leader = agents.get(leader_id)
        if leader is None:
            return {"ok": False, "error": f"Leader agent not found: {leader_id}"}

        emit_aegean_round_started(
            self.event_bus, round_number, self.config.max_rounds, leader_id, config["session_id"]
        )

        proposal_task = create_proposal_task(config["task"], round_number)
        proposal_exec = leader.execute(proposal_task)
        if not proposal_exec.get("ok", False):
            return {"ok": False, "error": "Leader proposal generation failed"}
        proposal_output = proposal_exec["value"]["output"]
        proposal_tokens = proposal_exec["value"]["metadata"]["tokens_used"]
        proposal = create_proposal(round_number, leader_id, proposal_output)

        voter_ids = [e for e in experts if e != leader_id]
        required_quorum = evaluate_quorum_status(
            EvaluateQuorumOptions(votes=[], total_agents=len(experts), byzantine_tolerance=self.config.byzantine_tolerance)
        )["required"]

        def _collect_vote(voter_id: str) -> tuple[AgentVote, int]:
            agent = agents.get(voter_id)
            if agent is None:
                return create_timeout_vote(voter_id, proposal.proposal_id), 0
            vote_exec = agent.execute(create_vote_task(proposal, voter_id))
            if not vote_exec.get("ok", False):
                return create_timeout_vote(voter_id, proposal.proposal_id), 0
            result = create_vote_from_output(
                voter_id,
                proposal.proposal_id,
                vote_exec["value"]["output"],
                vote_exec["value"]["metadata"]["tokens_used"],
            )
            return result["vote"], result["tokens_used"]

        with ThreadPoolExecutor() as pool:
            futures = {voter_id: pool.submit(_collect_vote, voter_id) for voter_id in voter_ids}

        votes: list[AgentVote] = []
        vote_tokens = 0
        for voter_id in voter_ids:
            vote, tokens = futures[voter_id].result()
            votes.append(vote)
            vote_tokens += tokens
            emit_aegean_vote_collected(
                self.event_bus, round_number, voter_id, len(votes), required_quorum, config["session_id"]
            )

        votes.append(create_leader_vote(leader_id, proposal.proposal_id))
        quorum_dict = evaluate_quorum_status(
            EvaluateQuorumOptions(
                votes=votes, total_agents=len(experts), byzantine_tolerance=self.config.byzantine_tolerance
            )
        )
        quorum = QuorumStatus(**quorum_dict)
        if quorum.has_quorum:
            emit_aegean_quorum_detected(
                self.event_bus,
                round_number,
                quorum.accepts,
                self.config.early_termination,
                config["session_id"],
            )

        round_data = AegeanRound(
            round_number=round_number,
            phase="done",
            leader_id=leader_id,
            proposal=proposal,
            votes=votes,
            quorum_status=quorum,
            start_time=round_start,
            end_time=now_ms(),
        )
        return {"ok": True, "round_data": round_data, "tokens_used": proposal_tokens + vote_tokens}


def create_aegean_protocol(config: AegeanConfig | None = None, event_bus: EventBus | None = None) -> AegeanProtocol:
    return AegeanProtocol(config=config, event_bus=event_bus)
