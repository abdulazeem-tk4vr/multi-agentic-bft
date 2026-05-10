"""Optional human-readable console trace for an :class:`~aegean.types.AegeanResult`.

ASCII-only, fixed-width friendly for Windows terminals.
"""

from __future__ import annotations

import sys
from typing import IO, Any, TextIO

from .events import EventBus
from .types import AegeanConfig, AegeanResult, AegeanRound, AgentVote, calculate_quorum_size

_W = 76


def session_trace_enabled(config: AegeanConfig) -> bool:
    import os

    if config.session_trace:
        return True
    v = (os.getenv("AEGEAN_SESSION_TRACE") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def print_session_trace(
    result: AegeanResult,
    *,
    config: AegeanConfig,
    experts: list[str],
    session_id: str,
    event_bus: EventBus,
    task_description: str | None = None,
    stream: TextIO | None = None,
    run_title: str | None = None,
) -> None:
    """Print summary, compact timeline, and per-round detail. Defaults to :data:`sys.stderr`."""
    out: TextIO = stream if stream is not None else sys.stderr
    _print_full_report(
        result,
        experts=experts,
        aegean_cfg=config,
        session_id=session_id,
        bus=event_bus,
        task_description=task_description,
        run_title=run_title,
        file=out,
    )


def _rule(file: IO[str], ch: str = "=") -> None:
    print(ch * _W, file=file, flush=True)


def _p(file: IO[str], msg: str) -> None:
    print(msg, file=file, flush=True)


def _snippet(x: Any, max_len: int = 100) -> str:
    s = repr(x) if not isinstance(x, str) else x
    s = s.replace("\n", " ")
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _text_preview(text: Any, max_chars: int = 160) -> tuple[str, int]:
    if text is None:
        return "(none)", 0
    s = text if isinstance(text, str) else repr(text)
    n = len(s)
    one = s.replace("\r", "").replace("\n", " ")
    if len(one) > max_chars:
        return one[: max_chars - 3] + "...", n
    return one, n


def _print_compact_events(bus: EventBus, session_id: str, *, r_quorum: int, file: IO[str]) -> None:
    events = [e for e in bus.emitted_events if e.get("session_id") == session_id]
    if not events:
        return

    _p(file, "")
    _rule(file, "-")
    _p(file, "  TIMELINE  (r0=Soln, r1+=Refm; each 'quorum' line closes one step)")
    _rule(file, "-")

    voters: list[str] = []

    for ev in events:
        topic = ev.get("topic", "")
        payload = ev.get("payload") or {}

        if topic == "protocol.started":
            c = payload.get("config") or {}
            _p(
                file,
                f"  start   N={c.get('agentCount')}  max_refm={c.get('maxRounds')}  "
                f"a={c.get('alphaQuorum')}  b={c.get('betaStability')}  "
                f"conf>={c.get('confidenceThreshold')}  f={c.get('byzantineTolerance')}",
            )
        elif topic == "protocol.aegean.round_started":
            voters = []
            rn = payload.get("round")
            ld = payload.get("leaderId")
            _p(file, f"  r{rn}     leader {ld!r}")
        elif topic == "protocol.aegean.vote_collected":
            vid = payload.get("voterId")
            if vid is not None:
                voters.append(str(vid))
        elif topic == "protocol.aegean.quorum_detected":
            acc = payload.get("quorumSize")
            who = ", ".join(voters) if voters else "?"
            _p(file, f"          quorum  {acc}/{r_quorum} accepts  order: {who}")
            voters = []
        elif topic == "protocol.iteration":
            _p(file, f"  loop    {payload}")
        elif topic == "protocol.completed":
            _p(
                file,
                f"  end     ok={payload.get('success')}  rows={payload.get('iterations')}  "
                f"ms={payload.get('durationMs')}",
            )
        else:
            _p(file, f"  ?       {topic}  {payload}")

    _rule(file, "-")


def _votes_one_line(votes: list[AgentVote]) -> str:
    parts = []
    for v in votes:
        parts.append(f"{v.agent_id}:{v.status}")
    return "  ".join(parts)


def _print_round_compact(r: AegeanRound, idx: int, experts: list[str], file: IO[str]) -> None:
    qs = r.quorum_status
    if r.phase == "commit":
        tag = f"[{idx}] COMMIT"
        sub = "audit only (no new agent calls)"
    elif r.phase == "proposal":
        tag = f"[{idx}] SOLN"
        sub = f"round_number={r.round_number}"
    else:
        tag = f"[{idx}] REFM"
        sub = f"round_number={r.round_number}"

    _p(file, "")
    _p(file, f"  {tag}  |  {sub}")
    _p(
        file,
        f"      leader {r.leader_id!r}  |  quorum {qs.accepts}/{qs.required} accepts  "
        f"(rej {qs.rejects} pend {qs.pending})  ok={qs.has_quorum}",
    )

    if r.proposal is not None:
        prev, n = _text_preview(r.proposal.value, 180)
        extra = f"  [{n} chars]" if n > 180 else ""
        _p(file, f"      R-bar{extra}  {prev!r}")

    if r.votes:
        _p(file, f"      votes  {_votes_one_line(r.votes)}")
        _p(file, f"      order  matches experts {experts}")
    else:
        _p(file, "      votes  (none)")

    if r.decision_committed is not None:
        _p(
            file,
            f"      engine  commit={r.decision_committed}  beta_stability={r.decision_stability}  "
            f"eligible={_snippet(r.decision_eligible, 60)!r}",
        )
        if r.decision_committed is False and r.phase == "refinement":
            _p(file, "              (no alpha cluster or beta not satisfied yet)")


def _refm_rounds_used(rounds: list[AegeanRound]) -> int:
    return sum(1 for r in rounds if r.phase == "refinement")


def _print_full_report(
    result: AegeanResult,
    *,
    experts: list[str],
    aegean_cfg: AegeanConfig,
    session_id: str,
    bus: EventBus,
    task_description: str | None,
    run_title: str | None,
    file: IO[str],
) -> None:
    n = len(experts)
    f = aegean_cfg.byzantine_tolerance
    r_quorum = calculate_quorum_size(n, f)
    refm_count = _refm_rounds_used(result.rounds)
    leader_guess = next((r.leader_id for r in result.rounds if r.leader_id), "?")

    _p(file, "")
    _rule(file)
    _p(file, "  AEGEAN SESSION TRACE")
    _rule(file)

    if run_title:
        _p(file, f"  {run_title}")
        if task_description:
            prev, tn = _text_preview(task_description, 280)
            _p(file, f"  task ({tn} chars): {prev!r}")
        _p(file, "")

    _p(file, "")
    _p(file, "  OUTCOME")
    _rule(file, "-")
    yn = "YES" if result.consensus_reached else "NO"
    _p(file, f"  consensus      {yn}")
    _p(file, f"  value          {result.consensus_value!r}")
    _p(file, f"  stop_reason    {result.termination_reason!r}")
    if not result.consensus_reached and result.termination_reason == "max_rounds":
        _p(
            file,
            f"  hint           hit max_refm={aegean_cfg.max_rounds}; shorten task or raise max_rounds",
        )
    _p(file, f"  duration_ms    {result.total_duration_ms}")
    _p(file, f"  tokens_sum     {result.tokens_used}")
    _p(file, f"  leader         {leader_guess!r}")
    _p(file, f"  refm_rounds    {refm_count} used / {aegean_cfg.max_rounds} max")
    _p(file, f"  result_rows    {result.total_rounds} (includes commit row if any)")

    if result.commit_certificate:
        c = result.commit_certificate
        _p(file, "")
        _p(file, "  CERTIFICATE")
        _rule(file, "-")
        _p(file, f"  term {c.term_num}  refm_r {c.refinement_round}  leader {c.leader_id!r}")
        _p(file, f"  value {c.committed_value!r}  R={c.quorum_size_r}  a={c.alpha}  b={c.beta}")
        _p(file, f"  support {c.supporting_refm_agent_ids}")

    _p(file, "")
    _p(file, "  PARAMETERS")
    _rule(file, "-")
    _p(file, f"  session_id     {session_id!r}")
    _p(file, f"  experts        {', '.join(experts)}")
    _p(file, f"  alpha / beta   {aegean_cfg.alpha} / {aegean_cfg.beta}")
    _p(file, f"  quorum R       {r_quorum}  (N={n}, f={f})")
    _p(file, f"  conf_min       {aegean_cfg.confidence_threshold}")
    _p(file, f"  early_term     {aegean_cfg.early_termination}")

    _print_compact_events(bus, session_id, r_quorum=r_quorum, file=file)

    _p(file, "")
    _rule(file, "-")
    _p(file, "  ROUNDS  (detail from AegeanResult.rounds)")
    _rule(file, "-")
    for i, row in enumerate(result.rounds):
        _print_round_compact(row, i, experts, file)

    _p(file, "")
    _rule(file)
    _p(file, "")
