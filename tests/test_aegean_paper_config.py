"""Paper Aegean: fail-stop bounds and single quorum R = N - f (slice 1)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from aegean import (
    aegean_log,
    calculate_quorum_size,
    configure_aegean_file_logging,
    get_aegean_logger,
    max_failstop_faults_allowed,
    validate_failstop_fault_bound,
)


def test_max_failstop_faults_allowed():
    assert max_failstop_faults_allowed(3) == 1
    assert max_failstop_faults_allowed(4) == 2
    assert max_failstop_faults_allowed(5) == 2
    assert max_failstop_faults_allowed(6) == 3


def test_validate_failstop_fault_bound_rejects_small_n():
    with pytest.raises(ValueError, match="at least 3"):
        validate_failstop_fault_bound(2, 0)


def test_validate_failstop_fault_bound_rejects_negative_f():
    with pytest.raises(ValueError, match="non-negative"):
        validate_failstop_fault_bound(3, -1)


def test_validate_failstop_fault_bound_rejects_f_too_large():
    with pytest.raises(ValueError, match="exceeds paper limit"):
        validate_failstop_fault_bound(5, 3)


def test_calculate_quorum_size_paper_formula():
    assert calculate_quorum_size(5, 2) == 3
    assert calculate_quorum_size(4, 1) == 3
    assert calculate_quorum_size(3, 0) == 3


def test_round0_and_refinement_share_same_r():
    """Round 0 (Soln) and Refm rounds must use the same R = N - f."""
    n, f = 7, 2
    r0 = calculate_quorum_size(n, f)
    r_refm = calculate_quorum_size(n, f)
    assert r0 == r_refm == n - f


def test_calculate_quorum_invalid_n_raises():
    with pytest.raises(ValueError):
        calculate_quorum_size(1, 0)


def test_logging_writes_under_logs_dir(tmp_path: Path) -> None:
    log_dir = tmp_path / "run-logs"
    path = configure_aegean_file_logging(log_dir=log_dir, level=logging.DEBUG)
    assert path.parent == log_dir
    logger = get_aegean_logger("paper.test")
    logger.info("paper config slice-1")
    aegean_log(logging.WARNING, "via helper", logger_name="aegean.paper.test")
    text = path.read_text(encoding="utf-8")
    assert "paper config slice-1" in text
    assert "via helper" in text
