# State definition and Markov property

This note defines the compact Markov state of the Primordial Soup simulator:
the minimal collection of variables such that the future evolution of the
simulation is conditionally independent of the past given the current state.
Its purpose is to provide a reference for optimization, analysis, and future
extensions. Any change to the simulator that adds, removes, or modifies state
variables should be checked against this note.

The Markov property means: given the current state $S_t$, the joint distribution
of all future states $(S_{t+1}, S_{t+2}, \ldots)$ does not depend on $(S_0, \ldots,
S_{t-1})$. For this simulator, the property holds because every transition
(belief update, lifecycle change, value realization, capability decay) is
computed from current state and immutable parameters alone.

## Compact Markov state


### Academic
The state $S_t$ is partitioned into per-initiative, per-team, portfolio-level,
temporal, and pool-level components. Together with the immutable run parameters
(see **What is NOT state** below), these fully determine all future
trajectories.

#### Per-initiative state

Each initiative $i$ carries the following mutable state fields. These
correspond to the fields of `InitiativeState` in `state.py`.

| Field | Type | Description |
|-------|------|-------------|
| `initiative_id` | `str` | Unique identifier. Immutable after creation but included in state for indexing. |
| `lifecycle_state` | `LifecycleState` | One of UNASSIGNED, ACTIVE, STOPPED, COMPLETED. Determines which transitions apply. |
| `assigned_team_id` | `str \| None` | Currently assigned team, or None if unassigned/stopped/completed. |
| `quality_belief_t` | `float` | Current strategic quality belief ($c_t$ in the design docs). Updated each staffed tick via Bayesian-style learning. |
| `execution_belief_t` | `float \| None` | Current execution belief. None when `true_duration_ticks` is not set on the initiative config. |
| `executive_attention_t` | `float` | Executive attention allocated this tick. Determined by governance each tick. |
| `staffed_tick_count` | `int` | Lifetime count of staffed ticks. Never resets on reassignment. |
| `ticks_since_assignment` | `int` | Staffed ticks since most recent team assignment. Resets on reassignment. |
| `age_ticks` | `int` | Calendar age in ticks since creation. |
| `cumulative_value_realized` | `float` | Total value realized across all channels. |
| `cumulative_lump_value_realized` | `float` | Value realized through the completion-lump channel. |
| `cumulative_residual_value_realized` | `float` | Value realized through the residual channel. |
| `cumulative_labor_invested` | `float` | Total labor (team-size-ticks) invested. |
| `cumulative_attention_invested` | `float` | Total executive attention invested. |

| `belief_history` | `tuple[float, ...]` | Ring buffer of recent quality beliefs for stagnation detection. Trimmed to `stagnation_window_staffed_ticks` length. |
| `review_count` | `int` | Number of governance reviews this initiative has received. |
| `consecutive_reviews_below_tam_ratio` | `int` | Consecutive reviews where belief-to-ceiling ratio fell below the policy threshold. |
| `residual_activated` | `bool` | Whether the residual value channel has been activated. |
| `residual_activation_tick` | `int \| None` | Tick at which residual was activated, or None. |
| `major_win_surfaced` | `bool` | Whether a major-win event has been recorded. |
| `major_win_tick` | `int \| None` | Tick at which major win was surfaced, or None. |
| `completed_tick` | `int \| None` | Tick at which the initiative completed, or None. |

#### Per-team state

Each team $j$ carries the following mutable state fields. These correspond to
the fields of `TeamState` in `state.py`.

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | `str` | Unique identifier. |
| `team_size` | `int` | Number of people on this team. Fixed for the duration of a run in the canonical study. |
| `assigned_initiative_id` | `str \| None` | Currently assigned initiative, or None if the team is free. |

#### Portfolio-level state

| Field | Type | Description |
|-------|------|-------------|
| `portfolio_capability` | `float` | Portfolio capability scalar $C_t$. Initialized to 1.0, bounded by $[1.0, C_{\text{max}}]$. Evolves via enabler completions (increases) and exponential decay (decreases). Reduces effective signal noise for all staffed initiatives. |

