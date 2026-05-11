#!/usr/bin/env python3
"""Download and cache the SimCSE checkpoint used by semantic Aegean / the network monitor.

Run once (same Python as the monitor) before ``run_network_monitor.py`` so the first
semantic session does not block on Hugging Face Hub. Optional: set ``HF_TOKEN`` in
``.env`` or the environment for higher rate limits.

  py -3 examples/prefetch_semantic_model.py
  py -3 examples/prefetch_semantic_model.py --model princeton-nlp/sup-simcse-bert-base-uncased
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from aegean.types import SemanticEquivalenceConfig


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Same .env search order as ``network_monitor.runner.load_dotenv`` / ``simple_cluster``."""
    root = _repo_root()
    for path in (root / ".env", root / "network-monitor" / ".env", Path.cwd() / ".env"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = val


def main() -> int:
    default_model = SemanticEquivalenceConfig().simcse_model_name
    p = argparse.ArgumentParser(description="Prefetch SimCSE weights for semantic equivalence")
    p.add_argument(
        "--model",
        default=default_model,
        help=f"Hugging Face model id (default: {default_model})",
    )
    args = p.parse_args()

    _load_dotenv()

    # Disable HF's xet/CAS download protocol — falls back to plain HTTP which is
    # more reliable on most connections and does not stall on KeyboardInterrupt cleanup.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print(
            "sentence-transformers not installed. Run: pip install -e '.[semantic]'",
            file=sys.stderr,
        )
        return 1

    print(f"Downloading / loading into HF cache: {args.model}", flush=True)
    if os.getenv("HF_TOKEN", "").strip():
        print("  HF_TOKEN is set (authenticated Hub requests).", flush=True)
    else:
        print(
            "  Tip: set HF_TOKEN in .env for faster downloads (see https://huggingface.co/settings/tokens ).",
            flush=True,
        )

    m = SentenceTransformer(args.model)
    _ = m.encode(["warmup"], convert_to_numpy=True)
    print("Done — model is cached; start the network monitor when ready.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
