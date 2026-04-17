# Governance: Action space and policy interface

## Purpose

### Academic
Formalize the complete set of decisions a governance policy can make at a decision point (end-of-tick or review point), the information available to the policy, and the deterministic semantics the engine uses to apply those decisions.

Naming convention for this document:

- explanatory prose and pseudocode prefer descriptive names such as
  `quality_belief_t`, `execution_belief_t`, and `effective_tam_patience_window`,
- equations may still use compact notation such as $c_t$, $c_{\text{exec},t}$, and
  $T_{\text{tam}}$,
- the canonical mapping is recorded in `docs/study/naming_conventions.md`.

### Business
Define the complete set of decisions that governance can make at each decision point, the information available when making those decisions, and the precise rules the simulation follows when carrying out those decisions.

This document uses plain-language names throughout — for example, "strategic quality belief" rather than mathematical symbols. Where the technical specification uses compact notation, the mapping between the two is recorded in the project's naming conventions reference.

## Policy inputs (what the policy may see)

### Academic
The governance policy receives a `GovernanceObservation` bundle and a `GovernanceConfig`
object only. The canonical structures for both are defined in `interfaces.md`. The policy
must not receive `ModelConfig`, the full `SimulationConfiguration`, or any engine-internal
`WorldState`.

All mutable belief state (quality belief, execution belief), observable history, and
derived counters (such as `consecutive_reviews_below_tam_ratio` and
`staffed_tick_count`) are engine-owned and live in `InitiativeState`. They are
surfaced to the policy as read-only fields within `GovernanceObservation`. The
policy must not maintain private mutable copies of initiative state across ticks.

**The policy must not see latent quality or latent `true_duration_ticks`.** The policy may
use `quality_belief_t` ($c_t$), `execution_belief_t` ($c_{\text{exec},t}$), and `implied_duration_ticks` as
observable proxies. The derived observable `implied_duration_ticks` is provided
specifically so policies can reason about execution overrun in natural business units
rather than the normalized fidelity scalar.

### Business
At each decision point, governance receives two things: a snapshot of what is currently observable about the portfolio, and the fixed set of governance parameters that define the regime's decision rules.

Governance does not receive the full internal state of the simulation. It does not receive the parameters that govern how the simulated world evolves. It receives only what a real leadership team could plausibly know: observable attributes of each initiative, the organization's current beliefs about each initiative's quality and execution progress, and summary metrics about the portfolio as a whole.

All of the organization's evolving knowledge — its running estimate of each initiative's strategic quality, its estimate of execution progress, the history of reviews, and derived counters like how many consecutive reviews have fallen below a patience threshold — is maintained by the simulation engine. Governance sees these as read-only values in each decision snapshot. Governance does not maintain its own private records across decision points. This is a deliberate design choice: it ensures that every governance regime's decisions are fully explained by what it could see at the moment it decided, making the simulation reproducible and auditable.

**Governance never sees the true underlying quality of any initiative, and never sees how long an initiative will actually take.** It can only see the organization's current best estimate of strategic quality, its current best estimate of execution progress, and a derived projection of how long the initiative is expected to take based on what has been observed so far. That projection is provided specifically so governance can reason about schedule overruns in natural terms — "this initiative now looks like it will take three years instead of two" — rather than working with an abstract ratio.

## Governance architecture vs. operating policy

### Academic
This document is normative for **operating policy**: the recurring tick-by-tick
decisions a governance regime makes once a run is underway. The study also
distinguishes a higher-level layer called **governance architecture**, which
covers structural choices made before the run begins and then held fixed within
the run.

In the current study framing:

- **Governance architecture** includes team decomposition (how a fixed total
  labor endowment is partitioned into teams), ramp characteristics as modeled
  properties of that structure, and standing portfolio guardrails such as
  diversification or concentration targets.
- **Operating policy** includes stop/continue logic, team assignment choices,
  and executive-attention allocation on each tick.

The policy consumes architecture-level guardrails through `GovernanceConfig`
for backward compatibility, but the engine does not enforce them mechanically.
They are policy-read structural constraints, not engine invariants.

### Business
This document specifies **operating governance**: the recurring week-by-week decisions a governance regime makes once a simulation run is underway. The study also recognizes a higher-level layer called **governance architecture**, which covers structural choices made before the run begins and then held fixed throughout.

In the current study:

- **Governance architecture** includes how the total workforce is divided into teams, what ramp-up characteristics those teams have when assigned to new work, and any standing portfolio guardrails such as diversification targets or concentration limits. These are organizational design choices, not operating decisions.
- **Operating governance** includes which initiatives to continue or stop each week, which teams to assign to which initiatives, and how to allocate executive attention across active work. These are the recurring decisions that define a governance regime's behavior.

The operating policy can read the architecture-level guardrails — for example, it knows what diversification targets have been set — but the simulation engine does not mechanically enforce those guardrails. They are structural constraints that the policy is expected to honor, not hard rules that the engine imposes. This reflects how real organizations work: a board may set a portfolio concentration policy, but it is the executive team's operating decisions that either honor or violate it.

## Policy outputs (action vector at end-of-tick)

### Academic
The policy returns an *action vector* that the engine applies (effective next tick). The action vector is a set of action objects. Valid action classes:

#### 1. `ContinueStop` (per active initiative)
- `{ action: "ContinueStop", initiative_id: "X", decision: "continue" | "stop",
     triggering_rule?: str }`
- **`triggering_rule` is required when `decision == "stop"`**. Allowed values:
  `"tam_adequacy"` | `"stagnation"` | `"confidence_decline"` |
  `"execution_overrun"` | `"discretionary"`.
  - Use `triggering_rule="execution_overrun"` when the stop is driven purely by
    the execution-overrun signal path, e.g. execution belief falling below
    `exec_overrun_threshold` or equivalent policy logic based on
    `implied_duration_ticks`.
  - Use `triggering_rule="discretionary"` for mixed policy logic that is not
    identical to one canonical named rule.
  The engine records this field in the `StopEvent` payload defined in
  `review_and_reporting.md`. Omitting it from a stop action is a protocol
  violation. For `decision == "continue"`, the field must be absent or `None`.
- Semantics: if `"stop"`, initiative moves to `stopped` at the start of next tick and its team becomes free at start of next tick.

  **Residual and capability invariant**: a `Stop` action never triggers residual
  activation and never contributes portfolio capability, regardless of initiative
  type, how much work has been completed, or the initiative's
  `capability_contribution_scale` value. These are not edge cases or
  implementation details — they are load-bearing semantic distinctions in the
  study design. Stopping an initiative is the governance judgment that continued
  investment is no longer warranted. Completing an initiative is the engine
  detecting that bounded work has reached its natural end. Only the latter
  activates residual streams and portfolio capability. Policies may not override
  this invariant through any action or combination of actions.

#### 2. `SetExecAttention` (per initiative)
- `{ action: "SetExecAttention", initiative_id: "X", attention: a }`
- Canonical semantics:
  - $a = 0.0$ means the initiative receives no explicit executive attention on that
    tick.
  - $a > 0.0$ means the initiative is explicitly covered by attention on that tick.
  - If $a > 0.0$, then $a$ must lie within the effective per-initiative bounds:

    $$
    \text{attention\_min\_effective} \leq a \leq \text{attention\_max\_effective}
    $$
    where `attention_min_effective = attention_min` and
    `attention_max_effective = 1.0` if `attention_max is None`.
  - Silence is semantically meaningful: if an initiative is omitted from the
    `SetExecAttention` actions for a tick, its attention for that tick is exactly
    `0.0`. Prior attention does not persist.
  - This omission-means-zero contract is intentional. It keeps executive attention
    as an explicit per-tick policy output rather than hidden engine-owned state.
    A policy that wants steady attention on an initiative must emit that attention
    explicitly on every tick. This makes the action vector a complete statement of
    governance intent for that tick and avoids accidental carry-forward behavior
    when a policy forgets to include an initiative.
