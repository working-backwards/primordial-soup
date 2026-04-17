"""Tests for reporting.py — output schemas and aggregation functions.

Tests verify:
    - Frozen dataclass contracts for all record types
    - compute_belief_accuracy with known inputs
    - compute_value_by_channel label disaggregation
    - compute_major_win_profile with and without events
    - compute_idle_capacity_profile edge cases
    - compute_exploration_cost_profile with mixed events
    - compute_terminal_aggregate_residual_rate decay math
    - assemble_run_result integration
"""

from __future__ import annotations

import math

import pytest

from conftest import (
    make_initiative,
    make_simulation_config,
    make_value_channels,
)
from primordial_soup.config import ReportingConfig
from primordial_soup.events import CompletionEvent, MajorWinEvent, StopEvent
from primordial_soup.reporting import (
    PerInitiativeTickRecord,
    PortfolioTickRecord,
    RightTailFalseStopProfile,
    RunCollector,
    RunManifest,
    RunResult,
    assemble_run_result,
    compute_belief_accuracy,
    compute_exploration_cost_profile,
    compute_family_timing_profile,
    compute_frontier_summary,
    compute_idle_capacity_profile,
    compute_major_win_profile,
    compute_right_tail_false_stop_profile,
    compute_terminal_aggregate_residual_rate,
    compute_value_by_channel,
    compute_value_by_family,
)
from primordial_soup.state import InitiativeState, TeamState, WorldState
from primordial_soup.types import LifecycleState

# ============================================================================
# Frozen dataclass sanity checks
# ============================================================================


class TestPerInitiativeTickRecord:
    """PerInitiativeTickRecord is frozen and stores expected fields."""

    def test_frozen(self) -> None:
        record = PerInitiativeTickRecord(
            tick=0,
            initiative_id="init-0",
            lifecycle_state="active",
            quality_belief_t=0.5,
            latent_quality=0.6,
            exec_attention_a_t=0.3,
            effective_sigma_t=0.1,
            execution_belief_t=None,
            is_ramping=False,
            ramp_multiplier=None,
        )
        with pytest.raises(AttributeError):
            record.tick = 1  # type: ignore[misc]

    def test_fields_accessible(self) -> None:
        record = PerInitiativeTickRecord(
            tick=5,
            initiative_id="init-1",
            lifecycle_state="active",
            quality_belief_t=0.7,
            latent_quality=0.8,
            exec_attention_a_t=0.2,
            effective_sigma_t=0.15,
            execution_belief_t=0.9,
            is_ramping=True,
            ramp_multiplier=0.5,
        )
        assert record.tick == 5
        assert record.initiative_id == "init-1"
        assert record.latent_quality == 0.8
        assert record.is_ramping is True
        assert record.ramp_multiplier == 0.5


class TestPortfolioTickRecord:
    """PortfolioTickRecord is frozen and stores expected fields."""

    def test_frozen(self) -> None:
        record = PortfolioTickRecord(
            tick=0,
            capability_C_t=1.0,
            active_initiative_count=3,
            idle_team_count=1,
            total_exec_attention_allocated=0.6,
        )
        with pytest.raises(AttributeError):
            record.tick = 1  # type: ignore[misc]


class TestRunManifest:
    """RunManifest is frozen."""

    def test_frozen(self) -> None:
        config = make_simulation_config()
        manifest = RunManifest(
            policy_id="balanced",
            world_seed=42,
            is_replay=False,
            resolved_configuration=config,
            resolved_initiatives=config.initiatives or (),
            baseline_spec_version="0.1.0",
        )
        with pytest.raises(AttributeError):
            manifest.world_seed = 99  # type: ignore[misc]
        assert manifest.policy_id == "balanced"


# ============================================================================
# compute_belief_accuracy
# ============================================================================


class TestComputeBeliefAccuracy:
    """Tests for belief accuracy aggregation."""

    def test_empty_records_returns_zeros(self) -> None:
        result = compute_belief_accuracy([])
        assert result.mean_absolute_belief_error == 0.0
        assert result.mean_squared_belief_error == 0.0

    def test_perfect_beliefs(self) -> None:
        """When belief == latent_quality, errors are zero."""
        records = [
            PerInitiativeTickRecord(
                tick=t,
                initiative_id="init-0",
                lifecycle_state="active",
                quality_belief_t=0.6,
                latent_quality=0.6,
                exec_attention_a_t=0.3,
                effective_sigma_t=0.1,
                execution_belief_t=None,
                is_ramping=False,
                ramp_multiplier=None,
            )
            for t in range(5)
        ]
        result = compute_belief_accuracy(records)
        assert result.mean_absolute_belief_error == pytest.approx(0.0)
        assert result.mean_squared_belief_error == pytest.approx(0.0)

    def test_known_errors(self) -> None:
        """MAE and MSE with known belief-quality differences."""
        # belief=0.7, quality=0.5 → error=0.2
        # belief=0.3, quality=0.5 → error=-0.2
        records = [
            PerInitiativeTickRecord(
                tick=0,
                initiative_id="init-0",
                lifecycle_state="active",
                quality_belief_t=0.7,
                latent_quality=0.5,
                exec_attention_a_t=0.3,
                effective_sigma_t=0.1,
                execution_belief_t=None,
                is_ramping=False,
                ramp_multiplier=None,
            ),
            PerInitiativeTickRecord(
                tick=1,
                initiative_id="init-0",
                lifecycle_state="active",
                quality_belief_t=0.3,
                latent_quality=0.5,
                exec_attention_a_t=0.3,
                effective_sigma_t=0.1,
                execution_belief_t=None,
                is_ramping=False,
                ramp_multiplier=None,
            ),
        ]
        result = compute_belief_accuracy(records)
        # MAE = (0.2 + 0.2) / 2 = 0.2
        assert result.mean_absolute_belief_error == pytest.approx(0.2)
        # MSE = (0.04 + 0.04) / 2 = 0.04
        assert result.mean_squared_belief_error == pytest.approx(0.04)


