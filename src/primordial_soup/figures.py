"""Figure generation for run-bundle report packages.

Generates all required executive-summary and appendix figures from
canonical table data. Each figure is a standalone PNG file written
to the figures/ directory of the run bundle.

All figures read from in-memory data structures (the same row-dicts
used to write the Parquet tables), not from Parquet files on disk.

Style is configured via plt.rcParams directly (not named style
strings) to avoid version-dependent style name issues across
matplotlib installations.

Design reference: docs/implementation/reporting_package_specification.md §Required figures
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    from pathlib import Path

    from primordial_soup.run_bundle import ExperimentSpec, SeedRunRecord

logger = logging.getLogger(__name__)

# Use non-interactive backend for server/CI environments.
matplotlib.use("Agg")


# ---------------------------------------------------------------------------
# Style configuration — via rcParams, not named styles
# ---------------------------------------------------------------------------


def _configure_style() -> None:
    """Configure matplotlib style via rcParams directly.

    Avoids named style strings (e.g., seaborn-v0_8-whitegrid) which
    vary across matplotlib versions.
    """
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "#f8f8f8",
            "axes.grid": True,
            "grid.color": "#cccccc",
            "grid.linestyle": "-",
            "grid.linewidth": 0.5,
            "axes.edgecolor": "#333333",
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "figure.dpi": 150,
        }
    )


# ---------------------------------------------------------------------------
# Color palette — consistent across figures
# ---------------------------------------------------------------------------

# Map condition labels to colors. Falls back to a cycle for unknown labels.
_CONDITION_COLORS = [
    "#2196F3",  # blue
    "#FF5722",  # deep orange
    "#4CAF50",  # green
    "#9C27B0",  # purple
    "#FF9800",  # orange
    "#00BCD4",  # cyan
    "#E91E63",  # pink
    "#795548",  # brown
    "#607D8B",  # blue grey
]

_FAMILY_COLORS = {
    "flywheel": "#2196F3",
    "right_tail": "#FF5722",
    "enabler": "#4CAF50",
    "quick_win": "#FF9800",
}


# Colors for trajectory representative roles — consistent across all
# trajectory figures for visual identity.
_TRAJECTORY_ROLE_COLORS: dict[str, str] = {
    "flywheel_completed": "#2196F3",  # blue
    "right_tail_high_q": "#FF5722",  # deep orange
    "right_tail_stopped": "#9C27B0",  # purple
    "enabler": "#4CAF50",  # green
    "quick_win": "#FF9800",  # orange
}

# Fallback color cycle for manual or unknown roles.
_TRAJECTORY_FALLBACK_COLORS = (
    "#2196F3",
    "#FF5722",
    "#4CAF50",
    "#9C27B0",
    "#FF9800",
    "#00BCD4",
)


def _get_trajectory_role_color(role: str) -> str:
    """Return the color for a trajectory role label."""
    if role in _TRAJECTORY_ROLE_COLORS:
        return _TRAJECTORY_ROLE_COLORS[role]
    # Extract index from manual_N roles used for manual override selection.
    try:
        idx = int(role.split("_")[-1])
    except ValueError:
        idx = 0
    return _TRAJECTORY_FALLBACK_COLORS[idx % len(_TRAJECTORY_FALLBACK_COLORS)]


def _get_condition_color(idx: int) -> str:
    """Get color for condition by index."""
    return _CONDITION_COLORS[idx % len(_CONDITION_COLORS)]


def _get_family_color(family: str) -> str:
    """Get color for an initiative family."""
    return _FAMILY_COLORS.get(family, "#888888")


# ---------------------------------------------------------------------------
# Helper: group rows by a key
# ---------------------------------------------------------------------------


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[Any, list[dict[str, Any]]]:
    """Group rows by a key field."""
    groups: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        k = row.get(key)
        groups.setdefault(k, []).append(row)
    return groups


# ===========================================================================
# Representative initiative selection for trajectory figures
# ===========================================================================


def select_representative_initiatives(
    seed_run_record: SeedRunRecord,
) -> dict[str, str]:
    """Select one representative initiative per family role for trajectory plots.

    Returns a dict mapping role labels to initiative IDs:
        "flywheel_completed"   — moderate-quality flywheel that completed
        "right_tail_high_q"    — high-quality right-tail (major-win candidate)
        "right_tail_stopped"   — low-quality right-tail, correctly stopped
        "enabler"              — capability contributor
        "quick_win"            — fast-completing initiative

    Selection heuristics use post-hoc data (latent quality, terminal
    lifecycle state) because this is a diagnostic tool — the point is to
    show ground truth alongside the governance-observable trajectory.

    Adapted from scripts/initiative_trajectories.py _select_representatives(),
    reworked to accept SeedRunRecord (the canonical reporting-layer data
    structure) instead of raw RunResult + WorldState.
    """
    # ---- Build lookup dicts from SeedRunRecord fields ----

    # initiative_id → ResolvedInitiativeConfig (has generation_tag, latent_quality)
    resolved_by_id = {
        config.initiative_id: config for config in seed_run_record.initiative_configs
    }

    # initiative_id → InitiativeFinalState (has lifecycle_state as string,
    # completed_tick, major_win_surfaced, etc.)
    terminal_by_id = {
        final_state.initiative_id: final_state
        for final_state in seed_run_record.initiative_final_states
    }

    # ---- Index stop and major-win events by initiative_id ----
    # These come from the RunResult carried inside the SeedRunRecord.

    stop_events_by_id: dict[str, object] = {}
    if seed_run_record.run_result.stop_event_log:
        for stop_event in seed_run_record.run_result.stop_event_log:
            stop_events_by_id[stop_event.initiative_id] = stop_event

    major_win_initiative_ids: set[str] = set()
    if seed_run_record.run_result.major_win_event_log:
        for major_win_event in seed_run_record.run_result.major_win_event_log:
            major_win_initiative_ids.add(major_win_event.initiative_id)

    # ---- Select one representative per role ----
    selected: dict[str, str] = {}

    # -- Flywheel: completed, moderate quality --
    # We want a flywheel whose quality is close to the family median
    # (~0.6–0.7), so the trajectory shows typical flywheel behavior.
    flywheel_candidates = [
        (initiative_id, config)
        for initiative_id, config in resolved_by_id.items()
        if config.generation_tag == "flywheel"
        and terminal_by_id[initiative_id].lifecycle_state == "completed"
    ]
    # Sort by quality closest to the family median (~0.65).
    flywheel_candidates.sort(key=lambda pair: abs(pair[1].latent_quality - 0.65))
    if flywheel_candidates:
        selected["flywheel_completed"] = flywheel_candidates[0][0]

    # -- Right-tail high q: major-win winner or highest-q completed --
    # Prefer an initiative that actually surfaced a major win.  Fall
    # back to the highest-quality right-tail that completed, or if
    # none completed, the highest-quality right-tail overall.
    right_tail_candidates = [
        (initiative_id, config)
        for initiative_id, config in resolved_by_id.items()
        if config.generation_tag == "right_tail"
    ]

    # Sub-filter: those that surfaced a major win.
    right_tail_major_winners = [
        (initiative_id, config)
        for initiative_id, config in right_tail_candidates
        if initiative_id in major_win_initiative_ids
    ]
    if right_tail_major_winners:
        # Pick the one with highest latent quality among winners.
        right_tail_major_winners.sort(key=lambda pair: pair[1].latent_quality, reverse=True)
        selected["right_tail_high_q"] = right_tail_major_winners[0][0]
    else:
        # No major wins — pick highest-q right-tail that completed.
        right_tail_completed = [
            (initiative_id, config)
            for initiative_id, config in right_tail_candidates
            if terminal_by_id[initiative_id].lifecycle_state == "completed"
        ]
        right_tail_completed.sort(key=lambda pair: pair[1].latent_quality, reverse=True)
        if right_tail_completed:
            selected["right_tail_high_q"] = right_tail_completed[0][0]
        elif right_tail_candidates:
            # No completions either — just pick highest quality overall.
            right_tail_by_quality = sorted(
                right_tail_candidates,
                key=lambda pair: pair[1].latent_quality,
                reverse=True,
            )
            selected["right_tail_high_q"] = right_tail_by_quality[0][0]

    # -- Right-tail low q: stopped, low quality --
    # This shows what a "correctly killed" right-tail looks like.
    # Exclude whichever initiative was already selected as the high-q rep.
    right_tail_stopped = [
        (initiative_id, config)
        for initiative_id, config in right_tail_candidates
        if terminal_by_id[initiative_id].lifecycle_state == "stopped"
        and initiative_id != selected.get("right_tail_high_q")
    ]
    # Pick the lowest-quality stopped right-tail.
    right_tail_stopped.sort(key=lambda pair: pair[1].latent_quality)
    if right_tail_stopped:
        selected["right_tail_stopped"] = right_tail_stopped[0][0]

    # -- Enabler: capability contributor --
    # Prefer one that completed (full lifecycle visible).  Among those,
    # pick the one with quality closest to 0.5 (moderate).
    enabler_candidates = [
        (initiative_id, config)
        for initiative_id, config in resolved_by_id.items()
        if config.generation_tag == "enabler"
    ]
    enabler_completed = [
        (initiative_id, config)
        for initiative_id, config in enabler_candidates
        if terminal_by_id[initiative_id].lifecycle_state == "completed"
    ]
    if enabler_completed:
        # Pick one with moderate quality.
        enabler_completed.sort(key=lambda pair: abs(pair[1].latent_quality - 0.5))
        selected["enabler"] = enabler_completed[0][0]
    elif enabler_candidates:
        # No completed enablers — take the first one (stable id order
        # via the dict, but not critical since this is a fallback).
        selected["enabler"] = enabler_candidates[0][0]

    # -- Quick-win: fast completion --
    # The representative quick-win is the one that completed earliest.
    quick_win_candidates = [
        (initiative_id, config)
        for initiative_id, config in resolved_by_id.items()
        if config.generation_tag == "quick_win"
        and terminal_by_id[initiative_id].lifecycle_state == "completed"
    ]
    # Sort by completed_tick; use 9999 as sentinel for None (shouldn't
    # happen for completed initiatives, but be defensive).
    quick_win_candidates.sort(key=lambda pair: terminal_by_id[pair[0]].completed_tick or 9999)
    if quick_win_candidates:
        selected["quick_win"] = quick_win_candidates[0][0]

    return selected


# ===========================================================================
# Figure 1: Value by year, stacked by initiative family
# ===========================================================================


def plot_value_by_year_stacked(
    timeseries_rows: list[dict[str, Any]],
    figures_dir: Path,
) -> None:
    """Generate value_by_year_stacked.png.

    Stacked bar chart showing priced value per year decomposed by
    initiative family. One panel per experimental condition.
    """
    _configure_style()

    # Filter to family-level rows (not "overall").
    family_rows = [r for r in timeseries_rows if r["grouping_namespace"] == "initiative_family"]
    by_condition = _group_by(family_rows, "experimental_condition_id")

    n_conditions = len(by_condition)
    if n_conditions == 0:
        return

    fig, axes = plt.subplots(1, max(n_conditions, 1), figsize=(6 * n_conditions, 5), squeeze=False)

    for idx, (cid, cond_rows) in enumerate(sorted(by_condition.items())):
        ax = axes[0, idx]
        # Group by seed, then average across seeds.
        by_seed = _group_by(cond_rows, "seed_run_id")
        # Get time bins from first seed.
        first_seed_rows = list(by_seed.values())[0] if by_seed else []
        bins = sorted({r["time_bin_index"] for r in first_seed_rows})
        families = sorted({r["grouping_key"] for r in cond_rows})

        # Average value per family per bin across seeds.
        n_seeds = len(by_seed)
        family_values: dict[str, list[float]] = {f: [0.0] * len(bins) for f in families}
        for seed_rows in by_seed.values():
            for row in seed_rows:
                fam = row["grouping_key"]
                try:
                    bin_pos = bins.index(row["time_bin_index"])
                except ValueError:
                    continue
                family_values[fam][bin_pos] += row["value_total"] / n_seeds

        # Stack the bars.
        x = np.arange(len(bins))
        bottom = np.zeros(len(bins))
        for fam in families:
            vals = np.array(family_values[fam])
            ax.bar(
                x,
                vals,
                bottom=bottom,
                label=fam.replace("_", " ").title(),
                color=_get_family_color(fam),
                width=0.7,
            )
            bottom += vals

        ax.set_xlabel("Study Year")
        ax.set_ylabel("Priced Value")
        ax.set_title(str(cid))
        ax.set_xticks(x)
        ax.set_xticklabels([f"Y{b + 1}" for b in bins])
        ax.legend(loc="upper left", fontsize=8)

    fig.suptitle("Value by Year — Stacked by Initiative Family", fontsize=13)
    fig.tight_layout()
    fig.savefig(str(figures_dir / "value_by_year_stacked.png"))
    plt.close(fig)
    logger.info("Generated value_by_year_stacked.png")


# ===========================================================================
# Figure 2: Cumulative priced value by year
# ===========================================================================


def plot_cumulative_value_by_year(
    timeseries_rows: list[dict[str, Any]],
    condition_rows: list[dict[str, Any]],
    figures_dir: Path,
) -> None:
    """Generate cumulative_value_by_year.png."""
    _configure_style()

    overall_rows = [r for r in timeseries_rows if r["grouping_key"] == "all"]
    by_condition = _group_by(overall_rows, "experimental_condition_id")

    # Build label map from condition rows.
    label_map = {
        r["experimental_condition_id"]: r.get(
            "governance_regime_label", r["experimental_condition_id"]
        )
        for r in condition_rows
    }

    fig, ax = plt.subplots(figsize=(8, 5))

    for idx, (cid, cond_rows) in enumerate(sorted(by_condition.items())):
        by_seed = _group_by(cond_rows, "seed_run_id")
        bins = sorted({r["time_bin_index"] for r in cond_rows})

        # Average cumulative value across seeds.
        n_seeds = len(by_seed)
        cum_values = [0.0] * len(bins)
        for seed_rows in by_seed.values():
            for row in sorted(seed_rows, key=lambda r: r["time_bin_index"]):
                try:
                    bin_pos = bins.index(row["time_bin_index"])
                except ValueError:
                    continue
                cum_values[bin_pos] += row["value_total_cumulative"] / n_seeds

        ax.plot(
            bins,
            cum_values,
            marker="o",
            markersize=4,
            label=label_map.get(cid, cid),
            color=_get_condition_color(idx),
        )

    ax.set_xlabel("Study Year")
    ax.set_ylabel("Cumulative Priced Value")
    ax.set_title("Cumulative Priced Value by Year")
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(figures_dir / "cumulative_value_by_year.png"))
    plt.close(fig)
    logger.info("Generated cumulative_value_by_year.png")


# ===========================================================================
# Figure 3: Surfaced major wins by year
# ===========================================================================


def plot_surfaced_major_wins_by_year(
    timeseries_rows: list[dict[str, Any]],
    condition_rows: list[dict[str, Any]],
    figures_dir: Path,
) -> None:
    """Generate surfaced_major_wins_by_year.png."""
    _configure_style()

    overall_rows = [r for r in timeseries_rows if r["grouping_key"] == "all"]
    by_condition = _group_by(overall_rows, "experimental_condition_id")
    label_map = {
        r["experimental_condition_id"]: r.get(
            "governance_regime_label", r["experimental_condition_id"]
        )
        for r in condition_rows
    }

    fig, ax = plt.subplots(figsize=(8, 5))

    for idx, (cid, cond_rows) in enumerate(sorted(by_condition.items())):
        by_seed = _group_by(cond_rows, "seed_run_id")
        bins = sorted({r["time_bin_index"] for r in cond_rows})

        n_seeds = len(by_seed)
        cum_wins = [0.0] * len(bins)
        for seed_rows in by_seed.values():
            for row in sorted(seed_rows, key=lambda r: r["time_bin_index"]):
                try:
                    bin_pos = bins.index(row["time_bin_index"])
                except ValueError:
                    continue
                cum_wins[bin_pos] += row["surfaced_major_wins_cumulative"] / n_seeds

        ax.plot(
            bins,
            cum_wins,
            marker="o",
            markersize=4,
            label=label_map.get(cid, cid),
            color=_get_condition_color(idx),
        )

    ax.set_xlabel("Study Year")
    ax.set_ylabel("Cumulative Surfaced Major Wins")
    ax.set_title("Surfaced Major Wins by Year\n(surfaced-not-priced by design)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(figures_dir / "surfaced_major_wins_by_year.png"))
    plt.close(fig)
    logger.info("Generated surfaced_major_wins_by_year.png")


# ===========================================================================
# Figure 4: Tradeoff frontier
# ===========================================================================


def plot_tradeoff_frontier(
    condition_rows: list[dict[str, Any]],
    figures_dir: Path,
) -> None:
    """Generate tradeoff_frontier.png."""
    _configure_style()

    if not condition_rows:
        return

    fig, ax = plt.subplots(figsize=(8, 6))

    values = [r["total_value_mean"] for r in condition_rows]
    wins = [r["surfaced_major_wins_mean"] for r in condition_rows]
    caps = [r["terminal_capability_mean"] for r in condition_rows]
    labels = [
        r.get("governance_regime_label", r["experimental_condition_id"]) for r in condition_rows
    ]

    # Normalize caps for point sizing.
    cap_arr = np.array(caps)
    if cap_arr.max() > cap_arr.min():
        sizes = 100 + 400 * (cap_arr - cap_arr.min()) / (cap_arr.max() - cap_arr.min())
    else:
        sizes = np.full_like(cap_arr, 200)

    ax.scatter(
        values,
        wins,
        s=sizes,
        c=[_get_condition_color(i) for i in range(len(values))],
        alpha=0.8,
        edgecolors="black",
        linewidths=0.5,
    )

    for i, label in enumerate(labels):
        ax.annotate(
            label, (values[i], wins[i]), textcoords="offset points", xytext=(8, 4), fontsize=8
        )

    ax.set_xlabel("Total Priced Value (mean)")
    ax.set_ylabel("Surfaced Major Wins (mean)")
    ax.set_title("Tradeoff Frontier\n(point size = terminal capability)")
    fig.tight_layout()
    fig.savefig(str(figures_dir / "tradeoff_frontier.png"))
    plt.close(fig)
    logger.info("Generated tradeoff_frontier.png")


# ===========================================================================
# Figure 5: Terminal capability comparison
# ===========================================================================


def plot_terminal_capability(
    condition_rows: list[dict[str, Any]],
    figures_dir: Path,
) -> None:
    """Generate terminal_capability.png."""
    _configure_style()

    if not condition_rows:
        return

    labels = [
        r.get("governance_regime_label", r["experimental_condition_id"]) for r in condition_rows
    ]
    means = [r["terminal_capability_mean"] for r in condition_rows]
    stds = [r.get("terminal_capability_std", 0.0) for r in condition_rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(labels))
    colors = [_get_condition_color(i) for i in range(len(labels))]

    ax.bar(
        x, means, yerr=stds, color=colors, capsize=4, width=0.6, edgecolor="black", linewidth=0.5
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("Terminal Capability (mean)")
    ax.set_title("Terminal Capability Comparison")
    fig.tight_layout()
    fig.savefig(str(figures_dir / "terminal_capability.png"))
    plt.close(fig)
    logger.info("Generated terminal_capability.png")


# ===========================================================================
# Figure 6: Right-tail false-stop / survival view
# ===========================================================================


def plot_rt_survival_curves(
    condition_rows: list[dict[str, Any]],
    seed_run_rows: list[dict[str, Any]],
    figures_dir: Path,
) -> None:
    """Generate rt_survival_curves.png.

    Shows false-stop rate as a bar chart (survival view) per condition.
    """
    _configure_style()

    if not condition_rows:
        return

    labels = [
        r.get("governance_regime_label", r["experimental_condition_id"]) for r in condition_rows
    ]
    fsr = [r.get("right_tail_false_stop_rate_mean") for r in condition_rows]
    # Replace None with 0 for display.
    fsr_display = [v if v is not None else 0.0 for v in fsr]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(labels))
    colors = [_get_condition_color(i) for i in range(len(labels))]

    ax.bar(x, fsr_display, color=colors, width=0.6, edgecolor="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("Right-Tail False-Stop Rate (mean)")
    ax.set_title("Right-Tail False-Stop Rate by Governance Regime")
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    fig.savefig(str(figures_dir / "rt_survival_curves.png"))
    plt.close(fig)
    logger.info("Generated rt_survival_curves.png")


# ===========================================================================
# Figure 7: Enabler dashboard
# ===========================================================================


def plot_enabler_dashboard(
    enabler_rows: list[dict[str, Any]],
    condition_rows: list[dict[str, Any]],
    figures_dir: Path,
) -> None:
    """Generate enabler_dashboard.png.

    Multi-panel figure showing enabler-related metrics per condition.
    """
    _configure_style()

    if not condition_rows:
        return

    # Aggregate enabler_coupling rows by condition.
    by_condition = _group_by(enabler_rows, "experimental_condition_id")
    label_map = {
        r["experimental_condition_id"]: r.get(
            "governance_regime_label", r["experimental_condition_id"]
        )
        for r in condition_rows
    }

    panels = [
        ("enabler_completions", "Enabler Completions"),
        ("terminal_capability", "Terminal Capability"),
        ("right_tail_false_stop_rate", "RT False-Stop Rate"),
        ("right_tail_completions", "RT Completions"),
        ("surfaced_major_wins", "Surfaced Major Wins"),
        ("value_total", "Total Value"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes_flat = axes.flatten()

    cond_ids = sorted(by_condition.keys())
    x = np.arange(len(cond_ids))
    labels = [label_map.get(cid, str(cid)) for cid in cond_ids]

    for panel_idx, (metric, title) in enumerate(panels):
        ax = axes_flat[panel_idx]
        means = []
        for cid in cond_ids:
            cond_rows_list = by_condition.get(cid, [])
            vals = [float(r[metric]) for r in cond_rows_list if r.get(metric) is not None]
            means.append(float(np.mean(vals)) if vals else 0.0)

        colors = [_get_condition_color(i) for i in range(len(cond_ids))]
        ax.bar(x, means, color=colors, width=0.6, edgecolor="black", linewidth=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        ax.set_title(title, fontsize=10)

    fig.suptitle("Enabler Dashboard", fontsize=13)
    fig.tight_layout()
    fig.savefig(str(figures_dir / "enabler_dashboard.png"))
    plt.close(fig)
    logger.info("Generated enabler_dashboard.png")


# ===========================================================================
# Figure 8 (appendix): Seed-level distributions
# ===========================================================================


def plot_seed_distributions(
    seed_run_rows: list[dict[str, Any]],
    figures_dir: Path,
) -> None:
    """Generate seed_distributions.png.

    Boxplots for total value, major wins, terminal capability.
    """
    _configure_style()

    by_condition = _group_by(seed_run_rows, "experimental_condition_id")
    cond_ids = sorted(by_condition.keys())

    if not cond_ids:
        return

    metrics = [
        ("total_value", "Total Priced Value"),
        ("surfaced_major_wins", "Surfaced Major Wins"),
        ("terminal_capability", "Terminal Capability"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    for ax_idx, (metric, title) in enumerate(metrics):
        ax = axes[ax_idx]
        data = []
        labels = []
        for cid in cond_ids:
            vals = [r[metric] for r in by_condition[cid]]
            data.append(vals)
            labels.append(str(cid)[:20])

        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True)
        for i, patch in enumerate(bp["boxes"]):
            patch.set_facecolor(_get_condition_color(i))
            patch.set_alpha(0.7)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=30)

    fig.suptitle("Seed-Level Distributions", fontsize=13)
    fig.tight_layout()
    fig.savefig(str(figures_dir / "seed_distributions.png"))
    plt.close(fig)
    logger.info("Generated seed_distributions.png")


# ===========================================================================
# Figure 9 (appendix): Representative-run timelines
# ===========================================================================


def plot_representative_timelines(
    event_log_rows: list[dict[str, Any]],
    representative_rows: list[dict[str, Any]],
    condition_rows: list[dict[str, Any]],
    figures_dir: Path,
) -> None:
    """Generate representative_timelines.png.

    Multi-track timeline showing events (completions, stops, major wins)
    over ticks for the representative seed run (median-value) of each
    experimental condition.

    Per spec §Required appendix figures §9.
    """
    _configure_style()

    if not representative_rows or not event_log_rows:
        return

    # Find median-value representative seed_run_ids.
    median_reps = {
        r["experimental_condition_id"]: r["seed_run_id"]
        for r in representative_rows
        if r.get("selection_rule") == "median_value"
    }

    if not median_reps:
        return

    label_map = {
        r["experimental_condition_id"]: r.get(
            "governance_regime_label", r["experimental_condition_id"]
        )
        for r in condition_rows
    }

    # Event type → marker style and color.
    event_styles: dict[str, dict[str, Any]] = {
        "initiative_completed": {"marker": "o", "color": "#4CAF50", "label": "Completed"},
        "initiative_stopped": {"marker": "x", "color": "#FF5722", "label": "Stopped"},
        "major_win_surfaced": {
            "marker": "*",
            "color": "#FFD700",
            "label": "Major Win",
            "size": 120,
        },
        "initiative_started": {"marker": ">", "color": "#2196F3", "label": "Started"},
    }

    cond_ids = sorted(median_reps.keys())
    n_conditions = len(cond_ids)
    if n_conditions == 0:
        return

    fig, axes = plt.subplots(n_conditions, 1, figsize=(12, 3 * n_conditions), squeeze=False)

    for idx, cid in enumerate(cond_ids):
        ax = axes[idx, 0]
        seed_id = median_reps[cid]

        # Filter event log to this seed run.
        seed_events = [r for r in event_log_rows if r.get("seed_run_id") == seed_id]

        # Plot events by type.
        legend_entries: dict[str, bool] = {}
        for event in seed_events:
            etype = event.get("event_type", "")
            style = event_styles.get(etype)
            if style is None:
                continue

            tick = event.get("tick", 0)
            family = event.get("initiative_family", "unknown")
            # Y-axis: scatter by family for visual separation.
            family_y = list(("flywheel", "right_tail", "enabler", "quick_win", "unknown"))
            y_val = family_y.index(family) if family in family_y else 4

            show_label = etype not in legend_entries
            legend_entries[etype] = True

            # Unfilled markers (like "x") ignore edgecolors — only
            # set edgecolors for filled markers to avoid warnings.
            scatter_kwargs: dict[str, Any] = {
                "marker": style["marker"],
                "color": style["color"],
                "s": style.get("size", 50),
                "label": style["label"] if show_label else None,
                "alpha": 0.8,
            }
            if style["marker"] not in ("x", "+", "1", "2", "3", "4"):
                scatter_kwargs["edgecolors"] = "black"
                scatter_kwargs["linewidths"] = 0.3
            ax.scatter(tick, y_val, **scatter_kwargs)

        ax.set_yticks(range(len(family_y)))
        ax.set_yticklabels([f.replace("_", " ").title() for f in family_y], fontsize=8)
        ax.set_xlabel("Tick")
        ax.set_title(f"{label_map.get(cid, cid)} (representative run)", fontsize=10)
        ax.legend(loc="upper right", fontsize=7, ncol=2)

    fig.suptitle("Representative-Run Timelines", fontsize=13)
    fig.tight_layout()
    fig.savefig(str(figures_dir / "representative_timelines.png"))
    plt.close(fig)
    logger.info("Generated representative_timelines.png")


# ===========================================================================
# Orchestrator
# ===========================================================================


def generate_all_figures(
    table_data: dict[str, list[dict[str, Any]]],
    figures_dir: Path,
) -> None:
    """Generate all required figures from canonical table data.

    Args:
        table_data: Dict mapping table name to rows, as returned by
            tables.write_all_tables().
        figures_dir: Directory to write figure PNGs into.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)

    timeseries = table_data.get("yearly_timeseries", [])
    conditions = table_data.get("experimental_conditions", [])
    seed_runs = table_data.get("seed_runs", [])
    enabler = table_data.get("enabler_coupling", [])
    event_log = table_data.get("event_log", [])
    representative = table_data.get("representative_runs", [])

    # Executive-summary figures (1–7).
    plot_value_by_year_stacked(timeseries, figures_dir)
    plot_cumulative_value_by_year(timeseries, conditions, figures_dir)
    plot_surfaced_major_wins_by_year(timeseries, conditions, figures_dir)
    plot_tradeoff_frontier(conditions, figures_dir)
    plot_terminal_capability(conditions, figures_dir)
    plot_rt_survival_curves(conditions, seed_runs, figures_dir)
    plot_enabler_dashboard(enabler, conditions, figures_dir)

    # Appendix figures (8–9).
    plot_seed_distributions(seed_runs, figures_dir)
    plot_representative_timelines(event_log, representative, conditions, figures_dir)

    logger.info("All figures generated in %s", figures_dir)


