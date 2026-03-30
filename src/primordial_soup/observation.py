"""Observation boundary types.

This module defines the read-only observation structures that the
governance policy receives. These types enforce the observation
boundary: governance sees observables and belief summaries, never
latent ground truth.

Observation-interface extension (v1): generation_tag
----------------------------------------------------

generation_tag is the canonical bucket identifier for portfolio-mix
targeting in v1. It is surfaced on InitiativeObservation as observable
metadata — not as an engine change.

This is a policy-observation interface extension. It does not expose
latent state. generation_tag is set at pool generation time from public
InitiativeTypeSpec parameters that are visible in the environment family
definition, the YAML templates, and the run manifest. It does not reveal
latent_quality, true_duration_ticks, or any other hidden engine state.

The engine does not read, branch on, or enforce generation_tag. Only
the policy reads it, for governance-architecture purposes (portfolio mix
targeting via classify_initiative_bucket() in governance.py).

Per architecture.md invariant 6 and interfaces.md GovernanceObservation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InitiativeObservation:
    """What governance sees for a single initiative.

    Latent quality and true_duration_ticks are never present.
    Per interfaces.md InitiativeObservation.
    """

    initiative_id: str
    lifecycle_state: str  # matches LifecycleState.value
    assigned_team_id: str | None

    # Strategic quality belief (quality_belief_t; c_t in design docs).
    quality_belief_t: float

    # Observable bounded-prize ceiling. None = no bounded-prize channel.
    observable_ceiling: float | None

    # Immutable labor requirement for this initiative. Assignment requires
    # team_size >= required_team_size. Per interfaces.md InitiativeObservation.
    required_team_size: int

    # Derived bounded-prize patience window. None when no ceiling.
    # ceil(T_tam * observable_ceiling / reference_ceiling), min 1.
    effective_tam_patience_window: int | None

    # Execution belief (execution_belief_t; c_exec_t in design docs).
    # None when no execution channel.
    execution_belief_t: float | None

    # Derived implied duration in ticks. None when not available.
    # round(planned_duration_ticks / max(execution_belief_t, epsilon_exec))
    implied_duration_ticks: int | None

    # Observable plan reference.
    planned_duration_ticks: int | None

    # Progress against plan. None for unbounded-duration initiatives.
    # min(staffed_tick_count / planned_duration_ticks, 1.0)
    progress_fraction: float | None

    # Review tracking.
    review_count: int
    staffed_tick_count: int
    consecutive_reviews_below_tam_ratio: int

    # Observable capability contribution scale (set at generation).
    capability_contribution_scale: float

    # Belief history ring buffer for stagnation detection. Surfaced on the
    # observation so policies can evaluate stagnation without side-channel
    # arguments. Per interfaces.md InitiativeObservation.
    belief_history: tuple[float, ...] = ()

    # Generation-time type tag. Set from ResolvedInitiativeConfig at pool
    # generation and carried through unchanged. None for hand-crafted
    # initiatives that were not produced by the generator.
    #
    # This is observable metadata, not latent ground truth. It is derived
    # from the public pool-design parameters (InitiativeTypeSpec.generation_tag)
    # that are visible in the environment family definition and the run
    # manifest. It does not reveal latent_quality, true_duration_ticks, or
    # any other hidden engine state. canonical_core.md invariant #1
    # (type-independence) prohibits the ENGINE from branching on this field;
    # it does not prohibit the policy from reading it for portfolio
    # classification purposes, which is a governance-architecture choice.
    #
    # The canonical bucket names that appear here (flywheel, right_tail,
    # enabler, quick_win) are defined in config.CANONICAL_BUCKET_NAMES.
    generation_tag: str | None = None


@dataclass(frozen=True)
class TeamObservation:
    """What governance sees for a single team.

    Per interfaces.md TeamObservation.
    """

    team_id: str
    assigned_initiative_id: str | None
    available_next_tick: bool

    # Team size (number of personnel). Surfaced on the observation so
    # policies can match team sizes to initiative requirements without
    # side-channel arguments. Per interfaces.md TeamObservation.
    team_size: int = 1


@dataclass(frozen=True)
class PortfolioSummary:
    """Convenience aggregation of current portfolio state for policy-side
    portfolio management checks.

    These are derived from initiative/team state and do not create a
    second source of truth. The engine surfaces them so policies can
    express portfolio-risk preferences without recomputing from raw
    initiative observations each tick.

    Per interfaces.md PortfolioSummary.
    """

    # Total active labor currently allocated across staffed initiatives.
    active_labor_total: int

    # Labor currently allocated to initiatives whose strategic quality
    # belief is below the policy's low_quality_belief_threshold.
    # None when the policy does not define such a threshold.
    active_labor_below_quality_threshold: int | None

    # Active labor share allocated to initiatives below the configured
    # low-quality threshold. None when no threshold is configured or
    # when active_labor_total == 0.
    low_quality_belief_labor_share: float | None

    # Largest labor share currently allocated to any single active
    # initiative. None when no initiatives are active.
    max_single_initiative_labor_share: float | None


@dataclass(frozen=True)
class GovernanceObservation:
    """Complete policy-visible observation bundle.

    Constructed by the engine at the end of each tick. The policy must
    not receive the full WorldState — only this projection.

    Per interfaces.md GovernanceObservation.
    """

    tick: int
    available_team_count: int
    exec_attention_budget: float
    default_initial_quality_belief: float
    attention_min_effective: float
    attention_max_effective: float
    portfolio_capability_level: float
    # Convenience aggregation for policy-side portfolio checks.
    # Per interfaces.md PortfolioSummary.
    portfolio_summary: PortfolioSummary
    initiatives: tuple[InitiativeObservation, ...]
    teams: tuple[TeamObservation, ...]
