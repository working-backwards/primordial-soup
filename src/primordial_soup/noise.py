"""Per-initiative CRN stream construction using MRG32k3a.

This module isolates all MRG32k3a construction, substream indexing, and
random variate generation behind a single abstraction. No other module
in the simulator imports or references MRG32k3a directly — they receive
opaque RNG objects from this module.

The MRG32k3a generator (L'Ecuyer's combined multiple recursive generator)
provides native stream/substream partitioning that maps directly to our
CRN discipline:

    - world_seed → deterministic ref_seed for the MRG32k3a generator
      (derived via SHA-256 to produce the six seed components)
    - Per-initiative substream pairs (quality signal, execution signal)
    - Pool generator substream for attribute draws

Substream mapping (all within stream 0):

    - Substream 0:       pool generator (attribute draws during generation)
    - Substream 2i + 1:  initiative i quality signal draws
    - Substream 2i + 2:  initiative i execution signal draws

This ensures two runs sharing the same world_seed receive identical
observation noise for each initiative regardless of governance regime,
because each initiative's substream is independent of which other
initiatives are active.

See:
    - docs/design/architecture.md invariant 9 (CRN)
    - docs/implementation/simopt_notes.md
"""

from __future__ import annotations

import hashlib
import logging
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mrg32k3a.mrg32k3a import MRG32k3a

if TYPE_CHECKING:
    from primordial_soup.types import DistributionSpec

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MRG32k3a modulus constants
# ---------------------------------------------------------------------------

# These are the two moduli used internally by MRG32k3a. Seed components
# for the first state vector must be in [0, _MRG_M1) and for the second
# in [0, _MRG_M2). At least one component in each triple must be nonzero.
_MRG_M1: int = 4294967087
_MRG_M2: int = 4294944443

# Substream index reserved for the pool generator. Initiative substreams
# start after this at 2 * initiative_index + 1.
_POOL_SUBSTREAM_INDEX: int = 0

# Stream index for frontier RNG streams. Per-initiative signal streams
# use stream 0; frontier streams use stream 1 to avoid collisions.
# Each canonical family gets a dedicated substream within stream 1.
_FRONTIER_STREAM_INDEX: int = 1

# Per-family frontier substream indices within stream 1.
# Alphabetically ordered for stability. These map to the canonical
# initiative families defined in config.CANONICAL_BUCKET_NAMES.
_FRONTIER_FAMILY_SUBSTREAM: dict[str, int] = {
    "enabler": 0,
    "flywheel": 1,
    "quick_win": 2,
    "right_tail": 3,
}


# ---------------------------------------------------------------------------
# Opaque RNG type
# ---------------------------------------------------------------------------

# SimulationRng is the opaque type that all non-noise modules receive.
# It is a MRG32k3a instance, but external code should treat it as an
# opaque object and use only the variate helpers in this module.
SimulationRng = MRG32k3a


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InitiativeRngPair:
    """Paired RNG streams for a single initiative's CRN draws.

    quality_signal_rng: used for strategic quality signal draws (y_t).
    exec_signal_rng: used for execution progress signal draws (z_t).

    These are independent substreams of the same MRG32k3a generator,
    ensuring CRN isolation across initiatives and across governance
    regimes.
    """

    quality_signal_rng: SimulationRng
    exec_signal_rng: SimulationRng


# ---------------------------------------------------------------------------
# Seed derivation
# ---------------------------------------------------------------------------


