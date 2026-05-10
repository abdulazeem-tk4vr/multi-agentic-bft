from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import asdict
from typing import Any, Callable, Protocol

from .decision_engine import DecisionEngine, DecisionEngineConfig
from .election import (
    LocalElectionState,
    as_refinement_list,
    local_election_states_for_experts,
    new_term_ack_from_mapping,
    recovery_acks_all_bottom,
    simulate_leader_election,
    select_recovery_ack,
)
from .election_transport import run_election_with_messenger
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
    create_proposal,
    create_timeout_vote,
    evaluate_quorum_status,
    now_ms,
    select_leader,
)
from .logutil import configure_aegean_file_logging, get_aegean_logger
from .refinement_state import PerAgentRefmRoundTrack
from .task_routing import build_refm_task, build_soln_task, refm_task_matches_round
from .types import (
    AegeanConfig,
    AegeanResult,
    AegeanRound,
    AgentVote,
    CommitCertificate,
    QuorumStatus,
    calculate_quorum_size,
    is_consensus_failed,
    validate_failstop_fault_bound,
)

_log = get_aegean_logger("protocol")


class Agent(Protocol):
    def execute(self, task: dict[str, Any]) -> dict[str, Any]: ...


def _accept_vote(agent_id: str, proposal_id: str, *, confidence: float = 1.0) -> AgentVote:
    return AgentVote(
        agent_id=agent_id,
        proposal_id=proposal_id,
        status="accept",
        confidence=confidence,
        timestamp=now_ms(),
    )


def _vote_from_ok_exec(
    agent_id: str,
    proposal_id: str,
    exec_r: dict[str, Any],
    confidence_threshold: float,
) -> tuple[AgentVote, Any | None, int]:
    """Map a successful agent ``execute`` result to accept vs excluded (low confidence) row."""
    val = exec_r["value"]
    meta = val.get("metadata") or {}
    conf = float(meta.get("confidence", 1.0))
    tok = int(meta.get("tokens_used", 0))
    out = val.get("output")
    if conf < confidence_threshold:
        return (
            AgentVote(
                agent_id=agent_id,
                proposal_id=proposal_id,
                status="timeout",
                confidence=conf,
                timestamp=now_ms(),
                reasoning="below confidence_threshold",
            ),
            None,
            tok,
        )
    return _accept_vote(agent_id, proposal_id, confidence=conf), out, tok


def _validate_exec_result_shape(exec_r: Any) -> str | None:
    """Return an error string when execute() result shape is invalid, else None."""
    if not isinstance(exec_r, dict):
        return "execute() must return a dict"
    ok_val = exec_r.get("ok")
    if not isinstance(ok_val, bool):
        return "execute() result must include boolean key 'ok'"
    if not ok_val:
        return None
    val = exec_r.get("value")
    if not isinstance(val, dict):
        return "execute() with ok=True must include dict key 'value'"
    if "output" not in val:
        return "execute() with ok=True must include value['output']"
    meta = val.get("metadata")
    if meta is not None and not isinstance(meta, dict):
        return "execute() metadata must be a dict when provided"
    return None


def _is_production_env(config: dict[str, Any]) -> bool:
    env_val = config.get("environment")
    if env_val is None:
        env_val = os.getenv("AEGEAN_ENV") or os.getenv("ENV") or os.getenv("APP_ENV")
    env = str(env_val or "").strip().lower()
    return env in {"prod", "production"}


def _agent_is_mock(agent: Any) -> bool:
    return str(getattr(agent.__class__, "__module__", "")).startswith("aegean.mocks")


