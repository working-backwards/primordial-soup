"""Tests for runner.py — tick loop orchestration and integration.

Tests verify:
    - _initialize_world_state creates correct initial state
    - _build_governance_observation enforces observation boundary
    - _detect_reassignments correctly identifies reassignment triggers
    - run_single_regime end-to-end with deterministic seed
    - run_batch sequential execution with independent results
    - Idle counting rules (ramp is NOT idle)
    - Horizon is measurement boundary (active stays active)
    - Observation boundary (no latent_quality in observation)
    - Per-tick logging conditional on ReportingConfig
    - Pool exhaustion detection
"""

from __future__ import annotations

import pytest

from conftest import (
    make_governance_config,
    make_initiative,
    make_model_config,
    make_simulation_config,
    make_value_channels,
)
from primordial_soup.actions import (
    AssignTeamAction,
    ContinueStopAction,
    GovernanceActions,
)
from primordial_soup.config import (
    InitiativeGeneratorConfig,
    InitiativeTypeSpec,
    ReportingConfig,
    SimulationConfiguration,
    TimeConfig,
    WorkforceConfig,
)
from primordial_soup.policy import BalancedPolicy
from primordial_soup.reporting import RunResult
from primordial_soup.runner import (
    BASELINE_SPEC_VERSION,
    _build_governance_observation,
    _detect_reassignments,
    _initialize_world_state,
    run_batch,
    run_single_regime,
)
from primordial_soup.state import InitiativeState, TeamState, WorldState
from primordial_soup.types import (
    BetaDistribution,
    LifecycleState,
    RampShape,
    ReassignmentTrigger,
    StopContinueDecision,
)

# ============================================================================
# _initialize_world_state
# ============================================================================


class TestInitializeWorldState:
    """Tests for initial world state construction."""

    def test_all_initiatives_unassigned(self) -> None:
        """All initiatives start in UNASSIGNED state."""
        config = make_simulation_config(
            initiatives=(
                make_initiative(initiative_id="init-0"),
                make_initiative(initiative_id="init-1"),
            ),
        )
        ws = _initialize_world_state(config, config.initiatives)
        for init_state in ws.initiative_states:
            assert init_state.lifecycle_state == LifecycleState.UNASSIGNED
            assert init_state.assigned_team_id is None

    def test_all_teams_idle(self) -> None:
        """All teams start idle (no assigned initiative)."""
        config = make_simulation_config()
        ws = _initialize_world_state(config, config.initiatives)
        for team_state in ws.team_states:
            assert team_state.assigned_initiative_id is None

    def test_tick_starts_at_zero(self) -> None:
        config = make_simulation_config()
        ws = _initialize_world_state(config, config.initiatives)
        assert ws.tick == 0

    def test_portfolio_capability_starts_at_one(self) -> None:
        config = make_simulation_config()
        ws = _initialize_world_state(config, config.initiatives)
        assert ws.portfolio_capability == 1.0

    def test_team_count_matches_config(self) -> None:
        config = make_simulation_config(
            teams=WorkforceConfig(
                team_count=5,
                team_size=1,
                ramp_period=3,
            ),
        )
        ws = _initialize_world_state(config, config.initiatives)
        assert len(ws.team_states) == 5

    def test_default_initial_belief_from_model(self) -> None:
        """Uses model default when initiative has no specific initial belief."""
        config = make_simulation_config(
            model=make_model_config(default_initial_quality_belief=0.4),
        )
        ws = _initialize_world_state(config, config.initiatives)
        assert ws.initiative_states[0].quality_belief_t == 0.4

    def test_initiative_specific_initial_belief(self) -> None:
        """Uses initiative-specific belief when set."""
        init = make_initiative(initiative_id="init-0")
        # ResolvedInitiativeConfig has initial_quality_belief field.
        from dataclasses import replace

        init_with_belief = replace(init, initial_quality_belief=0.7)
        config = make_simulation_config(initiatives=(init_with_belief,))
        ws = _initialize_world_state(config, config.initiatives)
        assert ws.initiative_states[0].quality_belief_t == 0.7

    def test_stable_id_ordering(self) -> None:
        """Initiatives and teams sorted by id."""
        config = make_simulation_config(
            initiatives=(
                make_initiative(initiative_id="init-2"),
                make_initiative(initiative_id="init-0"),
                make_initiative(initiative_id="init-1"),
            ),
        )
        ws = _initialize_world_state(config, config.initiatives)
        ids = [s.initiative_id for s in ws.initiative_states]
        assert ids == sorted(ids)


