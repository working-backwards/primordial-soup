"""Tests for bundle_validation.py — run-bundle validation.

Tests verify:
    - Valid bundle passes all checks
    - Missing manifest detected
    - Missing required table detected
    - Missing required column detected
    - Telemetry validation
    - Report file validation
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TCH003 — pytest fixtures need Path at runtime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from primordial_soup.bundle_validation import ValidationResult, validate_bundle

# ============================================================================
# Helpers
# ============================================================================


def _create_minimal_valid_bundle(bundle_path: Path) -> None:
    """Create a minimal bundle that passes validation.

    Writes the manifest, required tables (with correct columns),
    and report files.
    """
    # Create directories.
    for subdir in ["config", "outputs", "derived", "figures", "report", "logs", "provenance"]:
        (bundle_path / subdir).mkdir(parents=True, exist_ok=True)

    # Manifest.
    manifest = {
        "run_bundle_id": "test",
        "title": "Test",
        "run_kind": "experiment",
        "created_at": "2026-03-17T00:00:00",
        "script": "test.py",
        "git_commit": "abc",
        "python_version": "3.12",
        "platform": "test",
        "schema_version": "1.0.0",
        "experiment_name": "test",
        "seed_count": 1,
        "world_seeds": [42],
        "experimental_condition_count": 1,
        "authoritative_files": {},
        "telemetry": {
            "status": "completed",
            "started_at": "2026-03-17T00:00:00",
            "completed_at": "2026-03-17T00:01:00",
            "wall_clock_seconds_total": 60.0,
            "seed_run_count_total": 1,
            "seed_runs_completed": 1,
        },
    }
    with (bundle_path / "manifest.json").open("w") as f:
        json.dump(manifest, f)

    # Required canonical tables with minimum columns.
    _write_table(
        bundle_path / "outputs" / "seed_runs.parquet",
        {
            "run_bundle_id": ["test"],
            "experiment_name": ["test"],
            "experimental_condition_id": ["c1"],
            "seed_run_id": ["c1__seed_42"],
            "world_seed": [42],
            "total_value": [100.0],
            "surfaced_major_wins": [1],
            "terminal_capability": [1.2],
            "right_tail_false_stop_rate": [0.5],
            "idle_pct": [0.1],
            "status": ["completed"],
        },
    )

    _write_table(
        bundle_path / "outputs" / "experimental_conditions.parquet",
        {
            "run_bundle_id": ["test"],
            "experiment_name": ["test"],
            "experimental_condition_id": ["c1"],
            "total_value_mean": [100.0],
            "surfaced_major_wins_mean": [1.0],
            "terminal_capability_mean": [1.2],
        },
    )

    _write_table(
        bundle_path / "outputs" / "family_outcomes.parquet",
        {
            "run_bundle_id": ["test"],
            "experiment_name": ["test"],
            "experimental_condition_id": ["c1"],
            "grouping_namespace": ["initiative_family"],
            "grouping_key": ["flywheel"],
            "grouping_label": ["Flywheel"],
            "initiative_count": [5],
            "aggregation_level": ["seed_run"],
        },
    )

    _write_table(
        bundle_path / "outputs" / "yearly_timeseries.parquet",
        {
            "run_bundle_id": ["test"],
            "experiment_name": ["test"],
            "experimental_condition_id": ["c1"],
            "seed_run_id": ["c1__seed_42"],
            "time_bin_index": [0],
            "grouping_key": ["all"],
            "value_total": [50.0],
            "value_total_cumulative": [50.0],
        },
    )

    _write_table(
        bundle_path / "outputs" / "initiative_outcomes.parquet",
        {
            "run_bundle_id": ["test"],
            "experiment_name": ["test"],
            "experimental_condition_id": ["c1"],
            "seed_run_id": ["c1__seed_42"],
            "initiative_id": ["init-0"],
            "status": ["stopped"],
            "is_major_win_eligible": [False],
            "belief_at_stop": [0.3],
        },
    )

    _write_table(
        bundle_path / "outputs" / "diagnostics.parquet",
        {
            "run_bundle_id": ["test"],
            "experiment_name": ["test"],
            "experimental_condition_id": ["c1"],
            "diagnostic_group": ["right_tail"],
            "diagnostic_name": ["false_stop_rate"],
            "metric_value": [0.5],
        },
    )

    _write_table(
        bundle_path / "outputs" / "event_log.parquet",
        {
            "run_bundle_id": ["test"],
            "experiment_name": ["test"],
            "experimental_condition_id": ["c1"],
            "seed_run_id": ["c1__seed_42"],
            "tick": [5],
            "event_type": ["initiative_stopped"],
            "initiative_id": ["init-0"],
        },
    )

    # Derived tables.
    _write_table(
        bundle_path / "derived" / "pairwise_deltas.parquet",
        {
            "comparison_name": ["test"],
        },
    )
    _write_table(
        bundle_path / "derived" / "representative_runs.parquet",
        {
            "seed_run_id": ["c1__seed_42"],
        },
    )
    _write_table(
        bundle_path / "derived" / "enabler_coupling.parquet",
        {
            "seed_run_id": ["c1__seed_42"],
        },
    )

    # Report files.
    (bundle_path / "report" / "index.html").write_text("<html></html>")
    (bundle_path / "report" / "report.md").write_text("# Report")

    # Figures.
    for fig in [
        "value_by_year_stacked.png",
        "cumulative_value_by_year.png",
        "surfaced_major_wins_by_year.png",
        "tradeoff_frontier.png",
        "terminal_capability.png",
        "rt_survival_curves.png",
        "enabler_dashboard.png",
    ]:
        (bundle_path / "figures" / fig).write_bytes(b"\x89PNG")


def _write_table(path: Path, columns: dict) -> None:
    """Write a minimal Parquet table."""
    table = pa.table(columns)
    pq.write_table(table, str(path))


# ============================================================================
# Tests
# ============================================================================


class TestValidateBundle:
    """Tests for validate_bundle()."""

    def test_valid_bundle_passes(self, tmp_path: Path) -> None:
        """A complete minimal bundle passes validation."""
        bundle = tmp_path / "bundle"
        _create_minimal_valid_bundle(bundle)
        result = validate_bundle(bundle)
        assert result.passed, f"Errors: {result.errors}"

    def test_missing_manifest(self, tmp_path: Path) -> None:
        """Missing manifest.json is detected."""
        bundle = tmp_path / "empty_bundle"
        bundle.mkdir()
        result = validate_bundle(bundle)
        assert not result.passed
        assert any("manifest.json is missing" in e for e in result.errors)

    def test_invalid_manifest_json(self, tmp_path: Path) -> None:
        """Invalid JSON in manifest.json is detected."""
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "manifest.json").write_text("not json{{{")
        result = validate_bundle(bundle)
        assert not result.passed
        assert any("not valid JSON" in e for e in result.errors)

    def test_missing_required_field(self, tmp_path: Path) -> None:
        """Missing required manifest field is detected."""
        bundle = tmp_path / "bundle"
        _create_minimal_valid_bundle(bundle)
        # Remove a required field.
        manifest = json.loads((bundle / "manifest.json").read_text())
        del manifest["schema_version"]
        with (bundle / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        result = validate_bundle(bundle)
        assert not result.passed
        assert any("schema_version" in e for e in result.errors)

    def test_seed_count_mismatch(self, tmp_path: Path) -> None:
        """seed_count != len(world_seeds) is detected."""
        bundle = tmp_path / "bundle"
        _create_minimal_valid_bundle(bundle)
        manifest = json.loads((bundle / "manifest.json").read_text())
        manifest["seed_count"] = 5  # Mismatch: world_seeds has 1 entry.
        with (bundle / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        result = validate_bundle(bundle)
        assert not result.passed
        assert any("seed_count" in e for e in result.errors)

    def test_missing_required_table(self, tmp_path: Path) -> None:
        """Missing canonical table is detected."""
        bundle = tmp_path / "bundle"
        _create_minimal_valid_bundle(bundle)
        (bundle / "outputs" / "seed_runs.parquet").unlink()

        result = validate_bundle(bundle)
        assert not result.passed
        assert any("seed_runs.parquet" in e for e in result.errors)

    def test_missing_column_in_table(self, tmp_path: Path) -> None:
        """Missing required column in a table is detected."""
        bundle = tmp_path / "bundle"
        _create_minimal_valid_bundle(bundle)
        # Overwrite seed_runs with a table missing 'total_value'.
        _write_table(
            bundle / "outputs" / "seed_runs.parquet",
            {
                "run_bundle_id": ["test"],
                "experiment_name": ["test"],
                "experimental_condition_id": ["c1"],
                "seed_run_id": ["c1__seed_42"],
                "world_seed": [42],
                # total_value intentionally omitted.
                "status": ["completed"],
            },
        )

        result = validate_bundle(bundle)
        assert not result.passed
        assert any("total_value" in e for e in result.errors)

    def test_missing_report_file(self, tmp_path: Path) -> None:
        """Missing report file is detected."""
        bundle = tmp_path / "bundle"
        _create_minimal_valid_bundle(bundle)
        (bundle / "report" / "index.html").unlink()

        result = validate_bundle(bundle)
        assert not result.passed
        assert any("index.html" in e for e in result.errors)

    def test_negative_wall_clock(self, tmp_path: Path) -> None:
        """Negative wall_clock_seconds_total is detected."""
        bundle = tmp_path / "bundle"
        _create_minimal_valid_bundle(bundle)
        manifest = json.loads((bundle / "manifest.json").read_text())
        manifest["telemetry"]["wall_clock_seconds_total"] = -1.0
        with (bundle / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        result = validate_bundle(bundle)
        assert not result.passed
        assert any("negative" in e for e in result.errors)

    def test_validation_result_frozen(self) -> None:
        """ValidationResult is frozen."""
        result = ValidationResult(passed=True, errors=(), warnings=())
        with pytest.raises(AttributeError):
            result.passed = False  # type: ignore[misc]
