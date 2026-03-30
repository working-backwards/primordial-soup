"""Tests for noise.py — MRG32k3a CRN stream construction and variate helpers.

Tests verify:
    - Seed derivation determinism and validity
    - Pool RNG determinism
    - Initiative RNG pair determinism
    - CRN isolation: different initiatives get independent substreams
    - CRN regime independence: stopping one initiative doesn't affect
      another's draws
    - Variate helpers produce values in expected ranges
    - draw_from_distribution dispatches correctly on DistributionSpec types
    - Error cases (missing seed, negative index, etc.)
    - Pre-built RNG path works
"""

from __future__ import annotations

import pytest

from primordial_soup.noise import (
    InitiativeRngPair,
    SimulationRng,
    create_all_initiative_rngs,
    create_initiative_rng_pair,
    create_pool_rng,
    derive_ref_seed,
    draw_beta,
    draw_from_distribution,
    draw_lognormal,
    draw_normal,
    draw_uniform,
    draw_uniform_int,
)
from primordial_soup.types import (
    BetaDistribution,
    LogNormalDistribution,
    UniformDistribution,
)

# ---------------------------------------------------------------------------
# Seed derivation
# ---------------------------------------------------------------------------


class TestDeriveRefSeed:
    """Tests for derive_ref_seed."""

    def test_determinism_same_seed_same_output(self):
        """Same world_seed must always produce the same ref_seed."""
        seed_a = derive_ref_seed(42)
        seed_b = derive_ref_seed(42)
        assert seed_a == seed_b

    def test_different_seeds_produce_different_output(self):
        """Different world_seeds must produce different ref_seeds."""
        seed_a = derive_ref_seed(42)
        seed_b = derive_ref_seed(99)
        assert seed_a != seed_b

    def test_output_is_6_tuple_of_ints(self):
        """ref_seed must be a 6-tuple of integers."""
        seed = derive_ref_seed(12345)
        assert isinstance(seed, tuple)
        assert len(seed) == 6
        assert all(isinstance(c, int) for c in seed)

    def test_components_within_modulus_range(self):
        """Each component must be within the MRG32k3a modulus range."""
        # m1 = 4294967087, m2 = 4294944443
        m1 = 4294967087
        m2 = 4294944443
        for world_seed in [0, 1, 42, 2**63 - 1, -1, -9999]:
            seed = derive_ref_seed(world_seed)
            # First three components: [0, m1)
            for component in seed[:3]:
                assert 0 <= component < m1
            # Last three components: [0, m2)
            for component in seed[3:]:
                assert 0 <= component < m2

    def test_at_least_one_nonzero_per_triple(self):
        """Each triple of seed components must have at least one nonzero."""
        for world_seed in [0, 1, 42, 999999]:
            seed = derive_ref_seed(world_seed)
            assert any(
                c != 0 for c in seed[:3]
            ), f"First triple all zeros for world_seed={world_seed}"
            assert any(
                c != 0 for c in seed[3:]
            ), f"Second triple all zeros for world_seed={world_seed}"

    def test_large_and_negative_seeds(self):
        """derive_ref_seed should handle large and negative integers."""
        # Should not raise
        derive_ref_seed(2**64)
        derive_ref_seed(-1)
        derive_ref_seed(0)


# ---------------------------------------------------------------------------
# Pool RNG creation
# ---------------------------------------------------------------------------


class TestCreatePoolRng:
    """Tests for create_pool_rng."""

    def test_determinism(self):
        """Same world_seed produces identical pool RNG draw sequences."""
        rng_a = create_pool_rng(world_seed=42)
        rng_b = create_pool_rng(world_seed=42)
        draws_a = [rng_a.random() for _ in range(10)]
        draws_b = [rng_b.random() for _ in range(10)]
        assert draws_a == draws_b

    def test_different_seeds_different_draws(self):
        """Different world_seeds produce different pool RNG draw sequences."""
        rng_a = create_pool_rng(world_seed=42)
        rng_b = create_pool_rng(world_seed=99)
        draws_a = [rng_a.random() for _ in range(10)]
        draws_b = [rng_b.random() for _ in range(10)]
        assert draws_a != draws_b

    def test_returns_simulation_rng(self):
        """create_pool_rng must return a SimulationRng instance."""
        rng = create_pool_rng(world_seed=42)
        assert isinstance(rng, SimulationRng)

    def test_pre_built_rng_passthrough(self):
        """When pre_built_rng is provided, it should be returned directly."""
        from mrg32k3a.mrg32k3a import MRG32k3a

        pre_built = MRG32k3a()
        result = create_pool_rng(pre_built_rng=pre_built)
        assert result is pre_built

    def test_error_when_neither_provided(self):
        """Must raise ValueError when neither world_seed nor pre_built_rng."""
        with pytest.raises(ValueError, match="Exactly one"):
            create_pool_rng()

    def test_error_when_both_provided(self):
        """Must raise ValueError when both world_seed and pre_built_rng."""
        from mrg32k3a.mrg32k3a import MRG32k3a

        with pytest.raises(ValueError, match="Exactly one"):
            create_pool_rng(world_seed=42, pre_built_rng=MRG32k3a())


