from __future__ import annotations

from typing import Any


def ok_result(output: Any, *, confidence: float | None = None, tokens_used: int | None = None, **metadata: Any) -> dict[str, Any]:
    meta: dict[str, Any] = dict(metadata)
    if confidence is not None:
        meta["confidence"] = float(confidence)
    if tokens_used is not None:
        meta["tokens_used"] = int(tokens_used)
    return {"ok": True, "value": {"output": output, "metadata": meta}}


def error_result(message: str) -> dict[str, Any]:
    return {"ok": False, "error": str(message)}