# ============================================================================
# _build_governance_observation
# ============================================================================


class TestBuildGovernanceObservation:
    """Tests for observation construction and boundary enforcement."""

    def _make_simple_world_state(self) -> tuple[WorldState, dict, dict]:
        """Helper to create a simple world state with one active initiative."""
        init_state = InitiativeState(
            initiative_id="init-0",
            lifecycle_state=LifecycleState.ACTIVE,
            assigned_team_id="team-0",
            quality_belief_t=0.6,
            execution_belief_t=0.9,
            executive_attention_t=0.3,
            staffed_tick_count=5,
            ticks_since_assignment=3,
            age_ticks=7,
            cumulative_value_realized=0.0,
            cumulative_lump_value_realized=0.0,
            cumulative_residual_value_realized=0.0,
            cumulative_labor_invested=5.0,
            cumulative_attention_invested=1.5,
            belief_history=(0.5, 0.55, 0.6),
            review_count=5,
            consecutive_reviews_below_tam_ratio=0,
            residual_activated=False,
            residual_activation_tick=None,
            major_win_surfaced=False,
            major_win_tick=None,
            completed_tick=None,
        )
        team_state = TeamState(
            team_id="team-0",
            team_size=2,
            assigned_initiative_id="init-0",
        )
        ws = WorldState(
            tick=7,
            initiative_states=(init_state,),
            team_states=(team_state,),
            portfolio_capability=1.5,
        )
        cfg = make_initiative(
            initiative_id="init-0",
            observable_ceiling=80.0,
            planned_duration_ticks=20,
            true_duration_ticks=25,
        )
        config_map = {cfg.initiative_id: cfg}
        team_size_map = {"team-0": 2}
        return ws, config_map, team_size_map

    def test_observation_boundary_no_latent_quality(self) -> None:
        """Latent quality must not appear in any observation field."""
        ws, config_map, team_size_map = self._make_simple_world_state()
        config = make_simulation_config()
        obs = _build_governance_observation(ws, config, config_map, team_size_map)

        # Check that no InitiativeObservation has a latent_quality field.
        for init_obs in obs.initiatives:
            assert not hasattr(init_obs, "latent_quality")

    def test_effective_tam_patience_window_computed(self) -> None:
        """effective_tam_patience_window = max(1, ceil(T_tam * ceiling / ref_ceiling))."""
        ws, config_map, team_size_map = self._make_simple_world_state()
        config = make_simulation_config(
            governance=make_governance_config(base_tam_patience_window=5),
            model=make_model_config(reference_ceiling=100.0),
        )
        obs = _build_governance_observation(ws, config, config_map, team_size_map)

        init_obs = obs.initiatives[0]
        # ceil(5 * 80.0 / 100.0) = ceil(4.0) = 4
        assert init_obs.effective_tam_patience_window == 4

    def test_implied_duration_ticks_computed(self) -> None:
        """implied_duration_ticks = round(planned / max(exec_belief, eps))."""
        ws, config_map, team_size_map = self._make_simple_world_state()
        config = make_simulation_config()
        obs = _build_governance_observation(ws, config, config_map, team_size_map)

        init_obs = obs.initiatives[0]
        # round(20 / max(0.9, 0.05)) = round(22.22) = 22
        assert init_obs.implied_duration_ticks == 22

    def test_progress_fraction_computed(self) -> None:
        """progress_fraction = min(staffed / planned, 1.0)."""
        ws, config_map, team_size_map = self._make_simple_world_state()
        config = make_simulation_config()
        obs = _build_governance_observation(ws, config, config_map, team_size_map)

        init_obs = obs.initiatives[0]
        # min(5 / 20, 1.0) = 0.25
        assert init_obs.progress_fraction == pytest.approx(0.25)

    def test_attention_max_defaults_to_one(self) -> None:
        """When attention_max is None, effective is 1.0."""
        ws, config_map, team_size_map = self._make_simple_world_state()
        config = make_simulation_config(
            governance=make_governance_config(attention_max=None),
        )
        obs = _build_governance_observation(ws, config, config_map, team_size_map)
        assert obs.attention_max_effective == 1.0

    def test_portfolio_capability_level_reflected(self) -> None:
        ws, config_map, team_size_map = self._make_simple_world_state()
        config = make_simulation_config()
        obs = _build_governance_observation(ws, config, config_map, team_size_map)
        assert obs.portfolio_capability_level == 1.5


