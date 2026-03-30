"""Run-bundle validation for reporting package completeness.

Validates that a run bundle on disk satisfies the requirements from
the reporting package specification: manifest completeness, canonical
table presence, report-package artifacts, and telemetry.

Design reference: docs/implementation/reporting_package_specification.md §Validation
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pyarrow.parquet as pq

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationResult:
    """Result of run-bundle validation.

    Attributes:
        passed: True if all validation rules passed.
        errors: Tuple of error messages (failures that make the bundle invalid).
        warnings: Tuple of warning messages (non-blocking issues).
    """

    passed: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def validate_bundle(bundle_path: Path) -> ValidationResult:
    """Validate a run bundle against the reporting package specification.

    Checks:
    1. Manifest validation (existence, required fields, path references)
    2. Table validation (existence, required columns)
    3. Report validation (required files)
    4. Telemetry validation (required fields)

    Args:
        bundle_path: Root directory of the run bundle.

    Returns:
        ValidationResult with pass/fail status and messages.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- 1. Manifest validation ---
    manifest_path = bundle_path / "manifest.json"
    if not manifest_path.exists():
        errors.append("manifest.json is missing")
        return ValidationResult(passed=False, errors=tuple(errors), warnings=tuple(warnings))

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        errors.append(f"manifest.json is not valid JSON: {e}")
        return ValidationResult(passed=False, errors=tuple(errors), warnings=tuple(warnings))

    # Required manifest fields.
    required_manifest_fields = [
        "run_bundle_id",
        "title",
        "run_kind",
        "created_at",
        "script",
        "git_commit",
        "python_version",
        "platform",
        "schema_version",
        "experiment_name",
        "seed_count",
        "world_seeds",
        "experimental_condition_count",
        "authoritative_files",
        "telemetry",
    ]
    for field in required_manifest_fields:
        if field not in manifest:
            errors.append(f"manifest.json missing required field: {field}")

    # seed_count matches world_seeds.
    seed_count = manifest.get("seed_count")
    world_seeds = manifest.get("world_seeds", [])
    if seed_count is not None and len(world_seeds) != seed_count:
        errors.append(
            f"seed_count ({seed_count}) disagrees with " f"len(world_seeds) ({len(world_seeds)})"
        )

    # Authoritative file paths exist (except diagnostic_flags which is Phase 2).
    auth_files = manifest.get("authoritative_files", {})
    for name, rel_path in auth_files.items():
        if name == "diagnostic_flags":
            continue  # Phase 2 — path need not exist.
        full_path = bundle_path / rel_path
        if not full_path.exists():
            # Warnings for optional artifacts, errors for required ones.
            warnings.append(f"authoritative_files['{name}'] path does not exist: {rel_path}")

    # --- 2. Table validation ---
    required_tables = {
        "outputs/seed_runs.parquet": [
            "run_bundle_id",
            "experiment_name",
            "experimental_condition_id",
            "seed_run_id",
            "world_seed",
            "total_value",
            "surfaced_major_wins",
            "terminal_capability",
            "right_tail_false_stop_rate",
            "idle_pct",
            "status",
        ],
        "outputs/experimental_conditions.parquet": [
            "run_bundle_id",
            "experiment_name",
            "experimental_condition_id",
            "total_value_mean",
            "surfaced_major_wins_mean",
            "terminal_capability_mean",
        ],
        "outputs/family_outcomes.parquet": [
            "run_bundle_id",
            "experiment_name",
            "experimental_condition_id",
            "grouping_namespace",
            "grouping_key",
            "grouping_label",
            "initiative_count",
            "aggregation_level",
        ],
        "outputs/yearly_timeseries.parquet": [
            "run_bundle_id",
            "experiment_name",
            "experimental_condition_id",
            "seed_run_id",
            "time_bin_index",
            "grouping_key",
            "value_total",
            "value_total_cumulative",
        ],
        "outputs/initiative_outcomes.parquet": [
            "run_bundle_id",
            "experiment_name",
            "experimental_condition_id",
            "seed_run_id",
            "initiative_id",
            "status",
            "is_major_win_eligible",
            "belief_at_stop",
        ],
        "outputs/diagnostics.parquet": [
            "run_bundle_id",
            "experiment_name",
            "experimental_condition_id",
            "diagnostic_group",
            "diagnostic_name",
            "metric_value",
        ],
        "outputs/event_log.parquet": [
            "run_bundle_id",
            "experiment_name",
            "experimental_condition_id",
            "seed_run_id",
            "tick",
            "event_type",
            "initiative_id",
        ],
    }

    for table_path, required_columns in required_tables.items():
        full_path = bundle_path / table_path
        if not full_path.exists():
            errors.append(f"Required table missing: {table_path}")
            continue

        try:
            table = pq.read_table(str(full_path))
            column_names = set(table.column_names)
            for col in required_columns:
                if col not in column_names:
                    errors.append(f"{table_path}: missing required column '{col}'")
        except Exception as e:
            errors.append(f"{table_path}: failed to read Parquet: {e}")

    # --- 3. Derived tables (existence check only) ---
    derived_tables = [
        "derived/pairwise_deltas.parquet",
        "derived/representative_runs.parquet",
        "derived/enabler_coupling.parquet",
    ]
    for table_path in derived_tables:
        if not (bundle_path / table_path).exists():
            warnings.append(f"Derived table missing: {table_path}")

    # --- 4. Report validation ---
    report_files = [
        "report/index.html",
        "report/report.md",
    ]
    for rf in report_files:
        if not (bundle_path / rf).exists():
            errors.append(f"Required report file missing: {rf}")

    # --- 5. Telemetry validation ---
    telemetry = manifest.get("telemetry", {})
    if not telemetry:
        errors.append("telemetry object is missing from manifest")
    else:
        required_telemetry = [
            "status",
            "started_at",
            "completed_at",
            "wall_clock_seconds_total",
            "seed_run_count_total",
        ]
        for field in required_telemetry:
            if field not in telemetry:
                errors.append(f"telemetry missing required field: {field}")

        wcs = telemetry.get("wall_clock_seconds_total")
        if wcs is not None and wcs < 0:
            errors.append(f"wall_clock_seconds_total is negative: {wcs}")

        completed = telemetry.get("seed_runs_completed")
        total = telemetry.get("seed_run_count_total")
        if completed is not None and total is not None and completed > total:
            errors.append(
                f"seed_runs_completed ({completed}) exceeds " f"seed_run_count_total ({total})"
            )

    # --- 6. Required figures ---
    required_figures = [
        "figures/value_by_year_stacked.png",
        "figures/cumulative_value_by_year.png",
        "figures/surfaced_major_wins_by_year.png",
        "figures/tradeoff_frontier.png",
        "figures/terminal_capability.png",
        "figures/rt_survival_curves.png",
        "figures/enabler_dashboard.png",
    ]
    for fig_path in required_figures:
        if not (bundle_path / fig_path).exists():
            warnings.append(f"Required figure missing: {fig_path}")

    # Trajectory figures are conditional — they require per-tick data
    # (record_per_tick_logs=True). When present, validate that both
    # plot types exist for each condition that has them.
    figures_path = bundle_path / "figures"
    if figures_path.exists():
        trajectory_beliefs = sorted(figures_path.glob("trajectory_beliefs_*.png"))
        trajectory_overlays = sorted(figures_path.glob("trajectory_overlay_*.png"))
        # Extract condition IDs from filenames for cross-check.
        beliefs_conditions = {
            p.stem.removeprefix("trajectory_beliefs_") for p in trajectory_beliefs
        }
        overlay_conditions = {
            p.stem.removeprefix("trajectory_overlay_") for p in trajectory_overlays
        }
        # If one type exists but not the other for a condition, warn.
        for cid in beliefs_conditions - overlay_conditions:
            warnings.append(
                f"trajectory_beliefs_{cid}.png exists but trajectory_overlay_{cid}.png is missing"
            )
        for cid in overlay_conditions - beliefs_conditions:
            warnings.append(
                f"trajectory_overlay_{cid}.png exists but trajectory_beliefs_{cid}.png is missing"
            )

    passed = len(errors) == 0
    result = ValidationResult(
        passed=passed,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )

    if passed:
        logger.info("Bundle validation passed: %s", bundle_path)
    else:
        logger.warning(
            "Bundle validation failed with %d errors: %s",
            len(errors),
            bundle_path,
        )

    return result
