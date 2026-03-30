"""Tick loop orchestration — the only impure module in the simulator.

This module runs the simulation: resolving generators, seeding RNGs,
initializing world state, executing the tick loop, constructing
governance observations, invoking policies, and assembling results.

The runner is responsible for:
    - Resolving initiative_generator into a concrete initiatives list
    - Seeding all RNGs from world_seed
    - Initializing WorldState (all UNASSIGNED, all teams idle, C_t=1.0)
    - Constructing GovernanceObservation each tick (observation boundary)
    - Computing derived fields (effective_tam_patience_window,
      implied_duration_ticks, progress_fraction, PortfolioSummary)
    - Extracting belief_histories and team_sizes for policy invocation
    - Collecting per-tick records and events
    - Assembling RunResult via reporting.py aggregation

Key invariants enforced here:
    - Observation boundary: latent_quality and true_duration_ticks NEVER
      appear in GovernanceObservation
    - Horizon is measurement boundary, not lifecycle event
    - Idle team-tick = team unassigned at start of tick (ramp is NOT idle)
    - All iteration in stable id order
    - exec_attention_a_t is REALIZED attention after engine validation

Design references:
    - docs/design/core_simulator.md (tick ordering, idle counting)
    - docs/design/interfaces.md (runner responsibilities, batch interface)
    - docs/design/review_and_reporting.md (output schema)
"""

from __future__ import annotations

import dataclasses
import logging
import math
from typing import TYPE_CHECKING

from primordial_soup.actions import SetExecAttentionAction
from primordial_soup.config import validate_configuration
from primordial_soup.events import AttentionFeasibilityViolationEvent, ReassignmentEvent
from primordial_soup.learning import ramp_multiplier
from primordial_soup.noise import (
    create_all_initiative_rngs,
    create_frontier_rng,
    create_initiative_rng_pair,
)
from primordial_soup.observation import (
    GovernanceObservation,
    InitiativeObservation,
    PortfolioSummary,
    TeamObservation,
)
from primordial_soup.pool import (
    generate_frontier_initiative,
    generate_initiative_pool,
    generate_prize_refresh_initiative,
)
from primordial_soup.reporting import (
    PerInitiativeTickRecord,
    PortfolioTickRecord,
    RunCollector,
    RunManifest,
    RunResult,
    assemble_run_result,
)
from primordial_soup.state import (
    FamilyFrontierState,
    InitiativeState,
    PrizeDescriptor,
    TeamState,
    WorldState,
)
from primordial_soup.tick import TickResult, apply_actions, step_world
from primordial_soup.types import (
    MIN_EXECUTION_BELIEF,
    LifecycleState,
    ReassignmentTrigger,
    StopContinueDecision,
)

if TYPE_CHECKING:
    from primordial_soup.actions import GovernanceActions
    from primordial_soup.config import (
        GovernanceConfig,
        InitiativeTypeSpec,
        ResolvedInitiativeConfig,
        SimulationConfiguration,
        WorkforceConfig,
    )
    from primordial_soup.noise import InitiativeRngPair, SimulationRng
    from primordial_soup.policy import GovernancePolicy

logger = logging.getLogger(__name__)

# Engine version identifier for manifest provenance.
ENGINE_VERSION: str = "0.1.0"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_single_regime(
    config: SimulationConfiguration,
    policy: GovernancePolicy,
) -> tuple[RunResult, WorldState]:
    """Execute a single simulation run.

    This is the main entry point for running one governance regime
    against one world configuration. It resolves generators, seeds
    RNGs, runs the full tick loop, and assembles the RunResult.

    Args:
        config: Complete simulation configuration.
        policy: Governance policy implementation.

    Returns:
        Tuple of (RunResult, final WorldState). The RunResult contains
        all primary outputs, event logs, and per-tick records
        (conditional on ReportingConfig flags). The WorldState is the
        final simulation state, provided for downstream reporting that
        needs per-initiative final state (e.g., InitiativeFinalState
        snapshots for run-bundle generation).

    Raises:
        ValueError: If configuration validation fails.
    """
    # --- Step 1: Validate configuration ---
    validate_configuration(config)

    # --- Step 2: Resolve initiative generator if provided ---
    initiative_configs = _resolve_initiatives(config)

    # --- Step 3: Seed all per-initiative RNGs ---
    rng_pairs = create_all_initiative_rngs(
        world_seed=config.world_seed,
        initiative_count=len(initiative_configs),
    )

    # --- Step 4: Initialize world state (including frontier state) ---
    world_state = _initialize_world_state(config, initiative_configs)

    # --- Step 5: Build manifest ---
    manifest = RunManifest(
        policy_id=config.governance.policy_id,
        world_seed=config.world_seed,
        is_replay=False,
        resolved_configuration=config,
        resolved_initiatives=initiative_configs,
        engine_version=ENGINE_VERSION,
    )

    # --- Step 6: Main tick loop ---
    # The tick loop may extend initiative_configs and rng_pairs via
    # frontier materialization. It returns the final versions.
    collector = RunCollector()
    world_state, initiative_configs, rng_pairs = _run_tick_loop(
        world_state=world_state,
        config=config,
        policy=policy,
        initiative_configs=initiative_configs,
        rng_pairs=rng_pairs,
        collector=collector,
    )

    # --- Step 7: Update manifest with final initiative configs ---
    # Frontier-generated initiatives are not in the original manifest.
    # Update it so the run result includes all realized initiatives.
    manifest = dataclasses.replace(manifest, resolved_initiatives=initiative_configs)

    # --- Step 8: Assemble RunResult ---
    logger.info(
        "Run complete: seed=%d, policy=%s, horizon=%d ticks.",
        config.world_seed,
        config.governance.policy_id,
        config.time.tick_horizon,
    )

    run_result = assemble_run_result(
        collector=collector,
        config=config,
        initiative_configs=initiative_configs,
        final_world_state=world_state,
        manifest=manifest,
    )
    return run_result, world_state


def run_batch(
    configs: list[SimulationConfiguration],
    policies: list[GovernancePolicy],
) -> list[tuple[RunResult, WorldState]]:
    """Execute a batch of simulation runs sequentially.

    Each configuration is independently seeded and produces an
    independent result. No mutable state is shared across configs.

    Per interfaces.md: sequential first, parallel later.

    Args:
        configs: List of simulation configurations to run.
        policies: Corresponding policy for each configuration.
            Must be the same length as configs.

    Returns:
        List of (RunResult, WorldState) tuples, one per configuration,
        in order.

    Raises:
        ValueError: If configs and policies have different lengths.
    """
    if len(configs) != len(policies):
        raise ValueError(
            f"configs and policies must have the same length, "
            f"got {len(configs)} configs and {len(policies)} policies."
        )

    results: list[tuple[RunResult, WorldState]] = []
    for i, (cfg, pol) in enumerate(zip(configs, policies, strict=True)):
        logger.info(
            "Running batch item %d/%d: seed=%d, policy=%s.",
            i + 1,
            len(configs),
            cfg.world_seed,
            cfg.governance.policy_id,
        )
        results.append(run_single_regime(cfg, pol))

    return results