# ============================================================================
# compute_value_by_channel
# ============================================================================


class TestComputeValueByChannel:
    """Tests for value-by-channel breakdown."""

    def test_basic_channel_separation(self) -> None:
        """Lump and residual values are correctly separated."""
        configs = (
            make_initiative(
                initiative_id="init-0",
                generation_tag="flywheel",
            ),
        )
        result = compute_value_by_channel(
            cumulative_lump_value=10.0,
            cumulative_residual_value=5.0,
            stop_events=[],
            completion_events=[],
            initiative_configs=configs,
            residual_value_by_initiative={"init-0": 5.0},
        )
        assert result.completion_lump_value == 10.0
        assert result.residual_value == 5.0
        assert result.residual_value_by_label == {"flywheel": 5.0}

    def test_residual_by_label_multiple_types(self) -> None:
        """Residual value disaggregated by label across types."""
        configs = (
            make_initiative(initiative_id="init-0", generation_tag="flywheel"),
            make_initiative(initiative_id="init-1", generation_tag="quick_win"),
            make_initiative(initiative_id="init-2", generation_tag="flywheel"),
        )
        result = compute_value_by_channel(
            cumulative_lump_value=0.0,
            cumulative_residual_value=9.0,
            stop_events=[],
            completion_events=[],
            initiative_configs=configs,
            residual_value_by_initiative={
                "init-0": 3.0,
                "init-1": 2.0,
                "init-2": 4.0,
            },
        )
        assert result.residual_value_by_label["flywheel"] == pytest.approx(7.0)
        assert result.residual_value_by_label["quick_win"] == pytest.approx(2.0)

    def test_no_residual_gives_empty_labels(self) -> None:
        """When no residual value, label dict is empty."""
        configs = (make_initiative(initiative_id="init-0"),)
        result = compute_value_by_channel(
            cumulative_lump_value=5.0,
            cumulative_residual_value=0.0,
            stop_events=[],
            completion_events=[],
            initiative_configs=configs,
            residual_value_by_initiative={},
        )
        assert result.residual_value_by_label == {}


# ============================================================================
# compute_major_win_profile
# ============================================================================


class TestComputeMajorWinProfile:
    """Tests for major-win profile computation."""

    def test_no_major_wins(self) -> None:
        result = compute_major_win_profile(
            major_win_events=[],
            initiative_configs=(),
            total_right_tail_labor=50.0,
        )
        assert result.major_win_count == 0
        assert result.time_to_major_win == ()
        assert result.major_win_count_by_label == {}
        assert result.labor_per_major_win is None

    def test_single_major_win(self) -> None:
        configs = (
            make_initiative(
                initiative_id="init-0",
                generation_tag="right_tail",
            ),
        )
        events = [
            MajorWinEvent(
                initiative_id="init-0",
                tick=15,
                latent_quality=0.9,
                observable_ceiling=100.0,
                quality_belief_at_completion=0.85,
                execution_belief_at_completion=None,
                cumulative_labor_invested=15.0,
                cumulative_attention_invested=5.0,
                staffed_tick_count=15,
                observed_history_snapshot=(0.5, 0.6, 0.7, 0.8),
            )
        ]
        result = compute_major_win_profile(
            major_win_events=events,
            initiative_configs=configs,
            total_right_tail_labor=30.0,
        )
        assert result.major_win_count == 1
        # created_tick defaults to 0, so time = 15 - 0 = 15.
        assert result.time_to_major_win == (15,)
        assert result.major_win_count_by_label == {"right_tail": 1}
        assert result.labor_per_major_win == pytest.approx(30.0)

    def test_multiple_major_wins(self) -> None:
        configs = (
            make_initiative(initiative_id="init-0", generation_tag="right_tail"),
            make_initiative(initiative_id="init-1", generation_tag="right_tail"),
        )
        events = [
            MajorWinEvent(
                initiative_id="init-0",
                tick=10,
                latent_quality=0.9,
                observable_ceiling=100.0,
                quality_belief_at_completion=0.8,
                execution_belief_at_completion=None,
                cumulative_labor_invested=10.0,
                cumulative_attention_invested=3.0,
                staffed_tick_count=10,
                observed_history_snapshot=(),
            ),
            MajorWinEvent(
                initiative_id="init-1",
                tick=20,
                latent_quality=0.85,
                observable_ceiling=80.0,
                quality_belief_at_completion=0.75,
                execution_belief_at_completion=None,
                cumulative_labor_invested=20.0,
                cumulative_attention_invested=6.0,
                staffed_tick_count=20,
                observed_history_snapshot=(),
            ),
        ]
        result = compute_major_win_profile(
            major_win_events=events,
            initiative_configs=configs,
            total_right_tail_labor=60.0,
        )
        assert result.major_win_count == 2
        assert result.labor_per_major_win == pytest.approx(30.0)


