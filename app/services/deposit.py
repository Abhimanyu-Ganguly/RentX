"""
Deposit State Machine Service (Simulated Escrow).

This service manages the lifecycle of simulated security deposits without any real money or tokens.
The state machine is implemented as a deterministic, pure-Python finite state machine.
"""

from typing import Optional


class InvalidDepositTransitionError(Exception):
    """
    Raised when an illegal deposit status transition is attempted.
    For example, attempting to release a deposit that is still pending or already resolved.
    """
    def __init__(self, current_status: str, target_status: str, reason: Optional[str] = None):
        message = f"Invalid deposit transition from '{current_status}' to '{target_status}'."
        if reason:
            message += f" Reason: {reason}"
        super().__init__(message)
        self.current_status = current_status
        self.target_status = target_status


# =========================================================================================
# SMART CONTRACT MAPPING (Architectural Note)
# -----------------------------------------------------------------------------------------
# In a decentralized or production blockchain deployment, this state machine maps 1:1 to an
# Escrow Smart Contract (e.g. Solidity / EVM or CosmWasm state machine):
#
# 1. PENDING  -> Smart contract escrow instance instantiated with item value & rental terms.
# 2. HELD     -> Renter funds locked in escrow contract upon owner approval (deposit locked).
# 3. RELEASED -> Mutual sign-off or timelock expiry releases collateral back to renter address.
# 4. DISPUTED -> Owner submits proof of damage; contract freezes escrow and calls arbitrator.
# 5. RESOLVED -> Arbitrator multi-sig executes payout (refund Renter, pay Owner, or split).
#
# Keeping this state machine pure and decoupled allows swapping this Python layer for a
# real smart contract interface without altering the rest of the application.
# =========================================================================================

# Explicit Transition Matrix: allowed (from_state) -> set of valid (to_state)
VALID_DEPOSIT_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"held"},
    "held": {"released", "disputed"},
    "disputed": {"resolved"},
    "released": set(),  # Terminal state
    "resolved": set(),  # Terminal state
}

# Supported dispute settlement strategies
ALLOWED_RESOLUTIONS: set[str] = {"refund_renter", "keep_deposit", "split"}


def validate_transition(current_status: str, target_status: str) -> None:
    """
    Validates whether the requested state transition is legally permissible according to the FSM.
    Raises InvalidDepositTransitionError if forbidden.
    """
    allowed_targets = VALID_DEPOSIT_TRANSITIONS.get(current_status, set())
    if target_status not in allowed_targets:
        raise InvalidDepositTransitionError(
            current_status=current_status,
            target_status=target_status,
            reason=f"Valid next states from '{current_status}' are: {list(allowed_targets) or 'None (terminal)'}"
        )


def transition_on_accept(current_deposit_status: str) -> str:
    """
    Transitions deposit from 'pending' to 'held' when an owner accepts a rental request.
    """
    validate_transition(current_deposit_status, "held")
    return "held"


def transition_on_confirm_return(current_deposit_status: str) -> str:
    """
    Transitions deposit from 'held' to 'released' when an owner confirms the return in good condition.
    """
    validate_transition(current_deposit_status, "released")
    return "released"


def transition_on_dispute(current_deposit_status: str) -> str:
    """
    Transitions deposit from 'held' to 'disputed' when an issue/damage is flagged.
    """
    validate_transition(current_deposit_status, "disputed")
    return "disputed"


def transition_on_resolve(current_deposit_status: str, resolution: str) -> str:
    """
    Transitions deposit from 'disputed' to 'resolved' with a specific payout outcome.
    """
    if resolution not in ALLOWED_RESOLUTIONS:
        raise ValueError(f"Unknown resolution '{resolution}'. Allowed: {ALLOWED_RESOLUTIONS}")
    validate_transition(current_deposit_status, "resolved")
    return "resolved"