# ---------------------------------------------------------------------------
# Initialization helpers
# ---------------------------------------------------------------------------


def _resolve_initiatives(
    config: SimulationConfiguration,
) -> tuple[ResolvedInitiativeConfig, ...]:
    """Resolve initiative generator or return explicit initiatives.

    Per interfaces.md: exactly one of initiatives or initiative_generator
    must be provided (validated earlier). If initiative_generator is
    present, resolve it deterministically using world_seed.

    Args:
        config: The simulation configuration.

    Returns:
        Tuple of ResolvedInitiativeConfig in stable ID order.
    """
    if config.initiatives is not None:
        return config.initiatives

    assert config.initiative_generator is not None
    return generate_initiative_pool(
        config.initiative_generator,
        world_seed=config.world_seed,
    )


def _initialize_world_state(
    config: SimulationConfiguration,
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
) -> WorldState:
    """Create the initial WorldState at tick 0.

    All initiatives start UNASSIGNED. All teams start idle.
    Portfolio capability is 1.0 (baseline).

    Args:
        config: Simulation configuration (for team structure).
        initiative_configs: Resolved initiative configs.

    Returns:
        Initial WorldState at tick 0.
    """
    model = config.model

    # Build initiative states — all UNASSIGNED at tick 0.
    initiative_states: list[InitiativeState] = []
    for cfg in initiative_configs:
        # Use initiative-specific initial belief if set, else model default.
        initial_belief = (
            cfg.initial_quality_belief
            if cfg.initial_quality_belief is not None
            else model.default_initial_quality_belief
        )

        # Execution belief: only for bounded-duration initiatives.
        initial_exec_belief: float | None = None
        if cfg.true_duration_ticks is not None:
            initial_exec_belief = cfg.initial_execution_belief

        initiative_states.append(
            InitiativeState(
                initiative_id=cfg.initiative_id,
                lifecycle_state=LifecycleState.UNASSIGNED,
                assigned_team_id=None,
                quality_belief_t=initial_belief,
                execution_belief_t=initial_exec_belief,
                executive_attention_t=0.0,
                staffed_tick_count=0,
                ticks_since_assignment=0,
                age_ticks=0,
                cumulative_value_realized=0.0,
                cumulative_lump_value_realized=0.0,
                cumulative_residual_value_realized=0.0,
                cumulative_labor_invested=0.0,
                cumulative_attention_invested=0.0,
                belief_history=(),
                review_count=0,
                consecutive_reviews_below_tam_ratio=0,
                residual_activated=False,
                residual_activation_tick=None,
                major_win_surfaced=False,
                major_win_tick=None,
                completed_tick=None,
            )
        )

    # Build team states — all idle at tick 0.
    # team_size can be a single int (all same) or a tuple of per-team sizes.
    team_sizes = config.teams.team_size
    team_states: list[TeamState] = []
    for i in range(config.teams.team_count):
        size = team_sizes if isinstance(team_sizes, int) else team_sizes[i]
        team_states.append(
            TeamState(
                team_id=f"team-{i}",
                team_size=size,
                assigned_initiative_id=None,
            )
        )

    # Initialize frontier state for families with dynamic frontiers.
    # Each family with a FrontierSpec gets an initial FamilyFrontierState
    # with n_resolved=0 and full alpha multiplier.
    frontier_state = _initialize_frontier_state(config)

    return WorldState(
        tick=0,
        initiative_states=tuple(
            s for s in sorted(initiative_states, key=lambda s: s.initiative_id)
        ),
        team_states=tuple(s for s in sorted(team_states, key=lambda s: s.team_id)),
        portfolio_capability=1.0,
        frontier_state_by_family=frontier_state,
    )


# ---------------------------------------------------------------------------
# Tick loop
# ---------------------------------------------------------------------------


