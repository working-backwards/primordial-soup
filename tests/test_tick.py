"""Tests for tick.py — tick engine (step_world and apply_actions).

Tests verify:
    - apply_actions: stop transitions, team assignment/release, attention,
      lifecycle state changes, deterministic ordering
    - step_world production & observation: signal draws, counter increments
    - Belief updates: quality and execution belief progression
    - Review-state update: review_count, TAM adequacy counter
    - Belief history: ring buffer sizing and trimming
    - Completion detection: staffed_tick_count >= true_duration_ticks
    - Value realization: completion-lump, residual (same-tick activation)
    - Major-win events: emission at completion
    - Capability update: decay + completion gains, clamping
    - Residual value pass: exponential decay, multi-tick persistence
    - Team release on completion: effective at t+1
    - Edge cases: zero pivots, all stopped, empty pool, ramp on first tick
"""

from __future__ import annotations

import math

import pytest

from primordial_soup.actions import (
    AssignTeamAction,
    ContinueStopAction,
    GovernanceActions,
    SetExecAttentionAction,
)
from primordial_soup.noise import InitiativeRngPair, create_initiative_rng_pair
from primordial_soup.state import InitiativeState, TeamState, WorldState
from primordial_soup.tick import (
    _append_belief_history,
    _update_portfolio_capability,
    _update_tam_counter,
    apply_actions,
    step_world,
)
from primordial_soup.types import (
    LifecycleState,
    StopContinueDecision,
    TriggeringRule,
)

# Import shared test factories from conftest.
from tests.conftest import (
    make_initiative,
    make_model_config,
    make_simulation_config,
    make_value_channels,
)

# ---------------------------------------------------------------------------
# Test helpers — factory functions for valid test objects
# ---------------------------------------------------------------------------


def _make_initiative_state(
    *,
    initiative_id: str = "init-1",
    lifecycle_state: LifecycleState = LifecycleState.ACTIVE,
    assigned_team_id: str | None = "team-1",
    quality_belief_t: float = 0.5,
    execution_belief_t: float | None = None,
    executive_attention_t: float = 0.0,
    staffed_tick_count: int = 0,
    ticks_since_assignment: int = 0,
    age_ticks: int = 0,
    cumulative_value_realized: float = 0.0,
    cumulative_lump_value_realized: float = 0.0,
    cumulative_residual_value_realized: float = 0.0,
    cumulative_labor_invested: float = 0.0,
    cumulative_attention_invested: float = 0.0,
    belief_history: tuple[float, ...] = (),
    review_count: int = 0,
    consecutive_reviews_below_tam_ratio: int = 0,
    residual_activated: bool = False,
    residual_activation_tick: int | None = None,
    major_win_surfaced: bool = False,
    major_win_tick: int | None = None,
    completed_tick: int | None = None,
) -> InitiativeState:
    """Build a valid InitiativeState for testing with sensible defaults."""
    return InitiativeState(
        initiative_id=initiative_id,
        lifecycle_state=lifecycle_state,
        assigned_team_id=assigned_team_id,
        quality_belief_t=quality_belief_t,
        execution_belief_t=execution_belief_t,
        executive_attention_t=executive_attention_t,
        staffed_tick_count=staffed_tick_count,
        ticks_since_assignment=ticks_since_assignment,
        age_ticks=age_ticks,
        cumulative_value_realized=cumulative_value_realized,
        cumulative_lump_value_realized=cumulative_lump_value_realized,
        cumulative_residual_value_realized=cumulative_residual_value_realized,
        cumulative_labor_invested=cumulative_labor_invested,
        cumulative_attention_invested=cumulative_attention_invested,
        belief_history=belief_history,
        review_count=review_count,
        consecutive_reviews_below_tam_ratio=consecutive_reviews_below_tam_ratio,
        residual_activated=residual_activated,
        residual_activation_tick=residual_activation_tick,
        major_win_surfaced=major_win_surfaced,
        major_win_tick=major_win_tick,
        completed_tick=completed_tick,
    )


def _make_team_state(
    *,
    team_id: str = "team-1",
    team_size: int = 1,
    assigned_initiative_id: str | None = None,
) -> TeamState:
    """Build a valid TeamState for testing."""
    return TeamState(
        team_id=team_id,
        team_size=team_size,
        assigned_initiative_id=assigned_initiative_id,
    )


def _make_world_state(
    *,
    tick: int = 0,
    initiative_states: tuple[InitiativeState, ...] | None = None,
    team_states: tuple[TeamState, ...] | None = None,
    portfolio_capability: float = 1.0,
) -> WorldState:
    """Build a valid WorldState for testing."""
    if initiative_states is None:
        initiative_states = (_make_initiative_state(),)
    if team_states is None:
        team_states = (_make_team_state(assigned_initiative_id="init-1"),)
    return WorldState(
        tick=tick,
        initiative_states=initiative_states,
        team_states=team_states,
        portfolio_capability=portfolio_capability,
    )


def _empty_actions() -> GovernanceActions:
    """Return an empty GovernanceActions vector (no actions)."""
    return GovernanceActions(
        continue_stop=(),
        assign_team=(),
        set_exec_attention=(),
    )


def _make_rng_pair(
    world_seed: int = 42,
    initiative_index: int = 0,
) -> InitiativeRngPair:
    """Create an InitiativeRngPair for tests."""
    return create_initiative_rng_pair(
        world_seed=world_seed,
        initiative_index=initiative_index,
    )


# ---------------------------------------------------------------------------
# Tests: apply_actions
# ---------------------------------------------------------------------------


