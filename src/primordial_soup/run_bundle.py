"""Run-bundle orchestration for experiment reporting.

This module defines the experiment-level data structures and the
top-level orchestration function for creating self-contained run
bundles. A run bundle is the canonical on-disk artifact produced
by one top-level experiment execution.

The module is responsible for:
    - Experiment-level data collection (ExperimentSpec and its components)
    - Directory layout creation per the reporting package specification
    - Manifest assembly and JSON serialization
    - Config artifact serialization
    - Provenance capture (git commit, platform, pip freeze)
    - Telemetry collection (wall-clock timing for each phase)
    - Orchestration of table, figure, and report generation
    - Validation orchestration

The run bundle is the system of record for reporting. The report
package (HTML + markdown) is derived from it and must never contain
information not traceable to canonical artifacts in the bundle.

Design reference: docs/implementation/reporting_package_specification.md
"""

from __future__ import annotations

import dataclasses
import json
import logging
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from primordial_soup.config import ResolvedInitiativeConfig, SimulationConfiguration
    from primordial_soup.reporting import RunResult
    from primordial_soup.state import WorldState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema version — bumped when the bundle layout or table schemas change
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# InitiativeFinalState — lightweight snapshot from WorldState
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InitiativeFinalState:
    """Frozen snapshot of per-initiative final state for reporting.

    Extracted from the WorldState returned by run_single_regime().
    This is a reporting-layer type — it does NOT belong in RunResult.
    It lives in SeedRunRecord only.

    Contains the subset of InitiativeState fields needed by the
    reporting tables (initiative_outcomes, family_outcomes, yearly
    timeseries value reconstruction).
    """

    initiative_id: str
    lifecycle_state: str  # string form of LifecycleState enum value
    quality_belief_t: float
    execution_belief_t: float | None
    staffed_tick_count: int
    cumulative_labor_invested: float
    cumulative_value_realized: float
    cumulative_lump_value_realized: float
    cumulative_residual_value_realized: float
    cumulative_attention_invested: float
    residual_activated: bool
    residual_activation_tick: int | None
    completed_tick: int | None
    major_win_surfaced: bool
    major_win_tick: int | None


def extract_initiative_final_states(
    world_state: WorldState,
) -> tuple[InitiativeFinalState, ...]:
    """Extract initiative final states from a WorldState.

    Converts each InitiativeState in the WorldState to a lightweight
    frozen snapshot suitable for the reporting pipeline.

    Args:
        world_state: Final WorldState from run_single_regime().

    Returns:
        Tuple of InitiativeFinalState, one per initiative, in the
        same order as world_state.initiative_states.
    """
    return tuple(
        InitiativeFinalState(
            initiative_id=init_state.initiative_id,
            lifecycle_state=init_state.lifecycle_state.value,
            quality_belief_t=init_state.quality_belief_t,
            execution_belief_t=init_state.execution_belief_t,
            staffed_tick_count=init_state.staffed_tick_count,
            cumulative_labor_invested=init_state.cumulative_labor_invested,
            cumulative_value_realized=init_state.cumulative_value_realized,
            cumulative_lump_value_realized=init_state.cumulative_lump_value_realized,
            cumulative_residual_value_realized=init_state.cumulative_residual_value_realized,
            cumulative_attention_invested=init_state.cumulative_attention_invested,
            residual_activated=init_state.residual_activated,
            residual_activation_tick=init_state.residual_activation_tick,
            completed_tick=init_state.completed_tick,
            major_win_surfaced=init_state.major_win_surfaced,
            major_win_tick=init_state.major_win_tick,
        )
        for init_state in world_state.initiative_states
    )


# ---------------------------------------------------------------------------
# Experiment-level data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentalConditionSpec:
    """Identity and grouping metadata for one experimental condition.

    These fields map directly to the required identifier and grouping
    columns in the canonical output tables.

    Per reporting_package_specification.md §experimental_conditions.parquet.
    """

    experimental_condition_id: str
    environmental_conditions_id: str
    environmental_conditions_name: str
    governance_architecture_id: str
    governance_architecture_name: str
    operating_policy_id: str
    operating_policy_name: str
    governance_regime_label: str