# ============================================================================
# compute_idle_capacity_profile
# ============================================================================


class TestComputeIdleCapacityProfile:
    """Tests for idle capacity profile computation."""

    def test_no_idle(self) -> None:
        result = compute_idle_capacity_profile(
            cumulative_idle_team_ticks=0,
            total_team_ticks=300,
            pool_exhaustion_tick=None,
        )
        assert result.cumulative_idle_team_ticks == 0
        assert result.idle_team_tick_fraction == pytest.approx(0.0)
        assert result.pool_exhaustion_tick is None

    def test_all_idle(self) -> None:
        result = compute_idle_capacity_profile(
            cumulative_idle_team_ticks=300,
            total_team_ticks=300,
            pool_exhaustion_tick=0,
        )
        assert result.idle_team_tick_fraction == pytest.approx(1.0)
        assert result.pool_exhaustion_tick == 0

    def test_partial_idle(self) -> None:
        result = compute_idle_capacity_profile(
            cumulative_idle_team_ticks=75,
            total_team_ticks=300,
            pool_exhaustion_tick=50,
        )
        assert result.idle_team_tick_fraction == pytest.approx(0.25)

    def test_zero_total_team_ticks(self) -> None:
        """Edge case: no team-ticks at all."""
        result = compute_idle_capacity_profile(
            cumulative_idle_team_ticks=0,
            total_team_ticks=0,
            pool_exhaustion_tick=None,
        )
        assert result.idle_team_tick_fraction == pytest.approx(0.0)


# ============================================================================
# compute_exploration_cost_profile
# ============================================================================


class TestComputeExplorationCostProfile:
    """Tests for exploration cost profile computation."""

    def test_no_events(self) -> None:
        result = compute_exploration_cost_profile(
            stop_events=[],
            completion_events=[],
            initiative_configs=(),
            cumulative_labor_by_initiative={},
            cumulative_attention_by_initiative={},
        )
        assert result.cumulative_labor_in_stopped_initiatives == 0.0
        assert result.cumulative_labor_in_completed_initiatives == 0.0
        assert result.stopped_initiative_count_by_label == {}
        assert result.completed_initiative_count_by_label == {}
        assert result.latent_quality_distribution_of_stopped == ()

    def test_mixed_stop_and_completion(self) -> None:
        configs = (
            make_initiative(initiative_id="init-0", generation_tag="flywheel"),
            make_initiative(initiative_id="init-1", generation_tag="right_tail"),
        )
        stop_events = [
            StopEvent(
                tick=5,
                initiative_id="init-0",
                quality_belief_t=0.3,
                execution_belief_t=None,
                latent_quality=0.4,
                triggering_rule="confidence_decline",
                cumulative_labor_invested=5.0,
                staffed_ticks=5,
                governance_archetype="balanced",
            ),
        ]
        completion_events = [
            CompletionEvent(
                initiative_id="init-1",
                tick=10,
                latent_quality=0.8,
                cumulative_labor_invested=10.0,
            ),
        ]
        result = compute_exploration_cost_profile(
            stop_events=stop_events,
            completion_events=completion_events,
            initiative_configs=configs,
            cumulative_labor_by_initiative={"init-0": 5.0, "init-1": 10.0},
            cumulative_attention_by_initiative={"init-0": 2.0, "init-1": 4.0},
        )
        assert result.cumulative_labor_in_stopped_initiatives == pytest.approx(5.0)
        assert result.cumulative_attention_in_stopped_initiatives == pytest.approx(2.0)
        assert result.stopped_initiative_count_by_label == {"flywheel": 1}
        assert result.latent_quality_distribution_of_stopped == (0.4,)
        assert result.cumulative_labor_in_completed_initiatives == pytest.approx(10.0)
        assert result.completed_initiative_count_by_label == {"right_tail": 1}


# ============================================================================
# compute_terminal_aggregate_residual_rate
# ============================================================================


class TestComputeTerminalAggregateResidualRate:
    """Tests for terminal residual rate computation."""

    def test_no_residual_activated(self) -> None:
        result = compute_terminal_aggregate_residual_rate(
            initiative_configs=(),
            residual_activated_ids=set(),
            final_tick=99,
            residual_activation_ticks={},
        )
        assert result == pytest.approx(0.0)

    def test_single_residual_no_decay(self) -> None:
        """Residual with decay=0 maintains full rate."""
        configs = (
            make_initiative(
                initiative_id="init-0",
                value_channels=make_value_channels(
                    residual_enabled=True,
                    residual_rate=2.0,
                    residual_decay=0.0,
                ),
            ),
        )
        result = compute_terminal_aggregate_residual_rate(
            initiative_configs=configs,
            residual_activated_ids={"init-0"},
            final_tick=50,
            residual_activation_ticks={"init-0": 10},
        )
        assert result == pytest.approx(2.0)

    def test_residual_with_decay(self) -> None:
        """Residual decays exponentially from activation tick."""
        configs = (
            make_initiative(
                initiative_id="init-0",
                value_channels=make_value_channels(
                    residual_enabled=True,
                    residual_rate=1.0,
                    residual_decay=0.1,
                ),
            ),
        )
        result = compute_terminal_aggregate_residual_rate(
            initiative_configs=configs,
            residual_activated_ids={"init-0"},
            final_tick=20,
            residual_activation_ticks={"init-0": 10},
        )
        # rate = 1.0 * exp(-0.1 * 10) = exp(-1.0)
        expected = math.exp(-1.0)
        assert result == pytest.approx(expected)

    def test_multiple_residuals_summed(self) -> None:
        """Multiple activated residuals are summed."""
        configs = (
            make_initiative(
                initiative_id="init-0",
                value_channels=make_value_channels(
                    residual_enabled=True,
                    residual_rate=1.0,
                    residual_decay=0.0,
                ),
            ),
            make_initiative(
                initiative_id="init-1",
                value_channels=make_value_channels(
                    residual_enabled=True,
                    residual_rate=3.0,
                    residual_decay=0.0,
                ),
            ),
        )
        result = compute_terminal_aggregate_residual_rate(
            initiative_configs=configs,
            residual_activated_ids={"init-0", "init-1"},
            final_tick=50,
            residual_activation_ticks={"init-0": 10, "init-1": 20},
        )
        assert result == pytest.approx(4.0)


