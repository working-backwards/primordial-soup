"""Tests for figures.py — figure generation and representative selection.

Smoke tests verify that each figure function:
1. Completes without error on valid data
2. Produces a non-empty PNG file
3. Handles empty/zero-count data gracefully

Selection tests verify that select_representative_initiatives():
1. Picks the correct initiative for each role based on the heuristics
2. Handles missing families gracefully
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 — pytest fixtures need Path at runtime

import pytest

from conftest import make_initiative, make_simulation_config
from primordial_soup.events import MajorWinEvent, StopEvent
from primordial_soup.figures import (
    generate_all_figures,
    plot_cumulative_value_by_year,
    plot_enabler_dashboard,
    plot_representative_timelines,
    plot_rt_survival_curves,
    plot_seed_distributions,
    plot_surfaced_major_wins_by_year,
    plot_terminal_capability,
    plot_tradeoff_frontier,
    plot_value_by_year_stacked,
    select_representative_initiatives,
)
from primordial_soup.reporting import RunCollector, RunManifest, assemble_run_result
from primordial_soup.run_bundle import (
    ExperimentalConditionRecord,
    ExperimentalConditionSpec,
    ExperimentSpec,
    InitiativeFinalState,
    SeedRunRecord,
    _create_bundle_directory,
    extract_initiative_final_states,
)
from primordial_soup.state import InitiativeState, TeamState, WorldState
from primordial_soup.tables import write_all_tables
from primordial_soup.types import LifecycleState

# ============================================================================
# Helpers — build minimal table data for figure tests
# ============================================================================


def _make_table_data() -> dict[str, list[dict]]:
    """Build minimal table data dict for figure smoke tests.

    Returns data matching what write_all_tables() produces: each key
    maps to a list of row dicts.
    """
    # Build a minimal experiment and run all tables.
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

    ws = WorldState(
        tick=10,
        initiative_states=(
            InitiativeState(
                initiative_id="init-0",
                lifecycle_state=LifecycleState.STOPPED,
                assigned_team_id=None,
                quality_belief_t=0.3,
                execution_belief_t=None,
                executive_attention_t=0.0,
                staffed_tick_count=5,
                ticks_since_assignment=5,
                age_ticks=10,
                cumulative_value_realized=2.0,
                cumulative_lump_value_realized=1.0,
                cumulative_residual_value_realized=1.0,
                cumulative_labor_invested=5.0,
                cumulative_attention_invested=1.5,
                belief_history=(0.3,),
                review_count=3,
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
            tick=5,
            initiative_id="init-0",
            quality_belief_t=0.3,
            execution_belief_t=None,
            latent_quality=0.8,
            triggering_rule="confidence_decline",
            cumulative_labor_invested=5.0,
            staffed_ticks=5,
            governance_archetype="balanced",
        )
    )

    run_result = assemble_run_result(
        collector=collector,
        config=config,
        initiative_configs=init_configs,
        final_world_state=ws,
        manifest=manifest,
    )

    final_states = extract_initiative_final_states(ws)

    seed_rec = SeedRunRecord(
        world_seed=42,
        run_result=run_result,
        initiative_final_states=final_states,
        initiative_configs=init_configs,
    )

    cond_spec = ExperimentalConditionSpec(
        experimental_condition_id="cond-1",
        environmental_conditions_id="balanced_incumbent",
        environmental_conditions_name="Balanced Incumbent",
        governance_architecture_id="default",
        governance_architecture_name="Default",
        operating_policy_id="balanced",
        operating_policy_name="Balanced",
        governance_regime_label="Balanced",
    )

    condition = ExperimentalConditionRecord(
        condition_spec=cond_spec,
        seed_run_records=(seed_rec,),
        simulation_config=config,
    )

    experiment = ExperimentSpec(
        experiment_name="test",
        title="Test",
        description="Test",
        world_seeds=(42,),
        condition_records=(condition,),
        script_name="test",
    )

    return experiment


# ============================================================================
# Smoke tests — each figure function produces a file
# ============================================================================


class TestFigureSmoke:
    """Smoke tests: each figure function produces a valid PNG file."""

    @pytest.fixture()
    def table_data(self, tmp_path: Path) -> dict[str, list[dict]]:
        """Generate table data for figure tests."""
        experiment = _make_table_data()
        bundle_path = tmp_path / "bundle"
        _create_bundle_directory(bundle_path)
        return write_all_tables(experiment, bundle_path)

    @pytest.fixture()
    def figures_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "figures"
        d.mkdir()
        return d

    def test_value_by_year_stacked(self, table_data, figures_dir) -> None:
        plot_value_by_year_stacked(table_data["yearly_timeseries"], figures_dir)
        assert (figures_dir / "value_by_year_stacked.png").exists()
        assert (figures_dir / "value_by_year_stacked.png").stat().st_size > 0

    def test_cumulative_value_by_year(self, table_data, figures_dir) -> None:
        plot_cumulative_value_by_year(
            table_data["yearly_timeseries"],
            table_data["experimental_conditions"],
            figures_dir,
        )
        assert (figures_dir / "cumulative_value_by_year.png").exists()

    def test_surfaced_major_wins_by_year(self, table_data, figures_dir) -> None:
        plot_surfaced_major_wins_by_year(
            table_data["yearly_timeseries"],
            table_data["experimental_conditions"],
            figures_dir,
        )
        assert (figures_dir / "surfaced_major_wins_by_year.png").exists()

    def test_tradeoff_frontier(self, table_data, figures_dir) -> None:
        plot_tradeoff_frontier(
            table_data["experimental_conditions"],
            figures_dir,
        )
        assert (figures_dir / "tradeoff_frontier.png").exists()

    def test_terminal_capability(self, table_data, figures_dir) -> None:
        plot_terminal_capability(
            table_data["experimental_conditions"],
            figures_dir,
        )
        assert (figures_dir / "terminal_capability.png").exists()

    def test_rt_survival_curves(self, table_data, figures_dir) -> None:
        plot_rt_survival_curves(
            table_data["experimental_conditions"],
            table_data["seed_runs"],
            figures_dir,
        )
        assert (figures_dir / "rt_survival_curves.png").exists()

    def test_enabler_dashboard(self, table_data, figures_dir) -> None:
        plot_enabler_dashboard(
            table_data["enabler_coupling"],
            table_data["experimental_conditions"],
            figures_dir,
        )
        assert (figures_dir / "enabler_dashboard.png").exists()

    def test_seed_distributions(self, table_data, figures_dir) -> None:
        plot_seed_distributions(table_data["seed_runs"], figures_dir)
        assert (figures_dir / "seed_distributions.png").exists()

    def test_representative_timelines(self, table_data, figures_dir) -> None:
        plot_representative_timelines(
            table_data["event_log"],
            table_data["representative_runs"],
            table_data["experimental_conditions"],
            figures_dir,
        )
        assert (figures_dir / "representative_timelines.png").exists()


class TestGenerateAllFigures:
    """Integration test for generate_all_figures()."""

    def test_all_figures_created(self, tmp_path: Path) -> None:
        """generate_all_figures() produces all expected PNG files."""
        experiment = _make_table_data()
        bundle_path = tmp_path / "bundle"
        _create_bundle_directory(bundle_path)
        table_data = write_all_tables(experiment, bundle_path)

        figures_dir = bundle_path / "figures"
        generate_all_figures(table_data, figures_dir)

        expected = [
            "value_by_year_stacked.png",
            "cumulative_value_by_year.png",
            "surfaced_major_wins_by_year.png",
            "tradeoff_frontier.png",
            "terminal_capability.png",
            "rt_survival_curves.png",
            "enabler_dashboard.png",
            "seed_distributions.png",
            "representative_timelines.png",
        ]
        for fname in expected:
            assert (figures_dir / fname).exists(), f"Missing: {fname}"


class TestEmptyDataHandling:
    """Figures handle empty data without crashing."""

    def test_empty_timeseries(self, tmp_path: Path) -> None:
        """Empty timeseries data doesn't crash."""
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()
        plot_value_by_year_stacked([], figures_dir)
        # No file produced (no data), but no crash.

    def test_empty_conditions(self, tmp_path: Path) -> None:
        """Empty condition data doesn't crash."""
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()
        plot_tradeoff_frontier([], figures_dir)
        plot_terminal_capability([], figures_dir)