class TestApplyActionsStop:
    """Tests for ContinueStop action processing in apply_actions."""

    def test_stop_transitions_initiative_to_stopped(self):
        """A STOP action should transition the initiative to STOPPED."""
        world = _make_world_state()
        configs = (make_initiative(),)
        actions = GovernanceActions(
            continue_stop=(
                ContinueStopAction(
                    initiative_id="init-1",
                    decision=StopContinueDecision.STOP,
                    triggering_rule=TriggeringRule.CONFIDENCE_DECLINE,
                ),
            ),
            assign_team=(),
            set_exec_attention=(),
        )

        new_world, stop_events = apply_actions(world, actions, configs, "balanced")

        init_state = new_world.initiative_states[0]
        assert init_state.lifecycle_state == LifecycleState.STOPPED

    def test_stop_releases_team(self):
        """A STOP action should release the assigned team."""
        world = _make_world_state()
        configs = (make_initiative(),)
        actions = GovernanceActions(
            continue_stop=(
                ContinueStopAction(
                    initiative_id="init-1",
                    decision=StopContinueDecision.STOP,
                    triggering_rule=TriggeringRule.STAGNATION,
                ),
            ),
            assign_team=(),
            set_exec_attention=(),
        )

        new_world, _ = apply_actions(world, actions, configs, "balanced")

        # Team should be unassigned.
        team = new_world.team_states[0]
        assert team.assigned_initiative_id is None
        # Initiative should have no team.
        init_state = new_world.initiative_states[0]
        assert init_state.assigned_team_id is None

    def test_stop_emits_stop_event(self):
        """A STOP action should emit a StopEvent with correct fields."""
        world = _make_world_state()
        configs = (make_initiative(latent_quality=0.7),)
        actions = GovernanceActions(
            continue_stop=(
                ContinueStopAction(
                    initiative_id="init-1",
                    decision=StopContinueDecision.STOP,
                    triggering_rule=TriggeringRule.TAM_ADEQUACY,
                ),
            ),
            assign_team=(),
            set_exec_attention=(),
        )

        _, stop_events = apply_actions(world, actions, configs, "aggressive")

        assert len(stop_events) == 1
        event = stop_events[0]
        assert event.initiative_id == "init-1"
        assert event.tick == 0
        assert event.latent_quality == pytest.approx(0.7)
        assert event.triggering_rule == "tam_adequacy"
        assert event.governance_archetype == "aggressive"

    def test_continue_action_does_not_change_state(self):
        """A CONTINUE action should leave the initiative unchanged."""
        world = _make_world_state()
        configs = (make_initiative(),)
        actions = GovernanceActions(
            continue_stop=(
                ContinueStopAction(
                    initiative_id="init-1",
                    decision=StopContinueDecision.CONTINUE,
                ),
            ),
            assign_team=(),
            set_exec_attention=(),
        )

        new_world, stop_events = apply_actions(world, actions, configs, "balanced")

        assert new_world.initiative_states[0].lifecycle_state == LifecycleState.ACTIVE
        assert len(stop_events) == 0


class TestApplyActionsAssign:
    """Tests for AssignTeam action processing in apply_actions."""

    def test_new_assignment_transitions_to_active(self):
        """Assigning a team to an UNASSIGNED initiative should make it ACTIVE."""
        init_state = _make_initiative_state(
            lifecycle_state=LifecycleState.UNASSIGNED,
            assigned_team_id=None,
        )
        team_state = _make_team_state(assigned_initiative_id=None)
        world = _make_world_state(
            initiative_states=(init_state,),
            team_states=(team_state,),
        )
        configs = (make_initiative(),)
        actions = GovernanceActions(
            continue_stop=(),
            assign_team=(AssignTeamAction(team_id="team-1", initiative_id="init-1"),),
            set_exec_attention=(),
        )

        new_world, _ = apply_actions(world, actions, configs, "balanced")

        init = new_world.initiative_states[0]
        assert init.lifecycle_state == LifecycleState.ACTIVE
        assert init.assigned_team_id == "team-1"
        assert init.ticks_since_assignment == 0

    def test_new_assignment_resets_ticks_since_assignment(self):
        """A new team assignment should reset ticks_since_assignment to 0."""
        # Initiative currently has team-1, assign team-2.
        init_state = _make_initiative_state(
            assigned_team_id="team-1",
            ticks_since_assignment=5,
        )
        team1 = _make_team_state(team_id="team-1", assigned_initiative_id="init-1")
        team2 = _make_team_state(team_id="team-2", assigned_initiative_id=None)
        world = _make_world_state(
            initiative_states=(init_state,),
            team_states=(team1, team2),
        )
        configs = (make_initiative(),)
        actions = GovernanceActions(
            continue_stop=(),
            assign_team=(AssignTeamAction(team_id="team-2", initiative_id="init-1"),),
            set_exec_attention=(),
        )

        new_world, _ = apply_actions(world, actions, configs, "balanced")

        init = new_world.initiative_states[0]
        assert init.assigned_team_id == "team-2"
        assert init.ticks_since_assignment == 0

    def test_same_team_does_not_reset_ramp(self):
        """Re-assigning the same team should not reset ticks_since_assignment."""
        init_state = _make_initiative_state(
            assigned_team_id="team-1",
            ticks_since_assignment=5,
        )
        team1 = _make_team_state(team_id="team-1", assigned_initiative_id="init-1")
        world = _make_world_state(
            initiative_states=(init_state,),
            team_states=(team1,),
        )
        configs = (make_initiative(),)
        actions = GovernanceActions(
            continue_stop=(),
            assign_team=(AssignTeamAction(team_id="team-1", initiative_id="init-1"),),
            set_exec_attention=(),
        )

        new_world, _ = apply_actions(world, actions, configs, "balanced")

        init = new_world.initiative_states[0]
        assert init.ticks_since_assignment == 5

    def test_idle_assignment_releases_team(self):
        """AssignTeam with initiative_id=None should leave the team idle."""
        team1 = _make_team_state(team_id="team-1", assigned_initiative_id="init-1")
        init_state = _make_initiative_state(assigned_team_id="team-1")
        world = _make_world_state(
            initiative_states=(init_state,),
            team_states=(team1,),
        )
        configs = (make_initiative(),)
        actions = GovernanceActions(
            continue_stop=(),
            assign_team=(AssignTeamAction(team_id="team-1", initiative_id=None),),
            set_exec_attention=(),
        )

        new_world, _ = apply_actions(world, actions, configs, "balanced")

        team = new_world.team_states[0]
        assert team.assigned_initiative_id is None


class TestApplyActionsAttention:
    """Tests for SetExecAttention action processing in apply_actions."""

    def test_attention_set_on_initiative(self):
        """SetExecAttention should update the initiative's attention."""
        world = _make_world_state()
        configs = (make_initiative(),)
        actions = GovernanceActions(
            continue_stop=(),
            assign_team=(),
            set_exec_attention=(SetExecAttentionAction(initiative_id="init-1", attention=0.5),),
        )

        new_world, _ = apply_actions(world, actions, configs, "balanced")

        init = new_world.initiative_states[0]
        assert init.executive_attention_t == pytest.approx(0.5)

    def test_attention_resets_to_zero_if_omitted(self):
        """Initiatives not in SetExecAttention should have attention = 0.0."""
        init_state = _make_initiative_state(executive_attention_t=0.8)
        world = _make_world_state(initiative_states=(init_state,))
        configs = (make_initiative(),)
        # No attention actions: initiative should reset to 0.0.
        actions = _empty_actions()

        new_world, _ = apply_actions(world, actions, configs, "balanced")

        init = new_world.initiative_states[0]
        assert init.executive_attention_t == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: step_world — production & observation
# ---------------------------------------------------------------------------