# ---------------------------------------------------------------------------
# Initiative RNG pair creation
# ---------------------------------------------------------------------------


class TestCreateInitiativeRngPair:
    """Tests for create_initiative_rng_pair."""

    def test_determinism(self):
        """Same world_seed and initiative_index produce identical RNG pairs."""
        pair_a = create_initiative_rng_pair(world_seed=42, initiative_index=0)
        pair_b = create_initiative_rng_pair(world_seed=42, initiative_index=0)

        draws_a = [pair_a.quality_signal_rng.random() for _ in range(5)]
        draws_b = [pair_b.quality_signal_rng.random() for _ in range(5)]
        assert draws_a == draws_b

        # Reset exec RNG check
        pair_c = create_initiative_rng_pair(world_seed=42, initiative_index=0)
        pair_d = create_initiative_rng_pair(world_seed=42, initiative_index=0)
        exec_a = [pair_c.exec_signal_rng.random() for _ in range(5)]
        exec_b = [pair_d.exec_signal_rng.random() for _ in range(5)]
        assert exec_a == exec_b

    def test_returns_initiative_rng_pair(self):
        """Must return an InitiativeRngPair dataclass."""
        pair = create_initiative_rng_pair(world_seed=42, initiative_index=0)
        assert isinstance(pair, InitiativeRngPair)
        assert isinstance(pair.quality_signal_rng, SimulationRng)
        assert isinstance(pair.exec_signal_rng, SimulationRng)

    def test_quality_and_exec_are_independent(self):
        """Quality and exec RNGs for the same initiative must differ."""
        pair = create_initiative_rng_pair(world_seed=42, initiative_index=0)
        quality_draws = [pair.quality_signal_rng.random() for _ in range(10)]
        exec_draws = [pair.exec_signal_rng.random() for _ in range(10)]
        # Different substreams, so draws must differ
        assert quality_draws != exec_draws

    def test_different_initiatives_independent(self):
        """Different initiative indices produce different RNG streams."""
        pair_0 = create_initiative_rng_pair(world_seed=42, initiative_index=0)
        pair_1 = create_initiative_rng_pair(world_seed=42, initiative_index=1)

        draws_0 = [pair_0.quality_signal_rng.random() for _ in range(10)]
        draws_1 = [pair_1.quality_signal_rng.random() for _ in range(10)]
        assert draws_0 != draws_1

    def test_pool_rng_independent_from_initiative_rngs(self):
        """Pool RNG must not overlap with any initiative's RNG substream."""
        pool_rng = create_pool_rng(world_seed=42)
        pair_0 = create_initiative_rng_pair(world_seed=42, initiative_index=0)

        pool_draws = [pool_rng.random() for _ in range(10)]
        quality_draws = [pair_0.quality_signal_rng.random() for _ in range(10)]
        assert pool_draws != quality_draws

    def test_negative_index_raises(self):
        """Negative initiative_index must raise ValueError."""
        with pytest.raises(ValueError, match="initiative_index must be >= 0"):
            create_initiative_rng_pair(world_seed=42, initiative_index=-1)

    def test_pre_built_rng_passthrough(self):
        """Pre-built RNG pair should be returned directly."""
        from mrg32k3a.mrg32k3a import MRG32k3a

        q_rng = MRG32k3a()
        e_rng = MRG32k3a(s_ss_sss_index=[0, 1, 0])
        pair = create_initiative_rng_pair(
            pre_built_quality_rng=q_rng,
            pre_built_exec_rng=e_rng,
            initiative_index=0,
        )
        assert pair.quality_signal_rng is q_rng
        assert pair.exec_signal_rng is e_rng

    def test_error_partial_pre_built_quality_only(self):
        """Must raise if only quality pre-built RNG is provided."""
        from mrg32k3a.mrg32k3a import MRG32k3a

        with pytest.raises(ValueError, match="Both pre_built"):
            create_initiative_rng_pair(
                pre_built_quality_rng=MRG32k3a(),
                initiative_index=0,
            )

    def test_error_partial_pre_built_exec_only(self):
        """Must raise if only exec pre-built RNG is provided."""
        from mrg32k3a.mrg32k3a import MRG32k3a

        with pytest.raises(ValueError, match="Both pre_built"):
            create_initiative_rng_pair(
                pre_built_exec_rng=MRG32k3a(),
                initiative_index=0,
            )

    def test_error_both_seed_and_pre_built(self):
        """Must raise if both world_seed and pre-built RNGs are provided."""
        from mrg32k3a.mrg32k3a import MRG32k3a

        with pytest.raises(ValueError, match="not both"):
            create_initiative_rng_pair(
                world_seed=42,
                pre_built_quality_rng=MRG32k3a(),
                pre_built_exec_rng=MRG32k3a(),
                initiative_index=0,
            )


