"""
Tests for Deposit State Machine transitions, legal paths, and illegal transition rejection.
"""

import pytest
from app.services.deposit import (
    validate_transition,
    transition_on_accept,
    transition_on_confirm_return,
    transition_on_dispute,
    transition_on_resolve,
    InvalidDepositTransitionError,
)


def test_legal_deposit_happy_path():
    """Verify standard happy path: pending -> held -> released."""
    status = "pending"

    # 1. Owner accepts rental
    status = transition_on_accept(status)
    assert status == "held"

    # 2. Owner confirms good return
    status = transition_on_confirm_return(status)
    assert status == "released"


def test_legal_deposit_dispute_path():
    """Verify dispute path: pending -> held -> disputed -> resolved."""
    status = "pending"

    # 1. Accept booking
    status = transition_on_accept(status)
    assert status == "held"

    # 2. Open dispute
    status = transition_on_dispute(status)
    assert status == "disputed"

    # 3. Resolve dispute (split deposit)
    status = transition_on_resolve(status, resolution="split")
    assert status == "resolved"


def test_illegal_deposit_transitions():
    """Verify that any non-permitted transition raises InvalidDepositTransitionError."""
    # Cannot jump straight from pending to released
    with pytest.raises(InvalidDepositTransitionError):
        validate_transition("pending", "released")

    # Cannot jump straight from pending to disputed
    with pytest.raises(InvalidDepositTransitionError):
        validate_transition("pending", "disputed")

    # Cannot transition out of released (terminal state)
    with pytest.raises(InvalidDepositTransitionError):
        validate_transition("released", "held")

    with pytest.raises(InvalidDepositTransitionError):
        validate_transition("released", "disputed")

    # Cannot jump from disputed directly to released without arbitration
    with pytest.raises(InvalidDepositTransitionError):
        validate_transition("disputed", "released")

    # Cannot transition out of resolved (terminal state)
    with pytest.raises(InvalidDepositTransitionError):
        validate_transition("resolved", "held")


def test_invalid_resolution_argument():
    """Verify that unknown settlement resolutions are rejected."""
    with pytest.raises(ValueError):
        transition_on_resolve("disputed", resolution="unauthorized_payout")
