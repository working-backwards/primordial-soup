"""Tests for governance decision primitives.

Each test exercises a single governance primitive with known inputs
and verifies the expected boolean/numeric output. Edge cases get
their own tests per CLAUDE.md testing rules.

Per governance.md stop/continue criteria, selection and portfolio
management semantics, and execution belief / cost tolerance sections.
"""

from __future__ import annotations

import pytest

from conftest import (
    make_governance_config,
    make_initiative_observation,
    make_portfolio_summary,
)
from primordial_soup.governance import (
    compute_equal_attention,
    compute_weighted_attention,
    expected_prize_value,
    expected_prize_value_density,
    is_low_quality_labor_share_exceeded,
    is_single_initiative_concentration_exceeded,
    rank_unassigned_bounded_prize,
    rank_unassigned_initiatives,
    should_stop_confidence_decline,
    should_stop_execution_overrun,
    should_stop_stagnation,
    should_stop_tam_adequacy,
    would_assignment_exceed_concentration,
    would_assignment_exceed_low_quality_share,
)

# ============================================================================
# Confidence decline stop
# ============================================================================


class TestConfidenceDeclineStop:
    """Test should_stop_confidence_decline primitive."""

    def test_below_threshold_returns_true(self) -> None:
        init = make_initiative_observation(quality_belief_t=0.2)
        config = make_governance_config(confidence_decline_threshold=0.3)
        assert should_stop_confidence_decline(init, config) is True

    def test_at_threshold_returns_false(self) -> None:
        """Exactly at threshold does NOT trigger (strict <)."""
        init = make_initiative_observation(quality_belief_t=0.3)
        config = make_governance_config(confidence_decline_threshold=0.3)
        assert should_stop_confidence_decline(init, config) is False

    def test_above_threshold_returns_false(self) -> None:
        init = make_initiative_observation(quality_belief_t=0.5)
        config = make_governance_config(confidence_decline_threshold=0.3)
        assert should_stop_confidence_decline(init, config) is False

    def test_threshold_none_returns_false(self) -> None:
        """Disabled threshold never triggers."""
        init = make_initiative_observation(quality_belief_t=0.0)
        config = make_governance_config(confidence_decline_threshold=None)
        assert should_stop_confidence_decline(init, config) is False

    def test_zero_belief_triggers(self) -> None:
        init = make_initiative_observation(quality_belief_t=0.0)
        config = make_governance_config(confidence_decline_threshold=0.1)
        assert should_stop_confidence_decline(init, config) is True


# ============================================================================
# TAM adequacy stop
# ============================================================================


class TestTamAdequacyStop:
    """Test should_stop_tam_adequacy primitive."""

    def test_counter_reaches_window_triggers(self) -> None:
        """Stop when counter >= effective patience window."""
        init = make_initiative_observation(
            observable_ceiling=100.0,
            effective_tam_patience_window=5,
            consecutive_reviews_below_tam_ratio=5,
        )
        assert should_stop_tam_adequacy(init) is True

    def test_counter_exceeds_window_triggers(self) -> None:
        init = make_initiative_observation(
            observable_ceiling=100.0,
            effective_tam_patience_window=5,
            consecutive_reviews_below_tam_ratio=7,
        )
        assert should_stop_tam_adequacy(init) is True

    def test_counter_below_window_does_not_trigger(self) -> None:
        init = make_initiative_observation(
            observable_ceiling=100.0,
            effective_tam_patience_window=5,
            consecutive_reviews_below_tam_ratio=4,
        )
        assert should_stop_tam_adequacy(init) is False

    def test_no_observable_ceiling_returns_false(self) -> None:
        """Non-TAM initiatives never trigger TAM stop."""
        init = make_initiative_observation(
            observable_ceiling=None,
            effective_tam_patience_window=None,
            consecutive_reviews_below_tam_ratio=100,
        )
        assert should_stop_tam_adequacy(init) is False

    def test_zero_counter_does_not_trigger(self) -> None:
        init = make_initiative_observation(
            observable_ceiling=100.0,
            effective_tam_patience_window=5,
            consecutive_reviews_below_tam_ratio=0,
        )
        assert should_stop_tam_adequacy(init) is False

    def test_patience_window_one_triggers_immediately(self) -> None:
        """With patience window 1, a single below-threshold review triggers."""
        init = make_initiative_observation(
            observable_ceiling=50.0,
            effective_tam_patience_window=1,
            consecutive_reviews_below_tam_ratio=1,
        )
        assert should_stop_tam_adequacy(init) is True


