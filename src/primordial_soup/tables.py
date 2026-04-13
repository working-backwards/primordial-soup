"""Canonical and derived Parquet table generation for run bundles.

This module converts experiment results (ExperimentSpec and its
components) into the canonical machine-readable output tables required
by the reporting package specification. Each table has one public
writer function and one internal row-builder function.

All tables are written in Parquet format via pyarrow. Column schemas
are enforced per the spec.

The canonical tables are the analytical substrate of the run bundle.
The HTML report, markdown report, figures, and any later analysis
layer must derive from them rather than reconstructing results from
logs or console text.

Design reference:
    docs/implementation/reporting_package_specification.md
"""

from __future__ import annotations

import json
import logging
import math
from typing import TYPE_CHECKING, Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

if TYPE_CHECKING:
    from pathlib import Path

    from primordial_soup.config import ResolvedInitiativeConfig
    from primordial_soup.run_bundle import (
        ExperimentSpec,
    )

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default time-bin width for yearly timeseries (52 ticks = 1 study year).
TICKS_PER_YEAR = 52

# The four canonical initiative families. Used to ensure zero-count
# families still appear in grouped tables.
CANONICAL_FAMILIES = ("flywheel", "right_tail", "enabler", "quick_win")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _config_map(
    configs: tuple[ResolvedInitiativeConfig, ...],
) -> dict[str, ResolvedInitiativeConfig]:
    """Build initiative_id → config lookup."""
    return {cfg.initiative_id: cfg for cfg in configs}


def _family_label(tag: str | None) -> str:
    """Convert a generation_tag to a human-readable label."""
    if tag is None:
        return "Unknown"
    return tag.replace("_", " ").title()


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a list of row-dicts to a Parquet file.

    Creates parent directories if they don't exist. If rows is empty,
    writes an empty Parquet file.

    Args:
        path: Output file path.
        rows: List of dictionaries, one per row. All dicts must have
            the same keys.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        # Write an empty Parquet file with no columns.
        table = pa.table({})
        pq.write_table(table, str(path))
        return

    # Build column arrays from row dicts.
    columns: dict[str, list[Any]] = {key: [] for key in rows[0]}
    for row in rows:
        for key in columns:
            columns[key].append(row.get(key))

    table = pa.table(columns)
    pq.write_table(table, str(path))


# ===========================================================================
# Table 1: seed_runs.parquet
# ===========================================================================


def _build_seed_run_rows(
    experiment_spec: ExperimentSpec,
) -> list[dict[str, Any]]:
    """Build rows for seed_runs.parquet.

    One row per seed run under one experimental condition.

    Per reporting_package_specification.md §seed_runs.parquet.
    """
    rows: list[dict[str, Any]] = []
    run_bundle_id = experiment_spec.experiment_name

    for cond_rec in experiment_spec.condition_records:
        cond_spec = cond_rec.condition_spec
        config = cond_rec.simulation_config

        for seed_rec in cond_rec.seed_run_records:
            result = seed_rec.run_result
            rtfsp = result.right_tail_false_stop_profile
            timing = result.family_timing

            # first_completion_tick_any: earliest completion across all families.
            first_ticks = [
                t for t in timing.first_completion_tick_by_family.values() if t is not None
            ]
            first_completion_any = min(first_ticks) if first_ticks else None

            # free_teams_mean = idle_team_tick_fraction * team_count.
            # Per plan §Decision 1.
            team_count = config.teams.team_count
            free_teams_mean = result.idle_capacity_profile.idle_team_tick_fraction * team_count

            rows.append(
                {
                    "run_bundle_id": run_bundle_id,
                    "experiment_name": experiment_spec.experiment_name,
                    "experimental_condition_id": cond_spec.experimental_condition_id,
                    "seed_run_id": (
                        f"{cond_spec.experimental_condition_id}__seed_{seed_rec.world_seed}"
                    ),
                    "world_seed": seed_rec.world_seed,
                    # --- Outcome metrics ---
                    "total_value": result.cumulative_value_total,
                    "surfaced_major_wins": result.major_win_profile.major_win_count,
                    "terminal_capability": result.terminal_capability_t,
                    "right_tail_completions": rtfsp.right_tail_completions,
                    "right_tail_stops": rtfsp.right_tail_stops,
                    "right_tail_eligible_count": rtfsp.right_tail_eligible_count,
                    "right_tail_stopped_eligible_count": rtfsp.right_tail_stopped_eligible_count,
                    "right_tail_false_stop_rate": rtfsp.right_tail_false_stop_rate,
                    "idle_pct": result.idle_capacity_profile.idle_team_tick_fraction,
                    "free_teams_mean": free_teams_mean,
                    "peak_capacity": result.max_portfolio_capability_t,
                    # --- Timing markers ---
                    "first_completion_tick_any": first_completion_any,
                    "first_right_tail_completion_tick": (
                        timing.first_completion_tick_by_family.get("right_tail")
                    ),
                    "first_right_tail_stop_tick": timing.first_right_tail_stop_tick,
                    # --- Completeness ---
                    "status": "completed",
                    "completed_ticks": config.time.tick_horizon,
                    "horizon_ticks": config.time.tick_horizon,
                }
            )

    return rows


def write_seed_runs(
    experiment_spec: ExperimentSpec,
    bundle_path: Path,
) -> list[dict[str, Any]]:
    """Write outputs/seed_runs.parquet.

    Returns the rows for reuse by downstream table builders.
    """
    rows = _build_seed_run_rows(experiment_spec)
    _write_parquet(bundle_path / "outputs" / "seed_runs.parquet", rows)
    logger.info("Wrote seed_runs.parquet: %d rows", len(rows))
    return rows


# ===========================================================================
# Table 2: experimental_conditions.parquet
# ===========================================================================


