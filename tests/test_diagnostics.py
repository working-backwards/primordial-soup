"""Tests for ground-truth diagnostic metrics.

Tests use synthetic RunResult data to verify each diagnostic function
independently. No simulation runs are needed — the tests construct
minimal RunResult instances with known event logs and manifest data.

Per plan §A.2.2.
"""

from __future__ import annotations

import pytest

from primordial_soup.config import ResolvedInitiativeConfig
from primordial_soup.diagnostics import (
    compute_attention_conditioned_false_negatives,
    compute_belief_at_stop,
    compute_false_stop_rate,
    compute_stop_hazard,
    compute_survival_curves,
    is_major_win_eligible,
    is_right_tail,
)
from primordial_soup.events import MajorWinEvent, StopEvent
from primordial_soup.reporting import (
    BeliefAccuracy,
    ExplorationCostProfile,
    FamilyTimingProfile,
    IdleCapacityProfile,
    MajorWinProfile,
    ReassignmentProfile,
    RightTailFalseStopProfile,
    RunManifest,
    RunResult,
    ValueByChannel,
)
from primordial_soup.types import (
    CompletionLumpChannel,
    MajorWinEventChannel,
    ResidualChannel,
    ValueChannels,
)

# ===========================================================================
# Test fixtures — synthetic data builders
# ===========================================================================


def _make_value_channels(
    *,
    major_win_enabled: bool = False,
    is_major_win: bool = False,
) -> ValueChannels:
    """Build a minimal ValueChannels for testing."""
    return ValueChannels(
        completion_lump=CompletionLumpChannel(enabled=False),
        residual=ResidualChannel(enabled=False),
        major_win_event=MajorWinEventChannel(
            enabled=major_win_enabled,
            is_major_win=is_major_win,
        ),
    )


def _make_config(
    initiative_id: str,
    *,
    generation_tag: str = "right_tail",
    latent_quality: float = 0.5,
    major_win_enabled: bool = True,
    is_major_win: bool = False,
) -> ResolvedInitiativeConfig:
    """Build a minimal ResolvedInitiativeConfig for testing."""
    return ResolvedInitiativeConfig(
        initiative_id=initiative_id,
        latent_quality=latent_quality,
        dependency_level=0.3,
        base_signal_st_dev=0.15,
        generation_tag=generation_tag,
        value_channels=_make_value_channels(
            major_win_enabled=major_win_enabled,
            is_major_win=is_major_win,
        ),
    )


def _make_stop_event(
    initiative_id: str,
    *,
    tick: int = 100,
    quality_belief_t: float = 0.3,
    latent_quality: float = 0.5,
    staffed_ticks: int = 50,
    cumulative_labor_invested: float = 50.0,
) -> StopEvent:
    """Build a minimal StopEvent for testing."""
    return StopEvent(
        tick=tick,
        initiative_id=initiative_id,
        quality_belief_t=quality_belief_t,
        execution_belief_t=0.8,
        latent_quality=latent_quality,
        triggering_rule="confidence_decline",
        cumulative_labor_invested=cumulative_labor_invested,
        staffed_ticks=staffed_ticks,
        governance_archetype="balanced",
    )


def _make_major_win_event(
    initiative_id: str,
    *,
    tick: int = 200,
    latent_quality: float = 0.9,
    cumulative_labor_invested: float = 100.0,
    cumulative_attention_invested: float = 80.0,
) -> MajorWinEvent:
    """Build a minimal MajorWinEvent for testing."""
    return MajorWinEvent(
        initiative_id=initiative_id,
        tick=tick,
        latent_quality=latent_quality,
        observable_ceiling=50.0,
        quality_belief_at_completion=0.85,
        execution_belief_at_completion=None,
        cumulative_labor_invested=cumulative_labor_invested,
        cumulative_attention_invested=cumulative_attention_invested,
        staffed_tick_count=10,
        observed_history_snapshot=(0.5, 0.6, 0.7, 0.8, 0.85),
    )