# ============================================================================
# Stagnation stop
# ============================================================================


class TestStagnationStop:
    """Test should_stop_stagnation primitive (conjunctive rule)."""

    def test_both_legs_hold_for_bounded_prize(self) -> None:
        """Stagnation fires when belief is flat AND TAM counter > 0."""
        # Flat belief history over 5 staffed ticks.
        init = make_initiative_observation(
            quality_belief_t=0.4,
            observable_ceiling=100.0,
            consecutive_reviews_below_tam_ratio=1,
            belief_history=(0.40, 0.401, 0.399, 0.40, 0.40),
        )
        config = make_governance_config(
            stagnation_window_staffed_ticks=5,
            stagnation_belief_change_threshold=0.02,
        )
        assert should_stop_stagnation(init, config) is True

    def test_stagnant_but_tam_counter_zero_does_not_trigger(self) -> None:
        """Bounded-prize: stagnant but passing TAM → no stagnation stop."""
        init = make_initiative_observation(
            quality_belief_t=0.4,
            observable_ceiling=100.0,
            consecutive_reviews_below_tam_ratio=0,
            belief_history=(0.40, 0.40, 0.40, 0.40, 0.40),
        )
        config = make_governance_config(
            stagnation_window_staffed_ticks=5,
            stagnation_belief_change_threshold=0.02,
        )
        assert should_stop_stagnation(init, config) is False

    def test_both_legs_hold_for_non_tam(self) -> None:
        """Non-TAM: stagnant AND belief <= initial baseline → stop."""
        init = make_initiative_observation(
            quality_belief_t=0.5,
            observable_ceiling=None,
            belief_history=(0.50, 0.50, 0.50, 0.50, 0.50),
        )
        config = make_governance_config(
            default_initial_quality_belief=0.5,
            stagnation_window_staffed_ticks=5,
            stagnation_belief_change_threshold=0.02,
        )
        assert should_stop_stagnation(init, config) is True

    def test_non_tam_belief_above_baseline_does_not_trigger(self) -> None:
        """Non-TAM: stagnant but belief above baseline → no stop."""
        init = make_initiative_observation(
            quality_belief_t=0.6,
            observable_ceiling=None,
            belief_history=(0.60, 0.60, 0.60, 0.60, 0.60),
        )
        config = make_governance_config(
            default_initial_quality_belief=0.5,
            stagnation_window_staffed_ticks=5,
            stagnation_belief_change_threshold=0.02,
        )
        assert should_stop_stagnation(init, config) is False

    def test_belief_moved_enough_does_not_trigger(self) -> None:
        """Belief moved more than epsilon → not stagnant."""
        # Oldest belief 0.40, current 0.45 → delta 0.05 > epsilon 0.02.
        init = make_initiative_observation(
            quality_belief_t=0.45,
            observable_ceiling=100.0,
            consecutive_reviews_below_tam_ratio=3,
            belief_history=(0.40, 0.41, 0.42, 0.43, 0.45),
        )
        config = make_governance_config(
            stagnation_window_staffed_ticks=5,
            stagnation_belief_change_threshold=0.02,
        )
        assert should_stop_stagnation(init, config) is False

    def test_history_too_short_does_not_trigger(self) -> None:
        """Cannot evaluate stagnation without a full window of history."""
        # Only 3 entries, need 5.
        init = make_initiative_observation(
            quality_belief_t=0.4,
            observable_ceiling=100.0,
            consecutive_reviews_below_tam_ratio=3,
            belief_history=(0.40, 0.40, 0.40),
        )
        config = make_governance_config(
            stagnation_window_staffed_ticks=5,
            stagnation_belief_change_threshold=0.02,
        )
        assert should_stop_stagnation(init, config) is False

    def test_empty_history_does_not_trigger(self) -> None:
        init = make_initiative_observation(quality_belief_t=0.3)
        config = make_governance_config(stagnation_window_staffed_ticks=5)
        assert should_stop_stagnation(init, config) is False

    def test_window_size_one(self) -> None:
        """Edge case: stagnation window of 1 staffed tick."""
        init = make_initiative_observation(
            quality_belief_t=0.5,
            observable_ceiling=None,
            belief_history=(0.50,),
        )
        config = make_governance_config(
            default_initial_quality_belief=0.5,
            stagnation_window_staffed_ticks=1,
            stagnation_belief_change_threshold=0.02,
        )
        assert should_stop_stagnation(init, config) is True


