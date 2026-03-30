"""Tests for learning.py — signal model, belief updates, and learning mechanics.

Tests verify:
    - Attention noise modifier g(a): shape, boundary conditions, clamping
    - Effective signal st_dev: formula correctness, dependency/capability effects
    - Learning efficiency L(d): canonical formula and override
    - Ramp multiplier: linear/exponential shapes, boundary ticks, monotonicity
    - Signal draws: determinism, distributional correctness
    - Quality belief update: convergence, clamping, zero-rate edge cases
    - Execution belief update: convergence, clamping, no dependency modulation
"""

from __future__ import annotations

import math

import pytest

from primordial_soup.learning import (
    attention_noise_modifier,
    draw_execution_signal,
    draw_quality_signal,
    effective_signal_st_dev_t,
    learning_efficiency,
    ramp_multiplier,
    update_execution_belief,
    update_quality_belief,
)
from primordial_soup.noise import create_initiative_rng_pair
from primordial_soup.types import RAMP_EXPONENTIAL_K, RampShape

# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

# Default g(a) parameters matching conftest.py's make_model_config defaults.
# Used to reduce boilerplate in tests that aren't specifically testing
# the attention curve shape.
_DEFAULT_G_PARAMS = dict(
    attention_noise_threshold=0.1,  # a_min
    low_attention_penalty_slope=2.0,  # k_low
    attention_curve_exponent=3.0,  # k
    min_attention_noise_modifier=0.3,  # g_min
    max_attention_noise_modifier=None,  # g_max (uncapped)
)


def _make_rng_pair(world_seed: int = 42, initiative_index: int = 0):
    """Create an InitiativeRngPair for tests that need RNG draws."""
    return create_initiative_rng_pair(
        world_seed=world_seed,
        initiative_index=initiative_index,
    )


# ---------------------------------------------------------------------------
# Attention noise modifier g(a)
# ---------------------------------------------------------------------------