- Budget feasibility:

    $$
    \sum_i \text{attention}_i \leq \text{exec\_attention\_budget}
    $$

    over all `SetExecAttention` actions in the action vector for that tick.

#### 3. `AssignTeam`
- `{ action: "AssignTeam", team_id: "T", initiative_id: "X" | null }`
- Assign team `T` to initiative `X` for the next tick. `initiative_id=null` means leave team idle. Assignment only succeeds if `team_size >= initiative.required_team_size` and team is available at application time.
- Selection convention:
  - Governance selects only from initiatives currently in the `unassigned`
    lifecycle state.
  - The initiative pool is fixed at run start under the canonical design.
    There is no replacement or replenishment during a run unless a future
    extension adds it explicitly.
  - Once an initiative leaves `unassigned` by becoming active, stopped, or
    completed, it is no longer available as a fresh selection candidate.
- The engine never auto-assigns idle teams to unassigned initiatives. Governance
  silence about an unassigned initiative leaves it dormant; it does not constitute
  activation.

### Business
At each decision point, governance produces a complete set of decisions that the simulation engine carries out at the start of the following week. These decisions fall into three categories.

#### 1. Continue or stop each active initiative

For every initiative that is currently staffed and active, governance must make an explicit decision: continue investing, or stop. There is no option to abstain or defer. Every active initiative must receive a clear verdict.

When governance decides to stop an initiative, it must state why. The allowed reasons correspond to the study's canonical governance logic:

- **Prize inadequacy** — the bounded opportunity looks too small relative to the investment, and patience has run out.
- **Stagnation** — the initiative has stopped generating new information, and has not earned continued patience.
- **Confidence decline** — the organization's belief in the initiative's strategic quality has dropped below the threshold where continued investment is justified.
- **Execution overrun** — the initiative's execution has deteriorated badly enough to trigger a cost-based stop, independent of strategic conviction.
- **Discretionary** — the stop was driven by mixed considerations that do not map cleanly to one of the named rules above.

The simulation records this reason in the event log for every stop, enabling post-hoc analysis of what governance regimes actually do and why. Omitting a reason from a stop decision is a protocol violation.

**A stopped initiative forfeits all future value.** This is one of the most consequential design choices in the study. When governance stops an initiative:

- Any ongoing value stream it might have activated upon completion is permanently forfeited. The mechanism that would have kept producing returns after the team moved on never gets built.
- Any contribution to organizational capability — the improvement in the organization's ability to evaluate future work — is permanently forfeited.
- Any major-win discovery that might have been surfaced at completion is permanently forfeited.

There are no partial credits. Stopping an initiative is the governance judgment that continued investment is no longer warranted. Completing an initiative is the simulation's determination that bounded work has reached its natural end. Only completion activates value streams and capability contributions. This distinction is not an implementation detail — it is a load-bearing design choice that makes the consequences of stop decisions analytically visible. Governance cannot game this by stopping an initiative "just before" completion to capture most of the value; the study treats stopping and completing as fundamentally different outcomes.

#### 2. Allocate executive attention

For each initiative, governance sets a level of executive attention for the coming week. This is expressed as a fraction of the executive's available time.

Key rules governing attention allocation:

- **Zero attention is the default.** If governance does not explicitly assign attention to an initiative for a given week, that initiative receives zero executive attention. Prior attention does not carry forward. This is intentional: it forces governance to make an active, explicit commitment of attention every week rather than allowing initiatives to coast on attention that was assigned weeks ago and never revisited. A governance regime that wants steady attention on an initiative must say so every week.

- **Positive attention has a minimum threshold.** If governance chooses to give an initiative any attention at all, the amount must be at least the minimum meaningful level. Below that level, the model treats attention as actively harmful — shallow engagement that generates noise without generating insight. This reflects the study's position that a CEO who glances at a weekly status update may leave the team harder to evaluate than if leadership had stayed entirely out of it.

- **Total attention is budget-constrained.** The sum of attention allocated across all initiatives cannot exceed the executive's available time budget. Time spent going deep on one initiative is time unavailable for everything else.

- **Silence is meaningful.** Not assigning attention to an initiative is a real decision with real consequences. The initiative's signals will be noisier, and the organization's ability to learn about that initiative's true quality will be diminished.

#### 3. Assign teams to initiatives

Governance assigns available teams to unassigned initiatives from the pool. The simulation never automatically assigns teams — if governance does not explicitly assign a team to an initiative, that initiative remains unstaffed and dormant.

Key constraints:

- A team can only be assigned to an initiative if the team is large enough to meet the initiative's staffing requirements.
- Teams are indivisible. A team cannot be split across multiple initiatives.
- Governance can only assign teams to initiatives that are currently in the unassigned pool. Once an initiative has been activated, stopped, or completed, it is no longer available as a fresh assignment target.
- The initiative pool is fixed at the start of the run. There are no new initiatives appearing mid-run in the canonical study design.

## Review semantics (canonical)

### Academic
A **review** is a specific engine-defined event, not an informal synonym for "the
policy looked at this initiative."

1. At the end of each tick, after belief updates and engine-side counter updates,
   the engine invokes governance exactly once.
2. An initiative counts as **reviewed on tick t** iff, at that end-of-tick
   governance invocation, it is:
   - `lifecycle_state == "active"`, and
   - currently staffed (`assigned_team_id is not None`).
3. Every reviewed initiative must receive exactly one explicit
   `ContinueStop(continue)` or `ContinueStop(stop)` decision. There is no abstain
   option for reviewed initiatives.
4. `review_count` increments by 1 exactly on reviewed ticks and never increments
   otherwise.
5. `consecutive_reviews_below_tam_ratio` is updated by the engine **before** the
   policy is invoked on that tick, using the current end-of-tick strategic belief
   and `observable_ceiling` from that same review.
6. `consecutive_reviews_below_tam_ratio` resets to zero on:
   - any reviewed tick where the bounded-prize adequacy condition passes, and
   - any tick where the initiative is not reviewed (for example because it is
     paused/unassigned/stopped/completed).

This means the patience window is defined over **consecutive reviews**, not over
calendar ticks and not over lifetime history. A restaffed initiative begins a new
review streak for bounded-prize inadequacy rather than resuming an old streak
after a pause.

### Business
A **review** is a specific, precisely defined event in the simulation — not an informal term for "leadership looked at this initiative."

The rules are:

1. At the end of each week, after the organization's beliefs have been updated and all engine-maintained counters have been refreshed, governance is invoked exactly once.
2. An initiative counts as **reviewed** on a given week if and only if, at that end-of-week governance invocation, it is both active and currently staffed with a team.
3. Every reviewed initiative must receive an explicit continue-or-stop decision. There is no abstain option.
4. The initiative's review count increments by exactly one on reviewed weeks and never increments otherwise.
5. The engine updates the initiative's bounded-prize patience counter **before** governance is invoked, using the current end-of-week strategic belief and the initiative's visible opportunity ceiling.
6. The bounded-prize patience counter resets to zero whenever the initiative passes the adequacy test on a review, and also resets to zero on any week where the initiative is not reviewed — for example, because it is paused, unstaffed, stopped, or completed.

The practical consequence is that the patience window counts **consecutive reviews**, not calendar time and not the initiative's entire history. If an initiative is temporarily unstaffed and then restaffed, its bounded-prize patience counter starts fresh rather than resuming from where it left off. This means an initiative cannot accumulate patience strikes during a period when governance is not actually evaluating it.