# ============================================================================
# Execution overrun stop
# ============================================================================


class TestExecutionOverrunStop:
    """Test should_stop_execution_overrun primitive."""

    def test_below_threshold_triggers(self) -> None:
        init = make_initiative_observation(execution_belief_t=0.3)
        config = make_governance_config(exec_overrun_threshold=0.5)
        assert should_stop_execution_overrun(init, config) is True

    def test_at_threshold_does_not_trigger(self) -> None:
        init = make_initiative_observation(execution_belief_t=0.5)
        config = make_governance_config(exec_overrun_threshold=0.5)
        assert should_stop_execution_overrun(init, config) is False

    def test_above_threshold_does_not_trigger(self) -> None:
        init = make_initiative_observation(execution_belief_t=0.8)
        config = make_governance_config(exec_overrun_threshold=0.5)
        assert should_stop_execution_overrun(init, config) is False

    def test_no_threshold_returns_false(self) -> None:
        init = make_initiative_observation(execution_belief_t=0.0)
        config = make_governance_config(exec_overrun_threshold=None)
        assert should_stop_execution_overrun(init, config) is False

    def test_no_execution_channel_returns_false(self) -> None:
        """Initiatives without execution belief can't trigger overrun."""
        init = make_initiative_observation(execution_belief_t=None)
        config = make_governance_config(exec_overrun_threshold=0.5)
        assert should_stop_execution_overrun(init, config) is False


# ============================================================================
# Attention allocation helpers
# ============================================================================


class TestComputeEqualAttention:
    """Test compute_equal_attention helper."""

    def test_equal_split(self) -> None:
        config = make_governance_config(exec_attention_budget=1.0, attention_min=0.1)
        result = compute_equal_attention(5, config)
        assert result == pytest.approx(0.2)

    def test_clamp_to_min(self) -> None:
        """Budget too small → clamp up to attention_min."""
        config = make_governance_config(
            exec_attention_budget=0.3,
            attention_min=0.1,
        )
        # 10 initiatives: raw share = 0.03 < 0.1 → clamp to 0.1
        result = compute_equal_attention(10, config)
        assert result == pytest.approx(0.1)

    def test_clamp_to_max(self) -> None:
        config = make_governance_config(
            exec_attention_budget=2.0,
            attention_min=0.1,
            attention_max=0.5,
        )
        # 1 initiative: raw share = 2.0 > 0.5 → clamp to 0.5
        result = compute_equal_attention(1, config)
        assert result == pytest.approx(0.5)

    def test_zero_initiatives_returns_zero(self) -> None:
        config = make_governance_config()
        assert compute_equal_attention(0, config) == pytest.approx(0.0)

    def test_max_none_means_one(self) -> None:
        """attention_max=None → effective max is 1.0."""
        config = make_governance_config(
            exec_attention_budget=5.0,
            attention_min=0.1,
            attention_max=None,
        )
        result = compute_equal_attention(1, config)
        assert result == pytest.approx(1.0)


