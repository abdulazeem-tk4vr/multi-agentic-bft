"""Persistent framed JSON TCP session utilities."""

from __future__ import annotations

import json
import socket
import struct
import threading
import uuid
from dataclasses import dataclass
from typing import Any


_LEN_STRUCT = struct.Struct("!I")


def read_frame(sock_file: Any) -> dict[str, Any]:
    """Read one length-prefixed JSON frame."""
    header = sock_file.read(_LEN_STRUCT.size)
    if not header:
        raise EOFError("socket closed")
    if len(header) != _LEN_STRUCT.size:
        raise EOFError("incomplete frame header")
    (nbytes,) = _LEN_STRUCT.unpack(header)
    if nbytes <= 0 or nbytes > 16 * 1024 * 1024:
        raise ValueError(f"invalid frame size: {nbytes}")
    payload = sock_file.read(nbytes)
    if len(payload) != nbytes:
        raise EOFError("incomplete frame payload")
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("frame payload must decode to object")
    return data


def write_frame(sock_file: Any, payload: dict[str, Any]) -> None:
    """Write one length-prefixed JSON frame."""
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    sock_file.write(_LEN_STRUCT.pack(len(body)))
    sock_file.write(body)
    sock_file.flush()


@dataclass(frozen=True)
class TcpSessionMessage:
    session_id: str
    msg_id: str
    message_type: str
    agent_id: str
    term: int
    round_num: int
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "msg_id": self.msg_id,
            "type": self.message_type,
            "agent_id": self.agent_id,
            "term": self.term,
            "round": self.round_num,
            "payload": self.payload,
        }


class TcpSessionClient:
    """One persistent bidirectional connection for request/response RPC."""

    def __init__(self, host: str, port: int, *, session_id: str, agent_id: str, timeout_s: float = 120.0) -> None:
        self._host = host
        self._port = port
        self._session_id = session_id
        self._agent_id = agent_id
        self._timeout_s = timeout_s
        self._sock: socket.socket | None = None
        self._sock_file: Any | None = None
        self._reader: threading.Thread | None = None
        self._closed = threading.Event()
        self._write_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}
        self._pending_events: dict[str, threading.Event] = {}
        self._pending_errors: dict[str, BaseException] = {}

    def connect(self) -> None:
        if self._sock is not None:
            return
        sock = socket.create_connection((self._host, self._port), timeout=self._timeout_s)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock_file = sock.makefile("rwb")
        self._sock = sock
        self._sock_file = sock_file
        self._closed.clear()
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self._sock_file is not None:
            try:
                self._sock_file.close()
            except OSError:
                pass
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        with self._pending_lock:
            for ev in self._pending_events.values():
                ev.set()
            self._pending_events.clear()
            self._pending.clear()
            self._pending_errors.clear()

    def request(self, *, message_type: str, term: int, round_num: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.connect()
        if self._sock_file is None:
            raise RuntimeError("tcp session not connected")
        msg_id = uuid.uuid4().hex
        msg = TcpSessionMessage(
            session_id=self._session_id,
            msg_id=msg_id,
            message_type=message_type,
            agent_id=self._agent_id,
            term=term,
            round_num=round_num,
            payload=payload,
        )
        ev = threading.Event()
        with self._pending_lock:
            self._pending_events[msg_id] = ev
        with self._write_lock:
            write_frame(self._sock_file, msg.as_dict())
        if not ev.wait(timeout=self._timeout_s):
            with self._pending_lock:
                self._pending_events.pop(msg_id, None)
                self._pending.pop(msg_id, None)
                self._pending_errors.pop(msg_id, None)
            raise TimeoutError(f"timeout waiting for tcp response from {self._agent_id}")
        with self._pending_lock:
            err = self._pending_errors.pop(msg_id, None)
            out = self._pending.pop(msg_id, None)
            self._pending_events.pop(msg_id, None)
        if err is not None:
            raise RuntimeError(f"tcp response error: {err}") from err
        if out is None:
            raise RuntimeError("tcp response missing payload")
        return out

    def _reader_loop(self) -> None:
        if self._sock_file is None:
            return
        try:
            while not self._closed.is_set():
                frame = read_frame(self._sock_file)
                msg_id = str(frame.get("msg_id", ""))
                if not msg_id:
                    continue
                with self._pending_lock:
                    if msg_id in self._pending_events:
                        self._pending[msg_id] = frame
                        self._pending_events[msg_id].set()
        except EOFError:
            # Peer closed connection. Keep already-delivered responses intact.
            with self._pending_lock:
                for msg_id, ev in self._pending_events.items():
                    if msg_id in self._pending:
                        continue
                    self._pending_errors[msg_id] = EOFError("socket closed")
                    ev.set()
        except Exception as exc:  # noqa: BLE001
            with self._pending_lock:
                for msg_id, ev in self._pending_events.items():
                    self._pending_errors[msg_id] = exc
                    ev.set()

