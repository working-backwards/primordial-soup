"""HTML and markdown report generation for run bundles.

Generates the human-facing report package: a static HTML report
(report/index.html) and a companion markdown report (report/report.md).

Both are derived from canonical table data and figures in the run
bundle. No jinja2 dependency — reports are generated with Python
f-strings and helper functions.

Two report shapes:

- **Single-run shape** (single_run_report_spec.md, 2026-04-18) — applied
  when the bundle contains exactly one experimental condition. Six
  sections: run identity, headline metrics, 4-paragraph narrative,
  figures with plain-language captions, governance-actions detail,
  appendix with full config and reproduction instructions.
- **Multi-condition shape** (reporting_package_specification.md §HTML
  report-package structure) — preserved for bundles with multiple
  conditions. Comparison-first layout.

The single-run path reads author-curated reasonable-range anchors from
report_ranges.py keyed by the bundle's ``baseline_spec_version``.

Design references:
    docs/design/single_run_report_spec.md
    docs/design/exec_intent_spec.md
    docs/implementation/reporting_package_specification.md
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from primordial_soup.report_ranges import METRIC_KEYS, get_ranges

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Figure captions (single-run shape)
# ---------------------------------------------------------------------------
#
# Per single_run_report_spec.md §Figure captions, each figure gets a
# one-sentence plain-language caption that says what the axes show and
# what pattern means "this governance regime did its job." The spec
# explicitly places these next to the figure filename in this module
# rather than in figures.py or the spec itself, so edits stay close to
# the render site.

SINGLE_RUN_FIGURE_CAPTIONS: dict[str, tuple[str, str]] = {
    # filename → (display title, one-sentence caption)
    "value_by_year_stacked.png": (
        "Value by year — stacked by family",
        "Yearly value creation decomposed into quick-win, flywheel, "
        "enabler, and right-tail contributions. A healthy portfolio "
        "typically shows flywheel and quick-win stacks growing over "
        "time; enablers show up later; right-tail shows intermittently.",
    ),
    "cumulative_value_by_year.png": (
        "Cumulative priced value by year",
        "Running total of priced value across the run. A steepening "
        "curve means governance is compounding; a flattening one means "
        "the portfolio has run out of high-quality work to do.",
    ),
    "surfaced_major_wins_by_year.png": (
        "Surfaced major wins by year",
        "Count of right-tail breakthroughs governance allowed to "
        "complete, binned by year. Values are surfaced, not priced — "
        "more wins earlier means patient governance paid off.",
    ),
    "tradeoff_frontier.png": (
        "Tradeoff frontier",
        "Total value vs. major-win count across seeds. Governance that "
        "lands in the upper-right is both productive and "
        "breakthrough-discovering; upper-left is productive but "
        "breakthrough-starved.",
    ),
    "terminal_capability.png": (
        "Terminal capability",
        "The portfolio-capability multiplier at the final week. 1.0× is "
        "baseline; values above 1.5× indicate enablers compounded into "
        "durable capability.",
    ),
    "rt_survival_curves.png": (
        "Right-tail false-stop rate",
        "Of right-tail initiatives that would have surfaced a major "
        "win, the fraction governance stopped before completion. Lower "
        "is better — near-zero means patience with the right "
        "initiatives.",
    ),
    "enabler_dashboard.png": (
        "Enabler dashboard",
        "When enablers complete, the productivity multiplier steps up; "
        "long flat stretches mean enablers are stalled or being "
        "stopped before delivering capability.",
    ),
    "representative_timelines.png": (
        "Representative-run timelines",
        "Mechanism-level timeline for the median-value seed run: "
        "completions, stops, and major-win events over weeks. Useful "
        "for reading governance behaviour one run at a time.",
    ),
    "seed_distributions.png": (
        "Seed-level distributions",
        "Per-seed distributions of headline outcomes. Narrow spreads "
        "mean the regime's behaviour is consistent across stochastic "
        "draws; wide spreads mean seed-to-seed variance dominates.",
    ),
}


def _caption_for(filename: str) -> tuple[str, str]:
    """Look up the (title, caption) pair for a figure filename.

    Falls back to the filename stem when no caption is registered — new
    figures still render, just without the single-run flavour text.
    """
    if filename in SINGLE_RUN_FIGURE_CAPTIONS:
        return SINGLE_RUN_FIGURE_CAPTIONS[filename]
    stem = filename.rsplit(".", 1)[0].replace("_", " ").title()
    return stem, ""


# ---------------------------------------------------------------------------
# HTML table rendering
# ---------------------------------------------------------------------------


def _html_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    caption: str = "",
) -> str:
    """Render an HTML table from headers and row data.

    Args:
        headers: Column header labels.
        rows: List of rows, each a list of cell values (as strings).
        caption: Optional table caption.

    Returns:
        HTML string for the table.
    """
    lines = ['<table style="border-collapse:collapse; margin:1em 0;">']
    if caption:
        lines.append(f"<caption>{caption}</caption>")
    lines.append("<thead><tr>")
    for h in headers:
        th_style = "border:1px solid #ccc; padding:6px 10px; background:#f0f0f0;"
        lines.append(f'<th style="{th_style}">{h}</th>')
    lines.append("</tr></thead><tbody>")
    for row in rows:
        lines.append("<tr>")
        for cell in row:
            lines.append(f'<td style="border:1px solid #ccc; padding:6px 10px;">{cell}</td>')
        lines.append("</tr>")
    lines.append("</tbody></table>")
    return "\n".join(lines)


def _md_table(
    headers: list[str],
    rows: list[list[str]],
) -> str:
    """Render a GFM pipe-format markdown table.

    Args:
        headers: Column header labels.
        rows: List of rows, each a list of cell values (as strings).

    Returns:
        Markdown string for the table.
    """
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _fmt(value: Any, decimals: int = 2) -> str:
    """Format a numeric value for display.

    Handles None → 'N/A', floats → fixed decimals, ints → str.
    """
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


# ---------------------------------------------------------------------------
# Headline comparison table data
# ---------------------------------------------------------------------------


def _build_headline_table(
    condition_rows: list[dict[str, Any]],
) -> tuple[list[str], list[list[str]]]:
    """Build the headline comparison table.

    Returns (headers, rows) for rendering as HTML or markdown.
    """
    headers = [
        "Condition",
        "Value (mean)",
        "Major Wins (mean)",
        "Terminal Cap (mean)",
        "RT False-Stop Rate",
        "Idle %",
    ]
    rows: list[list[str]] = []
    for r in condition_rows:
        label = r.get("governance_regime_label", r.get("experimental_condition_id", ""))
        rows.append(
            [
                str(label),
                _fmt(r.get("total_value_mean")),
                _fmt(r.get("surfaced_major_wins_mean")),
                _fmt(r.get("terminal_capability_mean"), 3),
                _fmt(r.get("right_tail_false_stop_rate_mean"), 3),
                _fmt(r.get("idle_pct_mean"), 3),
            ]
        )
    return headers, rows


# ---------------------------------------------------------------------------
# Trajectory figure discovery
# ---------------------------------------------------------------------------


def _build_trajectory_figures_html(figures_dir: Path) -> str:
    """Build HTML for trajectory figures dynamically discovered in figures_dir.

    Trajectory figures are conditional — they only exist when per-tick data
    was recorded. This scans for trajectory_beliefs_*.png and
    trajectory_overlay_*.png and renders them if present.

    Returns empty string if no trajectory figures exist.
    """
    html_parts: list[str] = []

    # Discover trajectory belief figures (multi-subplot, one per condition).
    beliefs_files = sorted(figures_dir.glob("trajectory_beliefs_*.png"))
    overlay_files = sorted(figures_dir.glob("trajectory_overlay_*.png"))

    if not beliefs_files and not overlay_files:
        html_parts.append(
            '<p style="color:#888;">No trajectory figures available '
            "(per-tick logging may not have been enabled).</p>"
        )
        return "\n".join(html_parts)

    for fpath in beliefs_files:
        condition_id = fpath.stem.removeprefix("trajectory_beliefs_")
        caption = f"Quality Belief Trajectories — {condition_id}"
        html_parts.append('<figure style="margin:1em 0;">')
        html_parts.append(
            f'<img src="../figures/{fpath.name}" style="max-width:100%;" alt="{caption}">'
        )
        html_parts.append(f"<figcaption>{caption}</figcaption>")
        html_parts.append("</figure>")

    for fpath in overlay_files:
        condition_id = fpath.stem.removeprefix("trajectory_overlay_")
        caption = f"Trajectory Overlay — {condition_id}"
        html_parts.append('<figure style="margin:1em 0;">')
        html_parts.append(
            f'<img src="../figures/{fpath.name}" style="max-width:100%;" alt="{caption}">'
        )
        html_parts.append(f"<figcaption>{caption}</figcaption>")
        html_parts.append("</figure>")

    return "\n".join(html_parts)


def _build_trajectory_figures_markdown(figures_dir: Path) -> str:
    """Build markdown for trajectory figures dynamically discovered in figures_dir.

    Returns empty string if no trajectory figures exist.
    """
    md_parts: list[str] = []

    beliefs_files = sorted(figures_dir.glob("trajectory_beliefs_*.png"))
    overlay_files = sorted(figures_dir.glob("trajectory_overlay_*.png"))

    if not beliefs_files and not overlay_files:
        md_parts.append(
            "*No trajectory figures available (per-tick logging may not have been enabled).*"
        )
        return "\n\n".join(md_parts)

    for fpath in beliefs_files:
        condition_id = fpath.stem.removeprefix("trajectory_beliefs_")
        caption = f"Quality Belief Trajectories — {condition_id}"
        md_parts.append(f"### {caption}\n\n![{caption}](../figures/{fpath.name})")

    for fpath in overlay_files:
        condition_id = fpath.stem.removeprefix("trajectory_overlay_")
        caption = f"Trajectory Overlay — {condition_id}"
        md_parts.append(f"### {caption}\n\n![{caption}](../figures/{fpath.name})")

    return "\n\n".join(md_parts)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------


def _generate_html_report(
    manifest: dict[str, Any],
    table_data: dict[str, list[dict[str, Any]]],
    figures_dir: Path,
    report_dir: Path,
) -> None:
    """Generate report/index.html.

    Single static HTML file with embedded CSS and all required sections
    per the reporting package specification.
    """
    conditions = table_data.get("experimental_conditions", [])
    headline_headers, headline_rows = _build_headline_table(conditions)

    # Build figure HTML (relative paths from report/ to figures/).
    figure_names = [
        ("value_by_year_stacked.png", "Value by Year — Stacked by Family"),
        ("cumulative_value_by_year.png", "Cumulative Priced Value by Year"),
        ("surfaced_major_wins_by_year.png", "Surfaced Major Wins by Year"),
        ("tradeoff_frontier.png", "Tradeoff Frontier"),
        ("terminal_capability.png", "Terminal Capability Comparison"),
        ("rt_survival_curves.png", "Right-Tail False-Stop Rate"),
        ("enabler_dashboard.png", "Enabler Dashboard"),
    ]
    figure_html = ""
    for fname, caption in figure_names:
        fpath = figures_dir / fname
        if fpath.exists():
            figure_html += '<figure style="margin:1em 0;">\n'
            img_src = f"../figures/{fname}"
            figure_html += f'<img src="{img_src}" style="max-width:100%;" alt="{caption}">\n'
            figure_html += f"<figcaption>{caption}</figcaption>\n"
            figure_html += "</figure>\n"

    # Appendix figures.
    appendix_figures = [
        ("seed_distributions.png", "Seed-Level Distributions"),
    ]
    appendix_html = ""
    for fname, caption in appendix_figures:
        fpath = figures_dir / fname
        if fpath.exists():
            appendix_html += '<figure style="margin:1em 0;">\n'
            img_src = f"../figures/{fname}"
            appendix_html += f'<img src="{img_src}" style="max-width:100%;" alt="{caption}">\n'
            appendix_html += f"<figcaption>{caption}</figcaption>\n"
            appendix_html += "</figure>\n"

    # Extract nested values before the f-string to avoid brace-escaping issues.
    telemetry = manifest.get("telemetry", {})
    seed_runs_completed = telemetry.get("seed_runs_completed", "")

    # Build representative-timelines figure HTML outside the f-string
    # to avoid E501 on the img/figcaption lines.
    rep_img = (
        '<img src="../figures/representative_timelines.png"'
        ' style="max-width:100%;"'
        ' alt="Representative-Run Timelines">'
    )
    rep_caption = (
        "Representative-Run Timelines"
        " — events over ticks for the"
        " median-value seed run per condition"
    )
    rep_figure_html = (
        '<figure style="margin:1em 0;">\n'
        f"{rep_img}\n"
        f"<figcaption>{rep_caption}</figcaption>\n"
        "</figure>"
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{manifest.get("title", "Experiment Report")}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 1200px; margin: 0 auto; padding: 2em; line-height: 1.6; color: #333; }}
h1 {{ border-bottom: 2px solid #2196F3; padding-bottom: 0.3em; }}
h2 {{ border-bottom: 1px solid #ccc; padding-bottom: 0.2em; margin-top: 2em; }}
.meta {{ background: #f8f8f8; padding: 1em; border-radius: 4px; font-size: 0.9em; }}
.note {{ background: #fff3cd; padding: 1em; border-left: 4px solid #ffc107; margin: 1em 0; }}
figure {{ text-align: center; }}
figcaption {{ font-style: italic; font-size: 0.9em; color: #666; }}
</style>
</head>
<body>

<h1>{manifest.get("title", "Experiment Report")}</h1>

<div class="meta">
<strong>Run Bundle:</strong> {manifest.get("run_bundle_id", "")}<br>
<strong>Script:</strong> {manifest.get("script", "")}<br>
<strong>Created:</strong> {manifest.get("created_at", "")}<br>
<strong>Git Commit:</strong> {manifest.get("git_commit", "")}<br>
<strong>Schema Version:</strong> {manifest.get("schema_version", "")}<br>
<strong>Conditions:</strong> {manifest.get("experimental_condition_count", "")},
<strong>Seeds:</strong> {manifest.get("seed_count", "")}
</div>

<h2>Study Interpretation Notes</h2>
<div class="note">
<ul>
<li><strong>Right-tail wins are surfaced-not-priced by design.</strong> The major-win count
tracks how many breakthrough opportunities governance allowed to complete. It is not
included in the total priced value.</li>
<li><strong>Terminal capability is a primary outcome.</strong> It measures the organization's
accumulated learning environment at the end of the study horizon.</li>
<li><strong>Experimental-condition labels are inherited from run-bundle presets.</strong></li>
</ul>
</div>

<h2>Executive Summary</h2>
<h3>Headline Comparison</h3>
{_html_table(headline_headers, headline_rows)}

<h2>Core Figures</h2>
{figure_html}

<h2>Diagnostic Interpretation</h2>
<p>See the right-tail false-stop rate and enabler dashboard figures above for
governance quality diagnostics. Lower false-stop rates indicate governance that
better preserves latent breakthrough opportunities.</p>

<h2>Representative Runs</h2>
<p>Representative seed runs are selected per condition: median, max, and min total value.
See the representative-run timeline figure below for a mechanism-level drill-down.</p>
{rep_figure_html}

<h2>Initiative Trajectories</h2>
<p>Per-initiative quality belief trajectories for representative initiatives selected
from the median-value seed run per condition. Shows quality belief convergence toward
latent quality, attention allocation, and stop/completion/major-win events.</p>
{_build_trajectory_figures_html(figures_dir)}

<h2>Methods and Reproducibility</h2>
<ul>
<li><strong>Seeds:</strong> {manifest.get("world_seeds", [])}</li>
<li><strong>Conditions:</strong> {manifest.get("experimental_condition_count", "")}</li>
<li><strong>Completed seed runs:</strong> {seed_runs_completed}</li>
<li><strong>Horizon:</strong> per run configuration</li>
<li><strong>Command:</strong> <code>{manifest.get("command", "")}</code></li>
</ul>

<h2>Appendix</h2>
{appendix_html}

</body>
</html>
"""

    (report_dir / "index.html").write_text(html, encoding="utf-8")
    logger.info("Generated report/index.html")


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def _generate_markdown_report(
    manifest: dict[str, Any],
    table_data: dict[str, list[dict[str, Any]]],
    figures_dir: Path,
    report_dir: Path,
) -> None:
    """Generate report/report.md.

    Companion markdown with parallel structure to the HTML report.
    """
    conditions = table_data.get("experimental_conditions", [])
    headline_headers, headline_rows = _build_headline_table(conditions)

    # Extract nested values before f-string.
    telemetry = manifest.get("telemetry", {})
    seed_runs_completed = telemetry.get("seed_runs_completed", "")

    md = f"""# {manifest.get("title", "Experiment Report")}

**Run Bundle:** {manifest.get("run_bundle_id", "")}
**Script:** {manifest.get("script", "")}
**Created:** {manifest.get("created_at", "")}
**Git Commit:** {manifest.get("git_commit", "")}
**Schema Version:** {manifest.get("schema_version", "")}

## Study Interpretation Notes

- **Right-tail wins are surfaced-not-priced by design.** The major-win count
  tracks how many breakthrough opportunities governance allowed to complete.
- **Terminal capability is a primary outcome.**
- **Labels are inherited from run-bundle presets.**

## Executive Summary

### Headline Comparison

{_md_table(headline_headers, headline_rows)}

## Core Figures

"""

    figure_names = [
        ("value_by_year_stacked.png", "Value by Year — Stacked by Family"),
        ("cumulative_value_by_year.png", "Cumulative Priced Value by Year"),
        ("surfaced_major_wins_by_year.png", "Surfaced Major Wins by Year"),
        ("tradeoff_frontier.png", "Tradeoff Frontier"),
        ("terminal_capability.png", "Terminal Capability Comparison"),
        ("rt_survival_curves.png", "Right-Tail False-Stop Rate"),
        ("enabler_dashboard.png", "Enabler Dashboard"),
    ]
    for fname, caption in figure_names:
        if (figures_dir / fname).exists():
            md += f"### {caption}\n\n![{caption}](../figures/{fname})\n\n"

    md += """## Representative Runs

Representative seed runs are selected per condition: median, max, and min total value.

### Representative-Run Timelines

![Representative-Run Timelines](../figures/representative_timelines.png)

## Initiative Trajectories

Per-initiative quality belief trajectories for representative initiatives selected
from the median-value seed run per condition. Shows quality belief convergence toward
latent quality, attention allocation, and stop/completion/major-win events.

"""

    md += _build_trajectory_figures_markdown(figures_dir)
    md += "\n\n"

    md += f"""## Methods and Reproducibility

- **Seeds:** {manifest.get("world_seeds", [])}
- **Conditions:** {manifest.get("experimental_condition_count", "")}
- **Completed seed runs:** {seed_runs_completed}
- **Command:** `{manifest.get("command", "")}`

## Appendix

"""

    if (figures_dir / "seed_distributions.png").exists():
        md += (
            "### Seed-Level Distributions\n\n"
            "![Seed Distributions]"
            "(../figures/seed_distributions.png)\n\n"
        )

    (report_dir / "report.md").write_text(md, encoding="utf-8")
    logger.info("Generated report/report.md")