def _run_tick_loop(
    world_state: WorldState,
    config: SimulationConfiguration,
    policy: GovernancePolicy,
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    rng_pairs: tuple[InitiativeRngPair, ...],
    collector: RunCollector,
) -> tuple[WorldState, tuple[ResolvedInitiativeConfig, ...], tuple[InitiativeRngPair, ...]]:
    """Execute the main tick loop from tick 0 to tick_horizon - 1.

    Complete per-tick cycle (per dynamic_opportunity_frontier.md):
        1. Runner frontier materialization (inter-tick, before tick T)
        2. Engine apply-actions (tick T begins)
        3. Engine step-world (tick T execution)
        4. Runner updates frontier n_resolved for stops and completions
        5. Governance observation and policy decision

    The tick loop may extend initiative_configs and rng_pairs via
    frontier materialization. It returns the final versions along
    with the final WorldState.

    Per core_simulator.md: governance decisions at end-of-tick T take
    effect at start of tick T+1. The tick loop implements this by
    invoking policy.decide() to get actions, then applying them at
    the *start* of the next tick via apply_actions().

    However, the design requires that governance sees end-of-tick
    state (updated beliefs) before deciding. So the actual flow is:
        - Tick T begins with actions from T-1 already applied
        - step_world produces TickResult (updated state and events)
        - Policy sees updated state and decides actions for T+1
        - Those actions are stored and applied at start of T+1

    Args:
        world_state: Initial WorldState at tick 0.
        config: Full simulation configuration.
        policy: Governance policy to invoke each tick.
        initiative_configs: Resolved initiative configs.
        rng_pairs: Per-initiative RNG pairs.
        collector: Mutable RunCollector to accumulate results.

    Returns:
        Tuple of (final WorldState, final initiative_configs, final rng_pairs).
    """
    tick_horizon = config.time.tick_horizon
    governance = config.governance
    workforce = config.teams

    # Config map for label lookups and sigma computation.
    config_map: dict[str, ResolvedInitiativeConfig] = {
        cfg.initiative_id: cfg for cfg in initiative_configs
    }

    # Team size lookup map.
    team_size_map: dict[str, int] = {}
    for team_state in world_state.team_states:
        team_size_map[team_state.team_id] = team_state.team_size

    # --- Frontier infrastructure ---
    # Build type spec and frontier RNG maps for families with dynamic
    # frontiers. These are created once and reused across all ticks.
    type_spec_map, frontier_rngs = _setup_frontier(config)
    next_initiative_index = len(initiative_configs)

    # Track pending actions (from prior tick's governance decision).
    # At tick 0, there are no pending actions — governance hasn't
    # decided anything yet. So the first tick runs step_world on the
    # initial state, then governance decides, then those actions are
    # applied at the start of tick 1.
    pending_actions = None

    for current_tick in range(tick_horizon):
        # ==============================================================
        # Step 1: Runner frontier materialization (inter-tick)
        # ==============================================================
        # Per dynamic_opportunity_frontier.md: before tick T, the runner
        # inspects frontier state and the current unassigned pool. If
        # any family's pool is at or below its replenishment threshold,
        # the runner materializes new initiatives from the frontier.
        if frontier_rngs:
            (
                world_state,
                initiative_configs,
                rng_pairs,
                config_map,
                next_initiative_index,
            ) = _materialize_frontier_initiatives(
                world_state=world_state,
                config=config,
                initiative_configs=initiative_configs,
                rng_pairs=rng_pairs,
                config_map=config_map,
                type_spec_map=type_spec_map,
                frontier_rngs=frontier_rngs,
                next_initiative_index=next_initiative_index,
                current_tick=current_tick,
            )

        # --- Count idle teams at tick start (before any actions) ---
        # Per core_simulator.md: a team-tick is idle when the team has
        # no assigned initiative at the start of that tick.
        idle_team_count = sum(
            1 for team in world_state.team_states if team.assigned_initiative_id is None
        )
        collector.cumulative_idle_team_ticks += idle_team_count

        # ==============================================================
        # Step 2: Apply pending governance actions from prior tick
        # ==============================================================
        stop_events_this_tick: list = []
        if pending_actions is not None:
            # Detect reassignments before applying actions.
            reassignment_events = _detect_reassignments(
                world_state=world_state,
                actions=pending_actions,
                config_map=config_map,
                current_tick=current_tick,
            )
            collector.reassignment_events.extend(reassignment_events)

            world_state, stop_events = apply_actions(
                world_state=world_state,
                actions=pending_actions,
                initiative_configs=initiative_configs,
                governance_archetype=governance.policy_id,
            )
            stop_events_this_tick = list(stop_events)
            collector.stop_events.extend(stop_events)

        # ==============================================================
        # Step 3: Step world (production, belief update, completion)
        # ==============================================================
        # step_world uses replace() to carry forward all WorldState fields,
        # including runner-owned frontier_state_by_family and
        # available_prize_descriptors.
        tick_result: TickResult = step_world(
            world_state=world_state,
            config=config,
            initiative_configs=initiative_configs,
            rng_pairs=rng_pairs,
        )

        world_state = tick_result.world_state

        # ==============================================================
        # Step 4: Update frontier n_resolved for stops and completions
        # ==============================================================
        # After apply_actions (stops) and step_world (completions),
        # increment n_resolved for each newly resolved initiative's
        # family. This updated count affects frontier quality degradation
        # for future materialization draws.
        if frontier_rngs:
            world_state = _update_frontier_resolved(
                world_state=world_state,
                stop_events=stop_events_this_tick,
                completion_events=tick_result.completion_events,
                config_map=config_map,
                type_spec_map=type_spec_map,
            )

        # Track the running maximum of portfolio_capability_t and the
        # tick at which it was first reached, for the run-level summary.
        # Unconditional — not gated on reporting flags.
        if world_state.portfolio_capability > collector.max_portfolio_capability_t:
            collector.max_portfolio_capability_t = world_state.portfolio_capability
            collector.peak_capability_tick = current_tick

        # --- Collect events ---
        collector.completion_events.extend(tick_result.completion_events)
        collector.major_win_events.extend(tick_result.major_win_events)
        # Note: stop_events from step_world are empty (stops come from
        # apply_actions). stop_events from tick_result are () per tick.py.

        # --- Accumulate value ---
        collector.cumulative_lump_value += tick_result.lump_value_realized_this_tick
        collector.cumulative_residual_value += tick_result.residual_value_realized_this_tick

        # --- Collect per-tick records (conditional on reporting config) ---
        if config.reporting.record_per_tick_logs:
            _collect_per_tick_records(
                current_tick=current_tick,
                world_state=world_state,
                config=config,
                config_map=config_map,
                idle_team_count=idle_team_count,
                collector=collector,
            )

        # --- Track ramp labor this tick ---
        # Sum of team_size for each initiative that is active, staffed,
        # and currently ramping.
        _accumulate_ramp_labor(
            world_state=world_state,
            workforce=workforce,
            team_size_map=team_size_map,
            collector=collector,
        )

        # --- Check for pool exhaustion ---
        # With dynamic frontier, pool exhaustion only applies to families
        # without frontier specs. When all families have frontier enabled,
        # pool exhaustion effectively cannot occur.
        if collector.pool_exhaustion_tick is None and idle_team_count > 0:
            has_assignable = any(
                init_state.lifecycle_state == LifecycleState.UNASSIGNED
                for init_state in world_state.initiative_states
            )
            if not has_assignable:
                # Check if any frontier can still produce initiatives.
                # If all frontier-enabled families could still materialize,
                # this is not true pool exhaustion.
                any_frontier_available = any(
                    type_spec_map.get(tag) is not None and type_spec_map[tag].frontier is not None
                    for tag, _ in world_state.frontier_state_by_family
                )
                if not any_frontier_available:
                    collector.pool_exhaustion_tick = current_tick

        # ==============================================================
        # Step 5: Governance observation and policy decision
        # ==============================================================
        # Per core_simulator.md step 7: governance sees end-of-tick
        # state and decides actions for T+1.
        observation = _build_governance_observation(
            world_state=world_state,
            config=config,
            config_map=config_map,
            team_size_map=team_size_map,
        )

        # Invoke policy. Belief histories and team sizes are now surfaced
        # on the observation types (InitiativeObservation.belief_history,
        # TeamObservation.team_size), closing the observation boundary.
        pending_actions = policy.decide(observation, governance)

        # --- Validate ContinueStop coverage ---
        # Per governance.md §Review semantics: every active-staffed
        # initiative must receive exactly one ContinueStop decision.
        active_staffed_ids = {
            init_obs.initiative_id
            for init_obs in observation.initiatives
            if init_obs.lifecycle_state == "active" and init_obs.assigned_team_id is not None
        }
        covered_ids = {cs.initiative_id for cs in pending_actions.continue_stop}
        if active_staffed_ids != covered_ids:
            missing = active_staffed_ids - covered_ids
            extra = covered_ids - active_staffed_ids
            parts = []
            if missing:
                parts.append(f"missing={sorted(missing)}")
            if extra:
                parts.append(f"extra={sorted(extra)}")
            raise ValueError(
                f"ContinueStop coverage mismatch at tick "
                f"{current_tick}: {', '.join(parts)}. "
                f"Per governance.md, every active-staffed initiative "
                f"must receive exactly one ContinueStop decision."
            )

        # --- Validate attention feasibility ---
        # Per governance.md §Budget and feasibility constraints:
        # reject entire allocation if any positive attention violates
        # per-initiative bounds or if total exceeds budget.
        pending_actions = _validate_attention_feasibility(
            pending_actions=pending_actions,
            observation=observation,
            governance=governance,
            current_tick=current_tick,
            collector=collector,
            governance_archetype=governance.policy_id,
        )

    # --- Horizon reached: no additional lifecycle transitions ---
    # Per core_simulator.md and review_and_reporting.md: the horizon is
    # a measurement boundary, not a lifecycle event. Active initiatives
    # remain active.

    return world_state, initiative_configs, rng_pairs


# ---------------------------------------------------------------------------
# Frontier infrastructure
# ---------------------------------------------------------------------------


