"""Simulation state types.

This module defines the mutable world state that the engine owns and
advances each tick. All types are frozen dataclasses — mutation happens
by creating new instances via dataclasses.replace(), not by modifying
existing ones.

Per architecture.md, the engine owns all mutable simulation state.
Belief state, counters, and derived statistics belong to initiative
state, not to the policy object.

Canonical symbol mappings (see docs/study/naming_conventions.md):
    c_t       → quality_belief_t   (posterior mean estimate of latent quality at tick t)
    c_exec_t  → execution_belief_t  (execution belief; estimate of on-schedule probability)
    a         — executive attention level allocated to an initiative
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primordial_soup.types import LifecycleState


@dataclass(frozen=True)
class FamilyFrontierState:
    """Compact frontier state for a single initiative family.

    Tracks how many initiatives of this family have been resolved
    (completed + stopped) and how many have been drawn from the
    frontier RNG stream. Used by the runner for quality degradation
    and RNG position tracking in inter-tick frontier materialization.

    effective_alpha_multiplier is the current quality degradation
    factor: max(floor, 1.0 - rate * n_resolved). It is stored
    explicitly for state self-description, even though it could be
    derived from n_resolved and the frontier parameters.

    Per dynamic_opportunity_frontier.md §State variables.
    """

    n_resolved: int = 0
    n_frontier_draws: int = 0
    effective_alpha_multiplier: float = 1.0


@dataclass(frozen=True)
class PrizeDescriptor:
    """Persistent right-tail prize descriptor for re-attempt tracking.

    Represents a market opportunity (observable ceiling) that can be
    approached multiple times. When a right-tail initiative is stopped,
    the runner records its ceiling as a PrizeDescriptor available for
    re-attempt. When a re-attempt completes, the prize is consumed.

    Per dynamic_opportunity_frontier.md §2 (prize-preserving refresh).

    Attributes:
        prize_id: Stable identifier derived from the original initiative
            that created this prize (e.g., "prize-init-5").
        observable_ceiling: The persistent market opportunity ceiling.
        attempt_count: Number of completed attempts (including the
            original). Incremented each time the prize returns to the
            available set after a failed attempt.
    """

    prize_id: str
    observable_ceiling: float
    attempt_count: int = 1


@dataclass(frozen=True)
class InitiativeState:
    """Mutable per-initiative state that changes during the run.

    Carried forward each tick by the engine. The corresponding immutable
    attributes live in ResolvedInitiativeConfig (config.py) and are
    looked up by initiative_id.

    Per initiative_model.md mutable state section.
    """

    initiative_id: str
    lifecycle_state: LifecycleState
    assigned_team_id: str | None

    # Strategic quality belief (c_t in design docs). Per core_simulator.md step 5.
    quality_belief_t: float

    # Execution belief (c_exec_t in design docs). None when true_duration_ticks not set.
    # Per core_simulator.md step 5, execution belief update.
    execution_belief_t: float | None

    # Last-applied executive attention for this tick.
    # a in the design docs.
    executive_attention_t: float

    # Lifetime staffed-tick count. Never resets on reassignment.
    # Used for completion detection, stagnation window, progress tracking.
    staffed_tick_count: int

    # Assignment-relative staffed tick count. Resets to 0 on each new
    # assignment. Used only for ramp-up logic.
    ticks_since_assignment: int

    # Calendar age in ticks since creation.
    age_ticks: int

    # Cumulative value tracking (channel-separated per core_simulator.md).
    cumulative_value_realized: float
    cumulative_lump_value_realized: float
    cumulative_residual_value_realized: float
    cumulative_labor_invested: float
    cumulative_attention_invested: float

    # Belief history ring buffer for stagnation detection.
    # Stored as a tuple; the engine rebuilds it each tick by appending
    # the current quality belief and trimming to W_stag entries.
    # Per core_simulator.md stagnation sliding window implementation.
    belief_history: tuple[float, ...]

    # Review tracking.
    review_count: int
    consecutive_reviews_below_tam_ratio: int

    # Residual activation state.
    residual_activated: bool
    residual_activation_tick: int | None

    # Major-win and completion tracking.
    major_win_surfaced: bool
    major_win_tick: int | None
    completed_tick: int | None


@dataclass(frozen=True)
class TeamState:
    """Per-team mutable state.

    team_size is constant for the duration of a run (no hiring/firing
    in canonical scope). assigned_initiative_id is None when the team
    is idle (not assigned to any initiative).

    Per team_and_resources.md.
    """

    team_id: str
    team_size: int
    assigned_initiative_id: str | None


@dataclass(frozen=True)
class WorldState:
    """Complete mutable simulation state owned by the engine.

    A new WorldState is produced each tick from the previous state,
    observations, and governance actions. The engine never mutates
    a WorldState in place.

    portfolio_capability is a scalar C_t representing accumulated
    organizational capability from completed initiatives. It is
    initialized to 1.0 and bounded by [1.0, C_max]. The engine
    enforces the bounds during the capability update step.

    Per architecture.md WorldState description.
    """

    tick: int
    initiative_states: tuple[InitiativeState, ...]
    team_states: tuple[TeamState, ...]

    # Portfolio capability scalar C_t, initialized to 1.0, bounded
    # by [1.0, C_max]. Per core_simulator.md capability update.
    portfolio_capability: float

    # Per-family frontier state for dynamic opportunity frontier.
    # Stored as an immutable tuple of (generation_tag, FamilyFrontierState)
    # pairs, consistent with frozen dataclass discipline. Empty tuple
    # means no frontier state is tracked (fixed-pool mode).
    # Per dynamic_opportunity_frontier.md §State variables.
    frontier_state_by_family: tuple[tuple[str, FamilyFrontierState], ...] = ()

    # Available right-tail prize descriptors for re-attempt. When a
    # right-tail initiative is stopped, its prize descriptor is added
    # here. When a re-attempt is materialized from this prize, it is
    # removed until the attempt resolves. Sorted by prize_id for
    # deterministic selection ordering.
    # Per dynamic_opportunity_frontier.md §2 (prize-preserving refresh).
    available_prize_descriptors: tuple[PrizeDescriptor, ...] = ()

    @property
    def frontier_state_dict(self) -> dict[str, FamilyFrontierState]:
        """Return frontier state as a dict for O(1) lookup by family tag."""
        return dict(self.frontier_state_by_family)