class TestComputeWeightedAttention:
    """Test compute_weighted_attention helper."""

    def test_proportional_allocation(self) -> None:
        config = make_governance_config(
            exec_attention_budget=1.0,
            attention_min=0.1,
            attention_max=None,
        )
        weights = (("A", 3.0), ("B", 1.0))
        result = compute_weighted_attention(weights, config)
        result_dict = dict(result)
        assert result_dict["A"] == pytest.approx(0.75)
        assert result_dict["B"] == pytest.approx(0.25)

    def test_empty_weights_returns_empty(self) -> None:
        config = make_governance_config()
        assert compute_weighted_attention((), config) == ()

    def test_zero_weights_distributes_equally(self) -> None:
        config = make_governance_config(
            exec_attention_budget=1.0,
            attention_min=0.1,
        )
        weights = (("A", 0.0), ("B", 0.0))
        result = compute_weighted_attention(weights, config)
        result_dict = dict(result)
        assert result_dict["A"] == pytest.approx(0.5)
        assert result_dict["B"] == pytest.approx(0.5)

    def test_clamp_to_max(self) -> None:
        config = make_governance_config(
            exec_attention_budget=1.0,
            attention_min=0.1,
            attention_max=0.4,
        )
        # All weight to one initiative → clamped to 0.4
        weights = (("A", 10.0), ("B", 0.001))
        result = compute_weighted_attention(weights, config)
        result_dict = dict(result)
        assert result_dict["A"] == pytest.approx(0.4)


# ============================================================================
# Selection and ranking helpers
# ============================================================================


class TestExpectedPrizeValue:
    """Test expected_prize_value and density calculations."""

    def test_basic_computation(self) -> None:
        init = make_initiative_observation(
            quality_belief_t=0.7,
            observable_ceiling=200.0,
        )
        assert expected_prize_value(init) == pytest.approx(140.0)

    def test_no_ceiling_returns_zero(self) -> None:
        init = make_initiative_observation(observable_ceiling=None)
        assert expected_prize_value(init) == pytest.approx(0.0)

    def test_density_normalizes_by_team_size(self) -> None:
        init = make_initiative_observation(
            quality_belief_t=0.8,
            observable_ceiling=100.0,
            required_team_size=2,
        )
        # expected = 80, density = 80 / 2 = 40
        assert expected_prize_value_density(init) == pytest.approx(40.0)

    def test_density_team_size_one(self) -> None:
        init = make_initiative_observation(
            quality_belief_t=0.5,
            observable_ceiling=100.0,
            required_team_size=1,
        )
        assert expected_prize_value_density(init) == pytest.approx(50.0)


class TestRankUnassignedBoundedPrize:
    """Test rank_unassigned_bounded_prize ranking function."""

    def test_ranks_by_density_descending(self) -> None:
        a = make_initiative_observation(
            initiative_id="A",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.5,
            observable_ceiling=100.0,
            required_team_size=1,
        )
        b = make_initiative_observation(
            initiative_id="B",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.8,
            observable_ceiling=100.0,
            required_team_size=1,
        )
        result = rank_unassigned_bounded_prize((a, b))
        assert result[0].initiative_id == "B"
        assert result[1].initiative_id == "A"

    def test_filters_non_unassigned(self) -> None:
        active = make_initiative_observation(
            initiative_id="A",
            lifecycle_state="active",
            observable_ceiling=100.0,
        )
        unassigned = make_initiative_observation(
            initiative_id="B",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            observable_ceiling=100.0,
        )
        result = rank_unassigned_bounded_prize((active, unassigned))
        assert len(result) == 1
        assert result[0].initiative_id == "B"

    def test_filters_no_ceiling(self) -> None:
        no_ceiling = make_initiative_observation(
            initiative_id="A",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            observable_ceiling=None,
        )
        result = rank_unassigned_bounded_prize((no_ceiling,))
        assert len(result) == 0

    def test_ties_broken_by_id(self) -> None:
        """Equal density → alphabetical initiative_id."""
        a = make_initiative_observation(
            initiative_id="B",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.5,
            observable_ceiling=100.0,
        )
        b = make_initiative_observation(
            initiative_id="A",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.5,
            observable_ceiling=100.0,
        )
        result = rank_unassigned_bounded_prize((a, b))
        assert result[0].initiative_id == "A"
        assert result[1].initiative_id == "B"