## Selection and portfolio management semantics

### Academic
The canonical engine does **not** enforce portfolio diversification or portfolio
budgets. Those are governance-policy choices.

However, the canonical governance interface is allowed to express portfolio-risk
preferences in labor-share terms using observable quantities. The recommended
primitives are:

- current strategic quality belief,
- current execution belief,
- current active labor exposure,
- patience-state indicators already surfaced by the engine,
- and concentration of labor in individual initiatives.

This means a policy may express rules such as:

- "Do not allocate more than 20% of active labor to initiatives whose current
  quality belief is below X."
- "Do not allocate more than Y% of active labor to any one initiative."

These are governance-side controls only. The engine exposes the observation
state needed to compute them but does not enforce them mechanically.

In the current three-layer study framing, these are best understood as
**governance-architecture guardrails surfaced to the operating policy**. A
regime may honor them approximately or rebalance toward them periodically rather
than enforcing them exactly at every tick. The simulator's role is to expose the
state needed to support those choices, not to make them hard engine rules.

#### Ranking convention for bounded-prize selection

When a canonical archetype ranks **unassigned bounded-prize initiatives** using
expected value, it should normalize by `required_team_size`:

$$
\text{expected\_prize\_value\_density} = \frac{\text{expected\_prize\_value}}{\text{required\_team\_size}}
$$

This keeps labor exposure explicit during selection among unassigned
bounded-prize initiatives. It does **not** by itself define a canonical ranking
rule for initiatives without an observable bounded prize. Policies may define
such ranking logic explicitly if needed.

#### PortfolioSummary use

`GovernanceObservation.portfolio_summary` is a convenience aggregation that
supports policy-side portfolio checks. It does not replace the underlying
initiative observations as the source of truth.

#### Stop / Continue criteria (canonical)

Governance uses explicit stop/continue criteria built from observable quantities and beliefs. Two canonical, testable stop rules in scope are:

1. **Prize adequacy (bounded-prize patience condition)**

   - **Scope**
     - Applies only to initiatives where `observable_ceiling` is set. The rule
       answers the question "is the bounded prize large enough to matter," which is
       only meaningful when there is a discrete prize ceiling to evaluate.
       Initiatives without an observable bounded prize are not subject to this rule.

   - **Parameters**
     - $\theta_{\text{tam\_ratio}} \in [0,1]$: the fraction of `observable_ceiling` below which
       expected prize value is considered below the prize-relative patience
       condition.
     - $T_{\text{tam}}$ (integer): base patience window — the number of consecutive
       governance evaluations earned by an initiative whose
       `observable_ceiling == reference_ceiling`.
     - Realized bounded-prize patience scales linearly with visible upside:

       $$
       T_{\text{tam\_effective}} = \operatorname{max}\!\left(1,\; \lceil T_{\text{tam}} \cdot \frac{\text{observable\_ceiling}}{\text{reference\_ceiling}} \rceil\right)
       $$

       where `reference_ceiling` is a model-level normalization constant and
       $T_{\text{tam\_effective}}$ is surfaced to governance as
       `effective_tam_patience_window`.

   - **Definition (two-step persistence rule)**
     - At each review, compute expected prize value using the strategic quality
       belief only:

       $$
       \text{expected\_prize\_value} = \text{quality\_belief}_t \times \text{observable\_ceiling}
       $$

     - The engine updates `consecutive_reviews_below_tam_ratio` before the policy
       is invoked on that review.
     - If $\text{expected\_prize\_value} < \theta_{\text{tam\_ratio}} \times \text{observable\_ceiling}$, the counter increments
       by 1.
     - If $\text{expected\_prize\_value} \geq \theta_{\text{tam\_ratio}} \times \text{observable\_ceiling}$, the counter resets to
       zero.
     - **Stop rule:** recommend termination on the same review when
       $\text{consecutive\_reviews\_below\_tam\_ratio} \geq T_{\text{tam\_effective}}$.

   - **Interpretation**
     - This rule stops bounded-prize initiatives that have persistently failed to
       earn continued patience under the prize-relative bounded-prize rule.
     - The patience window is prize-relative: larger visible bounded opportunities
       earn more review patience than smaller ones.
     - `T_tam` is therefore a base patience parameter, not a one-size-fits-all
       absolute count.
     - Reset-on-recovery ensures that termination reflects persistent failure to
       earn continued patience rather than historical failures that have since
       been corrected.
     - Because the counter is updated before the policy acts, a stop may occur on
       the same review that causes the counter to reach `T_tam_effective`.
     - Quality belief here refers to the strategic quality belief only. Execution
       overrun is a separate signal tracked through execution belief and governed
       through `exec_overrun_threshold` in `GovernanceConfig`. A governance policy
       may additionally reduce its patience in response to deteriorating execution
       belief, but that is policy logic, not a canonical engine rule.

2. **Stagnation rule (informational stasis plus failure to earn continued patience)**

   - **Scope**
     - Applies to all initiatives, but the second leg of the conjunctive rule is
       defined differently depending on whether the initiative has an
       `observable_ceiling`.

   - **Parameters**
     - $W_{\text{stag}}$ (integer): window length in **staffed ticks** — ticks during which the
       initiative was assigned a team and generating observations. The engine maintains
       `staffed_tick_count` per initiative. Idle ticks between staffing assignments do
       not count and do not contribute to stagnation detection.
     - $\varepsilon_{\text{stag}}$ (float $> 0$): minimum net belief movement required to avoid being
       classified as informationally stagnant over the staffed-tick window.

   - **Definition (conjunctive rule)**

     Compute **informational stasis**:

     $$
     \Delta_c = |c_t - c_{t - W_{\text{stag}} \text{ staffed ticks}}|
     $$

     where quality belief is the current strategic belief and the prior value is the
     strategic belief $W_{\text{stag}}$ staffed ticks ago. If $\Delta_c < \varepsilon_{\text{stag}}$, the initiative
     is informationally stagnant.

     Compute the **second-leg patience condition**:

     - For bounded-prize initiatives (`observable_ceiling is not None`), the
       condition holds when `consecutive_reviews_below_tam_ratio > 0` at the
       current evaluation.
     - For initiatives without an observable bounded prize, the condition holds
       when:
       $$
       \text{quality\_belief}_t \leq \text{default\_initial\_quality\_belief}
       $$
       where `default_initial_quality_belief` is the canonical neutral baseline for
       quality belief surfaced in the observation/config contract.

     **Stop rule:** recommend termination only when **both** conditions hold
     simultaneously — informational stasis AND the relevant second-leg patience
     condition.

   - **Interpretation**
     - Stagnation occurs when the organization is neither learning anything new
       about the initiative's strategic quality nor seeing evidence that the
       initiative has earned continued patience under the relevant rule for its
       observable state.
       Either condition alone is insufficient.
     - An initiative with high stable belief is not stagnant — it is well understood
       and still appearing promising. The second-leg patience condition will not
       fire for such an initiative.
     - A bounded-prize initiative that is below its prize-relative patience condition
       but still producing meaningful belief movement should continue, because new
       information may rehabilitate its assessment.
     - A non-TAM initiative whose belief has stabilized above the canonical neutral
       baseline is not stagnant simply because it has stopped moving. The rule is
       designed to catch stale non-TAM work that has failed to earn stronger
       conviction than where the organization began.
     - The informational stasis statistic is **absolute net change** (endpoint
       difference over the window), not range. An initiative that oscillates noisily
       within the window without producing a durable shift in organizational conviction
       is genuinely stagnant from a governance standpoint. Net change captures this
       correctly; range does not.
     - **Sliding window implementation**: the engine maintains a ring buffer
       `belief_history` of length $W_{\text{stag}}$ per initiative. At each staffed tick,
       after appending the current quality belief, the engine retains only the most
       recent $W_{\text{stag}}$ strategic beliefs. The stagnation comparison is available once
       `len(belief_history) == W_stag`:

       $$
       \text{belief\_change\_over\_window} = |\text{quality\_belief}_t - \text{belief\_history}[0]|
       $$
       where `belief_history[0]` is the oldest retained quality belief in the
       rolling staffed-tick window. Informational stasis holds if
       `belief_change_over_window < stagnation_epsilon`.
       If $\text{belief\_change\_over\_window} < \varepsilon_{\text{stag}}$ for the current tick, the informational stagnation
       condition is met. The non-overlapping checkpoint interpretation — updating a
       single stored value every $W_{\text{stag}}$ ticks — is explicitly not used, because it
       misses stagnation events that begin partway through a window.

       This wording is intentional. The simulator uses a bounded rolling deque, not
       a lifetime-indexed history array. Referring to the oldest retained belief in
       the current window is therefore the most direct and least error-prone
       specification.
     - The stagnation rule operates on quality belief (strategic) only. Execution
       overrun does not contribute to informational stagnation; it is a separate
       governance signal available through execution belief.

   - **Interaction with confidence decline**
     - If $\text{confidence\_decline\_threshold} \geq \text{default\_initial\_quality\_belief}$, confidence decline may dominate
       the non-TAM stagnation path and make it unreachable in practice. Canonical
       configurations should avoid this unless that dominance is intentional.

   - **Policies using disjunction**
     - A policy that wishes to flag stagnation on informational stasis alone (without
       requiring the second-leg patience condition) may implement that logic explicitly in policy
       code. The conjunctive form is the canonical engine default. The policy should
       record the reason for every stop recommendation for later analysis.