# ---------------------------------------------------------------------------
# Single-run shape — helpers (single_run_report_spec.md, 2026-04-18)
# ---------------------------------------------------------------------------


def _fmt_mean_range(mean: Any, lo: Any, hi: Any, decimals: int = 2) -> str:
    """Format ``mean (lo–hi)`` when a per-seed range is available.

    The single-run report spec calls for the mean-across-seeds as the
    headline number with the per-seed min–max shown inline. Single-seed
    runs drop the range; zero-seed runs render as N/A.

    Missing bound: renders the point value alone (no parentheses).
    """
    if mean is None:
        return "N/A"
    mean_str = _fmt(mean, decimals)
    if lo is None or hi is None or lo == hi:
        return mean_str
    return f"{mean_str} ({_fmt(lo, decimals)}–{_fmt(hi, decimals)})"


def _fmt_percent(value: Any, decimals: int = 0) -> str:
    """Render a 0–1 fraction as a percentage. ``None`` → 'n/a'."""
    if value is None:
        return "n/a"
    return f"{value * 100:.{decimals}f}%"


def _fmt_range(range_spec: Any, unit: str, value_unit: str) -> str:
    """Format a range-anchor tuple for display, substituting value_unit.

    The metric anchors in report_ranges.py express ranges as
    ``(low, high)`` pairs; the per-family anchor for #14 uses a dict.
    This helper formats only the simple tuple case — per-family metrics
    are rendered row-by-row by the governance-actions renderer.

    Args:
        range_spec: ``(low, high)`` tuple or ``None``.
        unit: Display unit. May contain ``{value_unit}`` placeholders.
        value_unit: Exec-supplied value label (e.g. ``"$M"``).

    Returns:
        Rendered range string, e.g. ``"3,000 – 7,000 $M"`` or
        ``"40 – 70 %"``. ``"(curated band unavailable)"`` for unknown
        shapes.
    """
    if range_spec is None or not isinstance(range_spec, tuple) or len(range_spec) != 2:
        return "(curated band unavailable)"
    lo, hi = range_spec
    unit_rendered = unit.replace("{value_unit}", value_unit)
    # Percentages: the underlying share is in [0, 1] but the anchor
    # says "% of total" or similar — show the anchor endpoints as
    # percentages for readability.
    if "%" in unit_rendered:
        return f"{lo * 100:.0f}–{hi * 100:.0f} {unit_rendered}"
    lo_str = _fmt(lo, 0 if lo == int(lo) else 2)
    hi_str = _fmt(hi, 0 if hi == int(hi) else 2)
    return f"{lo_str}–{hi_str} {unit_rendered}"


