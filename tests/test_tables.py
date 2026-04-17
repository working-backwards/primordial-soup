"""Tests for tables.py — canonical and derived Parquet table generation.

Tests verify:
    - Each table writer produces a valid Parquet file
    - Required columns are present
    - Row counts match expectations
    - Values are traceable to source RunResult fields
    - Zero-count families produce zero-valued rows, not missing rows
    - Null handling is correct (e.g., false_stop_rate null when eligible=0)
    - Derived tables aggregate correctly from canonical tables
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 — pytest fixtures need Path at runtime
from typing import TYPE_CHECKING

import pyarrow.parquet as pq
import pytest

from conftest import make_initiative, make_simulation_config, make_value_channels
from primordial_soup.events import StopEvent
from primordial_soup.reporting import RunCollector, RunManifest, assemble_run_result
from primordial_soup.run_bundle import (
    ExperimentalConditionRecord,
    ExperimentalConditionSpec,
    ExperimentSpec,
    SeedRunRecord,
    extract_initiative_final_states,
)
from primordial_soup.state import InitiativeState, TeamState, WorldState
from primordial_soup.tables import (
    CANONICAL_FAMILIES,
    _compute_residual_value_for_bin,
    write_all_tables,
    write_event_log,
    write_experimental_conditions,
    write_family_outcomes,
    write_initiative_outcomes,
    write_pairwise_deltas,
    write_seed_runs,
    write_yearly_timeseries,
)
from primordial_soup.types import LifecycleState

if TYPE_CHECKING:
    from primordial_soup.config import SimulationConfiguration

# ============================================================================
# Test helpers
# ============================================================================


def _make_condition_spec(
    condition_id: str = "cond-1",
    env_name: str = "balanced_incumbent",
    regime_label: str = "Balanced",
    policy_id: str = "balanced",
) -> ExperimentalConditionSpec:
    return ExperimentalConditionSpec(
        experimental_condition_id=condition_id,
        environmental_conditions_id=env_name,
        environmental_conditions_name=env_name,
        governance_architecture_id="default",
        governance_architecture_name="Default",
        operating_policy_id=policy_id,
        operating_policy_name=regime_label,
        governance_regime_label=regime_label,
    )


def _make_seed_run(
    seed: int = 42,
    generation_tag: str = "flywheel",
    lifecycle: LifecycleState = LifecycleState.STOPPED,
    quality_belief: float = 0.3,
    major_win_enabled: bool = False,
    is_major_win: bool = False,
) -> tuple[SeedRunRecord, SimulationConfiguration]:
    """Build a seed run record with one initiative."""

    config = make_simulation_config(
        world_seed=seed,
        initiatives=(
            make_initiative(
                initiative_id="init-0",
                generation_tag=generation_tag,
                latent_quality=0.8,
                value_channels=make_value_channels(
                    major_win_enabled=major_win_enabled,
                    is_major_win=is_major_win,
                ),
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
                lifecycle_state=lifecycle,
                assigned_team_id=None,
                quality_belief_t=quality_belief,
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
                belief_history=(quality_belief,),
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

    final_states = extract_initiative_final_states(ws)

    manifest = RunManifest(
        policy_id="balanced",
        world_seed=seed,
        is_replay=False,
        resolved_configuration=config,
        resolved_initiatives=init_configs,
        baseline_spec_version="0.1.0",
    )

    collector = RunCollector()
    if lifecycle == LifecycleState.STOPPED:
        collector.stop_events.append(
            StopEvent(
                tick=5,
                initiative_id="init-0",
                quality_belief_t=quality_belief,
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

    record = SeedRunRecord(
        world_seed=seed,
        run_result=run_result,
        initiative_final_states=final_states,
        initiative_configs=init_configs,
    )
    return record, config


def _make_experiment_spec(
    seeds: tuple[int, ...] = (42, 43),
    n_conditions: int = 1,
) -> ExperimentSpec:
    """Build a minimal ExperimentSpec with n_conditions conditions."""
    conditions: list[ExperimentalConditionRecord] = []
    for i in range(n_conditions):
        seed_runs = []
        config = None
        for s in seeds:
            rec, cfg = _make_seed_run(seed=s)
            seed_runs.append(rec)
            config = cfg

        assert config is not None
        cond_id = f"cond-{i}" if n_conditions > 1 else "cond-1"
        label = "Balanced" if i == 0 else f"Regime-{i}"
        conditions.append(
            ExperimentalConditionRecord(
                condition_spec=_make_condition_spec(
                    condition_id=cond_id,
                    regime_label=label,
                ),
                seed_run_records=tuple(seed_runs),
                simulation_config=config,
            )
        )

    return ExperimentSpec(
        experiment_name="test_experiment",
        title="Test Experiment",
        description="Test",
        world_seeds=seeds,
        condition_records=tuple(conditions),
        script_name="test",
    )


# ============================================================================
# seed_runs.parquet
# ============================================================================


class TestWriteSeedRuns:
    """Tests for write_seed_runs()."""

    def test_correct_row_count(self, tmp_path: Path) -> None:
        """One row per seed × condition."""
        spec = _make_experiment_spec(seeds=(42, 43))
        rows = write_seed_runs(spec, tmp_path)
        assert len(rows) == 2

    def test_required_columns(self, tmp_path: Path) -> None:
        """All required columns present in written Parquet."""
        spec = _make_experiment_spec(seeds=(42,))
        write_seed_runs(spec, tmp_path)

        table = pq.read_table(str(tmp_path / "outputs" / "seed_runs.parquet"))
        required = [
            "run_bundle_id",
            "experiment_name",
            "experimental_condition_id",
            "seed_run_id",
            "world_seed",
            "total_value",
            "surfaced_major_wins",
            "terminal_capability",
            "right_tail_completions",
            "right_tail_stops",
            "right_tail_eligible_count",
            "right_tail_stopped_eligible_count",
            "right_tail_false_stop_rate",
            "idle_pct",
            "free_teams_mean",
            "peak_capacity",
            "first_completion_tick_any",
            "first_right_tail_completion_tick",
            "first_right_tail_stop_tick",
            "status",
            "completed_ticks",
            "horizon_ticks",
        ]
        column_names = set(table.column_names)
        for col in required:
            assert col in column_names, f"Missing column: {col}"

    def test_values_traceable(self, tmp_path: Path) -> None:
        """Key values match RunResult fields."""
        spec = _make_experiment_spec(seeds=(42,))
        rows = write_seed_runs(spec, tmp_path)

        result = spec.condition_records[0].seed_run_records[0].run_result
        row = rows[0]
        assert row["total_value"] == pytest.approx(result.cumulative_value_total)
        assert row["terminal_capability"] == pytest.approx(result.terminal_capability_t)
        assert row["surfaced_major_wins"] == result.major_win_profile.major_win_count


# ============================================================================
# experimental_conditions.parquet
# ============================================================================


class TestWriteExperimentalConditions:
    """Tests for write_experimental_conditions()."""

    def test_one_row_per_condition(self, tmp_path: Path) -> None:
        spec = _make_experiment_spec(seeds=(42, 43), n_conditions=2)
        seed_rows = write_seed_runs(spec, tmp_path)
        cond_rows = write_experimental_conditions(spec, seed_rows, tmp_path)
        assert len(cond_rows) == 2

    def test_seed_count_matches(self, tmp_path: Path) -> None:
        spec = _make_experiment_spec(seeds=(42, 43, 44))
        seed_rows = write_seed_runs(spec, tmp_path)
        cond_rows = write_experimental_conditions(spec, seed_rows, tmp_path)
        assert cond_rows[0]["seed_count"] == 3


# ============================================================================
# family_outcomes.parquet
# ============================================================================


class TestWriteFamilyOutcomes:
    """Tests for write_family_outcomes()."""

    def test_canonical_families_present(self, tmp_path: Path) -> None:
        """All four canonical families appear even with zero initiatives."""
        spec = _make_experiment_spec(seeds=(42,))
        rows = write_family_outcomes(spec, tmp_path)

        # Filter seed-level rows.
        seed_rows = [r for r in rows if r["aggregation_level"] == "seed_run"]
        family_keys = {r["grouping_key"] for r in seed_rows}
        for family in CANONICAL_FAMILIES:
            assert family in family_keys, f"Missing family: {family}"

    def test_zero_count_families_have_zero_values(self, tmp_path: Path) -> None:
        """Families with no initiatives have zero counts, not missing rows."""
        spec = _make_experiment_spec(seeds=(42,))
        rows = write_family_outcomes(spec, tmp_path)

        seed_rows = [r for r in rows if r["aggregation_level"] == "seed_run"]
        # Our test data has only flywheel initiatives.
        rt_rows = [r for r in seed_rows if r["grouping_key"] == "right_tail"]
        assert len(rt_rows) == 1
        assert rt_rows[0]["initiative_count"] == 0
        assert rt_rows[0]["completed_count"] == 0

    def test_condition_level_rows_present(self, tmp_path: Path) -> None:
        """Condition-level aggregated rows are included."""
        spec = _make_experiment_spec(seeds=(42, 43))
        rows = write_family_outcomes(spec, tmp_path)

        cond_rows = [r for r in rows if r["aggregation_level"] == "experimental_condition"]
        assert len(cond_rows) > 0


# ============================================================================
# yearly_timeseries.parquet
# ============================================================================


class TestWriteYearlyTimeseries:
    """Tests for write_yearly_timeseries()."""

    def test_produces_rows(self, tmp_path: Path) -> None:
        """Timeseries produces at least one row per bin."""
        spec = _make_experiment_spec(seeds=(42,))
        rows = write_yearly_timeseries(spec, tmp_path)
        assert len(rows) > 0

    def test_overall_rows_present(self, tmp_path: Path) -> None:
        """Overall (all families) rows are included."""
        spec = _make_experiment_spec(seeds=(42,))
        rows = write_yearly_timeseries(spec, tmp_path)
        overall = [r for r in rows if r["grouping_key"] == "all"]
        assert len(overall) > 0

    def test_cumulative_non_decreasing(self, tmp_path: Path) -> None:
        """Cumulative value is non-decreasing across bins."""
        spec = _make_experiment_spec(seeds=(42,))
        rows = write_yearly_timeseries(spec, tmp_path)
        overall = sorted(
            [r for r in rows if r["grouping_key"] == "all"],
            key=lambda r: r["time_bin_index"],
        )
        for i in range(1, len(overall)):
            assert (
                overall[i]["value_total_cumulative"]
                >= overall[i - 1]["value_total_cumulative"] - 1e-10
            )


# ============================================================================
# initiative_outcomes.parquet
# ============================================================================


class TestWriteInitiativeOutcomes:
    """Tests for write_initiative_outcomes()."""

    def test_one_row_per_initiative(self, tmp_path: Path) -> None:
        """One row per initiative per seed run."""
        spec = _make_experiment_spec(seeds=(42,))
        rows = write_initiative_outcomes(spec, tmp_path)
        # One condition × one seed × one initiative.
        assert len(rows) == 1

    def test_belief_at_stop_from_stop_event(self, tmp_path: Path) -> None:
        """belief_at_stop matches StopEvent.quality_belief_t."""
        spec = _make_experiment_spec(seeds=(42,))
        rows = write_initiative_outcomes(spec, tmp_path)
        row = rows[0]
        # Our test data stops init-0 with quality_belief_t=0.3.
        assert row["stopped"] is True
        assert row["belief_at_stop"] == pytest.approx(0.3)


# ============================================================================
# event_log.parquet
# ============================================================================


class TestWriteEventLog:
    """Tests for write_event_log()."""

    def test_stop_events_included(self, tmp_path: Path) -> None:
        """Stop events appear in the event log."""
        spec = _make_experiment_spec(seeds=(42,))
        rows = write_event_log(spec, tmp_path)
        stop_rows = [r for r in rows if r["event_type"] == "initiative_stopped"]
        assert len(stop_rows) >= 1

    def test_required_columns(self, tmp_path: Path) -> None:
        spec = _make_experiment_spec(seeds=(42,))
        write_event_log(spec, tmp_path)
        table = pq.read_table(str(tmp_path / "outputs" / "event_log.parquet"))
        required = [
            "run_bundle_id",
            "experiment_name",
            "experimental_condition_id",
            "seed_run_id",
            "world_seed",
            "tick",
            "event_type",
            "initiative_id",
            "initiative_family",
            "initiative_family_label",
            "value_delta",
            "capability_delta",
            "quality_belief",
            "notes_json",
        ]
        for col in required:
            assert col in table.column_names, f"Missing: {col}"


# ============================================================================
# Residual value reconstruction
# ============================================================================


class TestResidualValueForBin:
    """Tests for _compute_residual_value_for_bin()."""

    def test_no_decay_constant_rate(self) -> None:
        """With decay=0, residual is rate * n_ticks."""
        cfg = make_initiative(
            value_channels=make_value_channels(
                residual_enabled=True,
                residual_rate=2.0,
                residual_decay=0.0,
            ),
        )
        val = _compute_residual_value_for_bin(cfg, activation_tick=0, bin_start=0, bin_end=10)
        assert val == pytest.approx(20.0)

    def test_activation_after_bin_start(self) -> None:
        """Only ticks at or after activation are counted."""
        cfg = make_initiative(
            value_channels=make_value_channels(
                residual_enabled=True,
                residual_rate=1.0,
                residual_decay=0.0,
            ),
        )
        val = _compute_residual_value_for_bin(cfg, activation_tick=5, bin_start=0, bin_end=10)
        # Only ticks 5..9 = 5 ticks.
        assert val == pytest.approx(5.0)

    def test_activation_after_bin_end(self) -> None:
        """Activation after bin end → zero value."""
        cfg = make_initiative(
            value_channels=make_value_channels(
                residual_enabled=True,
                residual_rate=1.0,
                residual_decay=0.0,
            ),
        )
        val = _compute_residual_value_for_bin(cfg, activation_tick=20, bin_start=0, bin_end=10)
        assert val == pytest.approx(0.0)

    def test_with_decay(self) -> None:
        """Decayed residual value is less than undecayed."""
        cfg_no_decay = make_initiative(
            value_channels=make_value_channels(
                residual_enabled=True,
                residual_rate=1.0,
                residual_decay=0.0,
            ),
        )
        cfg_decay = make_initiative(
            value_channels=make_value_channels(
                residual_enabled=True,
                residual_rate=1.0,
                residual_decay=0.1,
            ),
        )
        val_no = _compute_residual_value_for_bin(cfg_no_decay, 0, 0, 10)
        val_yes = _compute_residual_value_for_bin(cfg_decay, 0, 0, 10)
        assert val_yes < val_no
        assert val_yes > 0.0


# ============================================================================
# pairwise_deltas.parquet
# ============================================================================


class TestWritePairwiseDeltas:
    """Tests for write_pairwise_deltas()."""

    def test_produces_deltas(self, tmp_path: Path) -> None:
        """Two conditions produce one delta row."""
        spec = _make_experiment_spec(seeds=(42,), n_conditions=2)
        seed_rows = write_seed_runs(spec, tmp_path)
        cond_rows = write_experimental_conditions(spec, seed_rows, tmp_path)
        delta_rows = write_pairwise_deltas(spec, cond_rows, tmp_path)
        assert len(delta_rows) == 1

    def test_explicit_baseline(self, tmp_path: Path) -> None:
        """Explicit baseline_condition_id is used."""
        spec = _make_experiment_spec(seeds=(42,), n_conditions=2)
        seed_rows = write_seed_runs(spec, tmp_path)
        cond_rows = write_experimental_conditions(spec, seed_rows, tmp_path)
        delta_rows = write_pairwise_deltas(
            spec,
            cond_rows,
            tmp_path,
            baseline_condition_id="cond-1",
        )
        assert len(delta_rows) == 1
        assert delta_rows[0]["rhs_experimental_condition_id"] == "cond-1"


# ============================================================================
# write_all_tables (integration)
# ============================================================================


class TestWriteAllTables:
    """Integration test for write_all_tables()."""

    def test_all_output_files_created(self, tmp_path: Path) -> None:
        """All expected Parquet files are created."""
        spec = _make_experiment_spec(seeds=(42,))

        # Create directory structure first.
        from primordial_soup.run_bundle import _create_bundle_directory

        _create_bundle_directory(tmp_path)

        write_all_tables(spec, tmp_path)

        expected_files = [
            "outputs/seed_runs.parquet",
            "outputs/experimental_conditions.parquet",
            "outputs/family_outcomes.parquet",
            "outputs/yearly_timeseries.parquet",
            "outputs/initiative_outcomes.parquet",
            "outputs/diagnostics.parquet",
            "outputs/event_log.parquet",
            "derived/pairwise_deltas.parquet",
            "derived/representative_runs.parquet",
            "derived/enabler_coupling.parquet",
        ]
        for f in expected_files:
            assert (tmp_path / f).exists(), f"Missing: {f}"

    def test_returns_all_table_data(self, tmp_path: Path) -> None:
        """Return dict contains all table names."""
        spec = _make_experiment_spec(seeds=(42,))
        from primordial_soup.run_bundle import _create_bundle_directory

        _create_bundle_directory(tmp_path)

        results = write_all_tables(spec, tmp_path)
        expected_keys = [
            "seed_runs",
            "experimental_conditions",
            "family_outcomes",
            "yearly_timeseries",
            "initiative_outcomes",
            "diagnostics",
            "event_log",
            "pairwise_deltas",
            "representative_runs",
            "enabler_coupling",
        ]
        for key in expected_keys:
            assert key in results, f"Missing key: {key}"