def _make_run_result(
    configs: tuple[ResolvedInitiativeConfig, ...],
    *,
    stop_events: tuple[StopEvent, ...] = (),
    major_win_events: tuple[MajorWinEvent, ...] = (),
) -> RunResult:
    """Build a minimal RunResult for diagnostic testing.

    Most fields are zeroed/empty — only the fields needed by
    diagnostics are populated.
    """
    manifest = RunManifest(
        policy_id="balanced",
        world_seed=42,
        is_replay=False,
        resolved_configuration=None,  # type: ignore[arg-type]
        resolved_initiatives=configs,
        engine_version="test",
    )

    return RunResult(
        cumulative_value_total=0.0,
        value_by_channel=ValueByChannel(
            completion_lump_value=0.0,
            residual_value=0.0,
            residual_value_by_label={},
        ),
        major_win_profile=MajorWinProfile(
            major_win_count=len(major_win_events),
            time_to_major_win=(),
            major_win_count_by_label={},
            labor_per_major_win=None,
        ),
        belief_accuracy=BeliefAccuracy(
            mean_absolute_belief_error=0.0,
            mean_squared_belief_error=0.0,
        ),
        terminal_capability_t=1.0,
        max_portfolio_capability_t=1.0,
        terminal_aggregate_residual_rate=0.0,
        idle_capacity_profile=IdleCapacityProfile(
            cumulative_idle_team_ticks=0,
            idle_team_tick_fraction=0.0,
            pool_exhaustion_tick=None,
        ),
        exploration_cost_profile=ExplorationCostProfile(
            cumulative_labor_in_stopped_initiatives=0.0,
            cumulative_attention_in_stopped_initiatives=0.0,
            stopped_initiative_count_by_label={},
            cumulative_labor_in_stopped_by_label={},
            cumulative_attention_in_stopped_by_label={},
            latent_quality_distribution_of_stopped=(),
            cumulative_labor_in_completed_initiatives=0.0,
            cumulative_attention_in_completed_initiatives=0.0,
            completed_initiative_count_by_label={},
            cumulative_labor_in_completed_by_label={},
            cumulative_attention_in_completed_by_label={},
        ),
        right_tail_false_stop_profile=RightTailFalseStopProfile(
            right_tail_eligible_count=0,
            right_tail_stopped_eligible_count=0,
            right_tail_completions=0,
            right_tail_stops=0,
            right_tail_false_stop_rate=None,
            belief_at_stop_for_stopped_eligible=(),
        ),
        reassignment_profile=ReassignmentProfile(
            reassignment_event_count=0,
            reassignment_event_log=None,
        ),
        cumulative_ramp_labor=0.0,
        ramp_labor_fraction=0.0,
        value_by_family={},
        family_timing=FamilyTimingProfile(
            first_completion_tick_by_family={},
            mean_completion_tick_by_family={},
            completion_ticks_by_family={},
            peak_capability_tick=0,
            first_right_tail_stop_tick=None,
        ),
        frontier_summary=None,
        attention_feasibility_violation_count=0,
        major_win_event_log=major_win_events if major_win_events else None,
        stop_event_log=stop_events if stop_events else None,
        per_initiative_tick_records=None,
        portfolio_tick_records=None,
        manifest=manifest,
    )


# ===========================================================================
# Helper function tests
# ===========================================================================


class TestHelpers:
    """Tests for helper functions."""

    def test_is_right_tail_true(self) -> None:
        cfg = _make_config("rt-1", generation_tag="right_tail")
        assert is_right_tail(cfg) is True

    def test_is_right_tail_false_for_other_types(self) -> None:
        cfg = _make_config("fw-1", generation_tag="flywheel")
        assert is_right_tail(cfg) is False

    def test_is_major_win_eligible_true(self) -> None:
        cfg = _make_config("rt-1", major_win_enabled=True, is_major_win=True)
        assert is_major_win_eligible(cfg) is True

    def test_is_major_win_eligible_false_when_not_major_win(self) -> None:
        cfg = _make_config("rt-1", major_win_enabled=True, is_major_win=False)
        assert is_major_win_eligible(cfg) is False

    def test_is_major_win_eligible_false_when_not_enabled(self) -> None:
        cfg = _make_config("rt-1", major_win_enabled=False, is_major_win=True)
        assert is_major_win_eligible(cfg) is False


# ===========================================================================
# Metric 1: False-stop rate
# ===========================================================================