def _unit_display(unit: str, value_unit: str) -> str:
    """Substitute ``{value_unit}`` into a unit string for display."""
    return unit.replace("{value_unit}", value_unit)


def _total_by_family(
    family_rows: list[dict[str, Any]],
    field: str,
    *,
    canonical_families: tuple[str, ...] = (
        "quick_win",
        "flywheel",
        "enabler",
        "right_tail",
    ),
) -> dict[str, Any]:
    """Return per-family scalar from condition-level family_outcomes rows.

    family_outcomes.parquet holds both seed-run rows and
    aggregation_level="experimental_condition" rows. For a single-run
    report we want the condition-level aggregate for each canonical
    family. Returns a dict keyed by family name; missing families map
    to ``None``.
    """
    result: dict[str, Any] = {family: None for family in canonical_families}
    for row in family_rows:
        if row.get("aggregation_level") != "experimental_condition":
            continue
        key = row.get("grouping_key")
        if key in result:
            result[key] = row.get(field)
    return result


def _pretty_family_name(tag: str) -> str:
    """Plain-English label for a canonical family tag."""
    return {
        "quick_win": "Quick-wins",
        "flywheel": "Flywheels",
        "enabler": "Enablers",
        "right_tail": "Right-tails",
    }.get(tag, tag.replace("_", " ").title())