def derive_ref_seed(world_seed: int) -> tuple[int, int, int, int, int, int]:
    """Convert a world_seed integer into a 6-component MRG32k3a ref_seed.

    Uses SHA-256 to derive six 32-bit seed components from the world_seed.
    The first three components are reduced modulo _MRG_M1, the last three
    modulo _MRG_M2. At least one component in each triple is guaranteed
    nonzero (clamped to 1 if the hash happens to produce all zeros in a
    triple, which is astronomically unlikely but handled defensively).

    Args:
        world_seed: The world seed for this simulation run (int).

    Returns:
        A 6-tuple of integers suitable for MRG32k3a ref_seed initialization.
    """
    # SHA-256 of the string representation of the seed gives a
    # deterministic, uniformly distributed 256-bit digest.
    digest = hashlib.sha256(str(world_seed).encode("utf-8")).digest()

    # Extract 6 unsigned 32-bit integers from the first 24 bytes
    # of the digest (big-endian byte order).
    raw_values = struct.unpack(">6I", digest[:24])

    # Reduce each component modulo the appropriate MRG32k3a modulus.
    # First three components use m1, last three use m2.
    components = [
        raw_values[0] % _MRG_M1,
        raw_values[1] % _MRG_M1,
        raw_values[2] % _MRG_M1,
        raw_values[3] % _MRG_M2,
        raw_values[4] % _MRG_M2,
        raw_values[5] % _MRG_M2,
    ]

    # MRG32k3a requires at least one nonzero component in each triple
    # of the seed vector. Clamp the first element of each triple to
    # at least 1 if the triple is all zeros.
    if all(c == 0 for c in components[:3]):
        components[0] = 1
    if all(c == 0 for c in components[3:]):
        components[3] = 1

    return (
        components[0],
        components[1],
        components[2],
        components[3],
        components[4],
        components[5],
    )


# ---------------------------------------------------------------------------
# Substream index helpers
# ---------------------------------------------------------------------------


def _quality_substream_index(initiative_index: int) -> int:
    """Compute the substream index for an initiative's quality signal RNG.

    Maps initiative_index → substream (2 * initiative_index + 1).
    The +1 offset reserves substream 0 for the pool generator.
    """
    return 2 * initiative_index + 1


def _exec_substream_index(initiative_index: int) -> int:
    """Compute the substream index for an initiative's execution signal RNG.

    Maps initiative_index → substream (2 * initiative_index + 2).
    The +2 offset reserves substream 0 for the pool generator and
    keeps the quality/exec pair adjacent.
    """
    return 2 * initiative_index + 2


# ---------------------------------------------------------------------------
# RNG factory functions
# ---------------------------------------------------------------------------


def create_pool_rng(
    *,
    world_seed: int | None = None,
    pre_built_rng: SimulationRng | None = None,
) -> SimulationRng:
    """Create the pool generator RNG for initiative attribute draws.

    The pool RNG occupies substream 0 of the MRG32k3a generator seeded
    from world_seed. It is used exclusively by pool.py to draw initiative
    attributes during pool generation.

    Exactly one of world_seed or pre_built_rng must be provided:
      - world_seed: creates a new MRG32k3a instance seeded from the
        world seed (normal case).
      - pre_built_rng: uses a pre-built RNG directly (for SimOpt wrapper
        compatibility, where SimOpt provides its own RNG streams).

    Args:
        world_seed: The world seed for this simulation run.
        pre_built_rng: A pre-built MRG32k3a instance from an external source.

    Returns:
        An opaque SimulationRng positioned at the pool generator substream.

    Raises:
        ValueError: If neither or both of world_seed and pre_built_rng
            are provided.
    """
    if (world_seed is None) == (pre_built_rng is None):
        raise ValueError("Exactly one of 'world_seed' or 'pre_built_rng' must be provided.")

    if pre_built_rng is not None:
        return pre_built_rng

    # world_seed is guaranteed non-None here because of the XOR check above.
    assert world_seed is not None  # for type narrowing
    ref_seed = derive_ref_seed(world_seed)
    return MRG32k3a(
        ref_seed=ref_seed,
        s_ss_sss_index=[0, _POOL_SUBSTREAM_INDEX, 0],
    )