class TestAttentionNoiseModifier:
    """Tests for the attention noise modifier g(a) curve."""

    def test_at_threshold_raw_value_is_one(self):
        """g_raw(a_min) = 1.0 in both branches before clamping."""
        result = attention_noise_modifier(
            0.1,  # a = a_min
            attention_noise_threshold=0.1,
            low_attention_penalty_slope=2.0,
            attention_curve_exponent=3.0,
            min_attention_noise_modifier=0.0,  # no floor, to see raw value
            max_attention_noise_modifier=None,
        )
        assert result == pytest.approx(1.0)

    def test_above_threshold_noise_decreases(self):
        """Higher attention above a_min should give lower g(a) (less noise)."""
        g_low = attention_noise_modifier(0.2, **_DEFAULT_G_PARAMS)
        g_high = attention_noise_modifier(0.8, **_DEFAULT_G_PARAMS)
        # More attention → less noise → lower g(a).
        assert g_high < g_low

    def test_below_threshold_noise_increases(self):
        """Lower attention below a_min should give higher g(a) (more noise)."""
        g_at_threshold = attention_noise_modifier(0.1, **_DEFAULT_G_PARAMS)
        g_below = attention_noise_modifier(0.05, **_DEFAULT_G_PARAMS)
        # Less attention → more noise → higher g(a).
        assert g_below > g_at_threshold

    def test_zero_attention_gives_large_noise_modifier(self):
        """At a=0, g(a) should be significantly above 1.0."""
        result = attention_noise_modifier(0.0, **_DEFAULT_G_PARAMS)
        # g_raw(0) = 1 + k_low * a_min = 1 + 2.0 * 0.1 = 1.2
        assert result == pytest.approx(1.2)

    def test_max_attention_gives_small_noise_modifier(self):
        """At a=1.0, g(a) should be well below 1.0 (clamped by g_min)."""
        result = attention_noise_modifier(1.0, **_DEFAULT_G_PARAMS)
        # g_raw(1.0) = 1 / (1 + 3.0 * (1.0 - 0.1)) = 1/3.7 ≈ 0.27
        # But g_min = 0.3, so the floor clamp applies.
        assert result == pytest.approx(0.3)
        # Verify the raw value is below the floor to confirm clamping.
        g_raw = 1.0 / (1.0 + 3.0 * 0.9)
        assert g_raw < 0.3

    def test_max_attention_unclamped_gives_formula_value(self):
        """At a=1.0 with g_min=0, the raw formula value is returned."""
        result = attention_noise_modifier(
            1.0,
            attention_noise_threshold=0.1,
            low_attention_penalty_slope=2.0,
            attention_curve_exponent=3.0,
            min_attention_noise_modifier=0.0,  # no floor
            max_attention_noise_modifier=None,
        )
        expected = 1.0 / (1.0 + 3.0 * 0.9)
        assert result == pytest.approx(expected)

    def test_floor_clamp_prevents_below_g_min(self):
        """g(a) must never go below g_min, even with very high attention."""
        result = attention_noise_modifier(
            1.0,
            attention_noise_threshold=0.1,
            low_attention_penalty_slope=2.0,
            attention_curve_exponent=100.0,  # extreme curvature
            min_attention_noise_modifier=0.5,  # high floor
            max_attention_noise_modifier=None,
        )
        # Without floor, g_raw would be very small. Floor should clamp it.
        assert result == pytest.approx(0.5)

    def test_ceiling_clamp_when_g_max_is_set(self):
        """g(a) must not exceed g_max when g_max is not None."""
        result = attention_noise_modifier(
            0.0,  # low attention → high g_raw
            attention_noise_threshold=0.5,
            low_attention_penalty_slope=10.0,  # steep penalty
            attention_curve_exponent=3.0,
            min_attention_noise_modifier=0.3,
            max_attention_noise_modifier=2.0,  # cap at 2.0
        )
        # g_raw(0) = 1 + 10.0 * 0.5 = 6.0, but capped at 2.0
        assert result == pytest.approx(2.0)

    def test_ceiling_none_allows_large_values(self):
        """When g_max is None, g(a) is unbounded above (only floor applies)."""
        result = attention_noise_modifier(
            0.0,  # low attention → high g_raw
            attention_noise_threshold=0.5,
            low_attention_penalty_slope=10.0,  # steep penalty
            attention_curve_exponent=3.0,
            min_attention_noise_modifier=0.3,
            max_attention_noise_modifier=None,  # no ceiling
        )
        # g_raw(0) = 1 + 10.0 * 0.5 = 6.0, no cap applied
        assert result == pytest.approx(6.0)

    def test_continuity_at_threshold(self):
        """Both branches of g_raw should give the same value at a_min."""
        # Test with a value slightly below and at a_min.
        epsilon = 1e-12
        a_min = 0.3

        g_just_below = attention_noise_modifier(
            a_min - epsilon,
            attention_noise_threshold=a_min,
            low_attention_penalty_slope=5.0,
            attention_curve_exponent=3.0,
            min_attention_noise_modifier=0.0,  # no floor, to see raw value
            max_attention_noise_modifier=None,
        )
        g_at = attention_noise_modifier(
            a_min,
            attention_noise_threshold=a_min,
            low_attention_penalty_slope=5.0,
            attention_curve_exponent=3.0,
            min_attention_noise_modifier=0.0,
            max_attention_noise_modifier=None,
        )

        # Both should be very close to 1.0 (the shared value at a_min).
        assert g_just_below == pytest.approx(1.0, abs=1e-10)
        assert g_at == pytest.approx(1.0)

    def test_exact_formula_below_threshold(self):
        """Verify the exact below-threshold formula: g_raw = 1 + k_low * (a_min - a)."""
        result = attention_noise_modifier(
            0.02,
            attention_noise_threshold=0.1,
            low_attention_penalty_slope=3.0,
            attention_curve_exponent=5.0,
            min_attention_noise_modifier=0.0,
            max_attention_noise_modifier=None,
        )
        # g_raw = 1 + 3.0 * (0.1 - 0.02) = 1 + 3.0 * 0.08 = 1.24
        assert result == pytest.approx(1.24)

    def test_exact_formula_above_threshold(self):
        """Verify the exact above-threshold formula: g_raw = 1 / (1 + k * (a - a_min))."""
        result = attention_noise_modifier(
            0.5,
            attention_noise_threshold=0.2,
            low_attention_penalty_slope=2.0,
            attention_curve_exponent=4.0,
            min_attention_noise_modifier=0.0,
            max_attention_noise_modifier=None,
        )
        # g_raw = 1 / (1 + 4.0 * (0.5 - 0.2)) = 1 / (1 + 1.2) = 1 / 2.2
        assert result == pytest.approx(1.0 / 2.2)


# ---------------------------------------------------------------------------
# Effective signal standard deviation σ_eff
# ---------------------------------------------------------------------------