def _build_experimental_condition_rows(
    experiment_spec: ExperimentSpec,
    seed_run_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build rows for experimental_conditions.parquet.

    One row per experimental condition. Aggregated from seed_run_rows.

    Per reporting_package_specification.md §experimental_conditions.parquet.
    """
    # Group seed-run rows by condition.
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for row in seed_run_rows:
        cid = row["experimental_condition_id"]
        by_condition.setdefault(cid, []).append(row)

    rows: list[dict[str, Any]] = []

    for cond_rec in experiment_spec.condition_records:
        cond_spec = cond_rec.condition_spec
        cid = cond_spec.experimental_condition_id
        seed_rows = by_condition.get(cid, [])

        if not seed_rows:
            continue

        # Extract arrays for aggregation.
        values = np.array([r["total_value"] for r in seed_rows])
        wins = np.array([r["surfaced_major_wins"] for r in seed_rows], dtype=float)
        caps = np.array([r["terminal_capability"] for r in seed_rows])
        rt_comp = np.array([r["right_tail_completions"] for r in seed_rows], dtype=float)
        rt_stops = np.array([r["right_tail_stops"] for r in seed_rows], dtype=float)
        # For false-stop rate, filter out None values.
        fsr_values = [
            r["right_tail_false_stop_rate"]
            for r in seed_rows
            if r["right_tail_false_stop_rate"] is not None
        ]
        fsr_mean = float(np.mean(fsr_values)) if fsr_values else None
        idle = np.array([r["idle_pct"] for r in seed_rows])
        free = np.array([r["free_teams_mean"] for r in seed_rows])
        peak = np.array([r["peak_capacity"] for r in seed_rows])

        rows.append(
            {
                "run_bundle_id": experiment_spec.experiment_name,
                "experiment_name": experiment_spec.experiment_name,
                "experimental_condition_id": cid,
                # --- Grouping ---
                "environmental_conditions_id": cond_spec.environmental_conditions_id,
                "environmental_conditions_name": cond_spec.environmental_conditions_name,
                "governance_architecture_id": cond_spec.governance_architecture_id,
                "governance_architecture_name": cond_spec.governance_architecture_name,
                "operating_policy_id": cond_spec.operating_policy_id,
                "operating_policy_name": cond_spec.operating_policy_name,
                "governance_regime_label": cond_spec.governance_regime_label,
                # --- Execution ---
                "seed_count": len(seed_rows),
                "seed_runs_completed": len(seed_rows),
                # --- Summary metrics ---
                "total_value_mean": float(np.mean(values)),
                "total_value_median": float(np.median(values)),
                "total_value_std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                "total_value_p25": float(np.percentile(values, 25)),
                "total_value_p75": float(np.percentile(values, 75)),
                "surfaced_major_wins_mean": float(np.mean(wins)),
                "surfaced_major_wins_median": float(np.median(wins)),
                "surfaced_major_wins_std": float(np.std(wins, ddof=1)) if len(wins) > 1 else 0.0,
                "terminal_capability_mean": float(np.mean(caps)),
                "terminal_capability_median": float(np.median(caps)),
                "terminal_capability_std": float(np.std(caps, ddof=1)) if len(caps) > 1 else 0.0,
                "right_tail_completions_mean": float(np.mean(rt_comp)),
                "right_tail_stops_mean": float(np.mean(rt_stops)),
                "right_tail_false_stop_rate_mean": fsr_mean,
                "idle_pct_mean": float(np.mean(idle)),
                "free_teams_mean": float(np.mean(free)),
                "peak_capacity_mean": float(np.mean(peak)),
            }
        )

    return rows


def write_experimental_conditions(
    experiment_spec: ExperimentSpec,
    seed_run_rows: list[dict[str, Any]],
    bundle_path: Path,
) -> list[dict[str, Any]]:
    """Write outputs/experimental_conditions.parquet.

    Returns the rows for reuse by downstream table builders.
    """
    rows = _build_experimental_condition_rows(experiment_spec, seed_run_rows)
    _write_parquet(bundle_path / "outputs" / "experimental_conditions.parquet", rows)
    logger.info("Wrote experimental_conditions.parquet: %d rows", len(rows))
    return rows


# ===========================================================================
# Table 3: family_outcomes.parquet
# ===========================================================================


def _build_family_outcome_rows(
    experiment_spec: ExperimentSpec,
) -> list[dict[str, Any]]:
    """Build rows for family_outcomes.parquet.

    One row per grouping bucket (initiative family) per seed run,
    plus condition-level aggregated rows.

    Per reporting_package_specification.md §family_outcomes.parquet.
    """
    rows: list[dict[str, Any]] = []

    for cond_rec in experiment_spec.condition_records:
        cond_spec = cond_rec.condition_spec

        # Accumulate per-family metrics across seeds for condition-level rows.
        family_accumulators: dict[str, list[dict[str, Any]]] = {}

        for seed_rec in cond_rec.seed_run_records:
            result = seed_rec.run_result
            configs = seed_rec.initiative_configs
            final_states = seed_rec.initiative_final_states
            cmap = _config_map(configs)

            # Build per-initiative lookups.
            {s.initiative_id: s for s in final_states}

            # Count initiatives by family.
            family_counts: dict[str, int] = {}
            for cfg in configs:
                tag = cfg.generation_tag or "unknown"
                family_counts[tag] = family_counts.get(tag, 0) + 1

            # Count completed/stopped/never_started by family.
            completed_by_family: dict[str, int] = {}
            stopped_by_family: dict[str, int] = {}
            never_started_by_family: dict[str, int] = {}
            for s in final_states:
                s_cfg = cmap.get(s.initiative_id)
                s_tag = s_cfg.generation_tag or "unknown" if s_cfg else "unknown"
                if s.lifecycle_state == "completed":
                    completed_by_family[s_tag] = completed_by_family.get(s_tag, 0) + 1
                elif s.lifecycle_state == "stopped":
                    stopped_by_family[s_tag] = stopped_by_family.get(s_tag, 0) + 1
                elif s.lifecycle_state == "unassigned":
                    never_started_by_family[s_tag] = never_started_by_family.get(s_tag, 0) + 1

            # Value by family: from RunResult.value_by_family.
            value_by_family = result.value_by_family

            # Lump value by family: sum cumulative_lump_value_realized per init.
            lump_by_family: dict[str, float] = {}
            for s in final_states:
                s_cfg = cmap.get(s.initiative_id)
                s_tag = s_cfg.generation_tag or "unknown" if s_cfg else "unknown"
                lump_by_family[tag] = (
                    lump_by_family.get(tag, 0.0) + s.cumulative_lump_value_realized
                )

            # Residual value by family: from value_by_channel.residual_value_by_label.
            residual_by_family = result.value_by_channel.residual_value_by_label

            # Major wins by family: from major_win_profile.major_win_count_by_label.
            wins_by_family = result.major_win_profile.major_win_count_by_label

            # Right-tail eligible/stopped-eligible counts.
            rtfsp = result.right_tail_false_stop_profile

            # Emit one row per canonical family (plus any non-canonical).
            all_families = set(CANONICAL_FAMILIES) | set(family_counts.keys())
            for family in sorted(all_families):
                init_count = family_counts.get(family, 0)
                completed = completed_by_family.get(family, 0)
                stopped = stopped_by_family.get(family, 0)
                never_started = never_started_by_family.get(family, 0)
                active_at_horizon = init_count - completed - stopped - never_started

                # Eligible counts only for right_tail family.
                eligible = rtfsp.right_tail_eligible_count if family == "right_tail" else 0
                stopped_eligible = (
                    rtfsp.right_tail_stopped_eligible_count if family == "right_tail" else 0
                )

                row = {
                    "run_bundle_id": experiment_spec.experiment_name,
                    "experiment_name": experiment_spec.experiment_name,
                    "experimental_condition_id": cond_spec.experimental_condition_id,
                    "seed_run_id": (
                        f"{cond_spec.experimental_condition_id}__seed_{seed_rec.world_seed}"
                    ),
                    "world_seed": seed_rec.world_seed,
                    "grouping_namespace": "initiative_family",
                    "grouping_key": family,
                    "grouping_label": _family_label(family),
                    "initiative_count": init_count,
                    "completed_count": completed,
                    "stopped_count": stopped,
                    "active_at_horizon_count": max(active_at_horizon, 0),
                    "never_started_count": never_started,
                    "realized_value_lump": lump_by_family.get(family, 0.0),
                    "realized_value_residual": residual_by_family.get(family, 0.0),
                    "realized_value_total": value_by_family.get(family, 0.0),
                    "surfaced_major_wins": wins_by_family.get(family, 0),
                    "eligible_count": eligible,
                    "stopped_eligible_count": stopped_eligible,
                    "aggregation_level": "seed_run",
                }
                rows.append(row)

                # Accumulate for condition-level aggregation.
                family_accumulators.setdefault(family, []).append(row)

        # Condition-level aggregated rows (means across seeds).
        for family, family_rows in sorted(family_accumulators.items()):
            n = len(family_rows)
            if n == 0:
                continue
            rows.append(
                {
                    "run_bundle_id": experiment_spec.experiment_name,
                    "experiment_name": experiment_spec.experiment_name,
                    "experimental_condition_id": cond_spec.experimental_condition_id,
                    "seed_run_id": None,
                    "world_seed": None,
                    "grouping_namespace": "initiative_family",
                    "grouping_key": family,
                    "grouping_label": _family_label(family),
                    "initiative_count": sum(r["initiative_count"] for r in family_rows) / n,
                    "completed_count": sum(r["completed_count"] for r in family_rows) / n,
                    "stopped_count": sum(r["stopped_count"] for r in family_rows) / n,
                    "active_at_horizon_count": sum(
                        r["active_at_horizon_count"] for r in family_rows
                    )
                    / n,
                    "never_started_count": sum(r["never_started_count"] for r in family_rows) / n,
                    "realized_value_lump": sum(r["realized_value_lump"] for r in family_rows) / n,
                    "realized_value_residual": sum(
                        r["realized_value_residual"] for r in family_rows
                    )
                    / n,
                    "realized_value_total": sum(r["realized_value_total"] for r in family_rows)
                    / n,
                    "surfaced_major_wins": sum(r["surfaced_major_wins"] for r in family_rows) / n,
                    "eligible_count": sum(r["eligible_count"] for r in family_rows) / n,
                    "stopped_eligible_count": sum(r["stopped_eligible_count"] for r in family_rows)
                    / n,
                    "aggregation_level": "experimental_condition",
                }
            )

    return rows


def write_family_outcomes(
    experiment_spec: ExperimentSpec,
    bundle_path: Path,
) -> list[dict[str, Any]]:
    """Write outputs/family_outcomes.parquet."""
    rows = _build_family_outcome_rows(experiment_spec)
    _write_parquet(bundle_path / "outputs" / "family_outcomes.parquet", rows)
    logger.info("Wrote family_outcomes.parquet: %d rows", len(rows))
    return rows


# ===========================================================================
# Table 4: yearly_timeseries.parquet
# ===========================================================================


def _compute_residual_value_for_bin(
    config: ResolvedInitiativeConfig,
    activation_tick: int,
    bin_start: int,
    bin_end: int,
) -> float:
    """Compute residual value for one initiative in one time bin.

    Analytically sums the decay formula over ticks in [bin_start, bin_end):
        value = sum_{t=bin_start}^{bin_end-1} rate * exp(-decay * (t - activation_tick))

    Only includes ticks where t >= activation_tick.

    Args:
        config: Initiative config with residual channel parameters.
        activation_tick: Tick when residual was activated.
        bin_start: First tick of the bin (inclusive).
        bin_end: Last tick of the bin (exclusive).

    Returns:
        Total residual value for this initiative in this bin.
    """
    residual = config.value_channels.residual
    if not residual.enabled:
        return 0.0

    rate = residual.residual_rate
    decay = residual.residual_decay

    # Only count ticks at or after activation.
    effective_start = max(bin_start, activation_tick)
    if effective_start >= bin_end:
        return 0.0

    total = 0.0
    if decay == 0.0:
        # No decay: constant rate per tick.
        total = rate * (bin_end - effective_start)
    else:
        # Sum the geometric series analytically.
        # sum_{t=a}^{b-1} rate * exp(-decay * (t - act))
        # = rate * sum_{k=a-act}^{b-1-act} exp(-decay * k)
        # = rate * exp(-decay * (a-act)) * (1 - exp(-decay * (b-a))) / (1 - exp(-decay))
        k_start = effective_start - activation_tick
        n_ticks = bin_end - effective_start
        exp_start = math.exp(-decay * k_start)
        exp_ratio = math.exp(-decay)
        if abs(1.0 - exp_ratio) < 1e-15:
            # decay is effectively zero.
            total = rate * n_ticks * exp_start
        else:
            total = rate * exp_start * (1.0 - exp_ratio**n_ticks) / (1.0 - exp_ratio)

    return max(total, 0.0)


def _build_yearly_timeseries_rows(
    experiment_spec: ExperimentSpec,
) -> list[dict[str, Any]]:
    """Build rows for yearly_timeseries.parquet.

    One row per time bin per seed run per grouping bucket.
    Time bin = TICKS_PER_YEAR ticks (52 = one study year).

    Value fields use analytical reconstruction per plan §Decision 2.
    Capability per bin uses PortfolioTickRecord when available.

    Per reporting_package_specification.md §yearly_timeseries.parquet.
    """
    rows: list[dict[str, Any]] = []

    for cond_rec in experiment_spec.condition_records:
        cond_spec = cond_rec.condition_spec
        horizon = cond_rec.simulation_config.time.tick_horizon

        # Determine time bins.
        n_bins = math.ceil(horizon / TICKS_PER_YEAR)
        bins = []
        for i in range(n_bins):
            tick_start = i * TICKS_PER_YEAR
            tick_end = min((i + 1) * TICKS_PER_YEAR, horizon)
            bins.append((i, tick_start, tick_end))

        for seed_rec in cond_rec.seed_run_records:
            result = seed_rec.run_result
            configs = seed_rec.initiative_configs
            final_states = seed_rec.initiative_final_states
            _config_map(configs)
            state_map = {s.initiative_id: s for s in final_states}

            # Build stop event lookup by initiative_id for tick.
            stop_ticks: dict[str, int] = {}
            if result.stop_event_log:
                for ev in result.stop_event_log:
                    stop_ticks[ev.initiative_id] = ev.tick

            # Build major-win event lookup.
            mw_ticks: dict[str, int] = {}
            if result.major_win_event_log:
                for mw_event in result.major_win_event_log:
                    mw_ticks[mw_event.initiative_id] = mw_event.tick

            # Build capability per tick from portfolio records.
            cap_by_tick: dict[int, float] = {}
            if result.portfolio_tick_records:
                for rec in result.portfolio_tick_records:
                    cap_by_tick[rec.tick] = rec.capability_C_t

            seed_run_id = f"{cond_spec.experimental_condition_id}__seed_{seed_rec.world_seed}"

            # Compute per-family per-bin metrics.
            all_families = set(CANONICAL_FAMILIES)
            for cfg in configs:
                if cfg.generation_tag:
                    all_families.add(cfg.generation_tag)

            # Track cumulative values for cumulative columns.
            cumulative_by_family: dict[str, dict[str, float]] = {}
            cumulative_overall: dict[str, float] = {
                "lump": 0.0,
                "residual": 0.0,
                "total": 0.0,
                "wins": 0.0,
            }

            for bin_idx, bin_start, bin_end in bins:
                year_label = f"Year {bin_idx + 1}"

                # Per-family accumulators for this bin.
                family_metrics: dict[str, dict[str, float]] = {}
                for family in sorted(all_families):
                    family_metrics[family] = {
                        "lump": 0.0,
                        "residual": 0.0,
                        "completions": 0.0,
                        "stops": 0.0,
                        "wins": 0.0,
                        "enabler_completions": 0.0,
                    }

                # Process each initiative for this bin.
                for cfg in configs:
                    tag = cfg.generation_tag or "unknown"
                    if tag not in family_metrics:
                        family_metrics[tag] = {
                            "lump": 0.0,
                            "residual": 0.0,
                            "completions": 0.0,
                            "stops": 0.0,
                            "wins": 0.0,
                            "enabler_completions": 0.0,
                        }
                    fm = family_metrics[tag]
                    state = state_map.get(cfg.initiative_id)

                    # Completion in this bin?
                    if (
                        state
                        and state.completed_tick is not None
                        and bin_start <= state.completed_tick < bin_end
                    ):
                        fm["completions"] += 1
                        # Lump value from this completion.
                        fm["lump"] += state.cumulative_lump_value_realized
                        if tag == "enabler":
                            fm["enabler_completions"] += 1

                    # Stop in this bin?
                    stop_tick = stop_ticks.get(cfg.initiative_id)
                    if stop_tick is not None and bin_start <= stop_tick < bin_end:
                        fm["stops"] += 1

                    # Major win in this bin?
                    mw_tick = mw_ticks.get(cfg.initiative_id)
                    if mw_tick is not None and bin_start <= mw_tick < bin_end:
                        fm["wins"] += 1

                    # Residual value in this bin (analytical reconstruction).
                    if (
                        state
                        and state.residual_activated
                        and state.residual_activation_tick is not None
                    ):
                        fm["residual"] += _compute_residual_value_for_bin(
                            cfg,
                            state.residual_activation_tick,
                            bin_start,
                            bin_end,
                        )

                # Capability at end of bin.
                cap_tick = bin_end - 1
                terminal_cap = cap_by_tick.get(cap_tick, 1.0)

                # Emit per-family rows.
                overall_lump = 0.0
                overall_residual = 0.0
                overall_wins = 0.0
                overall_completions = 0.0
                overall_stops = 0.0
                overall_enabler = 0.0

                for family in sorted(all_families):
                    fm = family_metrics.get(
                        family,
                        {
                            "lump": 0.0,
                            "residual": 0.0,
                            "completions": 0.0,
                            "stops": 0.0,
                            "wins": 0.0,
                            "enabler_completions": 0.0,
                        },
                    )
                    value_total = fm["lump"] + fm["residual"]

                    # Update cumulative.
                    if family not in cumulative_by_family:
                        cumulative_by_family[family] = {
                            "lump": 0.0,
                            "residual": 0.0,
                            "total": 0.0,
                            "wins": 0.0,
                        }
                    cum = cumulative_by_family[family]
                    cum["lump"] += fm["lump"]
                    cum["residual"] += fm["residual"]
                    cum["total"] += value_total
                    cum["wins"] += fm["wins"]

                    rows.append(
                        {
                            "run_bundle_id": experiment_spec.experiment_name,
                            "experiment_name": experiment_spec.experiment_name,
                            "experimental_condition_id": cond_spec.experimental_condition_id,
                            "seed_run_id": seed_run_id,
                            "world_seed": seed_rec.world_seed,
                            "time_bin_index": bin_idx,
                            "time_bin_label": year_label,
                            "tick_start": bin_start,
                            "tick_end": bin_end,
                            "grouping_namespace": "initiative_family",
                            "grouping_key": family,
                            "grouping_label": _family_label(family),
                            "value_lump": fm["lump"],
                            "value_residual": fm["residual"],
                            "value_total": value_total,
                            "value_lump_cumulative": cum["lump"],
                            "value_residual_cumulative": cum["residual"],
                            "value_total_cumulative": cum["total"],
                            "surfaced_major_wins": fm["wins"],
                            "surfaced_major_wins_cumulative": cum["wins"],
                            "completions": fm["completions"],
                            "stops": fm["stops"],
                            "enabler_completions": fm["enabler_completions"],
                            "terminal_capability": terminal_cap,
                        }
                    )

                    # Accumulate overall.
                    overall_lump += fm["lump"]
                    overall_residual += fm["residual"]
                    overall_wins += fm["wins"]
                    overall_completions += fm["completions"]
                    overall_stops += fm["stops"]
                    overall_enabler += fm["enabler_completions"]

                # Emit "overall" row for this bin.
                overall_total = overall_lump + overall_residual
                cumulative_overall["lump"] += overall_lump
                cumulative_overall["residual"] += overall_residual
                cumulative_overall["total"] += overall_total
                cumulative_overall["wins"] += overall_wins

                rows.append(
                    {
                        "run_bundle_id": experiment_spec.experiment_name,
                        "experiment_name": experiment_spec.experiment_name,
                        "experimental_condition_id": cond_spec.experimental_condition_id,
                        "seed_run_id": seed_run_id,
                        "world_seed": seed_rec.world_seed,
                        "time_bin_index": bin_idx,
                        "time_bin_label": year_label,
                        "tick_start": bin_start,
                        "tick_end": bin_end,
                        "grouping_namespace": "overall",
                        "grouping_key": "all",
                        "grouping_label": "All",
                        "value_lump": overall_lump,
                        "value_residual": overall_residual,
                        "value_total": overall_total,
                        "value_lump_cumulative": cumulative_overall["lump"],
                        "value_residual_cumulative": cumulative_overall["residual"],
                        "value_total_cumulative": cumulative_overall["total"],
                        "surfaced_major_wins": overall_wins,
                        "surfaced_major_wins_cumulative": cumulative_overall["wins"],
                        "completions": overall_completions,
                        "stops": overall_stops,
                        "enabler_completions": overall_enabler,
                        "terminal_capability": terminal_cap,
                    }
                )

    return rows


def write_yearly_timeseries(
    experiment_spec: ExperimentSpec,
    bundle_path: Path,
) -> list[dict[str, Any]]:
    """Write outputs/yearly_timeseries.parquet."""
    rows = _build_yearly_timeseries_rows(experiment_spec)
    _write_parquet(bundle_path / "outputs" / "yearly_timeseries.parquet", rows)
    logger.info("Wrote yearly_timeseries.parquet: %d rows", len(rows))
    return rows


# ===========================================================================
# Table 5: initiative_outcomes.parquet
# ===========================================================================


def _build_initiative_outcome_rows(
    experiment_spec: ExperimentSpec,
) -> list[dict[str, Any]]:
    """Build rows for initiative_outcomes.parquet.

    One row per initiative per seed run.

    Per reporting_package_specification.md §initiative_outcomes.parquet.
    """
    rows: list[dict[str, Any]] = []

    for cond_rec in experiment_spec.condition_records:
        cond_spec = cond_rec.condition_spec
        model_config = cond_rec.simulation_config.model

        for seed_rec in cond_rec.seed_run_records:
            result = seed_rec.run_result
            configs = seed_rec.initiative_configs
            final_states = seed_rec.initiative_final_states
            state_map = {s.initiative_id: s for s in final_states}
            seed_run_id = f"{cond_spec.experimental_condition_id}__seed_{seed_rec.world_seed}"

            # Stop events by initiative for belief_at_stop.
            stop_belief: dict[str, float] = {}
            stop_tick_map: dict[str, int] = {}
            if result.stop_event_log:
                for ev in result.stop_event_log:
                    stop_belief[ev.initiative_id] = ev.quality_belief_t
                    stop_tick_map[ev.initiative_id] = ev.tick

            # Major-win set.
            mw_set: set[str] = set()
            if result.major_win_event_log:
                for mw_event in result.major_win_event_log:
                    mw_set.add(mw_event.initiative_id)

            for cfg in configs:
                state = state_map.get(cfg.initiative_id)
                if state is None:
                    continue

                # is_major_win_eligible per spec: both conditions required.
                mw_channel = cfg.value_channels.major_win_event
                is_eligible = mw_channel.enabled and mw_channel.is_major_win

                # Map lifecycle state to spec vocabulary.
                status_map = {
                    "completed": "completed",
                    "stopped": "stopped",
                    "active": "active_at_horizon",
                    "unassigned": "never_started",
                }
                status = status_map.get(state.lifecycle_state, state.lifecycle_state)

                # Initial quality belief: per-initiative override or model default.
                initial_belief = cfg.initial_quality_belief
                if initial_belief is None:
                    initial_belief = model_config.default_initial_quality_belief

                rows.append(
                    {
                        "run_bundle_id": experiment_spec.experiment_name,
                        "experiment_name": experiment_spec.experiment_name,
                        "experimental_condition_id": cond_spec.experimental_condition_id,
                        "seed_run_id": seed_run_id,
                        "world_seed": seed_rec.world_seed,
                        "initiative_id": cfg.initiative_id,
                        # --- Classification ---
                        "initiative_family": cfg.generation_tag,
                        "initiative_family_label": _family_label(cfg.generation_tag),
                        # --- Attributes ---
                        "true_quality": cfg.latent_quality,
                        "initial_quality_belief": initial_belief,
                        "final_quality_belief": state.quality_belief_t,
                        "required_team_size": cfg.required_team_size,
                        "true_duration_ticks": cfg.true_duration_ticks,
                        "planned_duration_ticks": cfg.planned_duration_ticks,
                        # --- Outcome ---
                        "status": status,
                        "completed": state.lifecycle_state == "completed",
                        "stopped": state.lifecycle_state == "stopped",
                        "completion_tick": state.completed_tick,
                        "stop_tick": stop_tick_map.get(cfg.initiative_id),
                        "staffed_ticks_total": state.staffed_tick_count,
                        "realized_value_lump": state.cumulative_lump_value_realized,
                        "realized_value_residual": state.cumulative_residual_value_realized,
                        "realized_value_total": state.cumulative_value_realized,
                        "is_major_win_eligible": is_eligible,
                        "surfaced_major_win": cfg.initiative_id in mw_set,
                        "belief_at_stop": stop_belief.get(cfg.initiative_id),
                    }
                )

    return rows


def write_initiative_outcomes(
    experiment_spec: ExperimentSpec,
    bundle_path: Path,
) -> list[dict[str, Any]]:
    """Write outputs/initiative_outcomes.parquet."""
    rows = _build_initiative_outcome_rows(experiment_spec)
    _write_parquet(bundle_path / "outputs" / "initiative_outcomes.parquet", rows)
    logger.info("Wrote initiative_outcomes.parquet: %d rows", len(rows))
    return rows


# ===========================================================================
# Table 6: diagnostics.parquet
# ===========================================================================


def _build_diagnostics_rows(
    experiment_spec: ExperimentSpec,
    seed_run_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build rows for diagnostics.parquet.

    Long-form diagnostic table: one row per diagnostic metric per
    experimental condition, optionally sliced.

    Per reporting_package_specification.md §diagnostics.parquet.
    """
    rows: list[dict[str, Any]] = []

    # Group seed-run data by condition for aggregation.
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for row in seed_run_rows:
        cid = row["experimental_condition_id"]
        by_condition.setdefault(cid, []).append(row)

    for cond_rec in experiment_spec.condition_records:
        cond_spec = cond_rec.condition_spec
        cid = cond_spec.experimental_condition_id
        cond_seed_rows = by_condition.get(cid, [])

        base = {
            "run_bundle_id": experiment_spec.experiment_name,
            "experiment_name": experiment_spec.experiment_name,
            "experimental_condition_id": cid,
        }

        # --- Right-tail false-stop diagnostics ---
        fsr_values = [
            r["right_tail_false_stop_rate"]
            for r in cond_seed_rows
            if r["right_tail_false_stop_rate"] is not None
        ]
        eligible_values = [r["right_tail_eligible_count"] for r in cond_seed_rows]
        stopped_eligible_values = [r["right_tail_stopped_eligible_count"] for r in cond_seed_rows]

        rows.append(
            {
                **base,
                "diagnostic_group": "right_tail",
                "diagnostic_name": "false_stop_rate",
                "slice_namespace": "overall",
                "slice_key": "all",
                "slice_label": "All seeds",
                "metric_value": float(np.mean(fsr_values)) if fsr_values else None,
                "metric_unit": "rate",
            }
        )
        rows.append(
            {
                **base,
                "diagnostic_group": "right_tail",
                "diagnostic_name": "eligible_count",
                "slice_namespace": "overall",
                "slice_key": "all",
                "slice_label": "All seeds",
                "metric_value": float(np.mean(eligible_values)) if eligible_values else 0.0,
                "metric_unit": "count",
            }
        )
        rows.append(
            {
                **base,
                "diagnostic_group": "right_tail",
                "diagnostic_name": "stopped_eligible_count",
                "slice_namespace": "overall",
                "slice_key": "all",
                "slice_label": "All seeds",
                "metric_value": (
                    float(np.mean(stopped_eligible_values)) if stopped_eligible_values else 0.0
                ),
                "metric_unit": "count",
            }
        )

        # --- Belief-at-stop for stopped eligible RT ---
        all_beliefs: list[float] = []
        for seed_rec in cond_rec.seed_run_records:
            rtfsp = seed_rec.run_result.right_tail_false_stop_profile
            all_beliefs.extend(rtfsp.belief_at_stop_for_stopped_eligible)

        if all_beliefs:
            beliefs_arr = np.array(all_beliefs)
            for stat_name, stat_val in [
                ("belief_at_stop_mean", float(np.mean(beliefs_arr))),
                ("belief_at_stop_p25", float(np.percentile(beliefs_arr, 25))),
                ("belief_at_stop_p50", float(np.percentile(beliefs_arr, 50))),
                ("belief_at_stop_p75", float(np.percentile(beliefs_arr, 75))),
            ]:
                rows.append(
                    {
                        **base,
                        "diagnostic_group": "right_tail",
                        "diagnostic_name": stat_name,
                        "slice_namespace": "overall",
                        "slice_key": "all",
                        "slice_label": "All seeds",
                        "metric_value": stat_val,
                        "metric_unit": "belief",
                    }
                )

        # --- Stop hazard by staffed-time bin ---
        # Aggregate stop events across seeds for this condition.
        # Uses diagnostics.compute_stop_hazard() per seed, then averages.
        from primordial_soup.diagnostics import compute_stop_hazard, compute_survival_curves

        hazard_bin_fractions: dict[int, list[float]] = {}
        survival_points: dict[int, list[float]] = {}

        for seed_rec in cond_rec.seed_run_records:
            result = seed_rec.run_result

            # Stop hazard.
            hazard = compute_stop_hazard(result)
            for bin_idx, fraction in enumerate(hazard.bin_fractions):
                hazard_bin_fractions.setdefault(bin_idx, []).append(fraction)

            # Survival curves (all right-tail).
            surv = compute_survival_curves(result)
            for tick, fraction_alive in surv.all_rt_curve:
                survival_points.setdefault(tick, []).append(fraction_alive)

        # Emit stop hazard rows per bin.
        for bin_idx in sorted(hazard_bin_fractions.keys()):
            fracs = hazard_bin_fractions[bin_idx]
            bin_start = bin_idx * 20  # default bin_width=20
            bin_end = bin_start + 20
            rows.append(
                {
                    **base,
                    "diagnostic_group": "right_tail",
                    "diagnostic_name": f"stop_hazard_bin_{bin_idx}",
                    "slice_namespace": "staffed_time_bin",
                    "slice_key": f"{bin_start}-{bin_end}",
                    "slice_label": f"Staffed ticks {bin_start}-{bin_end}",
                    "metric_value": float(np.mean(fracs)),
                    "metric_unit": "fraction",
                }
            )

        # Emit survival rate rows per staffed-tick point.
        for tick in sorted(survival_points.keys()):
            alive_vals = survival_points[tick]
            rows.append(
                {
                    **base,
                    "diagnostic_group": "right_tail",
                    "diagnostic_name": f"survival_rate_tick_{tick}",
                    "slice_namespace": "staffed_tick",
                    "slice_key": str(tick),
                    "slice_label": f"Staffed tick {tick}",
                    "metric_value": float(np.mean(alive_vals)),
                    "metric_unit": "fraction",
                }
            )

        # --- Terminal capability diagnostics ---
        cap_values = [r["terminal_capability"] for r in cond_seed_rows]
        peak_values = [r["peak_capacity"] for r in cond_seed_rows]

        rows.append(
            {
                **base,
                "diagnostic_group": "capability",
                "diagnostic_name": "terminal_capability_mean",
                "slice_namespace": "overall",
                "slice_key": "all",
                "slice_label": "All seeds",
                "metric_value": float(np.mean(cap_values)) if cap_values else None,
                "metric_unit": "scalar",
            }
        )
        rows.append(
            {
                **base,
                "diagnostic_group": "capability",
                "diagnostic_name": "terminal_capability_std",
                "slice_namespace": "overall",
                "slice_key": "all",
                "slice_label": "All seeds",
                "metric_value": float(np.std(cap_values, ddof=1)) if len(cap_values) > 1 else 0.0,
                "metric_unit": "scalar",
            }
        )
        rows.append(
            {
                **base,
                "diagnostic_group": "capability",
                "diagnostic_name": "peak_capability_mean",
                "slice_namespace": "overall",
                "slice_key": "all",
                "slice_label": "All seeds",
                "metric_value": float(np.mean(peak_values)) if peak_values else None,
                "metric_unit": "scalar",
            }
        )

    return rows


def write_diagnostics(
    experiment_spec: ExperimentSpec,
    seed_run_rows: list[dict[str, Any]],
    bundle_path: Path,
) -> list[dict[str, Any]]:
    """Write outputs/diagnostics.parquet."""
    rows = _build_diagnostics_rows(experiment_spec, seed_run_rows)
    _write_parquet(bundle_path / "outputs" / "diagnostics.parquet", rows)
    logger.info("Wrote diagnostics.parquet: %d rows", len(rows))
    return rows


# ===========================================================================
# Table 7: event_log.parquet
# ===========================================================================


def _build_event_log_rows(
    experiment_spec: ExperimentSpec,
) -> list[dict[str, Any]]:
    """Build rows for event_log.parquet.

    One row per event per seed run. Unified schema across event types.

    Per reporting_package_specification.md §event_log.parquet.
    """
    rows: list[dict[str, Any]] = []

    for cond_rec in experiment_spec.condition_records:
        cond_spec = cond_rec.condition_spec

        for seed_rec in cond_rec.seed_run_records:
            result = seed_rec.run_result
            configs = seed_rec.initiative_configs
            cmap = _config_map(configs)
            seed_run_id = f"{cond_spec.experimental_condition_id}__seed_{seed_rec.world_seed}"

            base = {
                "run_bundle_id": experiment_spec.experiment_name,
                "experiment_name": experiment_spec.experiment_name,
                "experimental_condition_id": cond_spec.experimental_condition_id,
                "seed_run_id": seed_run_id,
                "world_seed": seed_rec.world_seed,
            }

            # --- Stop events → initiative_stopped ---
            if result.stop_event_log:
                for ev in result.stop_event_log:
                    cfg = cmap.get(ev.initiative_id)
                    tag = cfg.generation_tag if cfg else None
                    rows.append(
                        {
                            **base,
                            "tick": ev.tick,
                            "event_type": "initiative_stopped",
                            "initiative_id": ev.initiative_id,
                            "initiative_family": tag,
                            "initiative_family_label": _family_label(tag),
                            "value_delta": 0.0,
                            "capability_delta": 0.0,
                            "quality_belief": ev.quality_belief_t,
                            "notes_json": json.dumps(
                                {
                                    "triggering_rule": ev.triggering_rule,
                                    "latent_quality": ev.latent_quality,
                                    "governance_archetype": ev.governance_archetype,
                                }
                            ),
                        }
                    )

            # --- Completion events → initiative_completed + enabler_completed ---
            # Derive from InitiativeFinalState (completed_tick).
            for state in seed_rec.initiative_final_states:
                if state.lifecycle_state == "completed" and state.completed_tick is not None:
                    cfg = cmap.get(state.initiative_id)
                    tag = cfg.generation_tag if cfg else None
                    lump_val = 0.0
                    cap_delta = 0.0
                    if cfg:
                        cl = cfg.value_channels.completion_lump
                        if cl.enabled and cl.realized_value is not None:
                            lump_val = cl.realized_value
                        cap_delta = cfg.capability_contribution_scale

                    rows.append(
                        {
                            **base,
                            "tick": state.completed_tick,
                            "event_type": "initiative_completed",
                            "initiative_id": state.initiative_id,
                            "initiative_family": tag,
                            "initiative_family_label": _family_label(tag),
                            "value_delta": lump_val,
                            "capability_delta": cap_delta,
                            "quality_belief": state.quality_belief_t,
                            "notes_json": json.dumps(
                                {
                                    "latent_quality": cfg.latent_quality if cfg else None,
                                }
                            ),
                        }
                    )

                    # Also emit enabler_completed if applicable.
                    if tag == "enabler":
                        rows.append(
                            {
                                **base,
                                "tick": state.completed_tick,
                                "event_type": "enabler_completed",
                                "initiative_id": state.initiative_id,
                                "initiative_family": tag,
                                "initiative_family_label": _family_label(tag),
                                "value_delta": lump_val,
                                "capability_delta": cap_delta,
                                "quality_belief": state.quality_belief_t,
                                "notes_json": "{}",
                            }
                        )

            # --- Major-win events → major_win_surfaced ---
            if result.major_win_event_log:
                for mw_ev in result.major_win_event_log:
                    mw_cfg = cmap.get(mw_ev.initiative_id)
                    mw_tag = mw_cfg.generation_tag if mw_cfg else None
                    rows.append(
                        {
                            **base,
                            "tick": mw_ev.tick,
                            "event_type": "major_win_surfaced",
                            "initiative_id": mw_ev.initiative_id,
                            "initiative_family": mw_tag,
                            "initiative_family_label": _family_label(mw_tag),
                            "value_delta": 0.0,
                            "capability_delta": 0.0,
                            "quality_belief": mw_ev.quality_belief_at_completion,
                            "notes_json": json.dumps(
                                {
                                    "latent_quality": mw_ev.latent_quality,
                                    "observable_ceiling": mw_ev.observable_ceiling,
                                }
                            ),
                        }
                    )

            # --- initiative_started events ---
            # Derived from ReassignmentEvents (per plan §Decision 4).
            if result.reassignment_profile.reassignment_event_log:
                # Track which initiatives we've already emitted a start for.
                started_ids: set[str] = set()
                for ra_ev in result.reassignment_profile.reassignment_event_log:
                    init_id = ra_ev.to_initiative_id
                    if init_id not in started_ids:
                        started_ids.add(init_id)
                        ra_cfg = cmap.get(init_id)
                        ra_tag = ra_cfg.generation_tag if ra_cfg else None
                        rows.append(
                            {
                                **base,
                                "tick": ra_ev.tick,
                                "event_type": "initiative_started",
                                "initiative_id": init_id,
                                "initiative_family": ra_tag,
                                "initiative_family_label": _family_label(ra_tag),
                                "value_delta": 0.0,
                                "capability_delta": 0.0,
                                "quality_belief": None,
                                "notes_json": json.dumps(
                                    {
                                        "team_id": ra_ev.team_id,
                                    }
                                ),
                            }
                        )

    return rows


def write_event_log(
    experiment_spec: ExperimentSpec,
    bundle_path: Path,
) -> list[dict[str, Any]]:
    """Write outputs/event_log.parquet."""
    rows = _build_event_log_rows(experiment_spec)
    _write_parquet(bundle_path / "outputs" / "event_log.parquet", rows)
    logger.info("Wrote event_log.parquet: %d rows", len(rows))
    return rows


# ===========================================================================
# Derived Table 1: pairwise_deltas.parquet
# ===========================================================================


def write_pairwise_deltas(
    experiment_spec: ExperimentSpec,
    condition_rows: list[dict[str, Any]],
    bundle_path: Path,
    *,
    baseline_condition_id: str | None = None,
) -> list[dict[str, Any]]:
    """Write derived/pairwise_deltas.parquet.

    One row per pair of conditions, compared against a baseline.

    Per reporting_package_specification.md §pairwise_deltas.parquet.

    Args:
        experiment_spec: Experiment specification.
        condition_rows: Rows from experimental_conditions.parquet.
        bundle_path: Bundle root path.
        baseline_condition_id: Explicit baseline condition. When None,
            falls back to auto-detecting the "Balanced" regime.
    """
    if not condition_rows:
        _write_parquet(bundle_path / "derived" / "pairwise_deltas.parquet", [])
        return []

    # Find baseline condition.
    baseline_row = None
    if baseline_condition_id is not None:
        for row in condition_rows:
            if row["experimental_condition_id"] == baseline_condition_id:
                baseline_row = row
                break

    if baseline_row is None:
        # Heuristic: first condition with "balanced" in governance_regime_label.
        for row in condition_rows:
            label = row.get("governance_regime_label", "")
            if isinstance(label, str) and "balanced" in label.lower():
                baseline_row = row
                break

    if baseline_row is None:
        # Fallback: first condition.
        baseline_row = condition_rows[0]

    baseline_id = baseline_row["experimental_condition_id"]
    rows: list[dict[str, Any]] = []

    for row in condition_rows:
        cid = row["experimental_condition_id"]
        if cid == baseline_id:
            continue

        rows.append(
            {
                "run_bundle_id": experiment_spec.experiment_name,
                "experiment_name": experiment_spec.experiment_name,
                "comparison_name": f"{cid}_vs_{baseline_id}",
                "lhs_experimental_condition_id": cid,
                "rhs_experimental_condition_id": baseline_id,
                "delta_total_value_mean": (
                    (row.get("total_value_mean") or 0.0)
                    - (baseline_row.get("total_value_mean") or 0.0)
                ),
                "delta_surfaced_major_wins_mean": (
                    (row.get("surfaced_major_wins_mean") or 0.0)
                    - (baseline_row.get("surfaced_major_wins_mean") or 0.0)
                ),
                "delta_terminal_capability_mean": (
                    (row.get("terminal_capability_mean") or 0.0)
                    - (baseline_row.get("terminal_capability_mean") or 0.0)
                ),
                "delta_right_tail_false_stop_rate_mean": _safe_delta(
                    row.get("right_tail_false_stop_rate_mean"),
                    baseline_row.get("right_tail_false_stop_rate_mean"),
                ),
                "delta_idle_pct_mean": (
                    (row.get("idle_pct_mean") or 0.0) - (baseline_row.get("idle_pct_mean") or 0.0)
                ),
            }
        )

    _write_parquet(bundle_path / "derived" / "pairwise_deltas.parquet", rows)
    logger.info("Wrote pairwise_deltas.parquet: %d rows", len(rows))
    return rows


def _safe_delta(a: float | None, b: float | None) -> float | None:
    """Compute a - b, returning None if either is None."""
    if a is None or b is None:
        return None
    return a - b


# ===========================================================================
# Derived Table 2: representative_runs.parquet
# ===========================================================================


def write_representative_runs(
    seed_run_rows: list[dict[str, Any]],
    experiment_spec: ExperimentSpec,
    bundle_path: Path,
) -> list[dict[str, Any]]:
    """Write derived/representative_runs.parquet.

    Selects representative seed runs per condition (median, max, min value).

    Per reporting_package_specification.md §representative_runs.parquet.
    """
    # Group seed-run rows by condition.
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for row in seed_run_rows:
        cid = row["experimental_condition_id"]
        by_condition.setdefault(cid, []).append(row)

    rows: list[dict[str, Any]] = []

    for cid, cond_rows in by_condition.items():
        if not cond_rows:
            continue

        sorted_by_value = sorted(cond_rows, key=lambda r: r["total_value"])

        # Median: closest to median value.
        median_val = float(np.median([r["total_value"] for r in cond_rows]))
        median_row = min(cond_rows, key=lambda r: abs(r["total_value"] - median_val))

        selections = [
            ("median_value", 1, "Closest to median total value", median_row),
            ("max_value", 2, "Highest total value", sorted_by_value[-1]),
            ("min_value", 3, "Lowest total value", sorted_by_value[0]),
        ]

        for rule, rank, reason, selected in selections:
            rows.append(
                {
                    "run_bundle_id": experiment_spec.experiment_name,
                    "experiment_name": experiment_spec.experiment_name,
                    "experimental_condition_id": cid,
                    "seed_run_id": selected["seed_run_id"],
                    "selection_rule": rule,
                    "selection_rank": rank,
                    "selection_reason": reason,
                }
            )

    _write_parquet(bundle_path / "derived" / "representative_runs.parquet", rows)
    logger.info("Wrote representative_runs.parquet: %d rows", len(rows))
    return rows


# ===========================================================================
# Derived Table 3: enabler_coupling.parquet
# ===========================================================================


def write_enabler_coupling(
    experiment_spec: ExperimentSpec,
    seed_run_rows: list[dict[str, Any]],
    family_outcome_rows: list[dict[str, Any]],
    timeseries_rows: list[dict[str, Any]],
    bundle_path: Path,
) -> list[dict[str, Any]]:
    """Write derived/enabler_coupling.parquet.

    Per-seed and per-condition enabler-related metrics including
    value_total_late_period.

    Per reporting_package_specification.md §enabler_coupling.parquet.
    """
    rows: list[dict[str, Any]] = []

    # Build enabler completion counts from family_outcomes (seed-level rows).
    enabler_completions_by_seed: dict[str, float] = {}
    for row in family_outcome_rows:
        if row.get("aggregation_level") == "seed_run" and row.get("grouping_key") == "enabler":
            seed_id = row.get("seed_run_id", "")
            enabler_completions_by_seed[seed_id] = row.get("completed_count", 0)

    # Compute value_total_late_period from timeseries rows.
    # Late period = final third of tick horizon: ceil(2*T/3) through T-1.
    late_value_by_seed: dict[str, float] = {}
    for row in timeseries_rows:
        if row.get("grouping_key") != "all":
            continue
        seed_id = row.get("seed_run_id", "")
        # Determine if this bin overlaps the late period.
        # We need the horizon to compute the late-period start. Use tick_end as proxy
        # for the last bin's end (which equals the horizon).
        # Accumulate — we'll filter by late-period threshold below.
        late_value_by_seed.setdefault(seed_id, 0.0)

    # Determine horizon per condition and compute late-period value.
    for cond_rec in experiment_spec.condition_records:
        horizon = cond_rec.simulation_config.time.tick_horizon
        late_start = math.ceil(2 * horizon / 3)
        cond_id = cond_rec.condition_spec.experimental_condition_id

        for seed_rec in cond_rec.seed_run_records:
            seed_run_id = f"{cond_id}__seed_{seed_rec.world_seed}"
            late_total = 0.0
            for row in timeseries_rows:
                if row.get("seed_run_id") != seed_run_id:
                    continue
                if row.get("grouping_key") != "all":
                    continue
                # Check if this bin overlaps the late period.
                bin_start = row.get("tick_start", 0)
                bin_end = row.get("tick_end", 0)
                if bin_end <= late_start:
                    continue
                # Full bin in late period: add full value_total.
                # Partial overlap: prorate.
                effective_start = max(bin_start, late_start)
                bin_width = bin_end - bin_start
                if bin_width > 0:
                    fraction = (bin_end - effective_start) / bin_width
                    late_total += row.get("value_total", 0.0) * fraction

            late_value_by_seed[seed_run_id] = late_total

    # Build per-seed rows.
    for seed_row in seed_run_rows:
        seed_id = seed_row["seed_run_id"]
        cid = seed_row["experimental_condition_id"]

        # Find matching condition record for belief-at-stop data.
        mean_belief = None
        for cond_rec in experiment_spec.condition_records:
            if cond_rec.condition_spec.experimental_condition_id == cid:
                for seed_rec in cond_rec.seed_run_records:
                    check_id = f"{cid}__seed_{seed_rec.world_seed}"
                    if check_id == seed_id:
                        rtfsp = seed_rec.run_result.right_tail_false_stop_profile
                        beliefs = rtfsp.belief_at_stop_for_stopped_eligible
                        if beliefs:
                            mean_belief = float(np.mean(beliefs))
                        break
                break

        rows.append(
            {
                "run_bundle_id": experiment_spec.experiment_name,
                "experiment_name": experiment_spec.experiment_name,
                "experimental_condition_id": cid,
                "seed_run_id": seed_id,
                "enabler_completions": enabler_completions_by_seed.get(seed_id, 0),
                "terminal_capability": seed_row["terminal_capability"],
                "right_tail_false_stop_rate": seed_row["right_tail_false_stop_rate"],
                "right_tail_completions": seed_row["right_tail_completions"],
                "surfaced_major_wins": seed_row["surfaced_major_wins"],
                "value_total": seed_row["total_value"],
                "value_total_late_period": late_value_by_seed.get(seed_id, 0.0),
                "mean_belief_at_stop_for_stopped_eligible_rt": mean_belief,
            }
        )

    _write_parquet(bundle_path / "derived" / "enabler_coupling.parquet", rows)
    logger.info("Wrote enabler_coupling.parquet: %d rows", len(rows))
    return rows


# ===========================================================================
# Orchestrator
# ===========================================================================


def write_all_tables(
    experiment_spec: ExperimentSpec,
    bundle_path: Path,
    *,
    baseline_condition_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Write all canonical and derived tables to the bundle.

    Calls each table writer in dependency order, passing intermediate
    results to downstream writers as needed.

    Args:
        experiment_spec: Complete experiment specification.
        bundle_path: Root directory for the run bundle.
        baseline_condition_id: Explicit baseline for pairwise deltas.

    Returns:
        Dict mapping table name to its rows, for use by figure and
        report generators.
    """
    results: dict[str, list[dict[str, Any]]] = {}

    # --- Canonical tables ---
    results["seed_runs"] = write_seed_runs(experiment_spec, bundle_path)
    results["experimental_conditions"] = write_experimental_conditions(
        experiment_spec,
        results["seed_runs"],
        bundle_path,
    )
    results["family_outcomes"] = write_family_outcomes(experiment_spec, bundle_path)
    results["yearly_timeseries"] = write_yearly_timeseries(experiment_spec, bundle_path)
    results["initiative_outcomes"] = write_initiative_outcomes(experiment_spec, bundle_path)
    results["diagnostics"] = write_diagnostics(
        experiment_spec,
        results["seed_runs"],
        bundle_path,
    )
    results["event_log"] = write_event_log(experiment_spec, bundle_path)

    # --- Derived tables ---
    results["pairwise_deltas"] = write_pairwise_deltas(
        experiment_spec,
        results["experimental_conditions"],
        bundle_path,
        baseline_condition_id=baseline_condition_id,
    )
    results["representative_runs"] = write_representative_runs(
        results["seed_runs"],
        experiment_spec,
        bundle_path,
    )
    results["enabler_coupling"] = write_enabler_coupling(
        experiment_spec,
        results["seed_runs"],
        results["family_outcomes"],
        results["yearly_timeseries"],
        bundle_path,
    )

    return results