def create_initiative_rng_pair(
    *,
    world_seed: int | None = None,
    pre_built_quality_rng: SimulationRng | None = None,
    pre_built_exec_rng: SimulationRng | None = None,
    initiative_index: int,
) -> InitiativeRngPair:
    """Create the quality + execution signal RNG pair for one initiative.

    Each initiative gets a dedicated pair of MRG32k3a substreams indexed
    by initiative_index:
        - quality signal: substream 2 * initiative_index + 1
        - exec signal:    substream 2 * initiative_index + 2

    The +1/+2 offsets reserve substream 0 for the pool generator.

    Either world_seed or the pre-built RNG pair must be provided (not
    both). When using pre-built RNGs, both quality and exec must be
    supplied together.

    Args:
        world_seed: The world seed for this simulation run.
        pre_built_quality_rng: Pre-built quality signal RNG (SimOpt compat).
        pre_built_exec_rng: Pre-built execution signal RNG (SimOpt compat).
        initiative_index: Zero-based index of the initiative in the pool.

    Returns:
        An InitiativeRngPair with independent quality and execution RNGs.

    Raises:
        ValueError: If initiative_index is negative, or if the seed/pre-built
            arguments are inconsistent.
    """
    if initiative_index < 0:
        raise ValueError(f"initiative_index must be >= 0, got {initiative_index}.")

    has_seed = world_seed is not None
    has_pre_built = pre_built_quality_rng is not None or pre_built_exec_rng is not None

    if has_seed == has_pre_built:
        raise ValueError(
            "Provide either 'world_seed' or the pre-built RNG pair, not both (and not neither)."
        )

    if has_pre_built:
        if pre_built_quality_rng is None or pre_built_exec_rng is None:
            raise ValueError(
                "Both pre_built_quality_rng and pre_built_exec_rng must be provided together."
            )
        return InitiativeRngPair(
            quality_signal_rng=pre_built_quality_rng,
            exec_signal_rng=pre_built_exec_rng,
        )

    # world_seed is guaranteed non-None here.
    assert world_seed is not None  # for type narrowing
    ref_seed = derive_ref_seed(world_seed)

    # Quality signal substream: 2 * initiative_index + 1
    quality_rng = MRG32k3a(
        ref_seed=ref_seed,
        s_ss_sss_index=[0, _quality_substream_index(initiative_index), 0],
    )

    # Execution signal substream: 2 * initiative_index + 2
    exec_rng = MRG32k3a(
        ref_seed=ref_seed,
        s_ss_sss_index=[0, _exec_substream_index(initiative_index), 0],
    )

    return InitiativeRngPair(
        quality_signal_rng=quality_rng,
        exec_signal_rng=exec_rng,
    )


def create_all_initiative_rngs(
    *,
    world_seed: int,
    initiative_count: int,
) -> tuple[InitiativeRngPair, ...]:
    """Create RNG pairs for all initiatives in the pool.

    Convenience wrapper that creates one InitiativeRngPair per initiative
    using sequential initiative indices [0, initiative_count).

    Args:
        world_seed: The world seed for this simulation run.
        initiative_count: Number of initiatives in the pool.

    Returns:
        A tuple of InitiativeRngPair, one per initiative, in index order.

    Raises:
        ValueError: If initiative_count is negative.
    """
    if initiative_count < 0:
        raise ValueError(f"initiative_count must be >= 0, got {initiative_count}.")

    return tuple(
        create_initiative_rng_pair(
            world_seed=world_seed,
            initiative_index=i,
        )
        for i in range(initiative_count)
    )


# ---------------------------------------------------------------------------
# Frontier RNG factory
# ---------------------------------------------------------------------------


def create_frontier_rng(
    *,
    world_seed: int,
    family_tag: str,
) -> SimulationRng:
    """Create a frontier RNG stream for a specific initiative family.

    Each canonical family gets a dedicated MRG32k3a substream on
    stream 1 (separate from per-initiative signal streams on stream 0).
    The frontier RNG for family F is used exclusively for generating
    new initiatives of family F from the frontier. Cross-family
    independence is guaranteed by the substream separation.

    Per dynamic_opportunity_frontier.md §Deterministic seeding:
    the k-th initiative drawn from family F's frontier always uses
    the k-th draw from family F's frontier RNG stream, regardless
    of what happens in other families.

    Args:
        world_seed: The world seed for this simulation run.
        family_tag: The generation_tag identifying the family
            (e.g., "flywheel", "right_tail").

    Returns:
        An opaque SimulationRng positioned at this family's frontier
        substream.

    Raises:
        ValueError: If family_tag is not a recognized canonical family.
    """
    if family_tag not in _FRONTIER_FAMILY_SUBSTREAM:
        raise ValueError(
            f"Unknown family tag for frontier RNG: {family_tag!r}. "
            f"Recognized families: {sorted(_FRONTIER_FAMILY_SUBSTREAM.keys())}."
        )

    ref_seed = derive_ref_seed(world_seed)
    substream_index = _FRONTIER_FAMILY_SUBSTREAM[family_tag]

    return MRG32k3a(
        ref_seed=ref_seed,
        s_ss_sss_index=[_FRONTIER_STREAM_INDEX, substream_index, 0],
    )