3. **Confidence decline / discretionary stop threshold**

   Unlike the prize-adequacy and stagnation rules, which the engine evaluates and flags
   through explicit state/counters, confidence decline is a policy-side decision rule
   built directly from the strategic quality belief:

   **Observation-boundary note:** the canonical governance rules must be computable
   from `GovernanceObservation` alone. In the canonical interface this means:

   - `quality_belief_t` provides the strategic belief needed for confidence decline,
   - `execution_belief_t` provides the execution belief needed for cost-overrun
     policies.
   - `observable_ceiling` provides the bounded-prize ceiling needed for prize adequacy,
   - `staffed_tick_count` and `consecutive_reviews_below_tam_ratio` provide the
     engine-maintained review-window state needed for stagnation and patience rules.
   - `portfolio_summary` provides convenience aggregates for any policy-side
     labor-share exposure checks.

   $$
   \text{stop if } \text{quality\_belief}_t < \text{confidence\_decline\_threshold}
   $$

  - $\text{confidence\_decline\_threshold} \in [0,1]$ is a governance policy threshold, not an engine invariant.
    `confidence_decline_threshold = None` disables the rule entirely.
  - The policy reads `quality_belief_t` from `InitiativeObservation` and compares it against
    `confidence_decline_threshold` from `GovernanceConfig`. No engine flag is required.

  - **Interaction with other rules**
    - Governance may combine prize adequacy, stagnation, and confidence-decline signals
      in various combinations via policy logic. For example: stop if (prize inadequacy
      AND low execution belief), or stop if (confidence decline OR stagnation).
     - Only the two named engine-tracked rules above require canonical state
       maintenance (`consecutive_reviews_below_tam_ratio`, `belief_history`).
       Confidence decline does not require engine-side counters.

4. **Combined rule application**
   - Governance may combine prize adequacy, stagnation, and confidence-decline signals in
     various combinations via policy logic. For example: stop if (prize inadequacy AND
     stagnation) OR $\text{quality\_belief}_t < \text{confidence\_decline\_threshold}$.
   - The stagnation rule is internally conjunctive by canonical default (informational
     stasis AND the relevant second-leg patience condition must both hold). Policies wishing to use
     disjunctive stopping must implement that logic explicitly in policy code.
   - The policy should record the reason for every stop recommendation in the event
     log for later analysis and experiment comparison.

   **Worked example (bounded-prize adequacy from observation only):**
   ```
   if obs.observable_ceiling is not None:
       expected_prize_value = obs.quality_belief_t * obs.observable_ceiling
       threshold = tam_threshold_ratio * obs.observable_ceiling
       if (
           expected_prize_value < threshold
           and obs.consecutive_reviews_below_tam_ratio >= obs.effective_tam_patience_window
       ):
           emit ContinueStop(stop, triggering_rule="tam_adequacy")
   ```

**Operational notes**
- All stop/continue logic must be based on **observable state and beliefs** only.
  Policies must not use latent quality or latent `true_duration_ticks`. Policies may use
  `quality_belief_t` ($c_t$), `execution_belief_t` ($c_{\text{exec},t}$),
  `implied_duration_ticks`,
  `consecutive_reviews_below_tam_ratio`, `staffed_tick_count`, and any other
  observable fields provided in `GovernanceObservation`.
- Policies must not rely on hidden initiative labels, latent uncertainty classes, or
  unobserved type-specific fields. Canonical policy logic must be expressible using
  only the observation bundle defined in `interfaces.md` plus the immutable
  parameters in `GovernanceConfig`.
- The engine applies `Stop` at the start of the next tick as per the main tick ordering (a stop at end-of-tick `t` frees the team at start-of-`t+1`).

### Business
The simulation engine does **not** mechanically enforce portfolio diversification rules or portfolio budgets. Those are governance-policy choices — the policy decides whether and how to honor them, and the engine provides the information needed to do so.

The information available for portfolio management decisions includes:

- Each initiative's current strategic quality belief — how promising it currently looks.
- Each initiative's current execution belief — how well it is tracking to plan.
- The current labor exposure across the portfolio — how many people are working on what.
- Patience-state indicators already maintained by the engine — how close an initiative is to triggering a stop rule.
- Concentration of labor in individual initiatives — whether any single initiative is consuming a disproportionate share of the workforce.

Using these observables, a governance policy can express rules such as:

- "Do not allocate more than 20% of active labor to initiatives whose current strategic conviction is below a certain level."
- "Do not allow any single initiative to consume more than a certain percentage of the workforce."

These are governance-side controls. The engine exposes the portfolio state needed to evaluate them, but does not enforce them. This is a deliberate design choice. In the study's three-layer framework, these rules are best understood as **governance-architecture guardrails surfaced to the operating policy**. A regime might honor them approximately or rebalance toward them periodically rather than enforcing them rigidly at every decision point — just as real organizations treat portfolio guidelines as directional rather than absolute.

#### How governance ranks opportunities for team assignment

When a governance regime is choosing among unassigned bounded-prize initiatives — opportunities where the visible upside ceiling is known — the canonical ranking normalizes by staffing requirements:

$$
\text{Expected value per unit of labor} = \frac{\text{current quality belief} \times \text{visible opportunity ceiling}}{\text{required team size}}
$$

This keeps labor exposure explicit when comparing opportunities that require different amounts of workforce investment. A large opportunity that requires a large team is not automatically preferred over a smaller opportunity that requires fewer people — the comparison is made on a per-unit-of-labor basis.

This ranking convention applies specifically to bounded-prize initiatives. For initiatives without a visible opportunity ceiling, governance policies may define their own ranking logic as needed.

#### Portfolio summary as a convenience tool

The observation snapshot includes a portfolio summary block that aggregates key metrics — total active labor, labor allocated to low-conviction work, maximum concentration in any single initiative. This is a convenience for governance policies implementing portfolio checks. It does not replace the underlying initiative-level observations as the authoritative source of information.