class TestStepWorldProduction:
    """Tests for step_world production & observation (step 3)."""

    def test_staffed_tick_count_increments(self):
        """Staffed active initiative should increment staffed_tick_count."""
        world = _make_world_state(tick=0)
        config = make_simulation_config()
        initiative_configs = config.initiatives
        assert initiative_configs is not None
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, initiative_configs, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.staffed_tick_count == 1

    def test_ticks_since_assignment_increments(self):
        """Staffed active initiative should increment ticks_since_assignment."""
        world = _make_world_state(tick=0)
        config = make_simulation_config()
        initiative_configs = config.initiatives
        assert initiative_configs is not None
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, initiative_configs, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.ticks_since_assignment == 1

    def test_age_ticks_increments(self):
        """All initiatives should increment age_ticks each tick."""
        world = _make_world_state(tick=5)
        config = make_simulation_config()
        initiative_configs = config.initiatives
        assert initiative_configs is not None
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, initiative_configs, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.age_ticks == 1

    def test_labor_invested_increments(self):
        """Staffed initiative should accumulate one unit of labor per tick."""
        world = _make_world_state(tick=0)
        config = make_simulation_config()
        initiative_configs = config.initiatives
        assert initiative_configs is not None
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, initiative_configs, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.cumulative_labor_invested == pytest.approx(1.0)

    def test_attention_invested_accumulates(self):
        """Staffed initiative should accumulate executive attention invested."""
        init_state = _make_initiative_state(executive_attention_t=0.4)
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(_make_team_state(assigned_initiative_id="init-1"),),
        )
        config = make_simulation_config()
        initiative_configs = config.initiatives
        assert initiative_configs is not None
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, initiative_configs, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.cumulative_attention_invested == pytest.approx(0.4)

    def test_unstaffed_initiative_not_processed(self):
        """An active but unstaffed initiative should not increment staffed counters."""
        init_state = _make_initiative_state(
            assigned_team_id=None,
            staffed_tick_count=3,
        )
        team = _make_team_state(assigned_initiative_id=None)
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config()
        initiative_configs = config.initiatives
        assert initiative_configs is not None
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, initiative_configs, rng_pairs)

        init = result.world_state.initiative_states[0]
        # Staffed tick count should NOT increment (not staffed).
        assert init.staffed_tick_count == 3
        # Age should still increment.
        assert init.age_ticks == 1

    def test_stopped_initiative_not_processed(self):
        """A STOPPED initiative should not be processed for production."""
        init_state = _make_initiative_state(
            lifecycle_state=LifecycleState.STOPPED,
            assigned_team_id=None,
        )
        team = _make_team_state(assigned_initiative_id=None)
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config()
        initiative_configs = config.initiatives
        assert initiative_configs is not None
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, initiative_configs, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.staffed_tick_count == 0
        assert init.lifecycle_state == LifecycleState.STOPPED


# ---------------------------------------------------------------------------
# Tests: step_world — belief updates
# ---------------------------------------------------------------------------