# ---------------------------------------------------------------------------
# Variate-drawing helpers
# ---------------------------------------------------------------------------

# These helpers provide a stable interface for drawing random variates
# without requiring callers to know about MRG32k3a method names.
# The engine and pool generator use these exclusively.


def draw_normal(rng: SimulationRng, mean: float = 0.0, st_dev: float = 1.0) -> float:
    """Draw a single value from Normal(mean, st_dev).

    Args:
        rng: The opaque RNG object.
        mean: Mean of the normal distribution.
        st_dev: Standard deviation of the normal distribution.

    Returns:
        A single float drawn from the specified normal distribution.
    """
    return rng.normalvariate(mean, st_dev)


def draw_uniform(rng: SimulationRng, low: float, high: float) -> float:
    """Draw a single value from Uniform(low, high).

    Args:
        rng: The opaque RNG object.
        low: Lower bound of the uniform distribution (inclusive).
        high: Upper bound of the uniform distribution (inclusive).

    Returns:
        A single float drawn from Uniform[low, high].
    """
    return rng.uniform(low, high)


def draw_uniform_int(rng: SimulationRng, low: int, high: int) -> int:
    """Draw a single integer from the discrete uniform distribution [low, high].

    Args:
        rng: The opaque RNG object.
        low: Lower bound (inclusive).
        high: Upper bound (inclusive).

    Returns:
        A single integer drawn uniformly from [low, high].
    """
    return rng.randint(low, high)


def draw_beta(rng: SimulationRng, alpha: float, beta: float) -> float:
    """Draw a single value from Beta(alpha, beta).

    Args:
        rng: The opaque RNG object.
        alpha: Alpha shape parameter (> 0).
        beta: Beta shape parameter (> 0).

    Returns:
        A single float drawn from Beta(alpha, beta), in [0, 1].
    """
    return rng.betavariate(alpha, beta)


def draw_lognormal(rng: SimulationRng, mean: float, st_dev: float) -> float:
    """Draw a single value from LogNormal(mean, st_dev).

    mean and st_dev are the parameters of the underlying normal
    distribution (not the mean/std of the log-normal itself).

    Args:
        rng: The opaque RNG object.
        mean: Mean of the underlying normal (mu parameter).
        st_dev: Standard deviation of the underlying normal (sigma parameter).

    Returns:
        A single positive float drawn from the log-normal distribution.
    """
    return rng.lognormvariate(mean, st_dev)


def draw_from_distribution(rng: SimulationRng, spec: DistributionSpec) -> float:
    """Draw a single value from a DistributionSpec.

    Dispatches on the DistributionSpec type to select the appropriate
    variate method. Used by the pool generator to resolve attribute draws.

    Args:
        rng: The opaque RNG object.
        spec: A BetaDistribution, UniformDistribution, or LogNormalDistribution.

    Returns:
        A single float drawn from the specified distribution.

    Raises:
        TypeError: If spec is not a recognized DistributionSpec type.
    """
    # Import here to avoid circular dependency (types.py has no
    # dependency on noise.py, but noise.py references types for
    # DistributionSpec in TYPE_CHECKING above).
    from primordial_soup.types import (
        BetaDistribution,
        LogNormalDistribution,
        UniformDistribution,
    )

    if isinstance(spec, BetaDistribution):
        return draw_beta(rng, spec.alpha, spec.beta)
    if isinstance(spec, UniformDistribution):
        return draw_uniform(rng, spec.low, spec.high)
    if isinstance(spec, LogNormalDistribution):
        return draw_lognormal(rng, spec.mean, spec.st_dev)

    raise TypeError(
        f"Unrecognized DistributionSpec type: {type(spec).__name__}. "
        "Expected BetaDistribution, UniformDistribution, or LogNormalDistribution."
    )