class TestRankUnassignedInitiatives:
    """Test rank_unassigned_initiatives (bounded first, then unbounded)."""

    def test_bounded_before_unbounded(self) -> None:
        bounded = make_initiative_observation(
            initiative_id="B",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.3,
            observable_ceiling=50.0,
        )
        unbounded = make_initiative_observation(
            initiative_id="U",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.9,
            observable_ceiling=None,
        )
        result = rank_unassigned_initiatives((unbounded, bounded))
        assert result[0].initiative_id == "B"
        assert result[1].initiative_id == "U"

    def test_unbounded_ranked_by_belief(self) -> None:
        u1 = make_initiative_observation(
            initiative_id="U1",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.4,
            observable_ceiling=None,
        )
        u2 = make_initiative_observation(
            initiative_id="U2",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.7,
            observable_ceiling=None,
        )
        result = rank_unassigned_initiatives((u1, u2))
        assert result[0].initiative_id == "U2"
        assert result[1].initiative_id == "U1"

    def test_empty_returns_empty(self) -> None:
        assert rank_unassigned_initiatives(()) == ()

    def test_filters_non_unassigned(self) -> None:
        active = make_initiative_observation(
            initiative_id="A",
            lifecycle_state="active",
            quality_belief_t=0.9,
        )
        result = rank_unassigned_initiatives((active,))
        assert len(result) == 0


# ============================================================================
# Portfolio-risk check helpers
# ============================================================================


class TestLowQualityLaborShareExceeded:
    """Test is_low_quality_labor_share_exceeded."""

    def test_exceeded(self) -> None:
        ps = make_portfolio_summary(
            active_labor_total=10,
            active_labor_below_quality_threshold=4,
            low_quality_belief_labor_share=0.4,
        )
        config = make_governance_config(
            low_quality_belief_threshold=0.4,
            max_low_quality_belief_labor_share=0.3,
        )
        assert is_low_quality_labor_share_exceeded(ps, config) is True

    def test_within_limit(self) -> None:
        ps = make_portfolio_summary(
            active_labor_total=10,
            active_labor_below_quality_threshold=2,
            low_quality_belief_labor_share=0.2,
        )
        config = make_governance_config(
            low_quality_belief_threshold=0.4,
            max_low_quality_belief_labor_share=0.3,
        )
        assert is_low_quality_labor_share_exceeded(ps, config) is False

    def test_no_threshold_configured(self) -> None:
        ps = make_portfolio_summary(low_quality_belief_labor_share=0.9)
        config = make_governance_config(low_quality_belief_threshold=None)
        assert is_low_quality_labor_share_exceeded(ps, config) is False

    def test_no_cap_configured(self) -> None:
        ps = make_portfolio_summary(low_quality_belief_labor_share=0.9)
        config = make_governance_config(
            low_quality_belief_threshold=0.4,
            max_low_quality_belief_labor_share=None,
        )
        assert is_low_quality_labor_share_exceeded(ps, config) is False

    def test_no_share_data(self) -> None:
        """None labor share (no active labor) → not exceeded."""
        ps = make_portfolio_summary(low_quality_belief_labor_share=None)
        config = make_governance_config(
            low_quality_belief_threshold=0.4,
            max_low_quality_belief_labor_share=0.3,
        )
        assert is_low_quality_labor_share_exceeded(ps, config) is False