#### When governance stops an initiative: the four canonical rules

Governance uses explicit stop criteria built from observable quantities and beliefs. Two rules require the engine to maintain specific counters; the other two are pure policy-side evaluations.

1. **Prize adequacy (bounded-prize patience)**

   - **When it applies:** Only to initiatives where governance can see a ceiling on potential value — a bounded opportunity. The rule answers the question "is this bounded prize large enough to justify continued investment?" which only makes sense when there is a visible ceiling to evaluate against.

   - **How it works:**
     - At each review, governance computes the expected prize value using its current belief about the initiative's quality:

       $$
       \text{Expected prize value} = \text{current strategic quality belief} \times \text{visible opportunity ceiling}
       $$

     - If that expected value falls below a threshold fraction of the opportunity ceiling, the initiative has failed the adequacy test for that review.
     - The engine tracks how many consecutive reviews the initiative has failed this test. If the initiative passes the test on any review, the counter resets to zero.
     - Governance recommends termination when the initiative has failed the adequacy test for enough consecutive reviews to exhaust its patience.

   - **How patience scales:** Larger visible opportunities earn more patience. The patience window scales linearly with the size of the opportunity relative to a reference benchmark. An initiative with twice the visible upside ceiling gets roughly twice the review patience before the inadequacy trigger fires. This reflects the intuition that a larger prize justifies more investment in trying to determine whether the initiative is good enough to capture it.

   - **Key properties:**
     - The patience window counts consecutive reviews, not calendar time. An initiative that is temporarily unstaffed does not accumulate strikes during the gap.
     - Reset-on-recovery means that termination reflects persistent failure to earn continued patience, not historical failures that have since been corrected. If an initiative's prospects improve enough to pass the adequacy test, its strike counter resets, and it earns a fresh window.
     - A stop can occur on the same review that causes the counter to reach the patience threshold. The engine updates the counter before governance makes its decision.
     - Only the strategic quality belief enters this calculation. Execution overrun is a separate concern handled through execution belief and a different governance threshold. A policy may additionally reduce its patience in response to deteriorating execution estimates, but that is a policy design choice, not part of this canonical rule.

2. **Stagnation (informational stasis plus failure to earn continued patience)**

   - **When it applies:** To all initiatives, but the second condition of the rule works differently depending on whether the initiative has a visible opportunity ceiling.

   - **How it works (two conditions, both must hold):**

     The first condition is **informational stasis**: the organization's belief about the initiative's strategic quality has not moved meaningfully over a sustained window of active work. The window is measured in staffed weeks — weeks during which the initiative actually had a team working on it and producing signals. Weeks when the initiative was sitting idle between team assignments do not count.

     Specifically, governance compares the current strategic quality belief to the belief that existed at the start of the window (the oldest retained belief in the rolling window). If the absolute change is smaller than a minimum threshold, the initiative is informationally stagnant — the organization is not learning anything new about whether this initiative is worth pursuing.

     The second condition depends on the initiative's observable state:

     - For bounded-prize initiatives (those with a visible opportunity ceiling): the initiative must also currently be failing the prize adequacy test — its bounded-prize patience counter must be above zero.
     - For initiatives without a visible opportunity ceiling: the initiative's current strategic quality belief must be at or below the neutral starting point — the organization has not developed stronger conviction than where it began.

     **Governance recommends termination only when both conditions hold simultaneously.** Either condition alone is insufficient.

   - **Why both conditions are required:**
     - An initiative with high, stable belief is not stagnant — it is well understood and still looks promising. The second condition will not fire for such an initiative, even though its belief has stopped moving.
     - A bounded-prize initiative that is currently failing the adequacy test but still producing meaningful belief movement should continue, because new information may rehabilitate its assessment.
     - A non-bounded-prize initiative whose belief has stabilized above the neutral baseline is not stagnant simply because it has stopped moving. The stagnation rule is designed to catch stale work that has failed to develop conviction beyond the starting point, not to penalize initiatives that have reached a stable and positive assessment.
     - The measure of informational stasis uses the absolute net change over the window (how far the belief has actually moved from start to end), not the range of fluctuation. An initiative whose belief bounces around noisily within the window without producing a durable shift in organizational conviction is genuinely stagnant from a governance standpoint. Net change captures this correctly; range of fluctuation does not.

   - **How the window works:** The engine maintains a rolling buffer of strategic quality beliefs for each initiative, recording one entry per staffed week. The buffer retains the most recent entries spanning the configured window length. The stagnation comparison becomes available once the buffer is full. This is a sliding window — it continuously evaluates the most recent period of active work, not periodic snapshots taken at fixed intervals. The sliding approach catches stagnation events that begin partway through any fixed checkpoint interval.

   - **Interaction with confidence decline:** If the confidence decline threshold is set at or above the neutral starting point, the confidence decline rule may trigger before the stagnation rule ever has a chance to fire for non-bounded-prize initiatives. Canonical configurations should be aware of this interaction and avoid it unless the dominance is intentional.

   - **Policy flexibility:** A governance regime that wants to flag stagnation based on informational stasis alone — without requiring the second condition — may implement that logic explicitly. The two-condition form is the canonical default. Whatever the policy does, it should record the reason for every stop recommendation for later analysis.

   - **Scope limitation:** The stagnation rule evaluates strategic quality belief only. Execution overrun is a separate governance concern handled through the execution belief signal, not through the stagnation mechanism.

3. **Confidence decline**

   Unlike the prize adequacy and stagnation rules, which require the engine to maintain specific counters, confidence decline is a straightforward policy-side check:

   *Stop if the organization's current strategic quality belief has fallen below the confidence decline threshold.*

   This is a governance parameter, not an engine rule. Setting the threshold to a higher value makes governance more willing to cut losses early; setting it lower makes governance more patient. Disabling the threshold entirely (setting it to null) removes this stop path.

   **What governance needs to evaluate all four rules:** The canonical stop rules can be fully evaluated using only the information in the observation snapshot:

   - The strategic quality belief provides the input for confidence decline.
   - The execution belief provides the input for cost-overrun policies.
   - The visible opportunity ceiling provides the input for prize adequacy.
   - The staffed-week count and consecutive-reviews-below-patience counter provide the engine-maintained window state for stagnation and prize patience rules.
   - The portfolio summary provides the convenience aggregates for any labor-share exposure checks the policy wants to apply.

4. **Combined rule application**

   Governance regimes may combine these rules in whatever logical structure fits their design philosophy. For example: stop if prize inadequacy has triggered, or if the strategic belief has dropped below the confidence decline threshold, or if both stagnation conditions are met. The stagnation rule is internally conjunctive by default (both informational stasis and failure to earn continued patience must hold), but a policy that wants a looser stagnation trigger can implement that explicitly.

   Whatever combination a regime uses, it should record the reason for every stop decision in the event log so that post-hoc analysis can distinguish why different regimes stopped different initiatives.

   **Concrete example of how prize adequacy works from the observation snapshot:**

   If an initiative has a visible opportunity ceiling, governance computes the expected prize value from its current strategic quality belief. If that expected value is below the adequacy threshold, and the initiative has failed this test for at least as many consecutive reviews as its patience window allows, governance stops the initiative and records "prize inadequacy" as the reason.

**Rules that apply to all stop decisions:**

- All stop logic must be based on observable state and beliefs only. Governance must never use the true underlying quality, the true duration, hidden initiative labels, or any information not present in the observation snapshot.
- Governance decisions must be expressible using only the observation snapshot and the fixed governance parameters. No hidden information, no private memory, no backdoor access to simulation internals.
- When governance decides to stop an initiative, the stop takes effect at the start of the following week. The team is freed at that point, consistent with the study's action-timing rules.