def _initialize_frontier_state(
    config: SimulationConfiguration,
) -> tuple[tuple[str, FamilyFrontierState], ...]:
    """Create initial frontier state for families with dynamic frontiers.

    Each family whose InitiativeTypeSpec has a FrontierSpec gets an
    initial FamilyFrontierState with n_resolved=0 and full alpha
    multiplier (1.0). Families without a FrontierSpec are omitted.

    Args:
        config: Simulation configuration.

    Returns:
        Tuple of (generation_tag, FamilyFrontierState) pairs, sorted
        by generation_tag for deterministic ordering.
    """
    if config.initiative_generator is None:
        return ()

    entries: list[tuple[str, FamilyFrontierState]] = []
    for type_spec in config.initiative_generator.type_specs:
        if type_spec.frontier is not None:
            entries.append(
                (
                    type_spec.generation_tag,
                    FamilyFrontierState(
                        n_resolved=0,
                        n_frontier_draws=0,
                        effective_alpha_multiplier=1.0,
                    ),
                )
            )

    # Sort by generation_tag for deterministic ordering.
    entries.sort(key=lambda pair: pair[0])
    return tuple(entries)


def _setup_frontier(
    config: SimulationConfiguration,
) -> tuple[dict[str, InitiativeTypeSpec], dict[str, SimulationRng]]:
    """Build type spec map and frontier RNG streams for families with frontiers.

    Called once at the start of the tick loop. Creates persistent frontier
    RNG objects that advance across the run.

    Args:
        config: Simulation configuration.

    Returns:
        Tuple of (type_spec_map, frontier_rngs).
        type_spec_map: Dict from generation_tag to InitiativeTypeSpec.
        frontier_rngs: Dict from generation_tag to frontier SimulationRng.
            Empty if no families have frontier specs.
    """
    type_spec_map: dict[str, InitiativeTypeSpec] = {}
    frontier_rngs: dict[str, SimulationRng] = {}

    if config.initiative_generator is None:
        return type_spec_map, frontier_rngs

    for type_spec in config.initiative_generator.type_specs:
        type_spec_map[type_spec.generation_tag] = type_spec
        if type_spec.frontier is not None:
            frontier_rngs[type_spec.generation_tag] = create_frontier_rng(
                world_seed=config.world_seed,
                family_tag=type_spec.generation_tag,
            )

    return type_spec_map, frontier_rngs


def _make_initial_initiative_state(
    cfg: ResolvedInitiativeConfig,
    config: SimulationConfiguration,
) -> InitiativeState:
    """Create an initial UNASSIGNED InitiativeState for one initiative.

    Reusable helper for both initial pool setup and frontier
    materialization. Produces the same initial state fields as
    _initialize_world_state.

    Args:
        cfg: The resolved initiative config.
        config: Simulation configuration (for model defaults and ramp).

    Returns:
        An InitiativeState in UNASSIGNED lifecycle state.
    """
    model = config.model

    # Use initiative-specific initial belief if set, else model default.
    initial_belief = (
        cfg.initial_quality_belief
        if cfg.initial_quality_belief is not None
        else model.default_initial_quality_belief
    )

    # Execution belief: only for bounded-duration initiatives.
    initial_exec_belief: float | None = None
    if cfg.true_duration_ticks is not None:
        initial_exec_belief = cfg.initial_execution_belief

    return InitiativeState(
        initiative_id=cfg.initiative_id,
        lifecycle_state=LifecycleState.UNASSIGNED,
        assigned_team_id=None,
        quality_belief_t=initial_belief,
        execution_belief_t=initial_exec_belief,
        executive_attention_t=0.0,
        staffed_tick_count=0,
        ticks_since_assignment=0,
        age_ticks=0,
        cumulative_value_realized=0.0,
        cumulative_lump_value_realized=0.0,
        cumulative_residual_value_realized=0.0,
        cumulative_labor_invested=0.0,
        cumulative_attention_invested=0.0,
        belief_history=(),
        review_count=0,
        consecutive_reviews_below_tam_ratio=0,
        residual_activated=False,
        residual_activation_tick=None,
        major_win_surfaced=False,
        major_win_tick=None,
        completed_tick=None,
    )


