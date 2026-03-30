"""Tick engine — pure state-transition functions for the simulation.

This module implements the core simulation loop as two pure functions:

    step_world:    Advance the simulation by one tick. Executes the full
                   canonical tick sequence from core_simulator.md steps 1–7:
                   apply actions → production & observation → belief update →
                   review-state update → completion detection & capability
                   update → residual value pass → record outputs.

    apply_actions: Apply a GovernanceActions vector to a WorldState,
                   producing a new WorldState with updated initiative and
                   team states. Handles ContinueStop (stop transitions),
                   AssignTeam (team assignment / release), and
                   SetExecAttention (attention allocation).

Both functions are pure: same inputs produce same outputs, no side
effects, no random calls. All stochasticity is pre-drawn from
per-initiative RNG streams and passed in as data.

Key design references:
    - docs/design/core_simulator.md (full tick ordering, value formulas)
    - docs/design/initiative_model.md (lifecycle transitions, mutable state)
    - docs/design/interfaces.md (observation boundary, GovernanceObservation)
    - docs/study/naming_conventions.md (canonical name mapping)

Compact symbol → descriptive name mapping for this module:
    c_t         → quality_belief_t
    c_exec_t    → execution_belief_t
    q           → latent_quality
    q_exec      → latent_execution_fidelity
    σ_eff       → effective_signal_st_dev_t
    C_t         → portfolio_capability_t
    W_stag      → stagnation_window_staffed_ticks
    η           → learning_rate
    η_exec      → execution_learning_rate
    R           → ramp_period_ticks
    τ_residual  → ticks_since_residual_activation
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from primordial_soup.events import CompletionEvent, MajorWinEvent, StopEvent
from primordial_soup.learning import (
    attention_noise_modifier,
    draw_execution_signal,
    draw_quality_signal,
    effective_signal_st_dev_t,
    learning_efficiency,
    ramp_multiplier,
    update_execution_belief,
    update_quality_belief,
)
from primordial_soup.types import LifecycleState, StopContinueDecision

if TYPE_CHECKING:
    from primordial_soup.actions import GovernanceActions
    from primordial_soup.config import ResolvedInitiativeConfig, SimulationConfiguration
    from primordial_soup.noise import InitiativeRngPair
    from primordial_soup.state import InitiativeState, TeamState, WorldState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container for step_world
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TickResult:
    """Output of a single tick's execution.

    Contains the new world state and all events emitted during the tick.
    The engine produces one TickResult per tick; the runner collects them
    for reporting and analysis.
    """

    world_state: WorldState
    completion_events: tuple[CompletionEvent, ...]
    major_win_events: tuple[MajorWinEvent, ...]
    stop_events: tuple[StopEvent, ...]

    # Channel-separated value realized this tick.
    lump_value_realized_this_tick: float
    residual_value_realized_this_tick: float


# ---------------------------------------------------------------------------
# apply_actions — apply governance actions to world state
# ---------------------------------------------------------------------------


def apply_actions(
    world_state: WorldState,
    actions: GovernanceActions,
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    governance_archetype: str,
) -> tuple[WorldState, tuple[StopEvent, ...]]:
    """Apply a GovernanceActions vector to a WorldState.

    Governance actions decided at end-of-tick T are applied at the start
    of tick T+1. This function executes them in deterministic order per
    governance.md:
        1. ContinueStop actions (stop transitions, team release)
        2. AssignTeam actions (new assignments, ticks_since_assignment reset)
        3. SetExecAttention actions (attention updates)

    Initiatives not mentioned in SetExecAttention get attention = 0.0
    (no persistence). Per governance.md, attention does not persist
    across ticks unless explicitly re-assigned.

    Args:
        world_state: Current WorldState to modify.
        actions: GovernanceActions vector from the policy.
        initiative_configs: Resolved initiative configs, id-indexed.
        governance_archetype: Policy identifier for stop event recording.

    Returns:
        A tuple of (new_world_state, stop_events).
    """
    # Build lookup maps for efficient access during action application.
    # Per CLAUDE.md: stable id-ordered iteration.
    initiative_state_map: dict[str, InitiativeState] = {
        state.initiative_id: state for state in world_state.initiative_states
    }
    team_state_map: dict[str, TeamState] = {
        state.team_id: state for state in world_state.team_states
    }
    config_map: dict[str, ResolvedInitiativeConfig] = {
        cfg.initiative_id: cfg for cfg in initiative_configs
    }

    stop_events: list[StopEvent] = []

    # --- Step 1: ContinueStop actions ---
    # Process in id order for determinism.
    sorted_cs_actions = sorted(actions.continue_stop, key=lambda a: a.initiative_id)
    for cs_action in sorted_cs_actions:
        if cs_action.decision == StopContinueDecision.STOP:
            init_state = initiative_state_map[cs_action.initiative_id]
            cfg = config_map[cs_action.initiative_id]

            # Per governance.md: triggering_rule is required on STOP
            # actions. Omitting it is a protocol violation.
            if cs_action.triggering_rule is None:
                raise ValueError(
                    f"STOP action for initiative "
                    f"'{cs_action.initiative_id}' at tick "
                    f"{world_state.tick} has triggering_rule=None. "
                    f"Per governance.md, triggering_rule is required "
                    f"on all STOP actions."
                )

            # Record stop event before transitioning.
            stop_events.append(
                StopEvent(
                    tick=world_state.tick,
                    initiative_id=cs_action.initiative_id,
                    quality_belief_t=init_state.quality_belief_t,
                    execution_belief_t=init_state.execution_belief_t,
                    latent_quality=cfg.latent_quality,
                    triggering_rule=cs_action.triggering_rule.value,
                    cumulative_labor_invested=init_state.cumulative_labor_invested,
                    staffed_ticks=init_state.staffed_tick_count,
                    governance_archetype=governance_archetype,
                )
            )

            # Transition initiative to STOPPED state.
            initiative_state_map[cs_action.initiative_id] = replace(
                init_state,
                lifecycle_state=LifecycleState.STOPPED,
            )

            # Release the team (if assigned). Team becomes available
            # this tick since the stop action is applied at start-of-tick.
            if init_state.assigned_team_id is not None:
                team = team_state_map[init_state.assigned_team_id]
                team_state_map[init_state.assigned_team_id] = replace(
                    team, assigned_initiative_id=None
                )
                # Clear initiative's team reference.
                initiative_state_map[cs_action.initiative_id] = replace(
                    initiative_state_map[cs_action.initiative_id],
                    assigned_team_id=None,
                )

    # --- Step 2: AssignTeam actions ---
    # Process in the order provided (first-come-first-served per governance.md).
    for assign_action in actions.assign_team:
        team = team_state_map[assign_action.team_id]

        if assign_action.initiative_id is None:
            # Leave the team idle (unassign if currently assigned).
            if team.assigned_initiative_id is not None:
                old_init = initiative_state_map[team.assigned_initiative_id]
                initiative_state_map[team.assigned_initiative_id] = replace(
                    old_init, assigned_team_id=None
                )
            team_state_map[assign_action.team_id] = replace(team, assigned_initiative_id=None)
            continue

        # Assign team to initiative.
        target_init = initiative_state_map[assign_action.initiative_id]

        # If team was previously assigned elsewhere, clear old assignment.
        if (
            team.assigned_initiative_id is not None
            and team.assigned_initiative_id != assign_action.initiative_id
        ):
            old_init = initiative_state_map[team.assigned_initiative_id]
            initiative_state_map[team.assigned_initiative_id] = replace(
                old_init, assigned_team_id=None
            )

        # Determine if this is a NEW assignment (triggers ramp reset).
        # A new assignment is when the initiative's current team differs
        # from the one being assigned.
        is_new_assignment = target_init.assigned_team_id != assign_action.team_id

        # Update team state.
        team_state_map[assign_action.team_id] = replace(
            team, assigned_initiative_id=assign_action.initiative_id
        )

        # Update initiative state.
        if is_new_assignment:
            # Per core_simulator.md step 2: new assignment resets
            # ticks_since_assignment to 0. Lifecycle transitions to ACTIVE
            # if currently UNASSIGNED.
            new_lifecycle = target_init.lifecycle_state
            if new_lifecycle == LifecycleState.UNASSIGNED:
                new_lifecycle = LifecycleState.ACTIVE

            initiative_state_map[assign_action.initiative_id] = replace(
                target_init,
                assigned_team_id=assign_action.team_id,
                lifecycle_state=new_lifecycle,
                ticks_since_assignment=0,
            )
        else:
            # Same team, no ramp reset needed. Just ensure references match.
            initiative_state_map[assign_action.initiative_id] = replace(
                target_init,
                assigned_team_id=assign_action.team_id,
            )

    # --- Step 3: SetExecAttention actions ---
    # First, reset all initiative attention to 0.0 (no persistence).
    # Per governance.md: omission from action vector means attention = 0.0.
    for init_id in initiative_state_map:
        init_state = initiative_state_map[init_id]
        if init_state.executive_attention_t != 0.0:
            initiative_state_map[init_id] = replace(init_state, executive_attention_t=0.0)

    # Then apply explicit attention settings.
    for attn_action in actions.set_exec_attention:
        init_state = initiative_state_map[attn_action.initiative_id]
        initiative_state_map[attn_action.initiative_id] = replace(
            init_state, executive_attention_t=attn_action.attention
        )

    # Rebuild tuples in stable id order per CLAUDE.md determinism rules.
    new_initiative_states = tuple(
        initiative_state_map[k] for k in sorted(initiative_state_map.keys())
    )
    new_team_states = tuple(team_state_map[k] for k in sorted(team_state_map.keys()))

    new_world_state = replace(
        world_state,
        initiative_states=new_initiative_states,
        team_states=new_team_states,
    )

    return new_world_state, tuple(stop_events)


# ---------------------------------------------------------------------------
# step_world — advance the simulation by one tick
# ---------------------------------------------------------------------------


def step_world(
    world_state: WorldState,
    config: SimulationConfiguration,
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    rng_pairs: tuple[InitiativeRngPair, ...],
) -> TickResult:
    """Advance the simulation by one tick.

    Implements the canonical tick sequence from core_simulator.md:

        1. (Actions already applied by caller before this function)
        2. (New assignments already applied — ticks_since_assignment = 0)
        3. Production & observation: signal draws, counter increments
        4. (Value realization deferred to end-of-tick)
        5. Belief update, review-state update, completion detection,
           capability update
        6. End-of-tick residual value pass
        7. Record outputs and advance tick counter

    This function assumes that apply_actions has already been called for
    this tick's start-of-tick actions. It handles steps 3–7.

    All stochasticity comes from the rng_pairs (pre-initialized per-initiative
    CRN streams). The function is pure given the same RNG states.

    Args:
        world_state: Current WorldState (with actions already applied).
        config: Full simulation configuration (read-only).
        initiative_configs: Resolved initiative configs, index-aligned
            with rng_pairs.
        rng_pairs: Per-initiative RNG pairs, index-aligned with
            initiative_configs.

    Returns:
        A TickResult containing the new world state and all events
        emitted during this tick.
    """
    current_tick = world_state.tick
    model = config.model
    governance = config.governance
    workforce = config.teams

    # Build lookup maps for efficient access.
    config_map: dict[str, ResolvedInitiativeConfig] = {
        cfg.initiative_id: cfg for cfg in initiative_configs
    }
    rng_map: dict[str, InitiativeRngPair] = {
        cfg.initiative_id: rng_pairs[i] for i, cfg in enumerate(initiative_configs)
    }
    # Team size lookup for staffing intensity multiplier computation.
    # team_size is constant for the duration of a run (no hiring/firing
    # in canonical scope), so this map is stable across ticks.
    team_size_map: dict[str, int] = {ts.team_id: ts.team_size for ts in world_state.team_states}

    # Working copies of state (will be progressively updated).
    initiative_state_map: dict[str, InitiativeState] = {
        s.initiative_id: s for s in world_state.initiative_states
    }

    # Track events emitted this tick.
    completion_events: list[CompletionEvent] = []
    major_win_events: list[MajorWinEvent] = []
    lump_value_this_tick: float = 0.0
    residual_value_this_tick: float = 0.0

    # Track capability gains from completions this tick.
    # Per core_simulator.md step 5c: aggregate after all completions.
    capability_gains: list[float] = []

    # Track team releases from completion (effective at start of t+1).
    # We record them but apply the release at the end so the completing
    # initiative's team is still marked during this tick's processing.
    teams_to_release: list[str] = []

    # --- Steps 3-5: Process each staffed active initiative ---
    # Iterate in stable id order per CLAUDE.md determinism rules.
    for init_id in sorted(initiative_state_map.keys()):
        init_state = initiative_state_map[init_id]
        cfg = config_map[init_id]

        # Only process staffed active initiatives for production & observation.
        if init_state.lifecycle_state != LifecycleState.ACTIVE:
            # Non-active initiatives: increment age, reset consecutive
            # reviews counter (not reviewed this tick).
            # Per core_simulator.md: for initiatives not reviewed on a tick,
            # consecutive_reviews_below_tam_ratio resets to zero.
            initiative_state_map[init_id] = replace(
                init_state,
                age_ticks=init_state.age_ticks + 1,
                consecutive_reviews_below_tam_ratio=0,
            )
            continue

        if init_state.assigned_team_id is None:
            # Active but unstaffed: not reviewed, reset TAM counter.
            # Per core_simulator.md: unstaffed initiatives reset counter.
            initiative_state_map[init_id] = replace(
                init_state,
                age_ticks=init_state.age_ticks + 1,
                consecutive_reviews_below_tam_ratio=0,
            )
            continue

        # --- This initiative is active and staffed ---

        rng_pair = rng_map[init_id]

        # Read pre-increment values for ramp computation.
        # Per core_simulator.md step 2/3: ramp multiplier uses the
        # pre-increment ticks_since_assignment value.
        ticks_since_assignment_pre = init_state.ticks_since_assignment

        # --- Step 3: Production & observation ---

        # Compute attention noise modifier g(a).
        g_a = attention_noise_modifier(
            init_state.executive_attention_t,
            attention_noise_threshold=model.attention_noise_threshold,
            low_attention_penalty_slope=model.low_attention_penalty_slope,
            attention_curve_exponent=model.attention_curve_exponent,
            min_attention_noise_modifier=model.min_attention_noise_modifier,
            max_attention_noise_modifier=model.max_attention_noise_modifier,
        )

        # Compute effective signal st_dev σ_eff.
        effective_signal_st_dev = effective_signal_st_dev_t(
            base_signal_st_dev=cfg.base_signal_st_dev,
            dependency_level=cfg.dependency_level,
            dependency_noise_exponent=model.dependency_noise_exponent,
            attention_noise_modifier_value=g_a,
            portfolio_capability_t=world_state.portfolio_capability,
        )

        # Draw strategic quality signal y_t.
        # y_t ~ Normal(q, σ_eff^2)
        quality_signal = draw_quality_signal(
            latent_quality=cfg.latent_quality,
            effective_signal_st_dev=effective_signal_st_dev,
            rng=rng_pair.quality_signal_rng,
        )

        # Draw execution signal z_t (only for bounded-duration initiatives).
        execution_signal: float | None = None
        if cfg.true_duration_ticks is not None and cfg.planned_duration_ticks is not None:
            # q_exec = min(1.0, planned_duration_ticks / true_duration_ticks)
            latent_execution_fidelity = min(
                1.0, cfg.planned_duration_ticks / cfg.true_duration_ticks
            )
            execution_signal = draw_execution_signal(
                latent_execution_fidelity=latent_execution_fidelity,
                execution_signal_st_dev=model.execution_signal_st_dev,
                rng=rng_pair.exec_signal_rng,
            )

        # Increment staffed tick counters (post-production).
        # Per core_simulator.md step 3: increment staffed_tick_count and
        # ticks_since_assignment AFTER ramp multiplier has been read.
        new_staffed_tick_count = init_state.staffed_tick_count + 1
        new_ticks_since_assignment = ticks_since_assignment_pre + 1

        # Update progress fraction (for bounded-duration initiatives).
        # Per core_simulator.md step 3:
        # progress_fraction = min(staffed_tick_count / planned_duration_ticks, 1.0)
        # Uses post-increment staffed_tick_count and planned (not true) duration.

        # Accumulate labor and attention invested this tick.
        # Per state_definition_and_markov_property.md: cumulative_labor_invested
        # is measured in team-size-ticks, not staffed-tick-count.
        assigned_team_size = team_size_map.get(init_state.assigned_team_id, 1)
        new_cumulative_labor = init_state.cumulative_labor_invested + assigned_team_size
        new_cumulative_attention = (
            init_state.cumulative_attention_invested + init_state.executive_attention_t
        )

        # --- Step 5: Belief update ---

        # Compute ramp multiplier using pre-increment ticks_since_assignment.
        ramp_mult = ramp_multiplier(
            ticks_since_assignment=ticks_since_assignment_pre,
            ramp_period_ticks=workforce.ramp_period,
            ramp_shape=workforce.ramp_multiplier_shape,
        )

        # Compute learning efficiency L(d).
        learn_eff = learning_efficiency(
            dependency_level=cfg.dependency_level,
            dependency_learning_scale=model.dependency_learning_scale,
        )

        # Compute staffing intensity multiplier.
        #
        # When the assigned team is larger than the initiative's minimum
        # staffing threshold (required_team_size), additional staffing
        # accelerates learning with diminishing returns. The formula:
        #
        #   staffing_multiplier = 1.0 + staffing_response_scale
        #                             * (1.0 - required_team_size / assigned_team_size)
        #
        # Properties:
        #   - assigned == required  → multiplier = 1.0 (baseline)
        #   - assigned > required   → multiplier > 1.0, saturating toward
        #                             1.0 + staffing_response_scale
        #   - staffing_response_scale == 0.0 → multiplier = 1.0 always
        #     (full backward compatibility)
        #
        # This multiplier is applied to the learning rate only, not to
        # execution progress. Per opportunity_staffing_intensity_design.md.
        staffing_multiplier = 1.0
        if cfg.staffing_response_scale != 0.0 and init_state.assigned_team_id is not None:
            assigned_team_size = team_size_map.get(init_state.assigned_team_id, 1)
            if assigned_team_size > 0 and cfg.required_team_size > 0:
                staffing_multiplier = 1.0 + cfg.staffing_response_scale * (
                    1.0 - cfg.required_team_size / assigned_team_size
                )

        # Compute the effective learning rate incorporating staffing intensity.
        # When staffing_response_scale == 0.0, effective_learning_rate == model.learning_rate.
        effective_learning_rate = model.learning_rate * staffing_multiplier

        # Update strategic quality belief.
        # c_{t+1} = clamp(c_t + η_eff * ramp * L(d) * (y_t - c_t), 0, 1)
        # where η_eff = η * staffing_multiplier
        new_quality_belief = update_quality_belief(
            quality_belief_t=init_state.quality_belief_t,
            quality_signal=quality_signal,
            learning_rate=effective_learning_rate,
            ramp_multiplier_value=ramp_mult,
            learning_efficiency_value=learn_eff,
        )

        # Update execution belief (only for bounded-duration initiatives).
        new_execution_belief = init_state.execution_belief_t
        if execution_signal is not None and init_state.execution_belief_t is not None:
            # c_exec_{t+1} = clamp(c_exec_t + η_exec * (z_t - c_exec_t), 0, 1)
            new_execution_belief = update_execution_belief(
                execution_belief_t=init_state.execution_belief_t,
                execution_signal=execution_signal,
                execution_learning_rate=model.execution_learning_rate,
            )

        # --- Step 5b: Review-state update ---
        # Per core_simulator.md step 5b: this initiative is active and staffed,
        # so it is reviewed on this tick.
        new_review_count = init_state.review_count + 1

        # Evaluate TAM adequacy test using end-of-tick quality belief.
        # E[v_prize] = c_t * observable_ceiling
        # If E[v_prize] < θ_tam_ratio * observable_ceiling, increment counter.
        # Otherwise reset to 0.
        new_consecutive_below_tam = _update_tam_counter(
            current_count=init_state.consecutive_reviews_below_tam_ratio,
            quality_belief_t=new_quality_belief,
            observable_ceiling=cfg.observable_ceiling,
            tam_threshold_ratio=governance.tam_threshold_ratio,
        )

        # --- Update belief history (ring buffer for stagnation detection) ---
        # Per core_simulator.md: append end-of-tick quality belief to
        # belief_history after the belief update step. Trim to
        # stagnation_window_staffed_ticks entries.
        new_belief_history = _append_belief_history(
            belief_history=init_state.belief_history,
            new_belief=new_quality_belief,
            stagnation_window_staffed_ticks=governance.stagnation_window_staffed_ticks,
        )

        # Apply all state updates for this initiative (pre-completion).
        initiative_state_map[init_id] = replace(
            init_state,
            quality_belief_t=new_quality_belief,
            execution_belief_t=new_execution_belief,
            staffed_tick_count=new_staffed_tick_count,
            ticks_since_assignment=new_ticks_since_assignment,
            age_ticks=init_state.age_ticks + 1,
            cumulative_labor_invested=new_cumulative_labor,
            cumulative_attention_invested=new_cumulative_attention,
            review_count=new_review_count,
            consecutive_reviews_below_tam_ratio=new_consecutive_below_tam,
            belief_history=new_belief_history,
        )

        # --- Step 5c: Completion detection ---
        # For bounded initiatives: complete when staffed_tick_count >= true_duration_ticks.
        # Uses POST-increment staffed_tick_count.
        if (
            cfg.true_duration_ticks is not None
            and new_staffed_tick_count >= cfg.true_duration_ticks
        ):
            updated_state = initiative_state_map[init_id]

            # Record completion event.
            completion_events.append(
                CompletionEvent(
                    initiative_id=init_id,
                    tick=current_tick,
                    latent_quality=cfg.latent_quality,
                    cumulative_labor_invested=updated_state.cumulative_labor_invested,
                )
            )

            # Realize completion-lump value.
            lump_value = 0.0
            if cfg.value_channels.completion_lump.enabled:
                # realized_value is guaranteed non-None by validation.
                assert cfg.value_channels.completion_lump.realized_value is not None
                lump_value = cfg.value_channels.completion_lump.realized_value
                lump_value_this_tick += lump_value

            # Check for major-win event.
            if (
                cfg.value_channels.major_win_event.enabled
                and cfg.value_channels.major_win_event.is_major_win
            ):
                major_win_events.append(
                    MajorWinEvent(
                        initiative_id=init_id,
                        tick=current_tick,
                        latent_quality=cfg.latent_quality,
                        observable_ceiling=cfg.observable_ceiling,
                        quality_belief_at_completion=new_quality_belief,
                        execution_belief_at_completion=updated_state.execution_belief_t,
                        cumulative_labor_invested=updated_state.cumulative_labor_invested,
                        cumulative_attention_invested=updated_state.cumulative_attention_invested,
                        staffed_tick_count=updated_state.staffed_tick_count,
                        observed_history_snapshot=updated_state.belief_history,
                    )
                )

            # Check for residual activation at completion.
            new_residual_activated = updated_state.residual_activated
            new_residual_activation_tick = updated_state.residual_activation_tick
            if (
                cfg.value_channels.residual.enabled
                and cfg.value_channels.residual.activation_state == "completed"
            ):
                new_residual_activated = True
                new_residual_activation_tick = current_tick

            # Capability contribution from this completion.
            # ΔC_i = q_i * capability_contribution_scale_i
            if cfg.capability_contribution_scale > 0:
                capability_gain = cfg.latent_quality * cfg.capability_contribution_scale
                capability_gains.append(capability_gain)

            # Record team to release at end (effective at start of t+1).
            # Per core_simulator.md step 5c: team release effective at t+1.
            if updated_state.assigned_team_id is not None:
                teams_to_release.append(updated_state.assigned_team_id)

            # Transition to COMPLETED state.
            initiative_state_map[init_id] = replace(
                updated_state,
                lifecycle_state=LifecycleState.COMPLETED,
                completed_tick=current_tick,
                cumulative_lump_value_realized=(
                    updated_state.cumulative_lump_value_realized + lump_value
                ),
                cumulative_value_realized=(updated_state.cumulative_value_realized + lump_value),
                residual_activated=new_residual_activated,
                residual_activation_tick=new_residual_activation_tick,
                major_win_surfaced=(
                    updated_state.major_win_surfaced
                    or (
                        cfg.value_channels.major_win_event.enabled
                        and cfg.value_channels.major_win_event.is_major_win
                    )
                ),
                major_win_tick=(
                    current_tick
                    if (
                        cfg.value_channels.major_win_event.enabled
                        and cfg.value_channels.major_win_event.is_major_win
                    )
                    else updated_state.major_win_tick
                ),
            )

    # --- Step 5c (continued): Capability update ---
    # Per core_simulator.md: after all completion transitions, update
    # portfolio capability.
    # C_{t+1} = clamp(1.0 + (C_t - 1.0) * exp(-capability_decay) + ΔC, 1.0, C_max)
    new_portfolio_capability = _update_portfolio_capability(
        current_capability=world_state.portfolio_capability,
        capability_decay=model.capability_decay,
        capability_gains=capability_gains,
        max_portfolio_capability=model.max_portfolio_capability,
    )

    # --- Step 6: End-of-tick residual value pass ---
    # Per core_simulator.md step 6: for every initiative with
    # residual_activated == True, realize residual value.
    # Residual fires on the same tick as completion (τ_residual = 0).
    for init_id in sorted(initiative_state_map.keys()):
        init_state = initiative_state_map[init_id]
        if not init_state.residual_activated:
            continue

        cfg = config_map[init_id]
        assert init_state.residual_activation_tick is not None

        # τ_residual(t) = t - residual_activation_tick
        ticks_since_activation = current_tick - init_state.residual_activation_tick

        # residual_rate_t = residual_rate * exp(-residual_decay * τ_residual)
        residual_rate_t = cfg.value_channels.residual.residual_rate * math.exp(
            -cfg.value_channels.residual.residual_decay * ticks_since_activation
        )

        # v_residual_realized_t = max(residual_rate_t, 0)
        residual_value = max(residual_rate_t, 0.0)
        residual_value_this_tick += residual_value

        # Update initiative's cumulative residual tracking.
        initiative_state_map[init_id] = replace(
            init_state,
            cumulative_residual_value_realized=(
                init_state.cumulative_residual_value_realized + residual_value
            ),
            cumulative_value_realized=(init_state.cumulative_value_realized + residual_value),
        )

    # --- Team release from completion (effective at start of t+1) ---
    # Per core_simulator.md step 5c: the team release is recorded but the
    # team remains assigned for the rest of this tick. We mark it now so
    # the next tick's apply_actions sees it. However, per the design doc,
    # "set team.assigned_initiative_id = None, effective at start of t+1".
    # Since we're producing the end-of-tick state here, we apply the
    # release so it's visible at the start of the next tick.
    team_state_map: dict[str, TeamState] = {s.team_id: s for s in world_state.team_states}
    for team_id in teams_to_release:
        team = team_state_map[team_id]
        team_state_map[team_id] = replace(team, assigned_initiative_id=None)

    # --- Step 7: Record outputs, advance tick ---
    # Build the new world state with the advanced tick counter.
    new_initiative_states = tuple(
        initiative_state_map[k] for k in sorted(initiative_state_map.keys())
    )
    new_team_states = tuple(team_state_map[k] for k in sorted(team_state_map.keys()))

    # Use replace() to carry forward all existing fields (including
    # runner-owned frontier_state_by_family and available_prize_descriptors)
    # rather than constructing a fresh WorldState that drops them.
    # Per issue #12: step_world should not silently discard state it
    # does not own.
    new_world_state = replace(
        world_state,
        tick=current_tick + 1,
        initiative_states=new_initiative_states,
        team_states=new_team_states,
        portfolio_capability=new_portfolio_capability,
    )

    return TickResult(
        world_state=new_world_state,
        completion_events=tuple(completion_events),
        major_win_events=tuple(major_win_events),
        stop_events=(),  # Stop events come from apply_actions, not step_world.
        lump_value_realized_this_tick=lump_value_this_tick,
        residual_value_realized_this_tick=residual_value_this_tick,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _update_tam_counter(
    current_count: int,
    quality_belief_t: float,
    observable_ceiling: float | None,
    tam_threshold_ratio: float,
) -> int:
    """Evaluate the bounded-prize adequacy test for one reviewed initiative.

    Per core_simulator.md step 5b:
        E[v_prize] = c_t * observable_ceiling
        If E[v_prize] < θ_tam_ratio * observable_ceiling, increment
        consecutive_reviews_below_tam_ratio by 1.
        Otherwise, reset to 0.

    Since observable_ceiling cancels out in the comparison:
        If c_t < θ_tam_ratio, increment; else reset.

    For initiatives without observable_ceiling, the TAM test does not
    apply and the counter stays at 0.

    Args:
        current_count: Current consecutive_reviews_below_tam_ratio value.
        quality_belief_t: End-of-tick quality belief (c_t).
        observable_ceiling: Initiative's observable ceiling (None if absent).
        tam_threshold_ratio: TAM threshold ratio (θ_tam_ratio).

    Returns:
        The updated consecutive_reviews_below_tam_ratio value.
    """
    if observable_ceiling is None:
        # No bounded-prize channel: TAM adequacy test does not apply.
        return 0

    # E[v_prize] = c_t * observable_ceiling
    # Threshold: θ_tam_ratio * observable_ceiling
    # Since observable_ceiling > 0 (validated), this simplifies to c_t < θ_tam_ratio.
    if quality_belief_t < tam_threshold_ratio:
        # Below threshold: increment consecutive streak.
        return current_count + 1
    else:
        # Above threshold: reset streak to 0.
        return 0


def _append_belief_history(
    belief_history: tuple[float, ...],
    new_belief: float,
    stagnation_window_staffed_ticks: int,
) -> tuple[float, ...]:
    """Append a belief value to the history ring buffer.

    Per core_simulator.md: the engine maintains a ring buffer of
    quality beliefs with maxlen = stagnation_window_staffed_ticks.
    Appends the current end-of-tick quality belief and trims to
    the configured window size.

    Uses tuple (not deque) since InitiativeState is frozen.
    Per decisions.md issue 4.

    Args:
        belief_history: Current belief history tuple.
        new_belief: End-of-tick quality belief to append.
        stagnation_window_staffed_ticks: Maximum entries to retain (W_stag).

    Returns:
        Updated belief history tuple, trimmed to at most
        stagnation_window_staffed_ticks entries.
    """
    # Append and trim from the left (oldest entries discarded first).
    extended = belief_history + (new_belief,)
    if len(extended) > stagnation_window_staffed_ticks:
        # Keep only the most recent W_stag entries.
        extended = extended[-stagnation_window_staffed_ticks:]
    return extended


def _update_portfolio_capability(
    current_capability: float,
    capability_decay: float,
    capability_gains: list[float],
    max_portfolio_capability: float,
) -> float:
    """Update portfolio capability after all completions on this tick.

    Per core_simulator.md step 5c:

        C_{t+1} = clamp(
            1.0 + (C_t - 1.0) * exp(-capability_decay) + ΔC_completion_t,
            1.0,
            C_max
        )

    Decay applies to existing excess capability first, then new gains
    are added without being immediately decayed. This makes new gains
    fully available when they first take effect at t+1.

    Args:
        current_capability: Current portfolio capability C_t (>= 1.0).
        capability_decay: Per-tick exponential decay rate (>= 0).
        capability_gains: List of ΔC_i from completions this tick.
        max_portfolio_capability: Upper bound C_max (>= 1.0).

    Returns:
        Updated portfolio capability, clamped to [1.0, C_max].
    """
    # Decay the existing excess capability above baseline.
    # excess_{t+1, pre-completion} = (C_t - 1.0) * exp(-capability_decay)
    decayed_excess = (current_capability - 1.0) * math.exp(-capability_decay)

    # Add completion-time gains.
    total_gains = sum(capability_gains)

    # C_{t+1} = 1.0 + decayed_excess + ΔC_completion_t
    new_capability = 1.0 + decayed_excess + total_gains

    # Clamp to [1.0, C_max].
    return max(1.0, min(max_portfolio_capability, new_capability))
