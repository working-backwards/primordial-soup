"""Core domain types for the Primordial Soup simulation.

This module defines enums, value channel structures, distribution specs,
and shared constants used across the simulation. It has no dependencies
on other simulation modules.

Canonical symbol mappings (see docs/study/naming_conventions.md):
    q       → latent_quality
    c_t     → quality_belief_t
    d       → dependency_level
    sigma   → st_dev (in distribution specs)
    eta     → learning_rate
    C_t     → portfolio_capability_t
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Floor on execution belief for implied_duration_ticks to prevent division by
# near-zero. Caps implied duration at 20x planned_duration_ticks.
# Per interfaces.md; not a tunable config parameter.
MIN_EXECUTION_BELIEF: float = 0.05

# Fixed constant for exponential ramp shape; gives ~95% efficiency
# at t_elapsed = R. Per core_simulator.md.
RAMP_EXPONENTIAL_K: float = 3.0


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LifecycleState(Enum):
    """Initiative lifecycle states per initiative_model.md.

    Transitions:
        UNASSIGNED → ACTIVE   (when a team is assigned)
        ACTIVE     → STOPPED  (when governance decides to stop)
        ACTIVE     → COMPLETED (when staffed_tick_count reaches true_duration_ticks)
        STOPPED and COMPLETED are terminal states.
    """

    UNASSIGNED = "unassigned"
    ACTIVE = "active"
    STOPPED = "stopped"
    COMPLETED = "completed"


class RampShape(Enum):
    """Shape of the ramp-up multiplier applied to newly assigned teams.

    During the ramp period (first R ticks after assignment), the team
    operates at reduced effectiveness. The shape controls how quickly
    efficiency increases toward 1.0.

    LINEAR:      ramp(t) = t / R  (linear interpolation from 0 to 1)
    EXPONENTIAL: ramp(t) = 1 - exp(-K * t / R)  where K = RAMP_EXPONENTIAL_K

    Per core_simulator.md ramp multiplier section.
    """

    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class TriggeringRule(Enum):
    """Identifies which governance rule caused a stop decision.

    Attached to ContinueStop actions when decision == STOP, and
    recorded in StopEvents for post-hoc analysis. Per governance.md.

    TAM_ADEQUACY:       belief stayed below threshold for T_tam ticks
    STAGNATION:         belief change over W_stag window < epsilon_stag
    CONFIDENCE_DECLINE: belief dropped below theta_stop threshold
    EXECUTION_OVERRUN:  execution belief dropped below overrun threshold
    DISCRETIONARY:      policy-specific stop logic not covered above
    """

    TAM_ADEQUACY = "tam_adequacy"
    STAGNATION = "stagnation"
    CONFIDENCE_DECLINE = "confidence_decline"
    EXECUTION_OVERRUN = "execution_overrun"
    DISCRETIONARY = "discretionary"


class StopContinueDecision(Enum):
    """Binary decision value for ContinueStop governance actions.

    CONTINUE: keep the initiative active and staffed.
    STOP:     transition the initiative to STOPPED and free its team.
    """

    CONTINUE = "continue"
    STOP = "stop"


class ReassignmentTrigger(Enum):
    """Records what caused a team reassignment for post-hoc analysis.

    Per review_and_reporting.md ReassignmentEvent schema.

    GOVERNANCE_STOP:    team freed because governance stopped its initiative
    COMPLETION:         team freed because its initiative completed
    IDLE_REASSIGNMENT:  team was idle and assigned to a new initiative
    """

    GOVERNANCE_STOP = "governance_stop"
    COMPLETION = "completion"
    IDLE_REASSIGNMENT = "idle_reassignment"


# ---------------------------------------------------------------------------
# Distribution specifications (for initiative generation)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BetaDistribution:
    """Beta(alpha, beta) distribution specification.

    Used primarily for initiative quality draws in the pool generator.
    alpha and beta are the standard shape parameters. Higher alpha/beta
    ratio shifts the distribution toward higher quality.
    """

    alpha: float
    beta: float


@dataclass(frozen=True)
class UniformDistribution:
    """Uniform(low, high) distribution specification.

    Used for generating attribute ranges (e.g., sigma_base, dependency)
    in the pool generator. Draws are uniform on [low, high].
    """

    low: float
    high: float


@dataclass(frozen=True)
class LogNormalDistribution:
    """LogNormal(mean, st_dev) distribution specification.

    Used for generating skewed positive-valued attributes (e.g.,
    observable ceilings). mean and st_dev are the parameters of the
    underlying normal distribution (not the mean/std of the
    log-normal itself).
    """

    mean: float  # mu of the underlying normal
    st_dev: float  # sigma of the underlying normal


# Union type for generator distribution parameters. The pool generator
# dispatches on this type to select the appropriate numpy sampling call.
DistributionSpec = BetaDistribution | UniformDistribution | LogNormalDistribution


# ---------------------------------------------------------------------------
# Value channel dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletionLumpChannel:
    """One-time lump value realized at the completion transition.

    When enabled, the engine credits realized_value to the initiative's
    cumulative_lump_value_realized at the tick it completes. This is
    the primary value channel for initiatives with a defined endpoint.

    realized_value must be >= 0 when enabled, and must not be None
    (the engine must not silently default to zero).
    Per initiative_model.md and interfaces.md validation rules.
    """

    enabled: bool
    realized_value: float | None = None


@dataclass(frozen=True)
class ResidualChannel:
    """Post-activation residual value stream with exponential decay.

    Once activated (at completion by default), the engine credits
    residual value each tick using the decay law:
        value_t = residual_rate * exp(-residual_decay * ticks_since_activation)

    activation_state controls when the channel activates ("completed"
    means it activates at the completion transition).
    residual_rate is the initial per-tick value rate (at activation).
    residual_decay is the exponential decay constant (>= 0; 0 = no decay).
    Per core_simulator.md residual value section.
    """

    enabled: bool
    activation_state: str = "completed"
    residual_rate: float = 0.0
    residual_decay: float = 0.0


@dataclass(frozen=True)
class MajorWinEventChannel:
    """Completion-time major-win discovery event.

    is_major_win is a latent boolean assigned at generation time based
    on the initiative's quality (typically q >= q_major_win_threshold).
    It is immutable and never observable by governance — the engine
    reveals it only at completion by emitting a MajorWinEvent.
    Per initiative_model.md and sourcing_and_generation.md.
    """

    enabled: bool
    is_major_win: bool = False


@dataclass(frozen=True)
class ValueChannels:
    """Composable value channel configuration for an initiative.

    Each initiative has exactly one ValueChannels instance that
    declares which value mechanisms are active. The three channels
    are independent and additive — an initiative can have any
    combination of lump, residual, and major-win channels.

    Channel structure is declarative: it determines whether a channel
    exists and its parameters. The actual value computation equations
    live in the engine, not here.
    Per initiative_model.md value_channels section.
    """

    completion_lump: CompletionLumpChannel
    residual: ResidualChannel
    major_win_event: MajorWinEventChannel