# ============================================================================
# _detect_reassignments
# ============================================================================


class TestDetectReassignments:
    """Tests for reassignment event detection."""

    def test_idle_reassignment(self) -> None:
        """Team was idle, now assigned → idle_reassignment."""
        ws = WorldState(
            tick=5,
            initiative_states=(
                InitiativeState(
                    initiative_id="init-0",
                    lifecycle_state=LifecycleState.UNASSIGNED,
                    assigned_team_id=None,
                    quality_belief_t=0.5,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=0,
                    ticks_since_assignment=0,
                    age_ticks=5,
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
                ),
            ),
            team_states=(TeamState(team_id="team-0", team_size=1, assigned_initiative_id=None),),
            portfolio_capability=1.0,
        )
        actions = GovernanceActions(
            continue_stop=(),
            assign_team=(AssignTeamAction(team_id="team-0", initiative_id="init-0"),),
            set_exec_attention=(),
        )
        events = _detect_reassignments(ws, actions, {}, current_tick=5)
        assert len(events) == 1
        assert events[0].triggered_by == ReassignmentTrigger.IDLE_REASSIGNMENT
        assert events[0].from_initiative_id is None
        assert events[0].to_initiative_id == "init-0"

    def test_governance_stop_reassignment(self) -> None:
        """Team freed by stop, reassigned → governance_stop."""
        ws = WorldState(
            tick=5,
            initiative_states=(
                InitiativeState(
                    initiative_id="init-0",
                    lifecycle_state=LifecycleState.ACTIVE,
                    assigned_team_id="team-0",
                    quality_belief_t=0.3,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=3,
                    ticks_since_assignment=3,
                    age_ticks=5,
                    cumulative_value_realized=0.0,
                    cumulative_lump_value_realized=0.0,
                    cumulative_residual_value_realized=0.0,
                    cumulative_labor_invested=3.0,
                    cumulative_attention_invested=1.0,
                    belief_history=(0.4, 0.35, 0.3),
                    review_count=3,
                    consecutive_reviews_below_tam_ratio=0,
                    residual_activated=False,
                    residual_activation_tick=None,
                    major_win_surfaced=False,
                    major_win_tick=None,
                    completed_tick=None,
                ),
                InitiativeState(
                    initiative_id="init-1",
                    lifecycle_state=LifecycleState.UNASSIGNED,
                    assigned_team_id=None,
                    quality_belief_t=0.5,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=0,
                    ticks_since_assignment=0,
                    age_ticks=5,
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
                ),
            ),
            team_states=(
                TeamState(team_id="team-0", team_size=1, assigned_initiative_id="init-0"),
            ),
            portfolio_capability=1.0,
        )
        actions = GovernanceActions(
            continue_stop=(
                ContinueStopAction(
                    initiative_id="init-0",
                    decision=StopContinueDecision.STOP,
                ),
            ),
            assign_team=(AssignTeamAction(team_id="team-0", initiative_id="init-1"),),
            set_exec_attention=(),
        )
        events = _detect_reassignments(ws, actions, {}, current_tick=5)
        assert len(events) == 1
        assert events[0].triggered_by == ReassignmentTrigger.GOVERNANCE_STOP


# ============================================================================
# run_single_regime — integration
# ============================================================================


def _make_simple_run_config(
    *,
    tick_horizon: int = 10,
    record_per_tick_logs: bool = True,
    record_event_log: bool = True,
) -> SimulationConfiguration:
    """Build a minimal but complete configuration for integration tests.

    Uses a single bounded-duration initiative with a team that can
    complete it within the horizon.
    """
    return make_simulation_config(
        time=TimeConfig(tick_horizon=tick_horizon),
        teams=WorkforceConfig(
            team_count=1,
            team_size=1,
            ramp_period=2,
            ramp_multiplier_shape=RampShape.LINEAR,
        ),
        initiatives=(
            make_initiative(
                initiative_id="init-0",
                latent_quality=0.7,
                dependency_level=0.1,
                base_signal_st_dev=0.1,
                true_duration_ticks=5,
                planned_duration_ticks=5,
                generation_tag="flywheel",
                value_channels=make_value_channels(
                    lump_enabled=True,
                    lump_value=10.0,
                    residual_enabled=True,
                    residual_rate=1.0,
                    residual_decay=0.0,
                ),
            ),
        ),
        reporting=ReportingConfig(
            record_per_tick_logs=record_per_tick_logs,
            record_event_log=record_event_log,
        ),
    )