def _join_expert_futures(
    experts: list[str],
    futures: dict[str, Future],
    *,
    timeout_ms: int,
    timeout_row: Callable[[str], tuple[AgentVote, Any | None, int]],
) -> tuple[list[tuple[AgentVote, Any | None, int]], bool]:
    """Wait (wall-clock) up to ``timeout_ms`` for all futures; canceled stragglers use ``timeout_row``."""
    timeout_s = max(int(timeout_ms), 1) / 1000.0
    fut_set = set(futures.values())
    done, not_done = wait(fut_set, timeout=timeout_s)
    wall_timed_out = bool(not_done)
    for fut in not_done:
        fut.cancel()
    rows: list[tuple[AgentVote, Any | None, int]] = []
    for eid in experts:
        fut = futures[eid]
        if fut in not_done:
            rows.append(timeout_row(eid))
            continue
        try:
            rows.append(fut.result())
        except Exception:
            rows.append(timeout_row(eid))
    return rows, wall_timed_out


class AegeanProtocol:
    pattern = "aegean"

    def __init__(self, config: AegeanConfig | None = None, event_bus: EventBus | None = None):
        self.config = config or AegeanConfig()
        self.event_bus = event_bus or EventBus()
        self.cancelled = False
        configure_aegean_file_logging()

    def cancel(self, _reason: str) -> None:
        self.cancelled = True

    def execute(self, config: dict[str, Any], agents: dict[str, Agent]) -> dict[str, Any]:
        """Run one session.

        Optional ``config`` keys: ``election_messenger`` (pluggable RequestVote/Vote RPC);
        ``refm_round_track_init`` — ``{agent_id: last_accepted_broadcast_round}`` to simulate
        persisted RefmSet round guards (multi-term / stale delivery scenarios).
        ``max_election_attempts`` overrides :class:`~aegean.types.AegeanConfig.max_election_attempts`
        for election stall retries (bump term until Vote quorum or cap).
        """

        experts: list[str] = config["experts"]
        n = len(experts)
        f = self.config.byzantine_tolerance
        try:
            validate_failstop_fault_bound(n, f)
        except ValueError as exc:
            _log.warning("startup validation failed: %s", exc)
            return {"ok": False, "error": str(exc)}
        quorum_r = calculate_quorum_size(n, f)
        _log.info(
            "protocol execute start session_id=%s N=%s f=%s R=%s alpha=%s beta=%s "
            "round_timeout_ms=%s confidence_threshold=%s max_election_attempts=%s",
            config.get("session_id"),
            n,
            f,
            quorum_r,
            self.config.alpha,
            self.config.beta,
            self.config.round_timeout_ms,
            self.config.confidence_threshold,
            self.config.max_election_attempts,
        )
        expert_set = set(experts)
        if len(experts) != len(expert_set):
            return {"ok": False, "error": "experts list must not contain duplicate ids"}
        agent_ids = set(agents.keys())
        if expert_set != agent_ids:
            missing = sorted(expert_set - agent_ids)
            extra = sorted(agent_ids - expert_set)
            parts: list[str] = []
            if missing:
                parts.append(f"no agent for experts: {missing}")
            if extra:
                parts.append(f"agents not listed in experts: {extra}")
            return {"ok": False, "error": "; ".join(parts)}
        if _is_production_env(config):
            for expert in experts:
                agent = agents.get(expert)
                if agent is not None and _agent_is_mock(agent):
                    return {
                        "ok": False,
                        "error": (
                            f"Mock agent not allowed in production environment: {expert} "
                            f"({agent.__class__.__module__}.{agent.__class__.__name__})"
                        ),
                    }

        start = now_ms()
        emit_protocol_started(
            self.event_bus,
            session_id=config["session_id"],
            agent_count=len(experts),
            aegean_config=asdict(self.config),
        )

        if self.cancelled:
            res = self._final_result(start, [], "error", None, 0, None)
            self._emit_done(res, config["session_id"])
            return {"ok": True, "value": res}

        leader_id = select_leader(experts, 0)
        rounds: list[AegeanRound] = []
        total_tokens = 0
        consensus_value: Any = None
        reason: str = "max_rounds"
        any_wall_timeout = False
        commit_certificate: CommitCertificate | None = None

        recovery_cfg = config.get("recovery")
        term_num = 1
        skipped_soln = False
        broadcast_bar = []
        if isinstance(recovery_cfg, dict):
            raw_acks = recovery_cfg.get("acks")
            if raw_acks:
                acks = [new_term_ack_from_mapping(x) for x in raw_acks]
                if not recovery_acks_all_bottom(acks):
                    picked = select_recovery_ack(acks)
                    if picked is not None:
                        leader_id = str(recovery_cfg.get("leader_id", leader_id))
                        term_num = picked.term
                        broadcast_bar = as_refinement_list(picked.refm_set)
                        skipped_soln = True
                        _log.info(
                            "recovery: skip Round 0 Soln term=%s leader=%s r_bar_len=%s",
                            term_num,
                            leader_id,
                            len(broadcast_bar),
                        )

        if agents.get(leader_id) is None:
            return {"ok": False, "error": f"Leader agent not found: {leader_id}"}

        el_terms = config.get("election_initial_terms")
        parsed_el: dict[str, int] | None = None
        if isinstance(el_terms, dict):
            parsed_el = {str(k): int(v) for k, v in el_terms.items()}

        raw_max_e = config.get("max_election_attempts")
        if raw_max_e is not None:
            try:
                max_election_tries = max(1, int(raw_max_e))
            except (TypeError, ValueError):
                max_election_tries = self.config.max_election_attempts
        else:
            max_election_tries = self.config.max_election_attempts

        election_states: dict[str, LocalElectionState] | None = None
        custom_messenger = config.get("election_messenger")
        if custom_messenger is None:
            election_states = local_election_states_for_experts(experts, parsed_el)

        attempt_term = term_num
        el_out = None
        for election_try in range(max_election_tries):
            if custom_messenger is not None:
                el_out = run_election_with_messenger(
                    experts,
                    f,
                    term=attempt_term,
                    candidate_id=leader_id,
                    messenger=custom_messenger,
                )
            else:
                assert election_states is not None
                el_out = simulate_leader_election(
                    experts,
                    f,
                    term=attempt_term,
                    candidate_id=leader_id,
                    states=election_states,
                )
            if el_out.has_vote_quorum:
                term_num = attempt_term
                if election_try > 0:
                    _log.info(
                        "election recovered after term bump: term=%s (after %s stall retries)",
                        term_num,
                        election_try,
                    )
                break
            _log.info(
                "election stall: no Vote quorum at term=%s (try %s/%s), bumping term",
                attempt_term,
                election_try + 1,
                max_election_tries,
            )
            attempt_term += 1
        else:
            return {
                "ok": False,
                "error": (
                    f"Leader election failed after {max_election_tries} term attempts "
                    f"(last term tried {attempt_term})"
                ),
            }

        if skipped_soln and len(broadcast_bar) < quorum_r:
            emit_protocol_iteration(
                self.event_bus, 0, self.config.max_rounds, "recovery_insufficient_bar", config["session_id"]
            )
            res = self._final_result(start, rounds, "max_rounds", None, 0, None)
            self._emit_done(res, config["session_id"])
            return {"ok": True, "value": res}

        if not skipped_soln:
            round_start0 = now_ms()
            emit_aegean_round_started(
                self.event_bus, 0, self.config.max_rounds, leader_id, config["session_id"]
            )
            soln_pid = f"soln-{config['session_id']}-0"

            def _collect_soln(eid: str) -> tuple[AgentVote, Any | None, int]:
                ag = agents.get(eid)
                if ag is None:
                    return create_timeout_vote(eid, soln_pid), None, 0
                exec_r = ag.execute(build_soln_task(config["task"], round_num=0, agent_id=eid))
                shape_err = _validate_exec_result_shape(exec_r)
                if shape_err is not None:
                    _log.warning("invalid execute() result for agent=%s phase=soln: %s", eid, shape_err)
                    return create_timeout_vote(eid, soln_pid), None, 0
                if not exec_r.get("ok", False):
                    return create_timeout_vote(eid, soln_pid), None, 0
                return _vote_from_ok_exec(
                    eid, soln_pid, exec_r, self.config.confidence_threshold
                )

            with ThreadPoolExecutor(max_workers=max(4, n)) as pool:
                soln_futs = {e: pool.submit(_collect_soln, e) for e in experts}
                soln_rows, soln_wall_to = _join_expert_futures(
                    experts,
                    soln_futs,
                    timeout_ms=self.config.round_timeout_ms,
                    timeout_row=lambda eid: (create_timeout_vote(eid, soln_pid), None, 0),
                )
            if soln_wall_to:
                any_wall_timeout = True

            soln_votes: list[AgentVote] = []
            soln_out: list[Any | None] = []
            t0 = 0
            for eid, (v, o, tok) in zip(experts, soln_rows, strict=True):
                soln_votes.append(v)
                soln_out.append(o if v.status == "accept" else None)
                t0 += tok
                emit_aegean_vote_collected(
                    self.event_bus,
                    0,
                    eid,
                    len(soln_votes),
                    quorum_r,
                    config["session_id"],
                )

            total_tokens += t0
            li = experts.index(leader_id)
            if soln_votes[li].status != "accept":
                return {"ok": False, "error": "Leader soln generation failed"}

            q0 = evaluate_quorum_status(
                EvaluateQuorumOptions(votes=soln_votes, total_agents=n, byzantine_tolerance=f)
            )
            quorum0 = QuorumStatus(**q0)
            broadcast_bar = [o for o in soln_out if o is not None]
            proposal0 = create_proposal(0, leader_id, list(broadcast_bar))
            rounds.append(
                AegeanRound(
                    round_number=0,
                    phase="proposal",
                    leader_id=leader_id,
                    proposal=proposal0,
                    votes=soln_votes,
                    quorum_status=quorum0,
                    start_time=round_start0,
                    end_time=now_ms(),
                )
            )

            if quorum0.has_quorum:
                emit_aegean_quorum_detected(
                    self.event_bus,
                    0,
                    quorum0.accepts,
                    self.config.early_termination,
                    config["session_id"],
                )

            if not quorum0.has_quorum:
                emit_protocol_iteration(
                    self.event_bus, 0, self.config.max_rounds, "no_soln_quorum", config["session_id"]
                )
                soln_term: str = "timeout" if any_wall_timeout else "max_rounds"
                res = self._final_result(start, rounds, soln_term, None, total_tokens, None)
                self._emit_done(res, config["session_id"])
                return {"ok": True, "value": res}

        engine = DecisionEngine(DecisionEngineConfig(self.config.alpha, self.config.beta))
        engine.on_new_term(term_num)

        ref_round_tracks = {e: PerAgentRefmRoundTrack() for e in experts}
        ri = config.get("refm_round_track_init")
        if isinstance(ri, dict):
            for key, val in ri.items():
                kid = str(key)
                if kid not in ref_round_tracks:
                    continue
                try:
                    ref_round_tracks[kid].last_accepted_broadcast_round = int(val)
                except (TypeError, ValueError):
                    _log.warning("ignore invalid refm_round_track_init[%s]=%r", key, val)

        ref_round = 1
        while ref_round <= self.config.max_rounds:
            if self.cancelled:
                reason = "error"
                break

            rs = now_ms()
            emit_aegean_round_started(
                self.event_bus, ref_round, self.config.max_rounds, leader_id, config["session_id"]
            )
            ref_pid = f"refm-{config['session_id']}-t{term_num}-r{ref_round}"

            def _collect_refm(eid: str) -> tuple[AgentVote, Any | None, int]:
                ag = agents.get(eid)
                if ag is None:
                    return create_timeout_vote(eid, ref_pid), None, 0
                tsk = build_refm_task(
                    config["task"],
                    refinement_set=list(broadcast_bar),
                    term_num=term_num,
                    round_num=ref_round,
                    agent_id=eid,
                )
                if not refm_task_matches_round(tsk, ref_round):
                    return create_timeout_vote(eid, ref_pid), None, 0
                if not ref_round_tracks[eid].try_accept_refm_broadcast(ref_round):
                    return create_timeout_vote(eid, ref_pid), None, 0
                exec_r = ag.execute(tsk)
                shape_err = _validate_exec_result_shape(exec_r)
                if shape_err is not None:
                    _log.warning("invalid execute() result for agent=%s phase=refm: %s", eid, shape_err)
                    return create_timeout_vote(eid, ref_pid), None, 0
                if not exec_r.get("ok", False):
                    return create_timeout_vote(eid, ref_pid), None, 0
                return _vote_from_ok_exec(
                    eid, ref_pid, exec_r, self.config.confidence_threshold
                )

            with ThreadPoolExecutor(max_workers=max(4, n)) as pool:
                ref_futs = {e: pool.submit(_collect_refm, e) for e in experts}
                ref_rows, ref_wall_to = _join_expert_futures(
                    experts,
                    ref_futs,
                    timeout_ms=self.config.round_timeout_ms,
                    timeout_row=lambda eid: (create_timeout_vote(eid, ref_pid), None, 0),
                )
            if ref_wall_to:
                any_wall_timeout = True

            ref_votes: list[AgentVote] = []
            ref_out: list[Any | None] = []
            tr = 0
            for eid, (v, o, tok) in zip(experts, ref_rows, strict=True):
                ref_votes.append(v)
                ref_out.append(o if v.status == "accept" else None)
                tr += tok
                emit_aegean_vote_collected(
                    self.event_bus,
                    ref_round,
                    eid,
                    len(ref_votes),
                    quorum_r,
                    config["session_id"],
                )

            total_tokens += tr
            qref = evaluate_quorum_status(
                EvaluateQuorumOptions(votes=ref_votes, total_agents=n, byzantine_tolerance=f)
            )
            qref_s = QuorumStatus(**qref)
            ref_proposal = create_proposal(ref_round, leader_id, list(broadcast_bar))
            t_done = now_ms()

            if not qref_s.has_quorum:
                rounds.append(
                    AegeanRound(
                        round_number=ref_round,
                        phase="refinement",
                        leader_id=leader_id,
                        proposal=ref_proposal,
                        votes=ref_votes,
                        quorum_status=qref_s,
                        start_time=rs,
                        end_time=t_done,
                    )
                )
                if self.config.early_termination and is_consensus_failed(qref_s, n):
                    emit_protocol_iteration(
                        self.event_bus,
                        ref_round - 1,
                        self.config.max_rounds,
                        "max_reached",
                        config["session_id"],
                    )
                    break
                emit_protocol_iteration(
                    self.event_bus,
                    ref_round - 1,
                    self.config.max_rounds,
                    "no_refm_quorum",
                    config["session_id"],
                )
                ref_round += 1
                continue

            emit_aegean_quorum_detected(
                self.event_bus,
                ref_round,
                qref_s.accepts,
                self.config.early_termination,
                config["session_id"],
            )

            ref_vals = [ref_out[i] for i in range(n) if ref_votes[i].status == "accept"]
            decision = engine.step(r_bar_prev=list(broadcast_bar), current_round_outputs=ref_vals)
            _log.debug(
                "ref_round=%s committed=%s stability=%s candidate=%s",
                ref_round,
                decision.committed,
                decision.stability,
                decision.eligible_candidate,
            )
            t_after_decision = now_ms()
            rounds.append(
                AegeanRound(
                    round_number=ref_round,
                    phase="refinement",
                    leader_id=leader_id,
                    proposal=ref_proposal,
                    votes=ref_votes,
                    quorum_status=qref_s,
                    start_time=rs,
                    end_time=t_after_decision,
                    decision_committed=decision.committed,
                    decision_stability=decision.stability,
                    decision_eligible=decision.eligible_candidate,
                    decision_overturned=decision.overturned,
                )
            )

            if decision.committed:
                consensus_value = decision.value
                reason = "consensus"
                supporting = tuple(
                    eid for eid, rv in zip(experts, ref_votes, strict=True) if rv.status == "accept"
                )
                commit_certificate = CommitCertificate(
                    term_num=term_num,
                    refinement_round=ref_round,
                    leader_id=leader_id,
                    committed_value=consensus_value,
                    quorum_size_r=quorum_r,
                    alpha=self.config.alpha,
                    beta=self.config.beta,
                    supporting_refm_agent_ids=supporting,
                )
                commit_prop = create_proposal(ref_round, leader_id, [consensus_value])
                rounds.append(
                    AegeanRound(
                        round_number=ref_round,
                        phase="commit",
                        leader_id=leader_id,
                        proposal=commit_prop,
                        votes=[],
                        quorum_status=QuorumStatus(
                            required=quorum_r,
                            accepts=len(supporting),
                            rejects=0,
                            pending=0,
                            has_quorum=True,
                            consensus_reached=True,
                        ),
                        start_time=t_after_decision,
                        end_time=now_ms(),
                    )
                )
                emit_protocol_iteration(
                    self.event_bus,
                    ref_round - 1,
                    self.config.max_rounds,
                    "converged",
                    config["session_id"],
                )
                break

            if self.config.early_termination and is_consensus_failed(qref_s, n):
                emit_protocol_iteration(
                    self.event_bus,
                    ref_round - 1,
                    self.config.max_rounds,
                    "max_reached",
                    config["session_id"],
                )
                break

            nxt = [ref_out[i] for i in range(n) if ref_votes[i].status == "accept"]
            if len(nxt) < quorum_r:
                break
            broadcast_bar = nxt

            emit_protocol_iteration(
                self.event_bus,
                ref_round - 1,
                self.config.max_rounds,
                "in_progress",
                config["session_id"],
            )
            ref_round += 1

        if reason not in ("consensus", "error") and any_wall_timeout:
            reason = "timeout"

        res = self._final_result(start, rounds, reason, consensus_value, total_tokens, commit_certificate)
        self._emit_done(res, config["session_id"])
        return {"ok": True, "value": res}

    def _final_result(
        self,
        start_ms: int,
        rounds: list[AegeanRound],
        reason: str,
        consensus_value: Any | None,
        total_tokens: int,
        commit_certificate: CommitCertificate | None,
    ) -> AegeanResult:
        return AegeanResult(
            consensus_value=consensus_value,
            consensus_reached=reason == "consensus",
            total_rounds=len(rounds),
            total_duration_ms=now_ms() - start_ms,
            tokens_used=total_tokens,
            rounds=rounds,
            termination_reason=reason,  # type: ignore[arg-type]
            commit_certificate=commit_certificate,
        )

    def _emit_done(self, aegean_result: AegeanResult, session_id: str) -> None:
        emit_protocol_completed(
            self.event_bus,
            success=aegean_result.consensus_reached,
            iterations=aegean_result.total_rounds,
            duration_ms=aegean_result.total_duration_ms,
            session_id=session_id,
        )


