from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import re
import time

from .logutil import get_aegean_logger
from .types import AgentVote, Proposal, calculate_quorum_size

_log = get_aegean_logger("quorum")

ACCEPT_PATTERN = re.compile(r"accept|approve|agree|yes", re.IGNORECASE)
REJECT_PATTERN = re.compile(r"reject|disapprove|disagree|no", re.IGNORECASE)


def now_ms() -> int:
    return int(time.time() * 1000)


def parse_vote_status(output: Any) -> dict[str, Any]:
    output_str = output if isinstance(output, str) else json.dumps(output)
    is_reject = bool(REJECT_PATTERN.search(output_str))
    is_accept = (not is_reject) and bool(ACCEPT_PATTERN.search(output_str))
    return {
        "status": "reject" if is_reject else ("accept" if is_accept else "pending"),
        "confidence": 0.8 if (is_accept or is_reject) else 0.5,
    }


def extract_reasoning(output: Any, max_length: int = 500) -> str:
    output_str = output if isinstance(output, str) else json.dumps(output)
    return output_str[:max_length]


def create_timeout_vote(agent_id: str, proposal_id: str) -> AgentVote:
    return AgentVote(
        agent_id=agent_id,
        proposal_id=proposal_id,
        status="timeout",
        confidence=0.0,
        timestamp=now_ms(),
        reasoning="Agent did not respond in time",
    )


def create_leader_vote(leader_id: str, proposal_id: str) -> AgentVote:
    return AgentVote(
        agent_id=leader_id,
        proposal_id=proposal_id,
        status="accept",
        confidence=1.0,
        timestamp=now_ms(),
        reasoning="Leader accepts own proposal",
    )


def create_vote_from_output(
    agent_id: str, proposal_id: str, output: Any, tokens_used: int
) -> dict[str, Any]:
    parsed = parse_vote_status(output)
    return {
        "vote": AgentVote(
            agent_id=agent_id,
            proposal_id=proposal_id,
            status=parsed["status"],
            confidence=parsed["confidence"],
            timestamp=now_ms(),
            reasoning=extract_reasoning(output),
        ),
        "tokens_used": tokens_used,
    }


def create_proposal_task(task: dict[str, Any], round_number: int) -> dict[str, Any]:
    return {
        **task,
        "id": f"{task['id']}-proposal-{round_number}",
        "description": (
            f"{task['description']}\n\nAs the leader for round {round_number + 1}, "
            "propose a solution."
        ),
    }


def create_proposal(round_number: int, leader_id: str, output: Any) -> Proposal:
    return Proposal(
        proposal_id=f"proposal-{round_number}-{now_ms()}",
        round=round_number,
        leader_id=leader_id,
        value=output,
        timestamp=now_ms(),
    )


def create_vote_task(proposal: Proposal, agent_id: str) -> dict[str, Any]:
    return {
        "id": f"vote-{proposal.proposal_id}-{agent_id}",
        "description": (
            "Review the following proposal and vote ACCEPT or REJECT.\n\n"
            f"Proposal:\n{json.dumps(proposal.value, indent=2)}"
        ),
        "context": {"metadata": {"proposal": proposal}},
    }


def select_leader(experts: list[str], round_number: int) -> str:
    if not experts:
        return ""
    seed = round_number * 2654435761
    idx = abs(seed) % len(experts)
    return experts[idx]


def dedupe_votes_by_agent_last_wins(
    votes: list[AgentVote],
) -> tuple[list[AgentVote], frozenset[str]]:
    """One tally slot per ``agent_id``: later entries override earlier (duplicate ids do not inflate R).

    Returns ``(unique_votes, duplicate_agent_ids)`` where duplicates were detected when the same
    ``agent_id`` appeared more than once in ``votes``.
    """
    last_by_agent: dict[str, AgentVote] = {}
    duplicate_ids: set[str] = set()
    for v in votes:
        if v.agent_id in last_by_agent:
            duplicate_ids.add(v.agent_id)
        last_by_agent[v.agent_id] = v
    unique = list(last_by_agent.values())
    return unique, frozenset(duplicate_ids)


@dataclass(frozen=True)
class EvaluateQuorumOptions:
    votes: list[AgentVote]
    total_agents: int
    byzantine_tolerance: int


def evaluate_quorum_status(opts: EvaluateQuorumOptions) -> dict[str, Any]:
    """Tally accepts/rejects/pending with **unique agent ids**; same **R** as Soln/Refm (via ``calculate_quorum_size``)."""
    required = calculate_quorum_size(opts.total_agents, opts.byzantine_tolerance)
    unique_votes, duplicate_ids = dedupe_votes_by_agent_last_wins(opts.votes)
    if duplicate_ids:
        _log.warning("duplicate vote entries for agent ids %s (using last vote per id for quorum tally)", sorted(duplicate_ids))
    accepts = len([v for v in unique_votes if v.status == "accept"])
    rejects = len([v for v in unique_votes if v.status == "reject"])
    pending = len([v for v in unique_votes if v.status in ("pending", "timeout")])
    has_quorum = accepts >= required
    return {
        "required": required,
        "accepts": accepts,
        "rejects": rejects,
        "pending": pending,
        "has_quorum": has_quorum,
        "consensus_reached": has_quorum,
    }
