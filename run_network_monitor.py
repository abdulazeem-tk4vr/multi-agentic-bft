#!/usr/bin/env python3
"""Launch the Aegean network monitor without PYTHONPATH."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_NM = _ROOT / "network-monitor"
for p in (_ROOT, _NM):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

if __name__ == "__main__":
    from network_monitor.__main__ import main

    main()
