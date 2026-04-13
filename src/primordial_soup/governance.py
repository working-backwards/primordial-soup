"""Governance decision primitives.

This module exports pure functions that each evaluate a single governance
concern using the policy-visible observation bundle and governance
configuration. These primitives are the building blocks that policy
archetypes in policy.py compose into complete governance strategies.

Each primitive operates on GovernanceObservation / InitiativeObservation
and GovernanceConfig only. No primitive accesses WorldState, ModelConfig,
or latent initiative attributes. This enforces the observation boundary.

Per governance.md stop/continue criteria, selection and portfolio
management semantics, and execution belief and cost tolerance sections.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primordial_soup.config import GovernanceConfig
    from primordial_soup.observation import (
        InitiativeObservation,
        PortfolioSummary,
    )

logger = logging.getLogger(__name__)


# ============================================================================
# Stop / continue decision primitives
# ============================================================================


def should_stop_confidence_decline(
    initiative: InitiativeObservation,
    config: GovernanceConfig,
) -> bool:
    """Evaluate the confidence-decline stop rule.

    Returns True if the initiative's strategic quality belief has dropped
    below the confidence_decline_threshold (theta_stop). This is a
    policy-side decision rule — no engine counters are needed.

    Per governance.md section 3 (confidence decline / discretionary stop).

    Args:
        initiative: Policy-visible observation for the initiative.
        config: Immutable governance parameters.

    Returns:
        True if quality_belief_t < confidence_decline_threshold and
        the threshold is enabled (not None). False otherwise.
    """
    # theta_stop = None means confidence-decline stopping is disabled.
    if config.confidence_decline_threshold is None:
        return False

    return initiative.quality_belief_t < config.confidence_decline_threshold


def should_stop_tam_adequacy(
    initiative: InitiativeObservation,
) -> bool:
    """Evaluate the TAM (bounded-prize) adequacy stop rule.

    Returns True if a bounded-prize initiative has persistently failed
    to earn continued patience under the prize-relative patience rule.
    The engine maintains consecutive_reviews_below_tam_ratio and
    effective_tam_patience_window; this primitive simply checks the
    threshold condition.

    Only applies to initiatives with an observable_ceiling.
    Initiatives without a bounded prize always return False.

    Per governance.md section 1 (prize adequacy / bounded-prize patience).

    Args:
        initiative: Policy-visible observation for the initiative.

    Returns:
        True if the TAM inadequacy counter has reached or exceeded
        the effective patience window. False otherwise.
    """
    # TAM adequacy only applies to bounded-prize initiatives.
    if initiative.observable_ceiling is None:
        return False

    # effective_tam_patience_window is None when no ceiling; guarded above.
    if initiative.effective_tam_patience_window is None:
        return False

    # Stop when consecutive below-threshold reviews reach the patience window.
    # Per governance.md: "stop when consecutive_reviews_below_tam_ratio
    # >= T_tam_effective".
    return (
        initiative.consecutive_reviews_below_tam_ratio >= initiative.effective_tam_patience_window
    )


def should_stop_stagnation(
    initiative: InitiativeObservation,
    config: GovernanceConfig,
) -> bool:
    """Evaluate the stagnation stop rule (conjunctive: stasis AND patience).

    This is a two-leg conjunctive rule:
    1. Informational stasis: quality belief has not moved by more than
       stagnation_belief_change_threshold over the stagnation window (W_stag staffed ticks).
    2. Second-leg patience condition:
       - For bounded-prize initiatives: consecutive_reviews_below_tam_ratio > 0
       - For non-TAM initiatives: quality_belief_t <= default_initial_quality_belief

    Both conditions must hold simultaneously for a stagnation stop.

    Per governance.md section 2 (stagnation rule).

    Args:
        initiative: Policy-visible observation for the initiative.
            belief_history is available on initiative.belief_history.
        config: Immutable governance parameters.

    Returns:
        True if both informational stasis and the second-leg patience
        condition hold. False otherwise.
    """
    stagnation_window = config.stagnation_window_staffed_ticks
    belief_history = initiative.belief_history

    # Stagnation comparison requires a full window of history.
    # Per governance.md: "available once len(belief_history) == W_stag".
    if len(belief_history) < stagnation_window:
        return False

    # --- Leg 1: Informational stasis ---
    # belief_history[0] is the oldest retained belief in the rolling
    # staffed-tick window. Per governance.md sliding window implementation.
    oldest_belief = belief_history[0]
    belief_change_over_window = abs(initiative.quality_belief_t - oldest_belief)

    # If belief has moved more than epsilon, initiative is not stagnant.
    is_informationally_stagnant = (
        belief_change_over_window < config.stagnation_belief_change_threshold
    )
    if not is_informationally_stagnant:
        return False

    # --- Leg 2: Second-leg patience condition ---
    if initiative.observable_ceiling is not None:
        # Bounded-prize: fails patience when any reviews are below TAM ratio.
        # Per governance.md: "consecutive_reviews_below_tam_ratio > 0".
        second_leg_holds = initiative.consecutive_reviews_below_tam_ratio > 0
    else:
        # Non-TAM: fails patience when belief has not risen above the
        # canonical neutral baseline.
        # Per governance.md: "quality_belief_t <= default_initial_quality_belief".
        second_leg_holds = initiative.quality_belief_t <= config.default_initial_quality_belief

    return second_leg_holds


def should_stop_execution_overrun(
    initiative: InitiativeObservation,
    config: GovernanceConfig,
) -> bool:
    """Evaluate the execution-overrun stop rule.

    Returns True if the initiative's execution belief has dropped below
    the exec_overrun_threshold. This is a policy-side decision — the
    engine does not automatically stop initiatives for overrun.

    Per governance.md execution belief and cost tolerance section.

    Args:
        initiative: Policy-visible observation for the initiative.
        config: Immutable governance parameters.

    Returns:
        True if execution_belief_t is available and below the threshold.
        False if no execution channel or threshold is disabled (None).
    """
    # No threshold or no execution channel → rule does not apply.
    if config.exec_overrun_threshold is None:
        return False
    if initiative.execution_belief_t is None:
        return False

    return initiative.execution_belief_t < config.exec_overrun_threshold


# ============================================================================
# Attention allocation helpers
# ============================================================================


def compute_equal_attention(
    active_staffed_count: int,
    config: GovernanceConfig,
) -> float:
    """Compute equal attention level for active staffed initiatives.

    Distributes the executive attention budget equally across all active
    staffed initiatives, clamped to the per-initiative bounds
    [attention_min, attention_max_effective].

    If no initiatives are active, returns 0.0.

    Args:
        active_staffed_count: Number of active, staffed initiatives
            that should receive attention this tick.
        config: Immutable governance parameters.

    Returns:
        The per-initiative attention level, clamped to bounds.
    """
    if active_staffed_count <= 0:
        return 0.0

    # Zero budget means no executive attention is allocated. Per
    # governance.md §Zero-budget special case: the policy should emit
    # no SetExecAttention actions, relying on the omission-means-zero
    # contract. Return 0.0 so the caller can skip attention actions.
    if config.exec_attention_budget == 0.0:
        return 0.0

    # Raw equal share of the budget.
    raw_share = config.exec_attention_budget / active_staffed_count

    # Resolve effective max: None means 1.0 per interfaces.md.
    attention_max_effective = config.attention_max if config.attention_max is not None else 1.0

    # Clamp to per-initiative bounds.
    clamped = max(config.attention_min, min(raw_share, attention_max_effective))

    return clamped


def compute_weighted_attention(
    initiative_weights: tuple[tuple[str, float], ...],
    config: GovernanceConfig,
) -> tuple[tuple[str, float], ...]:
    """Compute attention allocation weighted by initiative importance.

    Distributes the executive attention budget proportionally to the
    given weights, then clamps each allocation to the per-initiative
    bounds [attention_min, attention_max_effective].

    If the total after clamping exceeds budget, all allocations are
    scaled down proportionally (then re-clamped to attention_min).

    Args:
        initiative_weights: Tuples of (initiative_id, weight). Weights
            must be >= 0. Zero-weight initiatives receive attention_min.
        config: Immutable governance parameters.

    Returns:
        Tuples of (initiative_id, attention) for each initiative.
    """
    if not initiative_weights:
        return ()

    # Zero budget means no executive attention is allocated. Per
    # governance.md §Zero-budget special case: return all-zero
    # allocations so the caller can skip attention actions.
    if config.exec_attention_budget == 0.0:
        return tuple((init_id, 0.0) for init_id, _ in initiative_weights)

    # Resolve effective max: None means 1.0 per interfaces.md.
    attention_max_effective = config.attention_max if config.attention_max is not None else 1.0
    budget = config.exec_attention_budget

    total_weight = sum(weight for _, weight in initiative_weights)

    # Compute raw proportional allocations.
    if total_weight <= 0:
        # All weights zero or negative — distribute equally.
        raw_share = budget / len(initiative_weights)
        allocations = [(init_id, raw_share) for init_id, _ in initiative_weights]
    else:
        allocations = [
            (init_id, (weight / total_weight) * budget) for init_id, weight in initiative_weights
        ]

    # Clamp to per-initiative bounds.
    clamped = [
        (init_id, max(config.attention_min, min(attention, attention_max_effective)))
        for init_id, attention in allocations
    ]

    # Check budget feasibility after clamping.
    total_clamped = sum(attention for _, attention in clamped)
    if total_clamped > budget and total_clamped > 0:
        # Scale down proportionally, preserving at least attention_min.
        scale_factor = budget / total_clamped
        clamped = [
            (init_id, max(config.attention_min, attention * scale_factor))
            for init_id, attention in clamped
        ]

    return tuple(clamped)


# ============================================================================
# Selection and ranking helpers
# ============================================================================


def expected_prize_value(initiative: InitiativeObservation) -> float:
    """Compute expected prize value for a bounded-prize initiative.

    Per governance.md: expected_prize_value = quality_belief_t * observable_ceiling.

    Returns 0.0 if the initiative has no observable_ceiling.

    Args:
        initiative: Policy-visible observation for the initiative.

    Returns:
        The expected prize value based on current strategic belief.
    """
    if initiative.observable_ceiling is None:
        return 0.0
    return initiative.quality_belief_t * initiative.observable_ceiling


def expected_prize_value_density(initiative: InitiativeObservation) -> float:
    """Compute labor-normalized expected prize value for selection ranking.

    Per governance.md selection convention: initiatives are ranked by
    expected_prize_value / required_team_size to keep labor exposure
    explicit during bounded-prize selection.

    Returns 0.0 if no observable_ceiling.

    Args:
        initiative: Policy-visible observation for the initiative.

    Returns:
        expected_prize_value divided by required_team_size.
    """
    prize = expected_prize_value(initiative)
    # required_team_size is always >= 1 (validated at config time).
    return prize / initiative.required_team_size


def rank_unassigned_bounded_prize(
    initiatives: tuple[InitiativeObservation, ...],
) -> tuple[InitiativeObservation, ...]:
    """Rank unassigned bounded-prize initiatives by prize value density.

    Filters to unassigned initiatives with an observable_ceiling, then
    sorts by descending expected_prize_value_density (ties broken by
    initiative_id for determinism).

    Per governance.md ranking convention for bounded-prize selection.

    Args:
        initiatives: All initiative observations from the current tick.

    Returns:
        Sorted tuple of unassigned bounded-prize initiatives, highest
        prize density first.
    """
    candidates = [
        init
        for init in initiatives
        if init.lifecycle_state == "unassigned" and init.observable_ceiling is not None
    ]

    # Sort by descending prize density, then ascending id for determinism.
    candidates.sort(key=lambda i: (-expected_prize_value_density(i), i.initiative_id))

    return tuple(candidates)


def rank_unassigned_initiatives(
    initiatives: tuple[InitiativeObservation, ...],
) -> tuple[InitiativeObservation, ...]:
    """Rank all unassigned initiatives for team assignment.

    Bounded-prize initiatives are ranked by expected prize value density.
    Non-bounded initiatives (no observable_ceiling) are ranked after
    bounded-prize ones, ordered by descending quality_belief_t then
    ascending initiative_id for determinism.

    Args:
        initiatives: All initiative observations from the current tick.

    Returns:
        Sorted tuple of all unassigned initiatives — bounded-prize first
        (by density), then non-bounded (by belief).
    """
    bounded = []
    unbounded = []

    for init in initiatives:
        if init.lifecycle_state != "unassigned":
            continue
        if init.observable_ceiling is not None:
            bounded.append(init)
        else:
            unbounded.append(init)

    # Sort bounded by descending prize density, ties by id.
    bounded.sort(key=lambda i: (-expected_prize_value_density(i), i.initiative_id))

    # Sort unbounded by descending quality belief, ties by id.
    unbounded.sort(key=lambda i: (-i.quality_belief_t, i.initiative_id))

    return tuple(bounded + unbounded)


# ============================================================================
# Portfolio-risk check helpers
# ============================================================================


def is_low_quality_labor_share_exceeded(
    portfolio_summary: PortfolioSummary,
    config: GovernanceConfig,
) -> bool:
    """Check if the low-quality labor share exceeds the configured cap.

    This is a policy-side check using PortfolioSummary. The engine does
    not enforce this — it is a governance preference.

    Per governance.md selection and portfolio management semantics.

    Args:
        portfolio_summary: Current portfolio state from observation.
        config: Immutable governance parameters.

    Returns:
        True if a low-quality threshold is configured and the current
        labor share exceeds max_low_quality_belief_labor_share.
        False if either threshold or cap is None, or if no active labor.
    """
    # Both threshold and cap must be configured for this check.
    if config.low_quality_belief_threshold is None:
        return False
    if config.max_low_quality_belief_labor_share is None:
        return False

    # If no active labor or no share computed, cannot exceed.
    if portfolio_summary.low_quality_belief_labor_share is None:
        return False

    return (
        portfolio_summary.low_quality_belief_labor_share
        > config.max_low_quality_belief_labor_share
    )


def is_single_initiative_concentration_exceeded(
    portfolio_summary: PortfolioSummary,
    config: GovernanceConfig,
) -> bool:
    """Check if any single initiative exceeds the concentration cap.

    This is a policy-side check using PortfolioSummary. The engine does
    not enforce this — it is a governance preference.

    Per governance.md selection and portfolio management semantics.

    Args:
        portfolio_summary: Current portfolio state from observation.
        config: Immutable governance parameters.

    Returns:
        True if a concentration cap is configured and the largest
        single-initiative labor share exceeds it.
        False if cap is None or no active labor.
    """
    if config.max_single_initiative_labor_share is None:
        return False

    if portfolio_summary.max_single_initiative_labor_share is None:
        return False

    return (
        portfolio_summary.max_single_initiative_labor_share
        > config.max_single_initiative_labor_share
    )


def would_assignment_exceed_concentration(
    initiative: InitiativeObservation,
    portfolio_summary: PortfolioSummary,
    config: GovernanceConfig,
) -> bool:
    """Check if assigning a team to this initiative would exceed concentration cap.

    Predicts the post-assignment labor share of the initiative and checks
    against max_single_initiative_labor_share.

    Args:
        initiative: The candidate initiative for assignment.
        portfolio_summary: Current portfolio state.
        config: Governance config with optional concentration cap.

    Returns:
        True if the assignment would exceed the cap. False if no cap
        is configured or the assignment is within limits.
    """
    if config.max_single_initiative_labor_share is None:
        return False

    # Total labor after assignment: existing + new team's size.
    new_total = portfolio_summary.active_labor_total + initiative.required_team_size

    if new_total <= 0:
        return False

    # The initiative's labor share after assignment.
    new_share = initiative.required_team_size / new_total

    return new_share > config.max_single_initiative_labor_share


def would_assignment_exceed_low_quality_share(
    initiative: InitiativeObservation,
    portfolio_summary: PortfolioSummary,
    config: GovernanceConfig,
) -> bool:
    """Check if assigning a team to a low-quality initiative would exceed cap.

    Predicts the post-assignment low-quality labor share and checks
    against max_low_quality_belief_labor_share.

    Args:
        initiative: The candidate initiative for assignment.
        portfolio_summary: Current portfolio state.
        config: Governance config with optional low-quality cap.

    Returns:
        True if the initiative is below the low-quality threshold and
        assigning it would exceed the cap. False if thresholds are not
        configured or the assignment is within limits.
    """
    if config.low_quality_belief_threshold is None:
        return False
    if config.max_low_quality_belief_labor_share is None:
        return False

    # Initiative is not low-quality → assignment is fine.
    if initiative.quality_belief_t >= config.low_quality_belief_threshold:
        return False

    # Predict post-assignment state.
    new_total = portfolio_summary.active_labor_total + initiative.required_team_size
    current_low = (
        portfolio_summary.active_labor_below_quality_threshold
        if portfolio_summary.active_labor_below_quality_threshold is not None
        else 0
    )
    new_low = current_low + initiative.required_team_size

    if new_total <= 0:
        return False

    new_share = new_low / new_total
    return new_share > config.max_low_quality_belief_labor_share


# ============================================================================
# Initiative bucket classification (generation_tag-based)
# ============================================================================
#
# These functions classify initiatives into canonical buckets for
# policy-side portfolio mix targeting. The engine never calls them;
# they are used only by governance policy code.
#
# Classification uses InitiativeObservation.generation_tag, which is
# observable metadata set at pool generation time. It is not latent
# ground truth — it comes from the public InitiativeTypeSpec parameters
# visible in the environment family definition and the run manifest.
#
# The canonical bucket names are defined in config.CANONICAL_BUCKET_NAMES:
#   flywheel, right_tail, enabler, quick_win
#
# This is a deliberate observation-interface extension. See the
# generation_tag field comment on InitiativeObservation for the full
# rationale on why this does not violate type-independence.


def classify_initiative_bucket(
    initiative: InitiativeObservation,
) -> str:
    """Classify an initiative into a canonical bucket using generation_tag.

    Returns the initiative's generation_tag if it is one of the canonical
    bucket names (flywheel, right_tail, enabler, quick_win). Returns
    "uncategorized" if generation_tag is None or not a canonical name.

    This is the single source of truth for bucket classification at
    runtime. The canonical bucket names are defined in
    config.CANONICAL_BUCKET_NAMES. The business intent registry
    (business_intent_registry.yaml) documents the same names and their
    business meanings; both sources must agree.

    "uncategorized" is not a valid mix-target bucket name. It cannot
    appear in PortfolioMixTargets.bucket_targets (the workbench
    validates this). In the policy's mix-target re-ranking,
    uncategorized initiatives are treated as residual: they have an
    implicit target of 0.0, so they land in the at-or-over-target
    group and receive no mix-target priority boost. They are still
    assignable — just not prioritized by mix targets.

    Args:
        initiative: The initiative observation to classify.

    Returns:
        A canonical bucket name, or "uncategorized" if the initiative
        has no generation_tag or a non-canonical tag.
    """
    from primordial_soup.config import CANONICAL_BUCKET_NAMES

    tag = initiative.generation_tag
    if tag is not None and tag in CANONICAL_BUCKET_NAMES:
        return tag
    return "uncategorized"


def compute_current_portfolio_mix(
    initiatives: tuple[InitiativeObservation, ...],
    stopped_ids: set[str],
) -> dict[str, float]:
    """Compute the current labor-share distribution across initiative buckets.

    Counts active, staffed initiatives (excluding those just stopped this
    tick) and computes each bucket's share of active labor. Uses
    generation_tag-based classification via classify_initiative_bucket().

    Args:
        initiatives: All initiative observations from the current tick.
        stopped_ids: Initiative ids being stopped this tick (excluded
            from the computation since their teams will be freed).

    Returns:
        Dict mapping bucket name to current labor share (0.0–1.0).
        Empty dict if no active staffed labor exists after stops.
    """
    bucket_labor: dict[str, int] = {}
    total_labor = 0

    for init in initiatives:
        # Only count active, currently staffed initiatives that are
        # not being stopped this tick.
        if init.lifecycle_state != "active":
            continue
        if init.assigned_team_id is None:
            continue
        if init.initiative_id in stopped_ids:
            continue

        bucket = classify_initiative_bucket(init)
        bucket_labor[bucket] = bucket_labor.get(bucket, 0) + init.required_team_size
        total_labor += init.required_team_size

    if total_labor == 0:
        return {}

    return {bucket: labor / total_labor for bucket, labor in bucket_labor.items()}