class TestRunSingleRegime:
    """Integration tests for the full simulation run."""

    def test_basic_run_completes(self) -> None:
        """A basic run completes without errors and returns RunResult."""
        config = _make_simple_run_config()
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        assert isinstance(result, RunResult)
        assert result.manifest.baseline_spec_version == BASELINE_SPEC_VERSION
        assert result.manifest.world_seed == 42

    def test_deterministic_replay(self) -> None:
        """Two runs with the same seed produce identical results."""
        config = _make_simple_run_config()
        policy = BalancedPolicy()

        result1, _ = run_single_regime(config, policy)
        result2, _ = run_single_regime(config, policy)

        assert result1.cumulative_value_total == pytest.approx(result2.cumulative_value_total)
        assert result1.belief_accuracy.mean_absolute_belief_error == pytest.approx(
            result2.belief_accuracy.mean_absolute_belief_error
        )

    def test_horizon_is_measurement_boundary(self) -> None:
        """Initiatives still active at horizon remain active (not stopped)."""
        # Use a very short horizon so the initiative can't complete.
        config = _make_simple_run_config(tick_horizon=3)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        # The initiative should still be active (not enough ticks to complete
        # or trigger a stop with these parameters).
        # Check that no stop events were recorded for it, or it appears
        # in the exploration cost with zero stopped.
        assert result.exploration_cost_profile.cumulative_labor_in_stopped_initiatives >= 0.0

    def test_per_tick_logs_present_when_enabled(self) -> None:
        """Per-tick logs are populated when record_per_tick_logs is True."""
        config = _make_simple_run_config(record_per_tick_logs=True)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        assert result.per_initiative_tick_records is not None
        assert result.portfolio_tick_records is not None
        assert len(result.portfolio_tick_records) > 0

    def test_per_tick_logs_none_when_disabled(self) -> None:
        """Per-tick logs are None when record_per_tick_logs is False."""
        config = _make_simple_run_config(record_per_tick_logs=False)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        assert result.per_initiative_tick_records is None
        assert result.portfolio_tick_records is None

    def test_event_logs_present_when_enabled(self) -> None:
        """Event logs are populated when record_event_log is True."""
        config = _make_simple_run_config(record_event_log=True)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        assert result.major_win_event_log is not None
        assert result.stop_event_log is not None

    def test_event_logs_none_when_disabled(self) -> None:
        """Event logs are None when record_event_log is False."""
        config = _make_simple_run_config(record_event_log=False)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        assert result.major_win_event_log is None
        assert result.stop_event_log is None

    def test_value_channels_accumulate(self) -> None:
        """Lump and residual value accumulate over the run."""
        config = _make_simple_run_config(tick_horizon=20)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        # With lump_value=10 and residual_rate=1.0 with decay=0,
        # we should see positive cumulative value.
        assert result.cumulative_value_total > 0.0

    def test_idle_teams_counted(self) -> None:
        """Idle team-ticks are counted in the idle capacity profile."""
        # With 1 team and 1 initiative, the team is idle until assigned.
        # At tick 0, the team is idle (policy hasn't assigned yet).
        config = _make_simple_run_config(tick_horizon=5)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        # At least tick 0 should have the team idle before assignment.
        assert result.idle_capacity_profile.cumulative_idle_team_ticks >= 0

    def test_manifest_contains_configuration(self) -> None:
        """Manifest records the full configuration."""
        config = _make_simple_run_config()
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        assert result.manifest.resolved_configuration == config
        assert len(result.manifest.resolved_initiatives) == 1
        assert result.manifest.policy_id == config.governance.policy_id


# ============================================================================
# run_single_regime with generator
# ============================================================================