#### Temporal state

| Field | Type | Description |
|-------|------|-------------|
| `tick` | `int` | Current simulation tick. Advances by 1 each step. |

#### Pool-level state (derived)

The partition of initiatives across lifecycle states (UNASSIGNED, ACTIVE,
STOPPED, COMPLETED) is fully determined by the per-initiative
`lifecycle_state` fields. It is not stored separately but is a derived
convenience view. The set of initiatives in each state at tick $t$ determines
which transitions are possible at tick $t+1$.


### Business
The simulation's state at any given week is the complete picture of everything that determines what can happen from that point forward. If you captured this snapshot and handed it — together with the fixed configuration parameters that define the simulation's rules — to someone who had never seen the prior history, they could run the simulation forward and produce exactly the same results as if it had been running continuously from the beginning. Nothing outside this snapshot is needed. Nothing from the prior history matters except insofar as it produced this current state.

The state is organized into five components: what the simulation tracks about each initiative, what it tracks about each team, the organization's overall capability level, where the simulation stands in time, and the derived composition of the initiative pool across lifecycle stages.

#### Per-initiative state

Each initiative carries the following state that evolves as the simulation progresses. These fields collectively represent everything the simulation knows about an initiative's current situation — its status, the organization's current beliefs about it, the resources invested in it, and the outcomes it has produced so far.

| Field | Description |
|-------|-------------|
| `initiative_id` | Unique identifier for the initiative. Fixed at creation but included in state for cross-referencing across all other records. |
| `lifecycle_state` | Where the initiative currently stands: unassigned (created but not yet staffed), active (a team is assigned and working), stopped (terminated by governance), or completed (reached its natural conclusion and realized its value). This single field determines which governance actions and state transitions can apply to the initiative. |
| `assigned_team_id` | The team currently assigned to this initiative, if any. Absent when the initiative is unassigned, stopped, or completed. |
| `quality_belief_t` | The organization's current best estimate of how strategically valuable this initiative is. This is the running assessment that accumulates as new evidence comes in each week the initiative is staffed. It is the primary input to governance's continue/stop decisions — the number that leadership watches most closely when deciding whether an initiative is worth continued investment. |
| `execution_belief_t` | The organization's current best estimate of whether execution is tracking to the original plan. Absent when the initiative's configuration does not include a true completion timeline. When present, this estimate adjusts toward what the observed progress implies about how long the initiative will actually take relative to its stated plan. |
| `executive_attention_t` | How much executive attention is allocated to this initiative in the current week. Set by governance each week. This allocation does not carry over — if governance does not explicitly allocate attention in a given week, the initiative receives none. |
| `staffed_tick_count` | Total number of weeks this initiative has had a team working on it across its entire lifetime. Never resets when a team is reassigned. This is the cumulative investment of staffed time, and it also determines how many signal draws have been made from the initiative's random streams. |
| `ticks_since_assignment` | Weeks of staffed work since the most recent team was assigned to this initiative. Resets to zero when a new team takes over. Used to determine whether the team is still in its ramp-up period, during which learning effectiveness is reduced as the team builds context on the initiative. |
| `age_ticks` | How many weeks have passed since this initiative was created, regardless of whether it has been staffed during that time. |
| `cumulative_value_realized` | Total value this initiative has generated across all value channels — one-time completion payoffs, ongoing residual streams, and any other active value mechanisms. |
| `cumulative_lump_value_realized` | Value generated specifically through one-time payoffs realized at completion. |
| `cumulative_residual_value_realized` | Value generated specifically through ongoing return streams that persist and compound after the team has moved on. |
| `cumulative_labor_invested` | Total person-weeks of team effort invested in this initiative. Computed from team size multiplied by staffed weeks. |
| `cumulative_attention_invested` | Total executive attention invested in this initiative, accumulated across all weeks of its existence. |