class TestEffectiveSignalStDev:
    """Tests for effective_signal_st_dev_t."""

    def test_baseline_no_dependency_no_capability(self):
        """With d=0, g(a)=1, C=1: σ_eff should equal base_signal_st_dev."""
        result = effective_signal_st_dev_t(
            base_signal_st_dev=0.15,
            dependency_level=0.0,
            dependency_noise_exponent=1.0,
            attention_noise_modifier_value=1.0,  # g(a) = 1
            portfolio_capability_t=1.0,  # C_t = 1
        )
        assert result == pytest.approx(0.15)

    def test_dependency_increases_noise(self):
        """Higher dependency level should increase effective noise."""
        sigma_no_dep = effective_signal_st_dev_t(
            base_signal_st_dev=0.15,
            dependency_level=0.0,
            dependency_noise_exponent=1.0,
            attention_noise_modifier_value=1.0,
            portfolio_capability_t=1.0,
        )
        sigma_high_dep = effective_signal_st_dev_t(
            base_signal_st_dev=0.15,
            dependency_level=0.5,
            dependency_noise_exponent=1.0,
            attention_noise_modifier_value=1.0,
            portfolio_capability_t=1.0,
        )
        assert sigma_high_dep > sigma_no_dep

    def test_higher_attention_reduces_noise(self):
        """Lower g(a) (more attention) should reduce effective noise."""
        sigma_low_attention = effective_signal_st_dev_t(
            base_signal_st_dev=0.15,
            dependency_level=0.0,
            dependency_noise_exponent=1.0,
            attention_noise_modifier_value=1.5,  # low attention → high g
            portfolio_capability_t=1.0,
        )
        sigma_high_attention = effective_signal_st_dev_t(
            base_signal_st_dev=0.15,
            dependency_level=0.0,
            dependency_noise_exponent=1.0,
            attention_noise_modifier_value=0.5,  # high attention → low g
            portfolio_capability_t=1.0,
        )
        assert sigma_high_attention < sigma_low_attention

    def test_portfolio_capability_reduces_noise(self):
        """Higher portfolio capability should reduce effective noise."""
        sigma_low_cap = effective_signal_st_dev_t(
            base_signal_st_dev=0.15,
            dependency_level=0.2,
            dependency_noise_exponent=1.0,
            attention_noise_modifier_value=1.0,
            portfolio_capability_t=1.0,
        )
        sigma_high_cap = effective_signal_st_dev_t(
            base_signal_st_dev=0.15,
            dependency_level=0.2,
            dependency_noise_exponent=1.0,
            attention_noise_modifier_value=1.0,
            portfolio_capability_t=2.0,
        )
        assert sigma_high_cap < sigma_low_cap
        # With C_t = 2.0, noise should be exactly halved.
        assert sigma_high_cap == pytest.approx(sigma_low_cap / 2.0)

    def test_exact_formula(self):
        """Verify the exact formula: σ_base * (1 + α_d * d) * g(a) / C_t."""
        result = effective_signal_st_dev_t(
            base_signal_st_dev=0.2,
            dependency_level=0.4,
            dependency_noise_exponent=1.5,
            attention_noise_modifier_value=0.8,
            portfolio_capability_t=1.5,
        )
        # σ_eff = 0.2 * (1 + 1.5 * 0.4) * 0.8 / 1.5
        #       = 0.2 * 1.6 * 0.8 / 1.5
        #       = 0.256 / 1.5
        expected = 0.2 * (1.0 + 1.5 * 0.4) * 0.8 / 1.5
        assert result == pytest.approx(expected)

    def test_zero_dependency_noise_exponent(self):
        """When α_d = 0, dependency has no effect on noise."""
        sigma_no_dep = effective_signal_st_dev_t(
            base_signal_st_dev=0.15,
            dependency_level=0.0,
            dependency_noise_exponent=0.0,
            attention_noise_modifier_value=1.0,
            portfolio_capability_t=1.0,
        )
        sigma_high_dep = effective_signal_st_dev_t(
            base_signal_st_dev=0.15,
            dependency_level=0.9,
            dependency_noise_exponent=0.0,
            attention_noise_modifier_value=1.0,
            portfolio_capability_t=1.0,
        )
        assert sigma_no_dep == pytest.approx(sigma_high_dep)


# ---------------------------------------------------------------------------
# Learning efficiency L(d)
# ---------------------------------------------------------------------------