@dataclass(frozen=True)
class SeedRunRecord:
    """One seed run's outputs, paired with its world seed.

    Carries both the RunResult (aggregated metrics) and the
    InitiativeFinalState snapshot (per-initiative final state needed
    by tables like initiative_outcomes.parquet).

    The initiative_configs are the resolved configs for all initiatives
    in this run, including any frontier-generated initiatives.
    """

    world_seed: int
    run_result: RunResult
    initiative_final_states: tuple[InitiativeFinalState, ...]
    initiative_configs: tuple[ResolvedInitiativeConfig, ...]


@dataclass(frozen=True)
class ExperimentalConditionRecord:
    """Groups seed runs under one experimental condition.

    One ExperimentalConditionRecord per cell in the experiment grid.
    """

    condition_spec: ExperimentalConditionSpec
    seed_run_records: tuple[SeedRunRecord, ...]
    # The SimulationConfiguration used for this condition (template —
    # world_seed varies across seed runs but all other fields are shared).
    simulation_config: SimulationConfiguration


@dataclass(frozen=True)
class ExperimentSpec:
    """Top-level experiment specification for bundle generation.

    This is the primary input to create_run_bundle(). The experiment
    script constructs this from its loop results.
    """

    experiment_name: str
    title: str
    description: str
    world_seeds: tuple[int, ...]
    condition_records: tuple[ExperimentalConditionRecord, ...]
    script_name: str
    study_phase: str = "evaluation"
    # Optional baseline condition for pairwise deltas. When None,
    # falls back to auto-detecting the "Balanced" regime.
    baseline_condition_id: str | None = None
    # Report-layer unit label for monetary / value outputs
    # (per exec_intent_spec.md #8). Free-text, propagated from
    # RunDesignSpec.value_unit into the manifest so report_gen.py
    # can render value metrics with this label. The engine and RunResult
    # remain unit-agnostic; no arithmetic depends on this field.
    value_unit: str = "units"


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------