class TestSingleInitiativeConcentrationExceeded:
    """Test is_single_initiative_concentration_exceeded."""

    def test_exceeded(self) -> None:
        ps = make_portfolio_summary(max_single_initiative_labor_share=0.6)
        config = make_governance_config(max_single_initiative_labor_share=0.5)
        assert is_single_initiative_concentration_exceeded(ps, config) is True

    def test_within_limit(self) -> None:
        ps = make_portfolio_summary(max_single_initiative_labor_share=0.3)
        config = make_governance_config(max_single_initiative_labor_share=0.5)
        assert is_single_initiative_concentration_exceeded(ps, config) is False

    def test_no_cap(self) -> None:
        ps = make_portfolio_summary(max_single_initiative_labor_share=1.0)
        config = make_governance_config(max_single_initiative_labor_share=None)
        assert is_single_initiative_concentration_exceeded(ps, config) is False

    def test_no_share_data(self) -> None:
        ps = make_portfolio_summary(max_single_initiative_labor_share=None)
        config = make_governance_config(max_single_initiative_labor_share=0.5)
        assert is_single_initiative_concentration_exceeded(ps, config) is False


class TestWouldAssignmentExceedConcentration:
    """Test would_assignment_exceed_concentration."""

    def test_would_exceed(self) -> None:
        init = make_initiative_observation(required_team_size=3)
        # After assignment: 3 new out of (2 existing + 3 new = 5) → 60%
        ps = make_portfolio_summary(active_labor_total=2)
        config = make_governance_config(max_single_initiative_labor_share=0.5)
        assert would_assignment_exceed_concentration(init, ps, config) is True

    def test_would_not_exceed(self) -> None:
        init = make_initiative_observation(required_team_size=1)
        # After: 1 new out of (10 existing + 1 = 11) → ~9%
        ps = make_portfolio_summary(active_labor_total=10)
        config = make_governance_config(max_single_initiative_labor_share=0.5)
        assert would_assignment_exceed_concentration(init, ps, config) is False

    def test_no_cap(self) -> None:
        init = make_initiative_observation(required_team_size=10)
        ps = make_portfolio_summary(active_labor_total=0)
        config = make_governance_config(max_single_initiative_labor_share=None)
        assert would_assignment_exceed_concentration(init, ps, config) is False


class TestWouldAssignmentExceedLowQualityShare:
    """Test would_assignment_exceed_low_quality_share."""

    def test_low_quality_would_exceed(self) -> None:
        # Initiative below threshold
        init = make_initiative_observation(
            quality_belief_t=0.3,
            required_team_size=2,
        )
        # Currently 1 low-quality labor out of 4. Adding 2 → 3/6 = 50% > 30%.
        ps = make_portfolio_summary(
            active_labor_total=4,
            active_labor_below_quality_threshold=1,
        )
        config = make_governance_config(
            low_quality_belief_threshold=0.4,
            max_low_quality_belief_labor_share=0.3,
        )
        assert would_assignment_exceed_low_quality_share(init, ps, config) is True

    def test_high_quality_not_checked(self) -> None:
        """Initiative above threshold → no low-quality concern."""
        init = make_initiative_observation(quality_belief_t=0.6)
        ps = make_portfolio_summary(active_labor_total=4)
        config = make_governance_config(
            low_quality_belief_threshold=0.4,
            max_low_quality_belief_labor_share=0.01,
        )
        assert would_assignment_exceed_low_quality_share(init, ps, config) is False

    def test_no_thresholds(self) -> None:
        init = make_initiative_observation(quality_belief_t=0.1)
        ps = make_portfolio_summary()
        config = make_governance_config(
            low_quality_belief_threshold=None,
            max_low_quality_belief_labor_share=None,
        )
        assert would_assignment_exceed_low_quality_share(init, ps, config) is False
