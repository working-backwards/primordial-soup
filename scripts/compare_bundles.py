#!/usr/bin/env python
"""Paired comparison of two run bundles' headline metrics.

Reads ``outputs/seed_runs.parquet`` from two run bundles and prints
per-metric paired deltas, joined on (experimental_condition_id,
world_seed). Because the simulator uses common random numbers
(per-initiative MRG32k3a substreams keyed by world_seed), two bundles
that share seeds see identical worlds — so each paired delta is
attributable to the configuration or code change between the bundles,
not to sampling noise.

Purpose (per docs/implementation/2026-06-10 Repo Improvement Plan.md,
Phase 0.2): every model-ladder rung and calibration change ends with a
one-command, clear-answer diff against the previous reference bundle.

Usage:
    python scripts/compare_bundles.py <bundle_dir_A> <bundle_dir_B>
    python scripts/compare_bundles.py results/old_bundle results/new_bundle

Bundle A is treated as the reference ("before"); bundle B as the
candidate ("after"). Deltas are reported as B - A.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pyarrow.parquet as pq

# Headline metrics to compare, in display order. Names must match
# seed_runs.parquet columns (written by tables.py). Metrics absent
# from either bundle are skipped with a notice, so this script keeps
# working as the schema evolves across model-ladder rungs.
HEADLINE_METRICS: tuple[str, ...] = (
    "total_value",
    "cumulative_lump_value",
    "cumulative_residual_value",
    "surfaced_major_wins",
    "terminal_capability",
    "right_tail_completions",
    "right_tail_stops",
    "right_tail_first_attempt_stops",
    "right_tail_refresh_stops",
    "right_tail_eligible_count",
    "right_tail_stopped_eligible_count",
    "right_tail_false_stop_rate",
    "idle_pct",
    "ramp_labor_fraction",
    "mean_absolute_belief_error",
)

# Join keys identifying a paired run across the two bundles.
JOIN_KEYS: tuple[str, ...] = ("experimental_condition_id", "world_seed")


def load_seed_runs(bundle_dir: Path) -> list[dict]:
    """Load seed_runs.parquet from a bundle as a list of row dicts.

    Raises FileNotFoundError with a helpful message when the bundle
    does not look like a run bundle.
    """
    parquet_path = bundle_dir / "outputs" / "seed_runs.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"{parquet_path} not found - is {bundle_dir} a run bundle directory?"
        )
    table = pq.read_table(parquet_path)
    return table.to_pylist()


def index_rows(rows: list[dict]) -> dict[tuple, dict]:
    """Index seed-run rows by the (condition_id, world_seed) join key."""
    indexed: dict[tuple, dict] = {}
    for row in rows:
        key = tuple(row.get(k) for k in JOIN_KEYS)
        indexed[key] = row
    return indexed


def numeric_or_none(value: object) -> float | None:
    """Coerce a parquet cell to float; None stays None."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def compare_bundles(bundle_a: Path, bundle_b: Path) -> int:
    """Print the paired comparison; return process exit code."""
    rows_a = index_rows(load_seed_runs(bundle_a))
    rows_b = index_rows(load_seed_runs(bundle_b))

    shared_keys = sorted(set(rows_a) & set(rows_b), key=str)
    only_a = sorted(set(rows_a) - set(rows_b), key=str)
    only_b = sorted(set(rows_b) - set(rows_a), key=str)

    print(f"Reference (A): {bundle_a}")
    print(f"Candidate (B): {bundle_b}")
    print(f"Paired runs: {len(shared_keys)} " f"(A-only: {len(only_a)}, B-only: {len(only_b)})")
    if only_a:
        print(f"  NOTE: A-only pairs skipped: {only_a}")
    if only_b:
        print(f"  NOTE: B-only pairs skipped: {only_b}")
    if not shared_keys:
        print("No paired (condition, seed) runs in common - nothing to compare.")
        return 1

    # Group shared keys by condition so per-condition means are visible
    # when bundles contain multiple experimental conditions.
    conditions = sorted({key[0] for key in shared_keys})

    exit_code = 0
    for condition in conditions:
        condition_keys = [k for k in shared_keys if k[0] == condition]
        print(f"\n=== Condition: {condition} ({len(condition_keys)} paired seeds) ===")
        header = f"{'metric':<36} {'mean A':>12} {'mean B':>12} {'mean delta':>12}"
        print(header)
        print("-" * len(header))

        for metric in HEADLINE_METRICS:
            values_a: list[float] = []
            values_b: list[float] = []
            for key in condition_keys:
                a_val = numeric_or_none(rows_a[key].get(metric))
                b_val = numeric_or_none(rows_b[key].get(metric))
                # Pair only when both sides have a numeric value (e.g.
                # false-stop rate is None when no eligible right-tails
                # exist on one side).
                if a_val is not None and b_val is not None:
                    values_a.append(a_val)
                    values_b.append(b_val)

            if not values_a:
                # Metric missing or all-None on one side: note and move on.
                in_a = metric in next(iter(rows_a.values()))
                in_b = metric in next(iter(rows_b.values()))
                if not (in_a and in_b):
                    print(f"{metric:<36} {'(absent in ' + ('A' if not in_a else 'B') + ')':>38}")
                else:
                    print(f"{metric:<36} {'(no paired numeric values)':>38}")
                continue

            mean_a = sum(values_a) / len(values_a)
            mean_b = sum(values_b) / len(values_b)
            delta = mean_b - mean_a
            marker = "" if abs(delta) < 1e-12 else "  *"
            print(f"{metric:<36} {mean_a:>12.4f} {mean_b:>12.4f} {delta:>+12.4f}{marker}")

    print(
        "\n(* = nonzero paired delta. Deltas are attributable to the change "
        "between bundles because seeds share common random numbers.)"
    )
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_a", type=Path, help="Reference bundle directory")
    parser.add_argument("bundle_b", type=Path, help="Candidate bundle directory")
    args = parser.parse_args()
    return compare_bundles(args.bundle_a, args.bundle_b)


if __name__ == "__main__":
    sys.exit(main())