def _create_bundle_directory(bundle_path: Path) -> None:
    """Create the run-bundle directory tree.

    Per reporting_package_specification.md §Required directory layout.

    Args:
        bundle_path: Root directory for this run bundle.
    """
    subdirs = [
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
    bundle_path.mkdir(parents=True, exist_ok=True)
    for subdir in subdirs:
        (bundle_path / subdir).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------


def _generate_run_bundle_id(experiment_name: str) -> str:
    """Generate a unique run-bundle ID from experiment name and timestamp.

    Format: YYYY-MM-DD_HHMMSS_<experiment_name>

    Args:
        experiment_name: The experiment name (sanitized for filesystem).

    Returns:
        A string suitable for use as a directory name and bundle ID.
    """
    timestamp = time.strftime("%Y-%m-%d_%H%M%S")
    # Sanitize experiment name for filesystem use.
    safe_name = experiment_name.replace(" ", "_").replace("/", "_")
    return f"{timestamp}_{safe_name}"


def _get_git_commit() -> str:
    """Get the current git commit hash, or 'unknown' if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def _build_authoritative_files() -> dict[str, str]:
    """Build the authoritative_files map for the manifest.

    Returns relative paths from the bundle root to each canonical artifact.
    """
    return {
        "run_spec": "config/run_spec.json",
        "simulation_config": "config/simulation_config.json",
        "environmental_conditions": "config/environmental_conditions.json",
        "governance_architecture": "config/governance_architecture.json",
        "operating_policies": "config/operating_policies.json",
        "initial_state_index": "inputs/initial_state_index.parquet",
        "experimental_conditions": "outputs/experimental_conditions.parquet",
        "seed_runs": "outputs/seed_runs.parquet",
        "family_outcomes": "outputs/family_outcomes.parquet",
        "yearly_timeseries": "outputs/yearly_timeseries.parquet",
        "initiative_outcomes": "outputs/initiative_outcomes.parquet",
        "diagnostics": "outputs/diagnostics.parquet",
        "event_log": "outputs/event_log.parquet",
        "pairwise_deltas": "derived/pairwise_deltas.parquet",
        "report_html": "report/index.html",
        "report_markdown": "report/report.md",
    }


def _build_manifest(
    experiment_spec: ExperimentSpec,
    run_bundle_id: str,
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the manifest dictionary.

    Per reporting_package_specification.md §Required manifest fields.

    Args:
        experiment_spec: The experiment specification.
        run_bundle_id: The unique bundle ID.
        telemetry: Telemetry data from the execution.

    Returns:
        Dictionary ready for JSON serialization as manifest.json.
    """
    return {
        "run_bundle_id": run_bundle_id,
        "title": experiment_spec.title,
        "description": experiment_spec.description,
        "run_kind": "experiment",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "script": experiment_spec.script_name,
        "command": " ".join(sys.argv),
        "git_commit": _get_git_commit(),
        "python_version": platform.python_version(),
        "platform": f"{platform.system()}-{platform.release()}",
        "schema_version": SCHEMA_VERSION,
        "study_phase": experiment_spec.study_phase,
        "experiment_name": experiment_spec.experiment_name,
        "seed_count": len(experiment_spec.world_seeds),
        "world_seeds": list(experiment_spec.world_seeds),
        "experimental_condition_count": len(experiment_spec.condition_records),
        "rerun_supported": True,
        "replay_supported": False,  # Phase 1: no initial-state snapshots
        "authoritative_files": _build_authoritative_files(),
        "telemetry": telemetry,
        # Report-layer value-unit label (per exec_intent_spec.md #8).
        # The engine is unit-agnostic; this label is applied at render
        # time by report_gen.py to every value-dimension metric.
        "value_unit": experiment_spec.value_unit,
    }


# ---------------------------------------------------------------------------
# Config serialization helpers
# ---------------------------------------------------------------------------


def _dataclass_to_json_dict(obj: Any) -> Any:
    """Recursively convert a dataclass (or nested structure) to a
    JSON-serializable dictionary.

    Handles:
    - Frozen dataclasses → dict via dataclasses.asdict()
    - Enums → their .value
    - Tuples → lists
    - None, str, int, float, bool → as-is
    """
    if obj is None or isinstance(obj, str | int | float | bool):
        return obj
    if isinstance(obj, tuple):
        return [_dataclass_to_json_dict(item) for item in obj]
    if isinstance(obj, list):
        return [_dataclass_to_json_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _dataclass_to_json_dict(v) for k, v in obj.items()}
    if hasattr(obj, "value") and hasattr(obj, "name"):
        # Enum-like object.
        return obj.value
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            field.name: _dataclass_to_json_dict(getattr(obj, field.name))
            for field in dataclasses.fields(obj)
        }
    # Fallback: convert to string.
    return str(obj)


