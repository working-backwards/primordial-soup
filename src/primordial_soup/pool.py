"""Initiative pool generator.

This module resolves an InitiativeGeneratorConfig into a concrete tuple of
ResolvedInitiativeConfig instances using the world_seed for deterministic
attribute draws. It is called by the runner before simulation start.

It also provides frontier generation: when the runner needs to materialize
a new initiative from the dynamic frontier, it calls
generate_frontier_initiative() to produce a single initiative with a
degraded quality distribution based on how many initiatives of that
family have already been resolved.

The generator:

    1. Takes an InitiativeGeneratorConfig (type specs with distribution params)
    2. Creates a pool-generator RNG from noise.py (substream 0)
    3. For each type spec, draws the specified count of initiatives
    4. Returns a tuple of ResolvedInitiativeConfig in stable ID order

Generator invariants enforced at construction time (not deferred to
validation):

    - Residual-on-completion requires true_duration_ticks
      (sourcing_and_generation.md)
    - Capability-on-completion requires true_duration_ticks
      (sourcing_and_generation.md)

See:
    - docs/design/sourcing_and_generation.md
    - docs/design/interfaces.md §InitiativeGeneratorConfig
    - docs/design/dynamic_opportunity_frontier.md
"""

from __future__ import annotations

import dataclasses
import logging