def _build_single_run_metric_rows(
    condition_row: dict[str, Any],
    family_rows: list[dict[str, Any]],
    baseline_spec_version: str,
    value_unit: str,
) -> list[list[str]]:
    """Build the 16-metric headline table for the single-run report.

    One row per metric, columns:
        # | Metric | Value (mean + range) | Unit | Reasonable range

    The row order and metric set come from METRIC_KEYS in
    report_ranges.py. Values are pulled off the single-row
    experimental_conditions aggregate; per-family metrics (#11, #12,
    #14) are pulled from family_outcomes condition-level rows.

    Args:
        condition_row: The single row from experimental_conditions.parquet.
        family_rows: All rows from family_outcomes.parquet (both seed
            and condition-level; we filter internally).
        baseline_spec_version: Used to key into report_ranges.
        value_unit: Exec-supplied unit label for value dimensions.

    Returns:
        A list of ``[#, metric_name, value, unit, range]`` rows as
        strings, ready for rendering into HTML or markdown.
    """
    anchors = get_ranges(baseline_spec_version)
    rows: list[list[str]] = []

    # Per-family sums for #11 and #12 — reported as totals plus a small
    # per-family breakdown in parentheses (QW/FW/EN/RT).
    stopped_by_family = _total_by_family(family_rows, "stopped_count")
    completed_by_family = _total_by_family(family_rows, "completed_count")
    first_completion_by_family = _total_by_family(family_rows, "first_completion_tick")

    for index, metric_key in enumerate(METRIC_KEYS, start=1):
        anchor = anchors[metric_key]
        label = anchor["label"]
        unit = anchor["unit"]
        source = anchor.get("source", "")
        unit_display = _unit_display(unit, value_unit)

        # Value cell — per-metric formatting. Most metrics come straight
        # off condition_row; a few need derivation or per-family display.
        if metric_key == "total_value":
            value_cell = _fmt_mean_range(
                condition_row.get("total_value_mean"),
                condition_row.get("total_value_min"),
                condition_row.get("total_value_max"),
            )
        elif metric_key in (
            "value_from_completions",
            "value_from_residual",
            "value_from_baseline",
        ):
            value_cell = _fmt_percent(condition_row.get(source), decimals=0)
        elif metric_key == "major_wins_surfaced":
            value_cell = _fmt_mean_range(
                condition_row.get("surfaced_major_wins_mean"),
                condition_row.get("surfaced_major_wins_min"),
                condition_row.get("surfaced_major_wins_max"),
                decimals=1,
            )
        elif metric_key == "productivity_at_end":
            value_cell = _fmt_mean_range(
                condition_row.get("terminal_capability_mean"),
                condition_row.get("terminal_capability_min"),
                condition_row.get("terminal_capability_max"),
                decimals=2,
            )
        elif metric_key == "peak_productivity":
            value_cell = _fmt_mean_range(
                condition_row.get("peak_capacity_mean"),
                condition_row.get("peak_capacity_min"),
                condition_row.get("peak_capacity_max"),
                decimals=2,
            )
        elif metric_key == "free_value_per_week_at_end":
            mean = condition_row.get("terminal_aggregate_residual_rate_mean")
            value_cell = _fmt(mean, decimals=2) if mean is not None else "N/A"
        elif metric_key == "idle_team_weeks_share":
            value_cell = _fmt_percent(condition_row.get("idle_pct_mean"), decimals=0)
        elif metric_key == "pool_exhaustion_week":
            tick = condition_row.get("pool_exhaustion_tick_mean")
            value_cell = f"week {tick:.0f}" if tick is not None else "not reached"
        elif metric_key == "initiatives_stopped":
            total = sum(v for v in stopped_by_family.values() if v is not None)
            parts = [
                f"{_pretty_family_name(fam)[:2]}={count:.0f}"
                for fam, count in stopped_by_family.items()
                if count is not None
            ]
            value_cell = f"{total:.0f} ({', '.join(parts)})" if parts else f"{total:.0f}"
        elif metric_key == "initiatives_completed":
            total = sum(v for v in completed_by_family.values() if v is not None)
            parts = [
                f"{_pretty_family_name(fam)[:2]}={count:.0f}"
                for fam, count in completed_by_family.items()
                if count is not None
            ]
            value_cell = f"{total:.0f} ({', '.join(parts)})" if parts else f"{total:.0f}"
        elif metric_key == "right_tail_false_stop_rate":
            fsr = condition_row.get("right_tail_false_stop_rate_mean")
            value_cell = _fmt_percent(fsr, decimals=1) if fsr is not None else "n/a"
        elif metric_key == "time_to_first_completion":
            # Per-family first-completion ticks. None when a family had
            # no completion at all across the cohort.
            parts = []
            for fam in ("quick_win", "flywheel", "enabler", "right_tail"):
                tick = first_completion_by_family.get(fam)
                short = _pretty_family_name(fam)[:2]
                parts.append(f"{short}={tick:.0f}" if tick is not None else f"{short}=None")
            value_cell = ", ".join(parts)
        elif metric_key == "ramp_overhead":
            value_cell = _fmt_percent(condition_row.get("ramp_labor_fraction_mean"), decimals=1)
        elif metric_key == "quality_estimation_error":
            value_cell = _fmt(condition_row.get("mean_absolute_belief_error_mean"), decimals=3)
        else:
            value_cell = "?"

        # Reasonable-range cell — per-family metrics use a richer form.
        if metric_key == "time_to_first_completion" and isinstance(anchor["range"], dict):
            range_cell = ", ".join(
                f"{_pretty_family_name(fam)[:2]}≈{int(lo)}–{int(hi)}"
                for fam, (lo, hi) in anchor["range"].items()
            )
        elif metric_key == "value_from_baseline":
            range_cell = "0% unless baseline rate set"
        elif metric_key == "pool_exhaustion_week":
            range_cell = "weeks 100–250 (balanced baseline)"
        else:
            range_cell = _fmt_range(anchor["range"], unit, value_unit)

        rows.append([str(index), label, value_cell, unit_display, range_cell])

    return rows


