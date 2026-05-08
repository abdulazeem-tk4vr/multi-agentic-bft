from aegean.election import refm_set_update_allowed
from aegean.refinement_state import PerAgentRefmRoundTrack


def test_refm_round_track_accepts_monotonic_and_rejects_stale():
    t = PerAgentRefmRoundTrack()
    assert t.try_accept_refm_broadcast(1) is True
    assert t.last_accepted_broadcast_round == 1
    assert t.try_accept_refm_broadcast(1) is True
    assert t.try_accept_refm_broadcast(2) is True
    assert t.try_accept_refm_broadcast(1) is False
    assert t.last_accepted_broadcast_round == 2


def test_track_and_refm_set_guard_agree_on_replay_ordering():
    """After accepting a higher logical Refm round, the paper ``>=`` guard rejects older rounds."""
    t = PerAgentRefmRoundTrack()
    assert t.try_accept_refm_broadcast(3) is True
    prior = t.last_accepted_broadcast_round
    assert refm_set_update_allowed(local_round=prior, incoming_round=2) is False
    assert t.try_accept_refm_broadcast(2) is False