# ===========================================================================
# Trajectory figure: per-initiative belief subplots
# ===========================================================================


def plot_trajectory_beliefs(
    condition_id: str,
    selected: dict[str, str],
    seed_run_record: SeedRunRecord,
    figures_dir: Path,
) -> Path | None:
    """Generate a multi-subplot trajectory figure for selected initiatives.

    One subplot row per selected representative initiative, sharing the
    x-axis (tick). Each subplot shows:
      - Quality belief (c_t) over time as a colored line
      - Latent quality (q) as a horizontal dashed reference
      - Ramp period shading (gray) when the initiative is ramping
      - Stop event: vertical dotted line + X marker
      - Completion event: vertical dotted green line
      - Major-win event: gold star marker
      - Secondary y-axis: executive attention as a filled area

    The figure mirrors the multi-panel layout used in
    scripts/initiative_trajectories.py _plot_all_trajectories(), adapted
    to work with SeedRunRecord (the canonical reporting-layer structure)
    instead of raw RunResult + WorldState.

    Args:
        condition_id: Experimental condition identifier (used in filename).
        selected: Mapping of role label to initiative_id, as returned by
            select_representative_initiatives().
        seed_run_record: The SeedRunRecord for the representative seed run.
        figures_dir: Directory to write the PNG into.

    Returns:
        Path to the saved figure, or None if per-tick records are missing.
    """
    _configure_style()

    # ---- Guard: per-tick records must be available ----
    per_tick_records = seed_run_record.run_result.per_initiative_tick_records
    if per_tick_records is None:
        logger.warning(
            "Skipping trajectory_beliefs for %s: per_initiative_tick_records is None",
            condition_id,
        )
        return None

    if not selected:
        logger.warning(
            "Skipping trajectory_beliefs for %s: no representatives selected",
            condition_id,
        )
        return None

    # ---- Build lookup dicts ----

    # initiative_id -> ResolvedInitiativeConfig (latent_quality, generation_tag).
    config_by_id = {config.initiative_id: config for config in seed_run_record.initiative_configs}

    # initiative_id -> InitiativeFinalState (lifecycle_state, completed_tick).
    terminal_by_id = {
        final_state.initiative_id: final_state
        for final_state in seed_run_record.initiative_final_states
    }

    # initiative_id -> StopEvent (tick, quality_belief_t, triggering_rule).
    stop_event_by_id: dict[str, object] = {}
    if seed_run_record.run_result.stop_event_log:
        for stop_event in seed_run_record.run_result.stop_event_log:
            stop_event_by_id[stop_event.initiative_id] = stop_event

    # initiative_id -> MajorWinEvent (tick, quality_belief_at_completion).
    major_win_by_id: dict[str, object] = {}
    if seed_run_record.run_result.major_win_event_log:
        for major_win_event in seed_run_record.run_result.major_win_event_log:
            major_win_by_id[major_win_event.initiative_id] = major_win_event

    # ---- Group per-tick records by initiative_id for fast lookup ----
    records_by_initiative: dict[str, list[object]] = {}
    for record in per_tick_records:
        records_by_initiative.setdefault(record.initiative_id, []).append(record)

    # ---- Create multi-subplot figure ----
    # One row per selected initiative, shared x-axis so timing is
    # visually comparable across roles.
    n_subplots = len(selected)
    fig, axes = plt.subplots(
        n_subplots,
        1,
        figsize=(12, 3.5 * n_subplots),
        sharex=True,
        squeeze=False,
    )

    for subplot_idx, (role, initiative_id) in enumerate(sorted(selected.items())):
        ax_primary = axes[subplot_idx, 0]

        # Per-tick records for this initiative.
        initiative_records = records_by_initiative.get(initiative_id, [])
        if not initiative_records:
            ax_primary.text(
                0.5,
                0.5,
                f"No tick records for {initiative_id}",
                transform=ax_primary.transAxes,
                ha="center",
            )
            continue

        ticks = [r.tick for r in initiative_records]
        beliefs = [r.quality_belief_t for r in initiative_records]
        attentions = [r.exec_attention_a_t for r in initiative_records]

        config = config_by_id.get(initiative_id)
        terminal_state = terminal_by_id.get(initiative_id)
        latent_quality = config.latent_quality if config else 0.0
        generation_tag = (config.generation_tag or "unknown") if config else "unknown"
        color = _get_trajectory_role_color(role)

        # ---- Primary y-axis: quality belief trajectory ----
        ax_primary.plot(
            ticks,
            beliefs,
            color=color,
            linewidth=1.5,
            label="quality belief",
        )

        # Latent quality horizontal reference line (ground truth).
        ax_primary.axhline(
            y=latent_quality,
            color=color,
            linestyle="--",
            linewidth=1.0,
            alpha=0.6,
            label=f"latent quality ({latent_quality:.3f})",
        )

        # Ramp period shading — marks the initial learning-rate ramp
        # where the team is still getting up to speed.
        ramp_ticks = [r.tick for r in initiative_records if r.is_ramping]
        if ramp_ticks:
            ax_primary.axvspan(
                min(ramp_ticks),
                max(ramp_ticks) + 0.5,
                alpha=0.08,
                color="gray",
                label="ramp period",
            )

        # Stop event — vertical line + X marker at the stop tick.
        stop_event = stop_event_by_id.get(initiative_id)
        if stop_event is not None:
            ax_primary.axvline(
                x=stop_event.tick,
                color="#E91E63",
                linestyle=":",
                linewidth=1.5,
                label=f"stopped ({stop_event.triggering_rule})",
            )
            ax_primary.plot(
                stop_event.tick,
                stop_event.quality_belief_t,
                marker="x",
                color="#E91E63",
                markersize=10,
                zorder=5,
            )

        # Completion — vertical green dotted line at the completion tick.
        if terminal_state is not None and terminal_state.completed_tick is not None:
            ax_primary.axvline(
                x=terminal_state.completed_tick,
                color="#4CAF50",
                linestyle=":",
                linewidth=1.5,
                label="completed",
            )

        # Major-win — gold star marker at the discovery tick.
        major_win_event = major_win_by_id.get(initiative_id)
        if major_win_event is not None:
            ax_primary.plot(
                major_win_event.tick,
                major_win_event.quality_belief_at_completion,
                marker="*",
                color="#FFD700",
                markersize=15,
                zorder=6,
                markeredgecolor="#333",
                label="major win",
            )

        ax_primary.set_ylabel("Quality belief")
        ax_primary.set_ylim(-0.05, 1.05)

        # ---- Secondary y-axis: executive attention ----
        # Shown as a light filled area behind the belief line so the
        # reader can see how attention allocation tracks belief changes.
        ax_attention = ax_primary.twinx()
        ax_attention.fill_between(
            ticks,
            attentions,
            alpha=0.12,
            color=color,
            label="attention",
        )
        ax_attention.set_ylabel("Executive attention", color="#888888")
        ax_attention.set_ylim(0, 1.5)
        ax_attention.tick_params(axis="y", labelcolor="#888888")

        # ---- Subplot title: role, initiative ID, family, quality, state ----
        lifecycle_label = terminal_state.lifecycle_state if terminal_state else "unknown"
        subplot_title = (
            f"{role} ({initiative_id}) — {generation_tag}, "
            f"q={latent_quality:.3f}, {lifecycle_label}"
        )
        ax_primary.set_title(subplot_title, fontsize=10, loc="left")

        # ---- Combined legend from both axes ----
        lines_primary, labels_primary = ax_primary.get_legend_handles_labels()
        lines_attention, labels_attention = ax_attention.get_legend_handles_labels()
        ax_primary.legend(
            lines_primary + lines_attention,
            labels_primary + labels_attention,
            loc="upper left",
            fontsize=8,
        )

    # X-axis label only on the bottom subplot.
    axes[-1, 0].set_xlabel("Tick (weeks)")
    fig.suptitle(
        f"Initiative Trajectories — Belief vs Latent Quality ({condition_id})",
        fontsize=13,
    )
    fig.tight_layout()

    output_path = figures_dir / f"trajectory_beliefs_{condition_id}.png"
    fig.savefig(str(output_path))
    plt.close(fig)
    logger.info("Generated %s", output_path.name)

    return output_path