| `belief_history` | A rolling window of recent strategic quality estimates, retained specifically for stagnation detection. Trimmed to the length of the configured stagnation detection window. If the organization's belief about an initiative has not meaningfully shifted across this window of active work, the initiative may be a candidate for the stagnation stopping rule — the evidence stream has stopped producing new information, and continued investment may not resolve the uncertainty. |
| `review_count` | How many times governance has formally reviewed this initiative. |
| `consecutive_reviews_below_tam_ratio` | The number of consecutive governance reviews in which the initiative's expected value — given current confidence in its quality and the visible opportunity ceiling — fell below the threshold that justifies continued investment. This counter drives the prize-inadequacy stopping rule. When it exceeds the patience window (which itself scales with the size of the visible opportunity — larger opportunities earn more patience), governance terminates the initiative. The counter resets to zero whenever a review produces a favorable enough ratio. |
| `residual_activated` | Whether the initiative's ongoing value stream has been activated. Activation occurs at completion for initiatives that carry a residual mechanism — the team has finished the work, and the compounding mechanism it built begins producing returns autonomously. |
| `residual_activation_tick` | The week in which the residual stream was activated. Absent if the residual has not been activated. |
| `major_win_surfaced` | Whether this initiative has been identified as a transformational outcome upon completion. A major-win event is recorded when a right-tail initiative completes and its hidden quality meets the major-win threshold. |
| `major_win_tick` | The week in which the major win was surfaced. Absent if no major win has occurred. |
| `completed_tick` | The week in which the initiative completed. Absent if the initiative has not yet completed. |

#### Per-team state

Each team carries the following state. Teams are the atomic units of labor allocation — each is assigned to at most one initiative at a time, and the simulation never splits a team across multiple initiatives.

| Field | Description |
|-------|-------------|
| `team_id` | Unique identifier for the team. |
| `team_size` | Number of people on this team. Fixed for the duration of a run in the canonical study — the organizational structure (how the total workforce is divided into teams) is set before the simulation begins and does not change during the run. |
| `assigned_initiative_id` | The initiative this team is currently working on. Absent when the team is available for assignment. |

#### Portfolio-level state

| Field | Description |
|-------|-------------|
| `portfolio_capability` | The organization's accumulated learning infrastructure — the stock of capability built through completed enabler initiatives. Initialized at 1.0 (baseline organizational capability), bounded by a configured maximum. Higher capability reduces the noise in strategic signals across all staffed initiatives simultaneously, meaning the organization reaches confident conclusions about initiative quality faster and with less wasted investment. Evolves through two mechanisms: increases when enabler initiatives complete (each contributing to the stock based on its capability contribution scale), and gradual decay over time if not replenished by further enabler completions. This single scalar represents the cumulative effect of all the organization's investments in learning infrastructure — experimentation platforms, data and analytics capabilities, process improvements, dependency reduction — and its effect on governance decision quality is pervasive and compounding. |

#### Temporal state

| Field | Description |
|-------|-------------|
| `tick` | The current week of the simulation. Advances by one each step. Together with the simulation horizon (a fixed parameter), this determines how many weeks remain. |

#### Pool-level state (derived)

The partition of initiatives across lifecycle states — how many are unassigned, active, stopped, or completed at any given week — is fully determined by the per-initiative lifecycle state fields listed above. It is not stored as a separate piece of state but is a derived convenience view, computable at any time from the initiative records. The composition of the pool at any given week — which initiatives are in each state — determines what transitions governance can trigger in the following week: which initiatives can be staffed, which can be stopped, which teams are occupied, and which are available for reassignment.

## What is NOT state


### Academic
The following are **parameters**, not state. They are immutable for the
duration of a run and do not evolve with ticks.

#### Per-initiative parameters (from `ResolvedInitiativeConfig`)

These are the immutable attributes resolved at pool generation time:

- `latent_quality` ($q$) — hidden ground truth, never observed by governance
- `true_duration_ticks` — hidden execution target, never observed by governance
- `base_signal_st_dev` — base noise on strategic signal
- `dependency_level` — inter-initiative dependency on signal noise
- `planned_duration_ticks` — observable plan reference
- `required_team_size` — minimum staffing threshold
- `staffing_response_scale` — learning-rate multiplier for surplus staffing
- `generation_tag` — family label for reporting and portfolio-mix targeting
- `observable_ceiling` — bounded-prize ceiling (policy-visible)
- Value channel configuration: `completion_lump_enabled`,
  `completion_lump_value`, `residual_enabled`, `residual_activation_state`,
  `residual_rate`, `residual_decay`, `major_win_event_enabled`,
  `is_major_win`, `capability_contribution_scale`
- Initial beliefs: `initial_quality_belief`, `initial_execution_belief`

#### Run-level parameters (from `SimulationConfiguration`)

- `ModelConfig`: learning rates, noise coefficients, capability bounds and
  decay, initial beliefs, stagnation window
- `GovernanceConfig`: thresholds, attention bounds, stop rules, portfolio-mix
  targets
- `WorkforceArchitectureSpec`: team decomposition, ramp period
- `horizon_ticks`: simulation length
- `world_seed`: RNG seed

These are fixed before the simulation begins and do not change during the
run. The simulator receives them and reads from them but never modifies them.

#### Derived quantities (not independently stored)

Some values computed during a tick are derived from state and parameters and
are not independently part of the Markov state:

- `effective_signal_st_dev_t` — computed from `base_signal_st_dev`,
  `dependency_level`, and `portfolio_capability`
- `PortfolioSummary` — aggregated from per-initiative and per-team state
- `GovernanceObservation` / `InitiativeObservation` — projections of state
  through the observation boundary
- Per-tick value increments — computed from state, parameters, and
  (for signal draws) RNG stream positions


### Business
The following are **parameters**, not state. They are fixed before the simulation begins and do not change during the run. The distinction matters: state represents the evolving situation that governance must respond to; parameters represent the rules of the world and the structural characteristics of the opportunities within it. Governance operates within the world these parameters define but cannot alter them.

#### Per-initiative parameters

These are the immutable attributes of each initiative, resolved when the initiative is created — either at initial pool generation before the run begins, or under the dynamic frontier, when the runner materializes a new initiative between review cycles. They describe what the initiative fundamentally is: its underlying truth, its structural characteristics, and which value mechanisms it activates. None of these change during the run.

- **True strategic quality** — the hidden ground truth about how valuable this initiative actually is. Drawn from a family-specific distribution at creation. Governance never observes this directly; it can only form beliefs about it from noisy weekly signals. This is the quantity the organization is trying to learn about through the entire lifecycle of the initiative.
- **True completion timeline** — how long the initiative will genuinely take to complete. Hidden from governance; leadership can only infer it from imperfect execution progress signals. The gap between this and the stated plan is the source of execution surprise.
- **Baseline signal uncertainty** — the inherent noisiness of strategic signals for this initiative before any modifiers (dependency level, executive attention, organizational capability) are applied. Higher baseline uncertainty means the initiative is fundamentally harder to evaluate, independent of how the organization chooses to allocate attention.
- **Dependency level** — how much the initiative depends on factors outside the team's direct control. Higher dependency amplifies signal noise and slows the rate at which the organization learns about the initiative's true quality. This friction is a structural attribute of the initiative, not something governance can reduce.
- **Stated plan timeline** — the observable planning estimate for how long the initiative is expected to take. This is what governance can see; the true timeline is hidden.
- **Required team size** — the minimum number of people needed to staff this initiative.
- **Staffing response scale** — how much additional learning benefit the initiative derives from surplus staffing (a team larger than the minimum). This governs the diminishing returns on overstaffing.
- **Family label** — which initiative family this belongs to (quick win, flywheel, enabler, right-tail). Used for reporting and portfolio-mix targeting. The simulation engine does not apply special rules by family — it operates entirely on the resolved attributes. The label is for the study designer and for post-hoc analysis, not for the engine.
- **Visible opportunity ceiling** — the observable upper bound on potential value for bounded-prize initiatives. Governance can see this and uses it to calibrate how patient to be: larger visible opportunities earn more runway before governance concludes the investment is not justified.
- **Value channel configuration** — which value mechanisms this initiative activates and the specific parameters of each: whether it produces a one-time completion payoff (and how large), whether it activates an ongoing residual return stream at completion (and at what rate and decay), whether it can surface a major-win event (and whether this particular initiative is in fact a major win — hidden until completion), and how much it contributes to organizational capability upon completion.
- **Initial beliefs** — the starting values for the organization's strategic quality estimate and execution tracking estimate when the initiative is first created. These are the priors from which belief updating begins.

