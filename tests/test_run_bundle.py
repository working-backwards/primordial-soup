"""Tests for run_bundle.py — run-bundle scaffolding and manifest.

Tests verify:
    - InitiativeFinalState extraction from WorldState
    - Directory layout creation matches spec
    - Manifest contains all required fields
    - Config artifacts are valid JSON
    - Provenance artifacts exist
    - Telemetry fields are populated
    - ExperimentSpec data structures are frozen
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TCH003 — pytest fixtures need Path at runtime

import pytest

from conftest import make_initiative, make_simulation_config
from primordial_soup.reporting import RunCollector, RunManifest, assemble_run_result
from primordial_soup.run_bundle import (
    ExperimentalConditionRecord,
    ExperimentalConditionSpec,
    ExperimentSpec,
    SeedRunRecord,
    _build_manifest,
    _create_bundle_directory,
    _dataclass_to_json_dict,
    _write_config_artifacts,
    _write_provenance,
    create_run_bundle,
    extract_initiative_final_states,
)
from primordial_soup.state import InitiativeState, TeamState, WorldState
from primordial_soup.types import LifecycleState

# ============================================================================
# Helpers
# ============================================================================


def _make_condition_spec(
    condition_id: str = "cond-1",
    env_name: str = "balanced_incumbent",
    regime_label: str = "Balanced",
    policy_id: str = "balanced",
) -> ExperimentalConditionSpec:
    """Build a minimal ExperimentalConditionSpec."""
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


def _make_world_state() -> WorldState:
    """Build a minimal WorldState with one stopped initiative."""
    return WorldState(
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
                cumulative_value_realized=2.5,
                cumulative_lump_value_realized=0.0,
                cumulative_residual_value_realized=2.5,
                cumulative_labor_invested=5.0,
                cumulative_attention_invested=1.5,
                belief_history=(0.3,),
                review_count=3,
                consecutive_reviews_below_tam_ratio=0,
                residual_activated=True,
                residual_activation_tick=3,
                major_win_surfaced=False,
                major_win_tick=None,
                completed_tick=None,
            ),
        ),
        team_states=(TeamState(team_id="team-0", team_size=1, assigned_initiative_id=None),),
        portfolio_capability=1.0,
    )


def _make_seed_run_record(seed: int = 42) -> SeedRunRecord:
    """Build a minimal SeedRunRecord for testing."""
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

    world_state = _make_world_state()
    final_states = extract_initiative_final_states(world_state)

    manifest = RunManifest(
        policy_id="balanced",
        world_seed=seed,
        is_replay=False,
        resolved_configuration=config,
        resolved_initiatives=init_configs,
        engine_version="0.1.0",
    )

    collector = RunCollector()
    run_result = assemble_run_result(
        collector=collector,
        config=config,
        initiative_configs=init_configs,
        final_world_state=world_state,
        manifest=manifest,
    )

    return SeedRunRecord(
        world_seed=seed,
        run_result=run_result,
        initiative_final_states=final_states,
        initiative_configs=init_configs,
    )


def _make_experiment_spec(
    seeds: tuple[int, ...] = (42, 43),
) -> ExperimentSpec:
    """Build a minimal ExperimentSpec for testing."""
    config = make_simulation_config(
        initiatives=(
            make_initiative(
                initiative_id="init-0",
                generation_tag="flywheel",
            ),
        ),
    )

    seed_runs = tuple(_make_seed_run_record(s) for s in seeds)
    condition = ExperimentalConditionRecord(
        condition_spec=_make_condition_spec(),
        seed_run_records=seed_runs,
        simulation_config=config,
    )

    return ExperimentSpec(
        experiment_name="test_experiment",
        title="Test Experiment",
        description="A test experiment for unit testing.",
        world_seeds=seeds,
        condition_records=(condition,),
        script_name="tests/test_run_bundle.py",
        study_phase="testing",
    )


# ============================================================================
# InitiativeFinalState extraction
# ============================================================================


class TestExtractInitiativeFinalStates:
    """Tests for extract_initiative_final_states()."""

    def test_extracts_all_fields(self) -> None:
        """All InitiativeState fields are correctly mapped."""
        ws = _make_world_state()
        states = extract_initiative_final_states(ws)

        assert len(states) == 1
        s = states[0]
        assert s.initiative_id == "init-0"
        assert s.lifecycle_state == "stopped"  # enum value string
        assert s.quality_belief_t == pytest.approx(0.3)
        assert s.execution_belief_t is None
        assert s.staffed_tick_count == 5
        assert s.cumulative_labor_invested == pytest.approx(5.0)
        assert s.cumulative_value_realized == pytest.approx(2.5)
        assert s.cumulative_lump_value_realized == pytest.approx(0.0)
        assert s.cumulative_residual_value_realized == pytest.approx(2.5)
        assert s.cumulative_attention_invested == pytest.approx(1.5)
        assert s.residual_activated is True
        assert s.residual_activation_tick == 3

    def test_frozen(self) -> None:
        """InitiativeFinalState is frozen."""
        ws = _make_world_state()
        states = extract_initiative_final_states(ws)
        with pytest.raises(AttributeError):
            states[0].quality_belief_t = 0.9  # type: ignore[misc]

    def test_empty_world_state(self) -> None:
        """Empty WorldState produces empty tuple."""
        ws = WorldState(
            tick=0,
            initiative_states=(),
            team_states=(),
            portfolio_capability=1.0,
        )
        assert extract_initiative_final_states(ws) == ()


# ============================================================================
# Data structure sanity
# ============================================================================


class TestDataStructures:
    """Frozen dataclass sanity checks for experiment types."""

    def test_condition_spec_frozen(self) -> None:
        spec = _make_condition_spec()
        with pytest.raises(AttributeError):
            spec.governance_regime_label = "X"  # type: ignore[misc]

    def test_seed_run_record_frozen(self) -> None:
        rec = _make_seed_run_record()
        with pytest.raises(AttributeError):
            rec.world_seed = 99  # type: ignore[misc]

    def test_experiment_spec_frozen(self) -> None:
        spec = _make_experiment_spec()
        with pytest.raises(AttributeError):
            spec.title = "X"  # type: ignore[misc]


# ============================================================================
# Directory creation
# ============================================================================


class TestCreateBundleDirectory:
    """Tests for _create_bundle_directory()."""

    def test_creates_all_subdirectories(self, tmp_path: Path) -> None:
        """All required subdirectories are created."""

        bundle_path = tmp_path / "test_bundle"
        _create_bundle_directory(bundle_path)

        expected_dirs = [
            "config",
            "inputs",
            "inputs/initial_state_snapshots",
            "outputs",
            "derived",
            "figures",
            "report",
            "logs",
            "provenance",
        ]
        for subdir in expected_dirs:
            assert (bundle_path / subdir).is_dir(), f"Missing: {subdir}"

    def test_idempotent(self, tmp_path: Path) -> None:
        """Calling twice does not raise."""
        bundle_path = tmp_path / "test_bundle"
        _create_bundle_directory(bundle_path)
        _create_bundle_directory(bundle_path)  # should not raise


# ============================================================================
# Manifest
# ============================================================================


class TestBuildManifest:
    """Tests for _build_manifest()."""

    def test_required_fields_present(self) -> None:
        """All required manifest fields are present."""
        spec = _make_experiment_spec()
        manifest = _build_manifest(spec, "test-bundle-id", {"status": "completed"})

        required_fields = [
            "run_bundle_id",
            "title",
            "description",
            "run_kind",
            "created_at",
            "script",
            "command",
            "git_commit",
            "python_version",
            "platform",
            "schema_version",
            "study_phase",
            "experiment_name",
            "seed_count",
            "world_seeds",
            "experimental_condition_count",
            "rerun_supported",
            "replay_supported",
            "authoritative_files",
            "telemetry",
        ]
        for field in required_fields:
            assert field in manifest, f"Missing manifest field: {field}"

    def test_seed_count_matches(self) -> None:
        """seed_count equals len(world_seeds)."""
        spec = _make_experiment_spec(seeds=(42, 43, 44))
        manifest = _build_manifest(spec, "test-id", {})

        assert manifest["seed_count"] == 3
        assert manifest["world_seeds"] == [42, 43, 44]
        assert manifest["seed_count"] == len(manifest["world_seeds"])

    def test_condition_count_matches(self) -> None:
        """experimental_condition_count matches actual conditions."""
        spec = _make_experiment_spec()
        manifest = _build_manifest(spec, "test-id", {})

        assert manifest["experimental_condition_count"] == len(spec.condition_records)


# ============================================================================
# Config serialization
# ============================================================================


class TestConfigSerialization:
    """Tests for _write_config_artifacts()."""

    def test_writes_all_config_files(self, tmp_path: Path) -> None:
        """All expected config files are written."""
        bundle_path = tmp_path / "bundle"
        _create_bundle_directory(bundle_path)

        spec = _make_experiment_spec()
        _write_config_artifacts(spec, bundle_path)

        config_dir = bundle_path / "config"
        expected_files = [
            "run_spec.json",
            "simulation_config.json",
            "governance_architecture.json",
            "operating_policies.json",
            "environmental_conditions.json",
            "reporting_config.json",
        ]
        for filename in expected_files:
            path = config_dir / filename
            assert path.exists(), f"Missing: {filename}"
            # Verify valid JSON.
            data = json.loads(path.read_text())
            assert isinstance(data, dict | list)

    def test_run_spec_contains_conditions(self, tmp_path: Path) -> None:
        """run_spec.json lists experimental conditions."""
        bundle_path = tmp_path / "bundle"
        _create_bundle_directory(bundle_path)

        spec = _make_experiment_spec()
        _write_config_artifacts(spec, bundle_path)

        run_spec = json.loads((bundle_path / "config" / "run_spec.json").read_text())
        assert "experimental_conditions" in run_spec
        assert len(run_spec["experimental_conditions"]) == 1


# ============================================================================
# Provenance
# ============================================================================


class TestProvenance:
    """Tests for _write_provenance()."""

    def test_writes_all_provenance_files(self, tmp_path: Path) -> None:
        """All expected provenance files are written."""
        bundle_path = tmp_path / "bundle"
        _create_bundle_directory(bundle_path)
        _write_provenance(bundle_path)

        provenance_dir = bundle_path / "provenance"
        expected_files = [
            "command.txt",
            "git_commit.txt",
            "environment.json",
            "pip_freeze.txt",
            "schema_versions.json",
        ]
        for filename in expected_files:
            assert (provenance_dir / filename).exists(), f"Missing: {filename}"

    def test_environment_json_valid(self, tmp_path: Path) -> None:
        """environment.json is valid JSON with expected fields."""
        bundle_path = tmp_path / "bundle"
        _create_bundle_directory(bundle_path)
        _write_provenance(bundle_path)

        env = json.loads((bundle_path / "provenance" / "environment.json").read_text())
        assert "python_version" in env
        assert "platform" in env


# ============================================================================
# Dataclass-to-JSON conversion
# ============================================================================


class TestDataclassToJsonDict:
    """Tests for _dataclass_to_json_dict()."""

    def test_simple_dataclass(self) -> None:
        """Frozen dataclass converts to dict."""
        from primordial_soup.config import TimeConfig

        tc = TimeConfig(tick_horizon=100, tick_label="week")
        result = _dataclass_to_json_dict(tc)
        assert result == {"tick_horizon": 100, "tick_label": "week"}

    def test_enum_value(self) -> None:
        """Enum converts to its .value."""
        from primordial_soup.types import RampShape

        assert _dataclass_to_json_dict(RampShape.LINEAR) == "linear"

    def test_none_passthrough(self) -> None:
        assert _dataclass_to_json_dict(None) is None

    def test_tuple_to_list(self) -> None:
        assert _dataclass_to_json_dict((1, 2, 3)) == [1, 2, 3]


# ============================================================================
# Full bundle creation (integration)
# ============================================================================


class TestCreateRunBundle:
    """Integration test for full run-bundle creation."""

    def test_creates_bundle_directory(self, tmp_path: Path) -> None:
        """create_run_bundle() produces a directory with manifest."""
        spec = _make_experiment_spec(seeds=(42,))
        bundle_path = create_run_bundle(spec, tmp_path, run_bundle_id="test-bundle")

        assert bundle_path.exists()
        assert bundle_path.name == "test-bundle"

        # Manifest exists and is valid JSON.
        manifest_path = bundle_path / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["run_bundle_id"] == "test-bundle"
        assert manifest["experiment_name"] == "test_experiment"

    def test_telemetry_in_manifest(self, tmp_path: Path) -> None:
        """Manifest contains telemetry with required fields."""
        spec = _make_experiment_spec(seeds=(42,))
        bundle_path = create_run_bundle(spec, tmp_path, run_bundle_id="test-bundle")

        manifest = json.loads((bundle_path / "manifest.json").read_text())
        telemetry = manifest["telemetry"]
        assert telemetry["status"] == "completed"
        assert "started_at" in telemetry
        assert "completed_at" in telemetry
        assert telemetry["wall_clock_seconds_total"] >= 0
        assert telemetry["seed_run_count_total"] == 1
        assert telemetry["seed_count"] == 1

    def test_timing_log_written(self, tmp_path: Path) -> None:
        """logs/timing.json is written."""
        spec = _make_experiment_spec(seeds=(42,))
        bundle_path = create_run_bundle(spec, tmp_path, run_bundle_id="test-bundle")

        timing_path = bundle_path / "logs" / "timing.json"
        assert timing_path.exists()
        timing = json.loads(timing_path.read_text())
        assert timing["status"] == "completed"

    def test_auto_generated_bundle_id(self, tmp_path: Path) -> None:
        """When run_bundle_id is None, one is auto-generated."""
        spec = _make_experiment_spec(seeds=(42,))
        bundle_path = create_run_bundle(spec, tmp_path)

        assert bundle_path.exists()
        # Name should contain the experiment name.
        assert "test_experiment" in bundle_path.name

    def test_config_and_provenance_written(self, tmp_path: Path) -> None:
        """Config and provenance directories are populated."""
        spec = _make_experiment_spec(seeds=(42,))
        bundle_path = create_run_bundle(spec, tmp_path, run_bundle_id="test-bundle")

        assert (bundle_path / "config" / "run_spec.json").exists()
        assert (bundle_path / "provenance" / "environment.json").exists()
