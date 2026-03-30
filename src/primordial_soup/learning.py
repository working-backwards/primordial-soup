"""Signal model, belief updates, and learning mechanics.

This module implements the observation-and-learning layer of the
simulator: the functions that translate latent initiative attributes
and executive attention into noisy signals, and the update rules that
revise governance beliefs in response to those signals.

All functions are pure. Stochasticity enters only through RNG objects
passed as arguments; no function here creates or stores an RNG.

Key design references:
    - docs/design/core_simulator.md §Tick ordering (steps 3 and 5)
    - docs/design/core_simulator.md §Effective noise and attention shape
    - docs/design/core_simulator.md §Ramp penalties on reassignment
    - docs/design/initiative_model.md §Mutable state
    - docs/study/naming_conventions.md (canonical name mapping)

Compact symbol → descriptive name mapping for this module:
    g(a)        → attention_noise_modifier
    σ_eff       → effective_signal_st_dev_t
    σ_base      → base_signal_st_dev
    α_d         → dependency_noise_exponent (config field name)
    a           → executive_attention_t
    a_min       → attention_noise_threshold
    k_low       → low_attention_penalty_slope
    k           → attention_curve_exponent
    g_min       → min_attention_noise_modifier
    g_max       → max_attention_noise_modifier
    C_t         → portfolio_capability_t
    L(d)        → learning_efficiency
    d           → dependency_level
    η           → learning_rate
    η_exec      → execution_learning_rate
    c_t         → quality_belief_t
    c_exec_t    → execution_belief_t
    y_t         → quality_signal (strategic quality observation)
    z_t         → execution_signal (execution progress observation)
    q           → latent_quality
    q_exec      → latent_execution_fidelity
    R           → ramp_period_ticks
"""

from __future__ import annotations

import logging
import math

from primordial_soup.noise import SimulationRng, draw_normal
from primordial_soup.types import RAMP_EXPONENTIAL_K, RampShape

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Attention noise modifier g(a)
# ---------------------------------------------------------------------------


def attention_noise_modifier(
    executive_attention_t: float,
    *,
    attention_noise_threshold: float,
    low_attention_penalty_slope: float,
    attention_curve_exponent: float,
    min_attention_noise_modifier: float,
    max_attention_noise_modifier: float | None,
) -> float:
    """Compute the attention noise modifier g(a).

    The attention noise modifier scales signal noise in the effective
    signal st_dev formula: higher g(a) means more noise (worse signal
    clarity), lower g(a) means less noise (better signal clarity).

    Shape (per core_simulator.md §Effective noise and attention shape):

        g_raw(a) = 1 + k_low * (a_min - a)         if a < a_min
        g_raw(a) = 1 / (1 + k * (a - a_min))       if a >= a_min

        g(a) = clamp(g_raw(a), g_min, g_max)

    The raw shape is continuous at a = a_min where g_raw(a_min) = 1.0
    in both branches before clamping. Below a_min, noise increases
    linearly as attention falls. Above a_min, noise decreases with
    diminishing returns as attention increases.

    When max_attention_noise_modifier (g_max) is None, only the floor
    clamp (g_min) is applied. Per open implementation issue 5.

    Args:
        executive_attention_t: Current executive attention level for
            this initiative, a ∈ [0, 1]. (a in the design docs)
        attention_noise_threshold: Attention level below which noise
            increases. (a_min in the design docs)
        low_attention_penalty_slope: Slope of noise increase below
            a_min. Must be >= 0. (k_low in the design docs)
        attention_curve_exponent: Curvature for diminishing returns
            above a_min. Must be > 0. (k in the design docs)
        min_attention_noise_modifier: Floor on g(a), ensuring noise
            cannot be driven to zero. Must be > 0. (g_min in the
            design docs)
        max_attention_noise_modifier: Ceiling on g(a), preventing
            numerical explosion at low attention. None means uncapped.
            (g_max in the design docs)

    Returns:
        The clamped attention noise modifier g(a), a positive float.
    """
    # Compute the raw (unclamped) attention noise modifier.
    # g_raw(a_min) = 1.0 in both branches, so the curve is continuous
    # at the threshold before clamping is applied.
    if executive_attention_t < attention_noise_threshold:
        # Below threshold: noise increases linearly as attention falls.
        # g_raw = 1 + k_low * (a_min - a)
        g_raw = 1.0 + low_attention_penalty_slope * (
            attention_noise_threshold - executive_attention_t
        )
    else:
        # At or above threshold: noise decreases with diminishing returns.
        # g_raw = 1 / (1 + k * (a - a_min))
        g_raw = 1.0 / (
            1.0 + attention_curve_exponent * (executive_attention_t - attention_noise_threshold)
        )

    # Apply floor clamp (g_min). Per open issue 5, when g_max is None,
    # only the floor is applied and the upper end is unbounded.
    g_clamped = max(g_raw, min_attention_noise_modifier)
    if max_attention_noise_modifier is not None:
        g_clamped = min(g_clamped, max_attention_noise_modifier)

    return g_clamped