# ---------------------------------------------------------------------------
# CRN regime independence
# ---------------------------------------------------------------------------


class TestCrnRegimeIndependence:
    """Tests for the CRN invariant: governance decisions must not shift
    observation draws for other initiatives.

    Two runs sharing the same world_seed must produce identical draws
    for initiative i regardless of whether other initiatives are active.
    This is the key CRN property that makes governance comparisons valid.
    """

    def test_initiative_draws_unaffected_by_other_initiatives(self):
        """Drawing from initiative 1's RNG must be unaffected by whether
        initiative 0's RNG has been used (simulating regime differences).
        """
        # Regime A: uses initiative 0 and 1
        pair_a_0 = create_initiative_rng_pair(world_seed=42, initiative_index=0)
        pair_a_1 = create_initiative_rng_pair(world_seed=42, initiative_index=1)

        # In regime A, initiative 0 gets some draws (it's active)
        _ = [pair_a_0.quality_signal_rng.random() for _ in range(20)]
        # Initiative 1 gets its draws
        draws_a_1 = [pair_a_1.quality_signal_rng.random() for _ in range(10)]

        # Regime B: only uses initiative 1 (initiative 0 was stopped)
        pair_b_1 = create_initiative_rng_pair(world_seed=42, initiative_index=1)
        # Initiative 1 gets its draws without initiative 0 being active
        draws_b_1 = [pair_b_1.quality_signal_rng.random() for _ in range(10)]

        # The draws for initiative 1 must be identical regardless of
        # whether initiative 0 was active or not.
        assert draws_a_1 == draws_b_1

    def test_exec_draws_also_independent(self):
        """Execution signal draws must also be regime-independent."""
        pair_a = create_initiative_rng_pair(world_seed=42, initiative_index=2)
        pair_b = create_initiative_rng_pair(world_seed=42, initiative_index=2)

        # Simulate regime A having drawn from other initiatives first
        _ = create_initiative_rng_pair(world_seed=42, initiative_index=0)
        draws_a = [pair_a.exec_signal_rng.random() for _ in range(10)]
        draws_b = [pair_b.exec_signal_rng.random() for _ in range(10)]
        assert draws_a == draws_b


# ---------------------------------------------------------------------------
# create_all_initiative_rngs
# ---------------------------------------------------------------------------


