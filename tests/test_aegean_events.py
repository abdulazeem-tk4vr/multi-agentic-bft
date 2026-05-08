from aegean.events import (
    EventBus,
    emit_aegean_quorum_detected,
    emit_aegean_round_started,
    emit_aegean_vote_collected,
    emit_protocol_completed,
    emit_protocol_iteration,
    emit_protocol_started,
)


def test_emit_protocol_started():
    bus = EventBus()
    emit_protocol_started(
        bus,
        session_id="s1",
        agent_count=5,
        aegean_config={
            "max_rounds": 3,
            "confidence_threshold": 0.8,
            "byzantine_tolerance": 1,
        },
    )
    event = bus.emitted_events[0]
    assert event["topic"] == "protocol.started"
    assert event["payload"]["protocolType"] == "aegean"
    assert event["payload"]["config"]["agentCount"] == 5
    assert event["payload"]["config"]["alphaQuorum"] == 2
    assert event["payload"]["config"]["betaStability"] == 2
    assert event["session_id"] == "s1"


def test_emit_protocol_started_alpha_beta_from_config():
    bus = EventBus()
    emit_protocol_started(
        bus,
        session_id="s1",
        agent_count=4,
        aegean_config={
            "max_rounds": 3,
            "confidence_threshold": 0.8,
            "byzantine_tolerance": 1,
            "alpha": 3,
            "beta": 1,
        },
    )
    cfg = bus.emitted_events[0]["payload"]["config"]
    assert cfg["alphaQuorum"] == 3
    assert cfg["betaStability"] == 1


def test_emit_protocol_iteration_round_is_one_indexed():
    bus = EventBus()
    emit_protocol_iteration(bus, round_number=2, max_rounds=10, status="converged", session_id="s1")
    event = bus.emitted_events[0]
    assert event["topic"] == "protocol.iteration"
    assert event["payload"]["round"] == 3
    assert event["payload"]["status"] == "converged"


def test_emit_protocol_completed():
    bus = EventBus()
    emit_protocol_completed(bus, success=False, iterations=7, duration_ms=1234, session_id="s2")
    event = bus.emitted_events[0]
    assert event["topic"] == "protocol.completed"
    assert event["payload"]["success"] is False
    assert event["payload"]["iterations"] == 7
    assert event["session_id"] == "s2"


def test_phase_event_emitters():
    bus = EventBus()
    emit_aegean_round_started(bus, 1, 5, "leader-1", "s1")
    emit_aegean_vote_collected(bus, 1, "voter-1", 3, 4, "s1")
    emit_aegean_quorum_detected(bus, 1, 4, False, "s1")
    topics = [e["topic"] for e in bus.emitted_events]
    assert "protocol.aegean.round_started" in topics
    assert "protocol.aegean.vote_collected" in topics
    assert "protocol.aegean.quorum_detected" in topics
