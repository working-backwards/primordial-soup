"""Author-curated reasonable-range anchors for the single-run report.

Per single_run_report_spec.md §The headline metrics, every surfaced
metric has a one-line plain-language definition, a unit, and a
reasonable range indicating whether the observed value is ordinary or
unusual. The ranges are intentionally curated, not asserted in tests:

- Empirical ranges from calibration runs drift whenever model physics
  change.
- Theoretical bounds rarely exist for multi-mechanism aggregates.

So we store indicative anchors here, keyed by `baseline_spec_version`
(the calibration/modeling revision the run was produced under — see
`runner.BASELINE_SPEC_VERSION`). When the model is re-calibrated and
the version is bumped, the ranges are reviewed as part of that bump.

The anchors are anchored to the canonical `balanced_incumbent`
environment at `total_labor_endowment=210`, `tick_horizon=313`, with a
3-seed cohort under the three named policy presets.

The data is a pure Python dict so tests can inspect it and report_gen
can format it without importing YAML. Each metric entry:

- ``label``     — plain-language name (matches the metric table heading)
- ``definition`` — one-liner describing what the metric means
- ``unit``      — business unit or unitless scale ("%", "×", "count",
                  "week", "0–1 scale", or a value-unit placeholder
                  ``"{value_unit}"``/``"{value_unit}/week"`` that
                  report_gen.py substitutes at render time)
- ``range``     — ``(low, high)`` tuple. ``None`` for either bound means
                  the anchor is open on that side. A single-element
                  string range (e.g. ``"weeks 100–250"``) is rendered
                  verbatim for metrics whose reasonable band is phrased
                  qualitatively rather than numerically.
- ``source``    — dotted path to the source field on the condition-level
                  row in ``experimental_conditions.parquet`` (or a
                  symbolic descriptor like ``"family_outcomes"`` for
                  per-family metrics rendered from that table).

See ``report_gen.py`` for how these are materialised into the
headline-metrics table and the 4-paragraph narrative.
"""

from __future__ import annotations

from typing import Any

# The canonical set of metric keys — stable; used by report_gen.py and
# tests. Order here determines table row order.
METRIC_KEYS: tuple[str, ...] = (
    "total_value",
    "value_from_completions",
    "value_from_residual",
    "value_from_baseline",
    "major_wins_surfaced",
    "productivity_at_end",
    "peak_productivity",
    "free_value_per_week_at_end",
    "idle_team_weeks_share",
    "pool_exhaustion_week",
    "initiatives_stopped",
    "initiatives_completed",
    "right_tail_false_stop_rate",
    "time_to_first_completion",
    "ramp_overhead",
    "quality_estimation_error",
)


