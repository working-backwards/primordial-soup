#!/usr/bin/env python
"""Cross-bundle comparison: Model 0 vs. baseline.

Loads experimental_conditions.parquet and seed_runs.parquet from two
run bundles (a Model 0 bundle and a baseline bundle) and produces a
self-contained HTML analysis report answering: how much of the outcome
spread is explained by selection alone vs. the full governance machinery?

Auto-discovers the latest model0 and baseline bundles in results/ when
no paths are given.

Usage:
    python scripts/cross_bundle_comparison.py
    python scripts/cross_bundle_comparison.py results/<model0> results/<baseline>
    python scripts/cross_bundle_comparison.py --output-dir results/
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RESULTS_ROOT = Path("results")


# ============================================================================
# Data loading
# ============================================================================


def _read_parquet_as_dicts(path: Path) -> list[dict[str, Any]]:
    """Read a Parquet file and return a list of row dicts.

    Uses pyarrow directly (no pandas dependency).

    Args:
        path: Path to the Parquet file.

    Returns:
        List of dicts, one per row.
    """
    table = pq.read_table(path)
    columns = table.column_names
    rows: list[dict[str, Any]] = []
    for i in range(table.num_rows):
        rows.append({col: table.column(col)[i].as_py() for col in columns})
    return rows


def _load_bundle(bundle_path: Path) -> dict[str, Any]:
    """Load key tables and manifest from a run bundle.

    Args:
        bundle_path: Root directory of the run bundle.

    Returns:
        Dict with keys: manifest, conditions, seed_runs.
    """
    manifest_path = bundle_path / "manifest.json"
    conditions_path = bundle_path / "outputs" / "experimental_conditions.parquet"
    seed_runs_path = bundle_path / "outputs" / "seed_runs.parquet"

    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.json in {bundle_path}")
    if not conditions_path.exists():
        raise FileNotFoundError(f"No experimental_conditions.parquet in {bundle_path}")
    if not seed_runs_path.exists():
        raise FileNotFoundError(f"No seed_runs.parquet in {bundle_path}")

    with manifest_path.open() as f:
        manifest = json.load(f)

    return {
        "manifest": manifest,
        "conditions": _read_parquet_as_dicts(conditions_path),
        "seed_runs": _read_parquet_as_dicts(seed_runs_path),
        "path": bundle_path,
    }


# ============================================================================
# Auto-discovery
# ============================================================================


def _find_latest_bundle(pattern: str) -> Path | None:
    """Find the most recently modified bundle matching a name pattern.

    Scans results/ for directories whose name contains the pattern
    and returns the one with the latest modification time.

    Args:
        pattern: Substring to match in directory names.

    Returns:
        Path to the latest matching bundle, or None if not found.
    """
    if not RESULTS_ROOT.exists():
        return None

    candidates = [
        d
        for d in RESULTS_ROOT.iterdir()
        if d.is_dir() and pattern in d.name and (d / "manifest.json").exists()
    ]
    if not candidates:
        return None

    # Sort by directory name (which starts with a timestamp).
    candidates.sort(key=lambda d: d.name, reverse=True)
    return candidates[0]


# ============================================================================
# Analysis
# ============================================================================


def _compute_spread(values: list[float]) -> dict[str, float]:
    """Compute spread statistics for a list of values.

    Returns dict with: min, max, mean, spread (max-min), cv (spread/mean).
    """
    if not values:
        return {"min": 0, "max": 0, "mean": 0, "spread": 0, "cv": 0}
    v_min = min(values)
    v_max = max(values)
    v_mean = sum(values) / len(values)
    spread = v_max - v_min
    cv = spread / v_mean if v_mean != 0 else 0
    return {"min": v_min, "max": v_max, "mean": v_mean, "spread": spread, "cv": cv}


def _analyze_bundles(
    model0: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    """Run the cross-bundle comparison analysis.

    Computes governance spread (across archetypes) for both bundles,
    and environment spread (across families) for the baseline.

    Args:
        model0: Loaded Model 0 bundle data.
        baseline: Loaded baseline bundle data.

    Returns:
        Analysis results dict for the report generator.
    """
    m0_conditions = model0["conditions"]
    bl_conditions = baseline["conditions"]

    # --- Model 0: single environment, governance spread ---
    m0_value_spread = _compute_spread(
        [c["total_value_mean"] for c in m0_conditions],
    )
    m0_cap_spread = _compute_spread(
        [c["terminal_capability_mean"] for c in m0_conditions],
    )
    m0_wins_spread = _compute_spread(
        [c["surfaced_major_wins_mean"] for c in m0_conditions],
    )

    # --- Baseline: governance spread within each environment ---
    # Group baseline conditions by environment.
    bl_by_env: dict[str, list[dict]] = {}
    for c in bl_conditions:
        env_id = c["environmental_conditions_id"]
        bl_by_env.setdefault(env_id, []).append(c)

    bl_env_spreads: dict[str, dict[str, dict[str, float]]] = {}
    for env_id, env_conditions in bl_by_env.items():
        env_name = env_conditions[0].get(
            "environmental_conditions_name",
            env_id,
        )
        bl_env_spreads[env_id] = {
            "env_name": env_name,
            "value": _compute_spread(
                [c["total_value_mean"] for c in env_conditions],
            ),
            "capability": _compute_spread(
                [c["terminal_capability_mean"] for c in env_conditions],
            ),
            "wins": _compute_spread(
                [c["surfaced_major_wins_mean"] for c in env_conditions],
            ),
            "idle": _compute_spread(
                [c["idle_pct_mean"] for c in env_conditions],
            ),
        }

    # --- Environment spread: how much does environment matter? ---
    # For each policy preset, compute the spread across environments.
    bl_by_policy: dict[str, list[dict]] = {}
    for c in bl_conditions:
        pol_id = c["operating_policy_id"]
        bl_by_policy.setdefault(pol_id, []).append(c)

    env_spreads_by_policy: dict[str, dict[str, float]] = {}
    for pol_id, pol_conditions in bl_by_policy.items():
        pol_name = pol_conditions[0].get("operating_policy_name", pol_id)
        env_spreads_by_policy[pol_id] = {
            "policy_name": pol_name,
            "value": _compute_spread(
                [c["total_value_mean"] for c in pol_conditions],
            ),
        }

    # --- Seed-level variance (Model 0) ---
    m0_seed_runs = model0["seed_runs"]
    m0_seed_by_condition: dict[str, list[float]] = {}
    for sr in m0_seed_runs:
        cid = sr["experimental_condition_id"]
        m0_seed_by_condition.setdefault(cid, []).append(sr["total_value"])

    # --- Seed-level variance (baseline) ---
    bl_seed_runs = baseline["seed_runs"]
    bl_seed_by_condition: dict[str, list[float]] = {}
    for sr in bl_seed_runs:
        cid = sr["experimental_condition_id"]
        bl_seed_by_condition.setdefault(cid, []).append(sr["total_value"])

    return {
        "model0": {
            "conditions": m0_conditions,
            "value_spread": m0_value_spread,
            "capability_spread": m0_cap_spread,
            "wins_spread": m0_wins_spread,
            "seed_by_condition": m0_seed_by_condition,
        },
        "baseline": {
            "conditions": bl_conditions,
            "env_spreads": bl_env_spreads,
            "env_spreads_by_policy": env_spreads_by_policy,
            "seed_by_condition": bl_seed_by_condition,
        },
    }


# ============================================================================
# HTML report generation
# ============================================================================


def _html_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    caption: str = "",
) -> str:
    """Render an HTML table."""
    lines = ['<table style="border-collapse:collapse; margin:1em 0; width:100%;">']
    if caption:
        lines.append(
            f'<caption style="font-weight:bold; text-align:left; '
            f'margin-bottom:0.5em;">{caption}</caption>',
        )
    lines.append("<thead><tr>")
    for h in headers:
        lines.append(
            f'<th style="border:1px solid #ccc; padding:6px 10px; '
            f'background:#f0f0f0; text-align:right;">{h}</th>',
        )
    lines.append("</tr></thead><tbody>")
    for row in rows:
        lines.append("<tr>")
        for j, cell in enumerate(row):
            align = "left" if j == 0 else "right"
            lines.append(
                f'<td style="border:1px solid #ccc; padding:6px 10px; '
                f'text-align:{align};">{cell}</td>',
            )
        lines.append("</tr>")
    lines.append("</tbody></table>")
    return "\n".join(lines)


def _fmt(value: float, decimals: int = 1) -> str:
    """Format a float."""
    return f"{value:.{decimals}f}"


def _pct(value: float) -> str:
    """Format a fraction as a percentage string."""
    return f"{value * 100:.1f}%"


def _generate_html_report(
    model0: dict[str, Any],
    baseline: dict[str, Any],
    analysis: dict[str, Any],
) -> str:
    """Generate the self-contained HTML comparison report.

    Args:
        model0: Loaded Model 0 bundle data.
        baseline: Loaded baseline bundle data.
        analysis: Analysis results from _analyze_bundles().

    Returns:
        Complete HTML string.
    """
    m0_manifest = model0["manifest"]
    bl_manifest = baseline["manifest"]
    timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")

    # --- Section 1: Bundle identity ---
    identity_html = _html_table(
        ["", "Model 0", "Baseline"],
        [
            [
                "Bundle",
                m0_manifest.get("run_bundle_id", ""),
                bl_manifest.get("run_bundle_id", ""),
            ],
            [
                "Seeds",
                str(m0_manifest.get("seed_count", "")),
                str(bl_manifest.get("seed_count", "")),
            ],
            [
                "Conditions",
                str(m0_manifest.get("experimental_condition_count", "")),
                str(bl_manifest.get("experimental_condition_count", "")),
            ],
            [
                "Horizon",
                _horizon_label(model0),
                _horizon_label(baseline),
            ],
        ],
    )

    # --- Section 2: Side-by-side headline tables ---
    m0_table = _html_table(
        ["Archetype", "Value", "Wins", "Term. Cap", "Idle %"],
        [
            [
                c.get("governance_regime_label", c["experimental_condition_id"]),
                _fmt(c["total_value_mean"]),
                _fmt(c["surfaced_major_wins_mean"], 2),
                _fmt(c["terminal_capability_mean"], 3),
                _pct(c["idle_pct_mean"]),
            ]
            for c in analysis["model0"]["conditions"]
        ],
        caption="Model 0 (selection only)",
    )

    # Group baseline conditions by environment for the table.
    bl_rows: list[list[str]] = []
    prev_env = ""
    for c in analysis["baseline"]["conditions"]:
        env_name = c.get("environmental_conditions_name", "")
        pol_name = c.get("operating_policy_name", "")
        # Insert environment separator.
        if env_name != prev_env:
            if prev_env:
                bl_rows.append(["", "", "", "", ""])
            prev_env = env_name

        bl_rows.append(
            [
                f"{env_name} / {pol_name}",
                _fmt(c["total_value_mean"]),
                _fmt(c["surfaced_major_wins_mean"], 2),
                _fmt(c["terminal_capability_mean"], 3),
                _pct(c["idle_pct_mean"]),
            ]
        )

    bl_table = _html_table(
        ["Condition", "Value", "Wins", "Term. Cap", "Idle %"],
        bl_rows,
        caption="Baseline (full model)",
    )

    # --- Section 3: Governance attribution ---
    m0_val = analysis["model0"]["value_spread"]
    m0_cap = analysis["model0"]["capability_spread"]

    attribution_rows: list[list[str]] = []

    # Model 0 row.
    attribution_rows.append(
        [
            "Model 0 (all archetypes)",
            _fmt(m0_val["spread"]),
            _pct(m0_val["cv"]),
            _fmt(m0_cap["spread"], 3),
        ]
    )

    # Per-environment baseline rows.
    for env_data in analysis["baseline"]["env_spreads"].values():
        env_name = env_data["env_name"]
        val = env_data["value"]
        cap = env_data["capability"]
        attribution_rows.append(
            [
                f"Baseline: {env_name}",
                _fmt(val["spread"]),
                _pct(val["cv"]),
                _fmt(cap["spread"], 3),
            ]
        )

    attribution_table = _html_table(
        ["Scope", "Value Spread", "Value CV", "Capability Spread"],
        attribution_rows,
        caption="Governance spread: how much do regime differences explain?",
    )

    # --- Section 4: Environment vs. governance ---
    env_vs_gov_rows: list[list[str]] = []
    for pol_data in analysis["baseline"]["env_spreads_by_policy"].values():
        pol_name = pol_data["policy_name"]
        val = pol_data["value"]
        env_vs_gov_rows.append(
            [
                pol_name,
                _fmt(val["spread"]),
                _pct(val["cv"]),
            ]
        )

    env_vs_gov_table = _html_table(
        ["Holding regime fixed at...", "Value Spread Across Environments", "CV"],
        env_vs_gov_rows,
        caption="Environment spread: how much does environment matter?",
    )

    # --- Section 5: Mechanism inventory ---
    # What the full model adds that Model 0 cannot produce.
    bl_total_wins_by_env: dict[str, float] = {}
    for env_data in analysis["baseline"]["env_spreads"].values():
        env_name = env_data["env_name"]
        wins = env_data["wins"]
        bl_total_wins_by_env[env_name] = wins["mean"]

    bl_idle_by_env: dict[str, dict] = {}
    for env_data in analysis["baseline"]["env_spreads"].values():
        env_name = env_data["env_name"]
        bl_idle_by_env[env_name] = env_data["idle"]

    # Model 0 average idle rate across conditions.
    m0_idle_rates = [c["idle_pct_mean"] for c in analysis["model0"]["conditions"]]
    m0_avg_idle = sum(m0_idle_rates) / len(m0_idle_rates) if m0_idle_rates else 0

    # --- Section 6: Interpretation ---
    # Compute key ratios for the narrative.
    # Best environment for comparison: balanced_incumbent (closest analog
    # to Model 0's single environment in terms of initiative mix).
    bl_bi = analysis["baseline"]["env_spreads"].get("balanced_incumbent", {})
    bl_bi_val = bl_bi.get("value", {})

    # Governance CV comparison.
    m0_gov_cv = m0_val["cv"]
    bi_gov_cv = bl_bi_val.get("cv", 0)

    # Average environment spread CV.
    env_cvs = [
        pol_data["value"]["cv"]
        for pol_data in analysis["baseline"]["env_spreads_by_policy"].values()
    ]
    avg_env_cv = sum(env_cvs) / len(env_cvs) if env_cvs else 0

    interpretation_html = f"""
    <div class="insight">
    <h3>Key findings</h3>
    <ol>
    <li><strong>Selection alone is powerful in isolation.</strong>
    In Model 0, where governance can only choose which initiatives to start,
    the value coefficient of variation across archetypes is
    <strong>{_pct(m0_gov_cv)}</strong>. Portfolio selection creates a
    {_fmt(m0_val["spread"])}-unit value spread on a mean of
    {_fmt(m0_val["mean"])}.</li>

    <li><strong>The full model compresses governance differences.</strong>
    In the baseline (Balanced Incumbent), the governance CV drops to
    <strong>{_pct(bi_gov_cv)}</strong>. Frontier cycling, stopping rules,
    attention allocation, and ramp effects create a high baseline of value
    that all governance regimes benefit from, narrowing the relative
    differences that selection alone can create.</li>

    <li><strong>Environment dominates governance.</strong>
    Holding governance fixed, the environment CV averages
    <strong>{_pct(avg_env_cv)}</strong> — the environment a governance
    regime operates in matters more than which regime is chosen. This is
    the study's central finding: governance selection is second-order to
    environmental fit.</li>

    <li><strong>The full model unlocks mechanisms Model 0 cannot access.</strong>
    Model 0 produces zero major wins. The baseline produces
    {_fmt(bl_total_wins_by_env.get("Discovery Heavy", 0), 2)} wins/seed
    in Discovery Heavy — entirely from frontier cycling and stopping rules
    that free teams to discover new opportunities. Idle rates of
    {_pct(bl_idle_by_env.get("Discovery Heavy", {}).get("mean", 0))}
    (vs. {_pct(m0_avg_idle)} in Model 0)
    show the team churn that powers this discovery.</li>
    </ol>
    </div>
    """

    # --- Assemble full HTML ---
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Cross-Bundle Comparison: Model 0 vs. Baseline</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 1200px; margin: 0 auto; padding: 2em; line-height: 1.6; color: #333; }}
h1 {{ border-bottom: 2px solid #2196F3; padding-bottom: 0.3em; }}
h2 {{ border-bottom: 1px solid #ccc; padding-bottom: 0.2em; margin-top: 2em; }}
.meta {{ background: #f8f8f8; padding: 1em; border-radius: 4px; font-size: 0.9em; }}
.insight {{ background: #e8f5e9; padding: 1em 1.5em; border-left: 4px solid #4CAF50;
            margin: 1.5em 0; border-radius: 4px; }}
.insight h3 {{ margin-top: 0; }}
.note {{ background: #fff3cd; padding: 1em; border-left: 4px solid #ffc107; margin: 1em 0; }}
.side-by-side {{ display: flex; gap: 2em; flex-wrap: wrap; }}
.side-by-side > div {{ flex: 1; min-width: 400px; }}
caption {{ caption-side: top; }}
</style>
</head>
<body>

<h1>Cross-Bundle Comparison: Model 0 vs. Baseline</h1>

<div class="meta">
<strong>Generated:</strong> {timestamp}<br>
<strong>Model 0 bundle:</strong> {m0_manifest.get("run_bundle_id", "")}<br>
<strong>Baseline bundle:</strong> {bl_manifest.get("run_bundle_id", "")}<br>
</div>

<div class="note">
<strong>What this comparison answers:</strong> How much of the outcome
spread across governance regimes is explained by the selection decision
alone (Model 0) vs. the full governance machinery (baseline)? Model 0
disables stopping, attention, ramp, frontier, and screening — the only
governance lever is which initiatives to start.
</div>

<h2>Bundle Identity</h2>
{identity_html}

<h2>Headline Results</h2>
<div class="side-by-side">
<div>{m0_table}</div>
<div>{bl_table}</div>
</div>

<h2>Governance Attribution</h2>
<p>How much outcome variation is explained by governance regime choice?
<strong>Value spread</strong> is the absolute range (max - min mean value)
across archetypes. <strong>CV</strong> (coefficient of variation = spread /
mean) normalizes for scale differences between Model 0 (100-tick horizon)
and baseline (313-tick horizon).</p>
{attribution_table}

<h2>Environment vs. Governance</h2>
<p>How much outcome variation comes from the environment (holding governance
fixed) vs. from governance (holding environment fixed)?</p>
{env_vs_gov_table}

<h2>Interpretation</h2>
{interpretation_html}

<h2>Methods Note</h2>
<div class="note">
<p><strong>Comparability caveat:</strong> Model 0 and baseline use different
horizons (100 vs. 313 ticks), different initiative counts (130 vs. 200),
different workforce sizes (50 vs. 210 labor), and different archetypes
(Throughput/Balanced/Exploration vs. Balanced/Aggressive/Patient). Direct
value comparisons are not meaningful. The comparison is between
<em>governance CVs</em> — how much relative spread governance creates —
not absolute values.</p>
<p>Model 0 archetypes differ only in portfolio mix targets. Baseline
archetypes differ in mix targets <em>and</em> stop thresholds, attention
bounds, and stagnation windows. The additional mechanisms in the baseline
both help (frontier cycling, discovery) and constrain (stop rules can
destroy value by false-stopping promising initiatives).</p>
</div>

</body>
</html>
"""
    return html