class TestFalseStopRate:
    """Tests for compute_false_stop_rate."""

    def test_no_eligible_initiatives(self) -> None:
        """When no major-win-eligible exist, rate is None."""
        configs = (
            _make_config("rt-1", is_major_win=False),
            _make_config("rt-2", is_major_win=False),
        )
        result = _make_run_result(configs)
        fsr = compute_false_stop_rate(result)
        assert fsr.total_major_win_eligible == 0
        assert fsr.false_stop_rate is None

    def test_all_eligible_stopped(self) -> None:
        """When all eligible are stopped, rate is 1.0."""
        configs = (
            _make_config("rt-1", is_major_win=True),
            _make_config("rt-2", is_major_win=True),
        )
        stops = (
            _make_stop_event("rt-1"),
            _make_stop_event("rt-2"),
        )
        result = _make_run_result(configs, stop_events=stops)
        fsr = compute_false_stop_rate(result)
        assert fsr.total_major_win_eligible == 2
        assert fsr.stopped_major_win_eligible == 2
        assert fsr.completed_major_win_eligible == 0
        assert fsr.false_stop_rate == pytest.approx(1.0)

    def test_none_eligible_stopped(self) -> None:
        """When no eligible are stopped (all complete), rate is 0.0."""
        configs = (_make_config("rt-1", is_major_win=True),)
        mw_events = (_make_major_win_event("rt-1"),)
        result = _make_run_result(configs, major_win_events=mw_events)
        fsr = compute_false_stop_rate(result)
        assert fsr.total_major_win_eligible == 1
        assert fsr.stopped_major_win_eligible == 0
        assert fsr.completed_major_win_eligible == 1
        assert fsr.false_stop_rate == pytest.approx(0.0)

    def test_mixed_stopped_and_completed(self) -> None:
        """Partial stops: 1 of 3 stopped → rate = 1/3."""
        configs = (
            _make_config("rt-1", is_major_win=True),
            _make_config("rt-2", is_major_win=True),
            _make_config("rt-3", is_major_win=True),
        )
        stops = (_make_stop_event("rt-1"),)
        mw_events = (
            _make_major_win_event("rt-2"),
            _make_major_win_event("rt-3"),
        )
        result = _make_run_result(configs, stop_events=stops, major_win_events=mw_events)
        fsr = compute_false_stop_rate(result)
        assert fsr.total_major_win_eligible == 3
        assert fsr.stopped_major_win_eligible == 1
        assert fsr.completed_major_win_eligible == 2
        assert fsr.false_stop_rate == pytest.approx(1.0 / 3.0)

    def test_non_rt_stops_ignored(self) -> None:
        """Stops of non-RT initiatives don't count."""
        configs = (
            _make_config("rt-1", is_major_win=True),
            _make_config("fw-1", generation_tag="flywheel", major_win_enabled=False),
        )
        stops = (_make_stop_event("fw-1"),)  # Flywheel stop.
        result = _make_run_result(configs, stop_events=stops)
        fsr = compute_false_stop_rate(result)
        assert fsr.total_major_win_eligible == 1
        assert fsr.stopped_major_win_eligible == 0


# ===========================================================================
# Metric 2: Survival curves
# ===========================================================================


class TestSurvivalCurves:
    """Tests for compute_survival_curves."""

    def test_no_rt_initiatives(self) -> None:
        """When no RT initiatives exist, curves are empty."""
        configs = (_make_config("fw-1", generation_tag="flywheel", major_win_enabled=False),)
        result = _make_run_result(configs)
        sc = compute_survival_curves(result)
        assert sc.all_rt_count == 0
        assert sc.eligible_count == 0
        assert sc.all_rt_curve == ((0, 1.0),)

    def test_all_rt_stopped(self) -> None:
        """When all RT are stopped, survival drops to 0."""
        configs = (
            _make_config("rt-1", is_major_win=False),
            _make_config("rt-2", is_major_win=False),
        )
        stops = (
            _make_stop_event("rt-1", staffed_ticks=10),
            _make_stop_event("rt-2", staffed_ticks=20),
        )
        result = _make_run_result(configs, stop_events=stops)
        sc = compute_survival_curves(result)
        assert sc.all_rt_count == 2
        # Curve should start at 1.0 and drop to 0.0.
        assert sc.all_rt_curve[0] == (0, 1.0)
        assert sc.all_rt_curve[-1][1] == pytest.approx(0.0)

    def test_survival_is_monotonically_nonincreasing(self) -> None:
        """Survival fractions are monotonically non-increasing."""
        configs = tuple(_make_config(f"rt-{i}", is_major_win=False) for i in range(5))
        stops = tuple(_make_stop_event(f"rt-{i}", staffed_ticks=i * 10) for i in range(5))
        result = _make_run_result(configs, stop_events=stops)
        sc = compute_survival_curves(result)
        fractions = [f for _, f in sc.all_rt_curve]
        for i in range(1, len(fractions)):
            assert fractions[i] <= fractions[i - 1]

    def test_eligible_curve_tracks_only_eligible(self) -> None:
        """Eligible curve tracks only major-win-eligible initiatives."""
        configs = (
            _make_config("rt-1", is_major_win=True),  # Eligible
            _make_config("rt-2", is_major_win=False),  # Not eligible
        )
        stops = (
            _make_stop_event("rt-1", staffed_ticks=10),
            _make_stop_event("rt-2", staffed_ticks=20),
        )
        result = _make_run_result(configs, stop_events=stops)
        sc = compute_survival_curves(result)
        # All RT curve: 2 at risk.
        assert sc.all_rt_count == 2
        # Eligible curve: 1 at risk.
        assert sc.eligible_count == 1