# Ranges keyed by baseline_spec_version. When the version bumps, add a
# new entry here (optionally keeping the old one for historical runs).
# Missing version → report_gen.py falls back to the latest entry with a
# "stale anchor" note.
RANGES_BY_BASELINE_SPEC_VERSION: dict[str, dict[str, dict[str, Any]]] = {
    "v2-intake-baseline-thinning": {
        # #1 — Total value (sum of completion + residual + baseline).
        "total_value": {
            "label": "Total value",
            "definition": (
                "Sum of all value created during the run: completion payoffs, "
                "residual streams, and baseline-work value."
            ),
            "unit": "{value_unit}",
            "range": (3000.0, 7000.0),
            "source": "total_value_mean",
        },
        # #2 — Share of total from completion lumps.
        "value_from_completions": {
            "label": "Value from completions",
            "definition": (
                "Share of total value from one-time payoffs when initiatives " "finished."
            ),
            "unit": "% of total",
            "range": (0.40, 0.70),
            "source": "value_from_completions_share",
        },
        # #3 — Share of total from residual streams.
        "value_from_residual": {
            "label": "Value from residual streams",
            "definition": (
                "Share of total value from ongoing flywheel and quick-win "
                "streams after completion."
            ),
            "unit": "% of total",
            "range": (0.30, 0.55),
            "source": "value_from_residual_share",
        },
        # #4 — Share of total from baseline (idle-team) work.
        "value_from_baseline": {
            "label": "Value from baseline work",
            "definition": (
                "Share of total value from idle-team baseline activity "
                "(maintenance, support, incremental process work)."
            ),
            "unit": "% of total",
            # Zero unless the exec set a baseline rate; upper bound is
            # "any". The report displays "0% unless baseline rate set".
            "range": (0.0, 0.0),
            "source": "value_from_baseline_share",
        },
        # #5 — Right-tail breakthroughs (surfaced, not priced).
        "major_wins_surfaced": {
            "label": "Major wins surfaced",
            "definition": (
                "Right-tail breakthroughs governance allowed to complete. "
                "Count only; not priced into total value."
            ),
            "unit": "count",
            "range": (0.0, 5.0),
            "source": "surfaced_major_wins_mean",
        },
        # #6 — Terminal portfolio-capability multiplier C_t.
        "productivity_at_end": {
            "label": "Productivity multiplier at end",
            "definition": (
                "Portfolio-capability multiplier at the final week; 1.0× is "
                "baseline, >1× means enablers have compounded."
            ),
            "unit": "×",
            "range": (1.5, 3.0),
            "source": "terminal_capability_mean",
        },
        # #7 — Peak portfolio-capability multiplier.
        "peak_productivity": {
            "label": "Peak productivity multiplier",
            "definition": ("Highest capability multiplier reached at any week during " "the run."),
            "unit": "×",
            "range": (1.8, 3.0),
            "source": "peak_capacity_mean",
        },
        # #8 — Free value per week at end from live residual streams.
        "free_value_per_week_at_end": {
            "label": "Free value per week at end",
            "definition": (
                "Value per week the portfolio would keep generating with no "
                "further labor, from residual streams alive at the last week."
            ),
            "unit": "{value_unit}/week",
            "range": (2.0, 15.0),
            "source": "terminal_aggregate_residual_rate_mean",
        },
        # #9 — Share of team-weeks with no portfolio assignment.
        "idle_team_weeks_share": {
            "label": "Idle team-weeks share",
            "definition": (
                "Fraction of team-weeks where the team had no portfolio " "assignment."
            ),
            "unit": "% of team-weeks",
            "range": (0.40, 0.70),
            "source": "idle_pct_mean",
        },
        # #10 — First week when labor was free but no initiative activated.
        "pool_exhaustion_week": {
            "label": "Pool exhaustion week",
            "definition": (
                "First week when governance had labor to spare but no "
                "initiative above its activation threshold. "
                '"Not reached" if it never happened.'
            ),
            "unit": "week",
            "range": (100.0, 250.0),
            "source": "pool_exhaustion_tick_mean",
        },
        # #11 — Governance-stopped initiatives. Per-family breakdown comes
        # from family_outcomes; the total is surfaced on the condition row.
        "initiatives_stopped": {
            "label": "Initiatives stopped",
            "definition": (
                "Count of initiatives governance stopped before completion, "
                "with a QW / FW / EN / RT breakdown."
            ),
            "unit": "count",
            "range": (40.0, 100.0),
            "source": "family_outcomes.stopped_count",
        },
        # #12 — Initiatives that reached completion.
        "initiatives_completed": {
            "label": "Initiatives completed",
            "definition": (
                "Count of initiatives that reached completion, with a "
                "QW / FW / EN / RT breakdown."
            ),
            "unit": "count",
            "range": (40.0, 90.0),
            "source": "family_outcomes.completed_count",
        },
        # #13 — Of right-tails that would have surfaced a major win, what
        # fraction governance stopped before completion. None when no
        # eligibles existed.
        "right_tail_false_stop_rate": {
            "label": "Right-tail false-stop rate",
            "definition": (
                "Of right-tail initiatives that would have surfaced a major "
                "win, the fraction governance stopped before completion. "
                '"n/a" if no eligibles existed.'
            ),
            "unit": "%",
            "range": (0.0, 0.40),
            "source": "right_tail_false_stop_rate_mean",
        },
        # #14 — Time to first completion by family. The range is a dict
        # keyed by family label; report_gen renders each family row.
        "time_to_first_completion": {
            "label": "Time to first completion (by family)",
            "definition": (
                "Earliest week a QW / FW / EN / RT initiative completed. "
                '"None" if none did in that family.'
            ),
            "unit": "week per family",
            "range": {
                "quick_win": (5.0, 15.0),
                "flywheel": (30.0, 55.0),
                "enabler": (15.0, 30.0),
                "right_tail": (120.0, 200.0),
            },
            "source": "family_outcomes.first_completion_tick",
        },
        # #15 — Share of team-weeks in ramp-up after reassignment.
        "ramp_overhead": {
            "label": "Ramp overhead",
            "definition": (
                "Share of team-weeks spent ramping up after a reassignment "
                "(not yet fully productive)."
            ),
            "unit": "% of team-weeks",
            "range": (0.03, 0.08),
            "source": "ramp_labor_fraction_mean",
        },
        # #16 — Mean absolute gap between belief and latent quality.
        "quality_estimation_error": {
            "label": "Quality estimation error",
            "definition": (
                "Mean absolute gap between governance's quality belief and "
                "the latent true quality, averaged over initiative-weeks. "
                "Lower is better."
            ),
            "unit": "0–1 scale",
            "range": (0.05, 0.15),
            "source": "mean_absolute_belief_error_mean",
        },
    },
}


def get_ranges(baseline_spec_version: str) -> dict[str, dict[str, Any]]:
    """Return the metric-range anchor dict for a given baseline_spec_version.

    Falls back to the most recently added version (last key in the dict)
    if the requested one is not registered, so a run with an unexpected
    baseline spec still renders something readable. The fallback path
    emits no warning — the report renders the ranges unchanged; reviewers
    treat an un-updated range as a smell (single_run_report_spec.md
    §Range maintenance).

    Args:
        baseline_spec_version: Version string from runner.BASELINE_SPEC_VERSION
            (surfaced on the bundle manifest).

    Returns:
        Dict mapping metric key to the metric descriptor
        (label, definition, unit, range, source).
    """
    if baseline_spec_version in RANGES_BY_BASELINE_SPEC_VERSION:
        return RANGES_BY_BASELINE_SPEC_VERSION[baseline_spec_version]
    # Fall back to the most recently added (insertion-ordered) entry.
    return next(reversed(RANGES_BY_BASELINE_SPEC_VERSION.values()))