def _materialize_frontier_initiatives(
    world_state: WorldState,
    config: SimulationConfiguration,
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    rng_pairs: tuple[InitiativeRngPair, ...],
    config_map: dict[str, ResolvedInitiativeConfig],
    type_spec_map: dict[str, InitiativeTypeSpec],
    frontier_rngs: dict[str, SimulationRng],
    next_initiative_index: int,
    current_tick: int,
) -> tuple[
    WorldState,
    tuple[ResolvedInitiativeConfig, ...],
    tuple[InitiativeRngPair, ...],
    dict[str, ResolvedInitiativeConfig],
    int,
]:
    """Materialize new initiatives from the frontier when pools are depleted.

    Per dynamic_opportunity_frontier.md §Complete per-tick cycle: this runs
    before tick T. For each family with a frontier spec, checks if the
    unassigned pool count is at or below the replenishment threshold. If
    so, materializes one new initiative with degraded quality.

    The runner:
    1. Reads frontier state from WorldState.
    2. Counts unassigned initiatives per family.
    3. For depleted families, generates a new initiative via
       pool.generate_frontier_initiative.
    4. Creates new per-initiative RNG substreams.
    5. Creates a new UNASSIGNED InitiativeState.
    6. Updates frontier state (increments n_frontier_draws).

    Args:
        world_state: Current WorldState (pre-tick).
        config: Simulation configuration.
        initiative_configs: Current initiative configs tuple.
        rng_pairs: Current per-initiative RNG pairs tuple.
        config_map: Mutable dict from initiative_id to config.
        type_spec_map: Dict from generation_tag to type spec.
        frontier_rngs: Dict from generation_tag to frontier RNG.
        next_initiative_index: Next sequential initiative index.
        current_tick: Current tick number (for created_tick).

    Returns:
        Tuple of (updated WorldState, initiative_configs, rng_pairs,
        config_map, next_initiative_index).
    """
    frontier_state_dict = world_state.frontier_state_dict

    # Count unassigned initiatives per family (generation_tag).
    unassigned_by_family: dict[str, int] = {}
    for init_state in world_state.initiative_states:
        if init_state.lifecycle_state == LifecycleState.UNASSIGNED:
            cfg = config_map.get(init_state.initiative_id)
            if cfg is not None and cfg.generation_tag is not None:
                tag = cfg.generation_tag
                unassigned_by_family[tag] = unassigned_by_family.get(tag, 0) + 1

    # Check each frontier-enabled family for materialization need.
    new_configs: list[ResolvedInitiativeConfig] = []
    new_rng_pairs: list[InitiativeRngPair] = []
    new_init_states: list[InitiativeState] = []
    updated_frontier_entries: dict[str, FamilyFrontierState] = dict(frontier_state_dict)

    # Mutable copy of available prize descriptors for right-tail
    # prize selection and removal. Sorted by prize_id for deterministic
    # FIFO-like selection (lowest prize_id first).
    updated_available_prizes: list[PrizeDescriptor] = sorted(
        world_state.available_prize_descriptors, key=lambda p: p.prize_id
    )

    for family_tag, frontier_rng in sorted(frontier_rngs.items()):
        type_spec = type_spec_map.get(family_tag)
        if type_spec is None or type_spec.frontier is None:
            continue

        frontier_spec = type_spec.frontier
        current_unassigned = unassigned_by_family.get(family_tag, 0)

        # Materialize if unassigned count is at or below threshold.
        # Per design note: v1 threshold is 0 (materialize when empty).
        if current_unassigned <= frontier_spec.replenishment_threshold:
            family_state = updated_frontier_entries.get(
                family_tag,
                FamilyFrontierState(),
            )

            new_cfg: ResolvedInitiativeConfig | None = None

            # Right-tail families use prize-preserving refresh: select
            # an available prize descriptor and generate a fresh attempt
            # for that persistent market opportunity.
            if (
                type_spec.major_win_event_enabled
                and type_spec.observable_ceiling_distribution is not None
                and updated_available_prizes
            ):
                # Select the available prize with the lowest prize_id
                # (FIFO-like, deterministic, no value judgment embedded).
                selected_prize = updated_available_prizes[0]
                updated_available_prizes = updated_available_prizes[1:]

                new_cfg = generate_prize_refresh_initiative(
                    type_spec=type_spec,
                    frontier_spec=frontier_spec,
                    initiative_index=next_initiative_index,
                    prize_id=selected_prize.prize_id,
                    observable_ceiling=selected_prize.observable_ceiling,
                    attempt_count=selected_prize.attempt_count,
                    rng=frontier_rng,
                    created_tick=current_tick,
                )

                logger.debug(
                    "Prize refresh: family=%s, initiative=%s, "
                    "prize=%s, ceiling=%.2f, attempt=%d, tick=%d.",
                    family_tag,
                    new_cfg.initiative_id,
                    selected_prize.prize_id,
                    selected_prize.observable_ceiling,
                    selected_prize.attempt_count,
                    current_tick,
                )

            else:
                # Standard declining frontier materialization.
                new_cfg = generate_frontier_initiative(
                    type_spec=type_spec,
                    frontier_spec=frontier_spec,
                    initiative_index=next_initiative_index,
                    n_resolved=family_state.n_resolved,
                    rng=frontier_rng,
                    created_tick=current_tick,
                )

                logger.debug(
                    "Frontier materialization: family=%s, initiative=%s, "
                    "n_resolved=%d, n_frontier_draws=%d, alpha_mult=%.3f, tick=%d.",
                    family_tag,
                    new_cfg.initiative_id,
                    family_state.n_resolved,
                    family_state.n_frontier_draws + 1,
                    family_state.effective_alpha_multiplier,
                    current_tick,
                )

            new_configs.append(new_cfg)
            config_map[new_cfg.initiative_id] = new_cfg

            # Create per-initiative RNG pair for the new initiative.
            new_pair = create_initiative_rng_pair(
                world_seed=config.world_seed,
                initiative_index=next_initiative_index,
            )
            new_rng_pairs.append(new_pair)

            # Create initial UNASSIGNED state for the new initiative.
            new_state = _make_initial_initiative_state(new_cfg, config)
            new_init_states.append(new_state)

            # Update frontier state: increment n_frontier_draws.
            new_n_draws = family_state.n_frontier_draws + 1
            updated_frontier_entries[family_tag] = FamilyFrontierState(
                n_resolved=family_state.n_resolved,
                n_frontier_draws=new_n_draws,
                effective_alpha_multiplier=family_state.effective_alpha_multiplier,
            )

            next_initiative_index += 1

    # If nothing was materialized, return unchanged state.
    if not new_configs:
        return (
            world_state,
            initiative_configs,
            rng_pairs,
            config_map,
            next_initiative_index,
        )

    # Extend initiative configs and rng pairs.
    initiative_configs = initiative_configs + tuple(new_configs)
    rng_pairs = rng_pairs + tuple(new_rng_pairs)

    # Extend initiative states in WorldState and update frontier state.
    # Sort all initiative states by initiative_id for deterministic ordering.
    all_init_states = list(world_state.initiative_states) + new_init_states
    all_init_states.sort(key=lambda s: s.initiative_id)

    # Rebuild frontier_state_by_family as sorted tuple-of-tuples.
    new_frontier_state = tuple(sorted(updated_frontier_entries.items(), key=lambda pair: pair[0]))

    world_state = dataclasses.replace(
        world_state,
        initiative_states=tuple(all_init_states),
        frontier_state_by_family=new_frontier_state,
        available_prize_descriptors=tuple(updated_available_prizes),
    )

    return (
        world_state,
        initiative_configs,
        rng_pairs,
        config_map,
        next_initiative_index,
    )


def _update_frontier_resolved(
    world_state: WorldState,
    stop_events: list,
    completion_events: tuple,
    config_map: dict[str, ResolvedInitiativeConfig],
    type_spec_map: dict[str, InitiativeTypeSpec],
) -> WorldState:
    """Update frontier resolved counts and prize lifecycle after stops/completions.

    Called after apply_actions (which produces stops) and step_world
    (which produces completions). Handles two concerns:

    1. For ALL frontier-enabled families: increments n_resolved and
       recomputes effective_alpha_multiplier.

    2. For RIGHT-TAIL prize lifecycle (per dynamic_opportunity_frontier.md §2):
       - Stop → prize descriptor returns to available set (with incremented
         attempt_count) for future re-attempts.
       - Completion → prize is consumed and does NOT return to available.
       - Initial pool right-tail initiatives that stop create NEW prize
         descriptors (they were implicit prizes).

    Args:
        world_state: Current WorldState (post-step).
        stop_events: Stop events from apply_actions this tick.
        completion_events: Completion events from step_world this tick.
        config_map: Dict from initiative_id to config.
        type_spec_map: Dict from generation_tag to type spec.

    Returns:
        Updated WorldState with incremented frontier resolved counts and
        updated available_prize_descriptors.
    """
    # Collect resolved initiative IDs and their families.
    resolved_by_family: dict[str, int] = {}
    for event in stop_events:
        cfg = config_map.get(event.initiative_id)
        if cfg is not None and cfg.generation_tag is not None:
            tag = cfg.generation_tag
            resolved_by_family[tag] = resolved_by_family.get(tag, 0) + 1

    for event in completion_events:
        cfg = config_map.get(event.initiative_id)
        if cfg is not None and cfg.generation_tag is not None:
            tag = cfg.generation_tag
            resolved_by_family[tag] = resolved_by_family.get(tag, 0) + 1

    # --- Prize lifecycle for right-tail stops and completions ---
    # Mutable copy of available prize descriptors.
    available_prizes = list(world_state.available_prize_descriptors)
    prizes_changed = False

    for event in stop_events:
        cfg = config_map.get(event.initiative_id)
        if cfg is None or cfg.generation_tag is None:
            continue

        # Check if this is a right-tail initiative (has observable_ceiling).
        type_spec = type_spec_map.get(cfg.generation_tag)
        if (
            type_spec is None
            or type_spec.frontier is None
            or type_spec.observable_ceiling_distribution is None
            or cfg.observable_ceiling is None
        ):
            continue

        # Right-tail initiative stopped → prize returns to available.
        if cfg.prize_id is not None:
            # This is a re-attempt. Use the attempt_count stored on the
            # config (preserved from when the prize was materialized) and
            # increment it. This avoids the broken lookup in available
            # descriptors (the prize was removed at materialization time).
            available_prizes.append(
                PrizeDescriptor(
                    prize_id=cfg.prize_id,
                    observable_ceiling=cfg.observable_ceiling,
                    attempt_count=cfg.prize_attempt_count + 1,
                )
            )
        else:
            # Initial pool initiative stopped → create new prize descriptor.
            new_prize_id = f"prize-{cfg.initiative_id}"
            available_prizes.append(
                PrizeDescriptor(
                    prize_id=new_prize_id,
                    observable_ceiling=cfg.observable_ceiling,
                    attempt_count=1,
                )
            )

        prizes_changed = True
        logger.debug(
            "Prize available: initiative=%s, prize=%s, ceiling=%.2f.",
            cfg.initiative_id,
            cfg.prize_id or f"prize-{cfg.initiative_id}",
            cfg.observable_ceiling,
        )

    # Right-tail completions: prize is consumed (NOT returned to available).
    # No action needed — the prize was already removed from available when
    # the attempt was materialized. We just log it.
    for event in completion_events:
        cfg = config_map.get(event.initiative_id)
        if cfg is not None and cfg.prize_id is not None:
            logger.debug(
                "Prize consumed: initiative=%s completed, prize=%s.",
                cfg.initiative_id,
                cfg.prize_id,
            )

    # If nothing was resolved and no prizes changed, return unchanged.
    if not resolved_by_family and not prizes_changed:
        return world_state

    # Update frontier state for each family with new resolutions.
    frontier_state_dict = dict(world_state.frontier_state_by_family)
    for family_tag, count in resolved_by_family.items():
        if family_tag not in frontier_state_dict:
            continue  # Family has no frontier state (fixed pool)

        type_spec = type_spec_map.get(family_tag)
        if type_spec is None or type_spec.frontier is None:
            continue

        frontier_spec = type_spec.frontier
        old_state = frontier_state_dict[family_tag]

        new_n_resolved = old_state.n_resolved + count
        new_multiplier = max(
            frontier_spec.frontier_quality_floor,
            1.0 - frontier_spec.frontier_degradation_rate * new_n_resolved,
        )

        frontier_state_dict[family_tag] = FamilyFrontierState(
            n_resolved=new_n_resolved,
            n_frontier_draws=old_state.n_frontier_draws,
            effective_alpha_multiplier=new_multiplier,
        )

    # Rebuild frontier_state_by_family as sorted tuple-of-tuples.
    new_frontier_state = tuple(sorted(frontier_state_dict.items(), key=lambda pair: pair[0]))

    # Sort available prizes by prize_id for deterministic ordering.
    available_prizes.sort(key=lambda p: p.prize_id)

    return dataclasses.replace(
        world_state,
        frontier_state_by_family=new_frontier_state,
        available_prize_descriptors=tuple(available_prizes),
    )