def create_aegean_protocol(config: AegeanConfig | None = None, event_bus: EventBus | None = None) -> AegeanProtocol:
    return AegeanProtocol(config=config, event_bus=event_bus)


class AegeanSessionError(RuntimeError):
    """Raised when :func:`run_aegean_session` cannot return a result (bad config, missing agents, election abort, etc.).

    A normal session that ends **without** consensus (e.g. ``max_rounds``) still returns an
    :class:`~aegean.types.AegeanResult` with ``consensus_reached=False`` — that is **not** an error.
    """


def run_aegean_session(
    session_cfg: dict[str, Any],
    agents: dict[str, Agent],
    *,
    config: AegeanConfig | None = None,
    event_bus: EventBus | None = None,
) -> AegeanResult:
    """Run one Aegean session and return :class:`~aegean.types.AegeanResult`.

    This is the usual **“pass agents → get outcome”** entry point. It wraps
    :func:`create_aegean_protocol` and :meth:`AegeanProtocol.execute` and unwraps ``value``.

    For **multiple sessions** with **`cancel()`** on the same config/bus, use :class:`AegeanRunner`
    instead. Use :class:`AegeanProtocol` directly if you need the raw ``{"ok": bool, ...}`` dict.

    When :attr:`~aegean.types.AegeanConfig.session_trace` is True or env ``AEGEAN_SESSION_TRACE``
    is set (``1``, ``true``, ``yes``, ``on``), prints a human-readable trace to stderr after success;
    see :func:`~aegean.session_trace.print_session_trace`.

    Raises:
        AegeanSessionError: When ``execute`` returns ``ok=False`` (validation, leader Soln failure, election failed, …).
    """
    cfg = config or AegeanConfig()
    protocol = create_aegean_protocol(config=cfg, event_bus=event_bus)
    out = protocol.execute(session_cfg, agents)
    if not out["ok"]:
        raise AegeanSessionError(out.get("error", str(out)))
    result: AegeanResult = out["value"]
    from .session_trace import print_session_trace, session_trace_enabled

    if session_trace_enabled(protocol.config):
        experts_list = list(session_cfg.get("experts") or [])
        sid = str(session_cfg.get("session_id", ""))
        task = session_cfg.get("task")
        desc: str | None = None
        if isinstance(task, dict):
            raw_d = task.get("description")
            if isinstance(raw_d, str):
                desc = raw_d
        print_session_trace(
            result,
            config=protocol.config,
            experts=experts_list,
            session_id=sid,
            event_bus=protocol.event_bus,
            task_description=desc,
        )
    return result