class TestStepWorldBeliefUpdate:
    """Tests for belief update step in step_world."""

    def test_quality_belief_updates_toward_latent_quality(self):
        """Over many ticks, quality belief should converge toward latent quality."""
        # Run many ticks with a high learning rate to see convergence.
        init_cfg = make_initiative(latent_quality=0.8, dependency_level=0.0)
        init_state = _make_initiative_state(quality_belief_t=0.5)
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(
            initiatives=(init_cfg,),
            model=make_model_config(learning_rate=0.3),
        )
        rng_pairs = (_make_rng_pair(world_seed=123),)

        # Run 50 ticks.
        current_world = world
        for _ in range(50):
            result = step_world(
                current_world,
                config,
                config.initiatives,
                rng_pairs,
            )
            current_world = result.world_state

        # After 50 ticks, belief should be closer to 0.8 than it started.
        final_belief = current_world.initiative_states[0].quality_belief_t
        assert abs(final_belief - 0.8) < abs(0.5 - 0.8)

    def test_execution_belief_updates_when_duration_set(self):
        """Execution belief should update for bounded-duration initiatives."""
        init_cfg = make_initiative(
            latent_quality=0.6,
            true_duration_ticks=20,
            planned_duration_ticks=20,
        )
        init_state = _make_initiative_state(
            quality_belief_t=0.5,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(world_seed=42),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        # Execution belief should have changed from 1.0 (we don't know
        # the exact direction since the signal is noisy).
        assert init.execution_belief_t is not None
        # It should be a valid belief value in [0, 1].
        assert 0.0 <= init.execution_belief_t <= 1.0

    def test_execution_belief_none_when_no_duration(self):
        """Execution belief should remain None for unbounded initiatives."""
        init_cfg = make_initiative(
            true_duration_ticks=None,
            planned_duration_ticks=None,
        )
        init_state = _make_initiative_state(
            execution_belief_t=None,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.execution_belief_t is None


# ---------------------------------------------------------------------------
# Tests: step_world — review state
# ---------------------------------------------------------------------------


class TestStepWorldReviewState:
    """Tests for review-state update (step 5b) in step_world."""

    def test_review_count_increments_for_staffed_active(self):
        """review_count should increment for a staffed active initiative."""
        world = _make_world_state(tick=0)
        config = make_simulation_config()
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.review_count == 1

    def test_review_count_does_not_increment_when_unstaffed(self):
        """review_count should not increment for an unstaffed initiative."""
        init_state = _make_initiative_state(
            assigned_team_id=None,
            review_count=3,
        )
        team = _make_team_state(assigned_initiative_id=None)
        world = _make_world_state(
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config()
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.review_count == 3

    def test_tam_counter_increments_when_belief_below_threshold(self):
        """consecutive_reviews_below_tam_ratio should increment when c_t < θ_tam_ratio."""
        # Set up with very low latent quality so belief stays low.
        init_cfg = make_initiative(
            latent_quality=0.05,
            observable_ceiling=100.0,
        )
        init_state = _make_initiative_state(
            quality_belief_t=0.1,
            consecutive_reviews_below_tam_ratio=2,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            initiative_states=(init_state,),
            team_states=(team,),
        )
        # tam_threshold_ratio = 0.3 by default in conftest.
        # With latent_quality=0.05, after one tick with learning_rate=0.1,
        # the belief will likely stay below 0.3.
        config = make_simulation_config(
            initiatives=(init_cfg,),
            model=make_model_config(learning_rate=0.01),
        )
        rng_pairs = (_make_rng_pair(world_seed=99),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        # With very low quality and small learning rate, belief should
        # stay below 0.3, so counter should increment.
        assert init.consecutive_reviews_below_tam_ratio >= 3

    def test_tam_counter_resets_when_no_ceiling(self):
        """consecutive_reviews_below_tam_ratio should be 0 when no observable_ceiling."""
        init_cfg = make_initiative(observable_ceiling=None)
        init_state = _make_initiative_state(
            consecutive_reviews_below_tam_ratio=5,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.consecutive_reviews_below_tam_ratio == 0

    def test_tam_counter_resets_for_unstaffed(self):
        """consecutive_reviews_below_tam_ratio should reset when unstaffed."""
        init_state = _make_initiative_state(
            assigned_team_id=None,
            consecutive_reviews_below_tam_ratio=5,
        )
        team = _make_team_state(assigned_initiative_id=None)
        world = _make_world_state(
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config()
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.consecutive_reviews_below_tam_ratio == 0


# ---------------------------------------------------------------------------
# Tests: belief history
# ---------------------------------------------------------------------------


class TestBeliefHistory:
    """Tests for belief history ring buffer management."""

    def test_append_belief_history_adds_entry(self):
        """Appending to belief history should add the new belief."""
        result = _append_belief_history(
            belief_history=(0.5, 0.6),
            new_belief=0.7,
            stagnation_window_staffed_ticks=10,
        )
        assert result == (0.5, 0.6, 0.7)

    def test_append_belief_history_trims_to_window(self):
        """Belief history should be trimmed to stagnation_window_staffed_ticks."""
        history = (0.1, 0.2, 0.3, 0.4, 0.5)
        result = _append_belief_history(
            belief_history=history,
            new_belief=0.6,
            stagnation_window_staffed_ticks=3,
        )
        # Should keep only the 3 most recent: (0.4, 0.5, 0.6)
        assert result == (0.4, 0.5, 0.6)

    def test_append_belief_history_empty_start(self):
        """Starting from empty history should work correctly."""
        result = _append_belief_history(
            belief_history=(),
            new_belief=0.5,
            stagnation_window_staffed_ticks=10,
        )
        assert result == (0.5,)

    def test_belief_history_grows_in_step_world(self):
        """step_world should append to belief_history each staffed tick."""
        world = _make_world_state(tick=0)
        config = make_simulation_config()
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert len(init.belief_history) == 1
        # The entry should be the updated quality belief.
        assert init.belief_history[0] == pytest.approx(init.quality_belief_t)


# ---------------------------------------------------------------------------
# Tests: completion detection
# ---------------------------------------------------------------------------


class TestCompletionDetection:
    """Tests for initiative completion at step 5c."""

    def test_completes_when_staffed_ticks_reach_true_duration(self):
        """Initiative should complete when staffed_tick_count reaches true_duration_ticks."""
        init_cfg = make_initiative(
            true_duration_ticks=3,
            planned_duration_ticks=3,
            value_channels=make_value_channels(lump_enabled=True, lump_value=100.0),
        )
        # staffed_tick_count=2, will become 3 after this tick → completes.
        init_state = _make_initiative_state(
            staffed_tick_count=2,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=5,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.lifecycle_state == LifecycleState.COMPLETED
        assert init.completed_tick == 5

    def test_does_not_complete_before_threshold(self):
        """Initiative should remain active before staffed_tick_count reaches threshold."""
        init_cfg = make_initiative(
            true_duration_ticks=5,
            planned_duration_ticks=5,
        )
        # staffed_tick_count=1, will become 2 (< 5).
        init_state = _make_initiative_state(
            staffed_tick_count=1,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=3,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.lifecycle_state == LifecycleState.ACTIVE
        assert init.completed_tick is None

    def test_completion_event_emitted(self):
        """Completion should emit a CompletionEvent with correct fields."""
        init_cfg = make_initiative(
            latent_quality=0.9,
            true_duration_ticks=1,
            planned_duration_ticks=1,
        )
        init_state = _make_initiative_state(
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=10,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        assert len(result.completion_events) == 1
        event = result.completion_events[0]
        assert event.initiative_id == "init-1"
        assert event.tick == 10
        assert event.latent_quality == pytest.approx(0.9)
        assert event.cumulative_labor_invested == pytest.approx(1.0)

    def test_no_completion_for_unbounded_initiative(self):
        """Initiatives without true_duration_ticks should never complete."""
        init_cfg = make_initiative(true_duration_ticks=None)
        init_state = _make_initiative_state(
            staffed_tick_count=100,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=100,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.lifecycle_state == LifecycleState.ACTIVE


# ---------------------------------------------------------------------------
# Tests: completion-lump value
# ---------------------------------------------------------------------------


class TestCompletionLumpValue:
    """Tests for completion-lump value realization at step 5c."""

    def test_lump_value_realized_on_completion(self):
        """Completion-lump value should be credited at the completion tick."""
        init_cfg = make_initiative(
            true_duration_ticks=1,
            planned_duration_ticks=1,
            value_channels=make_value_channels(lump_enabled=True, lump_value=50.0),
        )
        init_state = _make_initiative_state(
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.cumulative_lump_value_realized == pytest.approx(50.0)
        assert result.lump_value_realized_this_tick == pytest.approx(50.0)

    def test_no_lump_when_disabled(self):
        """No lump value should be realized when the channel is disabled."""
        init_cfg = make_initiative(
            true_duration_ticks=1,
            planned_duration_ticks=1,
            value_channels=make_value_channels(lump_enabled=False),
        )
        init_state = _make_initiative_state(
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.cumulative_lump_value_realized == pytest.approx(0.0)
        assert result.lump_value_realized_this_tick == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: major-win events
# ---------------------------------------------------------------------------


class TestMajorWinEvents:
    """Tests for major-win event emission at completion."""

    def test_major_win_emitted_on_completion(self):
        """A major-win event should be emitted when is_major_win is True."""
        init_cfg = make_initiative(
            latent_quality=0.9,
            observable_ceiling=500.0,
            true_duration_ticks=1,
            planned_duration_ticks=1,
            value_channels=make_value_channels(major_win_enabled=True, is_major_win=True),
        )
        init_state = _make_initiative_state(
            staffed_tick_count=0,
            quality_belief_t=0.7,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=20,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        assert len(result.major_win_events) == 1
        event = result.major_win_events[0]
        assert event.initiative_id == "init-1"
        assert event.tick == 20
        assert event.latent_quality == pytest.approx(0.9)
        assert event.observable_ceiling == pytest.approx(500.0)

        # Initiative state should reflect the major win.
        init = result.world_state.initiative_states[0]
        assert init.major_win_surfaced is True
        assert init.major_win_tick == 20

    def test_no_major_win_when_not_flagged(self):
        """No major-win event should fire when is_major_win is False."""
        init_cfg = make_initiative(
            true_duration_ticks=1,
            planned_duration_ticks=1,
            value_channels=make_value_channels(major_win_enabled=True, is_major_win=False),
        )
        init_state = _make_initiative_state(
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        assert len(result.major_win_events) == 0


# ---------------------------------------------------------------------------
# Tests: residual value
# ---------------------------------------------------------------------------


class TestResidualValue:
    """Tests for residual activation and value realization."""

    def test_residual_activates_on_completion(self):
        """Residual should activate at completion when activation_state='completed'."""
        init_cfg = make_initiative(
            true_duration_ticks=1,
            planned_duration_ticks=1,
            value_channels=make_value_channels(
                residual_enabled=True, residual_rate=10.0, residual_decay=0.1
            ),
        )
        init_state = _make_initiative_state(
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=5,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        init = result.world_state.initiative_states[0]
        assert init.residual_activated is True
        assert init.residual_activation_tick == 5

    def test_residual_fires_same_tick_as_completion(self):
        """Residual value should fire on the same tick as completion (τ=0)."""
        init_cfg = make_initiative(
            true_duration_ticks=1,
            planned_duration_ticks=1,
            value_channels=make_value_channels(
                residual_enabled=True, residual_rate=10.0, residual_decay=0.1
            ),
        )
        init_state = _make_initiative_state(
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=5,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        # At τ_residual = 0: residual_rate * exp(0) = 10.0
        assert result.residual_value_realized_this_tick == pytest.approx(10.0)
        init = result.world_state.initiative_states[0]
        assert init.cumulative_residual_value_realized == pytest.approx(10.0)

    def test_residual_decays_over_ticks(self):
        """Residual value should decay exponentially over subsequent ticks."""
        # Pre-activate residual (already completed in a prior tick).
        init_cfg = make_initiative(
            true_duration_ticks=1,
            planned_duration_ticks=1,
            value_channels=make_value_channels(
                residual_enabled=True, residual_rate=10.0, residual_decay=0.5
            ),
        )
        init_state = _make_initiative_state(
            lifecycle_state=LifecycleState.COMPLETED,
            assigned_team_id=None,
            residual_activated=True,
            residual_activation_tick=0,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id=None)
        world = _make_world_state(
            tick=3,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        # τ_residual = 3 - 0 = 3
        # residual_rate_t = 10.0 * exp(-0.5 * 3) = 10.0 * exp(-1.5)
        expected = 10.0 * math.exp(-1.5)
        assert result.residual_value_realized_this_tick == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Tests: capability update
# ---------------------------------------------------------------------------


class TestCapabilityUpdate:
    """Tests for portfolio capability update at step 5c."""

    def test_capability_gains_from_completion(self):
        """Completing an enabler initiative should increase portfolio capability."""
        init_cfg = make_initiative(
            latent_quality=0.8,
            true_duration_ticks=1,
            planned_duration_ticks=1,
            capability_contribution_scale=2.0,
        )
        init_state = _make_initiative_state(
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
            portfolio_capability=1.0,
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        # ΔC = q * scale = 0.8 * 2.0 = 1.6
        # C_{t+1} = 1.0 + (1.0 - 1.0) * exp(-decay) + 1.6 = 2.6
        # With capability_decay=0.01 from conftest defaults.
        assert result.world_state.portfolio_capability == pytest.approx(2.6)

    def test_capability_decays_without_completions(self):
        """Portfolio capability should decay toward 1.0 each tick without completions."""
        init_state = _make_initiative_state(staffed_tick_count=0)
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
            portfolio_capability=2.0,
        )
        config = make_simulation_config(
            model=make_model_config(capability_decay=0.1),
        )
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        # C_{t+1} = 1.0 + (2.0 - 1.0) * exp(-0.1) + 0 = 1 + exp(-0.1)
        expected = 1.0 + 1.0 * math.exp(-0.1)
        assert result.world_state.portfolio_capability == pytest.approx(expected)

    def test_capability_clamped_to_max(self):
        """Portfolio capability should be clamped to C_max."""
        init_cfg = make_initiative(
            latent_quality=1.0,
            true_duration_ticks=1,
            planned_duration_ticks=1,
            capability_contribution_scale=100.0,
        )
        init_state = _make_initiative_state(
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
            portfolio_capability=1.0,
        )
        config = make_simulation_config(
            initiatives=(init_cfg,),
            model=make_model_config(max_portfolio_capability=3.0),
        )
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        assert result.world_state.portfolio_capability == pytest.approx(3.0)

    def test_capability_floor_at_one(self):
        """Portfolio capability should never fall below 1.0."""
        result = _update_portfolio_capability(
            current_capability=1.0,
            capability_decay=0.5,
            capability_gains=[],
            max_portfolio_capability=3.0,
        )
        assert result == pytest.approx(1.0)

    def test_capability_decay_then_gains_order(self):
        """Decay should be applied first, then new gains added (not decayed)."""
        # C_t = 2.0, decay = 1.0 (heavy decay), gain = 0.5
        # decay: (2.0 - 1.0) * exp(-1.0) = 0.3679
        # C_{t+1} = 1.0 + 0.3679 + 0.5 = 1.8679
        result = _update_portfolio_capability(
            current_capability=2.0,
            capability_decay=1.0,
            capability_gains=[0.5],
            max_portfolio_capability=5.0,
        )
        expected = 1.0 + 1.0 * math.exp(-1.0) + 0.5
        assert result == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Tests: team release on completion
# ---------------------------------------------------------------------------


class TestTeamReleaseOnCompletion:
    """Tests for team release at initiative completion (effective at t+1)."""

    def test_team_released_after_completion(self):
        """Team should be unassigned in the output state after completion."""
        init_cfg = make_initiative(
            true_duration_ticks=1,
            planned_duration_ticks=1,
        )
        init_state = _make_initiative_state(
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        team = _make_team_state(assigned_initiative_id="init-1")
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        config = make_simulation_config(initiatives=(init_cfg,))
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        # Team should be released (effective at start of next tick, which
        # is how we represent it in end-of-tick state).
        team_out = result.world_state.team_states[0]
        assert team_out.assigned_initiative_id is None


# ---------------------------------------------------------------------------
# Tests: tick advancement
# ---------------------------------------------------------------------------


class TestTickAdvancement:
    """Tests for tick counter advancement."""

    def test_tick_counter_advances(self):
        """step_world should advance the tick counter by 1."""
        world = _make_world_state(tick=7)
        config = make_simulation_config()
        rng_pairs = (_make_rng_pair(),)

        result = step_world(world, config, config.initiatives, rng_pairs)

        assert result.world_state.tick == 8


# ---------------------------------------------------------------------------
# Tests: determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Tests for deterministic reproducibility."""

    def test_same_seed_same_result(self):
        """Two runs with the same seed should produce identical results."""
        world = _make_world_state(tick=0)
        config = make_simulation_config()
        rng_pairs_a = (_make_rng_pair(world_seed=42),)
        rng_pairs_b = (_make_rng_pair(world_seed=42),)

        result_a = step_world(world, config, config.initiatives, rng_pairs_a)
        result_b = step_world(world, config, config.initiatives, rng_pairs_b)

        init_a = result_a.world_state.initiative_states[0]
        init_b = result_b.world_state.initiative_states[0]
        assert init_a.quality_belief_t == pytest.approx(init_b.quality_belief_t)

    def test_different_seeds_different_results(self):
        """Two runs with different seeds should (almost certainly) differ."""
        world = _make_world_state(tick=0)
        config = make_simulation_config()
        rng_pairs_a = (_make_rng_pair(world_seed=42),)
        rng_pairs_b = (_make_rng_pair(world_seed=99),)

        result_a = step_world(world, config, config.initiatives, rng_pairs_a)
        result_b = step_world(world, config, config.initiatives, rng_pairs_b)

        init_a = result_a.world_state.initiative_states[0]
        init_b = result_b.world_state.initiative_states[0]
        # With different seeds, beliefs should (almost certainly) differ.
        assert init_a.quality_belief_t != pytest.approx(init_b.quality_belief_t)


# ---------------------------------------------------------------------------
# Tests: stable iteration order
# ---------------------------------------------------------------------------


class TestStableIterationOrder:
    """Tests for deterministic id-ordered iteration."""

    def test_initiative_states_sorted_by_id(self):
        """Output initiative states should be sorted by initiative_id."""
        init_a = _make_initiative_state(initiative_id="init-b")
        init_b = _make_initiative_state(
            initiative_id="init-a",
            assigned_team_id="team-2",
        )
        cfg_a = make_initiative(initiative_id="init-b")
        cfg_b = make_initiative(initiative_id="init-a")
        team1 = _make_team_state(team_id="team-1", assigned_initiative_id="init-b")
        team2 = _make_team_state(team_id="team-2", assigned_initiative_id="init-a")
        world = _make_world_state(
            initiative_states=(init_a, init_b),
            team_states=(team1, team2),
        )
        config = make_simulation_config(initiatives=(cfg_a, cfg_b))
        rng_pairs = (
            _make_rng_pair(initiative_index=0),
            _make_rng_pair(initiative_index=1),
        )

        result = step_world(world, config, (cfg_a, cfg_b), rng_pairs)

        ids = [s.initiative_id for s in result.world_state.initiative_states]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Tests: _update_tam_counter helper
# ---------------------------------------------------------------------------


class TestUpdateTamCounter:
    """Tests for the TAM adequacy counter helper."""

    def test_increments_when_below_threshold(self):
        """Counter should increment when c_t < θ_tam_ratio."""
        result = _update_tam_counter(
            current_count=3,
            quality_belief_t=0.2,
            observable_ceiling=100.0,
            tam_threshold_ratio=0.3,
        )
        assert result == 4

    def test_resets_when_above_threshold(self):
        """Counter should reset to 0 when c_t >= θ_tam_ratio."""
        result = _update_tam_counter(
            current_count=5,
            quality_belief_t=0.5,
            observable_ceiling=100.0,
            tam_threshold_ratio=0.3,
        )
        assert result == 0

    def test_zero_when_no_ceiling(self):
        """Counter should be 0 when observable_ceiling is None."""
        result = _update_tam_counter(
            current_count=10,
            quality_belief_t=0.1,
            observable_ceiling=None,
            tam_threshold_ratio=0.3,
        )
        assert result == 0

    def test_exactly_at_threshold_resets(self):
        """At c_t == θ_tam_ratio, the test passes (not strictly below)."""
        result = _update_tam_counter(
            current_count=3,
            quality_belief_t=0.3,
            observable_ceiling=100.0,
            tam_threshold_ratio=0.3,
        )
        assert result == 0


# ---------------------------------------------------------------------------
# Tests: _update_portfolio_capability helper
# ---------------------------------------------------------------------------


class TestUpdatePortfolioCapability:
    """Tests for the portfolio capability update helper."""

    def test_no_change_at_baseline_no_gains(self):
        """At C_t=1.0 with no gains, capability should stay at 1.0."""
        result = _update_portfolio_capability(
            current_capability=1.0,
            capability_decay=0.1,
            capability_gains=[],
            max_portfolio_capability=5.0,
        )
        assert result == pytest.approx(1.0)

    def test_gains_added(self):
        """Gains should be added to the decayed excess."""
        result = _update_portfolio_capability(
            current_capability=1.0,
            capability_decay=0.0,
            capability_gains=[0.5, 0.3],
            max_portfolio_capability=5.0,
        )
        # 1.0 + 0 + 0.8 = 1.8
        assert result == pytest.approx(1.8)

    def test_clamped_below(self):
        """Capability should not go below 1.0 even with negative excess."""
        # This shouldn't happen in practice, but test the clamp.
        result = _update_portfolio_capability(
            current_capability=1.0,
            capability_decay=100.0,  # extreme decay
            capability_gains=[],
            max_portfolio_capability=5.0,
        )
        assert result >= 1.0


# ---------------------------------------------------------------------------
# Tests: multi-initiative tick
# ---------------------------------------------------------------------------


class TestMultiInitiativeTick:
    """Tests for step_world with multiple initiatives."""

    def test_two_initiatives_processed_independently(self):
        """Each initiative should get its own signal draws and updates."""
        cfg_a = make_initiative(
            initiative_id="init-a",
            latent_quality=0.9,
        )
        cfg_b = make_initiative(
            initiative_id="init-b",
            latent_quality=0.2,
        )
        state_a = _make_initiative_state(
            initiative_id="init-a",
            assigned_team_id="team-1",
            quality_belief_t=0.5,
        )
        state_b = _make_initiative_state(
            initiative_id="init-b",
            assigned_team_id="team-2",
            quality_belief_t=0.5,
        )
        team1 = _make_team_state(team_id="team-1", assigned_initiative_id="init-a")
        team2 = _make_team_state(team_id="team-2", assigned_initiative_id="init-b")
        world = _make_world_state(
            tick=0,
            initiative_states=(state_a, state_b),
            team_states=(team1, team2),
        )
        config = make_simulation_config(initiatives=(cfg_a, cfg_b))
        rng_pairs = (
            _make_rng_pair(world_seed=42, initiative_index=0),
            _make_rng_pair(world_seed=42, initiative_index=1),
        )

        # Run many ticks to see convergence patterns.
        current_world = world
        for _ in range(30):
            result = step_world(current_world, config, (cfg_a, cfg_b), rng_pairs)
            current_world = result.world_state

        # Initiative A (q=0.9) should have higher belief than B (q=0.2).
        states = {s.initiative_id: s for s in current_world.initiative_states}
        assert states["init-a"].quality_belief_t > states["init-b"].quality_belief_t

    def test_multiple_completions_same_tick(self):
        """Multiple initiatives can complete on the same tick."""
        cfg_a = make_initiative(
            initiative_id="init-a",
            true_duration_ticks=1,
            planned_duration_ticks=1,
            value_channels=make_value_channels(lump_enabled=True, lump_value=10.0),
            capability_contribution_scale=1.0,
            latent_quality=0.5,
        )
        cfg_b = make_initiative(
            initiative_id="init-b",
            true_duration_ticks=1,
            planned_duration_ticks=1,
            value_channels=make_value_channels(lump_enabled=True, lump_value=20.0),
            capability_contribution_scale=0.5,
            latent_quality=0.8,
        )
        state_a = _make_initiative_state(
            initiative_id="init-a",
            assigned_team_id="team-1",
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        state_b = _make_initiative_state(
            initiative_id="init-b",
            assigned_team_id="team-2",
            staffed_tick_count=0,
            execution_belief_t=1.0,
        )
        team1 = _make_team_state(team_id="team-1", assigned_initiative_id="init-a")
        team2 = _make_team_state(team_id="team-2", assigned_initiative_id="init-b")
        world = _make_world_state(
            tick=10,
            initiative_states=(state_a, state_b),
            team_states=(team1, team2),
        )
        config = make_simulation_config(initiatives=(cfg_a, cfg_b))
        rng_pairs = (
            _make_rng_pair(world_seed=42, initiative_index=0),
            _make_rng_pair(world_seed=42, initiative_index=1),
        )

        result = step_world(world, config, (cfg_a, cfg_b), rng_pairs)

        # Both should complete.
        assert len(result.completion_events) == 2
        # Total lump = 10 + 20 = 30
        assert result.lump_value_realized_this_tick == pytest.approx(30.0)
        # Capability gains: 0.5 * 1.0 + 0.8 * 0.5 = 0.5 + 0.4 = 0.9
        # C_{t+1} = 1.0 + (1.0 - 1.0) * exp(-0.01) + 0.9 = 1.9
        assert result.world_state.portfolio_capability == pytest.approx(1.9)


# ---------------------------------------------------------------------------
# Tests: staffing intensity effect on learning
# ---------------------------------------------------------------------------


class TestStaffingIntensityMultiplierFormula:
    """Unit tests for the staffing intensity multiplier formula properties.

    The staffing multiplier is:
        staffing_multiplier = 1.0 + staffing_response_scale
                                  * (1.0 - required_team_size / assigned_team_size)

    These tests verify the formula's algebraic properties directly
    without running step_world, using computed expected values.
    """

    def test_at_threshold_multiplier_is_exactly_one(self):
        """When assigned_team_size == required_team_size, multiplier is 1.0.

        This is the baseline case: no surplus staffing, no acceleration.
        """
        scale = 2.0
        required = 5
        assigned = 5
        multiplier = 1.0 + scale * (1.0 - required / assigned)
        assert multiplier == pytest.approx(1.0)

    def test_zero_scale_always_one_regardless_of_team_size(self):
        """When staffing_response_scale == 0.0, multiplier is 1.0 for all team sizes.

        This is the backward compatibility guarantee: existing configs with
        the default scale of 0.0 produce identical behavior regardless of
        how large the assigned team is.
        """
        scale = 0.0
        required = 2
        for assigned in [2, 4, 10, 100, 1000]:
            multiplier = 1.0 + scale * (1.0 - required / assigned)
            assert multiplier == pytest.approx(
                1.0
            ), f"Expected 1.0 for assigned={assigned} with scale=0.0, got {multiplier}"

    def test_moderately_oversized_team_above_baseline(self):
        """A team moderately above threshold produces multiplier > 1.0."""
        scale = 1.5
        required = 2
        assigned = 4  # double the threshold
        multiplier = 1.0 + scale * (1.0 - required / assigned)
        # 1.0 + 1.5 * (1 - 2/4) = 1.0 + 1.5 * 0.5 = 1.75
        assert multiplier == pytest.approx(1.75)
        assert multiplier > 1.0

    def test_saturation_bounded_by_one_plus_scale(self):
        """The multiplier is bounded above by 1.0 + staffing_response_scale.

        As assigned_team_size → ∞, (1 - required / assigned) → 1.0,
        so the multiplier approaches 1.0 + scale from below and never
        exceeds it.
        """
        scale = 2.0
        required = 2

        # Very large teams approach the bound.
        multiplier_100 = 1.0 + scale * (1.0 - required / 100)
        multiplier_1000 = 1.0 + scale * (1.0 - required / 1000)
        multiplier_10000 = 1.0 + scale * (1.0 - required / 10000)

        bound = 1.0 + scale  # = 3.0

        # All below the bound.
        assert multiplier_100 < bound
        assert multiplier_1000 < bound
        assert multiplier_10000 < bound

        # Increasingly close to the bound.
        assert multiplier_10000 > multiplier_1000 > multiplier_100

        # Very large team is very close to the bound.
        assert multiplier_10000 == pytest.approx(bound, abs=0.001)

    def test_diminishing_marginal_returns(self):
        """Marginal gain from additional staffing decreases as team grows.

        This is the core saturation property: doubling a small team
        produces a larger improvement than doubling a large team.
        """
        scale = 2.0
        required = 2

        def mult(assigned: int) -> float:
            return 1.0 + scale * (1.0 - required / assigned)

        # Marginal gains for successive doublings.
        gain_2_to_4 = mult(4) - mult(2)  # threshold → 2x
        gain_4_to_8 = mult(8) - mult(4)  # 2x → 4x
        gain_8_to_16 = mult(16) - mult(8)  # 4x → 8x
        gain_16_to_32 = mult(32) - mult(16)  # 8x → 16x

        # Each successive doubling produces strictly less improvement.
        assert gain_2_to_4 > gain_4_to_8 > gain_8_to_16 > gain_16_to_32

        # All marginal gains are positive (the curve is monotonically
        # increasing, just sublinearly).
        assert gain_2_to_4 > 0
        assert gain_16_to_32 > 0

    def test_exact_formula_values(self):
        """Verify exact multiplier values for specific team sizes.

        These are regression values for the canonical formula:
            multiplier = 1.0 + scale * (1.0 - required / assigned)
        """
        scale = 1.0
        required = 2

        # At threshold: 1.0 + 1.0 * (1 - 2/2) = 1.0
        assert 1.0 + scale * (1.0 - required / 2) == pytest.approx(1.0)
        # 2x threshold: 1.0 + 1.0 * (1 - 2/4) = 1.5
        assert 1.0 + scale * (1.0 - required / 4) == pytest.approx(1.5)
        # 5x threshold: 1.0 + 1.0 * (1 - 2/10) = 1.8
        assert 1.0 + scale * (1.0 - required / 10) == pytest.approx(1.8)
        # 50x threshold: 1.0 + 1.0 * (1 - 2/100) = 1.98
        assert 1.0 + scale * (1.0 - required / 100) == pytest.approx(1.98)


class TestStaffingIntensityStepWorld:
    """Integration tests for staffing intensity through step_world.

    These tests run step_world to verify that the staffing multiplier is
    correctly applied to the learning-rate term in the belief update,
    using the same RNG seed so signal draws are identical across runs.
    """

    def _run_one_tick(
        self,
        team_size: int,
        staffing_response_scale: float,
        required_team_size: int = 2,
        world_seed: int = 42,
    ) -> float:
        """Run one tick of step_world and return the post-tick quality belief.

        Creates a minimal world with one active initiative assigned to one
        team of the given size. Uses a fixed seed so signal draws are
        identical across calls with different team_size or scale values.

        Args:
            team_size: Size of the assigned team.
            staffing_response_scale: The initiative's staffing response scale.
            required_team_size: Minimum team size for the initiative.
            world_seed: RNG seed for deterministic signal draws.

        Returns:
            The post-tick quality_belief_t for the initiative.
        """
        cfg = make_initiative(
            initiative_id="init-0",
            latent_quality=0.7,
            dependency_level=0.0,  # L(d) = 1.0 for clarity
            base_signal_st_dev=0.1,
            staffing_response_scale=staffing_response_scale,
        )
        # Override required_team_size since make_initiative defaults to 1.
        from dataclasses import replace as dc_replace

        cfg = dc_replace(cfg, required_team_size=required_team_size)

        init_state = _make_initiative_state(
            initiative_id="init-0",
            assigned_team_id="team-0",
            quality_belief_t=0.5,
            # Skip ramp for clarity: set ticks_since_assignment past ramp.
            ticks_since_assignment=10,
            staffed_tick_count=10,
        )
        team = _make_team_state(
            team_id="team-0",
            team_size=team_size,
            assigned_initiative_id="init-0",
        )
        world = _make_world_state(
            tick=0,
            initiative_states=(init_state,),
            team_states=(team,),
        )
        sim_config = make_simulation_config(initiatives=(cfg,))
        rng_pairs = (_make_rng_pair(world_seed=world_seed, initiative_index=0),)

        result = step_world(world, sim_config, (cfg,), rng_pairs)
        return result.world_state.initiative_states[0].quality_belief_t

    def test_zero_scale_identical_beliefs_regardless_of_team_size(self):
        """With scale=0.0, beliefs are identical for any team size.

        This is the backward compatibility proof: the staffing multiplier
        is exactly 1.0 when the scale is 0.0, so team size has no effect
        on learning. Existing configurations behave identically.
        """
        belief_small = self._run_one_tick(team_size=2, staffing_response_scale=0.0)
        belief_large = self._run_one_tick(team_size=50, staffing_response_scale=0.0)

        assert belief_small == pytest.approx(belief_large)

    def test_larger_team_learns_faster_with_positive_scale(self):
        """A larger team produces more learning per tick than a threshold team.

        With staffing_response_scale > 0, the larger team's effective
        learning rate is higher, so the belief moves further from the
        initial value toward latent quality.
        """
        initial_belief = 0.5
        belief_threshold = self._run_one_tick(
            team_size=2, staffing_response_scale=1.0, required_team_size=2
        )
        belief_large = self._run_one_tick(
            team_size=10, staffing_response_scale=1.0, required_team_size=2
        )

        # Both should have moved from 0.5 (since latent_quality=0.7 and
        # signals are centered there). The large team should have moved more.
        change_threshold = abs(belief_threshold - initial_belief)
        change_large = abs(belief_large - initial_belief)

        assert change_large > change_threshold

    def test_saturation_through_step_world(self):
        """Verify diminishing returns through step_world: doubling a large
        team produces less additional learning than doubling a small team.

        This proves the saturation shape end-to-end through the engine.
        """
        initial_belief = 0.5

        # Run four team sizes: threshold (2), moderate (4), large (10), huge (100).
        beliefs = {}
        for team_size in [2, 4, 10, 100]:
            beliefs[team_size] = self._run_one_tick(
                team_size=team_size,
                staffing_response_scale=2.0,
                required_team_size=2,
            )

        # All beliefs should differ (team size matters when scale > 0).
        changes = {ts: abs(beliefs[ts] - initial_belief) for ts in beliefs}

        # Larger teams learn more.
        assert changes[4] > changes[2]
        assert changes[10] > changes[4]
        assert changes[100] > changes[10]

        # Diminishing marginal returns: each additional doubling adds less.
        marginal_2_to_4 = changes[4] - changes[2]
        marginal_4_to_10 = changes[10] - changes[4]
        marginal_10_to_100 = changes[100] - changes[10]

        assert marginal_2_to_4 > marginal_4_to_10
        assert marginal_4_to_10 > marginal_10_to_100

    def test_staffing_multiplier_does_not_affect_execution_belief(self):
        """Staffing intensity affects learning rate only, not execution belief.

        Per the design: in v1, the multiplier applies to the strategic
        quality belief update only. Execution belief should be identical
        regardless of team size and staffing_response_scale.
        """
        cfg_base = make_initiative(
            initiative_id="init-0",
            latent_quality=0.7,
            dependency_level=0.0,
            base_signal_st_dev=0.1,
            staffing_response_scale=2.0,
        )
        from dataclasses import replace as dc_replace

        cfg_small = dc_replace(
            cfg_base,
            required_team_size=2,
            true_duration_ticks=50,
            planned_duration_ticks=50,
            initial_execution_belief=1.0,
        )
        cfg_large = dc_replace(
            cfg_base,
            required_team_size=2,
            true_duration_ticks=50,
            planned_duration_ticks=50,
            initial_execution_belief=1.0,
        )

        def run_exec_belief(team_size: int, cfg) -> float:
            init_state = _make_initiative_state(
                initiative_id="init-0",
                assigned_team_id="team-0",
                quality_belief_t=0.5,
                execution_belief_t=1.0,
                ticks_since_assignment=10,
                staffed_tick_count=10,
            )
            team = _make_team_state(
                team_id="team-0",
                team_size=team_size,
                assigned_initiative_id="init-0",
            )
            world = _make_world_state(
                tick=0,
                initiative_states=(init_state,),
                team_states=(team,),
            )
            sim_config = make_simulation_config(initiatives=(cfg,))
            rng_pairs = (_make_rng_pair(world_seed=42, initiative_index=0),)
            result = step_world(world, sim_config, (cfg,), rng_pairs)
            return result.world_state.initiative_states[0].execution_belief_t

        exec_belief_small = run_exec_belief(2, cfg_small)
        exec_belief_large = run_exec_belief(100, cfg_large)

        # Execution beliefs should be identical — staffing intensity
        # does not affect execution belief updates.
        assert exec_belief_small == pytest.approx(exec_belief_large)