# ---------------------------------------------------------------------------
# Attention feasibility validation
# ---------------------------------------------------------------------------


def _validate_attention_feasibility(
    pending_actions: GovernanceActions,
    observation: GovernanceObservation,
    governance: GovernanceConfig,
    current_tick: int,
    collector: RunCollector,
    governance_archetype: str,
) -> GovernanceActions:
    """Validate attention allocation against budget and per-initiative bounds.

    Per governance.md §Budget and feasibility constraints: if any positive
    attention value violates [attention_min_effective, attention_max_effective]
    or the total exceeds exec_attention_budget, the engine rejects the
    entire allocation and sets all named initiatives to attention_min_effective.

    Args:
        pending_actions: Actions from policy.decide().
        observation: Current governance observation (for bounds).
        governance: Governance config.
        current_tick: Current tick number.
        collector: Run collector for logging violation events.
        governance_archetype: Policy archetype name for event logging.

    Returns:
        The original actions if valid, or corrected actions with
        attention clamped to attention_min_effective on violation.
    """
    attn_actions = pending_actions.set_exec_attention
    if not attn_actions:
        return pending_actions

    attention_min = observation.attention_min_effective
    attention_max = observation.attention_max_effective
    budget = observation.exec_attention_budget

    # Check per-initiative bounds and compute total.
    total_attention = 0.0
    violation_kind: str | None = None

    for attn in attn_actions:
        if attn.attention > 0.0 and (
            attn.attention < attention_min or attn.attention > attention_max
        ):
            violation_kind = "per_initiative_bounds"
            break
        total_attention += attn.attention

    if violation_kind is None and total_attention > budget:
        violation_kind = "budget_exceeded"

    if violation_kind is None:
        # No violation — return actions unchanged.
        return pending_actions

    # Violation detected: reject entire allocation and clamp to min.
    affected_ids = tuple(a.initiative_id for a in attn_actions)
    fallback_actions = tuple(
        SetExecAttentionAction(
            initiative_id=a.initiative_id,
            attention=attention_min,
        )
        for a in attn_actions
    )

    # Emit violation event.
    collector.attention_feasibility_violation_events.append(
        AttentionFeasibilityViolationEvent(
            tick=current_tick,
            policy_id=governance_archetype,
            requested_total=total_attention,
            budget_limit=budget,
            affected_initiative_ids=affected_ids,
            fallback_attention_applied=attention_min,
            violation_kind=violation_kind,
        )
    )

    logger.warning(
        "Attention feasibility violation at tick %d: %s "
        "(requested=%.3f, budget=%.3f). Clamping all to %.3f.",
        current_tick,
        violation_kind,
        total_attention,
        budget,
        attention_min,
    )

    return dataclasses.replace(
        pending_actions,
        set_exec_attention=fallback_actions,
    )


# ---------------------------------------------------------------------------
# Observation construction
# ---------------------------------------------------------------------------