# ===========================================================================
# Trajectory figure: overlay (all selected on one plot)
# ===========================================================================


def plot_trajectory_overlay(
    condition_id: str,
    selected: dict[str, str],
    seed_run_record: SeedRunRecord,
    figures_dir: Path,
) -> Path | None:
    """Generate a single-panel overlay of all selected initiative trajectories.

    All selected initiatives share the same axes, each drawn in its role
    color. This gives a quick visual comparison of how different initiative
    types evolve under the same governance regime. Simpler than the
    multi-subplot version (plot_trajectory_beliefs) — no attention axis,
    no event markers beyond stop/completion lines.

    The legend shows role label, generation tag, and latent quality so the
    reader can identify each line without cross-referencing.

    Args:
        condition_id: Experimental condition identifier (used in filename).
        selected: Mapping of role label to initiative_id, as returned by
            select_representative_initiatives().
        seed_run_record: The SeedRunRecord for the representative seed run.
        figures_dir: Directory to write the PNG into.

    Returns:
        Path to the saved figure, or None if per-tick records are missing.
    """
    _configure_style()

    # ---- Guard: per-tick records must be available ----
    per_tick_records = seed_run_record.run_result.per_initiative_tick_records
    if per_tick_records is None:
        logger.warning(
            "Skipping trajectory_overlay for %s: per_initiative_tick_records is None",
            condition_id,
        )
        return None

    if not selected:
        logger.warning(
            "Skipping trajectory_overlay for %s: no representatives selected",
            condition_id,
        )
        return None

    # ---- Build lookup dicts ----

    config_by_id = {config.initiative_id: config for config in seed_run_record.initiative_configs}

    terminal_by_id = {
        final_state.initiative_id: final_state
        for final_state in seed_run_record.initiative_final_states
    }

    stop_event_by_id: dict[str, object] = {}
    if seed_run_record.run_result.stop_event_log:
        for stop_event in seed_run_record.run_result.stop_event_log:
            stop_event_by_id[stop_event.initiative_id] = stop_event

    # Group per-tick records by initiative_id.
    records_by_initiative: dict[str, list[object]] = {}
    for record in per_tick_records:
        records_by_initiative.setdefault(record.initiative_id, []).append(record)

    # ---- Single-panel figure ----
    fig, ax = plt.subplots(figsize=(12, 6))

    for role, initiative_id in sorted(selected.items()):
        initiative_records = records_by_initiative.get(initiative_id, [])
        if not initiative_records:
            continue

        ticks = [r.tick for r in initiative_records]
        beliefs = [r.quality_belief_t for r in initiative_records]

        config = config_by_id.get(initiative_id)
        latent_quality = config.latent_quality if config else 0.0
        generation_tag = (config.generation_tag or "unknown") if config else "unknown"
        color = _get_trajectory_role_color(role)

        # Legend label includes role, family, and ground-truth quality.
        legend_label = f"{role} ({generation_tag}, q={latent_quality:.3f})"

        # Belief trajectory line.
        ax.plot(
            ticks,
            beliefs,
            color=color,
            linewidth=1.5,
            label=legend_label,
        )

        # Latent quality reference — same color, dashed, no legend entry
        # to avoid clutter (the label already states q).
        ax.axhline(
            y=latent_quality,
            color=color,
            linestyle="--",
            linewidth=0.8,
            alpha=0.4,
        )

        # Stop marker — vertical dotted line in pink.
        stop_event = stop_event_by_id.get(initiative_id)
        if stop_event is not None:
            ax.axvline(
                x=stop_event.tick,
                color=color,
                linestyle=":",
                linewidth=1.0,
                alpha=0.5,
            )

        # Completion marker — vertical dotted line in the role color.
        terminal_state = terminal_by_id.get(initiative_id)
        if terminal_state is not None and terminal_state.completed_tick is not None:
            ax.axvline(
                x=terminal_state.completed_tick,
                color=color,
                linestyle=":",
                linewidth=1.0,
                alpha=0.5,
            )

    ax.set_xlabel("Tick (weeks)")
    ax.set_ylabel("Quality Belief")
    ax.set_ylim(-0.05, 1.05)
    ax.set_title(
        f"Initiative Trajectory Overlay ({condition_id})",
        fontsize=13,
    )
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()

    output_path = figures_dir / f"trajectory_overlay_{condition_id}.png"
    fig.savefig(str(output_path))
    plt.close(fig)
    logger.info("Generated %s", output_path.name)

    return output_path