def _build_narrative_paragraphs(
    condition_row: dict[str, Any],
    family_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> list[str]:
    """Render the 4-paragraph narrative template per the spec §Narrative.

    Produces four short paragraphs — Value sources, Governance actions,
    Idle capacity, Capability and discovery. ``None`` / ``n/a`` fields
    drop their sub-clause entirely, so the paragraphs stay readable
    even when a metric is undefined for this run (e.g. pool never
    exhausted, or no right-tails eligible).

    Returns:
        List of four paragraph strings.
    """
    value_unit = manifest.get("value_unit", "units")

    # Horizon in weeks. Per exec_intent_spec.md one tick = one week.
    # run_bundle._build_manifest stamps "tick_horizon" on every manifest
    # (taken from the condition's simulation config); fall back cleanly
    # if the caller passed a stripped-down manifest dict.
    horizon_weeks = manifest.get("tick_horizon")
    horizon_clause = f"Over {horizon_weeks} weeks," if horizon_weeks else "Over the run,"

    # --- Paragraph 1: Value sources ---
    total_value = condition_row.get("total_value_mean")
    share_completions = condition_row.get("value_from_completions_share")
    share_residual = condition_row.get("value_from_residual_share")
    share_baseline = condition_row.get("value_from_baseline_share")
    major_wins = condition_row.get("surfaced_major_wins_mean")

    p1_parts = []
    if total_value is not None:
        p1_parts.append(
            f"{horizon_clause} this run produced " f"{total_value:,.0f} {value_unit} of value."
        )
    if share_completions is not None:
        p1_parts.append(f"{share_completions * 100:.0f}% came from initiative completions")
    if share_residual is not None:
        p1_parts.append(f"{share_residual * 100:.0f}% from ongoing flywheel and quick-win streams")
    if share_baseline is not None and share_baseline > 0:
        p1_parts.append(f"{share_baseline * 100:.0f}% from baseline non-portfolio work")
    # Stitch the share clauses into one sentence.
    if len(p1_parts) > 1:
        parts_tail = ", ".join(p1_parts[1:])
        p1 = p1_parts[0] + " " + parts_tail + "."
    elif p1_parts:
        p1 = p1_parts[0]
    else:
        p1 = "Value accounting was unavailable for this run."
    if major_wins is not None:
        p1 += f" {major_wins:.1f} major wins were surfaced but are not priced into the total."

    # --- Paragraph 2: Governance actions ---
    stopped_by_family = _total_by_family(family_rows, "stopped_count")
    completed_by_family = _total_by_family(family_rows, "completed_count")
    stopped_total = sum(v for v in stopped_by_family.values() if v is not None)
    completed_total = sum(v for v in completed_by_family.values() if v is not None)
    family_clauses = []
    for fam in ("quick_win", "flywheel", "enabler", "right_tail"):
        st = stopped_by_family.get(fam)
        co = completed_by_family.get(fam)
        if st is None and co is None:
            continue
        label = _pretty_family_name(fam)
        family_clauses.append(
            f"{label}: {st:.0f} stopped / {co:.0f} completed"
            if st is not None and co is not None
            else f"{label}: data unavailable"
        )
    fsr = condition_row.get("right_tail_false_stop_rate_mean")
    p2 = (
        f"Governance stopped {stopped_total:.0f} initiatives and completed "
        f"{completed_total:.0f}."
    )
    if family_clauses:
        p2 += " " + "; ".join(family_clauses) + "."
    if fsr is not None:
        p2 += (
            f" Of the right-tails that could have surfaced a major win, "
            f"{fsr * 100:.0f}% were stopped."
        )

    # --- Paragraph 3: Idle capacity ---
    idle = condition_row.get("idle_pct_mean")
    pool_tick = condition_row.get("pool_exhaustion_tick_mean")
    ramp = condition_row.get("ramp_labor_fraction_mean")
    p3_bits = []
    if idle is not None:
        p3_bits.append(f"Teams were without a portfolio assignment {idle * 100:.0f}% of the run.")
    if pool_tick is not None:
        p3_bits.append(f"The initiative pool was exhausted at week {pool_tick:.0f}.")
    else:
        p3_bits.append("The initiative pool was never exhausted.")
    if ramp is not None:
        p3_bits.append(f"{ramp * 100:.1f}% of team-weeks went into ramp-up after reassignments.")
    p3 = " ".join(p3_bits)

    # --- Paragraph 4: Capability and discovery ---
    peak = condition_row.get("peak_capacity_mean")
    peak_week = condition_row.get("peak_capability_tick_mean")
    term_cap = condition_row.get("terminal_capability_mean")
    term_rate = condition_row.get("terminal_aggregate_residual_rate_mean")
    p4_bits = []
    if peak is not None and peak_week is not None:
        p4_bits.append(f"Productivity peaked at {peak:.2f}× at week {peak_week:.0f}")
    elif peak is not None:
        p4_bits.append(f"Productivity peaked at {peak:.2f}×")
    if term_cap is not None:
        if p4_bits:
            p4_bits.append(f"and ended at {term_cap:.2f}×.")
        else:
            p4_bits.append(f"Productivity ended at {term_cap:.2f}×.")
    if term_rate is not None:
        p4_bits.append(
            f"At the final week the portfolio was still generating "
            f"{term_rate:.2f} {value_unit} per week from ongoing streams "
            f"without new labor."
        )
    p4 = " ".join(p4_bits) if p4_bits else "Capability trajectory was unavailable."

    return [p1, p2, p3, p4]


def _build_governance_actions_table(
    family_rows: list[dict[str, Any]],
) -> tuple[list[str], list[list[str]]]:
    """Build the governance-actions-detail table per spec §5.

    One row per initiative family with count / outcome columns, drawn
    from family_outcomes.parquet condition-level rows.
    """
    headers = [
        "Family",
        "Initiatives (mean)",
        "Completed (mean)",
        "Stopped (mean)",
        "Never started (mean)",
        "Time to first completion",
        "Major wins surfaced",
    ]
    canonical_order = ("quick_win", "flywheel", "enabler", "right_tail")
    by_family = {
        row["grouping_key"]: row
        for row in family_rows
        if row.get("aggregation_level") == "experimental_condition"
    }
    rows: list[list[str]] = []
    for fam in canonical_order:
        row = by_family.get(fam)
        if row is None:
            rows.append([_pretty_family_name(fam), "—", "—", "—", "—", "—", "—"])
            continue
        first_tick = row.get("first_completion_tick")
        first_cell = f"week {first_tick:.0f}" if first_tick is not None else "None"
        rows.append(
            [
                _pretty_family_name(fam),
                _fmt(row.get("initiative_count"), 1),
                _fmt(row.get("completed_count"), 1),
                _fmt(row.get("stopped_count"), 1),
                _fmt(row.get("never_started_count"), 1),
                first_cell,
                _fmt(row.get("surfaced_major_wins"), 1),
            ]
        )
    return headers, rows


# ---------------------------------------------------------------------------
# Single-run shape — HTML and markdown renderers
# ---------------------------------------------------------------------------


def _build_identity_block(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    """Build the (label, value) pair list for the Run Identity section.

    Per single_run_report_spec.md §1: design name, title, description,
    resolved business-unit inputs, run-bundle id, git commit.

    The report has no direct access to the source RunDesignSpec; we
    reconstruct as much of the exec surface as the manifest dict carries.
    """
    return [
        ("Design", manifest.get("experiment_name", "")),
        ("Title", manifest.get("title", "")),
        ("Description", manifest.get("description", "")),
        ("Value unit", manifest.get("value_unit", "units")),
        ("Seeds", ", ".join(str(s) for s in manifest.get("world_seeds", []))),
        ("Seed count", str(manifest.get("seed_count", ""))),
        ("Run bundle id", manifest.get("run_bundle_id", "")),
        ("Git commit", manifest.get("git_commit", "")),
        ("Baseline spec version", manifest.get("baseline_spec_version", "")),
    ]


def _generate_html_single_run(
    manifest: dict[str, Any],
    table_data: dict[str, list[dict[str, Any]]],
    figures_dir: Path,
    report_dir: Path,
) -> None:
    """Render report/index.html in the single-run 6-section shape.

    Per single_run_report_spec.md §Report structure.
    """
    conditions = table_data.get("experimental_conditions", [])
    family_rows = table_data.get("family_outcomes", [])
    condition_row = conditions[0]
    value_unit = manifest.get("value_unit", "units")
    baseline_spec_version = manifest.get("baseline_spec_version", "")

    # --- Section 1: Run identity ---
    identity_pairs = _build_identity_block(manifest)
    identity_html = (
        "<dl>\n"
        + "\n".join(
            f"<dt><strong>{label}</strong></dt><dd>{value}</dd>"
            for label, value in identity_pairs
            if value != ""
        )
        + "\n</dl>"
    )

    # --- Section 2: Headline metrics ---
    metric_headers = ["#", "Metric", "Value (mean + range)", "Unit", "Reasonable range"]
    metric_rows = _build_single_run_metric_rows(
        condition_row, family_rows, baseline_spec_version, value_unit
    )
    headline_html = _html_table(metric_headers, metric_rows)

    # --- Section 3: Narrative ---
    paragraphs = _build_narrative_paragraphs(condition_row, family_rows, manifest)
    narrative_html = "\n".join(
        f"<p><strong>{title}.</strong> {body}</p>"
        for title, body in zip(
            ("Value sources", "Governance actions", "Idle capacity", "Capability and discovery"),
            paragraphs,
            strict=False,
        )
    )

    # --- Section 4: Figures with captions ---
    figure_filenames = [
        "value_by_year_stacked.png",
        "cumulative_value_by_year.png",
        "surfaced_major_wins_by_year.png",
        "tradeoff_frontier.png",
        "terminal_capability.png",
        "rt_survival_curves.png",
        "enabler_dashboard.png",
        "representative_timelines.png",
    ]
    figures_html = ""
    for fname in figure_filenames:
        fpath = figures_dir / fname
        if not fpath.exists():
            continue
        title, caption = _caption_for(fname)
        figures_html += '<figure style="margin:1.5em 0;">\n'
        figures_html += f'<img src="../figures/{fname}" style="max-width:100%;" alt="{title}">\n'
        figures_html += f"<figcaption><strong>{title}.</strong> {caption}</figcaption>\n"
        figures_html += "</figure>\n"

    # Trajectory figures come out of per-tick logging; include them if
    # present using the helper that scans the dir.
    figures_html += _build_trajectory_figures_html(figures_dir)

    # --- Section 5: Governance actions detail ---
    gov_headers, gov_rows = _build_governance_actions_table(family_rows)
    gov_html = _html_table(gov_headers, gov_rows)

    # --- Section 6: Appendix ---
    telemetry = manifest.get("telemetry", {})
    seed_runs_completed = telemetry.get("seed_runs_completed", "")
    appendix_html = f"""
<ul>
<li><strong>Completed seed runs:</strong> {seed_runs_completed}</li>
<li><strong>Command:</strong> <code>{manifest.get("command", "")}</code></li>
<li><strong>Python:</strong> {manifest.get("python_version", "")}
    on {manifest.get("platform", "")}</li>
<li><strong>Schema version:</strong> {manifest.get("schema_version", "")}</li>
<li><strong>Baseline spec version:</strong>
    {manifest.get("baseline_spec_version", "")}</li>
</ul>
<p>Full resolved configuration is in
<code>config/simulation_config.json</code> inside the run bundle.
To rerun with the same inputs, re-execute the command above
against the same bundle root.</p>
"""

    if (figures_dir / "seed_distributions.png").exists():
        title, caption = _caption_for("seed_distributions.png")
        appendix_html += f"""
<figure style="margin:1em 0;">
<img src="../figures/seed_distributions.png" style="max-width:100%;" alt="{title}">
<figcaption><strong>{title}.</strong> {caption}</figcaption>
</figure>
"""

    # --- Assemble ---
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{manifest.get("title", "Run Report")}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 1100px; margin: 0 auto; padding: 2em; line-height: 1.6; color: #333; }}
h1 {{ border-bottom: 2px solid #2196F3; padding-bottom: 0.3em; }}
h2 {{ border-bottom: 1px solid #ccc; padding-bottom: 0.2em; margin-top: 2.5em; }}
dl {{ background: #f8f8f8; padding: 1em; border-radius: 4px; }}
dt {{ float: left; clear: left; width: 12em; }}
dd {{ margin-left: 12em; }}
figure {{ text-align: center; }}
figcaption {{ font-style: italic; font-size: 0.9em; color: #555;
              max-width: 44em; margin: 0.5em auto 0; text-align: left; }}
table {{ border-collapse: collapse; margin: 1em 0; }}
</style>
</head>
<body>

<h1>{manifest.get("title", "Run Report")}</h1>

<h2>1. Run identity</h2>
{identity_html}

<h2>2. Headline outcomes</h2>
{headline_html}
<p style="font-size: 0.9em; color: #666;">
Mean across the seed cohort, with per-seed min–max range in parentheses
when applicable. Reasonable-range anchors are author-curated, keyed to
baseline spec version <code>{baseline_spec_version}</code>; a value
outside the range is a reason to look closer, not an error.
</p>

<h2>3. Narrative</h2>
{narrative_html}

<h2>4. Figures</h2>
{figures_html}

<h2>5. Governance actions detail</h2>
{gov_html}

<h2>6. Appendix — methods and provenance</h2>
{appendix_html}

</body>
</html>
"""
    (report_dir / "index.html").write_text(html, encoding="utf-8")
    logger.info("Generated report/index.html (single-run shape)")


def _generate_markdown_single_run(
    manifest: dict[str, Any],
    table_data: dict[str, list[dict[str, Any]]],
    figures_dir: Path,
    report_dir: Path,
) -> None:
    """Render report/report.md in the single-run 6-section shape.

    Companion markdown parallel to _generate_html_single_run.
    """
    conditions = table_data.get("experimental_conditions", [])
    family_rows = table_data.get("family_outcomes", [])
    condition_row = conditions[0]
    value_unit = manifest.get("value_unit", "units")
    baseline_spec_version = manifest.get("baseline_spec_version", "")

    identity_pairs = _build_identity_block(manifest)
    identity_md = "\n".join(
        f"- **{label}:** {value}" for label, value in identity_pairs if value != ""
    )

    metric_headers = ["#", "Metric", "Value (mean + range)", "Unit", "Reasonable range"]
    metric_rows = _build_single_run_metric_rows(
        condition_row, family_rows, baseline_spec_version, value_unit
    )
    headline_md = _md_table(metric_headers, metric_rows)

    paragraphs = _build_narrative_paragraphs(condition_row, family_rows, manifest)
    narrative_md = "\n\n".join(
        f"**{title}.** {body}"
        for title, body in zip(
            ("Value sources", "Governance actions", "Idle capacity", "Capability and discovery"),
            paragraphs,
            strict=False,
        )
    )

    figure_filenames = [
        "value_by_year_stacked.png",
        "cumulative_value_by_year.png",
        "surfaced_major_wins_by_year.png",
        "tradeoff_frontier.png",
        "terminal_capability.png",
        "rt_survival_curves.png",
        "enabler_dashboard.png",
        "representative_timelines.png",
    ]
    figures_md_parts: list[str] = []
    for fname in figure_filenames:
        if not (figures_dir / fname).exists():
            continue
        title, caption = _caption_for(fname)
        figures_md_parts.append(
            f"### {title}\n\n" f"![{title}](../figures/{fname})\n\n" f"*{caption}*"
        )
    figures_md = "\n\n".join(figures_md_parts)
    traj_md = _build_trajectory_figures_markdown(figures_dir)
    if traj_md:
        figures_md += "\n\n" + traj_md

    gov_headers, gov_rows = _build_governance_actions_table(family_rows)
    gov_md = _md_table(gov_headers, gov_rows)

    telemetry = manifest.get("telemetry", {})
    seed_runs_completed = telemetry.get("seed_runs_completed", "")

    md = f"""# {manifest.get("title", "Run Report")}

## 1. Run identity

{identity_md}

## 2. Headline outcomes

{headline_md}

*Mean across the seed cohort, with per-seed min–max range in
parentheses when applicable. Reasonable-range anchors are
author-curated, keyed to baseline spec version
`{baseline_spec_version}`; a value outside the range is a reason to
look closer, not an error.*

## 3. Narrative

{narrative_md}

## 4. Figures

{figures_md}

## 5. Governance actions detail

{gov_md}

## 6. Appendix — methods and provenance

- **Completed seed runs:** {seed_runs_completed}
- **Command:** `{manifest.get("command", "")}`
- **Python:** {manifest.get("python_version", "")} on {manifest.get("platform", "")}
- **Schema version:** {manifest.get("schema_version", "")}
- **Baseline spec version:** {manifest.get("baseline_spec_version", "")}

Full resolved configuration is in `config/simulation_config.json`
inside the run bundle. To rerun with the same inputs, re-execute the
command above against the same bundle root.
"""
    if (figures_dir / "seed_distributions.png").exists():
        title, caption = _caption_for("seed_distributions.png")
        md += (
            f"\n### {title}\n\n"
            f"![{title}](../figures/seed_distributions.png)\n\n"
            f"*{caption}*\n"
        )

    (report_dir / "report.md").write_text(md, encoding="utf-8")
    logger.info("Generated report/report.md (single-run shape)")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def generate_report(
    manifest: dict[str, Any],
    table_data: dict[str, list[dict[str, Any]]],
    figures_dir: Path,
    report_dir: Path,
) -> None:
    """Generate both HTML and markdown reports.

    Branches on the number of experimental conditions in the bundle:

    - **Single condition** — render the 6-section single-run shape
      defined by single_run_report_spec.md (Identity, Headline Metrics,
      Narrative, Figures-with-captions, Governance Actions detail,
      Appendix). Optimized for an exec or researcher reading one run
      on its own.
    - **Multiple conditions** — render the existing comparison-shaped
      report (headline comparison table + per-figure sections).

    Args:
        manifest: Manifest dictionary (as built by run_bundle.py).
        table_data: Dict mapping table name to rows.
        figures_dir: Path to the figures/ directory.
        report_dir: Path to the report/ directory.
    """
    report_dir.mkdir(parents=True, exist_ok=True)

    # Detect single-run vs multi-condition by condition count. Zero
    # conditions (empty run) falls through to the multi-condition
    # renderer, which already handles empty headline tables gracefully.
    conditions = table_data.get("experimental_conditions", [])
    is_single_run = len(conditions) == 1

    if is_single_run:
        _generate_html_single_run(manifest, table_data, figures_dir, report_dir)
        _generate_markdown_single_run(manifest, table_data, figures_dir, report_dir)
    else:
        _generate_html_report(manifest, table_data, figures_dir, report_dir)
        _generate_markdown_report(manifest, table_data, figures_dir, report_dir)

    logger.info("Report package generated in %s", report_dir)