#### Run-level parameters

These are the fixed configuration parameters that govern the entire simulation. They define the rules of the world, the structure of the organization, and the mechanics of how governance decisions translate into outcomes.

- **Model configuration** — learning rates, noise coefficients, capability bounds and decay rates, initial belief defaults, the stagnation detection window size, and all other parameters that govern how the simulation's learning, signal generation, and value realization mechanisms operate.
- **Governance configuration** — all thresholds and rules that define how governance decisions are evaluated: the confidence decline threshold below which an initiative is stopped, attention bounds, stop rule parameters (stagnation tolerance, prize-inadequacy patience, execution overrun thresholds), portfolio-mix targets, and review scheduling.
- **Workforce architecture** — how the total workforce is divided into teams, including the number of teams, the size of each team, and the ramp period that applies when a team is newly assigned to an initiative.
- **Simulation horizon** — how many weeks the simulation runs. In the canonical study, this is approximately six years (313 ticks).
- **World seed** — the random number seed that makes the entire simulation deterministically reproducible. Given the same seed and the same governance decisions, the simulation always produces identical results.

These are fixed before the simulation begins and do not change during the run. The simulator receives them and reads from them but never modifies them.

#### Derived quantities (not independently stored)

Some values computed during a given week are derived from the current state and parameters and are not independently part of the simulation's stored state. They are recomputed whenever they are needed:

- **Effective signal noise** for a given initiative in a given week — determined by the initiative's baseline signal uncertainty, its dependency level, the executive attention it is receiving, and the organization's current portfolio capability. This changes from week to week as attention allocation and organizational capability evolve, but it is not stored as state — it is the product of a computation that depends on values already tracked elsewhere.
- **Portfolio summary** — an aggregated view of the current state across all initiatives and teams. Useful for governance reporting and analysis but not an independent piece of state; it can be recomputed from the initiative and team records at any time.
- **Governance observations** — the projections of the full state through the observation boundary. These are what governance actually sees: the running estimates, the investment history, the initiative age and review count, and all other policy-visible information. They are derived from the underlying state and presented to the governance policy, but they are not independently stored. The observation boundary ensures that governance never sees the hidden truth — only the filtered, noisy picture that these projections provide.
- **Per-week value increments** — the value generated by each initiative in a given week. These are computed from current state, parameters, and (for initiatives that generate stochastic signals) the random stream positions.

## RNG streams as hidden state


### Academic
Per-initiative RNG stream positions are technically part of the Markov state:
they determine future signal draws and therefore affect future belief
trajectories. However, they are **deterministic** given `world_seed` and the
history of draws made so far. Because each initiative has two dedicated
MRG32k3a substreams (one for quality signals, one for execution signals)
indexed by `initiative_id`, and the number of draws from each stream equals
`staffed_tick_count`, the stream positions are a deterministic function of
`world_seed`, `initiative_id`, and `staffed_tick_count`.

This means the RNG positions do not add independent state dimensions. They
are recoverable from the stored state and parameters. For practical purposes
(checkpointing, restart), the stream objects must be carried forward, but
they do not expand the Markov state beyond what is already listed above.

All RNG construction is isolated in `noise.py`. The engine never imports
MRG32k3a directly.


### Business
The random number streams that generate each initiative's weekly evidence — the strategic quality signals and execution progress signals that drive the organization's belief updates — are technically part of the simulation's complete state. Their current positions determine what signals the initiative will produce in future weeks, which in turn affects how the organization's beliefs will evolve and what governance decisions will follow.

