#!/usr/bin/env python
"""Smoke baseline check for the canonical preset.

Runs the canonical full-model preset (balanced_incumbent environment,
balanced operating policy) for the pinned smoke seeds and compares
headline metrics against the tracked baseline in
``scripts/smoke_baseline.json``.

Purpose (per docs/implementation/2026-06-10 Repo Improvement Plan.md,
Phase 0.1): every change to the engine, presets, or policies must end
with an explained delta. The simulator is fully deterministic (pinned
seeds, per-initiative CRN substreams), so any drift in these metrics
is caused by a code or configuration change — never by randomness.
When a change intentionally shifts behavior, update the baseline JSON
in the same commit and record the before/after in the improvement
plan's Phase log.

Usage:
    python scripts/smoke_check.py                # check against baseline
    python scripts/smoke_check.py --write        # rewrite baseline from current code

Exit codes: 0 = all metrics match, 1 = drift detected (or missing baseline).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from primordial_soup.runner import run_single_regime
from primordial_soup.workbench import (
    RunDesignSpec,
    make_policy,
    resolve_run_design,
    validate_run_design,
)

if TYPE_CHECKING:
    from primordial_soup.reporting import RunResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# The canonical preset YAML — the exact file users run via
# scripts/run_design.py. The smoke check deliberately goes through the
# same workbench resolution path (RunDesignSpec -> resolve_run_design)
# rather than the make_balanced_config() Python factory, because the
# two entry points are not guaranteed to produce identical
# configurations and the YAML path is the one real runs use.
CANONICAL_PRESET = (
    Path(__file__).parent.parent / "templates" / "presets" / "balanced_incumbent_balanced.yaml"
)

# Location of the tracked baseline file, next to this script.
BASELINE_PATH = Path(__file__).parent / "smoke_baseline.json"

# Relative tolerance for float comparison. The simulator is
# deterministic, so this only absorbs floating-point representation
# differences across platforms — not behavioral drift.
RELATIVE_TOLERANCE = 1e-6


def compute_seed_metrics(result: RunResult) -> dict[str, float]:
    """Extract the headline smoke metrics from a single seed's RunResult.

    Returns a flat dict of metric name -> numeric value. Counts are
    stored as floats so the JSON round-trip and tolerance comparison
    are uniform across all metrics.
    """
    lump = result.value_by_channel.completion_lump_value
    residual = result.value_by_channel.residual_value
    total = result.cumulative_value_total

    # Residual share of total value. Guard the empty-run edge case
    # (total == 0) rather than dividing by zero.
    residual_share = residual / total if total > 0 else 0.0

    false_stop_rate = result.right_tail_false_stop_profile.right_tail_false_stop_rate

    return {
        "cumulative_value_total": total,
        "cumulative_value_total_discounted": result.cumulative_value_total_discounted,
        "completion_lump_value": lump,
        "residual_value": residual,
        "residual_share": residual_share,
        "major_win_count": float(result.major_win_profile.major_win_count),
        "terminal_capability": result.terminal_capability_t,
        "idle_team_tick_fraction": result.idle_capacity_profile.idle_team_tick_fraction,
        "ramp_labor_fraction": result.ramp_labor_fraction,
        # None false-stop rate (no eligible right-tails) is recorded
        # as -1.0 so the JSON stays flat and comparisons stay numeric.
        "right_tail_false_stop_rate": (false_stop_rate if false_stop_rate is not None else -1.0),
        "stop_count": float(
            len(result.stop_event_log) if result.stop_event_log is not None else 0
        ),
    }


def run_smoke_suite() -> dict[str, dict[str, float]]:
    """Run the canonical preset YAML for its configured seeds.

    Loads templates/presets/balanced_incumbent_balanced.yaml through
    the same workbench path scripts/run_design.py uses, runs every
    seed, and returns a mapping of seed (as string, for JSON
    stability) to its metric dict, plus a "mean" entry averaging each
    metric across seeds.
    """
    data = yaml.safe_load(CANONICAL_PRESET.read_text(encoding="utf-8"))
    spec = RunDesignSpec.from_dict(data)
    validate_run_design(spec)
    resolved = resolve_run_design(spec)

    per_seed: dict[str, dict[str, float]] = {}
    for sim_config in resolved.simulation_configs:
        logger.info(
            "Smoke run: seed=%d (canonical preset %s)",
            sim_config.world_seed,
            CANONICAL_PRESET.name,
        )
        policy = make_policy(resolved.governance)
        result, _world_state = run_single_regime(sim_config, policy)
        per_seed[str(sim_config.world_seed)] = compute_seed_metrics(result)

    # Mean across seeds for each metric, for at-a-glance drift checks.
    seed_count = len(per_seed)
    metric_names = next(iter(per_seed.values())).keys()
    per_seed["mean"] = {
        name: sum(metrics[name] for key, metrics in per_seed.items() if key != "mean") / seed_count
        for name in metric_names
    }
    return per_seed


def values_match(expected: float, actual: float) -> bool:
    """Compare two metric values with relative tolerance.

    Uses absolute tolerance near zero (where relative tolerance is
    meaningless) and relative tolerance elsewhere.
    """
    if expected == actual:
        return True
    scale = max(abs(expected), abs(actual))
    if scale < 1e-12:
        return True
    return abs(expected - actual) / scale <= RELATIVE_TOLERANCE


def compare_to_baseline(
    baseline: dict[str, dict[str, float]],
    current: dict[str, dict[str, float]],
) -> list[str]:
    """Return a list of human-readable drift descriptions (empty = pass)."""
    drift: list[str] = []
    for seed_key, expected_metrics in baseline.items():
        actual_metrics = current.get(seed_key)
        if actual_metrics is None:
            drift.append(f"seed {seed_key}: missing from current run")
            continue
        for name, expected in expected_metrics.items():
            actual = actual_metrics.get(name)
            if actual is None:
                drift.append(f"seed {seed_key} / {name}: missing from current run")
            elif not values_match(expected, actual):
                drift.append(
                    f"seed {seed_key} / {name}: baseline {expected:.6f} "
                    f"-> current {actual:.6f} "
                    f"(delta {actual - expected:+.6f})"
                )
    return drift


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Rewrite scripts/smoke_baseline.json from the current code. "
            "Only do this for an intentional behavior change, and record "
            "the before/after in the improvement plan's Phase log."
        ),
    )
    args = parser.parse_args()

    current = run_smoke_suite()

    if args.write:
        BASELINE_PATH.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        logger.info("Baseline written to %s", BASELINE_PATH)
        print(f"Baseline written: {BASELINE_PATH}")
        return 0

    if not BASELINE_PATH.exists():
        print(f"FAIL: no baseline at {BASELINE_PATH}. " "Run with --write to create one.")
        return 1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    drift = compare_to_baseline(baseline, current)

    if drift:
        print(f"DRIFT DETECTED ({len(drift)} metric(s)):")
        for line in drift:
            print(f"  {line}")
        print(
            "\nIf this drift is intentional, rerun with --write and record "
            "the change in the improvement plan's Phase log."
        )
        return 1

    print(f"PASS: all smoke metrics match baseline ({BASELINE_PATH.name}).")
    mean = current["mean"]
    print(
        f"  mean value {mean['cumulative_value_total']:.2f} | "
        f"major wins {mean['major_win_count']:.1f} | "
        f"residual share {mean['residual_share']:.3f} | "
        f"ramp {mean['ramp_labor_fraction']:.3f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
