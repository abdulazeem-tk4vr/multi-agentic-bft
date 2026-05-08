"""Per-agent RefmSet / refinement round bookkeeping (paper guards).

Coordinator seeds tracks via optional ``execute`` config key ``refm_round_track_init`` for
crash-recovery / adversarial re-ordering integration tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from .logutil import get_aegean_logger

_log = get_aegean_logger("refinement_state")


@dataclass
class PerAgentRefmRoundTrack:
    """Track highest accepted **RefmSet** broadcast round per agent (monotonic non-decreasing)."""

    last_accepted_broadcast_round: int = 0

    def try_accept_refm_broadcast(self, incoming_round: int) -> bool:
        """Accept iff ``incoming_round >= last_accepted``; ignore strictly stale rounds."""
        if incoming_round < self.last_accepted_broadcast_round:
            _log.debug(
                "refuse RefmSet round %s (< local %s)",
                incoming_round,
                self.last_accepted_broadcast_round,
            )
            return False
        self.last_accepted_broadcast_round = incoming_round
        return True