However, these stream positions do not add any independent information beyond what is already tracked in the state described above. Each initiative has two dedicated random streams — one for strategic quality signals, one for execution progress signals — both indexed by the initiative's unique identifier and seeded from the world seed. The number of draws made from each stream is exactly equal to the initiative's staffed week count, which is already part of the per-initiative state. This means the stream positions are fully determined by three things the simulation already knows: the world seed, the initiative's identifier, and how many weeks it has been staffed.

The consequence is that the stream positions are entirely recoverable from information already in the state snapshot. They do not expand what the simulation needs to track beyond the fields already listed. For practical purposes — saving and restoring the simulation mid-run, or checkpointing for restart — the stream objects must be carried forward so that the simulation can continue drawing from the correct position. But they do not represent independent information about the simulation's future that is not already captured elsewhere.

All random stream construction is centralized in a dedicated module (`noise.py`). The simulation engine does not construct RNG objects — it consumes injected stream objects and performs deterministic draws given the stream state. Purity means: same world state, same configuration, same governance actions, and same stream internal state always produce the same outputs. The streams are inputs to the engine, not hidden globals. This isolation keeps the reproducibility discipline auditable and ensures that no part of the engine can accidentally introduce uncontrolled randomness.

## Dynamic frontier state (Stage 3)


### Academic
The dynamic opportunity frontier replaces the fixed-pool-at-run-start
assumption with family-specific frontier distributions whose parameters
shift as the run progresses. Per `dynamic_opportunity_frontier.md`.

#### Family-level frontier state

Each family with a `FrontierSpec` carries a `FamilyFrontierState` in
`WorldState.frontier_state_by_family`:

| Field | Type | Description |
|-------|------|-------------|
| `n_resolved` | `int` | Count of resolved (completed + stopped) initiatives of this family. |
| `n_frontier_draws` | `int` | Count of initiatives drawn from the frontier (for RNG position tracking). |
| `effective_alpha_multiplier` | `float` | Current quality degradation multiplier: $\max(\text{floor},\; 1.0 - \text{rate} \times n_{\text{resolved}})$. |

`frontier_state_by_family` is stored as an immutable tuple of
`(generation_tag, FamilyFrontierState)` pairs, sorted by generation_tag.

#### Right-tail prize descriptor state

Right-tail initiatives use a prize-preserving refresh mechanism. When a
right-tail initiative is stopped, its observable ceiling is recorded as
an available `PrizeDescriptor` for re-attempt:

| Field | Type | Description |
|-------|------|-------------|
| `prize_id` | `str` | Stable identifier derived from the original initiative (e.g., `"prize-init-5"`). |
| `observable_ceiling` | `float` | The persistent market opportunity ceiling. |
| `attempt_count` | `int` | Incremented when the prize re-enters the available set after a stopped attempt. The initial attempt counts as 1, so a prize with `attempt_count = 3` has had two failed re-attempts after the original. |

`available_prize_descriptors` is stored in `WorldState` as a tuple of
`PrizeDescriptor`, sorted by `prize_id`. Re-attempts carry a `prize_id`
field on `ResolvedInitiativeConfig` linking back to the original prize.

#### Frontier RNG positions

Frontier RNG positions are deterministic given `world_seed` and
`n_frontier_draws` per family. They use a separate MRG32k3a stream
allocation (with per-family substreams) isolated from per-initiative
signal streams. Authoritative substream numbering is defined in
`noise.py`; the following is the architectural constraint: frontier
streams and per-initiative signal streams occupy distinct allocations
so that frontier activity in one family cannot affect signal draws for
existing initiatives. They do not add independent state dimensions,
for the same reason that per-initiative RNG positions do not.

#### Runner-side inter-tick frontier materialization

The complete per-tick cycle with dynamic frontier:

1. **Runner frontier materialization** — the runner inspects frontier state
   in `WorldState` and the current unassigned pool per family. If a
   family's unassigned count is at or below its replenishment threshold,
   the runner generates new initiatives from the frontier and adds them
   to the pool. This is a documented state transition.
