#!/usr/bin/env python
"""Model 1 calibration acceptance-criteria check.

Reads a Model 1 campaign bundle and evaluates the four Phase 1.3
acceptance criteria from docs/implementation/2026-06-10 Repo
Improvement Plan.md:

  (a) Quick-win intake discipline: fewer than 10% of quick-win draws
      enter below the Balanced intake floor (0.35). "Quick win" must
      mean well-understood, mostly-fundable work.
  (b) Right-tail opacity: major-win-eligible right-tails are NOT
      obvious at intake — their intake-belief distribution materially
      overlaps the non-eligible distribution. Quantified as: at least
      25% of eligible right-tails enter below the 75th percentile of
      non-eligible right-tail intake beliefs.
  (c) The hard decision exists: the kill-a-gem error occurs under at
      least one archetype AND nonzero major wins occur under at least
      one archetype, aggregated across seeds. The error is counted in
      both forms — false rejects (major-win-eligible right-tails never
      staffed; the omission error the intake floor creates) and
      mid-flight false stops (eligible right-tails stopped while
      active). Mid-flight false stops are reported but structurally
      near-zero at M1: an EMA belief mean-reverts upward toward high
      latent quality and never crosses a level-threshold stop rule.
      See the improvement plan Phase 1 (criterion revision 2026-06-10).
  (d) Regimes are distinguishable: the three archetypes' mean total
      value are not all within 1% of each other.

Exit code 0 when all criteria pass, 1 otherwise. Chosen calibration
values and rationale are recorded in docs/design/calibration_note.md.

Usage:
    python scripts/model1_calibration_check.py <model1_bundle_dir>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pyarrow.parquet as pq

# The Balanced archetype's intake floor — the reference bar for
# criterion (a). Kept in sync with make_model1_balanced_governance_config.
BALANCED_INTAKE_FLOOR = 0.35


def percentile(sorted_values: list[float], fraction: float) -> float:
    """Nearest-rank percentile of a pre-sorted list."""
    if not sorted_values:
        raise ValueError("percentile of empty list")
    index = min(int(fraction * len(sorted_values)), len(sorted_values) - 1)
    return sorted_values[index]


def check_bundle(bundle_dir: Path) -> int:
    """Evaluate all four criteria; print verdicts; return exit code."""
    outcomes = pq.read_table(bundle_dir / "outputs" / "initiative_outcomes.parquet").to_pylist()
    seed_runs = pq.read_table(bundle_dir / "outputs" / "seed_runs.parquet").to_pylist()

    failures: list[str] = []

    # ── Criterion (a): quick-win intake discipline ──────────────────
    quick_wins = [r for r in outcomes if r["initiative_family"] == "quick_win"]
    qw_beliefs = [
        r["initial_quality_belief"] for r in quick_wins if r["initial_quality_belief"] is not None
    ]
    below_floor = sum(1 for b in qw_beliefs if b < BALANCED_INTAKE_FLOOR)
    below_fraction = below_floor / len(qw_beliefs) if qw_beliefs else 1.0
    a_pass = below_fraction < 0.10
    print(
        f"(a) Quick-win discipline: {below_fraction:.1%} of {len(qw_beliefs)} "
        f"QW draws below floor {BALANCED_INTAKE_FLOOR} "
        f"(target < 10%) -> {'PASS' if a_pass else 'FAIL'}"
    )
    if not a_pass:
        failures.append("(a) quick-win Beta puts too many draws below the floor")

    # ── Criterion (b): right-tail opacity at intake ──────────────────
    right_tails = [r for r in outcomes if r["initiative_family"] == "right_tail"]
    eligible_beliefs = sorted(
        r["initial_quality_belief"]
        for r in right_tails
        if r["is_major_win_eligible"] and r["initial_quality_belief"] is not None
    )
    noneligible_beliefs = sorted(
        r["initial_quality_belief"]
        for r in right_tails
        if not r["is_major_win_eligible"] and r["initial_quality_belief"] is not None
    )
    if eligible_beliefs and noneligible_beliefs:
        noneligible_p75 = percentile(noneligible_beliefs, 0.75)
        overlap_fraction = sum(1 for b in eligible_beliefs if b < noneligible_p75) / len(
            eligible_beliefs
        )
        eligible_mean = sum(eligible_beliefs) / len(eligible_beliefs)
        noneligible_mean = sum(noneligible_beliefs) / len(noneligible_beliefs)
        b_pass = overlap_fraction >= 0.25
        print(
            f"(b) Right-tail opacity: {len(eligible_beliefs)} eligible "
            f"(mean intake belief {eligible_mean:.2f}) vs "
            f"{len(noneligible_beliefs)} non-eligible (mean {noneligible_mean:.2f}); "
            f"{overlap_fraction:.0%} of eligible below non-eligible p75 "
            f"{noneligible_p75:.2f} (target >= 25%) -> {'PASS' if b_pass else 'FAIL'}"
        )
        if not b_pass:
            failures.append("(b) eligible right-tails are still obvious at intake")
    else:
        print(
            f"(b) Right-tail opacity: UNMEASURABLE — eligible={len(eligible_beliefs)}, "
            f"non-eligible={len(noneligible_beliefs)}"
        )
        failures.append("(b) no eligible right-tails in the pool to measure")

    # ── Criterion (c): the hard decision occurs ───────────────────────
    # Mid-flight false stops, from seed_runs (engine-computed metric).
    stops_by_condition: dict[str, int] = {}
    wins_by_condition: dict[str, int] = {}
    for row in seed_runs:
        condition = row["experimental_condition_id"]
        stops_by_condition[condition] = stops_by_condition.get(condition, 0) + int(
            row["right_tail_stopped_eligible_count"] or 0
        )
        wins_by_condition[condition] = wins_by_condition.get(condition, 0) + int(
            row["surfaced_major_wins"] or 0
        )
    # False rejects, from initiative outcomes: eligible right-tails
    # that never received a team across the whole run (omission form
    # of the kill-a-gem error).
    rejects_by_condition: dict[str, int] = {}
    for row in right_tails:
        if row["is_major_win_eligible"] and row["staffed_ticks_total"] == 0:
            condition = row["experimental_condition_id"]
            rejects_by_condition[condition] = rejects_by_condition.get(condition, 0) + 1

    any_false_stops = any(v > 0 for v in stops_by_condition.values())
    any_false_rejects = any(v > 0 for v in rejects_by_condition.values())
    any_wins = any(v > 0 for v in wins_by_condition.values())
    c_pass = (any_false_stops or any_false_rejects) and any_wins
    print(
        f"(c) Hard decision exists: eligible-RT false rejects "
        f"{rejects_by_condition}, mid-flight false stops "
        f"{stops_by_condition} (structurally ~0 at M1), major wins "
        f"{wins_by_condition} -> {'PASS' if c_pass else 'FAIL'}"
    )
    if not c_pass:
        failures.append(
            "(c) "
            + (
                "no kill-a-gem errors in either form"
                if not (any_false_stops or any_false_rejects)
                else ""
            )
            + (" and " if not (any_false_stops or any_false_rejects) and not any_wins else "")
            + ("no major wins anywhere" if not any_wins else "")
        )

    # ── Criterion (d): regimes distinguishable ────────────────────────
    value_sums: dict[str, list[float]] = {}
    for row in seed_runs:
        value_sums.setdefault(row["experimental_condition_id"], []).append(row["total_value"])
    means = {c: sum(v) / len(v) for c, v in value_sums.items()}
    mean_values = list(means.values())
    spread = (max(mean_values) - min(mean_values)) / max(mean_values)
    d_pass = spread > 0.01
    print(
        f"(d) Regime spread: condition mean values "
        f"{ {c: round(m, 1) for c, m in means.items()} }, "
        f"relative spread {spread:.1%} (target > 1%) -> {'PASS' if d_pass else 'FAIL'}"
    )
    if not d_pass:
        failures.append("(d) archetype outcomes are indistinguishable")

    print()
    if failures:
        print(f"CALIBRATION CHECK FAILED ({len(failures)}):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("CALIBRATION CHECK PASSED: all four criteria met.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_dir", type=Path, help="Model 1 campaign bundle directory")
    args = parser.parse_args()
    return check_bundle(args.bundle_dir)


if __name__ == "__main__":
    sys.exit(main())