class TestLearningEfficiency:
    """Tests for learning_efficiency L(d)."""

    def test_zero_dependency_full_efficiency(self):
        """At d=0, L(d) = 1.0 (full learning efficiency)."""
        assert learning_efficiency(0.0) == pytest.approx(1.0)

    def test_max_dependency_zero_efficiency(self):
        """At d=1.0, L(d) = 0.0 (no learning)."""
        assert learning_efficiency(1.0) == pytest.approx(0.0)

    def test_mid_dependency_proportional(self):
        """At d=0.3, L(d) = 0.7 (linear relationship)."""
        assert learning_efficiency(0.3) == pytest.approx(0.7)

    def test_override_replaces_formula(self):
        """When dependency_learning_scale is set, it overrides L(d)."""
        # Even with d=0.9 (which would give L=0.1), the override wins.
        result = learning_efficiency(0.9, dependency_learning_scale=0.75)
        assert result == pytest.approx(0.75)

    def test_override_none_uses_canonical_formula(self):
        """When dependency_learning_scale is None, the canonical formula is used."""
        result = learning_efficiency(0.4, dependency_learning_scale=None)
        assert result == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Ramp multiplier
# ---------------------------------------------------------------------------


class TestRampMultiplier:
    """Tests for the assignment-relative ramp multiplier."""

    def test_first_tick_partial_efficiency_linear(self):
        """On the first staffed tick (t=0), linear ramp gives 1/R."""
        # R = 5, t_elapsed = 0: ramp_fraction = (0 + 1) / 5 = 0.2
        result = ramp_multiplier(0, 5, RampShape.LINEAR)
        assert result == pytest.approx(0.2)

    def test_first_tick_partial_efficiency_exponential(self):
        """On the first staffed tick (t=0), exponential ramp gives positive partial value."""
        # R = 5, t_elapsed = 0: ramp_fraction = 1/5 = 0.2
        # ramp = 1 - exp(-3.0 * 0.2) = 1 - exp(-0.6)
        result = ramp_multiplier(0, 5, RampShape.EXPONENTIAL)
        expected = 1.0 - math.exp(-RAMP_EXPONENTIAL_K * 0.2)
        assert result == pytest.approx(expected)
        # Must be positive but less than 1.
        assert 0.0 < result < 1.0

    def test_fully_ramped_linear(self):
        """At t_elapsed = R-1, linear ramp gives 1.0."""
        # R = 5, t_elapsed = 4: is_ramping = (4 < 4) = False → 1.0
        result = ramp_multiplier(4, 5, RampShape.LINEAR)
        assert result == pytest.approx(1.0)

    def test_fully_ramped_exponential(self):
        """At t_elapsed = R-1, exponential ramp gives 1.0 (not the formula value)."""
        # R = 5, t_elapsed = 4: is_ramping = (4 < 4) = False → 1.0
        # (The exponential formula would give ~0.95, but the spec says
        # ramp_multiplier = 1.0 when not ramping.)
        result = ramp_multiplier(4, 5, RampShape.EXPONENTIAL)
        assert result == pytest.approx(1.0)

    def test_past_ramp_period(self):
        """Well past the ramp period, multiplier is 1.0."""
        result = ramp_multiplier(100, 5, RampShape.LINEAR)
        assert result == pytest.approx(1.0)

    def test_mid_ramp_linear(self):
        """At t_elapsed = 2 with R = 5, linear ramp gives 3/5."""
        # ramp_fraction = (2 + 1) / 5 = 0.6
        result = ramp_multiplier(2, 5, RampShape.LINEAR)
        assert result == pytest.approx(0.6)

    def test_mid_ramp_exponential(self):
        """At t_elapsed = 2 with R = 5, exponential ramp matches formula."""
        # ramp_fraction = (2 + 1) / 5 = 0.6
        # ramp = 1 - exp(-3.0 * 0.6) = 1 - exp(-1.8)
        result = ramp_multiplier(2, 5, RampShape.EXPONENTIAL)
        expected = 1.0 - math.exp(-RAMP_EXPONENTIAL_K * 0.6)
        assert result == pytest.approx(expected)

    def test_ramp_period_one_immediate_full_efficiency(self):
        """With R=1, there is no ramp: multiplier is always 1.0."""
        assert ramp_multiplier(0, 1, RampShape.LINEAR) == pytest.approx(1.0)
        assert ramp_multiplier(0, 1, RampShape.EXPONENTIAL) == pytest.approx(1.0)

    def test_ramp_period_zero_immediate_full_efficiency(self):
        """With R=0 (edge case), multiplier is always 1.0."""
        assert ramp_multiplier(0, 0, RampShape.LINEAR) == pytest.approx(1.0)

    def test_linear_monotonically_increases(self):
        """Linear ramp multiplier should increase monotonically over the ramp period."""
        ramp_period = 10
        values = [
            ramp_multiplier(t, ramp_period, RampShape.LINEAR) for t in range(ramp_period + 2)
        ]
        # Check strict monotonicity up to R-1, then all 1.0.
        for i in range(1, ramp_period - 1):
            assert (
                values[i] > values[i - 1]
            ), f"Linear ramp not monotonic at t={i}: {values[i]} <= {values[i - 1]}"
        # At and past R-1, should be 1.0.
        for i in range(ramp_period - 1, len(values)):
            assert values[i] == pytest.approx(1.0)

    def test_exponential_monotonically_increases(self):
        """Exponential ramp multiplier should increase monotonically."""
        ramp_period = 10
        values = [
            ramp_multiplier(t, ramp_period, RampShape.EXPONENTIAL) for t in range(ramp_period + 2)
        ]
        for i in range(1, ramp_period - 1):
            assert (
                values[i] > values[i - 1]
            ), f"Exponential ramp not monotonic at t={i}: {values[i]} <= {values[i - 1]}"
        for i in range(ramp_period - 1, len(values)):
            assert values[i] == pytest.approx(1.0)

    def test_ramp_period_two_linear(self):
        """With R=2: t=0 gives 0.5, t=1 gives 1.0."""
        # t=0: ramp_fraction = 1/2 = 0.5, is_ramping = (0 < 1) = True
        assert ramp_multiplier(0, 2, RampShape.LINEAR) == pytest.approx(0.5)
        # t=1: is_ramping = (1 < 1) = False → 1.0
        assert ramp_multiplier(1, 2, RampShape.LINEAR) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Signal draws