# ============================================================================
# select_representative_initiatives tests
# ============================================================================


def _make_final_state(
    initiative_id: str,
    lifecycle_state: str = "active",
    completed_tick: int | None = None,
    **kwargs: object,
) -> InitiativeFinalState:
    """Build a minimal InitiativeFinalState for selection tests."""
    defaults = dict(
        initiative_id=initiative_id,
        lifecycle_state=lifecycle_state,
        quality_belief_t=0.5,
        execution_belief_t=None,
        staffed_tick_count=10,
        cumulative_labor_invested=10.0,
        cumulative_value_realized=0.0,
        cumulative_lump_value_realized=0.0,
        cumulative_residual_value_realized=0.0,
        cumulative_attention_invested=1.0,
        residual_activated=False,
        residual_activation_tick=None,
        completed_tick=completed_tick,
        major_win_surfaced=False,
        major_win_tick=None,
    )
    defaults.update(kwargs)
    return InitiativeFinalState(**defaults)  # type: ignore[arg-type]


def _make_seed_run_record(
    configs: tuple,
    final_states: tuple,
    stop_events: tuple | None = None,
    major_win_events: tuple | None = None,
) -> SeedRunRecord:
    """Build a SeedRunRecord with a minimal RunResult for selection tests.

    Uses a real simulation run under the hood to get a valid RunResult,
    then replaces the initiative_configs and initiative_final_states
    with the test-specific data.
    """
    # Build a real but minimal RunResult by running a single-tick sim.
    config = make_simulation_config(
        initiatives=(make_initiative(initiative_id="placeholder-0", generation_tag="flywheel"),),
    )
    init_configs = config.initiatives
    assert init_configs is not None

    ws = WorldState(
        tick=1,
        initiative_states=(
            InitiativeState(
                initiative_id="placeholder-0",
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
        team_states=(TeamState(team_id="team-0", team_size=5, assigned_initiative_id=None),),
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
    if stop_events:
        collector.stop_events.extend(stop_events)
    if major_win_events:
        collector.major_win_events.extend(major_win_events)

    run_result = assemble_run_result(
        collector=collector,
        config=config,
        initiative_configs=init_configs,
        final_world_state=ws,
        manifest=manifest,
    )

    return SeedRunRecord(
        world_seed=42,
        run_result=run_result,
        initiative_final_states=final_states,
        initiative_configs=configs,
    )


class TestSelectRepresentativeInitiatives:
    """Tests for select_representative_initiatives() selection heuristics."""

    def test_selects_one_from_each_family(self) -> None:
        """With all families present, returns all 5 role keys."""
        configs = (
            make_initiative(initiative_id="fw-1", generation_tag="flywheel", latent_quality=0.65),
            make_initiative(initiative_id="rt-1", generation_tag="right_tail", latent_quality=0.9),
            make_initiative(initiative_id="rt-2", generation_tag="right_tail", latent_quality=0.1),
            make_initiative(initiative_id="en-1", generation_tag="enabler", latent_quality=0.5),
            make_initiative(initiative_id="qw-1", generation_tag="quick_win", latent_quality=0.7),
        )
        finals = (
            _make_final_state("fw-1", lifecycle_state="completed", completed_tick=100),
            _make_final_state("rt-1", lifecycle_state="completed", completed_tick=200),
            _make_final_state("rt-2", lifecycle_state="stopped"),
            _make_final_state("en-1", lifecycle_state="completed", completed_tick=50),
            _make_final_state("qw-1", lifecycle_state="completed", completed_tick=20),
        )

        record = _make_seed_run_record(configs, finals)
        selected = select_representative_initiatives(record)

        assert set(selected.keys()) == {
            "flywheel_completed",
            "right_tail_high_q",
            "right_tail_stopped",
            "enabler",
            "quick_win",
        }

    def test_prefers_major_win_winner_for_right_tail_high_q(self) -> None:
        """A right-tail that surfaced a major win is preferred over a higher-q one."""
        configs = (
            make_initiative(
                initiative_id="rt-winner", generation_tag="right_tail", latent_quality=0.8
            ),
            make_initiative(
                initiative_id="rt-higher-q", generation_tag="right_tail", latent_quality=0.95
            ),
        )
        finals = (
            _make_final_state(
                "rt-winner",
                lifecycle_state="completed",
                completed_tick=200,
                major_win_surfaced=True,
                major_win_tick=200,
            ),
            _make_final_state("rt-higher-q", lifecycle_state="completed", completed_tick=250),
        )

        major_win = MajorWinEvent(
            initiative_id="rt-winner",
            tick=200,
            latent_quality=0.8,
            observable_ceiling=50.0,
            quality_belief_at_completion=0.75,
            execution_belief_at_completion=None,
            cumulative_labor_invested=100.0,
            cumulative_attention_invested=5.0,
            staffed_tick_count=100,
            observed_history_snapshot=(0.75,),
        )

        record = _make_seed_run_record(configs, finals, major_win_events=(major_win,))
        selected = select_representative_initiatives(record)

        # The major-win winner should be selected, not the higher-q non-winner.
        assert selected["right_tail_high_q"] == "rt-winner"

    def test_falls_back_to_highest_q_completed_when_no_major_wins(self) -> None:
        """Without major wins, picks the highest-quality completed right-tail."""
        configs = (
            make_initiative(
                initiative_id="rt-high", generation_tag="right_tail", latent_quality=0.9
            ),
            make_initiative(
                initiative_id="rt-med", generation_tag="right_tail", latent_quality=0.6
            ),
            make_initiative(
                initiative_id="rt-low", generation_tag="right_tail", latent_quality=0.2
            ),
        )
        finals = (
            _make_final_state("rt-high", lifecycle_state="completed", completed_tick=200),
            _make_final_state("rt-med", lifecycle_state="completed", completed_tick=180),
            _make_final_state("rt-low", lifecycle_state="stopped"),
        )

        record = _make_seed_run_record(configs, finals)
        selected = select_representative_initiatives(record)

        assert selected["right_tail_high_q"] == "rt-high"

    def test_picks_lowest_q_stopped_for_right_tail_stopped(self) -> None:
        """Picks the lowest-quality stopped right-tail, excluding the high-q selection."""
        configs = (
            make_initiative(
                initiative_id="rt-good", generation_tag="right_tail", latent_quality=0.85
            ),
            make_initiative(
                initiative_id="rt-bad", generation_tag="right_tail", latent_quality=0.05
            ),
            make_initiative(
                initiative_id="rt-worse", generation_tag="right_tail", latent_quality=0.01
            ),
        )
        finals = (
            _make_final_state("rt-good", lifecycle_state="completed", completed_tick=200),
            _make_final_state("rt-bad", lifecycle_state="stopped"),
            _make_final_state("rt-worse", lifecycle_state="stopped"),
        )

        record = _make_seed_run_record(configs, finals)
        selected = select_representative_initiatives(record)

        # rt-good is selected as right_tail_high_q.
        assert selected["right_tail_high_q"] == "rt-good"
        # The lowest-q stopped should be rt-worse (0.01), not rt-bad (0.05).
        assert selected["right_tail_stopped"] == "rt-worse"

    def test_picks_flywheel_closest_to_median_quality(self) -> None:
        """Picks the flywheel closest to q=0.65, not the highest or first."""
        configs = (
            make_initiative(
                initiative_id="fw-high", generation_tag="flywheel", latent_quality=0.95
            ),
            make_initiative(
                initiative_id="fw-mid", generation_tag="flywheel", latent_quality=0.64
            ),
            make_initiative(initiative_id="fw-low", generation_tag="flywheel", latent_quality=0.3),
        )
        finals = (
            _make_final_state("fw-high", lifecycle_state="completed", completed_tick=100),
            _make_final_state("fw-mid", lifecycle_state="completed", completed_tick=120),
            _make_final_state("fw-low", lifecycle_state="completed", completed_tick=150),
        )

        record = _make_seed_run_record(configs, finals)
        selected = select_representative_initiatives(record)

        # fw-mid (q=0.64) is closest to 0.65.
        assert selected["flywheel_completed"] == "fw-mid"

    def test_handles_missing_families_gracefully(self) -> None:
        """A pool with no enablers returns 4 keys, no error."""
        configs = (
            make_initiative(initiative_id="fw-1", generation_tag="flywheel", latent_quality=0.65),
            make_initiative(initiative_id="rt-1", generation_tag="right_tail", latent_quality=0.9),
            make_initiative(initiative_id="rt-2", generation_tag="right_tail", latent_quality=0.1),
            make_initiative(initiative_id="qw-1", generation_tag="quick_win", latent_quality=0.7),
        )
        finals = (
            _make_final_state("fw-1", lifecycle_state="completed", completed_tick=100),
            _make_final_state("rt-1", lifecycle_state="completed", completed_tick=200),
            _make_final_state("rt-2", lifecycle_state="stopped"),
            _make_final_state("qw-1", lifecycle_state="completed", completed_tick=20),
        )

        record = _make_seed_run_record(configs, finals)
        selected = select_representative_initiatives(record)

        # No enabler in pool → no "enabler" key, but no error.
        assert "enabler" not in selected
        assert "flywheel_completed" in selected
        assert "right_tail_high_q" in selected
        assert "right_tail_stopped" in selected
        assert "quick_win" in selected
