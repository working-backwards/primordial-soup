"""Tests for pool.py — initiative pool generator.

Tests verify:
    - Determinism (same seed → same pool)
    - Correct count of initiatives per type spec
    - Attribute ranges honored
    - Generator invariants enforced (residual-on-completion,
      capability-on-completion)
    - initiative_id sequential ordering
    - generation_tag propagated
    - major_win threshold correctly applied
    - Value channels correctly built
    - Pre-built RNG path works
    - Multiple type specs compose correctly
"""

from __future__ import annotations

import pytest

from primordial_soup.config import (
    InitiativeGeneratorConfig,
    InitiativeTypeSpec,
)
from primordial_soup.noise import create_pool_rng
from primordial_soup.pool import generate_initiative_pool
from primordial_soup.types import (
    BetaDistribution,
    LogNormalDistribution,
)

# ---------------------------------------------------------------------------
# Factory helpers for test InitiativeTypeSpecs
# ---------------------------------------------------------------------------


def make_flywheel_spec(
    *,
    count: int = 3,
    true_duration_range: tuple[int, int] = (20, 60),
    planned_duration_range: tuple[int, int] = (15, 50),
) -> InitiativeTypeSpec:
    """Build a canonical flywheel type spec for testing.

    Flywheels: high-quality beta, low noise, low dependency,
    residual-on-completion with slow decay, long duration.
    """
    return InitiativeTypeSpec(
        generation_tag="flywheel",
        count=count,
        quality_distribution=BetaDistribution(alpha=8.0, beta=2.0),
        base_signal_st_dev_range=(0.05, 0.15),
        dependency_level_range=(0.1, 0.4),
        true_duration_range=true_duration_range,
        planned_duration_range=planned_duration_range,
        residual_enabled=True,
        residual_activation_state="completed",
        residual_rate_range=(0.5, 2.0),
        residual_decay_range=(0.01, 0.05),
    )


def make_right_tail_spec(
    *,
    count: int = 2,
    q_major_win_threshold: float = 0.7,
) -> InitiativeTypeSpec:
    """Build a canonical right-tail type spec for testing.

    Right-tails: right-skewed quality, high noise, moderate-high
    dependency, major_win_event enabled, observable ceiling.
    """
    return InitiativeTypeSpec(
        generation_tag="right-tail",
        count=count,
        quality_distribution=BetaDistribution(alpha=2.0, beta=8.0),
        base_signal_st_dev_range=(0.20, 0.40),
        dependency_level_range=(0.2, 0.6),
        true_duration_range=(20, 80),
        planned_duration_range=(15, 60),
        major_win_event_enabled=True,
        q_major_win_threshold=q_major_win_threshold,
        observable_ceiling_distribution=LogNormalDistribution(mean=4.0, st_dev=0.5),
    )


def make_enabler_spec(*, count: int = 2) -> InitiativeTypeSpec:
    """Build a canonical enabler type spec for testing.

    Enablers: moderate quality, low noise, low dependency,
    capability_contribution_scale > 0, no residual.
    """
    return InitiativeTypeSpec(
        generation_tag="enabler",
        count=count,
        quality_distribution=BetaDistribution(alpha=5.0, beta=5.0),
        base_signal_st_dev_range=(0.05, 0.20),
        dependency_level_range=(0.0, 0.2),
        true_duration_range=(10, 30),
        planned_duration_range=(8, 25),
        capability_contribution_scale_range=(0.5, 2.0),
    )