from primordial_soup.config import (
    FrontierSpec,
    InitiativeGeneratorConfig,
    InitiativeTypeSpec,
    ResolvedInitiativeConfig,
)
from primordial_soup.noise import (
    SimulationRng,
    create_pool_rng,
    draw_from_distribution,
    draw_normal,
    draw_uniform,
    draw_uniform_int,
)
from primordial_soup.types import (
    BetaDistribution,
    CompletionLumpChannel,
    MajorWinEventChannel,
    ResidualChannel,
    ValueChannels,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_initiative_pool(
    generator_config: InitiativeGeneratorConfig,
    *,
    world_seed: int | None = None,
    pool_rng: SimulationRng | None = None,
) -> tuple[ResolvedInitiativeConfig, ...]:
    """Resolve an InitiativeGeneratorConfig into concrete initiatives.

    Draws initiative attributes stochastically from the type specs using
    the pool-generator RNG substream. Returns a deterministic tuple of
    ResolvedInitiativeConfig in stable initiative_id order.

    Initiatives are assigned sequential IDs ("init-0", "init-1", ...)
    across all type specs, in the order the specs appear in
    generator_config.type_specs.

    Exactly one of world_seed or pool_rng must be provided:
      - world_seed: creates the pool RNG internally via noise.py.
      - pool_rng: uses a pre-built RNG directly (for SimOpt wrapper
        compatibility).

    Args:
        generator_config: The type specs and counts for pool generation.
        world_seed: World seed for creating the pool RNG internally.
        pool_rng: Pre-built pool RNG (for SimOpt wrapper compatibility).

    Returns:
        A tuple of ResolvedInitiativeConfig in stable ID order
        (init-0, init-1, ..., init-N-1).

    Raises:
        ValueError: If neither or both of world_seed/pool_rng are provided,
            or if a generator invariant is violated.
    """
    rng = _resolve_pool_rng(world_seed=world_seed, pool_rng=pool_rng)

    # Generate initiatives in type-spec order, then by count within each
    # type. The initiative_id is assigned sequentially across all types
    # to give a stable global ordering.
    initiatives: list[ResolvedInitiativeConfig] = []
    global_index = 0

    for type_spec in generator_config.type_specs:
        for _ in range(type_spec.count):
            initiative = _generate_single_initiative(
                type_spec=type_spec,
                initiative_index=global_index,
                rng=rng,
            )
            initiatives.append(initiative)
            global_index += 1

    total_count = global_index
    logger.info(
        "Generated initiative pool: %d initiatives from %d type specs.",
        total_count,
        len(generator_config.type_specs),
    )

    return tuple(initiatives)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_pool_rng(
    *,
    world_seed: int | None,
    pool_rng: SimulationRng | None,
) -> SimulationRng:
    """Resolve the pool RNG from either a world_seed or pre-built RNG.

    Args:
        world_seed: World seed for creating the pool RNG.
        pool_rng: Pre-built pool RNG.

    Returns:
        The pool RNG to use for attribute draws.

    Raises:
        ValueError: If neither or both arguments are provided.
    """
    if (world_seed is None) == (pool_rng is None):
        raise ValueError("Exactly one of 'world_seed' or 'pool_rng' must be provided.")

    if pool_rng is not None:
        return pool_rng

    return create_pool_rng(world_seed=world_seed)


def _generate_single_initiative(
    type_spec: InitiativeTypeSpec,
    initiative_index: int,
    rng: SimulationRng,
) -> ResolvedInitiativeConfig:
    """Generate a single initiative from a type spec.

    Draws all stochastic attributes from the pool RNG and assembles
    a complete ResolvedInitiativeConfig. Enforces generator invariants
    before returning.

    Args:
        type_spec: The type spec defining distributions and templates.
        initiative_index: Global sequential index for initiative_id.
        rng: The pool-generator RNG for attribute draws.

    Returns:
        A fully resolved initiative configuration.

    Raises:
        ValueError: If a generator invariant is violated.
    """
    initiative_id = f"init-{initiative_index}"

    # --- Draw core stochastic attributes ---

    # Latent quality (q) — drawn from the type's quality distribution.
    latent_quality = draw_from_distribution(rng, type_spec.quality_distribution)

    # Base signal noise (sigma_base) — uniform draw from the specified range.
    base_signal_st_dev = draw_uniform(
        rng,
        type_spec.base_signal_st_dev_range[0],
        type_spec.base_signal_st_dev_range[1],
    )

    # Dependency level (d) — uniform draw from the specified range.
    dependency_level = draw_uniform(
        rng,
        type_spec.dependency_level_range[0],
        type_spec.dependency_level_range[1],
    )

    # --- Duration draws (when applicable) ---

    # True duration — the latent completion target, hidden from governance.
    true_duration_ticks: int | None = None
    if type_spec.true_duration_range is not None:
        true_duration_ticks = draw_uniform_int(
            rng,
            type_spec.true_duration_range[0],
            type_spec.true_duration_range[1],
        )

    # Planned duration — the observable schedule reference visible to governance.
    planned_duration_ticks: int | None = None
    if type_spec.planned_duration_range is not None:
        planned_duration_ticks = draw_uniform_int(
            rng,
            type_spec.planned_duration_range[0],
            type_spec.planned_duration_range[1],
        )

    # --- Observable ceiling (for right-tail TAM evaluation) ---

    observable_ceiling: float | None = None
    if type_spec.observable_ceiling_distribution is not None:
        observable_ceiling = draw_from_distribution(
            rng,
            type_spec.observable_ceiling_distribution,
        )

    # --- Capability contribution scale (for enablers) ---

    capability_contribution_scale = 0.0
    if type_spec.capability_contribution_scale_range is not None:
        capability_contribution_scale = draw_uniform(
            rng,
            type_spec.capability_contribution_scale_range[0],
            type_spec.capability_contribution_scale_range[1],
        )

    # --- Required team size ---
    # When a range is specified, draw a random team size for this initiative.
    # This creates per-initiative variation in staffing requirements within
    # a family: e.g., some right-tail bets need 5 people (small probe),
    # others need 15 (ambitious program). When no range is specified, all
    # initiatives of this type get the fixed required_team_size from the spec.
    required_team_size = type_spec.required_team_size
    if type_spec.required_team_size_range is not None:
        required_team_size = draw_uniform_int(
            rng,
            type_spec.required_team_size_range[0],
            type_spec.required_team_size_range[1],
        )

    # --- Staffing response scale (staffing intensity effect) ---
    # When the range is None, the resolved initiative gets the default
    # staffing_response_scale of 0.0 (no staffing intensity effect).
    # This preserves backward compatibility: existing configs that do
    # not specify a range produce initiatives that behave identically
    # to before this feature was added.
    staffing_response_scale = 0.0
    if type_spec.staffing_response_scale_range is not None:
        staffing_response_scale = draw_uniform(
            rng,
            type_spec.staffing_response_scale_range[0],
            type_spec.staffing_response_scale_range[1],
        )

    # --- Screening signal (ex ante intake evaluation) ---
    # When screening_signal_st_dev is set, the generator draws a noisy
    # signal correlated with true quality to set the initiative's
    # initial_quality_belief. This models the organization's intake
    # screening process (business cases, feasibility studies, etc.).
    # Per post_expert_review_plan.md Step 3 (Option A):
    #     screening_signal = clamp(q + Normal(0, sigma_screen), 0, 1)
    initial_quality_belief: float | None = None
    if type_spec.screening_signal_st_dev is not None:
        raw_signal = latent_quality + draw_normal(
            rng, mean=0.0, st_dev=type_spec.screening_signal_st_dev
        )
        # Clamp to [0, 1] — belief is a probability-like quantity.
        initial_quality_belief = max(0.0, min(1.0, raw_signal))

    # --- Build value channels from the type spec templates ---

    value_channels = _build_value_channels(
        type_spec=type_spec,
        latent_quality=latent_quality,
        rng=rng,
    )

    # --- Assemble the resolved initiative ---

    initiative = ResolvedInitiativeConfig(
        initiative_id=initiative_id,
        latent_quality=latent_quality,
        dependency_level=dependency_level,
        base_signal_st_dev=base_signal_st_dev,
        value_channels=value_channels,
        true_duration_ticks=true_duration_ticks,
        planned_duration_ticks=planned_duration_ticks,
        observable_ceiling=observable_ceiling,
        capability_contribution_scale=capability_contribution_scale,
        generation_tag=type_spec.generation_tag,
        initial_quality_belief=initial_quality_belief,
        initial_execution_belief=type_spec.initial_execution_belief,
        required_team_size=required_team_size,
        staffing_response_scale=staffing_response_scale,
    )

    # --- Enforce generator invariants before returning ---
    _enforce_generator_invariants(initiative)

    return initiative


def _build_value_channels(
    type_spec: InitiativeTypeSpec,
    latent_quality: float,
    rng: SimulationRng,
) -> ValueChannels:
    """Build the ValueChannels for an initiative from its type spec.

    Draws stochastic channel parameters (residual rate, residual decay,
    completion lump value) from the type spec ranges using the pool RNG.

    Args:
        type_spec: The type spec with channel templates.
        latent_quality: The initiative's drawn latent quality (q),
            used for major_win threshold evaluation.
        rng: The pool-generator RNG.

    Returns:
        A fully configured ValueChannels instance.
    """
    # --- Completion lump channel ---
    # When enabled, the realized_value is drawn from the specified range.
    lump_value: float | None = None
    if type_spec.completion_lump_enabled and type_spec.completion_lump_value_range is not None:
        lump_value = draw_uniform(
            rng,
            type_spec.completion_lump_value_range[0],
            type_spec.completion_lump_value_range[1],
        )

    completion_lump = CompletionLumpChannel(
        enabled=type_spec.completion_lump_enabled,
        realized_value=lump_value,
    )

    # --- Residual channel ---
    # Rate and decay drawn from ranges when the channel is enabled.
    residual_rate = 0.0
    residual_decay = 0.0
    if type_spec.residual_enabled:
        if type_spec.residual_rate_range is not None:
            residual_rate = draw_uniform(
                rng,
                type_spec.residual_rate_range[0],
                type_spec.residual_rate_range[1],
            )
        if type_spec.residual_decay_range is not None:
            residual_decay = draw_uniform(
                rng,
                type_spec.residual_decay_range[0],
                type_spec.residual_decay_range[1],
            )

    residual = ResidualChannel(
        enabled=type_spec.residual_enabled,
        activation_state=type_spec.residual_activation_state,
        residual_rate=residual_rate,
        residual_decay=residual_decay,
    )

    # --- Major-win event channel ---
    # is_major_win is a deterministic function of latent quality:
    #   is_major_win = (q >= q_major_win_threshold)
    # Per sourcing_and_generation.md canonical generation rule.
    is_major_win = False
    if type_spec.major_win_event_enabled:
        is_major_win = latent_quality >= type_spec.q_major_win_threshold

    major_win_event = MajorWinEventChannel(
        enabled=type_spec.major_win_event_enabled,
        is_major_win=is_major_win,
    )

    return ValueChannels(
        completion_lump=completion_lump,
        residual=residual,
        major_win_event=major_win_event,
    )


def _enforce_generator_invariants(initiative: ResolvedInitiativeConfig) -> None:
    """Enforce generator-time construction invariants.

    These are construction invariants that the generator must enforce to
    produce well-formed initiatives. They are distinct from validation
    rules (which belong to the runner and config.validate_configuration).

    Per sourcing_and_generation.md:
      - Residual-on-completion requires true_duration_ticks
      - Capability-on-completion requires true_duration_ticks

    Args:
        initiative: The fully assembled initiative to check.

    Raises:
        ValueError: If a generator invariant is violated.
    """
    prefix = f"Generator invariant violated for '{initiative.initiative_id}'"

    # Residual-on-completion requires duration: the engine cannot detect
    # the completion transition that triggers residual activation without
    # a defined true_duration_ticks.
    residual = initiative.value_channels.residual
    if (
        residual.enabled
        and residual.activation_state == "completed"
        and initiative.true_duration_ticks is None
    ):
        raise ValueError(
            f"{prefix}: residual with activation_state='completed' "
            "requires true_duration_ticks to be set."
        )

    # Capability-on-completion requires duration: enabler effects are
    # realized only at the completion transition, so an initiative
    # without a completion condition cannot validly contribute capability.
    if initiative.capability_contribution_scale > 0 and initiative.true_duration_ticks is None:
        raise ValueError(
            f"{prefix}: capability_contribution_scale > 0 requires true_duration_ticks to be set."
        )


# ---------------------------------------------------------------------------
# Frontier generation
# ---------------------------------------------------------------------------


def generate_frontier_initiative(
    type_spec: InitiativeTypeSpec,
    frontier_spec: FrontierSpec,
    initiative_index: int,
    n_resolved: int,
    rng: SimulationRng,
    created_tick: int = 0,
) -> ResolvedInitiativeConfig:
    """Generate a single initiative from the dynamic frontier.

    Draws initiative attributes from the same distributions as the initial
    pool, except the quality distribution's alpha is scaled down based on
    how many initiatives of this family have been resolved (completed or
    stopped). All other attributes (duration, dependency, value channels)
    are drawn from the same ranges as the initial pool.

    Functional form (per dynamic_opportunity_frontier.md §1):
        effective_alpha = base_alpha * max(floor, 1.0 - rate * n_resolved)

    The RNG passed here should be the per-family frontier RNG stream
    (created via noise.create_frontier_rng), NOT the pool-generator RNG.
    This ensures cross-family independence and deterministic draw ordering.

    Args:
        type_spec: The type spec for this family (with distribution
            params and value channel templates).
        frontier_spec: Frontier degradation parameters.
        initiative_index: Global sequential index for the initiative_id.
            Continues from where the initial pool ended.
        n_resolved: Number of initiatives of this family that have been
            resolved (completed + stopped) so far.
        rng: The per-family frontier RNG stream.
        created_tick: The tick at which this initiative is materialized.

    Returns:
        A fully resolved initiative configuration with degraded quality.
    """
    # Compute the effective alpha multiplier based on depletion history.
    alpha_multiplier = max(
        frontier_spec.frontier_quality_floor,
        1.0 - frontier_spec.frontier_degradation_rate * n_resolved,
    )

    # Create a modified type spec with the degraded quality distribution.
    modified_spec = _apply_quality_degradation(type_spec, alpha_multiplier)

    # Generate the initiative using standard generation logic with the
    # frontier RNG (not the pool RNG).
    initiative = _generate_single_initiative(
        type_spec=modified_spec,
        initiative_index=initiative_index,
        rng=rng,
    )

    # Set created_tick for frontier-generated initiatives. The initial
    # pool uses created_tick=0 (default); frontier initiatives record
    # the tick at which they were materialized for age tracking and
    # time-to-major-win reporting.
    if created_tick > 0:
        initiative = dataclasses.replace(initiative, created_tick=created_tick)

    return initiative


def _apply_quality_degradation(
    type_spec: InitiativeTypeSpec,
    alpha_multiplier: float,
) -> InitiativeTypeSpec:
    """Create a copy of type_spec with degraded quality alpha.

    Scales the alpha parameter of the quality BetaDistribution by
    alpha_multiplier while keeping beta unchanged. This shifts the
    distribution's mean downward, modeling declining opportunity quality
    as the frontier is consumed.

    Args:
        type_spec: The original type spec.
        alpha_multiplier: Factor to multiply alpha by (in (0, 1]).

    Returns:
        A new InitiativeTypeSpec with the scaled quality distribution.

    Raises:
        TypeError: If the quality distribution is not a BetaDistribution.
    """
    quality_dist = type_spec.quality_distribution
    if not isinstance(quality_dist, BetaDistribution):
        raise TypeError(
            f"Frontier quality degradation requires a BetaDistribution, "
            f"got {type(quality_dist).__name__}. Only Beta distributions "
            "support alpha-scaling for frontier degradation."
        )

    degraded_dist = BetaDistribution(
        alpha=quality_dist.alpha * alpha_multiplier,
        beta=quality_dist.beta,
    )

    return dataclasses.replace(type_spec, quality_distribution=degraded_dist)


def generate_prize_refresh_initiative(
    type_spec: InitiativeTypeSpec,
    frontier_spec: FrontierSpec,
    initiative_index: int,
    prize_id: str,
    observable_ceiling: float,
    attempt_count: int,
    rng: SimulationRng,
    created_tick: int = 0,
) -> ResolvedInitiativeConfig:
    """Generate a fresh right-tail initiative for a persistent prize descriptor.

    Draws a fresh approach (latent quality, dependency, etc.) for an
    existing market opportunity (observable ceiling). The ceiling is
    preserved from the original prize; all other attributes are drawn
    fresh from the type spec distributions. The quality may optionally
    be degraded based on the number of previous failed attempts.

    Per dynamic_opportunity_frontier.md §2 (prize-preserving refresh):
    - Same observable_ceiling as the original prize.
    - Fresh latent_quality from the quality distribution, optionally
      degraded by right_tail_refresh_quality_degradation * attempt_count.
    - Fresh is_major_win determined by threshold rule on fresh quality.
    - New unique initiative_id and prize_id linking to the original prize.

    Args:
        type_spec: The right-tail type spec.
        frontier_spec: Frontier parameters (for refresh quality degradation).
        initiative_index: Global sequential index for initiative_id.
        prize_id: The stable prize descriptor ID to link this attempt to.
        observable_ceiling: The persistent market opportunity ceiling.
        attempt_count: Number of previous attempts (for quality degradation).
        rng: The right-tail frontier RNG stream.
        created_tick: The tick at which this initiative is materialized.

    Returns:
        A ResolvedInitiativeConfig with the prize's ceiling and fresh quality.
    """
    # Compute per-prize quality degradation based on failed attempts.
    # attempt_count includes the original attempt that was stopped.
    refresh_degradation = frontier_spec.right_tail_refresh_quality_degradation
    if refresh_degradation > 0.0 and attempt_count > 0:
        # Each failed attempt reduces alpha for this specific prize.
        alpha_multiplier = max(
            frontier_spec.frontier_quality_floor,
            1.0 - refresh_degradation * attempt_count,
        )
        modified_spec = _apply_quality_degradation(type_spec, alpha_multiplier)
    else:
        modified_spec = type_spec

    # Generate the initiative with standard logic but using the
    # frontier RNG (not the pool RNG).
    initiative = _generate_single_initiative(
        type_spec=modified_spec,
        initiative_index=initiative_index,
        rng=rng,
    )

    # Override the observable_ceiling with the prize's persistent ceiling
    # (instead of drawing a fresh one from the distribution).
    # Also set the prize_id to link this attempt to the prize descriptor,
    # and set created_tick for frontier-generated initiatives.
    initiative = dataclasses.replace(
        initiative,
        observable_ceiling=observable_ceiling,
        prize_id=prize_id,
        prize_attempt_count=attempt_count,
        created_tick=created_tick if created_tick > 0 else initiative.created_tick,
    )

    return initiative
