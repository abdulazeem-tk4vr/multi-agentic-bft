"""Thread-safe dashboard state."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Any


def _phase_label(protocol_round: int | None) -> str:
    if protocol_round is None:
        return "—"
    return "SOLN" if protocol_round == 0 else "REFM"


_QUORUM_FAIL_ITERATION = frozenset(
    {"no_soln_quorum", "no_refm_quorum", "recovery_insufficient_bar", "max_reached"}
)


def _quorum_iteration_short_reason(status: str) -> str:
    return {
        "no_soln_quorum": "Soln round: quorum not met (timeouts/rejects).",
        "no_refm_quorum": "Refm round: quorum not met (timeouts/rejects).",
        "recovery_insufficient_bar": "Too few outputs to form quorum (recovery).",
        "max_reached": "Stopped: max rounds / early termination.",
    }.get(status, status.replace("_", " "))


@dataclass
class AgentViz:
    id: str
    last_preview: str = ""
    last_phase: str = ""
    last_round: str = ""
    tokens: str = ""
    ok: bool = True
    vote_slot: int | None = None


class VizState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seq = 0
        self._experts: list[str] = []
        self._session_id = ""
        self._leader: str | None = None
        self._protocol_round: int | None = None
        self._max_refm = 5
        self._alpha = 2
        self._beta = 2
        self._quorum_r = 3
        self._quorum_progress = (0, 3)
        self._last_quorum: int | None = None
        self._iter_status: str | None = None
        self._iter_round: int | None = None
        self._agents: dict[str, AgentViz] = {}
        self._log: list[dict[str, Any]] = []
        self._traffic: list[dict[str, Any]] = []
        self._consensus: bool | None = None
        self._value: Any = None
        self._reason: str | None = None
        self._duration_ms: int | None = None
        self._cert: str | None = None
        self._run_status: str = "idle"
        self._run_error: str | None = None

    def _bump(self) -> None:
        self._seq += 1

    def _push_log(self, kind: str, message: str) -> None:
        self._log.append({"t": time.time(), "kind": kind, "msg": message})
        if len(self._log) > 200:
            del self._log[:-200]

    def _push_traffic(self, row: dict[str, Any]) -> None:
        r = dict(row)
        r["t"] = time.time()
        self._traffic.append(r)
        if len(self._traffic) > 200:
            del self._traffic[:-200]

    def set_run_status(self, status: str, error: str | None = None) -> None:
        with self._lock:
            self._run_status = status
            self._run_error = error
            self._bump()

    def configure(self, *, experts: list[str], session_id: str = "") -> None:
        with self._lock:
            self._experts = list(experts)
            self._session_id = session_id
            for e in experts:
                self._agents.setdefault(e, AgentViz(id=e))
            self._bump()

    def set_quorum_r(self, r: int) -> None:
        with self._lock:
            self._quorum_r = r
            self._quorum_progress = (self._quorum_progress[0], r)
            self._bump()

    def ingest_protocol_event(self, ev: dict[str, Any]) -> None:
        topic = ev.get("topic", "")
        payload = ev.get("payload") or {}
        with self._lock:
            if topic == "protocol.started":
                c = payload.get("config") or {}
                self._max_refm = int(c.get("maxRounds", self._max_refm))
                self._alpha = int(c.get("alphaQuorum", self._alpha))
                self._beta = int(c.get("betaStability", self._beta))
                n = int(c.get("agentCount", len(self._experts) or 3))
                self._quorum_r = max(1, n)
                self._quorum_progress = (0, self._quorum_r)
                self._push_log("start", f"protocol started N={n} max_refm={self._max_refm}")
                self._push_traffic({"kind": "boot", "n": n})
            elif topic == "protocol.aegean.round_started":
                self._protocol_round = payload.get("round")
                self._leader = payload.get("leaderId")
                self._quorum_progress = (0, self._quorum_r)
                for a in self._agents.values():
                    a.vote_slot = None
                rn = self._protocol_round
                self._push_log("round", f"r{rn} leader={self._leader!r} {_phase_label(rn)}")
                self._push_traffic({"kind": "round", "round": rn, "leader": self._leader})
            elif topic == "protocol.aegean.vote_collected":
                vid = str(payload.get("voterId", ""))
                vc = int(payload.get("voteCount", 0))
                rq = int(payload.get("requiredQuorum", self._quorum_r))
                rn = payload.get("round")
                self._quorum_r = rq
                self._quorum_progress = (vc, rq)
                if vid in self._agents:
                    self._agents[vid].vote_slot = vc
                self._push_log("vote", f"{vid} vote {vc}/{rq}")
                self._push_traffic(
                    {"kind": "vote", "agent": vid, "round": rn, "vote_index": vc, "required": rq}
                )
            elif topic == "protocol.aegean.quorum_detected":
                self._last_quorum = int(payload.get("quorumSize", 0))
                rn = payload.get("round")
                self._push_log("quorum", f"quorum ok accepts={self._last_quorum}")
                self._push_traffic(
                    {
                        "kind": "quorum",
                        "ok": True,
                        "round": rn,
                        "accepts": self._last_quorum,
                        "required": int(self._quorum_r),
                    }
                )
            elif topic == "protocol.iteration":
                self._iter_round = payload.get("round")
                self._iter_status = str(payload.get("status", ""))
                self._push_log("loop", str(payload))
                if self._iter_status in _QUORUM_FAIL_ITERATION:
                    vc, rq = self._quorum_progress
                    self._push_traffic(
                        {
                            "kind": "quorum",
                            "ok": False,
                            "round": payload.get("round"),
                            "status": self._iter_status,
                            "reason": _quorum_iteration_short_reason(self._iter_status),
                            "votes": int(vc),
                            "required": int(rq),
                        }
                    )
            elif topic == "protocol.completed":
                self._consensus = bool(payload.get("success"))
                self._duration_ms = int(payload.get("durationMs", 0))
                self._push_log("end", f"completed ok={self._consensus} rows={payload.get('iterations')}")
            else:
                self._push_log(topic, str(payload)[:200])
            self._bump()

    def ingest_worker(
        self, *, agent_id: str, phase: str, round_num: Any, preview: str, tokens: Any, ok: bool
    ) -> None:
        with self._lock:
            a = self._agents.setdefault(agent_id, AgentViz(id=agent_id))
            a.last_preview = preview[:500]
            a.last_phase = phase
            a.last_round = str(round_num)
            a.tokens = str(tokens)
            a.ok = ok
            self._push_log("worker", f"{agent_id} {phase} r{round_num} ok={ok} {preview[:80]}")
            self._push_traffic(
                {
                    "kind": "worker",
                    "agent": agent_id,
                    "phase": phase,
                    "round": round_num,
                    "preview": preview[:120],
                    "ok": ok,
                }
            )
            self._bump()

    def finalize(
        self,
        *,
        consensus_reached: bool,
        consensus_value: Any,
        termination_reason: str,
        duration_ms: int,
        certificate: Any = None,
    ) -> None:
        with self._lock:
            self._consensus = consensus_reached
            self._value = consensus_value
            self._reason = termination_reason
            self._duration_ms = duration_ms
            if certificate is not None:
                self._cert = repr(certificate)
            self._push_log(
                "outcome",
                f"consensus={consensus_reached} reason={termination_reason!r} value={consensus_value!r}",
            )
            self._bump()

    def reset(self) -> None:
        with self._lock:
            self._seq = 0
            self._leader = None
            self._protocol_round = None
            self._quorum_progress = (0, self._quorum_r)
            self._last_quorum = None
            self._iter_status = None
            self._iter_round = None
            self._log.clear()
            self._traffic.clear()
            self._consensus = None
            self._value = None
            self._reason = None
            self._duration_ms = None
            self._cert = None
            for a in self._agents.values():
                a.last_preview = ""
                a.last_phase = ""
                a.last_round = ""
                a.tokens = ""
                a.ok = True
                a.vote_slot = None
            self._run_status = "idle"
            self._run_error = None
            self._bump()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "seq": self._seq,
                "ts": time.time(),
                "experts": list(self._experts) or list(self._agents.keys()),
                "session_id": self._session_id,
                "leader_id": self._leader,
                "protocol_round": self._protocol_round,
                "phase_label": _phase_label(self._protocol_round),
                "max_refm": self._max_refm,
                "alpha": self._alpha,
                "beta": self._beta,
                "quorum_r": self._quorum_r,
                "quorum_progress": self._quorum_progress,
                "last_quorum_size": self._last_quorum,
                "iteration_status": self._iter_status,
                "iteration_round": self._iter_round,
                "agents": {k: asdict(v) for k, v in self._agents.items()},
                "event_log": list(self._log[-80:]),
                "traffic": list(self._traffic[-120:]),
                "consensus_reached": self._consensus,
                "consensus_value": self._value,
                "termination_reason": self._reason,
                "duration_ms": self._duration_ms,
                "certificate_summary": self._cert,
                "run_status": self._run_status,
                "run_error": self._run_error,
            }
