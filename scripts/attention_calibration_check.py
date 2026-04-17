#!/usr/bin/env python
"""Executive attention calibration check.

Runs a small number of seeds for each of the three named governance
archetypes at the current baseline attention budget, and reports
whether the budget is binding.

Usage:
    python scripts/attention_calibration_check.py
    python scripts/attention_calibration_check.py --seeds 5
    python scripts/attention_calibration_check.py --family balanced_incumbent

The script produces a per-archetype summary of attention utilization
and a final verdict classifying budget-binding status.

Stage 2, Step 2.1 of the implementation plan
(docs/implementation/2026-03-16 Implementation Plan.md).
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import TYPE_CHECKING, Any

from primordial_soup.policy import (
    AggressiveStopLossPolicy,
    BalancedPolicy,
    GovernancePolicy,
    PatientMoonshotPolicy,
)
from primordial_soup.presets import (
    EnvironmentFamilyName,
    make_aggressive_stop_loss_config,
    make_balanced_config,
    make_patient_moonshot_config,
)
from primordial_soup.runner import run_single_regime

if TYPE_CHECKING:
    from primordial_soup.reporting import RunResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ============================================================================
# Archetype definitions
# ============================================================================

# Each entry: (label, config factory, policy instance).
ARCHETYPES: list[tuple[str, Any, GovernancePolicy]] = [
    ("Balanced", make_balanced_config, BalancedPolicy()),
    ("Aggressive Stop-Loss", make_aggressive_stop_loss_config, AggressiveStopLossPolicy()),
    ("Patient Moonshot", make_patient_moonshot_config, PatientMoonshotPolicy()),
]


# ============================================================================
# Analysis helpers
# ============================================================================


def _analyze_attention(
    result: RunResult,
) -> dict[str, Any]:
    """Extract attention utilization metrics from a single run result.

    Requires record_per_tick_logs=True (the baseline reporting config
    enables this). Returns a dictionary of attention metrics.

    Args:
        result: RunResult from run_single_regime() with per-tick logs.

    Returns:
        Dictionary with per-initiative and portfolio attention metrics.
    """
    per_init_records = result.per_initiative_tick_records
    portfolio_records = result.portfolio_tick_records

    if per_init_records is None or portfolio_records is None:
        return {
            "error": "Per-tick logs not recorded. Enable record_per_tick_logs.",
        }

    budget = result.manifest.resolved_configuration.model.exec_attention_budget

    # Per-initiative attention statistics.
    per_init_attentions = [r.exec_attention_a_t for r in per_init_records]
    mean_per_init_attention = (
        sum(per_init_attentions) / len(per_init_attentions) if per_init_attentions else 0.0
    )
    max_per_init_attention = max(per_init_attentions) if per_init_attentions else 0.0

    # Portfolio-level attention utilization per tick.
    # utilization = total_allocated / budget
    tick_utilizations = [
        r.total_exec_attention_allocated / budget if budget > 0 else 0.0 for r in portfolio_records
    ]
    mean_utilization = (
        sum(tick_utilizations) / len(tick_utilizations) if tick_utilizations else 0.0
    )
    max_utilization = max(tick_utilizations) if tick_utilizations else 0.0

    # Count ticks where utilization >= 95% of budget (near-binding).
    near_binding_threshold = 0.95
    near_binding_ticks = sum(1 for u in tick_utilizations if u >= near_binding_threshold)

    # Count ticks where utilization >= 99.9% (effectively binding).
    binding_threshold = 0.999
    binding_ticks = sum(1 for u in tick_utilizations if u >= binding_threshold)

    return {
        "budget": budget,
        "mean_per_init_attention": mean_per_init_attention,
        "max_per_init_attention": max_per_init_attention,
        "mean_utilization": mean_utilization,
        "max_utilization": max_utilization,
        "near_binding_ticks": near_binding_ticks,
        "binding_ticks": binding_ticks,
        "total_ticks": len(tick_utilizations),
    }


def _classify_binding(
    archetype_results: dict[str, list[dict[str, Any]]],
) -> str:
    """Classify budget-binding status across archetypes.

    Returns one of three verdicts:
    - "Budget is non-binding"
    - "Budget is always binding"
    - "Budget binds in some regimes"

    Args:
        archetype_results: Map from archetype label to list of per-seed
            attention metric dicts.

    Returns:
        Verdict string.
    """
    any_binding = False
    all_binding = True

    for _label, seed_results in archetype_results.items():
        archetype_has_binding = any(r.get("binding_ticks", 0) > 0 for r in seed_results)
        if archetype_has_binding:
            any_binding = True
        else:
            all_binding = False

    if all_binding and any_binding:
        return "Budget is always binding"
    elif any_binding:
        return "Budget binds in some regimes"
    else:
        return "Budget is non-binding"


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Executive attention calibration check.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=3,
        help="Number of seeds per archetype (default: 3).",
    )
    parser.add_argument(
        "--family",
        type=str,
        default="balanced_incumbent",
        help="Environment family (default: balanced_incumbent).",
    )
    args = parser.parse_args()

    seed_count: int = args.seeds
    family: EnvironmentFamilyName = args.family
    seeds = list(range(42, 42 + seed_count))

    print()
    print("=" * 70)
    print("Executive Attention Calibration Check")
    print("=" * 70)
    print(f"  Environment family: {family}")
    print(f"  Seeds: {seeds}")
    print()

    t0 = time.time()

    # Collect results per archetype.
    archetype_results: dict[str, list[dict[str, Any]]] = {}

    for label, config_factory, policy in ARCHETYPES:
        print(f"  Running {label}...")
        seed_metrics: list[dict[str, Any]] = []
        for seed in seeds:
            config = config_factory(seed, family)
            result, _ = run_single_regime(config, policy)
            metrics = _analyze_attention(result)
            metrics["world_seed"] = seed
            seed_metrics.append(metrics)
            logger.info("    %s seed %d done", label, seed)
        archetype_results[label] = seed_metrics

    # --- Print results ---
    print()
    for label, seed_metrics in archetype_results.items():
        print("-" * 70)
        print(f"  {label}")
        print("-" * 70)

        budget = seed_metrics[0].get("budget", "?")
        print(f"    Budget: {budget}")
        print()

        # Per-seed detail.
        for m in seed_metrics:
            if "error" in m:
                print(f"    seed {m.get('world_seed', '?')}: {m['error']}")
                continue
            print(
                f"    seed {m['world_seed']}: "
                f"utilization mean={m['mean_utilization']:.3f} "
                f"max={m['max_utilization']:.3f}  |  "
                f"per-init attn mean={m['mean_per_init_attention']:.4f} "
                f"max={m['max_per_init_attention']:.4f}  |  "
                f"near-binding ticks={m['near_binding_ticks']}/{m['total_ticks']} "
                f"binding ticks={m['binding_ticks']}/{m['total_ticks']}"
            )

        # Aggregate across seeds.
        n = len(seed_metrics)
        avg_util = sum(m["mean_utilization"] for m in seed_metrics) / n
        max_util = max(m["max_utilization"] for m in seed_metrics)
        total_binding = sum(m["binding_ticks"] for m in seed_metrics)
        total_near_binding = sum(m["near_binding_ticks"] for m in seed_metrics)
        total_ticks = sum(m["total_ticks"] for m in seed_metrics)
        print()
        print(f"    Aggregate ({n} seeds):")
        print(f"      Mean utilization: {avg_util:.3f}")
        print(f"      Max utilization:  {max_util:.3f}")
        print(f"      Near-binding ticks (>=95%): " f"{total_near_binding}/{total_ticks}")
        print(f"      Binding ticks (>=99.9%):    " f"{total_binding}/{total_ticks}")
        print()

    # --- Verdict ---
    verdict = _classify_binding(archetype_results)
    print("=" * 70)
    print(f"  VERDICT: {verdict}")
    print("=" * 70)

    if verdict == "Budget is non-binding":
        print()
        print("  The current exec_attention_budget is not binding for any")
        print("  archetype. Attention allocation is determined by governance")
        print("  policy, not by engine-side budget clamping. This is the")
        print("  desired state for the canonical governance sweep.")
    elif verdict == "Budget binds in some regimes":
        print()
        print("  The budget binds in at least one archetype but not all.")
        print("  This may be acceptable if the binding occurs only in")
        print("  regimes where attention scarcity is part of the study")
        print("  question (RQ1/RQ7). If the main governance sweep should")
        print("  have a non-binding budget, consider increasing")
        print("  exec_attention_budget.")
    else:
        print()
        print("  The budget is always binding. Attention allocation is")
        print("  determined by budget clamping, not by governance policy.")
        print("  Increase exec_attention_budget before running the canonical")
        print("  governance sweep.")
    print()

    elapsed = time.time() - t0
    print(f"Elapsed: {elapsed:.0f}s")
    print()


if __name__ == "__main__":
    main()