def _write_config_artifacts(
    experiment_spec: ExperimentSpec,
    bundle_path: Path,
) -> None:
    """Write configuration artifacts to config/ directory.

    Serializes the simulation configuration, governance architecture,
    operating policies, and environmental conditions as JSON.

    Args:
        experiment_spec: The experiment specification.
        bundle_path: Root directory for the run bundle.
    """
    config_dir = bundle_path / "config"

    # run_spec.json — experiment-level metadata.
    run_spec = {
        "experiment_name": experiment_spec.experiment_name,
        "title": experiment_spec.title,
        "description": experiment_spec.description,
        "script_name": experiment_spec.script_name,
        "study_phase": experiment_spec.study_phase,
        "seed_count": len(experiment_spec.world_seeds),
        "world_seeds": list(experiment_spec.world_seeds),
        "experimental_conditions": [
            {
                "experimental_condition_id": rec.condition_spec.experimental_condition_id,
                "environmental_conditions_name": rec.condition_spec.environmental_conditions_name,
                "governance_regime_label": rec.condition_spec.governance_regime_label,
                "operating_policy_id": rec.condition_spec.operating_policy_id,
            }
            for rec in experiment_spec.condition_records
        ],
    }
    _write_json(config_dir / "run_spec.json", run_spec)

    # simulation_config.json — first condition's config as representative.
    if experiment_spec.condition_records:
        first_config = experiment_spec.condition_records[0].simulation_config
        _write_json(
            config_dir / "simulation_config.json",
            _dataclass_to_json_dict(first_config),
        )

    # governance_architecture.json — structural workforce and standing
    # portfolio guardrails. Per governance.md, architecture = team
    # decomposition + ramp + standing guardrails, NOT per-tick stop
    # thresholds.
    architecture_by_condition: dict[str, Any] = {}
    for rec in experiment_spec.condition_records:
        cid = rec.condition_spec.experimental_condition_id
        if cid not in architecture_by_condition:
            gov = rec.simulation_config.governance
            architecture_by_condition[cid] = {
                "teams": _dataclass_to_json_dict(rec.simulation_config.teams),
                "low_quality_belief_threshold": gov.low_quality_belief_threshold,
                "max_low_quality_belief_labor_share": gov.max_low_quality_belief_labor_share,
                "max_single_initiative_labor_share": gov.max_single_initiative_labor_share,
                "portfolio_mix_targets": _dataclass_to_json_dict(gov.portfolio_mix_targets),
            }
    _write_json(config_dir / "governance_architecture.json", architecture_by_condition)

    # operating_policies.json — per-tick decision parameters (stop
    # thresholds, attention bounds, stagnation detection). Per
    # governance.md, these are the recurring levers the policy exercises.
    policy_configs: dict[str, Any] = {}
    for rec in experiment_spec.condition_records:
        policy_id = rec.condition_spec.operating_policy_id
        if policy_id not in policy_configs:
            policy_configs[policy_id] = _dataclass_to_json_dict(rec.simulation_config.governance)
    _write_json(config_dir / "operating_policies.json", policy_configs)

    # environmental_conditions.json — environment by condition name.
    environment_configs: dict[str, Any] = {}
    for rec in experiment_spec.condition_records:
        env_name = rec.condition_spec.environmental_conditions_name
        if env_name not in environment_configs:
            environment_configs[env_name] = {
                "time": _dataclass_to_json_dict(rec.simulation_config.time),
                "teams": _dataclass_to_json_dict(rec.simulation_config.teams),
                "model": _dataclass_to_json_dict(rec.simulation_config.model),
                "initiative_generator": _dataclass_to_json_dict(
                    rec.simulation_config.initiative_generator
                ),
            }
    _write_json(config_dir / "environmental_conditions.json", environment_configs)

    # reporting_config.json
    if experiment_spec.condition_records:
        _write_json(
            config_dir / "reporting_config.json",
            _dataclass_to_json_dict(
                experiment_spec.condition_records[0].simulation_config.reporting
            ),
        )


# ---------------------------------------------------------------------------
# Provenance capture
# ---------------------------------------------------------------------------