# ---------------------------------------------------------------------------


class TestDrawQualitySignal:
    """Tests for draw_quality_signal (strategic quality observation y_t)."""

    def test_deterministic_with_fixed_rng(self):
        """Same seed and index produce the same quality signal draw."""
        pair_a = _make_rng_pair(world_seed=42, initiative_index=0)
        pair_b = _make_rng_pair(world_seed=42, initiative_index=0)

        y_a = draw_quality_signal(0.7, 0.1, pair_a.quality_signal_rng)
        y_b = draw_quality_signal(0.7, 0.1, pair_b.quality_signal_rng)
        assert y_a == pytest.approx(y_b)

    def test_different_seeds_produce_different_draws(self):
        """Different world seeds should produce different draws."""
        pair_a = _make_rng_pair(world_seed=42)
        pair_b = _make_rng_pair(world_seed=99)

        y_a = draw_quality_signal(0.7, 0.1, pair_a.quality_signal_rng)
        y_b = draw_quality_signal(0.7, 0.1, pair_b.quality_signal_rng)
        assert y_a != pytest.approx(y_b)

    def test_mean_converges_to_latent_quality(self):
        """Over many draws, the sample mean should converge to q."""
        pair = _make_rng_pair(world_seed=123)
        latent_quality = 0.65
        sigma = 0.1
        num_draws = 5000

        draws = [
            draw_quality_signal(latent_quality, sigma, pair.quality_signal_rng)
            for _ in range(num_draws)
        ]
        sample_mean = sum(draws) / len(draws)

        # With 5000 draws and σ=0.1, standard error ≈ 0.1/√5000 ≈ 0.0014.
        # A tolerance of 0.02 is ~14 standard errors — extremely safe.
        assert sample_mean == pytest.approx(latent_quality, abs=0.02)

    def test_zero_noise_returns_exact_quality(self):
        """With σ_eff = 0, the signal should equal latent quality exactly."""
        pair = _make_rng_pair(world_seed=42)
        y = draw_quality_signal(0.7, 0.0, pair.quality_signal_rng)
        assert y == pytest.approx(0.7)


class TestDrawExecutionSignal:
    """Tests for draw_execution_signal (execution progress observation z_t)."""

    def test_deterministic_with_fixed_rng(self):
        """Same seed and index produce the same execution signal draw."""
        pair_a = _make_rng_pair(world_seed=42)
        pair_b = _make_rng_pair(world_seed=42)

        z_a = draw_execution_signal(0.8, 0.15, pair_a.exec_signal_rng)
        z_b = draw_execution_signal(0.8, 0.15, pair_b.exec_signal_rng)
        assert z_a == pytest.approx(z_b)

    def test_mean_converges_to_latent_execution_fidelity(self):
        """Over many draws, the sample mean should converge to q_exec."""
        pair = _make_rng_pair(world_seed=456)
        latent_exec_fidelity = 0.75
        sigma_exec = 0.15
        num_draws = 5000

        draws = [
            draw_execution_signal(latent_exec_fidelity, sigma_exec, pair.exec_signal_rng)
            for _ in range(num_draws)
        ]
        sample_mean = sum(draws) / len(draws)
        assert sample_mean == pytest.approx(latent_exec_fidelity, abs=0.02)

    def test_uses_exec_rng_not_quality_rng(self):
        """Execution signal should use exec_signal_rng, not quality_signal_rng."""
        # Draw from quality RNG first to advance its state, then check
        # that exec draws are unaffected.
        pair_a = _make_rng_pair(world_seed=42)
        pair_b = _make_rng_pair(world_seed=42)

        # Advance pair_a's quality RNG but not pair_b's.
        draw_quality_signal(0.5, 0.1, pair_a.quality_signal_rng)

        # Both exec draws should still be identical because exec RNG
        # is independent of quality RNG.
        z_a = draw_execution_signal(0.8, 0.15, pair_a.exec_signal_rng)
        z_b = draw_execution_signal(0.8, 0.15, pair_b.exec_signal_rng)
        assert z_a == pytest.approx(z_b)