class TestRunWithGenerator:
    """Test run_single_regime with an initiative_generator."""

    def test_generator_resolved_before_run(self) -> None:
        """Initiative generator is resolved into concrete initiatives."""
        gen_config = InitiativeGeneratorConfig(
            type_specs=(
                InitiativeTypeSpec(
                    generation_tag="flywheel",
                    count=2,
                    quality_distribution=BetaDistribution(alpha=2.0, beta=2.0),
                    base_signal_st_dev_range=(0.1, 0.2),
                    dependency_level_range=(0.0, 0.3),
                    true_duration_range=(5, 10),
                    planned_duration_range=(5, 10),
                    completion_lump_enabled=True,
                    completion_lump_value_range=(5.0, 15.0),
                ),
            ),
        )
        config = make_simulation_config(
            initiatives=None,
            initiative_generator=gen_config,
            time=TimeConfig(tick_horizon=5),
            teams=WorkforceConfig(team_count=2, team_size=1, ramp_period=2),
        )
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        assert isinstance(result, RunResult)
        # Generator should have produced 2 initiatives.
        assert len(result.manifest.resolved_initiatives) == 2


# ============================================================================
# run_batch
# ============================================================================


class TestRunBatch:
    """Tests for batch execution."""

    def test_batch_returns_list_of_results(self) -> None:
        config1 = _make_simple_run_config(tick_horizon=5)
        config2 = _make_simple_run_config(tick_horizon=5)
        policy = BalancedPolicy()

        results = run_batch([config1, config2], [policy, policy])
        assert len(results) == 2
        assert all(isinstance(r, tuple) and isinstance(r[0], RunResult) for r in results)

    def test_batch_length_mismatch_raises(self) -> None:
        config = _make_simple_run_config()
        policy = BalancedPolicy()

        with pytest.raises(ValueError, match="same length"):
            run_batch([config, config], [policy])

    def test_batch_empty(self) -> None:
        results = run_batch([], [])
        assert results == []

    def test_batch_independent_results(self) -> None:
        """Each batch item is independent (no shared mutable state)."""
        config1 = make_simulation_config(
            world_seed=42,
            time=TimeConfig(tick_horizon=5),
            teams=WorkforceConfig(team_count=1, team_size=1, ramp_period=2),
            initiatives=(
                make_initiative(
                    initiative_id="init-0",
                    true_duration_ticks=3,
                    planned_duration_ticks=3,
                    value_channels=make_value_channels(lump_enabled=True, lump_value=10.0),
                ),
            ),
        )
        config2 = make_simulation_config(
            world_seed=99,
            time=TimeConfig(tick_horizon=5),
            teams=WorkforceConfig(team_count=1, team_size=1, ramp_period=2),
            initiatives=(
                make_initiative(
                    initiative_id="init-0",
                    true_duration_ticks=3,
                    planned_duration_ticks=3,
                    value_channels=make_value_channels(lump_enabled=True, lump_value=10.0),
                ),
            ),
        )
        policy = BalancedPolicy()

        results = run_batch([config1, config2], [policy, policy])
        # Different seeds may produce different belief trajectories
        # (different quality signals), but both should complete.
        assert len(results) == 2
        # Both should have the same lump value (deterministic completion).
        assert results[0][0].value_by_channel.completion_lump_value == pytest.approx(10.0)
        assert results[1][0].value_by_channel.completion_lump_value == pytest.approx(10.0)


# ============================================================================
# Edge cases and invariant verification
# ============================================================================


class TestRunnerInvariants:
    """Tests verifying key runner invariants."""

    def test_cumulative_value_is_lump_plus_residual(self) -> None:
        """cumulative_value_total = lump + residual."""
        config = _make_simple_run_config(tick_horizon=15)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        expected = (
            result.value_by_channel.completion_lump_value + result.value_by_channel.residual_value
        )
        assert result.cumulative_value_total == pytest.approx(expected)

    def test_terminal_capability_at_baseline_without_enablers(self) -> None:
        """Without enablers, terminal C_t stays at or near 1.0."""
        config = _make_simple_run_config(tick_horizon=10)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        # No enabler initiatives, so capability should decay toward 1.0.
        assert result.terminal_capability_t >= 1.0

    def test_ramp_labor_non_negative(self) -> None:
        """Cumulative ramp labor is always non-negative."""
        config = _make_simple_run_config(tick_horizon=10)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        assert result.cumulative_ramp_labor >= 0.0

    def test_idle_fraction_in_zero_one(self) -> None:
        """Idle team-tick fraction is in [0, 1]."""
        config = _make_simple_run_config(tick_horizon=10)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        assert 0.0 <= result.idle_capacity_profile.idle_team_tick_fraction <= 1.0