# ===========================================================================
# Metric 3: Belief-at-stop distribution
# ===========================================================================


class TestBeliefAtStop:
    """Tests for compute_belief_at_stop."""

    def test_no_eligible_stops(self) -> None:
        """When no eligible initiatives are stopped, result is empty."""
        configs = (_make_config("rt-1", is_major_win=False),)
        stops = (_make_stop_event("rt-1", quality_belief_t=0.3),)
        result = _make_run_result(configs, stop_events=stops)
        bas = compute_belief_at_stop(result)
        assert bas.count == 0
        assert bas.mean_belief is None
        assert bas.beliefs == ()

    def test_single_eligible_stop(self) -> None:
        """Single eligible stop returns correct belief."""
        configs = (_make_config("rt-1", is_major_win=True),)
        stops = (_make_stop_event("rt-1", quality_belief_t=0.35),)
        result = _make_run_result(configs, stop_events=stops)
        bas = compute_belief_at_stop(result)
        assert bas.count == 1
        assert bas.mean_belief == pytest.approx(0.35)
        assert bas.min_belief == pytest.approx(0.35)
        assert bas.max_belief == pytest.approx(0.35)

    def test_multiple_eligible_stops(self) -> None:
        """Multiple eligible stops: correct mean, min, max."""
        configs = (
            _make_config("rt-1", is_major_win=True),
            _make_config("rt-2", is_major_win=True),
            _make_config("rt-3", is_major_win=True),
        )
        stops = (
            _make_stop_event("rt-1", quality_belief_t=0.20),
            _make_stop_event("rt-2", quality_belief_t=0.40),
            _make_stop_event("rt-3", quality_belief_t=0.30),
        )
        result = _make_run_result(configs, stop_events=stops)
        bas = compute_belief_at_stop(result)
        assert bas.count == 3
        assert bas.mean_belief == pytest.approx(0.30)
        assert bas.min_belief == pytest.approx(0.20)
        assert bas.max_belief == pytest.approx(0.40)


# ===========================================================================
# Metric 4: Attention-conditioned false negatives
# ===========================================================================


class TestAttentionConditioned:
    """Tests for compute_attention_conditioned_false_negatives."""

    def test_empty_data(self) -> None:
        """No eligible initiatives → all buckets empty."""
        configs = (_make_config("rt-1", is_major_win=False),)
        result = _make_run_result(configs)
        acr = compute_attention_conditioned_false_negatives(result)
        assert all(r is None for r in acr.bucket_false_stop_rates)
        assert all(c == 0 for c in acr.bucket_counts)

    def test_single_stopped_eligible(self) -> None:
        """Single stopped eligible lands in correct attention bucket."""
        configs = (_make_config("rt-1", is_major_win=True),)
        # Mean attention = 50 labor / 50 staffed = 1.0 → last bucket.
        stops = (
            _make_stop_event(
                "rt-1",
                staffed_ticks=50,
                cumulative_labor_invested=50.0,
            ),
        )
        result = _make_run_result(configs, stop_events=stops)
        acr = compute_attention_conditioned_false_negatives(result, n_buckets=5)
        # Last bucket (0.8–1.0) should have the stop.
        assert acr.bucket_counts[-1] == 1
        assert acr.bucket_false_stop_rates[-1] == pytest.approx(1.0)

    def test_bucket_edges_correct(self) -> None:
        """Bucket edges span 0 to 1 with correct count."""
        configs = (_make_config("rt-1", is_major_win=False),)
        result = _make_run_result(configs)
        acr = compute_attention_conditioned_false_negatives(result, n_buckets=4)
        assert len(acr.bucket_edges) == 5  # 4 buckets → 5 edges.
        assert acr.bucket_edges[0] == pytest.approx(0.0)
        assert acr.bucket_edges[-1] == pytest.approx(1.0)