# ---------------------------------------------------------------------------
# Quality belief update
# ---------------------------------------------------------------------------


class TestUpdateQualityBelief:
    """Tests for the strategic quality belief update."""

    def test_belief_moves_toward_positive_signal(self):
        """When signal > belief, the updated belief should increase."""
        updated = update_quality_belief(
            quality_belief_t=0.5,
            quality_signal=0.8,  # y_t > c_t
            learning_rate=0.1,
            ramp_multiplier_value=1.0,
            learning_efficiency_value=1.0,
        )
        assert updated > 0.5

    def test_belief_moves_toward_negative_signal(self):
        """When signal < belief, the updated belief should decrease."""
        updated = update_quality_belief(
            quality_belief_t=0.5,
            quality_signal=0.2,  # y_t < c_t
            learning_rate=0.1,
            ramp_multiplier_value=1.0,
            learning_efficiency_value=1.0,
        )
        assert updated < 0.5

    def test_exact_update_formula(self):
        """Verify the exact formula: c + η * ramp * L * (y - c)."""
        updated = update_quality_belief(
            quality_belief_t=0.4,
            quality_signal=0.9,
            learning_rate=0.2,
            ramp_multiplier_value=0.5,
            learning_efficiency_value=0.8,
        )
        # c + η * ramp * L * (y - c)
        # = 0.4 + 0.2 * 0.5 * 0.8 * (0.9 - 0.4)
        # = 0.4 + 0.2 * 0.5 * 0.8 * 0.5
        # = 0.4 + 0.04
        # = 0.44
        assert updated == pytest.approx(0.44)

    def test_clamp_to_zero(self):
        """Updated belief should not go below 0.0."""
        updated = update_quality_belief(
            quality_belief_t=0.05,
            quality_signal=-5.0,  # extreme negative signal
            learning_rate=0.5,
            ramp_multiplier_value=1.0,
            learning_efficiency_value=1.0,
        )
        assert updated == pytest.approx(0.0)

    def test_clamp_to_one(self):
        """Updated belief should not exceed 1.0."""
        updated = update_quality_belief(
            quality_belief_t=0.95,
            quality_signal=5.0,  # extreme positive signal
            learning_rate=0.5,
            ramp_multiplier_value=1.0,
            learning_efficiency_value=1.0,
        )
        assert updated == pytest.approx(1.0)

    def test_zero_learning_rate_no_change(self):
        """With η=0, belief should not change regardless of signal."""
        updated = update_quality_belief(
            quality_belief_t=0.5,
            quality_signal=0.9,
            learning_rate=0.0,  # no learning
            ramp_multiplier_value=1.0,
            learning_efficiency_value=1.0,
        )
        assert updated == pytest.approx(0.5)

    def test_zero_ramp_multiplier_no_change(self):
        """With ramp=0 (hypothetical edge), belief should not change."""
        updated = update_quality_belief(
            quality_belief_t=0.5,
            quality_signal=0.9,
            learning_rate=0.1,
            ramp_multiplier_value=0.0,  # zero ramp
            learning_efficiency_value=1.0,
        )
        assert updated == pytest.approx(0.5)

    def test_zero_learning_efficiency_no_change(self):
        """With L(d)=0 (max dependency), belief should not change."""
        updated = update_quality_belief(
            quality_belief_t=0.5,
            quality_signal=0.9,
            learning_rate=0.1,
            ramp_multiplier_value=1.0,
            learning_efficiency_value=0.0,  # max dependency, no learning
        )
        assert updated == pytest.approx(0.5)

    def test_convergence_toward_q_over_many_ticks(self):
        """Over many ticks, belief should converge toward latent quality q.

        Simulates the full signal→update loop with pinned RNG to verify
        that the belief update mechanism drives quality_belief_t toward
        the latent quality value.
        """
        pair = _make_rng_pair(world_seed=789, initiative_index=0)
        latent_quality = 0.75
        sigma_eff = 0.1
        learning_rate = 0.15
        belief = 0.5  # start at neutral prior

        # Run 200 ticks of signal + update.
        for _ in range(200):
            y_t = draw_quality_signal(latent_quality, sigma_eff, pair.quality_signal_rng)
            belief = update_quality_belief(
                quality_belief_t=belief,
                quality_signal=y_t,
                learning_rate=learning_rate,
                ramp_multiplier_value=1.0,
                learning_efficiency_value=1.0,
            )

        # After 200 ticks with moderate noise, belief should be close to q.
        assert belief == pytest.approx(latent_quality, abs=0.1)

    def test_ramp_slows_convergence(self):
        """A low ramp multiplier should slow belief convergence."""
        # Same setup, but one run has ramp=0.2 (slow) and one has ramp=1.0.
        pair_fast = _make_rng_pair(world_seed=42, initiative_index=0)
        pair_slow = _make_rng_pair(world_seed=42, initiative_index=0)

        belief_fast = 0.5
        belief_slow = 0.5
        latent_quality = 0.8

        for _ in range(50):
            y_fast = draw_quality_signal(latent_quality, 0.1, pair_fast.quality_signal_rng)
            y_slow = draw_quality_signal(latent_quality, 0.1, pair_slow.quality_signal_rng)
            # Both see the same signal (same RNG), but different ramp.
            belief_fast = update_quality_belief(belief_fast, y_fast, 0.1, 1.0, 1.0)
            belief_slow = update_quality_belief(belief_slow, y_slow, 0.1, 0.2, 1.0)

        # Fast convergence should be closer to q than slow.
        error_fast = abs(belief_fast - latent_quality)
        error_slow = abs(belief_slow - latent_quality)
        assert error_fast < error_slow

    def test_dependency_slows_convergence(self):
        """Higher dependency (lower L(d)) should slow belief convergence."""
        pair_low = _make_rng_pair(world_seed=42, initiative_index=0)
        pair_high = _make_rng_pair(world_seed=42, initiative_index=0)

        belief_low_dep = 0.5  # L(d) = 1.0 (d = 0)
        belief_high_dep = 0.5  # L(d) = 0.3 (d = 0.7)
        latent_quality = 0.8

        for _ in range(50):
            y_low = draw_quality_signal(latent_quality, 0.1, pair_low.quality_signal_rng)
            y_high = draw_quality_signal(latent_quality, 0.1, pair_high.quality_signal_rng)
            belief_low_dep = update_quality_belief(
                belief_low_dep,
                y_low,
                0.1,
                1.0,
                learning_efficiency(0.0),  # L(0) = 1.0
            )
            belief_high_dep = update_quality_belief(
                belief_high_dep,
                y_high,
                0.1,
                1.0,
                learning_efficiency(0.7),  # L(0.7) = 0.3
            )

        error_low = abs(belief_low_dep - latent_quality)
        error_high = abs(belief_high_dep - latent_quality)
        assert error_low < error_high