# ---------------------------------------------------------------------------
# Effective signal standard deviation σ_eff
# ---------------------------------------------------------------------------


def effective_signal_st_dev_t(
    base_signal_st_dev: float,
    dependency_level: float,
    dependency_noise_exponent: float,
    attention_noise_modifier_value: float,
    portfolio_capability_t: float,
) -> float:
    """Compute the effective strategic signal standard deviation.

    Per core_simulator.md §Effective noise and attention shape:

        σ_eff(d, a, C_t) = σ_base * (1 + α_d * d) * g(a) / C_t

    where:
        σ_base = base_signal_st_dev (per-initiative base noise)
        α_d    = dependency_noise_exponent (scales dependency noise)
        d      = dependency_level (initiative's immutable dependency)
        g(a)   = attention_noise_modifier_value (pre-computed by
                 attention_noise_modifier())
        C_t    = portfolio_capability_t (>= 1.0; higher reduces noise)

    Note on naming: the config field is called dependency_noise_exponent
    (α_d in the design docs) but the canonical formula uses it as a
    linear scale factor in (1 + α_d * d), not as an exponent. The
    config field name is a legacy misnomer from Phase 1. See
    core_simulator.md for the authoritative formula.

    Args:
        base_signal_st_dev: Initiative-level base signal noise.
            (σ_base in the design docs)
        dependency_level: Initiative's immutable dependency level,
            d ∈ [0, 1]. (d in the design docs)
        dependency_noise_exponent: Scale factor for dependency noise
            amplification, >= 0. (α_d in the design docs)
        attention_noise_modifier_value: Pre-computed g(a) value from
            attention_noise_modifier(). Positive float.
        portfolio_capability_t: Current portfolio capability scalar,
            >= 1.0. (C_t in the design docs)

    Returns:
        The effective signal standard deviation, a positive float.
    """
    # σ_eff = σ_base * (1 + α_d * d) * g(a) / C_t
    # per core_simulator.md §Effective noise and attention shape.
    return (
        base_signal_st_dev
        * (1.0 + dependency_noise_exponent * dependency_level)
        * attention_noise_modifier_value
        / portfolio_capability_t
    )


# ---------------------------------------------------------------------------
# Learning efficiency L(d)
# ---------------------------------------------------------------------------


def learning_efficiency(
    dependency_level: float,
    dependency_learning_scale: float | None = None,
) -> float:
    """Compute the dependency-adjusted learning efficiency L(d).

    Per core_simulator.md §Learning efficiency:

        L(d) = 1 - d

    This is the canonical linear form: learning efficiency decreases
    linearly with dependency level. At d = 0 (no dependency), learning
    is fully efficient. At d = 1 (maximum dependency), learning
    efficiency is zero.

    When dependency_learning_scale is provided (not None), it overrides
    the canonical formula and is returned directly. This allows
    ModelConfig to specify a fixed learning efficiency regardless of
    dependency level.

    Args:
        dependency_level: Initiative's immutable dependency level,
            d ∈ [0, 1]. (d in the design docs)
        dependency_learning_scale: Optional fixed override from
            ModelConfig. When set, replaces the L(d) = 1 - d formula.
            None means use the canonical formula.

    Returns:
        Learning efficiency, typically in [0, 1].
    """
    if dependency_learning_scale is not None:
        # ModelConfig override: use the fixed scale directly.
        return dependency_learning_scale

    # L(d) = 1 - d  (canonical linear form, per core_simulator.md)
    return 1.0 - dependency_level


# ---------------------------------------------------------------------------
# Ramp multiplier
# ---------------------------------------------------------------------------