class TestCreateAllInitiativeRngs:
    """Tests for create_all_initiative_rngs."""

    def test_correct_count(self):
        """Must produce the requested number of RNG pairs."""
        pairs = create_all_initiative_rngs(world_seed=42, initiative_count=5)
        assert len(pairs) == 5

    def test_empty_pool(self):
        """Zero initiatives produces an empty tuple."""
        pairs = create_all_initiative_rngs(world_seed=42, initiative_count=0)
        assert pairs == ()

    def test_determinism(self):
        """Same seed and count produce identical RNG pairs."""
        pairs_a = create_all_initiative_rngs(world_seed=42, initiative_count=3)
        pairs_b = create_all_initiative_rngs(world_seed=42, initiative_count=3)
        for pair_a, pair_b in zip(pairs_a, pairs_b, strict=True):
            q_a = [pair_a.quality_signal_rng.random() for _ in range(5)]
            q_b = [pair_b.quality_signal_rng.random() for _ in range(5)]
            assert q_a == q_b

    def test_negative_count_raises(self):
        """Negative initiative_count must raise ValueError."""
        with pytest.raises(ValueError, match="initiative_count must be >= 0"):
            create_all_initiative_rngs(world_seed=42, initiative_count=-1)

    def test_each_pair_is_independent(self):
        """Each pair in the tuple should have distinct draw sequences."""
        pairs = create_all_initiative_rngs(world_seed=42, initiative_count=3)
        draw_sets = []
        for pair in pairs:
            draws = tuple(pair.quality_signal_rng.random() for _ in range(5))
            draw_sets.append(draws)
        # All three quality draw sequences should be distinct
        assert len(set(draw_sets)) == 3


# ---------------------------------------------------------------------------
# Variate-drawing helpers
# ---------------------------------------------------------------------------


class TestVariateHelpers:
    """Tests for the variate-drawing helper functions."""

    def test_draw_normal_determinism(self):
        """Same RNG state produces same normal draw."""
        rng_a = create_pool_rng(world_seed=42)
        rng_b = create_pool_rng(world_seed=42)
        assert draw_normal(rng_a, 0.0, 1.0) == draw_normal(rng_b, 0.0, 1.0)

    def test_draw_uniform_range(self):
        """Uniform draws should be within [low, high]."""
        rng = create_pool_rng(world_seed=42)
        for _ in range(100):
            value = draw_uniform(rng, 0.1, 0.4)
            assert 0.1 <= value <= 0.4

    def test_draw_uniform_int_range(self):
        """Uniform int draws should be within [low, high]."""
        rng = create_pool_rng(world_seed=42)
        for _ in range(100):
            value = draw_uniform_int(rng, 5, 15)
            assert 5 <= value <= 15
            assert isinstance(value, int)

    def test_draw_beta_range(self):
        """Beta draws should be in [0, 1]."""
        rng = create_pool_rng(world_seed=42)
        for _ in range(100):
            value = draw_beta(rng, 2.0, 5.0)
            assert 0.0 <= value <= 1.0

    def test_draw_lognormal_positive(self):
        """Lognormal draws should be positive."""
        rng = create_pool_rng(world_seed=42)
        for _ in range(100):
            value = draw_lognormal(rng, 0.0, 1.0)
            assert value > 0.0


# ---------------------------------------------------------------------------
# draw_from_distribution
# ---------------------------------------------------------------------------


class TestDrawFromDistribution:
    """Tests for draw_from_distribution dispatch."""

    def test_beta_distribution(self):
        """BetaDistribution should dispatch to draw_beta."""
        rng = create_pool_rng(world_seed=42)
        spec = BetaDistribution(alpha=2.0, beta=5.0)
        value = draw_from_distribution(rng, spec)
        assert 0.0 <= value <= 1.0

    def test_uniform_distribution(self):
        """UniformDistribution should dispatch to draw_uniform."""
        rng = create_pool_rng(world_seed=42)
        spec = UniformDistribution(low=10.0, high=20.0)
        value = draw_from_distribution(rng, spec)
        assert 10.0 <= value <= 20.0

    def test_lognormal_distribution(self):
        """LogNormalDistribution should dispatch to draw_lognormal."""
        rng = create_pool_rng(world_seed=42)
        spec = LogNormalDistribution(mean=0.0, st_dev=0.5)
        value = draw_from_distribution(rng, spec)
        assert value > 0.0

    def test_unknown_type_raises(self):
        """Unrecognized DistributionSpec type should raise TypeError."""

        class FakeDistribution:
            pass

        rng = create_pool_rng(world_seed=42)
        with pytest.raises(TypeError, match="Unrecognized DistributionSpec"):
            draw_from_distribution(rng, FakeDistribution())  # type: ignore[arg-type]

    def test_determinism_across_types(self):
        """Same RNG state + same spec must produce same draw."""
        spec = BetaDistribution(alpha=3.0, beta=3.0)
        rng_a = create_pool_rng(world_seed=42)
        rng_b = create_pool_rng(world_seed=42)
        assert draw_from_distribution(rng_a, spec) == draw_from_distribution(rng_b, spec)