# ============================================================================
# RunCollector
# ============================================================================


class TestRunCollector:
    """RunCollector is mutable and initializes to empty state."""

    def test_default_state(self) -> None:
        collector = RunCollector()
        assert collector.cumulative_lump_value == 0.0
        assert collector.cumulative_residual_value == 0.0
        assert collector.completion_events == []
        assert collector.major_win_events == []
        assert collector.stop_events == []
        assert collector.reassignment_events == []
        assert collector.cumulative_idle_team_ticks == 0
        assert collector.pool_exhaustion_tick is None
        assert collector.cumulative_ramp_labor == 0.0

    def test_mutable(self) -> None:
        collector = RunCollector()
        collector.cumulative_lump_value = 5.0
        assert collector.cumulative_lump_value == 5.0


# ============================================================================
# assemble_run_result (integration)
# ============================================================================


class TestAssembleRunResult:
    """Integration test for full RunResult assembly."""

    def test_minimal_assembly(self) -> None:
        """Assemble a RunResult from a minimal single-tick scenario."""
        config = make_simulation_config(
            initiatives=(
                make_initiative(
                    initiative_id="init-0",
                    generation_tag="flywheel",
                ),
            ),
        )
        init_configs = config.initiatives
        assert init_configs is not None

        # Simulate a world state with one stopped initiative.
        final_ws = WorldState(
            tick=1,
            initiative_states=(
                InitiativeState(
                    initiative_id="init-0",
                    lifecycle_state=LifecycleState.STOPPED,
                    assigned_team_id=None,
                    quality_belief_t=0.3,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=1,
                    ticks_since_assignment=1,
                    age_ticks=1,
                    cumulative_value_realized=0.0,
                    cumulative_lump_value_realized=0.0,
                    cumulative_residual_value_realized=0.0,
                    cumulative_labor_invested=1.0,
                    cumulative_attention_invested=0.5,
                    belief_history=(0.3,),
                    review_count=1,
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

        manifest = RunManifest(
            policy_id="balanced",
            world_seed=42,
            is_replay=False,
            resolved_configuration=config,
            resolved_initiatives=init_configs,
            baseline_spec_version="0.1.0",
        )

        collector = RunCollector()
        collector.cumulative_lump_value = 0.0
        collector.cumulative_residual_value = 0.0
        collector.stop_events.append(
            StopEvent(
                tick=0,
                initiative_id="init-0",
                quality_belief_t=0.3,
                execution_belief_t=None,
                latent_quality=0.6,
                triggering_rule="confidence_decline",
                cumulative_labor_invested=1.0,
                staffed_ticks=1,
                governance_archetype="balanced",
            )
        )

        result = assemble_run_result(
            collector=collector,
            config=config,
            initiative_configs=init_configs,
            final_world_state=final_ws,
            manifest=manifest,
        )

        assert isinstance(result, RunResult)
        assert result.cumulative_value_total == pytest.approx(0.0)
        assert result.terminal_capability_t == pytest.approx(1.0)
        assert result.terminal_aggregate_residual_rate == pytest.approx(0.0)
        assert result.exploration_cost_profile.stopped_initiative_count_by_label == {"flywheel": 1}
        assert result.manifest.policy_id == "balanced"

    def test_event_logs_conditional_on_reporting_config(self) -> None:
        """Event logs are None when record_event_log is False."""
        config = make_simulation_config(
            reporting=ReportingConfig(
                record_event_log=False,
                record_per_tick_logs=False,
            ),
        )
        init_configs = config.initiatives
        assert init_configs is not None

        final_ws = WorldState(
            tick=1,
            initiative_states=(
                InitiativeState(
                    initiative_id="init-1",
                    lifecycle_state=LifecycleState.ACTIVE,
                    assigned_team_id=None,
                    quality_belief_t=0.5,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=0,
                    ticks_since_assignment=0,
                    age_ticks=1,
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

        manifest = RunManifest(
            policy_id="balanced",
            world_seed=42,
            is_replay=False,
            resolved_configuration=config,
            resolved_initiatives=init_configs,
            baseline_spec_version="0.1.0",
        )

        collector = RunCollector()
        result = assemble_run_result(
            collector=collector,
            config=config,
            initiative_configs=init_configs,
            final_world_state=final_ws,
            manifest=manifest,
        )

        # Event logs should be None when disabled.
        assert result.major_win_event_log is None
        assert result.stop_event_log is None
        assert result.per_initiative_tick_records is None
        assert result.portfolio_tick_records is None

    def test_new_fields_present_in_assembled_result(self) -> None:
        """New Stage 5 fields are populated in assembled RunResult."""
        config = make_simulation_config(
            initiatives=(
                make_initiative(
                    initiative_id="init-0",
                    generation_tag="flywheel",
                ),
            ),
        )
        init_configs = config.initiatives
        assert init_configs is not None

        final_ws = WorldState(
            tick=1,
            initiative_states=(
                InitiativeState(
                    initiative_id="init-0",
                    lifecycle_state=LifecycleState.ACTIVE,
                    assigned_team_id=None,
                    quality_belief_t=0.5,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=0,
                    ticks_since_assignment=0,
                    age_ticks=1,
                    cumulative_value_realized=10.0,
                    cumulative_lump_value_realized=5.0,
                    cumulative_residual_value_realized=5.0,
                    cumulative_labor_invested=1.0,
                    cumulative_attention_invested=0.5,
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

        manifest = RunManifest(
            policy_id="balanced",
            world_seed=42,
            is_replay=False,
            resolved_configuration=config,
            resolved_initiatives=init_configs,
            baseline_spec_version="0.1.0",
        )

        collector = RunCollector()
        collector.cumulative_ramp_labor = 2.0
        result = assemble_run_result(
            collector=collector,
            config=config,
            initiative_configs=init_configs,
            final_world_state=final_ws,
            manifest=manifest,
        )

        # Ramp labor fraction: 2.0 / (1 team * 313 tick horizon)
        total_team_ticks = config.teams.team_count * config.time.tick_horizon
        assert result.ramp_labor_fraction == pytest.approx(2.0 / total_team_ticks)
        # Value by family: flywheel gets all value.
        assert "flywheel" in result.value_by_family
        assert result.value_by_family["flywheel"] == pytest.approx(10.0)
        # Family timing: no completions, so all first ticks are None.
        assert result.family_timing.first_completion_tick_by_family["flywheel"] is None
        assert result.family_timing.peak_capability_tick == 0
        # Frontier summary: no frontier state → None.
        assert result.frontier_summary is None


# ============================================================================
# Tests for Stage 5 compute functions
# ============================================================================


class TestComputeValueByFamily:
    """Tests for compute_value_by_family()."""

    def test_single_family(self) -> None:
        configs = (
            make_initiative(initiative_id="a", generation_tag="flywheel"),
            make_initiative(initiative_id="b", generation_tag="flywheel"),
        )
        ws = WorldState(
            tick=1,
            initiative_states=(
                InitiativeState(
                    initiative_id="a",
                    lifecycle_state=LifecycleState.ACTIVE,
                    assigned_team_id=None,
                    quality_belief_t=0.5,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=0,
                    ticks_since_assignment=0,
                    age_ticks=1,
                    cumulative_value_realized=10.0,
                    cumulative_lump_value_realized=5.0,
                    cumulative_residual_value_realized=5.0,
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
                InitiativeState(
                    initiative_id="b",
                    lifecycle_state=LifecycleState.ACTIVE,
                    assigned_team_id=None,
                    quality_belief_t=0.5,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=0,
                    ticks_since_assignment=0,
                    age_ticks=1,
                    cumulative_value_realized=20.0,
                    cumulative_lump_value_realized=10.0,
                    cumulative_residual_value_realized=10.0,
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
            team_states=(),
            portfolio_capability=1.0,
        )
        result = compute_value_by_family(configs, ws)
        assert result["flywheel"] == pytest.approx(30.0)

    def test_multiple_families(self) -> None:
        configs = (
            make_initiative(initiative_id="a", generation_tag="flywheel"),
            make_initiative(initiative_id="b", generation_tag="quick_win"),
        )
        ws = WorldState(
            tick=1,
            initiative_states=(
                InitiativeState(
                    initiative_id="a",
                    lifecycle_state=LifecycleState.ACTIVE,
                    assigned_team_id=None,
                    quality_belief_t=0.5,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=0,
                    ticks_since_assignment=0,
                    age_ticks=1,
                    cumulative_value_realized=10.0,
                    cumulative_lump_value_realized=0.0,
                    cumulative_residual_value_realized=10.0,
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
                InitiativeState(
                    initiative_id="b",
                    lifecycle_state=LifecycleState.ACTIVE,
                    assigned_team_id=None,
                    quality_belief_t=0.5,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=0,
                    ticks_since_assignment=0,
                    age_ticks=1,
                    cumulative_value_realized=5.0,
                    cumulative_lump_value_realized=5.0,
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
            team_states=(),
            portfolio_capability=1.0,
        )
        result = compute_value_by_family(configs, ws)
        assert result["flywheel"] == pytest.approx(10.0)
        assert result["quick_win"] == pytest.approx(5.0)


class TestComputeFamilyTimingProfile:
    """Tests for compute_family_timing_profile()."""

    def test_no_events(self) -> None:
        """No completions or stops → all None fields."""
        result = compute_family_timing_profile(
            completion_events=[],
            stop_events=[],
            initiative_configs=(),
            peak_capability_tick=0,
        )
        for family in ["flywheel", "right_tail", "enabler", "quick_win"]:
            assert result.first_completion_tick_by_family[family] is None
            assert result.mean_completion_tick_by_family[family] is None
            assert result.completion_ticks_by_family[family] == ()
        assert result.peak_capability_tick == 0
        assert result.first_right_tail_stop_tick is None

    def test_completions_by_family(self) -> None:
        """Completion ticks are correctly aggregated by family."""
        configs = (
            make_initiative(initiative_id="fw-1", generation_tag="flywheel"),
            make_initiative(initiative_id="fw-2", generation_tag="flywheel"),
            make_initiative(initiative_id="qw-1", generation_tag="quick_win"),
        )
        completions = [
            CompletionEvent(
                initiative_id="fw-1", tick=10, latent_quality=0.8, cumulative_labor_invested=5.0
            ),
            CompletionEvent(
                initiative_id="fw-2", tick=20, latent_quality=0.7, cumulative_labor_invested=8.0
            ),
            CompletionEvent(
                initiative_id="qw-1", tick=5, latent_quality=0.6, cumulative_labor_invested=2.0
            ),
        ]
        result = compute_family_timing_profile(
            completion_events=completions,
            stop_events=[],
            initiative_configs=configs,
            peak_capability_tick=15,
        )
        assert result.first_completion_tick_by_family["flywheel"] == 10
        assert result.mean_completion_tick_by_family["flywheel"] == pytest.approx(15.0)
        assert result.completion_ticks_by_family["flywheel"] == (10, 20)
        assert result.first_completion_tick_by_family["quick_win"] == 5
        assert result.first_completion_tick_by_family["right_tail"] is None
        assert result.peak_capability_tick == 15

    def test_first_right_tail_stop(self) -> None:
        """First right-tail stop tick is computed correctly."""
        configs = (
            make_initiative(initiative_id="rt-1", generation_tag="right_tail"),
            make_initiative(initiative_id="rt-2", generation_tag="right_tail"),
            make_initiative(initiative_id="fw-1", generation_tag="flywheel"),
        )
        stops = [
            StopEvent(
                tick=15,
                initiative_id="rt-2",
                quality_belief_t=0.2,
                execution_belief_t=None,
                latent_quality=0.1,
                triggering_rule="confidence_decline",
                cumulative_labor_invested=3.0,
                staffed_ticks=5,
                governance_archetype="balanced",
            ),
            StopEvent(
                tick=8,
                initiative_id="rt-1",
                quality_belief_t=0.3,
                execution_belief_t=None,
                latent_quality=0.2,
                triggering_rule="stagnation",
                cumulative_labor_invested=2.0,
                staffed_ticks=3,
                governance_archetype="balanced",
            ),
            StopEvent(
                tick=5,
                initiative_id="fw-1",
                quality_belief_t=0.3,
                execution_belief_t=None,
                latent_quality=0.3,
                triggering_rule="confidence_decline",
                cumulative_labor_invested=1.0,
                staffed_ticks=2,
                governance_archetype="balanced",
            ),
        ]
        result = compute_family_timing_profile(
            completion_events=[],
            stop_events=stops,
            initiative_configs=configs,
            peak_capability_tick=0,
        )
        # Earliest right-tail stop is tick 8 (rt-1), not tick 5 (that's flywheel).
        assert result.first_right_tail_stop_tick == 8


class TestComputeFrontierSummary:
    """Tests for compute_frontier_summary()."""

    def test_no_frontier_state(self) -> None:
        """No frontier → returns None."""
        ws = WorldState(
            tick=1,
            initiative_states=(),
            team_states=(),
            portfolio_capability=1.0,
        )
        assert compute_frontier_summary(ws) is None

    def test_with_frontier_state(self) -> None:
        """Frontier state is correctly extracted."""
        from primordial_soup.state import FamilyFrontierState

        ws = WorldState(
            tick=100,
            initiative_states=(),
            team_states=(),
            portfolio_capability=1.5,
            frontier_state_by_family=(
                (
                    "enabler",
                    FamilyFrontierState(
                        n_resolved=5, n_frontier_draws=2, effective_alpha_multiplier=0.95
                    ),
                ),
                (
                    "flywheel",
                    FamilyFrontierState(
                        n_resolved=10, n_frontier_draws=3, effective_alpha_multiplier=0.80
                    ),
                ),
            ),
        )
        result = compute_frontier_summary(ws)
        assert result is not None
        assert "enabler" in result.family_frontier_states
        assert result.family_frontier_states["enabler"]["n_resolved"] == 5
        assert result.family_frontier_states["flywheel"]["n_frontier_draws"] == 3


# ============================================================================
# compute_right_tail_false_stop_profile
# ============================================================================


class TestComputeRightTailFalseStopProfile:
    """Tests for right-tail false-stop profile computation.

    Per reporting_package_specification.md §Source fields and computation:
    - is_major_win_eligible requires BOTH major_win_event.enabled AND
      major_win_event.is_major_win to be True
    - Only generation_tag == "right_tail" initiatives are counted
    - right_tail_false_stop_rate = stopped_eligible / eligible
    - belief_at_stop comes from StopEvent.quality_belief_t
    """

    def test_no_right_tail_initiatives(self) -> None:
        """Zero right-tail initiatives → eligible=0, rate=None."""
        configs = (
            make_initiative(
                initiative_id="fw-1",
                generation_tag="flywheel",
            ),
        )
        result = compute_right_tail_false_stop_profile(
            stop_events=[],
            completion_events=[],
            initiative_configs=configs,
        )
        assert result.right_tail_eligible_count == 0
        assert result.right_tail_stopped_eligible_count == 0
        assert result.right_tail_completions == 0
        assert result.right_tail_stops == 0
        assert result.right_tail_false_stop_rate is None
        assert result.belief_at_stop_for_stopped_eligible == ()

    def test_eligible_all_stopped(self) -> None:
        """All eligible right-tail initiatives stopped → rate=1.0."""
        configs = (
            make_initiative(
                initiative_id="rt-1",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=True,
                ),
            ),
            make_initiative(
                initiative_id="rt-2",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=True,
                ),
            ),
        )
        stop_events = [
            StopEvent(
                tick=10,
                initiative_id="rt-1",
                quality_belief_t=0.35,
                execution_belief_t=None,
                latent_quality=0.8,
                triggering_rule="confidence_decline",
                cumulative_labor_invested=5.0,
                staffed_ticks=5,
                governance_archetype="balanced",
            ),
            StopEvent(
                tick=15,
                initiative_id="rt-2",
                quality_belief_t=0.25,
                execution_belief_t=None,
                latent_quality=0.9,
                triggering_rule="stagnation",
                cumulative_labor_invested=8.0,
                staffed_ticks=8,
                governance_archetype="balanced",
            ),
        ]
        result = compute_right_tail_false_stop_profile(
            stop_events=stop_events,
            completion_events=[],
            initiative_configs=configs,
        )
        assert result.right_tail_eligible_count == 2
        assert result.right_tail_stopped_eligible_count == 2
        assert result.right_tail_false_stop_rate == pytest.approx(1.0)
        assert result.right_tail_stops == 2
        assert result.right_tail_completions == 0

    def test_no_eligible_stopped(self) -> None:
        """Eligible right-tail initiatives all completed → rate=0.0."""
        configs = (
            make_initiative(
                initiative_id="rt-1",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=True,
                ),
            ),
        )
        completion_events = [
            CompletionEvent(
                initiative_id="rt-1",
                tick=20,
                latent_quality=0.9,
                cumulative_labor_invested=10.0,
            ),
        ]
        result = compute_right_tail_false_stop_profile(
            stop_events=[],
            completion_events=completion_events,
            initiative_configs=configs,
        )
        assert result.right_tail_eligible_count == 1
        assert result.right_tail_stopped_eligible_count == 0
        assert result.right_tail_false_stop_rate == pytest.approx(0.0)
        assert result.right_tail_completions == 1
        assert result.right_tail_stops == 0

    def test_mixed_eligible_and_non_eligible(self) -> None:
        """Mix of eligible and non-eligible right-tail initiatives."""
        configs = (
            # Eligible: major_win_event enabled AND is_major_win True.
            make_initiative(
                initiative_id="rt-eligible-1",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=True,
                ),
            ),
            # Not eligible: is_major_win is False (low quality).
            make_initiative(
                initiative_id="rt-not-eligible",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=False,
                ),
            ),
            # Eligible: both conditions met.
            make_initiative(
                initiative_id="rt-eligible-2",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=True,
                ),
            ),
        )
        # Stop only one eligible and the non-eligible.
        stop_events = [
            StopEvent(
                tick=10,
                initiative_id="rt-eligible-1",
                quality_belief_t=0.3,
                execution_belief_t=None,
                latent_quality=0.8,
                triggering_rule="confidence_decline",
                cumulative_labor_invested=5.0,
                staffed_ticks=5,
                governance_archetype="balanced",
            ),
            StopEvent(
                tick=12,
                initiative_id="rt-not-eligible",
                quality_belief_t=0.2,
                execution_belief_t=None,
                latent_quality=0.3,
                triggering_rule="confidence_decline",
                cumulative_labor_invested=6.0,
                staffed_ticks=6,
                governance_archetype="balanced",
            ),
        ]
        result = compute_right_tail_false_stop_profile(
            stop_events=stop_events,
            completion_events=[],
            initiative_configs=configs,
        )
        # 2 eligible, 1 stopped eligible → rate = 0.5.
        assert result.right_tail_eligible_count == 2
        assert result.right_tail_stopped_eligible_count == 1
        assert result.right_tail_false_stop_rate == pytest.approx(0.5)
        # 2 total right-tail stops (eligible + non-eligible).
        assert result.right_tail_stops == 2
        assert result.right_tail_completions == 0

    def test_non_right_tail_with_major_win_not_counted(self) -> None:
        """Flywheel with is_major_win=True must NOT be counted.

        The generation_tag filter is required — only right_tail
        initiatives contribute to these metrics.
        """
        configs = (
            # Flywheel with major_win_event enabled and is_major_win True.
            # This must NOT count as eligible for right-tail false-stop.
            make_initiative(
                initiative_id="fw-mw",
                generation_tag="flywheel",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=True,
                ),
            ),
            # Right-tail with is_major_win True — this IS eligible.
            make_initiative(
                initiative_id="rt-mw",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=True,
                ),
            ),
        )
        stop_events = [
            StopEvent(
                tick=5,
                initiative_id="fw-mw",
                quality_belief_t=0.4,
                execution_belief_t=None,
                latent_quality=0.9,
                triggering_rule="confidence_decline",
                cumulative_labor_invested=3.0,
                staffed_ticks=3,
                governance_archetype="balanced",
            ),
        ]
        result = compute_right_tail_false_stop_profile(
            stop_events=stop_events,
            completion_events=[],
            initiative_configs=configs,
        )
        # Only the right-tail initiative is eligible.
        assert result.right_tail_eligible_count == 1
        assert result.right_tail_stopped_eligible_count == 0
        assert result.right_tail_false_stop_rate == pytest.approx(0.0)
        # The flywheel stop does not count as a right-tail stop.
        assert result.right_tail_stops == 0

    def test_belief_at_stop_values_match_stop_events(self) -> None:
        """belief_at_stop_for_stopped_eligible matches StopEvent.quality_belief_t."""
        configs = (
            make_initiative(
                initiative_id="rt-a",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=True,
                ),
            ),
            make_initiative(
                initiative_id="rt-b",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=True,
                ),
            ),
        )
        stop_events = [
            # rt-b stopped first (tick 5), but id-sorted output puts rt-a first.
            StopEvent(
                tick=5,
                initiative_id="rt-b",
                quality_belief_t=0.22,
                execution_belief_t=None,
                latent_quality=0.85,
                triggering_rule="stagnation",
                cumulative_labor_invested=4.0,
                staffed_ticks=4,
                governance_archetype="balanced",
            ),
            StopEvent(
                tick=8,
                initiative_id="rt-a",
                quality_belief_t=0.31,
                execution_belief_t=None,
                latent_quality=0.9,
                triggering_rule="confidence_decline",
                cumulative_labor_invested=6.0,
                staffed_ticks=6,
                governance_archetype="balanced",
            ),
        ]
        result = compute_right_tail_false_stop_profile(
            stop_events=stop_events,
            completion_events=[],
            initiative_configs=configs,
        )
        # Sorted by initiative_id: rt-a (0.31), rt-b (0.22).
        assert result.belief_at_stop_for_stopped_eligible == (
            pytest.approx(0.31),
            pytest.approx(0.22),
        )

    def test_eligible_requires_both_enabled_and_is_major_win(self) -> None:
        """major_win_event.enabled=True but is_major_win=False → not eligible."""
        configs = (
            # Enabled but not major win.
            make_initiative(
                initiative_id="rt-1",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=False,
                ),
            ),
            # Not enabled at all.
            make_initiative(
                initiative_id="rt-2",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=False,
                    is_major_win=False,
                ),
            ),
        )
        result = compute_right_tail_false_stop_profile(
            stop_events=[],
            completion_events=[],
            initiative_configs=configs,
        )
        assert result.right_tail_eligible_count == 0
        assert result.right_tail_false_stop_rate is None

    def test_frozen(self) -> None:
        """RightTailFalseStopProfile is frozen."""
        profile = RightTailFalseStopProfile(
            right_tail_eligible_count=1,
            right_tail_stopped_eligible_count=0,
            right_tail_completions=1,
            right_tail_stops=0,
            right_tail_false_stop_rate=0.0,
            belief_at_stop_for_stopped_eligible=(),
        )
        with pytest.raises(AttributeError):
            profile.right_tail_eligible_count = 5  # type: ignore[misc]

    def test_profile_wired_through_assemble(self) -> None:
        """RightTailFalseStopProfile is populated in assembled RunResult."""
        configs_tuple = (
            make_initiative(
                initiative_id="rt-1",
                generation_tag="right_tail",
                value_channels=make_value_channels(
                    major_win_enabled=True,
                    is_major_win=True,
                ),
            ),
        )
        config = make_simulation_config(initiatives=configs_tuple)
        init_configs = config.initiatives
        assert init_configs is not None

        final_ws = WorldState(
            tick=1,
            initiative_states=(
                InitiativeState(
                    initiative_id="rt-1",
                    lifecycle_state=LifecycleState.STOPPED,
                    assigned_team_id=None,
                    quality_belief_t=0.3,
                    execution_belief_t=None,
                    executive_attention_t=0.0,
                    staffed_tick_count=1,
                    ticks_since_assignment=1,
                    age_ticks=1,
                    cumulative_value_realized=0.0,
                    cumulative_lump_value_realized=0.0,
                    cumulative_residual_value_realized=0.0,
                    cumulative_labor_invested=1.0,
                    cumulative_attention_invested=0.5,
                    belief_history=(0.3,),
                    review_count=1,
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

        manifest = RunManifest(
            policy_id="balanced",
            world_seed=42,
            is_replay=False,
            resolved_configuration=config,
            resolved_initiatives=init_configs,
            baseline_spec_version="0.1.0",
        )

        collector = RunCollector()
        collector.stop_events.append(
            StopEvent(
                tick=0,
                initiative_id="rt-1",
                quality_belief_t=0.3,
                execution_belief_t=None,
                latent_quality=0.8,
                triggering_rule="confidence_decline",
                cumulative_labor_invested=1.0,
                staffed_ticks=1,
                governance_archetype="balanced",
            )
        )

        result = assemble_run_result(
            collector=collector,
            config=config,
            initiative_configs=init_configs,
            final_world_state=final_ws,
            manifest=manifest,
        )

        profile = result.right_tail_false_stop_profile
        assert profile.right_tail_eligible_count == 1
        assert profile.right_tail_stopped_eligible_count == 1
        assert profile.right_tail_false_stop_rate == pytest.approx(1.0)
        assert profile.right_tail_stops == 1
        assert profile.belief_at_stop_for_stopped_eligible == (pytest.approx(0.3),)