## Execution belief and cost tolerance

### Academic
When an initiative has `planned_duration_ticks` and `true_duration_ticks` set, governance
receives two execution-related observables in the observation bundle:

- `execution_belief_t` ($c_{\text{exec},t}$): governance's posterior belief about schedule fidelity
  relative to plan. $1.0$ means the initiative is believed to be tracking
  exactly to plan; values below $1.0$ indicate a projected overrun. Initialized to the
  planning prior ($\text{initial\_c\_exec\_0}$)
  (the planning prior, not certainty).
- `implied_duration_ticks`: a derived observable computed as
  $\text{round}(\text{planned\_duration\_ticks}\; /\; \operatorname{max}(c_{\text{exec},t},\; \varepsilon))$. This translates the normalized
  fidelity belief into business-interpretable units — the current best estimate of how
  long the initiative will take — so that policy logic and reporting can reason in terms
  of actual durations rather than a ratio scalar.

These observables are independent of the strategic quality belief. Governance
policies may condition stop decisions on execution belief independently of strategic
conviction. This is the mechanism by which the study represents governance regimes with
different tolerances for cost escalation.

The canonical stop rules (prize adequacy and stagnation) operate on quality belief only.
Governance responses to execution overrun are expressed entirely through policy
logic, using execution belief, `implied_duration_ticks`, and `exec_overrun_threshold`
as inputs. The engine does not automatically stop
initiatives for execution overrun. When a policy stops an initiative for pure
execution-overrun reasons, it should record
`triggering_rule="execution_overrun"`. If the stop is driven by mixed logic that
cannot be cleanly attributed to one named rule, it should record
`triggering_rule="discretionary"`.

### Business
Alongside its evolving view of whether an initiative is strategically sound, governance receives a separate, independent stream of evidence about whether execution is tracking to plan. Two pieces of information are available each week for any initiative with an execution timeline:

- **Schedule fidelity belief.** The organization's running estimate of how well the initiative is tracking against its original plan. A value of 1.0 means the initiative appears to be exactly on schedule. Values below 1.0 indicate a projected overrun — the further below 1.0, the worse the projected slippage. This estimate starts at the planning prior — the organization's initial assessment of the plan's realism — rather than at certainty, because no plan is assumed to be perfectly accurate from day one.

- **Implied completion time.** A translation of the schedule fidelity belief into concrete time units — the current best estimate of how long the initiative will actually take to complete. If the plan says 18 months and the fidelity belief has drifted to 0.75, the implied completion time is roughly 24 months. This translation exists so that governance can reason in terms of actual calendar durations rather than abstract ratios. It is what a program manager would report when asked "so when do we actually think this will be done?"

These two signals are entirely independent of the strategic quality assessment. An initiative can look strategically excellent — the organization's confidence in its underlying value remains high — while simultaneously showing significant schedule slippage. Conversely, an initiative can be tracking perfectly to plan while the organization's confidence in its strategic merit is deteriorating. The model treats these as separate dimensions of evidence because that is how they work in practice: the question of whether something is worth doing and the question of whether it is being done well are different questions with different evidence bases.

The study's canonical stop rules — bounded-prize patience, stagnation, and confidence decline — operate exclusively on the strategic quality belief. They answer the question "is this initiative still worth pursuing?" The execution signal answers a different question: "is this initiative costing more than we expected?" Whether and how to act on cost escalation is left entirely to governance policy. The simulation engine never automatically stops an initiative for running over budget or over schedule. This is deliberate: it means the study can compare governance regimes that respond to cost escalation in fundamentally different ways, without the engine presupposing which response is correct.

Three distinct governance postures toward cost escalation are representable:

- A **cost-tolerant, conviction-driven regime** continues as long as quality belief
  remains above threshold, treating execution belief as informational context but not
  as a trigger, up to a maximum encoded in `exec_overrun_threshold`.
- A **cost-sensitive regime** treats execution belief falling below
  `exec_overrun_threshold` as a stopping signal even when quality belief remains high.
- A **conviction-driven regime without a cap** ignores execution belief entirely.
  Its stopping behavior is governed exclusively by the strategic-channel stop
  logic (bounded-prize patience where applicable, stagnation, and confidence
  decline).

This design preserves the study's neutrality: the engine provides both signals without
encoding a normative response to either. The study can therefore compare regimes that
differ in cost-overrun sensitivity without presupposing which governance philosophy
produces better long-run outcomes.

When a governance regime does stop an initiative primarily because of cost escalation rather than loss of strategic conviction, that reason is recorded explicitly in the stop event. If the decision was driven by a mix of strategic and cost concerns that cannot be cleanly separated — as is often the case in real governance — the stop is recorded as a discretionary judgment call rather than being forced into a single category. This distinction matters for analysis: it lets the study trace whether a governance regime's termination pattern was driven by loss of faith in what initiatives were trying to achieve, by loss of patience with what they were costing, or by some combination of the two.

## Budget and feasibility constraints

### Academic
The engine enforces the following constraints on the action vector:

1. Attention values must lie in $[0,1]$.
2. Team assignments must respect availability and size constraints.
3. Total attention requested across all `SetExecAttention` actions must not exceed
   `exec_attention_budget`.
4. Any positive attention assignment must satisfy the effective per-initiative
   bounds:
   If $\text{attention} > 0$:

   $$
   \text{attention\_min\_effective} \leq \text{attention} \leq \text{attention\_max\_effective}
   $$

   where `attention_min_effective = attention_min`, and
   `attention_max_effective = 1.0` if `attention_max is None`.

If any positive per-initiative attention bound is violated, or if requested total
attention exceeds budget, the canonical engine behavior is:

1. Reject the entire proposed attention allocation for that tick.
2. Set attention for all initiatives named in `SetExecAttention` actions on that
   tick to `attention_min_effective`.
3. Emit an `attention_feasibility_violation_event` in the run log.

This default is chosen because dropping to zero attention would create artificial
signal collapse from a budgeting mistake rather than from an intended governance
choice.

Silence is not a `SetExecAttention` action. An initiative omitted from the
`SetExecAttention` action vector receives `0.0` attention on that tick. The engine
does not maintain persistent attention state across ticks.

### Business
The simulation engine enforces the following hard constraints on governance decisions:

1. **Attention values must be between zero and one.** No initiative can receive more than 100% of the executive's available time, and attention cannot be negative.

2. **Team assignments must respect availability and size.** A team can only be assigned if it is currently available and large enough for the initiative's requirements.

3. **Total attention cannot exceed the executive's time budget.** The sum of attention allocated across all initiatives for a given week cannot exceed the hard weekly limit.

4. **Positive attention must meet the minimum threshold.** If governance chooses to give any attention to an initiative, the amount must be at least the minimum meaningful level. Below that level, the model treats attention as harmful rather than merely ineffective.

**What happens when governance violates the attention budget:**

If the proposed attention allocation for a week either exceeds the total budget or includes any individual assignment outside the allowed bounds, the engine:

1. Rejects the entire proposed attention allocation for that week — not just the offending assignments, but all of them.
2. Sets attention for every initiative that was named in the proposed allocation to the minimum meaningful level.
3. Records the violation in the run log.

**Why the fallback is minimum attention rather than zero:** Zero attention would amplify signal noise for every affected initiative and could trigger stop rules through what amounts to an accounting error rather than a genuine deterioration in the organization's assessment. Minimum attention represents the lowest operationally meaningful level and is a less destructive fallback. This is why the minimum attention threshold is required to exist in the canonical study — it serves as a safety floor.

An initiative that governance does not mention in its attention allocation for a given week receives zero attention. This is not a violation — it is a deliberate governance choice. The violation handling applies only when governance explicitly names an initiative but proposes an infeasible allocation.