class AegeanRunner:
    """Combine **convenient** :meth:`run` (returns :class:`~aegean.types.AegeanResult`, raises on hard errors)
    with a **stable** :class:`AegeanProtocol` handle for :meth:`cancel` and repeated sessions.

    After :meth:`cancel`, this instance stays cancelled—create a **new** ``AegeanRunner`` for further work.
    """

    __slots__ = ("_protocol",)

    def __init__(self, config: AegeanConfig | None = None, event_bus: EventBus | None = None) -> None:
        self._protocol = create_aegean_protocol(config=config, event_bus=event_bus)

    @property
    def protocol(self) -> AegeanProtocol:
        return self._protocol

    def cancel(self, reason: str = "") -> None:
        """Request cooperative cancellation; see :meth:`AegeanProtocol.cancel`."""
        self._protocol.cancel(reason)

    def run(self, session_cfg: dict[str, Any], agents: dict[str, Agent]) -> AegeanResult:
        """Run one session on the wrapped protocol (same semantics as :func:`run_aegean_session`)."""
        out = self._protocol.execute(session_cfg, agents)
        if not out["ok"]:
            raise AegeanSessionError(out.get("error", str(out)))
        result: AegeanResult = out["value"]
        from .session_trace import print_session_trace, session_trace_enabled

        if session_trace_enabled(self._protocol.config):
            experts_list = list(session_cfg.get("experts") or [])
            sid = str(session_cfg.get("session_id", ""))
            task = session_cfg.get("task")
            desc: str | None = None
            if isinstance(task, dict):
                raw_d = task.get("description")
                if isinstance(raw_d, str):
                    desc = raw_d
            print_session_trace(
                result,
                config=self._protocol.config,
                experts=experts_list,
                session_id=sid,
                event_bus=self._protocol.event_bus,
                task_description=desc,
            )
        return result