# ===========================================================================
# Trajectory figure orchestrator
# ===========================================================================


def generate_trajectory_figures(
    experiment_spec: ExperimentSpec,
    representative_rows: list[dict],
    figures_dir: Path,
) -> None:
    """Generate trajectory figures for every experimental condition.

    For each condition, this function:
      1. Finds the median-value representative seed from representative_rows
      2. Locates the corresponding SeedRunRecord by world_seed
      3. Selects ~5 representative initiatives via select_representative_initiatives()
      4. Calls both plot_trajectory_beliefs() and plot_trajectory_overlay()

    Args:
        experiment_spec: The top-level ExperimentSpec carrying all condition
            records and their seed run records.
        representative_rows: List of row-dicts from the representative_runs
            table. Each row has experimental_condition_id, selection_rule,
            and seed_run_id fields. The world_seed is extracted from the
            seed_run_id (format: "{condition_id}__seed_{world_seed}").
        figures_dir: Directory to write trajectory PNGs into.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)

    for condition_record in experiment_spec.condition_records:
        condition_id = condition_record.condition_spec.experimental_condition_id

        # ---- Find the median-value representative seed for this condition ----
        median_seed_row = None
        for row in representative_rows:
            if (
                row.get("experimental_condition_id") == condition_id
                and row.get("selection_rule") == "median_value"
            ):
                median_seed_row = row
                break

        if median_seed_row is None:
            logger.warning(
                "No median-value representative found for condition %s; "
                "skipping trajectory figures",
                condition_id,
            )
            continue

        # The representative_runs table uses seed_run_id (format:
        # "{condition_id}__seed_{world_seed}") not a bare world_seed.
        # Extract the world seed from seed_run_id to match against
        # SeedRunRecord.world_seed.
        representative_seed_run_id = median_seed_row["seed_run_id"]
        # Parse world seed from the seed_run_id suffix.
        try:
            representative_world_seed = int(representative_seed_run_id.rsplit("__seed_", 1)[1])
        except (IndexError, ValueError):
            logger.warning(
                "Could not parse world_seed from seed_run_id=%s for condition %s; "
                "skipping trajectory figures",
                representative_seed_run_id,
                condition_id,
            )
            continue

        # ---- Find the SeedRunRecord matching the representative world_seed ----
        matching_seed_run_record: SeedRunRecord | None = None
        for seed_run_record in condition_record.seed_run_records:
            if seed_run_record.world_seed == representative_world_seed:
                matching_seed_run_record = seed_run_record
                break

        if matching_seed_run_record is None:
            logger.warning(
                "SeedRunRecord not found for world_seed=%d in condition %s; "
                "skipping trajectory figures",
                representative_world_seed,
                condition_id,
            )
            continue

        # ---- Guard: per-tick records required for trajectories ----
        if matching_seed_run_record.run_result.per_initiative_tick_records is None:
            logger.warning(
                "per_initiative_tick_records is None for condition %s seed %d; "
                "skipping trajectory figures",
                condition_id,
                representative_world_seed,
            )
            continue

        # ---- Select representative initiatives (~5 roles) ----
        selected_initiatives = select_representative_initiatives(
            matching_seed_run_record,
        )

        if not selected_initiatives:
            logger.warning(
                "No representative initiatives selected for condition %s; "
                "skipping trajectory figures",
                condition_id,
            )
            continue

        logger.info(
            "Generating trajectory figures for condition %s " "(seed %d, %d representatives)",
            condition_id,
            representative_world_seed,
            len(selected_initiatives),
        )

        # ---- Generate both trajectory figure variants ----
        plot_trajectory_beliefs(
            condition_id,
            selected_initiatives,
            matching_seed_run_record,
            figures_dir,
        )
        plot_trajectory_overlay(
            condition_id,
            selected_initiatives,
            matching_seed_run_record,
            figures_dir,
        )