Well-designed governance policies should avoid budget violations by computing their total allocation against the available budget before submitting decisions.

## Baseline work semantics

### Academic

Teams not assigned to portfolio initiatives are not wasted: they are on
*baseline*, performing routine maintenance, operational work, customer
support, incremental process improvements, and other productive
non-portfolio activity. When `ModelConfig.baseline_value_per_tick` is
set, each unassigned team accrues that amount per tick as runner-side
accounting, surfaced on `RunResult.cumulative_baseline_value`. The
engine itself does not consume this field; baseline work has no
signals, no learning, no capability contribution, no completion
mechanics.

Baseline value changes the substantive framing of governance decisions.
Without it, "do not staff" is indistinguishable from "waste a team,"
which unfairly penalizes a regime that rationally holds back from
marginal portfolio candidates. With baseline value, the decision
becomes: *is this initiative worth pulling a team off baseline
work?* That is the opportunity-cost framing organizations actually
face.

The default is `0.0` (opt-in): studies that want to credit baseline
work declare it explicitly. The calibrated nonzero value is
`0.1/tick` per `calibration_note.md`. A `0.0` baseline value reduces
to the legacy "idle = zero value" semantics and preserves comparability
with bundles produced before the field existed.

The intake screening signal (per `initiative_model.md` and decision 24)
pairs naturally with baseline value: screening gives governance
pre-execution information that a given initiative is likely worse than
baseline, and the hold-back decision becomes observable as a
governance behavior. Without screening, the flat default prior would
make baseline-versus-portfolio tradeoffs arbitrary at t=0.

Per design_decisions.md decision 23.

### Business

Teams that are not assigned to portfolio initiatives are not idle in
any meaningful business sense. They are doing the routine work that
keeps the organization running: maintenance, operational improvements,
customer support, process work. This baseline activity produces value
at a steady rate, independent of what the portfolio is doing.

The simulator represents this by accruing a small per-team value
(`baseline_value_per_tick`) for each unassigned team each tick. That
amount can be zero (the default, for studies that want to compare
against the "idle teams produce nothing" assumption), or a modest
positive number — the calibrated value is `0.1` per tick — when the
study wants to credit baseline work.

Treating unassigned teams as productive changes what the study can
observe. Without baseline value, a governance regime that holds back
from marginal portfolio initiatives looks wasteful: it "left teams
idle" and therefore produced less. With baseline value, that same
regime is rationally choosing routine operations over speculative
investment, which is a substantively meaningful governance decision
that organizations actually make. The study needs to be able to
observe that decision, not penalize it.

## Deterministic application order (engine)

### Academic
When the engine applies a policy's action vector at start-of-tick `t`, it does so in this order:

1. **Apply ContinueStop** for all initiatives. Mark `stopped` initiatives, free their teams at start-of-tick.
2. **Apply AssignTeam** actions (ordered): assign available teams to target initiatives, observing `team_size` constraints and `no-splitting`. If an `AssignTeam` references a team that is already assigned (or not available), the engine rejects that action.
3. **Apply SetExecAttention** and check $\sum \text{attention} \leq B$.

   **Attention-feasibility violation handling (canonical default: reject and clamp
   to `attention_min_effective`):** if the proposed `SetExecAttention` actions for
   a tick either:

   - exceed `exec_attention_budget`, or
   - include any positive assignment outside the effective per-initiative bounds,

   the engine:

   1. Rejects the entire proposed attention allocation for that tick.
   2. Sets attention for all initiatives named in `SetExecAttention` actions on that
      tick to `attention_min_effective`.
   3. Emits an `attention_feasibility_violation_event`:
      ```
      { tick, policy_id, requested_total, budget_limit,
        affected_initiative_ids, fallback_attention_applied,
        violation_kind }
      ```

   **Rationale for `attention_min_effective` (not zero):** zero attention would amplify
   signal noise for affected initiatives and could trigger stop rules through
   a budget accounting error rather than genuine belief deterioration.
   `attention_min_effective` represents the lowest operationally meaningful attention
   level and is a less destructive fallback than zero. In the canonical study,
   this rationale is load-bearing rather than optional, which is why
   `attention_min` is required to be non-null.

   Policies should avoid budget violations by computing total allocation
   against `GovernanceConfig.exec_attention_budget` before submitting actions.

**Effect-Timing rule**: Actions applied at start-of-tick `t` control the behavior for that tick (observations and value production in step `t` use those settings).

### Business
When the simulation engine carries out governance's decisions at the start of each week, it follows a strict, deterministic sequence:

1. **First: execute all continue/stop decisions.** Initiatives marked for stopping transition to the stopped state, and their teams are freed.
2. **Second: execute team assignments in order.** Available teams are assigned to their target initiatives, respecting size constraints and the rule that teams are indivisible. If multiple assignments target the same team, the engine executes the first one and rejects the rest, recording the rejections in the run manifest.
3. **Third: apply executive attention allocations and verify budget feasibility.** If the total proposed attention exceeds the budget, or any individual assignment violates the per-initiative bounds, the engine rejects the entire attention allocation for that week and falls back to minimum attention for all named initiatives, as described above. The details of the violation — what was proposed, what the budget was, which initiatives were affected, and what fallback was applied — are recorded in the run log.

**Timing rule:** Decisions applied at the start of a given week control what happens during that week. Observations generated and value produced during the week reflect those settings. This means a team assigned at the start of week 10 generates its first observations in week 10, and attention set at the start of week 10 governs the signal quality for week 10's observations.

## Canonical experiment posture on budget binding

### Academic
In the main governance sweep, hidden budget binding is not desirable. The canonical
experimental intent is that differences in realized attention come from policy
choices, not from frequent engine-side rejection/clamping events. Therefore:

- the main governance sweep should set `exec_attention_budget` high enough that
  feasibility violations are rare,
- any study of scarce-attention regimes where the budget is expected to bind should
  be run as a separate, explicitly labeled environmental-budget experiment.

### Business
In the main governance comparison experiment, the study does not want the executive attention budget to be a frequent binding constraint. The intent is that differences in how much attention different initiatives receive should come from governance choices — deliberate decisions about where to focus — not from the engine repeatedly rejecting and clamping attention proposals because the budget is too tight.

Therefore:

- The main governance comparison should set the executive attention budget high enough that budget violations are rare events, not routine occurrences.
- Any study of what happens when executive attention is genuinely scarce — where the budget is expected to bind regularly — should be run as a separate, explicitly labeled experiment focused on that question.

This separation keeps the main comparative findings clean. In the main experiment, attention differences between regimes reflect governance philosophy. In the scarce-attention experiment, attention differences reflect resource constraints. Mixing the two would make it impossible to attribute attention patterns to governance choices versus budget constraints.

### Zero-budget special case

`exec_attention_budget = 0.0` is a valid governance configuration representing
an executive who allocates no time to initiative oversight. When the budget is
zero:

- The policy should emit no `SetExecAttention` actions. Per the omission-means-zero
  contract (§SetExecAttention above), all initiatives receive attention = 0.0.
- `attention_min = 0.0` is valid in this configuration (see interfaces.md
  validation rules). The usual `attention_min > 0` constraint applies only when
  the budget is positive.
- The attention curve `g(a)` still applies at `a = 0`. Signal quality is
  determined entirely by `g(0)` and the base noise parameters. If the attention
  noise modifier is configured so that `g(0) = 1.0` (e.g., by setting
  `min_attention_noise_modifier = max_attention_noise_modifier = 1.0`), then
  attention has no effect on signal quality — the "attention off" configuration.
- This configuration is useful for simplified model variants that isolate
  governance decisions other than attention allocation (e.g., portfolio selection).

