"""Tests for report_gen.py — HTML and markdown report generation.

The report generator branches on the number of experimental conditions
in the bundle:
    - exactly 1 condition → single-run shape
      (single_run_report_spec.md, 2026-04-18)
    - >1 conditions → multi-condition shape
      (reporting_package_specification.md)

Tests below cover both shapes plus the formatting helpers.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 — pytest fixtures need Path at runtime
from typing import Any

from primordial_soup.report_gen import (
    SINGLE_RUN_FIGURE_CAPTIONS,
    _build_headline_table,
    _build_narrative_paragraphs,
    _build_single_run_metric_rows,
    _caption_for,
    _fmt,
    _fmt_mean_range,
    _fmt_percent,
    _fmt_range,
    _html_table,
    _md_table,
    generate_report,
)
from primordial_soup.report_ranges import METRIC_KEYS, get_ranges

# ============================================================================
# Helper function tests
# ============================================================================


class TestFmt:
    """Tests for _fmt() display formatting."""

    def test_none_returns_na(self) -> None:
        assert _fmt(None) == "N/A"

    def test_float_formatting(self) -> None:
        assert _fmt(3.14159, 2) == "3.14"
        assert _fmt(3.14159, 4) == "3.1416"

    def test_int_passthrough(self) -> None:
        assert _fmt(42) == "42"

    def test_zero(self) -> None:
        assert _fmt(0.0) == "0.00"


class TestFmtMeanRange:
    """Tests for the single-run mean-with-range formatter."""

    def test_none_mean(self) -> None:
        assert _fmt_mean_range(None, None, None) == "N/A"

    def test_point_when_bounds_missing(self) -> None:
        # Missing bound → no parentheses, just the point value.
        assert _fmt_mean_range(5.0, None, None) == "5.00"

    def test_point_when_bounds_equal(self) -> None:
        # Single-seed cohort → min == max → render as a point.
        assert _fmt_mean_range(5.0, 5.0, 5.0) == "5.00"

    def test_full_range(self) -> None:
        assert _fmt_mean_range(5.0, 4.0, 6.0) == "5.00 (4.00–6.00)"


class TestFmtPercent:
    def test_none_is_na(self) -> None:
        assert _fmt_percent(None) == "n/a"

    def test_fraction_renders_percent(self) -> None:
        assert _fmt_percent(0.45) == "45%"
        assert _fmt_percent(0.45, decimals=1) == "45.0%"


class TestFmtRange:
    def test_value_unit_substituted(self) -> None:
        # Unit with {value_unit} placeholder gets exec-supplied label.
        out = _fmt_range((3000.0, 7000.0), "{value_unit}", "$M")
        assert "$M" in out
        assert "3000" in out
        assert "7000" in out

    def test_percent_range_rendered_as_percentages(self) -> None:
        out = _fmt_range((0.4, 0.7), "% of total", "units")
        assert "40" in out
        assert "70" in out
        assert "%" in out

    def test_unknown_shape_returns_placeholder(self) -> None:
        assert "unavailable" in _fmt_range(None, "x", "units")


class TestHtmlTable:
    """Tests for _html_table()."""

    def test_basic_table(self) -> None:
        html = _html_table(["A", "B"], [["1", "2"], ["3", "4"]])
        assert "<table" in html
        assert "<th" in html
        assert "<td" in html
        assert "1" in html
        assert "4" in html

    def test_with_caption(self) -> None:
        html = _html_table(["X"], [["Y"]], caption="Test Caption")
        assert "Test Caption" in html

    def test_empty_rows(self) -> None:
        html = _html_table(["A"], [])
        assert "<table" in html
        assert "<th" in html


class TestMdTable:
    """Tests for _md_table()."""

    def test_basic_table(self) -> None:
        md = _md_table(["Col1", "Col2"], [["a", "b"]])
        assert "| Col1 | Col2 |" in md
        assert "| --- | --- |" in md
        assert "| a | b |" in md


class TestBuildHeadlineTable:
    """Tests for the multi-condition _build_headline_table()."""

    def test_with_conditions(self) -> None:
        conditions = [
            {
                "governance_regime_label": "Balanced",
                "total_value_mean": 100.5,
                "surfaced_major_wins_mean": 3.2,
                "terminal_capability_mean": 1.45,
                "right_tail_false_stop_rate_mean": 0.25,
                "idle_pct_mean": 0.08,
            },
        ]
        headers, rows = _build_headline_table(conditions)
        assert len(headers) == 6
        assert len(rows) == 1
        assert rows[0][0] == "Balanced"
        assert rows[0][1] == "100.50"

    def test_empty_conditions(self) -> None:
        headers, rows = _build_headline_table([])
        assert len(headers) == 6
        assert len(rows) == 0


# ============================================================================
# Shared fixtures
# ============================================================================


def _base_manifest() -> dict[str, Any]:
    """Build a minimal manifest for report testing, multi-condition shape."""
    return {
        "run_bundle_id": "test-bundle",
        "title": "Test Experiment Report",
        "description": "Smoke-test fixture",
        "script": "test.py",
        "created_at": "2026-03-17T12:00:00",
        "git_commit": "abc1234",
        "schema_version": "1.0.0",
        "python_version": "3.12.3",
        "platform": "test-platform",
        "experiment_name": "test",
        "experimental_condition_count": 1,
        "seed_count": 2,
        "world_seeds": [42, 43],
        "command": "python test.py",
        "telemetry": {
            "status": "completed",
            "seed_runs_completed": 2,
        },
        "value_unit": "units",
        "baseline_spec_version": "v2-intake-baseline-thinning",
    }


def _single_run_condition_row() -> dict[str, Any]:
    """Build one condition row with all fields the single-run report reads."""
    return {
        "experimental_condition_id": "cond-1",
        "governance_regime_label": "Balanced",
        "seed_count": 2,
        "seed_runs_completed": 2,
        # Total value, major wins, terminal capability — with min/max range.
        "total_value_mean": 5000.0,
        "total_value_min": 4800.0,
        "total_value_max": 5200.0,
        "surfaced_major_wins_mean": 2.0,
        "surfaced_major_wins_min": 1.0,
        "surfaced_major_wins_max": 3.0,
        "terminal_capability_mean": 2.0,
        "terminal_capability_min": 1.9,
        "terminal_capability_max": 2.1,
        "peak_capacity_mean": 2.4,
        "peak_capacity_min": 2.2,
        "peak_capacity_max": 2.6,
        # Derived value-channel share ratios.
        "value_from_completions_share": 0.55,
        "value_from_residual_share": 0.42,
        "value_from_baseline_share": 0.03,
        # Lump / residual / baseline means.
        "cumulative_lump_value_mean": 2750.0,
        "cumulative_residual_value_mean": 2100.0,
        "cumulative_baseline_value_mean": 150.0,
        # Organizational momentum.
        "terminal_aggregate_residual_rate_mean": 8.0,
        "peak_capability_tick_mean": 210.0,
        "pool_exhaustion_tick_mean": 180.0,
        # Idle / ramp.
        "idle_pct_mean": 0.55,
        "idle_pct_min": 0.50,
        "idle_pct_max": 0.60,
        # Right-tail false-stop.
        "right_tail_false_stop_rate_mean": 0.15,
        # Labor overhead, governance quality.
        "ramp_labor_fraction_mean": 0.05,
        "mean_absolute_belief_error_mean": 0.10,
    }


def _single_run_family_rows() -> list[dict[str, Any]]:
    """Family-outcomes rows (condition-level) for the single-run fixture.

    Includes all four canonical families plus per-family first-completion
    ticks that map cleanly to the 4-paragraph narrative.
    """
    base: dict[str, Any] = {
        "aggregation_level": "experimental_condition",
        "experimental_condition_id": "cond-1",
        "grouping_namespace": "initiative_family",
    }
    return [
        {
            **base,
            "grouping_key": "quick_win",
            "grouping_label": "Quick Win",
            "initiative_count": 80.0,
            "completed_count": 50.0,
            "stopped_count": 25.0,
            "active_at_horizon_count": 3.0,
            "never_started_count": 2.0,
            "realized_value_lump": 1000.0,
            "realized_value_residual": 500.0,
            "realized_value_total": 1500.0,
            "surfaced_major_wins": 0.0,
            "eligible_count": 0.0,
            "stopped_eligible_count": 0.0,
            "first_completion_tick": 10.0,
        },
        {
            **base,
            "grouping_key": "flywheel",
            "grouping_label": "Flywheel",
            "initiative_count": 70.0,
            "completed_count": 35.0,
            "stopped_count": 28.0,
            "active_at_horizon_count": 4.0,
            "never_started_count": 3.0,
            "realized_value_lump": 900.0,
            "realized_value_residual": 1500.0,
            "realized_value_total": 2400.0,
            "surfaced_major_wins": 0.0,
            "eligible_count": 0.0,
            "stopped_eligible_count": 0.0,
            "first_completion_tick": 40.0,
        },
        {
            **base,
            "grouping_key": "enabler",
            "grouping_label": "Enabler",
            "initiative_count": 30.0,
            "completed_count": 20.0,
            "stopped_count": 7.0,
            "active_at_horizon_count": 2.0,
            "never_started_count": 1.0,
            "realized_value_lump": 400.0,
            "realized_value_residual": 50.0,
            "realized_value_total": 450.0,
            "surfaced_major_wins": 0.0,
            "eligible_count": 0.0,
            "stopped_eligible_count": 0.0,
            "first_completion_tick": 20.0,
        },
        {
            **base,
            "grouping_key": "right_tail",
            "grouping_label": "Right Tail",
            "initiative_count": 20.0,
            "completed_count": 3.0,
            "stopped_count": 15.0,
            "active_at_horizon_count": 1.0,
            "never_started_count": 1.0,
            "realized_value_lump": 450.0,
            "realized_value_residual": 200.0,
            "realized_value_total": 650.0,
            "surfaced_major_wins": 2.0,
            "eligible_count": 3.0,
            "stopped_eligible_count": 0.0,
            "first_completion_tick": 155.0,
        },
    ]


def _single_run_table_data() -> dict[str, list[dict[str, Any]]]:
    return {
        "experimental_conditions": [_single_run_condition_row()],
        "family_outcomes": _single_run_family_rows(),
    }


def _multi_condition_table_data() -> dict[str, list[dict[str, Any]]]:
    """Two conditions so the multi-condition branch runs."""
    return {
        "experimental_conditions": [
            {
                "experimental_condition_id": "cond-1",
                "governance_regime_label": "Balanced",
                "total_value_mean": 50.0,
                "surfaced_major_wins_mean": 1.5,
                "terminal_capability_mean": 1.2,
                "right_tail_false_stop_rate_mean": 0.3,
                "idle_pct_mean": 0.05,
            },
            {
                "experimental_condition_id": "cond-2",
                "governance_regime_label": "Aggressive",
                "total_value_mean": 42.0,
                "surfaced_major_wins_mean": 0.5,
                "terminal_capability_mean": 1.1,
                "right_tail_false_stop_rate_mean": 0.5,
                "idle_pct_mean": 0.12,
            },
        ],
    }


# ============================================================================
# Multi-condition shape (unchanged — used for > 1 conditions)
# ============================================================================


class TestMultiConditionReport:
    """Smoke tests for the pre-existing multi-condition shape."""

    def test_html_report_created(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()

        manifest = _base_manifest()
        manifest["experimental_condition_count"] = 2

        generate_report(manifest, _multi_condition_table_data(), figures_dir, report_dir)

        assert (report_dir / "index.html").exists()
        html = (report_dir / "index.html").read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html

    def test_markdown_report_created(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()

        manifest = _base_manifest()
        manifest["experimental_condition_count"] = 2

        generate_report(manifest, _multi_condition_table_data(), figures_dir, report_dir)

        assert (report_dir / "report.md").exists()
        md = (report_dir / "report.md").read_text(encoding="utf-8")
        assert "# Test Experiment Report" in md

    def test_html_contains_required_sections(self, tmp_path: Path) -> None:
        """Multi-condition HTML carries the comparison-shaped sections."""
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()

        manifest = _base_manifest()
        manifest["experimental_condition_count"] = 2

        generate_report(manifest, _multi_condition_table_data(), figures_dir, report_dir)

        html = (report_dir / "index.html").read_text(encoding="utf-8")
        assert "Test Experiment Report" in html
        assert "test-bundle" in html
        assert "surfaced-not-priced" in html
        assert "Executive Summary" in html
        assert "Balanced" in html
        assert "Core Figures" in html
        assert "Diagnostic Interpretation" in html
        assert "Representative Runs" in html
        assert "Methods and Reproducibility" in html
        assert "Appendix" in html

    def test_md_contains_required_sections(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()

        manifest = _base_manifest()
        manifest["experimental_condition_count"] = 2

        generate_report(manifest, _multi_condition_table_data(), figures_dir, report_dir)

        md = (report_dir / "report.md").read_text(encoding="utf-8")
        assert "Study Interpretation Notes" in md
        assert "Executive Summary" in md
        assert "Representative Runs" in md
        assert "Methods and Reproducibility" in md
        assert "Appendix" in md


# ============================================================================
# Single-run shape (single_run_report_spec.md, 2026-04-18)
# ============================================================================


class TestSingleRunHeadlineMetrics:
    """Tests for the 16-row headline-metric table."""

    def test_row_count_matches_spec(self) -> None:
        rows = _build_single_run_metric_rows(
            _single_run_condition_row(),
            _single_run_family_rows(),
            "v2-intake-baseline-thinning",
            "$M",
        )
        assert len(rows) == len(METRIC_KEYS) == 16

    def test_value_unit_substituted_in_total_value_row(self) -> None:
        # The total-value unit column should carry the exec's unit label.
        rows = _build_single_run_metric_rows(
            _single_run_condition_row(),
            _single_run_family_rows(),
            "v2-intake-baseline-thinning",
            "$M",
        )
        total_value_row = rows[0]
        # Column 4 is Unit; column 5 is the reasonable-range band.
        assert "$M" in total_value_row[3]
        assert "$M" in total_value_row[4]

    def test_share_ratios_render_as_percentages(self) -> None:
        rows = _build_single_run_metric_rows(
            _single_run_condition_row(),
            _single_run_family_rows(),
            "v2-intake-baseline-thinning",
            "units",
        )
        # METRIC_KEYS order: total_value=0, value_from_completions=1, ...
        assert rows[1][2].endswith("%")
        assert rows[2][2].endswith("%")

    def test_pool_not_reached_renders_cleanly(self) -> None:
        cond = _single_run_condition_row()
        cond["pool_exhaustion_tick_mean"] = None
        rows = _build_single_run_metric_rows(
            cond,
            _single_run_family_rows(),
            "v2-intake-baseline-thinning",
            "units",
        )
        # Metric key "pool_exhaustion_week" is index 9 in METRIC_KEYS.
        pool_row = rows[9]
        assert "not reached" in pool_row[2].lower()

    def test_per_family_first_completion_includes_all_families(self) -> None:
        rows = _build_single_run_metric_rows(
            _single_run_condition_row(),
            _single_run_family_rows(),
            "v2-intake-baseline-thinning",
            "units",
        )
        # "time_to_first_completion" is index 13 in METRIC_KEYS.
        ttf_row = rows[13]
        # Short per-family labels are the two-letter prefix of the
        # pretty name; check that all four families show up.
        for short in ("Qu", "Fl", "En", "Ri"):
            assert short in ttf_row[2]


class TestSingleRunNarrative:
    """Tests for the 4-paragraph narrative template."""

    def test_produces_four_paragraphs(self) -> None:
        paragraphs = _build_narrative_paragraphs(
            _single_run_condition_row(),
            _single_run_family_rows(),
            _base_manifest(),
        )
        assert len(paragraphs) == 4

    def test_value_unit_flows_into_p1(self) -> None:
        manifest = _base_manifest()
        manifest["value_unit"] = "EUR_M"
        paragraphs = _build_narrative_paragraphs(
            _single_run_condition_row(), _single_run_family_rows(), manifest
        )
        # Paragraph 1 describes total value in the exec's unit.
        assert "EUR_M" in paragraphs[0]

    def test_pool_never_exhausted_sub_clause(self) -> None:
        cond = _single_run_condition_row()
        cond["pool_exhaustion_tick_mean"] = None
        paragraphs = _build_narrative_paragraphs(cond, _single_run_family_rows(), _base_manifest())
        # Paragraph 3 is the idle-capacity paragraph.
        assert "never exhausted" in paragraphs[2]

    def test_baseline_share_clause_suppressed_when_zero(self) -> None:
        """value_from_baseline_share == 0 should be omitted from P1."""
        cond = _single_run_condition_row()
        cond["value_from_baseline_share"] = 0.0
        paragraphs = _build_narrative_paragraphs(cond, _single_run_family_rows(), _base_manifest())
        # When baseline share is zero, the "from baseline" clause should
        # not appear in the value-sources paragraph.
        assert "baseline non-portfolio" not in paragraphs[0]

    def test_governance_paragraph_includes_family_detail(self) -> None:
        paragraphs = _build_narrative_paragraphs(
            _single_run_condition_row(),
            _single_run_family_rows(),
            _base_manifest(),
        )
        p2 = paragraphs[1]
        for family in ("Quick-wins", "Flywheels", "Enablers", "Right-tails"):
            assert family in p2


class TestSingleRunReport:
    """End-to-end smoke tests for the single-run HTML / markdown output."""

    def test_html_and_md_produced(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()
        generate_report(_base_manifest(), _single_run_table_data(), figures_dir, report_dir)
        assert (report_dir / "index.html").exists()
        assert (report_dir / "report.md").exists()

    def test_single_run_sections_present(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()
        generate_report(_base_manifest(), _single_run_table_data(), figures_dir, report_dir)

        html = (report_dir / "index.html").read_text(encoding="utf-8")
        md = (report_dir / "report.md").read_text(encoding="utf-8")

        # The six sections in both outputs.
        for heading in (
            "Run identity",
            "Headline outcomes",
            "Narrative",
            "Figures",
            "Governance actions detail",
            "Appendix",
        ):
            assert heading in html
            assert heading in md

    def test_single_run_does_not_render_multi_condition_sections(self, tmp_path: Path) -> None:
        """Ensure the single-run path doesn't leak multi-condition shells."""
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()
        generate_report(_base_manifest(), _single_run_table_data(), figures_dir, report_dir)

        html = (report_dir / "index.html").read_text(encoding="utf-8")
        # These are multi-condition-shape-only phrases.
        assert "Executive Summary" not in html
        assert "Diagnostic Interpretation" not in html

    def test_value_unit_appears_in_identity_block(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()
        manifest = _base_manifest()
        manifest["value_unit"] = "USD_M"
        generate_report(manifest, _single_run_table_data(), figures_dir, report_dir)
        html = (report_dir / "index.html").read_text(encoding="utf-8")
        assert "USD_M" in html


class TestFigureCaptions:
    """Captions live next to the filename per single_run_report_spec §Figures."""

    def test_every_canonical_figure_has_caption(self) -> None:
        canonical = {
            "value_by_year_stacked.png",
            "cumulative_value_by_year.png",
            "surfaced_major_wins_by_year.png",
            "tradeoff_frontier.png",
            "terminal_capability.png",
            "rt_survival_curves.png",
            "enabler_dashboard.png",
            "representative_timelines.png",
            "seed_distributions.png",
        }
        missing = canonical - set(SINGLE_RUN_FIGURE_CAPTIONS.keys())
        assert not missing, f"Missing captions for: {missing}"

    def test_caption_fallback_for_unknown_filename(self) -> None:
        title, caption = _caption_for("new_figure.png")
        assert title == "New Figure"
        assert caption == ""


class TestReportRangesLookup:
    """Thin tests against the report_ranges.py lookup surface."""

    def test_known_version_returns_sixteen_metrics(self) -> None:
        anchors = get_ranges("v2-intake-baseline-thinning")
        assert set(anchors.keys()) == set(METRIC_KEYS)

    def test_unknown_version_falls_back(self) -> None:
        """An unknown baseline_spec_version should fall back, not raise."""
        anchors = get_ranges("v999-not-registered")
        assert set(anchors.keys()) == set(METRIC_KEYS)