def ramp_multiplier(
    ticks_since_assignment: int,
    ramp_period_ticks: int,
    ramp_shape: RampShape,
) -> float:
    """Compute the assignment-relative ramp multiplier.

    When a team is newly assigned to an initiative, its effective
    learning efficiency is reduced for a ramp period. The ramp
    multiplier scales L(d) during this period:

        L_ramped(d) = ramp_multiplier * L(d)

    Per core_simulator.md §Ramp penalties on reassignment:

        ramp_fraction = min((t_elapsed + 1) / R, 1.0)

        Linear:      ramp_multiplier = ramp_fraction
        Exponential: ramp_multiplier = 1 - exp(-k * ramp_fraction)
                     where k = RAMP_EXPONENTIAL_K (3.0)

        is_ramping = (t_elapsed < R - 1)

    When is_ramping is False (t_elapsed >= R - 1), the ramp multiplier
    is 1.0 regardless of shape.

    IMPORTANT: ticks_since_assignment must be the pre-increment value,
    read before the tick's production step increments it. On the first
    staffed tick after assignment, ticks_since_assignment = 0, yielding
    ramp_fraction = 1/R (positive but partial learning).

    Args:
        ticks_since_assignment: Pre-increment assignment-relative
            staffed tick count. 0 on the first staffed tick after
            assignment. (t_elapsed in the design docs)
        ramp_period_ticks: Duration of the ramp-up period in ticks.
            Must be >= 1. (R in the design docs)
        ramp_shape: Shape of the ramp curve (LINEAR or EXPONENTIAL).

    Returns:
        Ramp multiplier in (0, 1]. Returns 1.0 when fully ramped.
    """
    # If ramp period is <= 1, there is no meaningful ramp: the team
    # is immediately at full efficiency on its first tick.
    if ramp_period_ticks <= 1:
        return 1.0

    # is_ramping = (t_elapsed < R - 1)
    # per core_simulator.md: once t_elapsed >= R - 1, the team is
    # fully ramped and the multiplier is 1.0 regardless of shape.
    if ticks_since_assignment >= ramp_period_ticks - 1:
        return 1.0

    # Compute ramp fraction: how far through the ramp the team is.
    # ramp_fraction = min((t_elapsed + 1) / R, 1.0)
    # For t_elapsed in [0, R-2], this yields values from 1/R to (R-1)/R.
    ramp_fraction = (ticks_since_assignment + 1) / ramp_period_ticks

    if ramp_shape == RampShape.LINEAR:
        # Linear ramp: multiplier equals ramp fraction directly.
        return ramp_fraction

    # Exponential ramp: 1 - exp(-k * ramp_fraction)
    # where k = RAMP_EXPONENTIAL_K (3.0). This gives approximately 95%
    # efficiency when ramp_fraction reaches 1.0.
    return 1.0 - math.exp(-RAMP_EXPONENTIAL_K * ramp_fraction)


# ---------------------------------------------------------------------------
# Signal draws
# ---------------------------------------------------------------------------


def draw_quality_signal(
    latent_quality: float,
    effective_signal_st_dev: float,
    rng: SimulationRng,
) -> float:
    """Draw a single strategic quality signal observation y_t.

    Per core_simulator.md §Tick ordering step 3:

        y_t ~ Normal(q, σ_eff^2)

    where q is the initiative's latent quality and σ_eff is the
    pre-computed effective signal standard deviation (from
    effective_signal_st_dev_t()).

    The draw is unbounded (no clamping). The belief update step
    handles clamping of the resulting belief.

    Args:
        latent_quality: Initiative's ground-truth strategic quality,
            q ∈ [0, 1]. (q in the design docs)
        effective_signal_st_dev: Pre-computed effective signal noise.
            (σ_eff in the design docs)
        rng: The initiative's quality signal RNG (from
            InitiativeRngPair.quality_signal_rng).

    Returns:
        A single observation y_t drawn from Normal(q, σ_eff^2).
    """
    # y_t ~ Normal(q, σ_eff^2)
    # per core_simulator.md step 3 (production & observation).
    return draw_normal(rng, mean=latent_quality, st_dev=effective_signal_st_dev)


def draw_execution_signal(
    latent_execution_fidelity: float,
    execution_signal_st_dev: float,
    rng: SimulationRng,
) -> float:
    """Draw a single execution progress signal observation z_t.

    Per core_simulator.md §Tick ordering step 3:

        z_t ~ Normal(q_exec, σ_exec^2)
        where q_exec = min(1.0, planned_duration_ticks / true_duration_ticks)

    The latent_execution_fidelity (q_exec) is pre-computed by the
    caller as min(1.0, planned_duration / true_duration). The execution
    signal is NOT modulated by executive attention — this is a
    deliberate design choice (see core_simulator.md attention
    asymmetry note). Execution progress is directly observable from
    elapsed time, milestones, and burn rate, regardless of leadership
    attention.

    The draw is unbounded (no clamping). The belief update step
    handles clamping of the resulting belief.

    Args:
        latent_execution_fidelity: Ground-truth schedule fidelity,
            q_exec = min(1.0, planned/true). (q_exec in the design docs)
        execution_signal_st_dev: Noise std for execution observations,
            a ModelConfig parameter shared across all initiatives.
            (σ_exec in the design docs)
        rng: The initiative's execution signal RNG (from
            InitiativeRngPair.exec_signal_rng).

    Returns:
        A single observation z_t drawn from Normal(q_exec, σ_exec^2).
    """
    # z_t ~ Normal(q_exec, σ_exec^2)
    # per core_simulator.md step 3 (production & observation).
    # Execution signal is NOT attention-modulated (asymmetry by design).
    return draw_normal(rng, mean=latent_execution_fidelity, st_dev=execution_signal_st_dev)