def _build_governance_observation(
    world_state: WorldState,
    config: SimulationConfiguration,
    config_map: dict[str, ResolvedInitiativeConfig],
    team_size_map: dict[str, int],
) -> GovernanceObservation:
    """Construct the policy-visible GovernanceObservation from WorldState.

    Enforces the observation boundary: latent_quality and
    true_duration_ticks never appear in the observation.

    Computes derived fields:
        - effective_tam_patience_window: max(1, ceil(T_tam * ceiling / ref_ceiling))
        - implied_duration_ticks: round(planned / max(c_exec, epsilon_exec))
        - progress_fraction: min(staffed / planned, 1.0)
        - PortfolioSummary from initiative/team state

    Per interfaces.md GovernanceObservation schema.

    Args:
        world_state: Current WorldState (post-step, end-of-tick).
        config: Full simulation configuration.
        config_map: Map of initiative_id to ResolvedInitiativeConfig.
        team_size_map: Map of team_id to team_size.

    Returns:
        GovernanceObservation with all policy-visible state.
    """
    governance = config.governance
    model = config.model

    # Resolve attention bounds.
    # Per interfaces.md: if attention_max is None, canonical interpretation is 1.0.
    attention_min_effective = governance.attention_min
    attention_max_effective = (
        governance.attention_max if governance.attention_max is not None else 1.0
    )

    # --- Build InitiativeObservations ---
    initiative_observations: list[InitiativeObservation] = []
    for init_state in world_state.initiative_states:
        cfg = config_map.get(init_state.initiative_id)
        if cfg is None:
            continue

        # Observation boundary: NO latent_quality, NO true_duration_ticks.

        # effective_tam_patience_window:
        # max(1, ceil(T_tam * observable_ceiling / reference_ceiling))
        effective_tam_pw: int | None = None
        if cfg.observable_ceiling is not None:
            effective_tam_pw = max(
                1,
                math.ceil(
                    governance.base_tam_patience_window
                    * cfg.observable_ceiling
                    / model.reference_ceiling
                ),
            )

        # implied_duration_ticks:
        # round(planned_duration_ticks / max(execution_belief_t, epsilon_exec))
        implied_duration: int | None = None
        if cfg.planned_duration_ticks is not None and init_state.execution_belief_t is not None:
            implied_duration = round(
                cfg.planned_duration_ticks
                / max(init_state.execution_belief_t, MIN_EXECUTION_BELIEF)
            )

        # progress_fraction:
        # min(staffed_tick_count / planned_duration_ticks, 1.0)
        progress_frac: float | None = None
        if cfg.planned_duration_ticks is not None:
            progress_frac = min(init_state.staffed_tick_count / cfg.planned_duration_ticks, 1.0)

        initiative_observations.append(
            InitiativeObservation(
                initiative_id=init_state.initiative_id,
                lifecycle_state=init_state.lifecycle_state.value,
                assigned_team_id=init_state.assigned_team_id,
                quality_belief_t=init_state.quality_belief_t,
                observable_ceiling=cfg.observable_ceiling,
                required_team_size=cfg.required_team_size,
                effective_tam_patience_window=effective_tam_pw,
                execution_belief_t=init_state.execution_belief_t,
                implied_duration_ticks=implied_duration,
                planned_duration_ticks=cfg.planned_duration_ticks,
                progress_fraction=progress_frac,
                review_count=init_state.review_count,
                staffed_tick_count=init_state.staffed_tick_count,
                consecutive_reviews_below_tam_ratio=init_state.consecutive_reviews_below_tam_ratio,
                capability_contribution_scale=cfg.capability_contribution_scale,
                # Belief history surfaced on observation so policies can
                # evaluate stagnation without side-channel arguments.
                belief_history=init_state.belief_history,
                # generation_tag is observable metadata set at pool generation.
                # It is not latent — it comes from InitiativeTypeSpec, which is
                # visible in the environment family definition and the manifest.
                generation_tag=cfg.generation_tag,
            )
        )

    # Stable id order for determinism.
    initiative_observations.sort(key=lambda obs: obs.initiative_id)

    # --- Build TeamObservations ---
    team_observations: list[TeamObservation] = []
    for team_state in world_state.team_states:
        team_observations.append(
            TeamObservation(
                team_id=team_state.team_id,
                assigned_initiative_id=team_state.assigned_initiative_id,
                # available_next_tick: True if currently unassigned.
                available_next_tick=team_state.assigned_initiative_id is None,
                # team_size surfaced on observation so policies can match
                # sizes to initiative requirements without side-channel args.
                team_size=team_size_map.get(team_state.team_id, 1),
            )
        )
    team_observations.sort(key=lambda obs: obs.team_id)

    # --- Compute available_team_count ---
    available_team_count = sum(
        1 for t in world_state.team_states if t.assigned_initiative_id is None
    )

    # --- Compute PortfolioSummary ---
    portfolio_summary = _compute_portfolio_summary(
        initiative_states=world_state.initiative_states,
        team_size_map=team_size_map,
        governance=governance,
    )

    return GovernanceObservation(
        tick=world_state.tick,
        available_team_count=available_team_count,
        exec_attention_budget=governance.exec_attention_budget,
        default_initial_quality_belief=governance.default_initial_quality_belief,
        attention_min_effective=attention_min_effective,
        attention_max_effective=attention_max_effective,
        portfolio_capability_level=world_state.portfolio_capability,
        portfolio_summary=portfolio_summary,
        initiatives=tuple(initiative_observations),
        teams=tuple(team_observations),
    )


def _compute_portfolio_summary(
    initiative_states: tuple[InitiativeState, ...],
    team_size_map: dict[str, int],
    governance: GovernanceConfig,
) -> PortfolioSummary:
    """Compute portfolio-level convenience aggregates.

    Per interfaces.md PortfolioSummary: derived from initiative/team
    state, not an independent source of truth.

    Args:
        initiative_states: Current initiative states.
        team_size_map: Map from team_id to team_size.
        governance: Governance config (for quality threshold).

    Returns:
        PortfolioSummary with active labor and concentration metrics.
    """
    active_labor_total = 0
    active_labor_below_threshold = 0
    max_single_labor = 0

    for init_state in initiative_states:
        # Only count active, staffed initiatives.
        if (
            init_state.lifecycle_state != LifecycleState.ACTIVE
            or init_state.assigned_team_id is None
        ):
            continue

        team_size = team_size_map.get(init_state.assigned_team_id, 1)
        active_labor_total += team_size
        max_single_labor = max(max_single_labor, team_size)

        # Count labor below quality threshold.
        if (
            governance.low_quality_belief_threshold is not None
            and init_state.quality_belief_t < governance.low_quality_belief_threshold
        ):
            active_labor_below_threshold += team_size

    # Compute shares.
    low_quality_share: float | None = None
    max_single_share: float | None = None

    if governance.low_quality_belief_threshold is not None:
        if active_labor_total > 0:
            low_quality_share = active_labor_below_threshold / active_labor_total
        active_labor_below_threshold_result: int | None = active_labor_below_threshold
    else:
        active_labor_below_threshold_result = None

    if active_labor_total > 0:
        max_single_share = max_single_labor / active_labor_total

    return PortfolioSummary(
        active_labor_total=active_labor_total,
        active_labor_below_quality_threshold=active_labor_below_threshold_result,
        low_quality_belief_labor_share=low_quality_share,
        max_single_initiative_labor_share=max_single_share,
    )


# ---------------------------------------------------------------------------
# Per-tick record collection
# ---------------------------------------------------------------------------


