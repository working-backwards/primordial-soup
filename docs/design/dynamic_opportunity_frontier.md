# Dynamic opportunity frontier

**Status:** Reviewed. Realization strategy resolved: runner-side inter-tick
frontier materialization (Option B). Ready for implementation.

**Dependencies:** `state_definition_and_markov_property.md` (Step 1.3),
`canonical_core.md` (invariant #6 update).

**Implementation plan reference:** Stage 3 of
`docs/implementation/2026-03-16 Implementation Plan.md`.

---

## Motivation


### Academic
The canonical study currently uses a fixed initiative pool resolved at run
start. This creates an experiment-design problem: for families where
governance actively cycles through opportunities (stops initiatives and
reassigns teams), the fixed pool can be exhausted before the horizon ends.
When that happens, later ticks reflect pool depletion rather than governance
behavior, and cross-regime comparisons become difficult to interpret.

The confound is specific: governance regimes with higher initiative
resolution rates — through aggressive stopping, faster team cycling, or
broader portfolio coverage — exhaust the pre-enumerated pool sooner than
patient regimes, creating a systematic bias against exactly the regime class
whose behavior the study must evaluate against patient alternatives. Outcome
differences in later ticks may reflect differential pool depletion (a
finite-pool artifact) rather than differential governance quality (the
phenomenon under study).

The dynamic opportunity frontier replaces the fixed-pool assumption with
family-specific frontier distributions that evolve as the run progresses.
This makes pool depletion a modeled phenomenon (declining opportunity
quality) rather than an implementation artifact (running out of pre-
enumerated initiatives).

The modeling assumption underlying the dynamic frontier is that opportunity
quality within a family follows a quality-ordered selection structure: the
pool-construction process surfaces the most promising opportunities first,
and the remaining frontier offers diminishing expected quality as the best
possibilities are consumed. The quality shift is endogenous — it depends on
the governance-driven resolution trajectory, not on calendar time — making
the realized opportunity landscape a function of cumulative governance
decisions. Under the dynamic frontier, an actively-cycling regime faces a
continuously declining quality distribution rather than a discrete exhaustion
boundary, and the cross-regime comparison remains interpretable across the
full horizon.

### Business
The canonical study currently uses a fixed pool of initiatives that is fully determined before the simulation begins. This creates a problem for the experimental design: for initiative families where governance actively cycles through opportunities — stopping underperforming initiatives and reassigning teams to new work — the fixed pool can be exhausted before the six-year horizon ends. When that happens, the later years of the simulation reflect the fact that the organization has run out of pre-enumerated opportunities, not anything about how governance is performing. Cross-regime comparisons become difficult to interpret because outcome differences in the later years may be driven by pool depletion rather than by governance quality.

This is not how real organizations experience their opportunity landscape. A company that aggressively stops underperforming initiatives and redeploys teams does not literally run out of things to work on. What happens instead is that the remaining opportunities tend to be somewhat less attractive than the ones the organization pursued first — the best ideas surface early, and the frontier of available work gradually shifts in quality as the most promising possibilities are consumed. An organization that has resolved fifty flywheel opportunities is unlikely to find the fifty-first as attractive as the first ten.

The dynamic opportunity frontier replaces the fixed-pool assumption with family-specific opportunity landscapes that evolve as the run progresses. Instead of a pre-enumerated list that can be exhausted, each initiative family has a frontier distribution from which new opportunities emerge when needed. The quality of those emerging opportunities shifts based on how many initiatives of that family the organization has already resolved — completed or stopped. This makes pool depletion a modeled phenomenon (the organization experiences declining opportunity quality as it works through its best options) rather than an implementation artifact (the simulation runs out of pre-built initiatives and has nothing left to offer).

The practical consequence for governance comparison is significant. Under the fixed-pool design, a governance regime that actively cycles through initiatives could appear disadvantaged simply because it consumed the pool faster. Under the dynamic frontier, that same regime faces a gradually declining opportunity landscape — which is a realistic organizational consequence of aggressive cycling — rather than an artificial cliff where opportunities suddenly disappear. The comparison between patient and impatient governance regimes becomes interpretable across the full horizon.

## Governing design principles


### Academic
Two architectural principles govern this design. Both must hold throughout
implementation.

#### Principle 1: The frontier is environment-side

In the three-layer model:

- The **environment** defines what opportunities exist and how their
  availability evolves over time. The frontier mechanism belongs here.
  Frontier state is environment state. Frontier parameters are environment
  parameters.
- The **runner** realizes opportunities from the environment's frontier into
  concrete `ResolvedInitiativeConfig` instances that the engine can consume.
  The runner mediates between the environment's evolving state and the
  engine's resolved-input contract. The runner's role is realization, not
  ownership.
- The **engine** consumes resolved initiative configs. It does not know or
  care whether they came from a fixed pre-enumerated pool or a dynamic
  frontier. The engine boundary does not change.

In a comparative experiment, frontier state and frontier parameters are held
constant across governance regimes, consistent with all other environmental
conditions (quality distributions, attention-to-signal curve, labor
endowment). Any divergence in the realized frontier across regimes is
attributable to governance-driven depletion trajectories, not to different
frontier configurations.

#### Principle 2: The engine never generates initiatives

Initiative materialization from the frontier is runner-side and occurs
between ticks. This preserves the existing simulator boundary defined in
`interfaces.md`: the engine consumes resolved initiative inputs, while the
runner owns orchestration and resolution. Concretely:

- `WorldState` may contain compact frontier state needed for Markov
  completeness (e.g., per-family resolved counts, right-tail prize
  descriptor state, frontier RNG positions).
- The runner may inspect that frontier state at the beginning or end of
  each tick cycle and decide whether new initiatives need to be materialized
  into the unassigned pool.
- The engine (`step_world`, `apply_actions`) still only advances the world
  given the current realized state and initiative configs. It never calls
  generation logic.
- Policy still only sees the observation boundary and does not generate
  initiatives. The policy has no access to frontier state, frontier
  parameters, or the frontier mechanism itself.
- The runner's inter-tick frontier materialization is a documented part of
  the run-cycle semantics, not an invisible orchestration side effect.

### Business
Two architectural principles govern this design. Both must hold throughout implementation, and both reflect the same separation of concerns that the study depends on elsewhere.

#### Principle 1: The frontier is environment-side

The study's three-layer model — environment, governance architecture, and operating policy — applies to the frontier in the same way it applies to everything else:

- The **environment** defines what opportunities exist and how their availability evolves over time. The opportunity frontier belongs here. It is part of the world the organization operates in, not a tool the organization uses to make decisions. Frontier state — how many opportunities have been consumed, how the quality of remaining opportunities has shifted — is environment state. Frontier parameters — how quickly quality declines, how the right-tail prize mechanism works — are environment parameters. In a comparative experiment, these are held constant across governance regimes, just like the attention-to-signal curve and the initiative quality distributions.

- The **runner** (the orchestration layer) realizes opportunities from the environment's frontier into concrete initiative specifications that the simulation engine can consume. The runner is the intermediary between the evolving opportunity landscape and the engine's requirement for fully resolved initiative inputs. Its role is realization — translating the frontier's current state into concrete initiatives — not ownership of what the frontier looks like or how it evolves.

- The **engine** consumes resolved initiative specifications. It does not know or care whether those specifications came from a fixed pre-enumerated pool or a dynamic frontier that generated them on demand. The engine boundary does not change. This is the same principle that applies to the initiative pool generally: the engine receives concrete initiatives with fully determined attributes and operates on them identically regardless of their origin.

#### Principle 2: The engine never generates initiatives

New initiatives emerging from the frontier are created by the runner between review cycles, not by the engine during a tick. This preserves the existing boundary defined in the interface specification: the engine consumes resolved initiative inputs, while the runner owns orchestration and resolution.

Concretely, this means:

- The simulation's world state may contain compact frontier tracking information needed for reproducibility — for example, how many initiatives of each family have been resolved, the state of right-tail prize descriptors, and the position of frontier random streams. This information lives in the world state so that the simulation's state is complete and self-contained.

- The runner may inspect that frontier state at the boundary between review cycles and decide whether new initiatives need to be created and added to the unassigned pool.

- The engine's core functions — advancing the world forward one tick, applying governance decisions — still only operate on the current realized state and the initiative specifications they have already received. The engine never calls any generation logic and never owns the process of creating new initiatives.

- Governance still sees only what the observation boundary permits. It does not generate initiatives and has no visibility into the frontier mechanism.

- The runner's between-tick frontier materialization is a documented part of the simulation's cycle semantics — it is a formal, visible step in how the simulation advances, not a hidden orchestration side effect that happens to produce new initiatives.

## Complete per-tick cycle


### Academic
With the dynamic frontier, the complete per-tick cycle becomes:

1. **Runner frontier materialization** (inter-tick, before tick T). The
   runner inspects frontier state in `WorldState` and the current unassigned
   pool. If any family's unassigned pool is below that family's
   replenishment threshold and the frontier for that family has not been
   exhausted, the runner draws new initiatives from the frontier and adds
   them to the pool. New initiative configs are appended to the initiative
   config list and new RNG streams are created. Frontier state in
   `WorldState` is updated (resolved counts, RNG positions). For the
   right-tail family, prize descriptor availability is also updated: when a
   prize is selected for re-attempt, its descriptor is removed from the
   available set until the new attempt resolves.

2. **Engine apply-actions** (tick T begins). The engine applies governance
   decisions (assignments, stops) from the previous tick. Teams are
   reassigned. Stopped initiatives transition to STOPPED.

3. **Engine step-world** (tick T execution). The engine advances initiative
   state: computes signals, updates beliefs, checks completion conditions,
   realizes value, decays capability.

Step 1 is runner-owned. Steps 2 and 3 are engine-owned. The boundary is
preserved.

Runner-side frontier realization is part of the formally documented
run-cycle semantics. Although it occurs outside `step_world`, it is part
of the state transition of the simulation and must be reflected in the
state-definition note and run-cycle documentation. This prevents the runner
from becoming a hidden second transition system that mutates the world in
ways the design docs do not account for. Every state change in the
simulation — whether engine-owned or runner-owned — must be visible in the
formal description of how the system evolves.

<!-- specification-gap: timing of n_resolved increment and prize-lifecycle updates (stop → available, complete → consumed) relative to the three-step cycle is not specified in this document; state_definition_and_markov_property.md defines a fourth runner-owned step for these updates, occurring after step 3 -->

**Trigger for materialization:** The runner materializes new initiatives
when the unassigned pool for a family falls below that family's
replenishment threshold. In v1, the replenishment threshold is zero: the
runner materializes only when the family's unassigned pool is completely
empty. This keeps the realized pool compact while leaving room for a
small-buffer strategy in future versions (e.g., materializing when the pool
drops to one or two rather than zero) without changing the architecture.

<!-- specification-gap: the number of initiatives materialized per replenishment event is not specified — whether the runner creates exactly one initiative per depleted family, or enough to reach some target buffer size, is left unresolved -->

### Business
With the dynamic frontier, the complete cycle for each week of the simulation becomes a three-step process. Understanding where the boundaries fall matters because it determines who owns what — and ensures that the engine's purity and the observation boundary are preserved.

1. **Runner frontier materialization** (between review cycles, before the current week begins). The runner inspects the frontier state in the world and examines the current pool of unassigned initiatives for each family. If any family's unassigned pool has fallen below that family's replenishment threshold and the frontier for that family has not been effectively exhausted, the runner draws new initiatives from the frontier and adds them to the pool. New initiative specifications are appended to the initiative list with new dedicated random streams created for their signals. The frontier state in the world is updated to reflect the new draws — resolved counts, random stream positions, and prize descriptor availability as applicable.

2. **Engine applies governance decisions** (the current week begins). The engine applies the governance decisions made at the end of the previous week. Teams are reassigned to newly designated initiatives. Stopped initiatives transition to their terminal state and their teams become available.

3. **Engine advances the world** (the current week executes). The engine advances all initiative state forward: computes strategic and execution signals for staffed initiatives, updates beliefs based on the new evidence, checks whether any initiatives have reached their completion conditions, realizes value for completed initiatives, and applies capability decay.

Step 1 is owned by the runner. Steps 2 and 3 are owned by the engine. The boundary between them is the same boundary that exists without the frontier — the only change is that step 1 is now a formally documented part of the cycle rather than being unnecessary (because the pool was previously fixed at the start).

The runner's frontier materialization, although it occurs outside the engine's core functions, is part of the state transition of the simulation. It must be reflected in the state definition and the run-cycle documentation. This prevents the runner from becoming a hidden second system that mutates the world in ways the design documents do not account for. Every state change in the simulation — whether engine-owned or runner-owned — must be visible in the formal description of how the simulation evolves.

**When materialization is triggered:** The runner creates new initiatives for a family when the unassigned pool for that family falls below the family's replenishment threshold. In the first version, the replenishment threshold is zero: the runner materializes new initiatives only when a family's unassigned pool is completely empty. This keeps the realized pool compact — the simulation is not pre-generating initiatives that may never be needed — while leaving room for a small-buffer strategy in future versions (materializing when the pool drops to one or two, rather than zero) without changing the architecture.

## Family-specific frontier behaviors


### Academic
Each initiative family has a frontier mechanism that reflects the dynamics
of how that type of opportunity landscape evolves as the organization
resolves initiatives. The four families require two fundamentally different
frontier models.

#### 1. Declining frontier for flywheel and quick-win

**Conceptual model:** Flywheel and quick-win opportunities represent a
finite but large landscape of possibilities. The best opportunities are
pursued first (by construction of the initial pool). As the run progresses
and the organization resolves more opportunities (completes or stops them),
the remaining frontier offers diminishing average quality.

**Mechanism:** When the runner needs to materialize a new flywheel or
quick-win initiative, it draws from a quality distribution whose parameters
have shifted based on how many initiatives of that family have already been
resolved (completed or stopped).

**Functional form:** For Beta(alpha, beta) quality distributions, the
effective alpha parameter shifts downward by a configurable degradation
rate per resolved initiative:

```
effective_alpha = base_alpha * max(0.1, 1.0 - degradation_rate * n_resolved)
```

The `max(0.1, ...)` floor ensures the Beta distribution remains valid and
does not collapse to a point mass. All other initiative attributes (duration,
dependency, value channels, etc.) are drawn from the same ranges as the
initial pool — only quality degrades. This reflects a modeling judgment that
the declining-frontier phenomenon operates primarily on strategic quality:
later opportunities are less strategically valuable on average, but not
necessarily more difficult to execute or structurally different.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `frontier_degradation_rate` | `float` | Per-resolved-initiative reduction in the quality distribution's alpha. Default: 0.01 for flywheel, 0.02 for quick-win. |
| `frontier_quality_floor` | `float` | Minimum multiplier on alpha (the floor in the max expression). Default: 0.1. |

These are per-family parameters set in the `InitiativeTypeSpec` or a new
`FrontierSpec` attached to it.

The higher default degradation rate for quick-win (0.02 vs. 0.01 for
flywheel) reflects the assumption that the quick-win opportunity landscape
is shallower — the variance between the most and least promising quick-win
opportunities is smaller, so quality degrades faster per resolved initiative.

**State:**

| Variable | Type | Description |
|----------|------|-------------|
| `n_resolved_by_family` | `dict[str, int]` | Map from `generation_tag` to count of resolved (completed + stopped) initiatives of that family. Compact family-level state. |
| `frontier_rng_position_by_family` | `dict[str, int]` | Map from `generation_tag` to the number of draws made from that family's frontier RNG stream. Deterministic given `world_seed` and draw count. |

**Frontier exhaustion:** There is no hard cap on how many initiatives can
be drawn. Instead, the declining quality serves as a soft exhaustion
mechanism: at sufficiently high `n_resolved`, the quality distribution
produces consistently low-quality initiatives that governance will
quickly stop (or never assign), effectively exhausting the frontier
without an arbitrary count limit.

#### 2. Prize-preserving refresh for right-tail

**Conceptual model:** A right-tail opportunity represents a persistent
prize descriptor — the observable ceiling / market opportunity — that can
be approached in multiple ways. When an attempt fails (initiative stopped
without completing), the prize remains available but the next attempt
draws a fresh approach (fresh latent quality). The ceiling is the market
opportunity; the quality is the organization's approach to capturing it.

This is conceptually distinct from the declining frontier. The flywheel
frontier models a landscape of independent opportunities whose average
quality declines as the best are consumed. The right-tail frontier
models persistent prizes that can be re-attempted with fresh approaches.

**Mechanism:** Each right-tail initiative in the initial pool has an
`observable_ceiling` drawn from the TAM distribution. When a right-tail
initiative is stopped (attempt fails), the runner records the prize
descriptor (ceiling, major-win eligibility parameters) as available for
re-attempt. When a team needs assignment and the right-tail unassigned
pool is depleted, the runner selects an available prize descriptor and
generates a new initiative with:

- The same `observable_ceiling` as the original prize descriptor.
- Fresh `latent_quality` drawn from the right-tail quality distribution,
  optionally degraded by the sensitivity parameter below.
- Fresh `is_major_win` determined by the threshold rule applied to the
  fresh quality draw.
- All other attributes drawn from the standard right-tail type spec
  ranges.
- A new unique `initiative_id` and new RNG substreams.

**Sensitivity parameter:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `right_tail_refresh_quality_degradation` | `float` | Per-failed-attempt reduction in the quality distribution's alpha for that specific prize descriptor. Default: 0.0 (no degradation — fresh draw from the same distribution). |

When `right_tail_refresh_quality_degradation > 0`, each failed attempt
shifts the quality distribution slightly downward for that specific prize,
modeling learning about the difficulty of a particular opportunity space.
This is a study hypothesis, not a default.

<!-- specification-gap: the functional form of per-prize quality degradation for right-tail refresh is not specified; by analogy with the declining frontier, the intended form may be effective_alpha = base_alpha * max(floor, 1.0 - right_tail_refresh_quality_degradation * attempt_count), but this is not stated explicitly and it is unclear whether the same floor parameter applies -->

**State:**

| Variable | Type | Description |
|----------|------|-------------|
| `available_prize_descriptors` | `tuple[PrizeDescriptor, ...]` | Prize descriptors from stopped right-tail initiatives that are available for re-attempt. |
| `per_prize_attempt_count` | `dict[str, int]` | Map from prize descriptor ID to number of failed attempts. Used for optional quality degradation. |
| `right_tail_frontier_rng_position` | `int` | Number of draws from the right-tail frontier RNG stream. |

<!-- inconsistency: The State table includes per_prize_attempt_count as a separate dict[str, int], but the Business source specifies that per-prize state (attempt count) is carried within PrizeDescriptor.attempt_count, not in a separate tracking structure. The PrizeDescriptor dataclass already has an attempt_count field, suggesting per_prize_attempt_count as an independent state variable is redundant. -->

**PrizeDescriptor** (new frozen dataclass):

| Field | Type | Description |
|-------|------|-------------|
| `prize_id` | `str` | Stable identifier derived from the original initiative that created this prize. |
| `observable_ceiling` | `float` | The persistent market opportunity. |
| `attempt_count` | `int` | Number of completed attempts (including the original). |

**Prize lifecycle:**
1. Initial pool generation creates right-tail initiatives with ceilings.
   Each becomes an implicit prize descriptor.
2. When a right-tail initiative is stopped, the runner records its ceiling
   and other prize-level attributes as an available prize descriptor.
3. When a team needs a right-tail assignment and the unassigned pool is
   empty, the runner selects from available prize descriptors according to
   a deterministic environment-side selection rule and generates a fresh
   initiative for that prize. The descriptor is removed from the available
   set until the attempt resolves. The default selection rule for v1
   should be determined during implementation review; "highest ceiling
   first" is one candidate but builds an ordering policy into the frontier
   mechanism rather than leaving selection to governance.
4. If the fresh initiative is also stopped, the prize returns to the
   available set (step 2 again), with incremented attempt count.
5. If the fresh initiative completes, the prize is consumed — it does not
   return to the available set regardless of whether a major win was
   surfaced.

Completion consumes the prize because it represents full resolution of the
opportunity: the approach has either succeeded or definitively failed to
capture the prize. A re-attempt is meaningful only when a prior approach
failed, not when the opportunity itself has been fully resolved.

#### 3. Enabler frontier

**Conceptual model:** Enablers represent a broad but finite landscape of
capability-building opportunities. The canonical study uses a modestly
sized but sufficient initial pool. The enabler frontier does not require
the same dynamic treatment as flywheel/quick-win or right-tail, because the
enabler opportunity space is structurally more bounded and governance
cycling rate through enabler initiatives is typically lower than for other
families, reducing pool-exhaustion risk within the canonical horizon.

**Mechanism:** The enabler frontier uses the same declining-frontier
mechanism as flywheel and quick-win, with a conservative degradation rate.
This provides mild quality degradation if the enabler pool is exhausted
without introducing additional complexity.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `frontier_degradation_rate` | `float` | Default: 0.005 (very slow degradation). |
| `frontier_quality_floor` | `float` | Default: 0.1 (same as flywheel/quick-win). |

### Business
Each initiative family has a frontier mechanism that reflects the real-world dynamics of how that type of opportunity landscape evolves as an organization works through it. The four families require two fundamentally different frontier models, reflecting two fundamentally different kinds of organizational opportunity.

#### 1. Declining frontier for flywheel and quick-win

**The organizational reality being modeled:** Flywheel and quick-win opportunities represent a large but finite landscape of independent possibilities. The organization's portfolio process naturally surfaces the most promising opportunities first — either because they are the most obvious, because they have the strongest internal advocates, or because they score highest on whatever intake criteria the organization uses. As the organization works through this landscape — completing some initiatives and stopping others — the remaining frontier offers diminishing average quality. The fiftieth automation opportunity is, on average, less valuable than the fifth. The twentieth market expansion is less compelling than the third.

**How this works in the simulation:** When the runner needs to create a new flywheel or quick-win initiative because the unassigned pool for that family is empty, it draws from a quality distribution whose parameters have shifted based on how many initiatives of that family have already been resolved (completed or stopped). Specifically, the distribution that governs initiative quality shifts downward — the expected quality of newly emerging opportunities declines as more opportunities are consumed.

The decline is gradual and bounded. The quality distribution never collapses entirely — there is a floor below which it cannot fall, ensuring that opportunities of some quality always remain available. All other initiative attributes — how long they take, how dependent they are on external factors, what value channels they activate — are drawn from the same ranges as the initial pool. Only quality degrades. This reflects the judgment that the declining-frontier phenomenon is primarily about strategic quality: later opportunities are less strategically valuable, not necessarily harder to execute or different in structure.

**Configuration parameters:**

- *Frontier degradation rate.* How much the quality distribution shifts downward per resolved initiative. The default is a 1% reduction per resolved flywheel and a 2% reduction per resolved quick-win, reflecting the assumption that the quick-win landscape is somewhat shallower (the gap between the best and worst quick-win opportunities is smaller than the gap between the best and worst flywheel opportunities).

- *Frontier quality floor.* The minimum quality multiplier — how low the distribution's shift factor can go before it stops declining further. The default is 10% of the original distribution parameter, ensuring the distribution remains well-defined and continues to produce meaningful (if low-quality) opportunities.

These parameters are set per family and belong to the environment configuration. They are held constant across governance regimes in comparative experiments.

**Frontier state tracked during the simulation:**

- The count of resolved initiatives per family (completed plus stopped). This compact counter is all that is needed to determine how far the frontier has shifted.

- The number of draws made from each family's frontier random stream. This is needed for reproducibility — given the world seed and the draw count, the exact sequence of frontier draws is fully determined.

**How the frontier effectively exhausts itself:** There is no hard cap on how many initiatives can be drawn from a family's frontier. Instead, the declining quality serves as a soft exhaustion mechanism. At sufficiently high resolved counts, the quality distribution consistently produces low-quality initiatives that governance will quickly stop (or never assign in the first place), effectively exhausting the frontier without an arbitrary numerical limit. This mirrors real organizational experience: opportunity landscapes do not have a hard boundary where possibilities suddenly end — they have a quality gradient that eventually makes further pursuit unproductive.

#### 2. Prize-preserving refresh for right-tail

**The organizational reality being modeled:** A right-tail opportunity represents something fundamentally different from a flywheel or quick-win. It is not an independent possibility that, once resolved, is gone. It is a persistent prize — a market opportunity, a technology platform, a strategic position — that the organization can approach in multiple ways. When one attempt to capture a major opportunity fails (the initiative is stopped without completing), the opportunity itself does not disappear. What failed was the organization's specific approach — the team composition, the technical strategy, the go-to-market plan, the timing. The market opportunity, the technology possibility, or the strategic position remains available for a fresh attempt with a different approach.

This is conceptually distinct from the declining frontier. The flywheel and quick-win frontier models a landscape of independent opportunities whose average quality declines as the best are consumed. The right-tail frontier models persistent prizes that can be re-attempted with fresh approaches. A company that fails to build a successful marketplace platform on its first try does not lose the marketplace opportunity — it loses that particular approach. The next attempt starts with a fresh strategy and a fresh assessment of how likely it is to succeed.

**How this works in the simulation:** Each right-tail initiative in the initial pool has a visible opportunity ceiling — the observable upper bound on how much value capturing that opportunity could create. When a right-tail initiative is stopped (the attempt fails), the runner records the prize — its ceiling and identifying information — as available for re-attempt. When a team needs assignment and the right-tail unassigned pool is empty, the runner selects an available prize and generates a new initiative with:

- The same visible opportunity ceiling as the original prize. The market opportunity has not changed — only the approach has failed.
- A fresh underlying quality, drawn from the right-tail quality distribution. This represents a genuinely new approach to the same opportunity, with its own probability of success.
- A fresh determination of whether this attempt would be a major win, based on the threshold rule applied to the new quality draw. A failed first attempt does not mean the opportunity cannot be transformational — it means the first approach was not the right one.
- All other attributes drawn from the standard right-tail type specification. The new attempt has its own timeline, its own dependency structure, and its own execution characteristics.
- A new unique identifier and new dedicated random streams. The simulation treats this as a new initiative, not a continuation of the old one.

**Optional sensitivity parameter:**

- *Right-tail refresh quality degradation.* An optional per-failed-attempt reduction in the quality distribution for a specific prize. When set to zero (the default), each new attempt draws from the same quality distribution as the original — the organization's chances of finding a winning approach do not diminish with failed attempts. When set to a positive value, each failed attempt shifts the quality distribution slightly downward for that specific prize, modeling the possibility that repeated failures reveal something about the fundamental difficulty of the opportunity space. This is a study hypothesis to be tested through sensitivity analysis, not a default assumption.

**State tracked during the simulation:**

- Available prize descriptors. Prize records from stopped right-tail initiatives that are available for re-attempt. Each descriptor carries a stable identifier (linking it to the original initiative that created the prize), the persistent opportunity ceiling, and the count of attempts made so far.

- Per-prize attempt count. How many times the organization has attempted each prize, used for the optional quality degradation mechanism.

- Right-tail frontier random stream position. The number of draws made from the right-tail frontier stream, needed for reproducibility.

**The prize lifecycle:**

1. Initial pool generation creates right-tail initiatives with visible opportunity ceilings. Each implicitly represents a prize — a persistent market opportunity that the organization is attempting to capture.

2. When a right-tail initiative is stopped (the attempt fails), the runner records the prize as available for re-attempt. The opportunity is still out there; the organization just failed to capture it this time.

3. When a team needs a right-tail assignment and the unassigned pool is empty, the runner selects from available prize descriptors using a deterministic environment-side selection rule and generates a fresh initiative for that prize. The prize descriptor is removed from the available set until the new attempt resolves — the organization is actively pursuing this opportunity again and it should not be double-counted. The default selection rule for the first version should be determined during implementation review. One candidate is selecting the largest-ceiling prize first, but this builds an ordering preference into the environment mechanism rather than leaving the selection to governance.

4. If the fresh initiative is also stopped, the prize returns to the available set (back to step 2), with the attempt count incremented. The organization can try again.

5. If the fresh initiative completes, the prize is consumed — it does not return to the available set regardless of whether a major win was surfaced. Completion means the organization has fully resolved its approach to this opportunity, whether the outcome was transformational or merely adequate. The market opportunity has been captured (or definitively not captured), and a new attempt is no longer meaningful.

#### 3. Enabler frontier

**The organizational reality being modeled:** Enablers represent a broad but finite landscape of capability-building opportunities — investments in data infrastructure, experimentation platforms, process improvements, and other organizational learning infrastructure. The canonical study uses a modestly sized but sufficient initial pool. The enabler frontier does not require the same dynamic treatment as the flywheel/quick-win or right-tail frontiers because enabler work tends to have a more bounded and stable opportunity set. The organization is not cycling through enablers at the same rate it cycles through other initiative types.

**How this works in the simulation:** The enabler frontier uses the same declining-frontier mechanism as flywheel and quick-win, with a much more conservative degradation rate. This provides mild quality degradation if the enabler pool is exhausted — reflecting the reality that later capability-building opportunities may be somewhat less impactful than earlier ones — without introducing additional complexity or a separate mechanism.

**Configuration parameters:**

- *Frontier degradation rate.* Default: 0.5% per resolved enabler — very slow degradation, reflecting the judgment that the enabler opportunity landscape declines more gradually than the flywheel or quick-win landscape.

- *Frontier quality floor.* Default: 10% of the original distribution parameter (same as flywheel and quick-win).

## Interface to the engine and simulator boundary


### Academic
The engine still receives resolved initiative configs. The change is in
HOW and WHEN they are produced, not in what the engine sees. The frontier
mechanism adds complexity to the runner's orchestration layer but does not
alter the engine's interface contract or behavior.

#### Realization strategy: runner-side inter-tick frontier materialization

Frontier state is part of environment/world state for Markov completeness,
but initiative realization from that frontier is runner-owned and occurs
between ticks. The runner may inspect frontier state, generate additional
resolved initiatives when needed, append them to the initiative list and
initiative states, and then hand the augmented realized world back to the
engine for the next tick. The engine never calls generation logic and never
owns frontier realization.

This keeps the realized pool compact, makes quality degradation concrete
in the actually-generated attributes, and avoids pre-enumerating thousands
of initiatives that may never be used. The tick-loop change is localized
to a single materialization step before `apply_actions`.

Invariants:
- The engine (`step_world`, `apply_actions`) never calls generation logic.
- Policy never generates initiatives.
- The runner's inter-tick materialization is a documented part of the
  run-cycle semantics.

#### What the runner is allowed to do between ticks

Between ticks (step 1 of the per-tick cycle), the runner may:

1. Read frontier state from `WorldState`.
2. Read the current set of UNASSIGNED initiatives per family.
3. If a family's unassigned pool is below that family's replenishment
   threshold and the frontier for that family has not been exhausted,
   generate one or more new `ResolvedInitiativeConfig` instances using
   the frontier's current quality distribution parameters and the family's
   type spec.
4. Create new per-initiative RNG substreams for the new initiatives using
   the frontier RNG (seeded from `world_seed`).
5. Append the new configs to the initiative config list.
6. Create new `InitiativeState` entries (UNASSIGNED, initial beliefs) and
   append them to `WorldState.initiative_states`.
7. Update frontier state in `WorldState` (increment `n_resolved_by_family`
   or `frontier_rng_position`, update prize descriptor availability).

The runner must NOT:
- Modify existing initiative configs or states.
- Call engine functions (`step_world`, `apply_actions`).
- Alter team states.
- Read or use latent quality from existing initiatives. The runner operates
  on frontier state and family-level configuration parameters, not on the
  latent attributes of individual initiatives.
- Generate initiatives for families whose unassigned pool is at or above
  the replenishment threshold. Materialization occurs only when a family's
  pool is depleted below the threshold; the runner does not pre-fill pools
  or maintain buffers beyond what the threshold specifies.

### Business
The engine still receives fully resolved initiative specifications. What changes with the dynamic frontier is how and when those specifications are produced — not what the engine sees or how it operates. This is a deliberate architectural choice: the frontier mechanism adds complexity to the orchestration layer but does not change the engine's contract or behavior.

#### How new initiatives are realized: runner-side between-tick materialization

Frontier state is part of the simulation's world state for completeness and reproducibility, but the actual creation of new initiatives from that frontier is owned by the runner and occurs between review cycles. The runner may inspect the frontier state, generate additional resolved initiatives when a family's unassigned pool is depleted, append those new initiatives to the initiative list and the world's initiative states, and then hand the augmented world back to the engine for the next tick. The engine never calls generation logic and never owns the process of frontier realization.

This approach keeps the realized pool compact — the simulation creates new initiatives only when they are actually needed, rather than pre-generating thousands of initiatives that may never be used. It makes quality degradation concrete in the actually-generated attributes — a new initiative created from a degraded frontier simply has lower quality built into its specification, rather than the degradation being tracked as an abstract modifier. And it avoids the memory and complexity costs of pre-enumerating a large pool to cover every possible governance trajectory.

The change to the tick loop is localized to a single materialization step before the engine applies governance decisions. Everything downstream of that step operates exactly as it did under the fixed-pool design.

**Invariants preserved:**

- The engine's core functions never call generation logic. They advance the world forward given the current realized state and initiative specifications, exactly as before.
- Governance never generates initiatives. It decides what to do with the initiatives that exist; it does not create new ones.
- The runner's between-tick materialization is a documented, formal part of the simulation's cycle semantics — not a hidden side effect.

#### What the runner is allowed to do between ticks

Between review cycles (step 1 of the per-tick cycle), the runner may:

1. Read frontier state from the world state.
2. Read the current set of unassigned initiatives per family.
3. If a family's unassigned pool is below that family's replenishment threshold and the frontier is not exhausted, generate one or more new initiative specifications using the frontier's current quality distribution parameters and the family's type specification.
4. Create new dedicated random streams for the new initiatives, seeded from the world seed through the frontier's random stream. This preserves deterministic reproducibility.
5. Append the new initiative specifications to the initiative list.
6. Create new initiative state entries (unassigned, with initial beliefs) and append them to the world state.
7. Update frontier state in the world — increment resolved counts or frontier draw positions, update prize descriptor availability as applicable.

The runner must NOT:

- Modify existing initiative specifications or states. The runner creates new initiatives; it does not alter ones that already exist.
- Call engine functions. The runner materializes initiatives; the engine advances the simulation. These responsibilities do not overlap.
- Alter team states. Team assignment is a governance decision applied by the engine, not a runner-side operation.
- Read or use the hidden true quality from existing initiatives. The runner operates on frontier state and family-level parameters, not on the latent attributes of individual initiatives.
- Generate initiatives for families whose unassigned pool is at or above the replenishment threshold. Materialization occurs only when a family's pool is depleted below the threshold — the runner does not pre-fill pools or maintain buffers beyond what the threshold specifies.

## Canonical core update


### Academic
Invariant #6 in `canonical_core.md` ("Fixed pool") must be updated to:

> **Deterministic pool (canonical scope)** — The initiative pool is
> deterministically seeded from `world_seed`. In the canonical study,
> initiatives are drawn from family-specific frontier distributions whose
> parameters may shift as the run progresses. The realized pool for a
> given seed and governance trajectory is fully reproducible. Different
> governance trajectories may produce different realized pools because
> pool depletion and initiative stopping affect frontier state. Paired-
> seed comparability is preserved: for a given seed, the frontier's
> stochastic draws are deterministic given the governance-driven depletion
> history.

This is a material change to a canonical invariant. It relaxes the fixed-
pool-at-run-start assumption while preserving the deterministic-seeding
and reproducibility guarantees that the invariant was designed to protect.

The formal content of paired-seed comparability is: given `world_seed` w
and a deterministic governance trajectory τ (the complete sequence of
policy decisions across all ticks), the realized initiative pool, the
frontier evolution, and all simulation outcomes are fully determined by
(w, τ). Two runs sharing the same w and τ produce identical pools and
identical outcomes. Two runs sharing w but differing in τ produce pools
that diverge only as a consequence of governance differences — which is
the phenomenon under study. The invariant guarantees that cross-regime
outcome differences are attributable to the policy mapping, not to
uncontrolled sampling variation.

The relaxation is necessary because the fixed-pool assumption created an
experimental design confound (see Motivation). The dynamic frontier
eliminates that confound while preserving the CRN identification strategy
on which comparative analysis depends.

### Business
The sixth invariant in the canonical core — previously titled "Fixed pool" — must be updated to reflect the dynamic frontier. The updated invariant reads:

> **Deterministic pool (canonical scope)** — The initiative pool is deterministically seeded from the world seed. In the canonical study, initiatives are drawn from family-specific frontier distributions whose parameters may shift as the run progresses. The realized pool for a given seed and governance trajectory is fully reproducible. Different governance trajectories may produce different realized pools because pool depletion and initiative stopping affect frontier state. Paired-seed comparability is preserved: for a given seed, the frontier's stochastic draws are deterministic given the governance-driven depletion history.

This is a material change to a canonical invariant — it relaxes the assumption that the entire initiative pool is fixed before the simulation begins. What it preserves is the deeper guarantee that the invariant was designed to protect: deterministic seeding and full reproducibility. Given the same world seed and the same sequence of governance decisions, the simulation always produces exactly the same pool of initiatives, the same frontier evolution, and the same outcomes. The comparison between governance regimes remains controlled because paired-seed comparability holds — two runs with the same seed that make the same governance decisions produce identical pools, and two runs that make different decisions produce pools that diverge only as a consequence of those governance differences.

The relaxation is necessary because the fixed-pool assumption created an experimental design problem (as described in the Motivation section). The dynamic frontier solves that problem while preserving every reproducibility guarantee that the controlled comparison requires.

## Deterministic seeding and paired-seed comparability


### Academic
All frontier draws must be deterministic given `world_seed` and the
depletion history. This means:

1. **Per-family frontier RNG streams.** Each family gets a dedicated
   frontier RNG stream derived from `world_seed`. These are separate from
   the per-initiative signal RNG streams (which are indexed by
   `initiative_id`). The frontier stream for family F is used only for
   generating new initiatives of family F from the frontier. This
   separation ensures that frontier activity in one family cannot affect
   the random draws for another family or for the signal streams of
   existing initiatives.

2. **Draw ordering.** The k-th initiative drawn from family F's frontier
   always uses the k-th draw from family F's frontier RNG stream,
   regardless of what happens in other families. This preserves cross-
   family independence. It also preserves cross-regime draw-by-draw
   comparability: if one governance regime triggers three frontier draws
   for family F and another triggers five, both regimes receive identical
   draws for the first three — the additional draws in the second regime
   do not retroactively alter the shared prefix.

3. **Governance-trajectory dependence.** Because frontier state depends on
   which initiatives are stopped (affecting `n_resolved_by_family` and
   prize descriptor availability), different governance regimes may
   produce different frontier draws even with the same `world_seed`. This
   is the intended behavior: the frontier evolves as a function of
   governance-driven depletion. Paired-seed comparability means that the
   *same governance trajectory* produces the *same frontier draws* —
   not that different trajectories produce the same pool. The divergence
   in realized pools across regimes is a consequence of governance
   differences, which is the phenomenon the study is designed to measure.

4. **Substream allocation.** The pool-generator RNG (substream 0) is used
   for the initial pool as today. Frontier draws use additional substreams
   allocated per family: e.g., substream 1 for flywheel frontier, substream
   2 for right-tail frontier, substream 3 for enabler frontier, substream 4
   for quick-win frontier. The exact substream numbering is an
   implementation detail but must be documented in `noise.py` so that the
   reproducibility guarantee is auditable.

### Business
All frontier draws must be fully deterministic given the world seed and the history of governance-driven depletion. This is the same reproducibility discipline that governs per-initiative signal streams, extended to the frontier mechanism. The specific guarantees are:

1. **Each family gets its own dedicated frontier random stream.** These streams are derived from the world seed but are entirely separate from the per-initiative signal streams (which are indexed by initiative identifier). The frontier stream for a given family is used only for generating new initiatives of that family from the frontier. This separation ensures that frontier activity in one family cannot affect the random draws for another family or for the signal streams of existing initiatives.

2. **Draw ordering is deterministic within each family.** The first initiative drawn from a family's frontier always uses the first draw from that family's frontier stream, the second initiative uses the second draw, and so on — regardless of what has happened in other families. If one governance regime triggers three frontier draws for flywheels and another triggers five, both regimes see identical draws for the first three. This preserves cross-family independence: what happens in the right-tail frontier does not affect what happens in the flywheel frontier.

3. **Governance trajectory dependence is intentional.** Because frontier state depends on which initiatives are stopped (which affects how many initiatives of each family have been resolved and which prize descriptors are available), different governance regimes may produce different frontier draws even when operating from the same world seed. This is the intended behavior, not a comparability failure. The frontier evolves as a function of governance-driven depletion — an impatient regime that stops more initiatives depletes the frontier faster and faces a more degraded opportunity landscape. Paired-seed comparability means that the *same governance trajectory* always produces the *same frontier draws* — not that different trajectories produce the same pool. The divergence between regimes is a consequence of governance differences, which is exactly what the study is designed to measure.

4. **Random stream allocation is structured and documented.** The pool-generator random stream (used for the initial pool) occupies one allocation. Frontier draws use additional allocations, one per family — for example, one stream for the flywheel frontier, another for the right-tail frontier, another for the enabler frontier, and another for the quick-win frontier. The exact stream numbering is an implementation detail, but it must be documented in the random number generation module so that the reproducibility guarantee is auditable.

## State variables added to Markov state


### Academic
The following state variables are added to `WorldState` for Markov
completeness. These should also be added to the Markov state note
(`state_definition_and_markov_property.md`) when this design is
implemented.

#### Family-level frontier state

| Variable | Type | Description |
|----------|------|-------------|
| `frontier_state_by_family` | `dict[str, FamilyFrontierState]` | Map from `generation_tag` to compact frontier state. |

**FamilyFrontierState** (new frozen dataclass):

| Field | Type | Description |
|-------|------|-------------|
| `n_resolved` | `int` | Count of resolved (completed + stopped) initiatives of this family. |
| `n_frontier_draws` | `int` | Count of initiatives drawn from the frontier (for RNG position tracking). |
| `effective_alpha_multiplier` | `float` | Current quality degradation multiplier: `max(floor, 1.0 - rate * n_resolved)`. |

`effective_alpha_multiplier` is a derived convenience field, fully
determined by `n_resolved`, `frontier_degradation_rate`, and
`frontier_quality_floor`. It does not add an independent state dimension
but is stored explicitly for immediate access without recomputation.

`frontier_state_by_family` is stored as an immutable tuple of
`(generation_tag, FamilyFrontierState)` pairs, sorted by `generation_tag`
for deterministic iteration ordering, consistent with the simulation's
convention for all state collections.

#### Right-tail prize descriptor state

| Variable | Type | Description |
|----------|------|-------------|
| `available_prize_descriptors` | `tuple[PrizeDescriptor, ...]` | Available prizes from stopped right-tail initiatives. |

Per-prize state is carried in `PrizeDescriptor.attempt_count` (see
Section 2 above).

`available_prize_descriptors` is stored as a sorted tuple (sorted by
`prize_id`) for deterministic ordering.

#### Frontier RNG positions

Frontier RNG positions are deterministic given `world_seed` and
`n_frontier_draws`. They do not add independent state dimensions, for the
same reason that per-initiative RNG positions do not (see the Markov state
note, Section 4). For practical purposes (checkpointing, simulation
restart), the stream objects must be carried forward, but they do not
represent independent information beyond what is already recoverable from
the stored state and parameters.

### Business
The dynamic frontier introduces new state variables that must be tracked in the simulation's world state for completeness and reproducibility. These variables ensure that the simulation's future evolution is fully determined by its current state — the same property that holds for all other state in the simulation. These should also be added to the formal state definition document when this design is implemented.

#### Family-level frontier state

For each initiative family with an active frontier, the simulation tracks a compact state record containing:

- *Resolved count.* The number of initiatives of this family that have been resolved (completed or stopped) so far. This count drives the quality degradation mechanism — as more initiatives are resolved, the frontier's quality distribution shifts downward.

- *Frontier draw count.* The number of initiatives drawn from this family's frontier random stream. This is needed for reproducibility — given the world seed and the draw count, the exact sequence of future draws is fully determined. It also tracks the frontier stream's position so that the simulation can resume from any checkpoint.

- *Effective quality multiplier.* The current quality degradation factor, computed from the degradation rate and the resolved count, bounded by the quality floor. This is a derived convenience value — it could be recomputed from the resolved count and the configuration parameters — but tracking it explicitly makes the frontier's current state immediately visible without requiring the computation to be repeated.

The frontier state is stored as a collection of per-family records, sorted by family tag for deterministic ordering.

#### Right-tail prize descriptor state

For the right-tail family's prize-preserving refresh mechanism, the simulation tracks the set of available prize descriptors — prizes from stopped right-tail initiatives that are available for re-attempt. Each descriptor carries:

- A stable prize identifier linking it to the original initiative that created the prize.
- The persistent visible opportunity ceiling — the market opportunity that remains available.
- The attempt count — how many times the organization has tried to capture this prize, including the original attempt.

Per-prize state (specifically the attempt count) is carried within the prize descriptor itself, not in a separate tracking structure. This keeps the prize lifecycle self-contained.

The available prize descriptors are stored as a sorted tuple for deterministic ordering, consistent with the simulation's convention for all state collections.

#### Frontier random stream positions

Frontier random stream positions — the internal state of each family's frontier random number generator — are technically part of the simulation's complete state. However, they are fully deterministic given the world seed and the number of draws made from each stream. They do not add independent state dimensions beyond what is already tracked in the frontier draw counts. This is the same property that holds for per-initiative signal random streams: the stream positions are recoverable from the stored state and parameters, so they do not expand the state beyond what is already listed. For practical purposes (checkpointing, simulation restart), the stream objects must be carried forward, but they do not represent additional information that the simulation "knows" beyond its other state variables.

## Conductor controls


### Academic
The dynamic frontier introduces new conductor-level controls:

| Control | Layer | Description |
|---------|-------|-------------|
| `frontier_degradation_rate` | Environment | Per-family quality degradation rate. |
| `frontier_quality_floor` | Environment | Per-family minimum alpha multiplier. |
| `right_tail_refresh_quality_degradation` | Environment | Per-attempt quality degradation for right-tail prize refresh. |
| `family_opportunity_supply` | Environment | Named control for overall family-level frontier availability. Maps to per-family degradation rate and initial pool size. |

These are environment parameters, not governance parameters. They should
be exposed in the YAML authoring surface (`EnvironmentSpec` or a new
`FrontierSpec` within it) and held constant across governance regimes in
comparative experiments.

Detailed semantics of each control:

- `frontier_degradation_rate` — the coefficient in the `effective_alpha`
  computation: `effective_alpha = base_alpha * max(frontier_quality_floor,
  1.0 - frontier_degradation_rate * n_resolved)`. A higher rate accelerates
  quality degradation for that family. Configured per family to reflect
  family-specific opportunity landscape depth (canonical defaults: 0.01 for
  flywheel, 0.02 for quick-win, 0.005 for enabler).

- `frontier_quality_floor` — the lower bound on the `effective_alpha`
  multiplier (the `floor` in the `max(floor, ...)` expression). Prevents
  the Beta distribution from collapsing to a degenerate form. At the floor,
  the frontier still produces initiatives with non-trivial quality variance.
  Default: 0.1 for all families.

- `right_tail_refresh_quality_degradation` — optional per-failed-attempt
  degradation of the quality distribution for a specific prize descriptor.
  When zero (default), each re-attempt draws from the unmodified right-tail
  quality distribution. When positive, models the hypothesis that repeated
  failures carry information about inherent opportunity difficulty. This is
  a sensitivity parameter, not a canonical default assumption.

- `family_opportunity_supply` — a named orchestration control that maps to
  the combination of `frontier_degradation_rate` and initial pool size for
  a family. Provides a higher-level abstraction for experiment design:
  rather than setting degradation rate and pool size independently, the
  study designer specifies the overall richness of the opportunity
  environment for each family.

<!-- specification-gap: family_opportunity_supply: the mapping from this named control to concrete frontier_degradation_rate and initial_pool_size values is not formally defined — it is unclear whether this is an enum of named presets, a continuous parameter with a defined transformation, or a design-time convenience with no runtime representation -->

Any divergence in how the frontier evolves across governance regimes within
a single experimental comparison must be attributable to governance-driven
depletion trajectories, not to different frontier configurations. These
controls are set once per comparison and held fixed across all regimes
being tested.

### Business
The dynamic frontier introduces new controls that the study designer uses to configure how the opportunity landscape evolves. These are environment parameters — they describe the world the organization operates in, not the governance decisions the organization makes. In comparative experiments, they must be held constant across governance regimes, just like the initiative quality distributions, the attention-to-signal curve, and every other environmental characteristic.

| Control | Layer | Description |
|---------|-------|-------------|
| Frontier degradation rate | Environment | How quickly the quality of newly emerging opportunities declines per resolved initiative, configured separately for each family. A higher rate means the opportunity landscape deteriorates faster as the organization works through it. |
| Frontier quality floor | Environment | The minimum quality level the frontier can degrade to, configured per family. This prevents the quality distribution from collapsing entirely, ensuring that opportunities of some quality always remain available even after extensive depletion. |
| Right-tail refresh quality degradation | Environment | How much each failed attempt at a specific right-tail prize shifts the quality distribution downward for subsequent attempts at that prize. Zero means each new attempt draws from the original distribution; positive values model the possibility that repeated failures reveal inherent difficulty. |
| Family opportunity supply | Environment | A named control for the overall availability of opportunities within each family. Maps to the combination of the family's degradation rate and initial pool size, providing a higher-level lever for the study designer to characterize how rich or scarce a particular type of opportunity is in the simulated environment. |

These controls should be exposed in the study's configuration surface — either within the existing environment specification or in a new frontier specification attached to it — and documented alongside the other environment parameters. They are set once per experimental comparison and held fixed across all governance regimes being tested, so that any differences in how the frontier evolves across regimes are attributable to governance-driven depletion, not to different frontier configurations.

## Frontier modes


### Academic
The dynamic frontier supports two distinct modes, controlled by
configuration. These are different modes and should not be conflated.

**Fixed-pool mode:** Frontier materialization is disabled entirely. The
initial pool is the complete pool and no new initiatives are generated
during the run. This is equivalent to the pre-frontier behavior. Enabled
when `frontier_enabled` is false (or equivalent configuration flag). This
mode preserves full backward compatibility with experiments designed under
the fixed-pool assumption.

**Dynamic frontier mode:** Runner-side inter-tick materialization is
active. The runner generates new initiatives from family-specific frontier
distributions when a family's unassigned pool falls below its
replenishment threshold. Within dynamic mode, `frontier_degradation_rate`
controls whether quality degrades as the frontier is consumed:

- When `frontier_degradation_rate > 0`: quality degrades per resolved
  initiative (the intended canonical behavior for most families).
- When `frontier_degradation_rate = 0`: replenishment is active but
  quality does not degrade. New initiatives are drawn from the same
  distribution as the initial pool. This is non-degrading dynamic mode,
  not fixed-pool mode — new initiatives are still generated on demand.
  Non-degrading dynamic mode serves as a sensitivity analysis baseline
  to test whether comparative findings depend on the declining-quality
  assumption, and for modeling environments with an effectively deep
  opportunity landscape where quality does not degrade with consumption.

The distinction matters: zero degradation does not imply fixed-pool
semantics. It only implies non-degrading replenishment semantics. The two
modes produce different behavior for governance regimes that actively cycle
through initiatives: under fixed-pool mode, the pool can be exhausted
entirely; under non-degrading dynamic mode, it replenishes indefinitely at
the original quality level. Conflating them would obscure this difference.

### Business
The dynamic frontier supports two distinct operating modes, controlled by configuration. These modes are meaningfully different and should not be conflated.

**Fixed-pool mode.** Frontier materialization is disabled entirely. The initial pool of initiatives, resolved before the simulation begins, is the complete pool. No new initiatives are generated during the run. This is equivalent to the pre-frontier behavior and preserves full backward compatibility with experiments designed under the fixed-pool assumption. Enabled when the frontier is configured as disabled (or when no frontier specification is provided).

**Dynamic frontier mode.** Runner-side between-tick materialization is active. The runner generates new initiatives from family-specific frontier distributions when a family's unassigned pool falls below its replenishment threshold. Within dynamic frontier mode, the frontier degradation rate controls whether and how quality declines as the frontier is consumed:

- When the degradation rate is positive (the intended canonical behavior for most families), the quality of newly emerging opportunities declines as more initiatives are resolved. The opportunity landscape gets gradually less attractive as the organization works through its best possibilities.

- When the degradation rate is zero, replenishment is active but quality does not degrade. New initiatives are drawn from the same quality distribution as the initial pool, meaning the opportunity landscape remains just as attractive regardless of how many initiatives the organization has resolved. This is useful as a sensitivity analysis baseline — testing whether findings depend on the declining-quality assumption — or for modeling environments where the organization faces a genuinely deep landscape of equally attractive opportunities.

The distinction between zero-degradation dynamic mode and fixed-pool mode matters and should not be lost. Zero degradation does not mean the pool is fixed — it means the pool replenishes on demand without quality erosion. New initiatives are still generated when needed; they are simply drawn from an undegraded distribution. Fixed-pool mode means no new initiatives are generated at all, period. The two modes have different implications for how governance regimes that actively cycle through initiatives experience the later years of the simulation, and conflating them would obscure that difference.