## Conflict resolution

### Academic
- If multiple actions attempt illegal changes (e.g., assign same team twice), the engine enforces a **deterministic priority order**: `ContinueStop` → `AssignTeam` (first come first served by action order) → `SetExecAttention`. If `AssignTeam` targets the same team multiple times, the engine executes the earliest action and rejects later ones; rejections are recorded in the run manifest.

### Business
When multiple governance decisions conflict — for example, two assignments targeting the same team — the engine resolves them using a deterministic priority order:

1. **Continue/stop decisions** are processed first.
2. **Team assignments** are processed next, in the order they appear. If two assignments target the same team, the first one wins and the second is rejected.
3. **Executive attention allocations** are processed last.

All rejections are recorded in the run manifest so that post-hoc analysis can identify whether a governance regime's decisions were consistently feasible or frequently required engine intervention.

## Policy interface

### Academic
This document defines the canonical governance action schema and semantics. The policy
consumes `GovernanceObservation` and `GovernanceConfig`, both defined in `interfaces.md`,
and returns a `GovernanceActions` vector whose structure and semantics are defined here.

The canonical protocol form, consistent with `interfaces.md` and `architecture.md`:

```python
class GovernancePolicy(Protocol):
    def decide(
        self,
        observation: GovernanceObservation,
        config: GovernanceConfig,
    ) -> GovernanceActions:
        ...
```

`GovernanceObservation` is the complete policy-visible bundle constructed by the engine at
each tick, as defined in `interfaces.md`. `GovernanceConfig` is the immutable governance
parameter block from `SimulationConfiguration`. The policy must not receive any other
engine state.

### Business
This document defines what governance can decide and how those decisions work. The governance policy takes in the observation snapshot (what the organization can see) and the governance parameters (the regime's configured thresholds and rules), and produces a complete set of decisions for that week.

The formal structure is:

- **Input:** the observation snapshot of the portfolio's current observable state, plus the immutable governance configuration.
- **Output:** a complete action vector specifying continue/stop decisions for every active staffed initiative, team assignments, and executive attention allocations.

The policy must not receive any information beyond the observation snapshot and the governance configuration. It does not see the full simulation state, the model parameters that govern how the world evolves, or any other engine internals. This boundary is fundamental to the study's design — it ensures that governance decisions are based only on what a real leadership team could plausibly know.

## Example action vector (JSON)

### Academic
```
[
  {"action":"ContinueStop", "initiative_id":"I-17", "decision":"stop",
   "triggering_rule":"confidence_decline"},
  {"action":"AssignTeam", "team_id":"team-3", "initiative_id":"I-42"},
  {"action":"SetExecAttention", "initiative_id":"I-42", "attention":0.35},
  {"action":"SetExecAttention", "initiative_id":"I-4", "attention":0.15}
]
```

### Business
A concrete example of a week's governance decisions:

- Stop initiative I-17 because strategic confidence has dropped below threshold.
- Assign team 3 to initiative I-42.
- Give initiative I-42 35% of executive attention this week.
- Give initiative I-4 15% of executive attention this week.

All other active initiatives receive zero executive attention this week (the default). All other teams retain their current assignments or remain idle.

## Implementation notes

### Academic
- **No direct mid-stream reallocation**: teams can only move to a new initiative as the result of a stop or at assignment time; reassigning a currently-staffed initiative's team to another requires a stop of the former.
- **Team splitting forbidden**: a team is atomic and cannot be fractionally assigned.
- **The engine invokes the policy every tick.** For every active staffed initiative,
  the policy must emit either `ContinueStop(continue)` or `ContinueStop(stop)`.
  There is no abstain option. Effective review depth is a behavioral property of
  the policy's internal logic: a policy implementing variable scrutiny does so by
  varying how it computes its stop/continue decision, not by omitting initiatives
  from the action vector.
- `review_count` therefore measures actual end-of-tick governance evaluations for
  active staffed initiatives, not mere initiative age or staffing duration.

### Business
- **Teams cannot be directly reassigned mid-stream.** If governance wants to move a team from one initiative to another, it must first stop the initiative the team is currently working on. The team becomes available at the start of the next week and can then be assigned to something new. There is no "swap" or "transfer" action — only stop (which frees the team) and assign (which deploys a free team).
- **Teams are indivisible.** A team cannot be split across multiple initiatives or fractionally assigned.
- **Governance is invoked every week.** For every active staffed initiative, governance must produce an explicit continue-or-stop decision. There is no abstain option. If a governance regime wants to vary how deeply it scrutinizes different initiatives — paying close attention to some and giving others only a cursory glance — it does so by varying how it computes its decision, not by skipping initiatives in the action vector. Every active staffed initiative must appear with a verdict.
- **Review count measures actual governance evaluations.** The number of reviews an initiative has received counts the number of end-of-week governance decision points where the initiative was both active and staffed. It does not measure the initiative's age, how long it has been staffed, or any other proxy. This ensures that governance evaluation frequency is precisely tracked for analysis.

## Example governance pseudocode (high level)

### Academic
```
function run_review(observation: GovernanceObservation, config: GovernanceConfig):
    # Every active staffed initiative must receive an explicit ContinueStop decision.
    # There is no abstain option; omitting an initiative from the action vector is
    # a protocol violation.
    active_staffed = [i for i in observation.initiatives
                      if i.lifecycle_state == "active" and i.assigned_team_id is not None]
    for i in active_staffed:
        if stop_rule(i, config):
            # triggering_rule is required; set to the canonical reason string
            # ("tam_adequacy", "stagnation", "confidence_decline", "discretionary")
            actions.append(ContinueStop(i.initiative_id, "stop",
                                        triggering_rule=determine_rule(i, config)))
        else:
            actions.append(ContinueStop(i.initiative_id, "continue"))
    freed_teams = estimate_freed_teams_after_stops(actions, observation.teams)
    for team in freed_teams:
        candidate = choose_best_unassigned(observation.initiatives)
        if candidate:
            actions.append(AssignTeam(team.team_id, candidate.initiative_id))
    active_after_stops = [i for i in active_staffed
                          if not stopped_this_tick(i.initiative_id, actions)]
    allocations = allocate_attention(active_after_stops, config)
    for (i, a) in allocations:
        actions.append(SetExecAttention(i.initiative_id, a))
    return actions
```

This file is the normative specification of governance. Policies should be engineered, tested and versioned as external modules that produce the action_vector above.

### Business
The following illustrates the structure of a governance decision cycle in plain terms:

1. **Identify all initiatives that require a decision this week.** These are the initiatives that are currently active and staffed with a team. Every one of them must receive an explicit continue-or-stop verdict.

2. **Evaluate each initiative against the stop rules.** For each initiative requiring a decision, determine whether any of the canonical stop criteria have been met — confidence decline, prize inadequacy, stagnation, or execution overrun. If a stop is warranted, record the specific reason. If no stop criteria are met, the decision is to continue.

3. **Identify teams that will become available from stop decisions.** Any initiative that is being stopped will free its team at the start of the next week.

4. **Assign newly freed teams to the best available unassigned initiatives.** Look at the pool of initiatives that have not yet been assigned a team, rank them according to the governance regime's selection criteria, and assign freed teams to the best candidates.

5. **Allocate executive attention across the portfolio.** For all initiatives that will remain active after this week's stop decisions, determine how much executive attention each one should receive, subject to the total budget constraint.

6. **Package all decisions into the action vector and submit.** The simulation engine will apply these decisions at the start of the next week.

This document is the authoritative specification of what governance can do and how those decisions work. Governance policies themselves should be designed, tested, and versioned as separate modules that produce the action vector described above.