def _collect_per_tick_records(
    current_tick: int,
    world_state: WorldState,
    config: SimulationConfiguration,
    config_map: dict[str, ResolvedInitiativeConfig],
    idle_team_count: int,
    collector: RunCollector,
) -> None:
    """Collect PerInitiativeTickRecord and PortfolioTickRecord for this tick.

    Only called when config.reporting.record_per_tick_logs is True.

    Per review_and_reporting.md: records are emitted for active staffed
    initiatives. exec_attention_a_t is the realized attention (after
    engine validation), and latent_quality is for post-hoc analysis only.

    Args:
        current_tick: The current tick number.
        world_state: WorldState AFTER step_world (contains updated beliefs).
        config: Simulation configuration.
        config_map: Initiative config lookup.
        idle_team_count: Number of idle teams at tick start.
        collector: Mutable collector to append records to.
    """
    model = config.model
    workforce = config.teams

    total_attention_allocated = 0.0
    active_count = 0

    for init_state in sorted(world_state.initiative_states, key=lambda s: s.initiative_id):
        # Only emit records for active staffed initiatives.
        if init_state.lifecycle_state != LifecycleState.ACTIVE:
            continue
        if init_state.assigned_team_id is None:
            continue

        active_count += 1
        cfg = config_map.get(init_state.initiative_id)
        if cfg is None:
            continue

        # Realized attention (after engine validation).
        exec_attention = init_state.executive_attention_t
        total_attention_allocated += exec_attention

        # Compute effective sigma for this tick.
        # Import here to avoid pulling learning.py at module level
        # (it's already imported for ramp_multiplier).
        from primordial_soup.learning import (
            attention_noise_modifier,
            effective_signal_st_dev_t,
        )

        g_a = attention_noise_modifier(
            exec_attention,
            attention_noise_threshold=model.attention_noise_threshold,
            low_attention_penalty_slope=model.low_attention_penalty_slope,
            attention_curve_exponent=model.attention_curve_exponent,
            min_attention_noise_modifier=model.min_attention_noise_modifier,
            max_attention_noise_modifier=model.max_attention_noise_modifier,
        )
        effective_signal_st_dev = effective_signal_st_dev_t(
            base_signal_st_dev=cfg.base_signal_st_dev,
            dependency_level=cfg.dependency_level,
            dependency_noise_exponent=model.dependency_noise_exponent,
            attention_noise_modifier_value=g_a,
            portfolio_capability_t=world_state.portfolio_capability,
        )

        # Ramp state.
        # Note: ticks_since_assignment in world_state is the POST-increment
        # value (it was incremented during step_world). The pre-increment
        # value is ticks_since_assignment - 1 (unless it was just assigned
        # this tick, in which case it's 0 and was incremented to 1).
        # For reporting, we use the post-step value to compute whether
        # the initiative was ramping during this tick.
        # Actually, the ramp_multiplier check uses the pre-increment value
        # that was used during the tick's production step. Since step_world
        # increments ticks_since_assignment, we need to use (current - 1)
        # to get the pre-increment value.
        pre_increment_tsa = max(0, init_state.ticks_since_assignment - 1)
        ramp_mult = ramp_multiplier(
            ticks_since_assignment=pre_increment_tsa,
            ramp_period_ticks=workforce.ramp_period,
            ramp_shape=workforce.ramp_multiplier_shape,
        )
        # Per core_simulator.md: is_ramping = (t_elapsed < R - 1)
        is_ramping = pre_increment_tsa < (workforce.ramp_period - 1)

        collector.per_initiative_tick_records.append(
            PerInitiativeTickRecord(
                tick=current_tick,
                initiative_id=init_state.initiative_id,
                lifecycle_state=init_state.lifecycle_state.value,
                quality_belief_t=init_state.quality_belief_t,
                latent_quality=cfg.latent_quality,
                exec_attention_a_t=exec_attention,
                effective_sigma_t=effective_signal_st_dev,
                execution_belief_t=init_state.execution_belief_t,
                is_ramping=is_ramping,
                ramp_multiplier=ramp_mult if is_ramping else None,
            )
        )

    # Portfolio tick record.
    collector.portfolio_tick_records.append(
        PortfolioTickRecord(
            tick=current_tick,
            capability_C_t=world_state.portfolio_capability,
            active_initiative_count=active_count,
            idle_team_count=idle_team_count,
            total_exec_attention_allocated=total_attention_allocated,
        )
    )


def _accumulate_ramp_labor(
    world_state: WorldState,
    workforce: WorkforceConfig,
    team_size_map: dict[str, int],
    collector: RunCollector,
) -> None:
    """Track ramp labor for this tick.

    Per review_and_reporting.md: cumulative_ramp_labor = total team-ticks
    consumed during ramp periods (team_size * 1 for each initiative-tick
    where is_ramping == True).

    Args:
        world_state: Current WorldState (post-step).
        workforce: Workforce config (for ramp period).
        team_size_map: Map from team_id to team_size.
        collector: Mutable collector.
    """
    for init_state in world_state.initiative_states:
        if init_state.lifecycle_state != LifecycleState.ACTIVE:
            continue
        if init_state.assigned_team_id is None:
            continue

        # Pre-increment ticks_since_assignment for ramp check.
        pre_increment_tsa = max(0, init_state.ticks_since_assignment - 1)
        is_ramping = pre_increment_tsa < (workforce.ramp_period - 1)

        if is_ramping:
            team_size = team_size_map.get(init_state.assigned_team_id, 1)
            collector.cumulative_ramp_labor += team_size


# ---------------------------------------------------------------------------
# Reassignment detection
# ---------------------------------------------------------------------------


def _detect_reassignments(
    world_state: WorldState,
    actions: GovernanceActions,
    config_map: dict[str, ResolvedInitiativeConfig],
    current_tick: int,
) -> list[ReassignmentEvent]:
    """Detect team reassignments from the action vector.

    Compares current team assignments against AssignTeam actions to
    detect new assignments. Records the trigger (governance_stop,
    completion, or idle_reassignment) for each reassignment event.

    Per review_and_reporting.md ReassignmentEvent schema.

    Args:
        world_state: WorldState BEFORE actions are applied (pre-tick).
        actions: GovernanceActions about to be applied.
        config_map: Initiative config lookup.
        current_tick: Current tick for event timestamping.

    Returns:
        List of ReassignmentEvent records.
    """
    events: list[ReassignmentEvent] = []

    # Build lookup of current team assignments.
    team_assignment: dict[str, str | None] = {
        team.team_id: team.assigned_initiative_id for team in world_state.team_states
    }

    # Build set of initiatives being stopped this tick.
    stopped_ids: set[str] = set()
    for cs_action in actions.continue_stop:
        if cs_action.decision == StopContinueDecision.STOP:
            stopped_ids.add(cs_action.initiative_id)

    # Build set of initiatives that completed last tick (their teams
    # were released and are now unassigned).
    # We identify completed initiatives by checking if any team's
    # current assignment points to a COMPLETED initiative.
    completed_ids: set[str] = set()
    for init_state in world_state.initiative_states:
        if init_state.lifecycle_state == LifecycleState.COMPLETED:
            completed_ids.add(init_state.initiative_id)

    # Check each AssignTeam action for new assignments.
    for assign_action in actions.assign_team:
        if assign_action.initiative_id is None:
            continue  # Leave idle — not a reassignment to a new initiative.

        team_id = assign_action.team_id
        from_init = team_assignment.get(team_id)
        to_init = assign_action.initiative_id

        # Only record if this is a NEW assignment (different initiative).
        if from_init == to_init:
            continue

        # Determine the trigger.
        if from_init is not None and from_init in stopped_ids:
            triggered_by = ReassignmentTrigger.GOVERNANCE_STOP
        elif from_init is not None and from_init in completed_ids:
            triggered_by = ReassignmentTrigger.COMPLETION
        else:
            # Team was idle or being reassigned for other reasons.
            triggered_by = ReassignmentTrigger.IDLE_REASSIGNMENT

        events.append(
            ReassignmentEvent(
                tick=current_tick,
                team_id=team_id,
                from_initiative_id=from_init,
                to_initiative_id=to_init,
                triggered_by=triggered_by,
            )
        )

    return events