def make_quick_win_spec(*, count: int = 3) -> InitiativeTypeSpec:
    """Build a canonical quick-win type spec for testing.

    Quick-wins: moderate-to-high quality, low noise, low dependency,
    residual-on-completion with high decay, short duration.
    """
    return InitiativeTypeSpec(
        generation_tag="quick-win",
        count=count,
        quality_distribution=BetaDistribution(alpha=6.0, beta=3.0),
        base_signal_st_dev_range=(0.05, 0.15),
        dependency_level_range=(0.0, 0.2),
        true_duration_range=(3, 10),
        planned_duration_range=(3, 8),
        residual_enabled=True,
        residual_activation_state="completed",
        residual_rate_range=(0.1, 0.5),
        residual_decay_range=(0.3, 0.8),
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Pool generation must be deterministic given the same seed."""

    def test_same_seed_same_pool(self):
        """Identical world_seed must produce identical initiative pools."""
        config = InitiativeGeneratorConfig(
            type_specs=(make_flywheel_spec(), make_quick_win_spec())
        )
        pool_a = generate_initiative_pool(config, world_seed=42)
        pool_b = generate_initiative_pool(config, world_seed=42)

        assert len(pool_a) == len(pool_b)
        for init_a, init_b in zip(pool_a, pool_b, strict=True):
            assert init_a == init_b

    def test_different_seeds_different_pools(self):
        """Different world_seeds must produce different pools."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(),))
        pool_a = generate_initiative_pool(config, world_seed=42)
        pool_b = generate_initiative_pool(config, world_seed=99)

        # At least one attribute should differ
        any_differ = False
        for init_a, init_b in zip(pool_a, pool_b, strict=True):
            if init_a.latent_quality != init_b.latent_quality:
                any_differ = True
                break
        assert any_differ

    def test_pre_built_rng_determinism(self):
        """Pre-built pool RNG should produce deterministic results."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=2),))
        rng_a = create_pool_rng(world_seed=42)
        rng_b = create_pool_rng(world_seed=42)

        pool_a = generate_initiative_pool(config, pool_rng=rng_a)
        pool_b = generate_initiative_pool(config, pool_rng=rng_b)

        for init_a, init_b in zip(pool_a, pool_b, strict=True):
            assert init_a == init_b


# ---------------------------------------------------------------------------
# Initiative count and ordering
# ---------------------------------------------------------------------------


class TestCountAndOrdering:
    """Tests for initiative count, ID ordering, and type composition."""

    def test_correct_total_count(self):
        """Total initiatives must equal sum of all type spec counts."""
        config = InitiativeGeneratorConfig(
            type_specs=(
                make_flywheel_spec(count=3),
                make_right_tail_spec(count=2),
                make_enabler_spec(count=2),
                make_quick_win_spec(count=3),
            )
        )
        pool = generate_initiative_pool(config, world_seed=42)
        assert len(pool) == 3 + 2 + 2 + 3

    def test_sequential_initiative_ids(self):
        """Initiative IDs must be sequential: init-0, init-1, ..."""
        config = InitiativeGeneratorConfig(
            type_specs=(
                make_flywheel_spec(count=2),
                make_quick_win_spec(count=3),
            )
        )
        pool = generate_initiative_pool(config, world_seed=42)
        expected_ids = [f"init-{i}" for i in range(5)]
        actual_ids = [init.initiative_id for init in pool]
        assert actual_ids == expected_ids

    def test_generation_tag_propagated(self):
        """Each initiative's generation_tag must match its type spec."""
        config = InitiativeGeneratorConfig(
            type_specs=(
                make_flywheel_spec(count=2),
                make_right_tail_spec(count=1),
            )
        )
        pool = generate_initiative_pool(config, world_seed=42)

        assert pool[0].generation_tag == "flywheel"
        assert pool[1].generation_tag == "flywheel"
        assert pool[2].generation_tag == "right-tail"

    def test_empty_type_spec(self):
        """A type spec with count=0 should produce no initiatives."""
        config = InitiativeGeneratorConfig(
            type_specs=(
                make_flywheel_spec(count=0),
                make_quick_win_spec(count=2),
            )
        )
        pool = generate_initiative_pool(config, world_seed=42)
        assert len(pool) == 2
        assert all(init.generation_tag == "quick-win" for init in pool)

    def test_single_type_single_initiative(self):
        """Minimal pool: one type, one initiative."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=1),))
        pool = generate_initiative_pool(config, world_seed=42)
        assert len(pool) == 1
        assert pool[0].initiative_id == "init-0"


# ---------------------------------------------------------------------------
# Attribute ranges
# ---------------------------------------------------------------------------


class TestAttributeRanges:
    """Tests that drawn attributes respect the specified ranges."""

    def test_latent_quality_in_zero_one(self):
        """Quality drawn from Beta must be in [0, 1]."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=20),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert 0.0 <= init.latent_quality <= 1.0

    def test_base_signal_st_dev_in_range(self):
        """base_signal_st_dev must be within the type spec's range."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=20),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert 0.05 <= init.base_signal_st_dev <= 0.15

    def test_dependency_level_in_range(self):
        """dependency_level must be within the type spec's range."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=20),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert 0.1 <= init.dependency_level <= 0.4

    def test_true_duration_ticks_in_range(self):
        """true_duration_ticks must be within the type spec's range."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=20),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert init.true_duration_ticks is not None
            assert 20 <= init.true_duration_ticks <= 60

    def test_planned_duration_ticks_in_range(self):
        """planned_duration_ticks must be within the type spec's range."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=20),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert init.planned_duration_ticks is not None
            assert 15 <= init.planned_duration_ticks <= 50

    def test_no_duration_when_range_not_set(self):
        """When true_duration_range is None, true_duration_ticks should be None."""
        # Right-tail spec has duration set; use a custom spec without it.
        spec = InitiativeTypeSpec(
            generation_tag="no-duration",
            count=5,
            quality_distribution=BetaDistribution(alpha=3.0, beta=3.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.1, 0.3),
            # Explicitly no duration ranges, no residual, no capability
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert init.true_duration_ticks is None
            assert init.planned_duration_ticks is None

    def test_observable_ceiling_positive(self):
        """Observable ceiling drawn from LogNormal should be positive."""
        config = InitiativeGeneratorConfig(type_specs=(make_right_tail_spec(count=20),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert init.observable_ceiling is not None
            assert init.observable_ceiling > 0.0

    def test_capability_contribution_scale_in_range(self):
        """capability_contribution_scale must be in the spec's range."""
        config = InitiativeGeneratorConfig(type_specs=(make_enabler_spec(count=20),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert 0.5 <= init.capability_contribution_scale <= 2.0


# ---------------------------------------------------------------------------
# Value channels
# ---------------------------------------------------------------------------


class TestValueChannels:
    """Tests for value channel construction from type specs."""

    def test_flywheel_residual_enabled(self):
        """Flywheel initiatives must have residual channel enabled."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=3),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert init.value_channels.residual.enabled is True
            assert init.value_channels.residual.activation_state == "completed"
            assert init.value_channels.residual.residual_rate > 0.0
            assert init.value_channels.residual.residual_decay >= 0.0

    def test_right_tail_major_win_enabled(self):
        """Right-tail initiatives must have major_win_event enabled."""
        config = InitiativeGeneratorConfig(type_specs=(make_right_tail_spec(count=5),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert init.value_channels.major_win_event.enabled is True

    def test_enabler_no_residual(self):
        """Enabler initiatives must have residual channel disabled."""
        config = InitiativeGeneratorConfig(type_specs=(make_enabler_spec(count=3),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert init.value_channels.residual.enabled is False
            assert init.capability_contribution_scale > 0.0

    def test_quick_win_residual_high_decay(self):
        """Quick-win residual must have high decay (within range)."""
        config = InitiativeGeneratorConfig(type_specs=(make_quick_win_spec(count=10),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert init.value_channels.residual.enabled is True
            assert 0.3 <= init.value_channels.residual.residual_decay <= 0.8

    def test_completion_lump_when_enabled(self):
        """Completion lump value must be drawn when enabled."""
        spec = InitiativeTypeSpec(
            generation_tag="lump-test",
            count=5,
            quality_distribution=BetaDistribution(alpha=5.0, beta=5.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.1, 0.3),
            completion_lump_enabled=True,
            completion_lump_value_range=(10.0, 100.0),
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert init.value_channels.completion_lump.enabled is True
            assert init.value_channels.completion_lump.realized_value is not None
            assert 10.0 <= init.value_channels.completion_lump.realized_value <= 100.0


# ---------------------------------------------------------------------------
# Major-win threshold
# ---------------------------------------------------------------------------


class TestMajorWinThreshold:
    """Tests for the is_major_win generation rule."""

    def test_major_win_threshold_applied_correctly(self):
        """is_major_win must be True iff latent_quality >= threshold.

        Per sourcing_and_generation.md: is_major_win = (q >= q_major_win_threshold).
        """
        config = InitiativeGeneratorConfig(
            type_specs=(make_right_tail_spec(count=50, q_major_win_threshold=0.3),)
        )
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            expected = init.latent_quality >= 0.3
            actual = init.value_channels.major_win_event.is_major_win
            assert actual == expected, (
                f"init={init.initiative_id}: q={init.latent_quality:.4f}, "
                f"expected is_major_win={expected}, got {actual}"
            )

    def test_major_win_disabled_never_true(self):
        """When major_win_event is disabled, is_major_win must be False."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=10),))
        pool = generate_initiative_pool(config, world_seed=42)
        for init in pool:
            assert init.value_channels.major_win_event.enabled is False
            assert init.value_channels.major_win_event.is_major_win is False


# ---------------------------------------------------------------------------
# Generator invariants
# ---------------------------------------------------------------------------


class TestGeneratorInvariants:
    """Tests for generator construction invariants."""

    def test_residual_on_completion_requires_duration(self):
        """Residual with activation_state='completed' must have
        true_duration_ticks set. Generator must raise ValueError.
        """
        spec = InitiativeTypeSpec(
            generation_tag="bad-residual",
            count=1,
            quality_distribution=BetaDistribution(alpha=5.0, beta=5.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.1, 0.3),
            # No true_duration_range → true_duration_ticks will be None
            residual_enabled=True,
            residual_activation_state="completed",
            residual_rate_range=(0.5, 1.0),
            residual_decay_range=(0.01, 0.05),
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        with pytest.raises(ValueError, match="residual.*requires true_duration_ticks"):
            generate_initiative_pool(config, world_seed=42)

    def test_capability_on_completion_requires_duration(self):
        """capability_contribution_scale > 0 must have true_duration_ticks.
        Generator must raise ValueError.
        """
        spec = InitiativeTypeSpec(
            generation_tag="bad-enabler",
            count=1,
            quality_distribution=BetaDistribution(alpha=5.0, beta=5.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.1, 0.3),
            # No true_duration_range → true_duration_ticks will be None
            capability_contribution_scale_range=(0.5, 2.0),
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        with pytest.raises(
            ValueError,
            match="capability_contribution_scale.*requires true_duration_ticks",
        ):
            generate_initiative_pool(config, world_seed=42)

    def test_residual_without_duration_ok_when_not_completion_gated(self):
        """Residual not gated on 'completed' should not require duration."""
        spec = InitiativeTypeSpec(
            generation_tag="non-completion-residual",
            count=1,
            quality_distribution=BetaDistribution(alpha=5.0, beta=5.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.1, 0.3),
            # No true_duration_range → true_duration_ticks will be None
            residual_enabled=True,
            residual_activation_state="active",  # Not "completed"
            residual_rate_range=(0.5, 1.0),
            residual_decay_range=(0.01, 0.05),
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        # Should NOT raise — activation_state is not "completed"
        pool = generate_initiative_pool(config, world_seed=42)
        assert len(pool) == 1

    def test_zero_capability_without_duration_ok(self):
        """Zero capability_contribution_scale should not require duration."""
        spec = InitiativeTypeSpec(
            generation_tag="no-enabler",
            count=1,
            quality_distribution=BetaDistribution(alpha=5.0, beta=5.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.1, 0.3),
            # No duration, no capability → should be fine
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool = generate_initiative_pool(config, world_seed=42)
        assert len(pool) == 1
        assert pool[0].capability_contribution_scale == 0.0


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestDefaults:
    """Tests for default field values on generated initiatives."""

    def test_initial_quality_belief_is_none(self):
        """initial_quality_belief should be None (use ModelConfig default)."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=1),))
        pool = generate_initiative_pool(config, world_seed=42)
        assert pool[0].initial_quality_belief is None

    def test_initial_execution_belief_default(self):
        """initial_execution_belief should be 1.0 (default)."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=1),))
        pool = generate_initiative_pool(config, world_seed=42)
        assert pool[0].initial_execution_belief == 1.0

    def test_required_team_size_default(self):
        """required_team_size should be 1 (default)."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=1),))
        pool = generate_initiative_pool(config, world_seed=42)
        assert pool[0].required_team_size == 1

    def test_created_tick_default(self):
        """created_tick should be 0 (default)."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=1),))
        pool = generate_initiative_pool(config, world_seed=42)
        assert pool[0].created_tick == 0


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    """Tests for error handling in generate_initiative_pool."""

    def test_neither_seed_nor_rng_raises(self):
        """Must raise ValueError when neither world_seed nor pool_rng."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=1),))
        with pytest.raises(ValueError, match="Exactly one"):
            generate_initiative_pool(config)

    def test_both_seed_and_rng_raises(self):
        """Must raise ValueError when both world_seed and pool_rng."""
        config = InitiativeGeneratorConfig(type_specs=(make_flywheel_spec(count=1),))
        rng = create_pool_rng(world_seed=42)
        with pytest.raises(ValueError, match="Exactly one"):
            generate_initiative_pool(config, world_seed=42, pool_rng=rng)


# ---------------------------------------------------------------------------
# Mixed type specs (integration)
# ---------------------------------------------------------------------------


class TestMixedTypeSpecs:
    """Integration test: canonical four-type pool generation."""

    def test_canonical_four_type_pool(self):
        """Generate a pool with all four canonical initiative types."""
        config = InitiativeGeneratorConfig(
            type_specs=(
                make_flywheel_spec(count=3),
                make_right_tail_spec(count=2),
                make_enabler_spec(count=2),
                make_quick_win_spec(count=3),
            )
        )
        pool = generate_initiative_pool(config, world_seed=42)

        # Total count
        assert len(pool) == 10

        # ID ordering
        assert [init.initiative_id for init in pool] == [f"init-{i}" for i in range(10)]

        # Tag ordering: 3 flywheel, 2 right-tail, 2 enabler, 3 quick-win
        tags = [init.generation_tag for init in pool]
        assert tags[:3] == ["flywheel"] * 3
        assert tags[3:5] == ["right-tail"] * 2
        assert tags[5:7] == ["enabler"] * 2
        assert tags[7:] == ["quick-win"] * 3

        # Flywheel: residual enabled, no major_win
        for init in pool[:3]:
            assert init.value_channels.residual.enabled is True
            assert init.value_channels.major_win_event.enabled is False

        # Right-tail: major_win enabled, observable ceiling set
        for init in pool[3:5]:
            assert init.value_channels.major_win_event.enabled is True
            assert init.observable_ceiling is not None

        # Enabler: capability > 0, no residual
        for init in pool[5:7]:
            assert init.capability_contribution_scale > 0.0
            assert init.value_channels.residual.enabled is False

        # Quick-win: residual with high decay, short duration
        for init in pool[7:]:
            assert init.value_channels.residual.enabled is True
            assert init.true_duration_ticks is not None
            assert init.true_duration_ticks <= 10


class TestStaffingResponseScaleGeneration:
    """Tests for staffing_response_scale propagation through pool generation."""

    def test_none_range_produces_zero_scale(self):
        """When staffing_response_scale_range is None, generated initiatives
        get the default staffing_response_scale of 0.0.

        This is the backward compatibility path: existing type specs that
        do not specify a range produce initiatives that behave identically
        to before the staffing intensity feature was added.
        """
        type_spec = InitiativeTypeSpec(
            generation_tag="test",
            count=5,
            quality_distribution=BetaDistribution(alpha=5.0, beta=3.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            true_duration_range=(5, 10),
            planned_duration_range=(6, 12),
            # staffing_response_scale_range is None (default)
        )
        gen_config = InitiativeGeneratorConfig(type_specs=(type_spec,))
        pool = generate_initiative_pool(gen_config, world_seed=42)

        for init in pool:
            assert init.staffing_response_scale == 0.0

    def test_range_produces_values_within_bounds(self):
        """When staffing_response_scale_range is provided, generated values
        are drawn uniformly within the specified range.
        """
        type_spec = InitiativeTypeSpec(
            generation_tag="test",
            count=20,
            quality_distribution=BetaDistribution(alpha=5.0, beta=3.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            true_duration_range=(5, 10),
            planned_duration_range=(6, 12),
            staffing_response_scale_range=(0.5, 2.0),
        )
        gen_config = InitiativeGeneratorConfig(type_specs=(type_spec,))
        pool = generate_initiative_pool(gen_config, world_seed=42)

        for init in pool:
            assert 0.5 <= init.staffing_response_scale <= 2.0

        # With 20 draws, not all should be identical (regression check).
        unique_values = {init.staffing_response_scale for init in pool}
        assert len(unique_values) > 1

    def test_deterministic_with_same_seed(self):
        """Same seed produces the same staffing_response_scale values."""
        type_spec = InitiativeTypeSpec(
            generation_tag="test",
            count=5,
            quality_distribution=BetaDistribution(alpha=5.0, beta=3.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            true_duration_range=(5, 10),
            planned_duration_range=(6, 12),
            staffing_response_scale_range=(0.5, 2.0),
        )
        gen_config = InitiativeGeneratorConfig(type_specs=(type_spec,))
        pool_a = generate_initiative_pool(gen_config, world_seed=42)
        pool_b = generate_initiative_pool(gen_config, world_seed=42)

        for a, b in zip(pool_a, pool_b, strict=True):
            assert a.staffing_response_scale == b.staffing_response_scale


# ---------------------------------------------------------------------------
# Screening signal (ex ante intake evaluation)
# ---------------------------------------------------------------------------


class TestScreeningSignal:
    """Tests for the screening signal mechanism (post_expert_review_plan Step 3).

    When screening_signal_st_dev is set on a type spec, the generator draws
    a noisy screening signal correlated with latent quality:
        screening_signal = clamp(q + Normal(0, sigma_screen), 0, 1)
        initial_quality_belief = screening_signal
    """

    def test_none_screening_preserves_default_behavior(self):
        """When screening_signal_st_dev is None, initial_quality_belief is None.

        This preserves backward compatibility: the runner will use
        ModelConfig.default_initial_quality_belief (0.5).
        """
        spec = InitiativeTypeSpec(
            generation_tag="test_no_screen",
            count=10,
            quality_distribution=BetaDistribution(alpha=5.0, beta=2.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            screening_signal_st_dev=None,  # Explicitly None
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool = generate_initiative_pool(config, world_seed=99)

        for init in pool:
            assert init.initial_quality_belief is None

    def test_screening_sets_initial_quality_belief(self):
        """When screening_signal_st_dev is set, initial_quality_belief is not None."""
        spec = InitiativeTypeSpec(
            generation_tag="test_screen",
            count=20,
            quality_distribution=BetaDistribution(alpha=5.0, beta=2.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            screening_signal_st_dev=0.15,
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool = generate_initiative_pool(config, world_seed=42)

        for init in pool:
            assert init.initial_quality_belief is not None
            # Belief must be clamped to [0, 1].
            assert 0.0 <= init.initial_quality_belief <= 1.0

    def test_screening_beliefs_bounded_zero_one(self):
        """Screening signal is clamped to [0, 1] even with extreme noise."""
        # Very high noise — some draws should hit the clamp boundaries.
        spec = InitiativeTypeSpec(
            generation_tag="test_extreme",
            count=100,
            quality_distribution=BetaDistribution(alpha=1.0, beta=1.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            screening_signal_st_dev=5.0,  # Extreme noise
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool = generate_initiative_pool(config, world_seed=77)

        for init in pool:
            assert init.initial_quality_belief is not None
            assert 0.0 <= init.initial_quality_belief <= 1.0

    def test_low_noise_beliefs_close_to_quality(self):
        """With very low screening noise, beliefs should track true quality.

        Uses enough draws for the law of large numbers to hold.
        """
        spec = InitiativeTypeSpec(
            generation_tag="test_precise",
            count=200,
            quality_distribution=BetaDistribution(alpha=5.0, beta=2.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            screening_signal_st_dev=0.001,  # Very precise screening
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool = generate_initiative_pool(config, world_seed=42)

        # With sigma_screen=0.001, beliefs should be very close to quality.
        errors = [abs(init.initial_quality_belief - init.latent_quality) for init in pool]
        mean_error = sum(errors) / len(errors)
        # Mean absolute error should be negligible (well under 0.01).
        assert mean_error < 0.01

    def test_high_noise_beliefs_differ_from_quality(self):
        """With high screening noise, beliefs should diverge from quality.

        The mean absolute error should be meaningfully larger than with
        low noise, confirming the noise mechanism is working.
        """
        spec = InitiativeTypeSpec(
            generation_tag="test_noisy",
            count=200,
            quality_distribution=BetaDistribution(alpha=5.0, beta=2.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            screening_signal_st_dev=0.30,  # High noise
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool = generate_initiative_pool(config, world_seed=42)

        errors = [abs(init.initial_quality_belief - init.latent_quality) for init in pool]
        mean_error = sum(errors) / len(errors)
        # Mean absolute error should be substantial with sigma=0.30.
        assert mean_error > 0.05

    def test_screening_deterministic_same_seed(self):
        """Screening signal draws must be deterministic given the same seed."""
        spec = InitiativeTypeSpec(
            generation_tag="test_det",
            count=10,
            quality_distribution=BetaDistribution(alpha=5.0, beta=2.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            screening_signal_st_dev=0.20,
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool_a = generate_initiative_pool(config, world_seed=42)
        pool_b = generate_initiative_pool(config, world_seed=42)

        for a, b in zip(pool_a, pool_b, strict=True):
            assert a.initial_quality_belief == b.initial_quality_belief

    def test_screening_varies_across_seeds(self):
        """Different seeds should produce different screening signals."""
        spec = InitiativeTypeSpec(
            generation_tag="test_vary",
            count=5,
            quality_distribution=BetaDistribution(alpha=5.0, beta=2.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            screening_signal_st_dev=0.20,
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool_a = generate_initiative_pool(config, world_seed=42)
        pool_b = generate_initiative_pool(config, world_seed=99)

        # At least one initiative should have a different belief.
        any_different = any(
            a.initial_quality_belief != b.initial_quality_belief
            for a, b in zip(pool_a, pool_b, strict=True)
        )
        assert any_different

    def test_screening_beliefs_are_differentiated(self):
        """Screening should produce non-uniform initial beliefs.

        With screening enabled, initiatives should start with different
        beliefs reflecting their different latent qualities + noise.
        """
        spec = InitiativeTypeSpec(
            generation_tag="test_diff",
            count=20,
            quality_distribution=BetaDistribution(alpha=2.0, beta=2.0),
            base_signal_st_dev_range=(0.1, 0.2),
            dependency_level_range=(0.0, 0.3),
            screening_signal_st_dev=0.15,
        )
        config = InitiativeGeneratorConfig(type_specs=(spec,))
        pool = generate_initiative_pool(config, world_seed=42)

        beliefs = [init.initial_quality_belief for init in pool]
        # With 20 draws from a Beta(2,2) + Normal noise, beliefs should
        # not all be the same value.
        unique_beliefs = set(beliefs)
        assert len(unique_beliefs) > 1