2. **Engine apply-actions** — the engine applies governance decisions
   (assignments, stops) from the previous tick.
3. **Engine step-world** — the engine advances initiative state, computes
   signals, updates beliefs, realizes value, and decays capability.
4. **Runner frontier state update** — the runner increments `n_resolved`
   for families with newly stopped or completed initiatives, and manages
   the right-tail prize lifecycle (stop → available, complete → consumed).

The engine boundary is preserved: the engine never generates initiatives.
The runner owns when and how new initiatives are drawn from the evolving
frontier. The frontier's evolving state is environment-owned and tracked in
`WorldState` for Markov completeness.


### Business
The dynamic opportunity frontier — described in full in the dynamic opportunity frontier design note — replaces the assumption that the entire initiative pool is fixed before the simulation begins. Under the dynamic frontier, each initiative family has a frontier distribution from which new opportunities emerge when the existing pool for that family is depleted. The parameters of these distributions may shift as the run progresses, reflecting the organizational reality that later opportunities tend to be somewhat less attractive than earlier ones as the best possibilities are consumed.

This mechanism introduces new state that the simulation must track for completeness and reproducibility. These variables ensure that the simulation's future evolution is fully determined by its current state — the same property that holds for all other state in the simulation.

#### Family-level frontier state

For each initiative family with an active frontier, the simulation tracks a compact state record containing three pieces of information:

- **Resolved count.** The number of initiatives of this family that have been resolved — completed or stopped — so far in the run. This counter is the sole driver of the quality degradation mechanism: as more initiatives are resolved, the frontier's quality distribution shifts downward, reflecting the organizational reality that the most promising opportunities in a given family tend to be pursued first, and the remaining landscape offers diminishing average quality. The resolved count is also what makes the dynamic frontier governance-sensitive — an impatient regime that stops more initiatives will deplete the frontier faster and face a more degraded opportunity landscape.

- **Frontier draw count.** The number of initiatives drawn from this family's frontier random stream since the run began. This is needed for reproducibility: given the world seed and the draw count, the exact sequence of future frontier draws is fully determined. It also establishes the frontier stream's position so that the simulation can resume from any checkpoint without losing its place in the draw sequence.

- **Effective quality multiplier.** The current quality degradation factor, computed from the family's degradation rate and the resolved count, bounded by the quality floor. This is a derived convenience value — it could be recomputed from the resolved count and the configuration parameters at any time — but tracking it explicitly makes the frontier's current state immediately visible without requiring the computation to be repeated. The multiplier governs how much the quality distribution has shifted: a multiplier of 1.0 means the frontier is still offering opportunities at the original quality level; a multiplier near the floor means the frontier has been substantially depleted and remaining opportunities are of consistently lower quality.

The frontier state for all families is stored as an immutable collection of per-family records, sorted by family identifier for deterministic ordering — consistent with the simulation's convention for all state collections that must be iterated in a stable sequence.

#### Right-tail prize descriptor state

Right-tail initiatives use a distinct frontier mechanism — prize-preserving refresh — that reflects the organizational reality that a failed attempt at a major opportunity does not eliminate the opportunity itself. When a right-tail initiative is stopped (the attempt fails), its observable ceiling — the persistent market opportunity — is recorded as a prize descriptor available for re-attempt. Each prize descriptor carries:

- **Prize identifier.** A stable identifier linking the prize back to the original initiative that created it. This maintains traceability across multiple attempts at the same opportunity.
- **Observable ceiling.** The persistent market opportunity that remains available for re-attempt. The ceiling does not change across attempts — the market opportunity is the same regardless of how many approaches the organization has tried.
- **Attempt count.** How many times the organization has attempted to capture this prize — incremented each time the prize returns to the available pool after a stopped attempt, with the initial attempt counting as 1. Used for the optional quality degradation mechanism (when configured, each failed attempt shifts the quality distribution slightly downward for that specific prize, modeling the possibility that repeated failures reveal something about the inherent difficulty of the opportunity space).

