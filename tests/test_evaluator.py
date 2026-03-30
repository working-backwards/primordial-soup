"""Tests for the evaluator wrapper (evaluator.py).

Tests verify:
    - GovernanceParams construction and frozen contract
    - SeedResult and ObjectiveResult dataclass contracts
    - evaluate_policy happy path (baseline, multiple seeds)
    - evaluate_policy with all three policy presets
    - evaluate_policy with portfolio guardrails
    - Workforce resolution edge cases
    - Unknown preset rejection
    - Empty seeds rejection
    - Determinism: same inputs produce same outputs
"""

from __future__ import annotations

import pytest

from primordial_soup.evaluator import (
    GovernanceParams,
    ObjectiveResult,
    evaluate_policy,
)
from primordial_soup.presets import make_environment_spec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _baseline_env():
    """Return the balanced_incumbent environment spec."""
    return make_environment_spec("balanced_incumbent")


# ---------------------------------------------------------------------------
# TestGovernanceParams
# ---------------------------------------------------------------------------


class TestGovernanceParams:
    def test_defaults(self):
        params = GovernanceParams()
        assert params.policy_preset == "balanced"
        assert params.team_count == 24
        assert params.total_labor_endowment == 210
        assert params.ramp_period == 4
        # Default team_sizes matches the baseline mixed-size workforce:
        # 10×5 + 12×10 + 2×20 = 210 total labor.
        assert params.team_sizes is not None
        assert len(params.team_sizes) == 24
        assert sum(params.team_sizes) == 210

    def test_frozen(self):
        params = GovernanceParams()
        with pytest.raises((AttributeError, TypeError)):
            params.policy_preset = "x"  # type: ignore[misc]

    def test_custom_workforce(self):
        params = GovernanceParams(
            team_count=3,
            total_labor_endowment=10,
            team_sizes=(4, 3, 3),
        )
        assert params.team_count == 3
        assert sum(params.team_sizes) == 10


# ---------------------------------------------------------------------------
# TestEvaluatePolicy — integration tests
# ---------------------------------------------------------------------------


class TestEvaluatePolicy:
    def test_baseline_single_seed(self):
        """Baseline evaluation with one seed returns valid ObjectiveResult."""
        params = GovernanceParams()
        result = evaluate_policy(params, seeds=(42,), environment_spec=_baseline_env())

        assert isinstance(result, ObjectiveResult)
        assert result.n_seeds == 1
        assert len(result.per_seed_results) == 1
        assert result.per_seed_results[0].seed == 42
        assert result.mean_cumulative_value > 0

    def test_multiple_seeds(self):
        """Multiple seeds produce one SeedResult each."""
        params = GovernanceParams()
        result = evaluate_policy(params, seeds=(42, 43), environment_spec=_baseline_env())

        assert result.n_seeds == 2
        assert len(result.per_seed_results) == 2
        assert result.per_seed_results[0].seed == 42
        assert result.per_seed_results[1].seed == 43

    def test_mean_is_average_of_seeds(self):
        """Aggregate means are arithmetic averages of per-seed values."""
        params = GovernanceParams()
        result = evaluate_policy(params, seeds=(42, 43), environment_spec=_baseline_env())

        expected_mean = sum(r.cumulative_value for r in result.per_seed_results) / 2
        assert result.mean_cumulative_value == pytest.approx(expected_mean)

    def test_total_major_wins_is_sum(self):
        """total_major_wins is the sum across seeds, not the mean."""
        params = GovernanceParams()
        result = evaluate_policy(params, seeds=(42, 43), environment_spec=_baseline_env())

        expected_total = sum(r.major_win_count for r in result.per_seed_results)
        assert result.total_major_wins == expected_total

    def test_all_three_presets(self):
        """All three policy presets produce valid results."""
        env = _baseline_env()
        for preset in ("balanced", "aggressive_stop_loss", "patient_moonshot"):
            params = GovernanceParams(policy_preset=preset)
            result = evaluate_policy(params, seeds=(42,), environment_spec=env)
            assert result.n_seeds == 1
            assert result.per_seed_results[0].summary["policy_id"] == preset

    def test_seed_result_has_summary_dict(self):
        """SeedResult.summary contains the full summarize_run_result dict."""
        params = GovernanceParams()
        result = evaluate_policy(params, seeds=(42,), environment_spec=_baseline_env())
        summary = result.per_seed_results[0].summary

        # Verify key fields from summarize_run_result are present.
        assert "cumulative_value" in summary
        assert "major_win_count" in summary
        assert "value_by_family" in summary
        assert "first_completion_tick_by_family" in summary

    def test_determinism(self):
        """Same inputs produce identical outputs."""
        params = GovernanceParams()
        env = _baseline_env()
        r1 = evaluate_policy(params, seeds=(42,), environment_spec=env)
        r2 = evaluate_policy(params, seeds=(42,), environment_spec=env)

        assert r1.mean_cumulative_value == pytest.approx(r2.mean_cumulative_value)
        assert r1.total_major_wins == r2.total_major_wins
        assert r1.mean_terminal_capability == pytest.approx(r2.mean_terminal_capability)


# ---------------------------------------------------------------------------
# TestEvaluatePolicyEdgeCases
# ---------------------------------------------------------------------------


class TestEvaluatePolicyEdgeCases:
    def test_unknown_preset_raises(self):
        params = GovernanceParams(policy_preset="nonexistent")
        with pytest.raises(ValueError, match="Unknown policy preset"):
            evaluate_policy(params, seeds=(42,), environment_spec=_baseline_env())

    def test_empty_seeds_raises(self):
        params = GovernanceParams()
        with pytest.raises(ValueError, match="seeds must not be empty"):
            evaluate_policy(params, seeds=(), environment_spec=_baseline_env())

    def test_team_sizes_mismatch_raises(self):
        params = GovernanceParams(
            team_count=3,
            total_labor_endowment=10,
            team_sizes=(4, 3),  # wrong length
        )
        with pytest.raises(ValueError, match="team_sizes length"):
            evaluate_policy(params, seeds=(42,), environment_spec=_baseline_env())

    def test_team_sizes_sum_mismatch_raises(self):
        params = GovernanceParams(
            team_count=3,
            total_labor_endowment=10,
            team_sizes=(4, 3, 2),  # sum=9 != 10
        )
        with pytest.raises(ValueError, match="team_sizes sum"):
            evaluate_policy(params, seeds=(42,), environment_spec=_baseline_env())

    def test_indivisible_labor_raises(self):
        params = GovernanceParams(
            team_count=3,
            total_labor_endowment=10,
            team_sizes=None,  # 10 / 3 doesn't divide evenly
        )
        with pytest.raises(ValueError, match="divisible"):
            evaluate_policy(params, seeds=(42,), environment_spec=_baseline_env())

    def test_different_environment_family(self):
        """Evaluator works with non-default environment families."""
        params = GovernanceParams()
        env = make_environment_spec("discovery_heavy")
        result = evaluate_policy(params, seeds=(42,), environment_spec=env)
        assert result.n_seeds == 1
        assert result.mean_cumulative_value > 0
