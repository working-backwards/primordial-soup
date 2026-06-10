"""Tests for scripts/compare_bundles.py (paired bundle comparison).

The compare script is a standalone tool under scripts/, so it is
loaded by file path rather than imported as a package module.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "compare_bundles.py"


def _load_script_module():
    """Load scripts/compare_bundles.py as a module by file path."""
    spec = importlib.util.spec_from_file_location("compare_bundles", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare_bundles_module = _load_script_module()


def _write_bundle(
    bundle_dir: Path,
    rows: list[dict],
) -> Path:
    """Write a minimal synthetic bundle containing only seed_runs.parquet."""
    outputs = bundle_dir / "outputs"
    outputs.mkdir(parents=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, outputs / "seed_runs.parquet")
    return bundle_dir


def _seed_row(
    *,
    condition: str = "cond-a",
    world_seed: int = 42,
    total_value: float = 100.0,
    right_tail_false_stop_rate: float | None = 0.0,
) -> dict:
    """Build a minimal seed-run row with the columns the script reads."""
    return {
        "experimental_condition_id": condition,
        "world_seed": world_seed,
        "total_value": total_value,
        "right_tail_false_stop_rate": right_tail_false_stop_rate,
    }


def test_identical_bundles_report_zero_deltas(tmp_path, capsys):
    rows = [_seed_row(world_seed=42), _seed_row(world_seed=43)]
    bundle_a = _write_bundle(tmp_path / "a", rows)
    bundle_b = _write_bundle(tmp_path / "b", rows)

    exit_code = compare_bundles_module.compare_bundles(bundle_a, bundle_b)

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Paired runs: 2" in output
    assert "+0.0000" in output
    # No nonzero-delta markers for identical bundles.
    assert "*" not in output.split("(* = nonzero")[0].split("total_value")[1]


def test_paired_delta_is_b_minus_a(tmp_path, capsys):
    bundle_a = _write_bundle(tmp_path / "a", [_seed_row(total_value=100.0)])
    bundle_b = _write_bundle(tmp_path / "b", [_seed_row(total_value=130.0)])

    compare_bundles_module.compare_bundles(bundle_a, bundle_b)

    output = capsys.readouterr().out
    assert "+30.0000" in output


def test_unpaired_seeds_are_skipped_with_notice(tmp_path, capsys):
    bundle_a = _write_bundle(tmp_path / "a", [_seed_row(world_seed=42), _seed_row(world_seed=43)])
    bundle_b = _write_bundle(tmp_path / "b", [_seed_row(world_seed=42)])

    compare_bundles_module.compare_bundles(bundle_a, bundle_b)

    output = capsys.readouterr().out
    assert "Paired runs: 1" in output
    assert "A-only: 1" in output


def test_none_metric_values_are_excluded_from_pairing(tmp_path, capsys):
    # False-stop rate is None when a run has no eligible right-tails;
    # such rows must not poison the mean computation.
    bundle_a = _write_bundle(
        tmp_path / "a",
        [
            _seed_row(world_seed=42, right_tail_false_stop_rate=None),
            _seed_row(world_seed=43, right_tail_false_stop_rate=0.5),
        ],
    )
    bundle_b = _write_bundle(
        tmp_path / "b",
        [
            _seed_row(world_seed=42, right_tail_false_stop_rate=None),
            _seed_row(world_seed=43, right_tail_false_stop_rate=0.25),
        ],
    )

    compare_bundles_module.compare_bundles(bundle_a, bundle_b)

    output = capsys.readouterr().out
    # Only seed 43 pairs numerically: mean A 0.5, mean B 0.25, delta -0.25.
    assert "-0.2500" in output


def test_no_shared_runs_returns_error_code(tmp_path, capsys):
    bundle_a = _write_bundle(tmp_path / "a", [_seed_row(world_seed=1)])
    bundle_b = _write_bundle(tmp_path / "b", [_seed_row(world_seed=2)])

    exit_code = compare_bundles_module.compare_bundles(bundle_a, bundle_b)

    assert exit_code == 1
    assert "nothing to compare" in capsys.readouterr().out


def test_missing_parquet_raises_with_helpful_message(tmp_path):
    empty_dir = tmp_path / "not_a_bundle"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="run bundle"):
        compare_bundles_module.load_seed_runs(empty_dir)
