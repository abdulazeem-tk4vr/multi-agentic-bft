"""Dashboard session object."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Callable

from aegean.types import AegeanResult

from .bus import VizEventBus
from .server_runtime import start_dashboard_server
from .state import VizState


class VizSession:
    def __init__(
        self, *, host: str = "127.0.0.1", port: int = 8765, repo_root: Path | None = None
    ) -> None:
        self.host = host
        self.port = port
        self._repo_root = repo_root if repo_root is not None else Path(__file__).resolve().parents[2]
        self.state = VizState()
        self._httpd = None
        self._run_lock = threading.Lock()
        self._running = False
        self._cancel_requested = False
        self._cancel_active: Callable[[], None] | None = None

        def _on_event(ev: dict[str, Any]) -> None:
            self.state.ingest_protocol_event(ev)

        self.bus = VizEventBus(on_event=_on_event)

    def capabilities(self) -> dict[str, Any]:
        from .runner import load_dotenv

        load_dotenv(self._repo_root)
        return {
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY", "").strip()),
            "model_default": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip()
            or "openai/gpt-4o-mini",
        }

    def submit_run(self, spec: dict[str, Any]) -> dict[str, Any]:
        from .runner import run_dashboard_session, validate_spec_for_submit

        err = validate_spec_for_submit(spec, self._repo_root)
        if err is not None:
            import sys

            print(f"[aegean-viz] POST /api/run rejected: {err}", file=sys.stderr, flush=True)
            return {"ok": False, "error": err}
        with self._run_lock:
            if self._running:
                return {"ok": False, "error": "A run is already in progress. Wait for it to finish."}
            self._running = True
            self._cancel_requested = False
            self._cancel_active = None

        def _register_cancel(cancel_fn: Callable[[], None]) -> None:
            call_now = False
            with self._run_lock:
                self._cancel_active = cancel_fn
                if self._cancel_requested:
                    call_now = True
            if call_now:
                cancel_fn()

        def work() -> None:
            try:
                self.state.reset()
                self.state.set_run_status("running")
                run_dashboard_session(
                    self,
                    spec,
                    repo_root=self._repo_root,
                    on_cancel_ready=_register_cancel,
                )
                with self._run_lock:
                    cancelled = self._cancel_requested
                if cancelled:
                    self.state.set_run_status("error", "Run cancelled by user.")
                else:
                    self.state.set_run_status("done")
            except Exception as e:  # noqa: BLE001
                with self._run_lock:
                    cancelled = self._cancel_requested
                self.state.set_run_status("error", "Run cancelled by user." if cancelled else str(e))
            finally:
                with self._run_lock:
                    self._running = False
                    self._cancel_active = None

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def cancel_run(self) -> dict[str, Any]:
        with self._run_lock:
            if not self._running:
                return {"ok": False, "error": "No active run to cancel."}
            self._cancel_requested = True
            cancel_fn = self._cancel_active
        if cancel_fn is not None:
            cancel_fn()
        self.state.set_run_status("error", "Run cancelled by user.")
        return {"ok": True}

    def start(self) -> str:
        self._httpd, _ = start_dashboard_server(self, host=self.host, port=self.port)
        return f"http://{self.host}:{self.port}/"

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd = None

    def configure(self, *, experts: list[str], session_id: str = "", quorum_r: int | None = None) -> None:
        self.state.configure(experts=experts, session_id=session_id)
        if quorum_r is not None:
            self.state.set_quorum_r(quorum_r)

    def worker_trace(
        self,
        *,
        agent_id: str,
        phase: str,
        round_num: Any,
        preview: str,
        tokens: Any,
        ok: bool,
    ) -> None:
        self.state.ingest_worker(
            agent_id=agent_id, phase=phase, round_num=round_num, preview=preview, tokens=tokens, ok=ok
        )

    def finalize(self, result: AegeanResult) -> None:
        self.state.finalize(
            consensus_reached=result.consensus_reached,
            consensus_value=result.consensus_value,
            termination_reason=str(result.termination_reason),
            duration_ms=result.total_duration_ms,
            certificate=result.commit_certificate,
            semantic_no_consensus=result.semantic_no_consensus,
        )