# ===========================================================================
# Metric 5: Stop hazard
# ===========================================================================


class TestStopHazard:
    """Tests for compute_stop_hazard."""

    def test_no_rt_stops(self) -> None:
        """When no RT stops exist, all bins are zero."""
        configs = (_make_config("fw-1", generation_tag="flywheel", major_win_enabled=False),)
        stops = (_make_stop_event("fw-1"),)
        result = _make_run_result(configs, stop_events=stops)
        sh = compute_stop_hazard(result, bin_width=20, max_tick=100)
        assert sh.total_stops == 0
        assert all(c == 0 for c in sh.stop_counts)

    def test_stops_in_correct_bins(self) -> None:
        """Stops at known staffed ticks land in correct bins."""
        configs = (
            _make_config("rt-1"),
            _make_config("rt-2"),
            _make_config("rt-3"),
        )
        stops = (
            _make_stop_event("rt-1", staffed_ticks=5),  # Bin 0 (0–19)
            _make_stop_event("rt-2", staffed_ticks=25),  # Bin 1 (20–39)
            _make_stop_event("rt-3", staffed_ticks=45),  # Bin 2 (40–59)
        )
        result = _make_run_result(configs, stop_events=stops)
        sh = compute_stop_hazard(result, bin_width=20, max_tick=100)
        assert sh.total_stops == 3
        assert sh.stop_counts[0] == 1
        assert sh.stop_counts[1] == 1
        assert sh.stop_counts[2] == 1

    def test_fractions_sum_to_one(self) -> None:
        """Bin fractions sum to 1.0 when there are stops."""
        configs = tuple(_make_config(f"rt-{i}") for i in range(10))
        stops = tuple(_make_stop_event(f"rt-{i}", staffed_ticks=i * 5) for i in range(10))
        result = _make_run_result(configs, stop_events=stops)
        sh = compute_stop_hazard(result, bin_width=10, max_tick=100)
        assert sum(sh.bin_fractions) == pytest.approx(1.0)

    def test_early_clustering_detection(self) -> None:
        """Detect when stops cluster in early bins."""
        configs = tuple(_make_config(f"rt-{i}") for i in range(6))
        # All stops in first bin (0–19 staffed ticks).
        stops = tuple(_make_stop_event(f"rt-{i}", staffed_ticks=i + 1) for i in range(6))
        result = _make_run_result(configs, stop_events=stops)
        sh = compute_stop_hazard(result, bin_width=20, max_tick=100)
        # All stops should be in the first bin.
        assert sh.stop_counts[0] == 6
        assert sh.bin_fractions[0] == pytest.approx(1.0)


# ===========================================================================
# Integration test with live simulation
# ===========================================================================


class TestDiagnosticsWithSimulation:
    """End-to-end test: run a simulation and compute diagnostics."""

    def test_diagnostics_computable_from_balanced_run(self) -> None:
        """All five diagnostics can be computed from a real Balanced run.

        This is a smoke test — it verifies that the diagnostic functions
        accept real RunResult data without errors.
        """
        from primordial_soup.policy import BalancedPolicy
        from primordial_soup.presets import make_balanced_config
        from primordial_soup.runner import run_single_regime

        config = make_balanced_config(world_seed=42)
        policy = BalancedPolicy()
        result, _ = run_single_regime(config, policy)

        # All five metrics should compute without error.
        fsr = compute_false_stop_rate(result)
        assert fsr.total_major_win_eligible >= 0

        sc = compute_survival_curves(result)
        assert len(sc.all_rt_curve) >= 1

        bas = compute_belief_at_stop(result)
        assert bas.count >= 0

        acr = compute_attention_conditioned_false_negatives(result)
        assert len(acr.bucket_edges) > 0

        sh = compute_stop_hazard(result)
        assert sh.total_stops >= 0
