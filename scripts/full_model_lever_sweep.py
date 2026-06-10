#!/usr/bin/env python
"""Full-model one-lever-at-a-time governance sweep.

Varies a single governance lever at a time against the canonical
balanced_incumbent full-model configuration (improvement plan Phase
3.2 — the full-model extension of the Model 1 sweep). Each condition
differs from the base in exactly one parameter, so the paired-CRN
deltas (now with 95% confidence intervals in the headline table) are
attributable to that lever alone.

Swept levers:
  - intake_belief_threshold: None, 0.20, 0.35, 0.50
  - confidence_decline_threshold: 0.08, 0.30, 0.40

Usage:
    python scripts/full_model_lever_sweep.py
    python scripts/full_model_lever_sweep.py --seeds 10
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import time
from pathlib import Path

from primordial_soup.presets import make_balanced_config
from primordial_soup.run_bundle import (
    ExperimentalConditionRecord,
    ExperimentalConditionSpec,
    ExperimentSpec,
    SeedRunRecord,
    create_run_bundle,
    extract_initiative_final_states,
)
from primordial_soup.runner import run_single_regime
from primordial_soup.workbench import make_policy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_SEED_COUNT = 30
SEED_BASE = 42

# Sweep definition: (lever_name, field_name, values). One condition
# per value; every other parameter stays at the Balanced base. The
# base values (floor 0.35, confidence 0.30) appear in their own sweeps
# so each sweep contains the baseline for paired comparison.
SWEEPS: tuple[tuple[str, str, tuple], ...] = (
    (
        "intake_floor",
        "intake_belief_threshold",
        (None, 0.20, 0.35, 0.50),
    ),
    (
        "confidence_decline",
        "confidence_decline_threshold",
        (0.08, 0.30, 0.40),
    ),
)


def run_lever_sweep(seeds: tuple[int, ...], output_dir: Path) -> Path:
    """Run all sweep conditions and write a single run bundle."""
    conditions: list[tuple[str, str, str, object]] = []
    for lever_label, field_name, values in SWEEPS:
        for value in values:
            value_label = "none" if value is None else f"{value:.2f}".replace(".", "p")
            condition_id = f"fmsweep__{lever_label}__{value_label}"
            conditions.append((condition_id, lever_label, field_name, value))

    total_runs = len(conditions) * len(seeds)
    logger.info(
        "full model lever sweep: %d conditions x %d seeds = %d runs",
        len(conditions),
        len(seeds),
        total_runs,
    )
    sweep_start = time.time()

    condition_records: list[ExperimentalConditionRecord] = []
    run_count = 0

    for condition_id, lever_label, field_name, value in conditions:
        seed_run_records: list[SeedRunRecord] = []
        representative_config = None

        for seed in seeds:
            run_count += 1
            logger.info("  Run %d/%d: %s seed=%d", run_count, total_runs, condition_id, seed)

            # Balanced base with exactly one governance field replaced.
            base_config = make_balanced_config(seed)
            governance = dataclasses.replace(base_config.governance, **{field_name: value})
            config = dataclasses.replace(base_config, governance=governance)
            representative_config = config

            policy = make_policy(config.governance)
            run_result, world_state = run_single_regime(config, policy)

            seed_run_records.append(
                SeedRunRecord(
                    world_seed=seed,
                    run_result=run_result,
                    initiative_final_states=extract_initiative_final_states(world_state),
                    initiative_configs=run_result.manifest.resolved_initiatives,
                )
            )

        assert representative_config is not None

        display = f"{lever_label} = {value}"
        condition_records.append(
            ExperimentalConditionRecord(
                condition_spec=ExperimentalConditionSpec(
                    experimental_condition_id=condition_id,
                    environmental_conditions_id="full_model",
                    environmental_conditions_name="full model",
                    governance_architecture_id="default",
                    governance_architecture_name="Default",
                    operating_policy_id=condition_id,
                    operating_policy_name=display,
                    governance_regime_label=display,
                ),
                seed_run_records=tuple(seed_run_records),
                simulation_config=representative_config,
            )
        )

    experiment_spec = ExperimentSpec(
        experiment_name="full_model_lever_sweep",
        title="Full-Model One-Lever-at-a-Time Sweep",
        description=(
            "Single-lever sweeps against the canonical balanced_incumbent "
            "full-model base: "
            "intake_belief_threshold in {None, 0.20, 0.35, 0.50} and "
            "confidence_decline_threshold in {0.08, 0.30, 0.40}. Each "
            "condition differs from the base in exactly one parameter, "
            "so paired deltas are attributable to that lever alone."
        ),
        world_seeds=seeds,
        condition_records=tuple(condition_records),
        script_name="scripts/full_model_lever_sweep.py",
        study_phase="evaluation",
        baseline_condition_id="fmsweep__intake_floor__0p35",
    )

    bundle_path = create_run_bundle(experiment_spec, output_dir)
    logger.info("Sweep complete in %.1fs. Bundle: %s", time.time() - sweep_start, bundle_path)
    return bundle_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEED_COUNT)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()

    seeds = tuple(range(SEED_BASE, SEED_BASE + args.seeds))
    bundle_path = run_lever_sweep(seeds, args.output_dir)
    print(f"Run bundle written to {bundle_path}")


if __name__ == "__main__":
    main()