def _write_provenance(bundle_path: Path) -> None:
    """Write provenance artifacts to provenance/ directory.

    Captures the execution environment for auditability and
    reproducibility.

    Args:
        bundle_path: Root directory for the run bundle.
    """
    provenance_dir = bundle_path / "provenance"

    # command.txt — the command that produced this bundle.
    (provenance_dir / "command.txt").write_text(" ".join(sys.argv) + "\n")

    # git_commit.txt
    (provenance_dir / "git_commit.txt").write_text(_get_git_commit() + "\n")

    # environment.json
    env_info = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
    }
    _write_json(provenance_dir / "environment.json", env_info)

    # pip_freeze.txt
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            (provenance_dir / "pip_freeze.txt").write_text(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        (provenance_dir / "pip_freeze.txt").write_text("# pip freeze unavailable\n")

    # schema_versions.json
    _write_json(
        provenance_dir / "schema_versions.json",
        {"reporting_package": SCHEMA_VERSION},
    )


# ---------------------------------------------------------------------------
# JSON writing helper
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: Any) -> None:
    """Write JSON data to a file with consistent formatting.

    Args:
        path: Output file path.
        data: JSON-serializable data.
    """
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
        f.write("\n")


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def create_run_bundle(
    experiment_spec: ExperimentSpec,
    output_dir: Path,
    *,
    run_bundle_id: str | None = None,
) -> Path:
    """Create a complete run bundle on disk.

    This is the top-level entry point for bundle generation. It creates
    the directory tree, writes all canonical and derived artifacts,
    generates figures and reports, writes the manifest, and runs
    validation.

    Args:
        experiment_spec: Complete experiment specification with all
            seed-run results.
        output_dir: Parent directory where the bundle directory will
            be created.
        run_bundle_id: Optional explicit bundle ID. If None, one is
            generated from the experiment name and timestamp.

    Returns:
        Path to the created run-bundle directory.
    """
    if run_bundle_id is None:
        run_bundle_id = _generate_run_bundle_id(experiment_spec.experiment_name)

    bundle_path = output_dir / run_bundle_id
    logger.info("Creating run bundle: %s", bundle_path)

    # --- Phase timing ---
    phase_timings: dict[str, float] = {}
    bundle_start = time.time()

    # --- Create directory tree ---
    _create_bundle_directory(bundle_path)

    # --- Write config artifacts ---
    config_start = time.time()
    _write_config_artifacts(experiment_spec, bundle_path)
    phase_timings["config_seconds"] = time.time() - config_start

    # --- Write provenance ---
    provenance_start = time.time()
    _write_provenance(bundle_path)
    phase_timings["provenance_seconds"] = time.time() - provenance_start

    # --- Write canonical and derived tables ---
    from primordial_soup.tables import write_all_tables

    simulation_start = time.time()
    table_data = write_all_tables(
        experiment_spec,
        bundle_path,
        baseline_condition_id=experiment_spec.baseline_condition_id,
    )
    phase_timings["simulation_seconds"] = time.time() - simulation_start

    # --- Generate figures ---
    from primordial_soup.figures import generate_all_figures, generate_trajectory_figures

    figure_start = time.time()
    generate_all_figures(table_data, bundle_path / "figures")

    # Trajectory figures are generated separately because they read from
    # the ExperimentSpec directly (per-tick records on SeedRunRecord),
    # not from the aggregate table_data used by the 9 standard figures.
    generate_trajectory_figures(
        experiment_spec,
        table_data.get("representative_runs", []),
        bundle_path / "figures",
    )
    phase_timings["figure_generation_seconds"] = time.time() - figure_start

    # --- Generate reports ---
    from primordial_soup.report_gen import generate_report

    report_start = time.time()
    # Build a preliminary manifest dict for the report (telemetry not final yet).
    preliminary_manifest = _build_manifest(
        experiment_spec,
        run_bundle_id,
        {"status": "in_progress"},
    )
    generate_report(
        preliminary_manifest,
        table_data,
        bundle_path / "figures",
        bundle_path / "report",
    )
    phase_timings["report_render_seconds"] = time.time() - report_start

    # --- Validation (deferred until after manifest is written) ---
    validation_start = time.time()
    phase_timings["validation_seconds"] = 0.0  # Updated after validation

    # --- Telemetry ---
    total_seconds = time.time() - bundle_start
    total_seed_runs = sum(len(rec.seed_run_records) for rec in experiment_spec.condition_records)
    telemetry = {
        "status": "completed",
        "started_at": time.strftime(
            "%Y-%m-%dT%H:%M:%S%z",
            time.localtime(bundle_start),
        ),
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "wall_clock_seconds_total": round(total_seconds, 2),
        "experimental_condition_count": len(experiment_spec.condition_records),
        "seed_count": len(experiment_spec.world_seeds),
        "seed_run_count_total": total_seed_runs,
        "seed_runs_completed": total_seed_runs,
        **{k: round(v, 2) for k, v in phase_timings.items()},
    }

    # --- Write manifest ---
    manifest = _build_manifest(experiment_spec, run_bundle_id, telemetry)
    _write_json(bundle_path / "manifest.json", manifest)

    # --- Write timing log ---
    _write_json(bundle_path / "logs" / "timing.json", telemetry)

    # --- Run validation ---
    from primordial_soup.bundle_validation import validate_bundle

    validation_result = validate_bundle(bundle_path)
    phase_timings["validation_seconds"] = time.time() - validation_start
    if not validation_result.passed:
        logger.warning(
            "Bundle validation found %d errors: %s",
            len(validation_result.errors),
            "; ".join(validation_result.errors[:5]),
        )
    for warning_msg in validation_result.warnings:
        logger.info("Bundle validation warning: %s", warning_msg)

    logger.info(
        "Run bundle created: %s (%d conditions, %d seed runs, %.1fs)",
        bundle_path,
        len(experiment_spec.condition_records),
        total_seed_runs,
        total_seconds,
    )

    return bundle_path
