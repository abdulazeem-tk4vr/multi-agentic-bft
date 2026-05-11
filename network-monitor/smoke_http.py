"""One-shot monitor smoke check."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PKG = Path(__file__).resolve().parent
for p in (_REPO, _PKG):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from network_monitor import VizSession  # noqa: E402


def main() -> None:
    v = VizSession(port=8788)
    url = v.start()
    raw = urllib.request.urlopen(url + "api/state").read()
    d = json.loads(raw.decode())
    assert "seq" in d
    v.stop()
    print("smoke ok", url)


if __name__ == "__main__":
    main()