# ---------------------------------------------------------------------------
# Belief updates
# ---------------------------------------------------------------------------


def update_quality_belief(
    quality_belief_t: float,
    quality_signal: float,
    learning_rate: float,
    ramp_multiplier_value: float,
    learning_efficiency_value: float,
) -> float:
    """Update the strategic quality belief given a new observation.

    Per core_simulator.md §Tick ordering step 5:

        c_{t+1} = clamp(c_t + η * staffing_multiplier * ramp_multiplier * L(d) * (y_t - c_t), 0, 1)

    The caller (tick.py) pre-multiplies η * staffing_multiplier into the
    learning_rate parameter passed here, so this function receives
    η_eff = η * staffing_multiplier as ``learning_rate``.

    The ramp multiplier scales learning during the ramp-up period after
    team reassignment. L(d) is the dependency-adjusted learning efficiency.

    Executive attention does NOT appear directly in this formula. It
    affects learning indirectly through signal noise (σ_eff), which
    shapes the distribution of y_t. See core_simulator.md for the
    attention asymmetry rationale.

    Args:
        quality_belief_t: Current strategic quality belief, c_t ∈ [0, 1].
            (c_t in the design docs)
        quality_signal: Observed strategic quality signal y_t for this
            tick. (y_t in the design docs)
        learning_rate: Effective learning rate, η_eff = η * staffing_multiplier.
            The caller pre-multiplies the base learning rate (η from ModelConfig)
            by the staffing intensity multiplier before passing it here.
        ramp_multiplier_value: Pre-computed ramp multiplier (1.0 when
            not ramping). From ramp_multiplier().
        learning_efficiency_value: Pre-computed L(d) from
            learning_efficiency(). Typically in [0, 1].

    Returns:
        Updated quality belief c_{t+1}, clamped to [0, 1].
    """
    # c_{t+1} = clamp(c_t + η_eff * ramp_multiplier * L(d) * (y_t - c_t), 0, 1)
    # where η_eff = η * staffing_multiplier (pre-multiplied by caller).
    # Per core_simulator.md step 5 (belief update).
    innovation = quality_signal - quality_belief_t  # y_t - c_t
    adjustment = learning_rate * ramp_multiplier_value * learning_efficiency_value * innovation
    updated_belief = quality_belief_t + adjustment

    # Clamp to the valid belief range [0, 1].
    return max(0.0, min(1.0, updated_belief))


def update_execution_belief(
    execution_belief_t: float,
    execution_signal: float,
    execution_learning_rate: float,
) -> float:
    """Update the execution fidelity belief given a new observation.

    Per core_simulator.md §Tick ordering step 5:

        c_exec_{t+1} = clamp(c_exec_t + η_exec * (z_t - c_exec_t), 0, 1)

    The execution belief update is NOT modulated by L(d) or executive
    attention (see core_simulator.md attention asymmetry note). It also
    has no ramp multiplier — execution progress signals (elapsed time,
    milestone delivery, burn rate) accumulate regardless of team
    familiarity.

    Args:
        execution_belief_t: Current execution fidelity belief,
            c_exec_t ∈ [0, 1]. (c_exec_t in the design docs)
        execution_signal: Observed execution signal z_t for this tick.
            (z_t in the design docs)
        execution_learning_rate: Execution learning rate from
            ModelConfig. (η_exec in the design docs)

    Returns:
        Updated execution belief c_exec_{t+1}, clamped to [0, 1].
    """
    # c_exec_{t+1} = clamp(c_exec_t + η_exec * (z_t - c_exec_t), 0, 1)
    # per core_simulator.md step 5 (execution belief update).
    # NOT modulated by L(d) or attention (asymmetry by design).
    innovation = execution_signal - execution_belief_t  # z_t - c_exec_t
    adjustment = execution_learning_rate * innovation
    updated_belief = execution_belief_t + adjustment

    # Clamp to the valid belief range [0, 1].
    return max(0.0, min(1.0, updated_belief))
