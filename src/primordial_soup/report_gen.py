"""HTML and markdown report generation for run bundles.

Generates the human-facing report package: a static HTML report
(report/index.html) and a companion markdown report (report/report.md).

Both are derived from canonical table data and figures in the run
bundle. No jinja2 dependency — reports are generated with Python
f-strings and helper functions.

Design reference:
    docs/implementation/reporting_package_specification.md
    §HTML report-package structure
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


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
            f'<img src="../figures/{fpath.name}" ' f'style="max-width:100%;" alt="{caption}">'
        )
        html_parts.append(f"<figcaption>{caption}</figcaption>")
        html_parts.append("</figure>")

    for fpath in overlay_files:
        condition_id = fpath.stem.removeprefix("trajectory_overlay_")
        caption = f"Trajectory Overlay — {condition_id}"
        html_parts.append('<figure style="margin:1em 0;">')
        html_parts.append(
            f'<img src="../figures/{fpath.name}" ' f'style="max-width:100%;" alt="{caption}">'
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
            "*No trajectory figures available " "(per-tick logging may not have been enabled).*"
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
            figure_html += f'<img src="{img_src}" style="max-width:100%;"' f' alt="{caption}">\n'
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
            appendix_html += f'<img src="{img_src}" style="max-width:100%;"' f' alt="{caption}">\n'
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
<title>{manifest.get('title', 'Experiment Report')}</title>
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

<h1>{manifest.get('title', 'Experiment Report')}</h1>

<div class="meta">
<strong>Run Bundle:</strong> {manifest.get('run_bundle_id', '')}<br>
<strong>Script:</strong> {manifest.get('script', '')}<br>
<strong>Created:</strong> {manifest.get('created_at', '')}<br>
<strong>Git Commit:</strong> {manifest.get('git_commit', '')}<br>
<strong>Schema Version:</strong> {manifest.get('schema_version', '')}<br>
<strong>Conditions:</strong> {manifest.get('experimental_condition_count', '')},
<strong>Seeds:</strong> {manifest.get('seed_count', '')}
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
<li><strong>Seeds:</strong> {manifest.get('world_seeds', [])}</li>
<li><strong>Conditions:</strong> {manifest.get('experimental_condition_count', '')}</li>
<li><strong>Completed seed runs:</strong> {seed_runs_completed}</li>
<li><strong>Horizon:</strong> per run configuration</li>
<li><strong>Command:</strong> <code>{manifest.get('command', '')}</code></li>
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

    md = f"""# {manifest.get('title', 'Experiment Report')}

**Run Bundle:** {manifest.get('run_bundle_id', '')}
**Script:** {manifest.get('script', '')}
**Created:** {manifest.get('created_at', '')}
**Git Commit:** {manifest.get('git_commit', '')}
**Schema Version:** {manifest.get('schema_version', '')}

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

- **Seeds:** {manifest.get('world_seeds', [])}
- **Conditions:** {manifest.get('experimental_condition_count', '')}
- **Completed seed runs:** {seed_runs_completed}
- **Command:** `{manifest.get('command', '')}`

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
# Orchestrator
# ---------------------------------------------------------------------------


def generate_report(
    manifest: dict[str, Any],
    table_data: dict[str, list[dict[str, Any]]],
    figures_dir: Path,
    report_dir: Path,
) -> None:
    """Generate both HTML and markdown reports.

    Args:
        manifest: Manifest dictionary (as built by run_bundle.py).
        table_data: Dict mapping table name to rows.
        figures_dir: Path to the figures/ directory.
        report_dir: Path to the report/ directory.
    """
    report_dir.mkdir(parents=True, exist_ok=True)

    _generate_html_report(manifest, table_data, figures_dir, report_dir)
    _generate_markdown_report(manifest, table_data, figures_dir, report_dir)

    logger.info("Report package generated in %s", report_dir)