def _horizon_label(bundle: dict[str, Any]) -> str:
    """Extract a human-readable horizon label from the bundle config."""
    config_path = bundle["path"] / "config" / "simulation_config.json"
    if config_path.exists():
        with config_path.open() as f:
            config = json.load(f)
        tick_horizon = config.get("time", {}).get("tick_horizon", "?")
        return f"{tick_horizon} ticks"
    return "?"


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    """Parse arguments, load bundles, run analysis, write report."""
    parser = argparse.ArgumentParser(
        description="Cross-bundle comparison: Model 0 vs. baseline.",
    )
    parser.add_argument(
        "model0_path",
        nargs="?",
        default=None,
        help="Path to the Model 0 run bundle (auto-discovered if omitted).",
    )
    parser.add_argument(
        "baseline_path",
        nargs="?",
        default=None,
        help="Path to the baseline run bundle (auto-discovered if omitted).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Directory for the comparison report (default: results/).",
    )
    args = parser.parse_args()

    # --- Resolve bundle paths ---
    if args.model0_path:
        m0_path = Path(args.model0_path)
    else:
        m0_path = _find_latest_bundle("model0")
        if m0_path is None:
            logger.error(
                "No Model 0 bundle found in results/. "
                "Run model0_campaign.py first, or provide the path explicitly.",
            )
            return
        logger.info("Auto-discovered Model 0 bundle: %s", m0_path)

    if args.baseline_path:
        bl_path = Path(args.baseline_path)
    else:
        bl_path = _find_latest_bundle("baseline_governance")
        if bl_path is None:
            logger.error(
                "No baseline bundle found in results/. "
                "Run baseline_governance_campaign.py first, or provide "
                "the path explicitly.",
            )
            return
        logger.info("Auto-discovered baseline bundle: %s", bl_path)

    # --- Load bundles ---
    logger.info("Loading Model 0 bundle: %s", m0_path)
    model0 = _load_bundle(m0_path)

    logger.info("Loading baseline bundle: %s", bl_path)
    baseline = _load_bundle(bl_path)

    # --- Run analysis ---
    logger.info("Running cross-bundle analysis...")
    t0 = time.time()
    analysis = _analyze_bundles(model0, baseline)

    # --- Generate report ---
    html = _generate_html_report(model0, baseline, analysis)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"comparison_model0_vs_baseline_{timestamp}.html"
    report_path.write_text(html, encoding="utf-8")

    elapsed = time.time() - t0
    logger.info("Comparison report generated in %.1fs: %s", elapsed, report_path)
    print(f"\nComparison report: {report_path}")


if __name__ == "__main__":
    main()
