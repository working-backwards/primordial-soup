"""Event types emitted by the simulation engine.

These are structured records for downstream analysis and reporting.
They are emitted during state transitions (completion, stop, major-win)
and recorded in the run's event log.

Per review_and_reporting.md event schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primordial_soup.types import ReassignmentTrigger


@dataclass(frozen=True)
class CompletionEvent:
    """Emitted when an initiative completes (reaches true_duration_ticks).

    Per core_simulator.md step 5c completion detection.
    """

    initiative_id: str
    tick: int
    latent_quality: float
    cumulative_labor_invested: float


@dataclass(frozen=True)
class MajorWinEvent:
    """Emitted when a completing initiative surfaces a major win.

    Per initiative_model.md major-win discovery event state.

    The observed_history_snapshot contains the quality belief ring buffer
    (up to W_stag entries). For the full trajectory including raw
    observations, execution beliefs, and attention levels, use per-tick
    logs (record_per_tick_logs=True).
    """

    initiative_id: str
    tick: int
    latent_quality: float
    observable_ceiling: float | None
    quality_belief_at_completion: float
    # Execution belief at completion. None when no execution channel.
    execution_belief_at_completion: float | None
    cumulative_labor_invested: float
    cumulative_attention_invested: float
    # Total staffed ticks from assignment to completion.
    staffed_tick_count: int
    # Quality belief ring buffer (up to W_stag entries, most recent last).
    # For the full belief trajectory, use per-tick logs.
    observed_history_snapshot: tuple[float, ...]


@dataclass(frozen=True)
class StopEvent:
    """Emitted when the engine executes a governance stop decision.

    Per review_and_reporting.md StopEvent schema.
    """

    tick: int
    initiative_id: str
    quality_belief_t: float
    execution_belief_t: float | None
    latent_quality: float
    triggering_rule: str
    cumulative_labor_invested: float
    staffed_ticks: int
    governance_archetype: str


@dataclass(frozen=True)
class ReassignmentEvent:
    """Emitted when a team is reassigned between initiatives.

    Per review_and_reporting.md ReassignmentEvent schema.
    """

    tick: int
    team_id: str
    from_initiative_id: str | None
    to_initiative_id: str
    triggered_by: ReassignmentTrigger


@dataclass(frozen=True)
class AttentionFeasibilityViolationEvent:
    """Emitted when proposed attention allocation violates constraints.

    Per governance.md attention-feasibility violation handling.
    """

    tick: int
    policy_id: str
    requested_total: float
    budget_limit: float
    affected_initiative_ids: tuple[str, ...]
    fallback_attention_applied: float
    violation_kind: str
