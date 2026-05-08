"""HTTP+JSON transport for **RequestVote** / **Vote** (stdlib only).

Each expert runs a :class:`threading.ThreadingHTTPServer` exposing ``POST /aegean/request_vote`` and
``POST /aegean/vote`` with one :class:`~aegean.election.LocalElectionState` per server process/thread.

For coordinator **execute**, pass :class:`HttpElectionMessenger` as ``config["election_messenger"]``
(see :mod:`aegean.protocol`). Remote peers must be started with matching
``election_initial_terms`` semantics (each peer’s persisted term before the run).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.error
import urllib.request

from .election import LocalElectionState
from .types import RequestVoteMessage, VoteMessage


def _json_vote_from_payload(payload: dict) -> VoteMessage:
    vf = payload.get("vote_for")
    vote_for: str | None = None
    if vf not in (None, "", "null"):
        vote_for = str(vf)
    return VoteMessage(
        term=int(payload["term"]),
        voter_id=str(payload["voter_id"]),
        grant=bool(payload.get("grant", True)),
        vote_for=vote_for,
    )


def make_request_handler(state: LocalElectionState) -> type[BaseHTTPRequestHandler]:
    """Build a handler class bound to a single peer’s election **state** (one server per expert)."""

    class _ElectionHTTPHandler(BaseHTTPRequestHandler):
        _state = state

        def do_POST(self) -> None:  # noqa: N802
            try:
                n = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(n)
                payload = json.loads(raw.decode())
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
                self.send_error(400, str(exc))
                return

            if self.path == "/aegean/request_vote":
                msg = RequestVoteMessage(int(payload["term"]), str(payload["candidate_id"]))
                granted = self._state.grant_request_vote(msg)
                body = json.dumps({"granted": granted}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path == "/aegean/vote":
                try:
                    vm = _json_vote_from_payload(payload)
                    self._state.record_vote(vm)
                except (KeyError, TypeError, ValueError) as exc:
                    self.send_error(400, str(exc))
                    return
                self.send_response(204)
                self.end_headers()
                return

            self.send_error(404)

        def log_message(self, format: str, *args: object) -> None:
            return

    return _ElectionHTTPHandler


def start_threading_election_server(
    *,
    initial_term: int = 0,
    host: str = "127.0.0.1",
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    """Start ``ThreadingHTTPServer`` with **LocalElectionState(term=initial_term)**.

    Returns ``(server, thread, base_url)``. Call :meth:`ThreadingHTTPServer.shutdown` when done.
    """
    state = LocalElectionState(term=initial_term)
    handler = make_request_handler(state)
    server = ThreadingHTTPServer((host, 0), handler)
    port = server.server_address[1]
    base = f"http://{host}:{port}"
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    return server, th, base


class HttpElectionMessenger:
    """POST **RequestVote** / **Vote** to per-expert HTTP bases (see :func:`start_threading_election_server`)."""

    __slots__ = ("_timeout_s", "_urls")

    def __init__(self, base_urls: dict[str, str], *, timeout_s: float = 15.0) -> None:
        self._urls = base_urls
        self._timeout_s = timeout_s

    def request_vote(self, peer_id: str, msg: RequestVoteMessage) -> bool:
        base = self._urls[peer_id].rstrip("/")
        url = base + "/aegean/request_vote"
        body = json.dumps({"term": msg.term, "candidate_id": msg.candidate_id}).encode()
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                out = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"request_vote HTTP {exc.code}: {exc.read().decode()}") from exc
        return bool(out.get("granted"))

    def record_vote(self, peer_id: str, msg: VoteMessage) -> None:
        base = self._urls[peer_id].rstrip("/")
        url = base + "/aegean/vote"
        payload = {
            "term": msg.term,
            "voter_id": msg.voter_id,
            "grant": msg.grant,
            "vote_for": msg.vote_for,
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                if resp.status not in (200, 204):
                    raise ValueError(f"unexpected status {resp.status}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise ValueError(f"vote HTTP {exc.code}: {detail}") from exc


def http_cluster_for_experts(
    experts: list[str],
    *,
    initial_local_terms: dict[str, int] | None = None,
) -> tuple[HttpElectionMessenger, list[ThreadingHTTPServer]]:
    """Start one HTTP peer per expert; return messenger and servers (shutdown in tests / teardown)."""
    init = initial_local_terms or {}
    servers: list[ThreadingHTTPServer] = []
    urls: dict[str, str] = {}
    for eid in experts:
        term = int(init.get(eid, 0))
        srv, _th, base = start_threading_election_server(initial_term=term)
        servers.append(srv)
        urls[eid] = base
    return HttpElectionMessenger(urls), servers


def shutdown_servers(servers: list[ThreadingHTTPServer]) -> None:
    for srv in servers:
        srv.shutdown()
        srv.server_close()