The set of available prize descriptors is stored in the world state as a sorted collection, ordered by prize identifier for deterministic iteration. When a new attempt is generated for a prize, the descriptor is removed from the available set until that attempt resolves — the organization is actively pursuing this opportunity again and it should not be double-counted. Re-attempt initiatives carry a prize identifier on their configuration linking back to the original prize, preserving the connection across the full lifecycle.

#### Frontier RNG positions

Frontier random stream positions — the internal state of each family's frontier random number generator — are deterministic given the world seed and the number of frontier draws made for that family. The frontier streams occupy a separate random stream allocation (distinct from the per-initiative signal streams), with each family using its own dedicated substream within that allocation. This separation ensures that frontier activity in one family cannot affect the random draws for another family or for the signal streams of existing initiatives.

Because the frontier stream positions are fully recoverable from the world seed and the frontier draw counts already tracked in the family-level frontier state, they do not add independent state dimensions — for the same reason that per-initiative signal stream positions do not. The stream objects must be carried forward for practical purposes (checkpointing and simulation restart), but they do not represent independent information beyond what is already stored.

#### Runner-side inter-tick frontier materialization

With the dynamic frontier, the complete cycle for each week of the simulation becomes a four-step process. The boundaries between steps matter because they determine who owns what — and ensure that the engine's purity, the observation boundary, and the frontier's environmental ownership are all preserved.

1. **Runner frontier materialization** (between review cycles, before the current week begins). The runner inspects the frontier state in the world and examines the current pool of unassigned initiatives for each family. If any family's unassigned pool has fallen to or below that family's replenishment threshold and the frontier for that family has not been effectively exhausted, the runner draws new initiatives from the frontier and adds them to the pool. New initiative specifications are appended to the initiative list with new dedicated random streams created for their signals. This is a formally documented state transition — not a hidden orchestration side effect.

2. **Engine applies governance decisions** (the current week begins). The engine applies the governance decisions made at the end of the previous week. Teams are reassigned to newly designated initiatives. Stopped initiatives transition to their terminal state and their teams become available.

3. **Engine advances the world** (the current week executes). The engine advances all initiative state forward: computes strategic and execution signals for staffed initiatives, updates beliefs based on the new evidence, checks whether any initiatives have reached their completion conditions, realizes value for completed initiatives, and applies capability decay.

4. **Runner frontier state update** (after the engine has finished the current week). The runner updates the frontier's tracking state to reflect what happened during the week: it increments the resolved count for any family that had initiatives stop or complete during step 3, and it manages the right-tail prize lifecycle — moving prize descriptors from stopped right-tail initiatives into the available set for re-attempt, and removing prize descriptors for right-tail initiatives that completed (consuming the prize permanently).

Steps 1 and 4 are owned by the runner. Steps 2 and 3 are owned by the engine. The engine boundary is preserved: the engine never generates initiatives and never updates frontier state. The runner owns when and how new initiatives are drawn from the evolving frontier, and when frontier tracking state is updated to reflect initiative resolution. The frontier's evolving state is environment-owned — it describes how the opportunity landscape changes as the organization works through it — and is tracked in the world state for completeness and reproducibility.

## Optimization readiness


### Academic
The purpose of this note is to provide a reference for future optimization
work, including SimOpt integration, state-space analysis, and any work that
requires a formal characterization of the simulation's state. Any change to
the simulator that adds, removes, or modifies state variables should be
checked against this note to ensure the Markov state definition remains
accurate and complete.


### Business
This state definition serves as the authoritative reference for understanding what the simulation tracks and what determines its future behavior. Any future work that requires a complete accounting of the simulation's state — including systematic optimization of governance policies through structured search, analysis of how the simulation's state space behaves across different governance trajectories, or integration with optimization frameworks that need to characterize the decision problem formally — should use this note as the starting point.

When changes to the simulation add, remove, or modify what is tracked in state, those changes should be checked against this note to ensure the state definition remains accurate and complete. A state definition that has drifted from the actual implementation undermines every use that depends on it — optimization, reproducibility analysis, and the formal characterization of what governance decisions actually affect.
