"""Governance action types.

This module defines the action schema that the governance policy
returns to the engine. The engine applies these actions at the start
of the next tick.

Per governance.md action vector specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primordial_soup.types import StopContinueDecision, TriggeringRule


@dataclass(frozen=True)
class ContinueStopAction:
    """Stop or continue decision for a single active initiative.

    triggering_rule is required when decision == STOP. It must be
    absent or None when decision == CONTINUE.
    Per governance.md ContinueStop action.
    """

    initiative_id: str
    decision: StopContinueDecision
    triggering_rule: TriggeringRule | None = None


@dataclass(frozen=True)
class SetExecAttentionAction:
    """Set executive attention for a single initiative on a tick.

    attention = 0.0 means no explicit attention. If attention > 0.0,
    it must satisfy attention_min_effective <= a <= attention_max_effective.

    Omission from the action vector means attention = 0.0 for that
    tick (no persistence). Per governance.md SetExecAttention.
    """

    initiative_id: str
    attention: float


@dataclass(frozen=True)
class AssignTeamAction:
    """Assign a team to an initiative (or leave idle).

    initiative_id = None means leave the team idle.
    Per governance.md AssignTeam action.
    """

    team_id: str
    initiative_id: str | None


@dataclass(frozen=True)
class GovernanceActions:
    """Complete action vector returned by the policy for one tick.

    The engine applies these in deterministic order:
    1. ContinueStop (all initiatives)
    2. AssignTeam (ordered, first-come-first-served)
    3. SetExecAttention (with budget feasibility check)

    Per governance.md deterministic application order.
    """

    continue_stop: tuple[ContinueStopAction, ...]
    assign_team: tuple[AssignTeamAction, ...]
    set_exec_attention: tuple[SetExecAttentionAction, ...]
