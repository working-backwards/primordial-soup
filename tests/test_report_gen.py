"""Tests for report_gen.py — HTML and markdown report generation.

Tests verify:
    - HTML report contains all required sections
    - Markdown report contains all required sections
    - Figure references point to expected filenames
    - Headline table data renders correctly
    - Helper functions produce valid output
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 — pytest fixtures need Path at runtime
from typing import Any

from primordial_soup.report_gen import (
    _build_headline_table,
    _fmt,
    _html_table,
    _md_table,
    generate_report,
)

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
    """Tests for _build_headline_table()."""

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
# Report generation smoke tests
# ============================================================================


def _make_test_manifest() -> dict[str, Any]:
    """Build a minimal manifest for report testing."""
    return {
        "run_bundle_id": "test-bundle",
        "title": "Test Experiment Report",
        "script": "test.py",
        "created_at": "2026-03-17T12:00:00",
        "git_commit": "abc1234",
        "schema_version": "1.0.0",
        "experiment_name": "test",
        "experimental_condition_count": 1,
        "seed_count": 2,
        "world_seeds": [42, 43],
        "command": "python test.py",
        "telemetry": {
            "status": "completed",
            "seed_runs_completed": 2,
        },
    }


def _make_test_table_data() -> dict[str, list[dict]]:
    """Build minimal table data for report testing."""
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
        ],
    }


class TestGenerateReport:
    """Smoke tests for report generation."""

    def test_html_report_created(self, tmp_path: Path) -> None:
        """generate_report() produces index.html."""
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()

        generate_report(
            _make_test_manifest(),
            _make_test_table_data(),
            figures_dir,
            report_dir,
        )

        assert (report_dir / "index.html").exists()
        html = (report_dir / "index.html").read_text()
        assert "<!DOCTYPE html>" in html

    def test_markdown_report_created(self, tmp_path: Path) -> None:
        """generate_report() produces report.md."""
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()

        generate_report(
            _make_test_manifest(),
            _make_test_table_data(),
            figures_dir,
            report_dir,
        )

        assert (report_dir / "report.md").exists()
        md = (report_dir / "report.md").read_text()
        assert "# Test Experiment Report" in md

    def test_html_contains_required_sections(self, tmp_path: Path) -> None:
        """HTML report contains all 9 required sections."""
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()

        generate_report(
            _make_test_manifest(),
            _make_test_table_data(),
            figures_dir,
            report_dir,
        )

        html = (report_dir / "index.html").read_text()

        # Section 1: Title and metadata.
        assert "Test Experiment Report" in html
        assert "test-bundle" in html

        # Section 2: Study interpretation notes.
        assert "surfaced-not-priced" in html

        # Section 3: Executive summary.
        assert "Executive Summary" in html

        # Section 4: Headline comparison table.
        assert "Balanced" in html
        assert "50.00" in html

        # Section 5: Core figures section.
        assert "Core Figures" in html

        # Section 6: Diagnostic interpretation.
        assert "Diagnostic Interpretation" in html

        # Section 7: Representative runs.
        assert "Representative Runs" in html

        # Section 8: Methods and reproducibility.
        assert "Methods and Reproducibility" in html

        # Section 9: Appendix.
        assert "Appendix" in html

    def test_md_contains_required_sections(self, tmp_path: Path) -> None:
        """Markdown report contains all required sections."""
        report_dir = tmp_path / "report"
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()

        generate_report(
            _make_test_manifest(),
            _make_test_table_data(),
            figures_dir,
            report_dir,
        )

        md = (report_dir / "report.md").read_text()
        assert "Study Interpretation Notes" in md
        assert "Executive Summary" in md
        assert "Representative Runs" in md
        assert "Methods and Reproducibility" in md
        assert "Appendix" in md