# ---------------------------------------------------------------------------
# Execution belief update
# ---------------------------------------------------------------------------


class TestUpdateExecutionBelief:
    """Tests for the execution fidelity belief update."""

    def test_belief_moves_toward_signal(self):
        """When signal > belief, execution belief should increase."""
        updated = update_execution_belief(
            execution_belief_t=0.7,
            execution_signal=0.9,
            execution_learning_rate=0.1,
        )
        assert updated > 0.7

    def test_belief_moves_away_from_overrun_signal(self):
        """When signal < belief, execution belief should decrease."""
        updated = update_execution_belief(
            execution_belief_t=0.8,
            execution_signal=0.5,
            execution_learning_rate=0.1,
        )
        assert updated < 0.8

    def test_exact_formula(self):
        """Verify: c_exec + η_exec * (z - c_exec)."""
        updated = update_execution_belief(
            execution_belief_t=0.6,
            execution_signal=0.9,
            execution_learning_rate=0.2,
        )
        # 0.6 + 0.2 * (0.9 - 0.6) = 0.6 + 0.06 = 0.66
        assert updated == pytest.approx(0.66)

    def test_clamp_to_zero(self):
        """Execution belief should not go below 0.0."""
        updated = update_execution_belief(
            execution_belief_t=0.1,
            execution_signal=-5.0,
            execution_learning_rate=0.5,
        )
        assert updated == pytest.approx(0.0)

    def test_clamp_to_one(self):
        """Execution belief should not exceed 1.0."""
        updated = update_execution_belief(
            execution_belief_t=0.9,
            execution_signal=5.0,
            execution_learning_rate=0.5,
        )
        assert updated == pytest.approx(1.0)

    def test_not_modulated_by_dependency(self):
        """Execution belief update has no dependency modulation.

        Unlike quality belief, execution belief update uses only
        η_exec * (z - c_exec) with no L(d) or ramp multiplier terms.
        This test verifies the interface: the function takes no
        dependency or ramp parameters.
        """
        # The function signature itself enforces this — it has no
        # dependency_level or ramp_multiplier parameter. This test
        # simply confirms the update works with default parameters.
        updated = update_execution_belief(
            execution_belief_t=0.5,
            execution_signal=0.8,
            execution_learning_rate=0.1,
        )
        # 0.5 + 0.1 * (0.8 - 0.5) = 0.5 + 0.03 = 0.53
        assert updated == pytest.approx(0.53)

    def test_convergence_toward_q_exec_over_many_ticks(self):
        """Over many ticks, execution belief converges toward q_exec."""
        pair = _make_rng_pair(world_seed=321, initiative_index=0)
        latent_exec_fidelity = 0.6
        sigma_exec = 0.15
        belief = 1.0  # start at default planning prior

        for _ in range(200):
            z_t = draw_execution_signal(latent_exec_fidelity, sigma_exec, pair.exec_signal_rng)
            belief = update_execution_belief(
                execution_belief_t=belief,
                execution_signal=z_t,
                execution_learning_rate=0.15,
            )

        # After 200 ticks, belief should be close to q_exec.
        assert belief == pytest.approx(latent_exec_fidelity, abs=0.1)


# ---------------------------------------------------------------------------
# Integration: end-to-end signal-to-belief pipeline
# ---------------------------------------------------------------------------


class TestEndToEndSignalBeliefPipeline:
    """Integration tests combining g(a), σ_eff, signal draws, and belief updates."""

    def test_high_attention_faster_convergence(self):
        """Higher attention → lower noise → faster belief convergence.

        Runs two scenarios with identical RNG but different attention
        levels. High attention should produce more accurate signals
        and faster convergence.
        """
        latent_quality = 0.8
        base_sigma = 0.2
        dependency_level = 0.0
        alpha_d = 1.0
        portfolio_cap = 1.0

        # High attention: a = 0.8, low noise
        g_high = attention_noise_modifier(0.8, **_DEFAULT_G_PARAMS)
        sigma_high = effective_signal_st_dev_t(
            base_sigma, dependency_level, alpha_d, g_high, portfolio_cap
        )

        # Low attention: a = 0.05, high noise
        g_low = attention_noise_modifier(0.05, **_DEFAULT_G_PARAMS)
        sigma_low = effective_signal_st_dev_t(
            base_sigma, dependency_level, alpha_d, g_low, portfolio_cap
        )

        # Confirm high attention produces lower noise.
        assert sigma_high < sigma_low

        # Run belief updates with both noise levels.
        pair_high = _make_rng_pair(world_seed=42, initiative_index=0)
        pair_low = _make_rng_pair(world_seed=42, initiative_index=1)

        belief_high = 0.5
        belief_low = 0.5
        learning_rate = 0.1

        for _ in range(100):
            y_high = draw_quality_signal(
                latent_quality,
                sigma_high,
                pair_high.quality_signal_rng,
            )
            y_low = draw_quality_signal(
                latent_quality,
                sigma_low,
                pair_low.quality_signal_rng,
            )
            belief_high = update_quality_belief(belief_high, y_high, learning_rate, 1.0, 1.0)
            belief_low = update_quality_belief(belief_low, y_low, learning_rate, 1.0, 1.0)

        # High attention belief should be closer to q.
        error_high = abs(belief_high - latent_quality)
        error_low = abs(belief_low - latent_quality)
        assert error_high < error_low

    def test_full_pipeline_determinism(self):
        """The full pipeline is deterministic given the same RNG seed."""
        results = []
        for _ in range(2):
            pair = _make_rng_pair(world_seed=42, initiative_index=0)
            g_value = attention_noise_modifier(0.5, **_DEFAULT_G_PARAMS)
            sigma = effective_signal_st_dev_t(0.15, 0.2, 1.0, g_value, 1.0)
            belief = 0.5
            for _ in range(10):
                y_t = draw_quality_signal(0.7, sigma, pair.quality_signal_rng)
                belief = update_quality_belief(
                    belief,
                    y_t,
                    0.1,
                    1.0,
                    learning_efficiency(0.2),
                )
            results.append(belief)

        assert results[0] == pytest.approx(results[1])
