# Core simulator and tick semantics

## Overview

### Academic
The simulator implements a partially observable sequential decision process with a one-period information delay. The governance policy observes end-of-tick state and emits an action vector; those actions alter the system only at the start of the next tick. Within any single tick, governance cannot observe the consequences of its current actions — the policy is a pure function of the observation bundle, not of the pending action vector. This delay is the minimal temporal structure needed to separate observation from intervention in the governance comparison.

The core simulator executes a sequence of discrete ticks. At each tick the engine:
1. Applies governance actions decided at the end of the previous tick (start-of-tick effect).
2. Runs staffed initiatives to produce noisy observations.
3. Updates beliefs, lifecycle state, and all mutable initiative state (completion detection, residual activation, capability update, completion-time major-win events).
4. Realizes residual value using end-of-tick state.
5. Records outputs and end-of-tick events.

Governance actions decided at end-of-tick $T$ become effective at the start of $T{+}1$ unless explicitly stated otherwise.

Naming convention for this document:

- explanatory prose uses descriptive names such as `quality_belief_t`,
  `execution_belief_t`, `latent_quality`, `effective_signal_st_dev_t`, and
  `base_tam_patience_window`,
- equations may still use compact symbols such as $c_t$, $c_{\text{exec},t}$, $q$,
  $\sigma_{\text{eff}}$, and $T_{\text{tam}}$,
- see `docs/study/naming_conventions.md` for the canonical mapping.

### Business
The simulation runs one week at a time. Each week follows a fixed sequence that mirrors the rhythm of a real governance cycle:

1. **Last week's decisions take effect.** Stop orders, team assignments, and attention allocations that governance decided at the end of the previous week become the new reality at the start of this week.
2. **Every staffed initiative generates new evidence.** Teams do their work and produce two kinds of signals: evidence about whether the initiative is strategically sound, and evidence about whether execution is tracking to plan. Both are imperfect.
3. **The organization updates its beliefs and detects completions.** Based on the new evidence, the organization's running estimates of each initiative's strategic promise and execution health are revised. If any initiative has actually finished, the simulation detects that now — realizing any one-time completion value, activating any ongoing value mechanism, recording any major-win discovery, and updating organizational capability.
4. **Ongoing value mechanisms produce their weekly returns.** Every initiative that previously completed and activated a persistent value stream — a distribution network, an automation system, a compounding platform — contributes this week's value, regardless of whether a team is still assigned to it.
5. **Everything is recorded** and the week advances.

Decisions made at the end of one week take effect at the start of the next. This one-week delay is a fundamental property of the model: governance acts on what it observed, and those actions shape the following week's reality. There is no same-week course correction.

## Tick ordering (deterministic)

### Academic
At tick $t$ the engine executes a deterministic sequence. **Key invariant (canonical — end-of-tick value realization):**
> All value for tick $t$ is realized after all belief updates and lifecycle transitions for tick $t$ have completed. Realized value formulas use true-world quantities (e.g., $q$) and initiative parameters — not belief scalars — so this ordering introduces no look-ahead bias.

Canonical sequence at tick $t$:

1. **Apply governance actions** decided at end-of-$t{-}1$ (start-of-tick effect). These actions (stop/continue, team assignment, exec attention settings) control staffing and attention for tick $t$.
2. **Apply new assignments and initialize assignment-relative state**: for each
   new assignment effective at the start of tick $t$, initialize
   `ticks_since_assignment = 0` on that initiative before the tick's production
   step. This value is read by the ramp formula *before* it is incremented in
   step 3. The ramp multiplier for tick $t$ is therefore computed using
   $t_{\text{elapsed}} = \text{ticks\_since\_assignment}$ at its pre-increment value of 0 on the
   first staffed tick.
3. **Production & observation**: for every staffed initiative, the engine samples two
   independent observation streams and increments both staffed clocks.

   *Strategic quality signal:*

   $$y_t \sim \mathcal{N}\!\bigl(q,\; \sigma_{\text{eff}}(d, a, C_t)^2\bigr)$$

   where latent quality ($q$) is the initiative's strategic quality and the effective
   signal st\_dev ($\sigma_{\text{eff}}$) is the attention- and dependency-modulated observation
   standard deviation (see below).

   *Execution progress signal* (only for initiatives where `true_duration_ticks` is set):

   $$z_t \sim \mathcal{N}\!\bigl(q_{\text{exec}},\; \sigma_{\text{exec}}^2\bigr)$$

   where

   $$q_{\text{exec}} = \operatorname{min}\!\bigl(1.0,\; \text{planned\_duration\_ticks} \,/\, \text{true\_duration\_ticks}\bigr)$$

   $\sigma_{\text{exec}}$ is a `ModelConfig` parameter shared across all initiatives.

   **Attention asymmetry (intentional design decision):** the execution signal is
   *not* modulated by executive attention, unlike the strategic quality signal.
   Strategic quality is difficult to observe and requires focused leadership inquiry
   to resolve. Execution progress is directly observable from elapsed time, milestone
   delivery, staffing burn rate, and similar operational signals that accumulate
   regardless of how much attention leadership is devoting to the initiative. This
   asymmetry is a deliberate modeling choice, not an omission.

   Its downstream consequence for comparative analysis: governance regimes that stop
   initiatives primarily for execution overruns benefit from the model's assumption
   that execution progress is always observable regardless of attention allocation.
   In settings where schedule slippage goes undetected absent active monitoring,
   such regimes would appear less effective than they do in this model. This is a
   known directional bias, symmetric across regimes sharing the same world.

   **Stationarity assumption (deliberate scoping decision):** Latent execution
   fidelity ($q_{\text{exec}}$) is fixed at generation. The model represents governance *gradually inferring* a fixed but
   initially unknown execution difficulty, not a project whose scope or difficulty
   genuinely changes midstream. This is a simplification. Real initiatives can experience genuine scope change.
   That mechanism is out of canonical scope for this study.

   *Staffed tick counter:* increment `staffed_tick_count` by 1 for each staffed
   initiative this tick.

   *Assignment-relative staffed tick counter:* increment `ticks_since_assignment`
   by 1 for each staffed initiative this tick. This increment happens *after*
   the ramp multiplier has been read by step 5's belief update formula. The
   post-increment value is what governance observes in `InitiativeObservation`
   at end-of-tick.

   Two distinct clocks are maintained per initiative. The lifetime staffed-tick
   counter (`staffed_tick_count`) accumulates across all assignments over the
   initiative's entire lifetime and is used for completion detection, progress
   fraction computation, and the stagnation window. The assignment-relative counter
   (`ticks_since_assignment`) resets to 0 on each new team assignment and is used
   exclusively for the ramp multiplier computation. These clocks serve different
   purposes and must not be confused or substituted for one another.

   *Progress fraction* (for initiatives with `true_duration_ticks` set):

   $$\text{progress\_fraction} = \operatorname{min}\!\bigl(\text{staffed\_tick\_count} \,/\, \text{planned\_duration\_ticks},\; 1.0\bigr)$$
   For initiatives without `true_duration_ticks` (unbounded duration): `progress_fraction = None`.
   The formula uses `planned_duration_ticks` (the original estimate), not
   `implied_duration_ticks` (the dynamically revised estimate), because
   governance-visible progress should reflect deviation from the original plan.
   An initiative overrunning its plan shows `progress_fraction = 1.0`, signaling
   to the policy that it is past its expected completion.

   `progress_fraction` is a derived observation field, not mutable state. It is
   computed at the observation boundary (when building `InitiativeObservation`)
   from `staffed_tick_count` and `planned_duration_ticks`, both of which are
   carried on `InitiativeState`. The engine does not store it separately.

   Raw observations ($y_t$ and $z_t$ where applicable) are drawn this step and
   fed into the belief updates in step 5. They are ephemeral intermediates, not
   persisted on initiative state. The `belief_history` tuple (maintained for
   stagnation detection) records quality beliefs, not raw signals.
4. **Value realization deferred (end-of-tick model)**: no value is realized at this step. All value realization for tick $t$ occurs after belief updates and lifecycle transitions have completed. Completion-lump value is realized in step 5c at the completion transition; residual value is realized in step 6.
5. **Belief update**: the engine updates both belief
   scalars.

   In this section, the compact symbols map to the following descriptive names:
   $c_t$ = `quality_belief_t`, $c_{\text{exec},t}$ = `execution_belief_t`,
   $q$ = `latent_quality`, $\sigma_{\text{eff}}$ = `effective_signal_st_dev_t`.

   *Strategic quality belief update:*

   $$c_{t+1} = \operatorname{clamp}\!\bigl( c_t + \eta \cdot \text{staffing\_multiplier}_t \cdot \text{ramp\_multiplier}_t \cdot L(d) \cdot (y_t - c_t),\; 0,\; 1 \bigr)$$

   - The base learning rate ($\eta$) is a ModelConfig parameter.
   - $\text{staffing\_multiplier}_t$ captures the effect of staffing intensity on
     learning. When the assigned team is larger than the initiative's minimum
     staffing threshold (`required_team_size`), additional staffing accelerates
     learning with diminishing returns:

     $$\text{staffing\_multiplier}_t = 1.0 + \text{staffing\_response\_scale} \times \bigl(1.0 - \text{required\_team\_size} \,/\, \text{assigned\_team\_size}\bigr)$$

     When `staffing_response_scale` $= 0.0$ (the default), the multiplier is
     exactly $1.0$ regardless of team size, preserving backward compatibility.
     `staffing_response_scale` is a per-initiative study parameter expressing a
     modeled hypothesis about how strongly learning responds to additional
     staffing, not an empirical truth. See `team_and_resources.md` for the
     full staffing intensity semantics.
   - $\text{ramp\_multiplier}_t = 1.0$ unless the initiative is currently in ramp, in
     which case it is the assignment-relative ramp multiplier defined below.
   - The dependency-adjusted learning efficiency $L(d)$ uses the initiative's
     immutable dependency attribute.
   - This update is attention- and dependency-modulated because strategic quality is
     difficult to observe and its clarity depends on how much focused leadership
     inquiry is applied.
   - Quality belief initializes at $c_0 = \text{initial\_belief\_c0}$, defaulting to $0.5$ —
     the symmetric midpoint of the $[0, 1]$ belief domain. This represents maximum
     prior uncertainty: the decision-maker begins with no information favoring
     high or low latent quality. The initialization is symmetric about the
     midpoint by design, so the prior does not bias the belief trajectory toward
     either boundary.

   *Execution belief update* (only for initiatives where `true_duration_ticks` is set):

   $$c_{\text{exec},t+1} = \operatorname{clamp}\!\bigl( c_{\text{exec},t} + \eta_{\text{exec}} \cdot (z_t - c_{\text{exec},t}),\; 0,\; 1 \bigr)$$

   - The execution learning rate ($\eta_{\text{exec}}$) is a ModelConfig parameter.
   - This update is **not** modulated by $L(d)$ or executive attention. See the
     attention asymmetry note in step 3.
   - Execution belief initializes to the planning prior (`initial_c_exec_0`),
     configurable per initiative, defaulting to $1.0$.
   - **Initialization boundary note:** Execution belief initializes to the planning
     prior (default $1.0$). For on-plan initiatives (latent execution fidelity $1.0$),
     the execution-progress signal $z_t$ exceeds $1.0$ with ${\sim}50\%$ probability and is
     clamped, while negative deviations are unclamped. This produces systematic
     downward drift in execution belief over time even for genuinely on-plan
     initiatives. The bias is consistent across all governance regimes sharing the
     same world seed and does not differentially affect comparative findings. It is
     documented as a known modeling assumption rather than corrected by changing the
     initialization.
   - Execution belief is a belief about schedule fidelity relative to plan, not a
     direct estimate of completion time. A value of $1.0$ means governance currently believes
     the initiative will run on plan; a value of $0.5$ means governance believes it will
     take approximately twice as long as planned. The derived observable
    `implied_duration_ticks` in `GovernanceObservation` translates this belief back
into business-interpretable units for use in policy logic and reporting.

5b. **Review-state update (before governance invocation)**:

    After belief updates for tick $t$ are complete, and before governance is
    invoked at the end of tick $t$, the engine updates per-initiative review
    state using the end-of-tick quality belief ($c_t$).

    For each initiative:

    - If the initiative is in `lifecycle_state == "active"` and is currently staffed
      (`assigned_team_id is not None`), then that initiative is considered
      **reviewed on tick $t$**.
    - For reviewed initiatives, increment:

      $$\text{review\_count} = \text{review\_count} + 1$$

    - For reviewed initiatives with `observable_ceiling is not None`, evaluate the
      bounded-prize adequacy test using the current end-of-tick
      quality belief from this same review:

      $$\mathbb{E}[v_{\text{prize}}] = c_t \times \text{observable\_ceiling}$$

      If $\mathbb{E}[v_{\text{prize}}] < \theta_{\text{tam\_ratio}} \times \text{observable\_ceiling}$, increment
      `consecutive_reviews_below_tam_ratio` by 1; otherwise reset it to 0.
    - For all initiatives that are **not** reviewed on tick $t$, reset
      `consecutive_reviews_below_tam_ratio = 0`.

    Governance therefore sees `review_count` and
    `consecutive_reviews_below_tam_ratio` **after** the current tick's review-state
    update and may stop on the same review that caused a counter to reach threshold.

5c. **Completion detection and capability update**: for every bounded initiative
    where `true_duration_ticks` is set, `lifecycle_state == "active"`, and
    `staffed_tick_count >= true_duration_ticks`, the engine:
    - transitions the initiative to `completed`,
    - records a completion event containing `initiative_id`, `tick`,
      latent quality, and `cumulative_labor_invested`,
    - if `value_channels.completion_lump.enabled == true`, realizes the configured
      one-time completion lump exactly once at this transition,
    - if `value_channels.major_win_event.enabled == true` and
      `value_channels.major_win_event.is_major_win == true`, records a structured
      `MajorWinEvent`,
    - if `value_channels.residual.enabled == true` and
      `value_channels.residual.activation_state == "completed"`, sets
      `residual_activated = true` and records `residual_activation_tick`,
    - **Team release**: set `team.assigned_initiative_id = None`, effective at start of
      tick $t{+}1$. The completing initiative's team is available for reassignment
      beginning at the governance step of tick $t{+}1$.
    - if `capability_contribution_scale > 0`, records that initiative's
      completion-time capability gain:

      $$\Delta C_i = q_i \cdot \text{capability\_contribution\_scale}_i$$

      for inclusion in the portfolio capability update after all completion
      transitions on tick $t$ have been processed.

    After all completion transitions on tick $t$ have been processed, the engine
    aggregates the completion-time capability gains:

    $$\Delta C_{\text{completion},t} = \sum_i \Delta C_i$$

    over all initiatives completing on tick $t$ with
    $\text{capability\_contribution\_scale}_i > 0$, and then updates portfolio capability:

    $$C_{t+1} = \operatorname{clamp}\!\Bigl( 1.0 + (C_t - 1.0) \cdot \exp(-\text{capability\_decay}) + \Delta C_{\text{completion},t},\; 1.0,\; C_{\max} \Bigr)$$

    where $\text{capability\_decay} \geq 0$ is the model-level per-tick exponential decay
    rate for the excess capability stock above baseline.

    This update order is intentional. Existing capability stock decays first, and
    new completion gains are then added without being immediately decayed on the
    same tick. That makes new enabler gains fully available when they first take
    effect at $t{+}1$, while still ensuring that previously accumulated advantage
    erodes over time.

    For right-tail initiatives, the canonical study treats the major-win outcome as
    a completion-time event derived from an immutable hidden generator-assigned flag
    rather than as a pre-completion lifecycle transition. The engine does not enter
    a separate `viable_discovered` state.

    The `is_major_win` flag is assigned at generation as a deterministic threshold
    function of latent quality: $\text{is\_major\_win} = (q \geq q_{\text{major\_win\_threshold}})$. It
    is hidden from governance throughout the run. There is no intermediate discovery
    state — major-win status is revealed only at completion, and only through the
    emitted `MajorWinEvent`. The engine does not spawn follow-on initiatives or
    price downstream economics of a major-win discovery within the horizon.

    Capability updates take effect at $C_{t+1}$, meaning initiatives completing at
    tick $t$ experience the updated capability starting at tick $t{+}1$, consistent
    with the general action-timing invariant. Residual activation takes effect
    immediately: an initiative whose residual activates at step 5c is included in
    the residual pass at step 6 of the same tick.

    **Horizon note**: the simulation horizon is a measurement boundary, not a
    lifecycle event. When the tick counter reaches `tick_horizon`, no additional
    lifecycle transitions are induced by horizon expiry. Initiatives still in
    `active` state at the final tick remain `active`. Their terminal state —
    including lifecycle status, current beliefs, staffed progress, active residual
    flags if any, and current portfolio capability — is recorded as part of
    the run output. Residual activation occurs only if an initiative actually
    reached its configured activation trigger (`completed`)
    during the run. An initiative still `active` at the horizon boundary does not
    activate residual.

    Two regimes may produce similar cumulative economic value while one has multiple
    active initiatives with healthy belief trajectories still running at the horizon
    and the other has none. This difference in terminal portfolio composition is
    analytically significant and is preserved in the run output.

6. **End-of-tick residual value pass**: for every initiative where
   `residual_activated == true`, realize residual value according to the residual
   channel parameters, regardless of whether the initiative is currently staffed.
   Residual persists after completion.

   Completion-lump value is realized only once, at the completion transition in
   step 5c, and is not repeated here. In the tick that residual first activates at
   completion, this pass fires in the same tick; that is correct and must not be
   suppressed.

7. **Record outputs & metrics** and advance to next tick. Governance sees the
   updated quality belief and all end-of-tick state/event outputs when it
   performs its end-of-tick review; governance decisions formed at end-of-tick
   $t$ take effect at start of tick $t{+}1$.

**Learning efficiency $L(d)$ (canonical default)**

The canonical closed-form default, applied to immutable initiative dependency:

$$L(d) = 1 - d$$

This is the canonical linear form (learning efficiency decreases linearly with
dependency level $d$). Implementations may parameterize alternative forms,
but $L(d) = 1 - d$ is the default.

Boundary cases: at $d = 0$ (no external dependencies), $L(0) = 1.0$ and the
belief update achieves full learning efficiency — the innovation term
$(y_t - c_t)$ enters the update at full scale. At $d = 1$ (maximum dependency),
$L(1) = 0.0$ and the belief update receives zero weight from the observation,
regardless of signal quality, staffing intensity, or attention allocation. In
this limit, observations carry no information about the initiative's intrinsic
strategic quality because outcomes are entirely determined by exogenous factors.
Intermediate values of $d$ produce proportional attenuation of the effective
learning rate, capturing the property that partially dependent initiatives
generate signals that are an unresolvable mixture of intrinsic quality and
exogenous noise.

### Business
Each week unfolds in a fixed, predictable order. This ordering matters because it determines what information is available when, what consequences follow from decisions, and where value is actually realized. One design principle governs the entire sequence: **all value for a given week is realized only after the organization has fully updated its beliefs and detected any completions.** Because realized value depends on the initiative's true underlying quality and its configured parameters — not on the organization's beliefs — this ordering does not create any informational advantage or distortion. The organization never acts on value it has not yet earned.

**The weekly governance cycle, step by step:**

**1. Last week's decisions take effect.** All governance decisions from the end of the prior week — which initiatives to continue or stop, which teams to assign where, how much executive attention to allocate to each initiative — become the operational reality at the start of this week. These decisions control which initiatives are staffed and how much attention each receives for the entire week.

**2. New team assignments are initialized.** When a team is newly assigned to an initiative this week, the simulation marks the start of a transition period. The team's time-on-assignment clock begins at zero. This clock is read by the ramp productivity formula before being advanced, which means the ramp calculation for the team's very first week on the initiative correctly reflects that they have just arrived.

**3. Every staffed initiative generates new evidence.** This is the week's primary information event. Two independent streams of evidence accumulate:

*Evidence about strategic quality.* Each staffed initiative produces a signal about how strategically valuable it actually is. This signal is centered on the initiative's true quality but includes noise. The amount of noise depends on the interplay of three factors: how dependent the initiative is on factors outside the team's control, how much executive attention leadership is devoting to it, and how much organizational learning capability has been built through prior enabler completions. These factors are described in detail in the sections on effective noise and portfolio capability below.

*Evidence about execution progress.* Separately, each initiative with a defined timeline generates a signal about whether it is tracking to its original plan. This signal centers on the initiative's true execution fidelity — the ratio of planned duration to actual duration — and includes its own noise, drawn from a shared noise level that applies to all initiatives equally.

**Attention asymmetry (deliberate design choice).** The execution signal is not affected by executive attention, unlike the strategic quality signal. Strategic quality is inherently difficult to assess and genuinely benefits from focused leadership inquiry to resolve. Execution progress is directly observable from elapsed time, milestone delivery, staffing burn rate, and similar operational signals that accumulate regardless of how closely leadership is watching. A CFO can tell whether a project is burning through its budget ahead of schedule by reading a monthly report. Whether that project is strategically sound requires the kind of hands-on engagement that only comes from dedicated attention. This asymmetry is deliberate. Its practical consequence is that governance regimes that stop initiatives primarily for cost overruns will look somewhat more effective in the model than they would in reality, where schedule slips often go undetected precisely because no one is paying close attention.

**Fixed execution difficulty (deliberate scoping decision).** The model assumes that each initiative's true execution difficulty is fixed from the start — it does not change during the course of the work. What changes is the organization's understanding of that difficulty, which improves as evidence accumulates week by week.

The Kindle scenario, in the model's terms, is that Amazon gradually learned that the initiative had always been harder than the original plan reflected — not that the initiative became harder during execution. This is a simplification. Real initiatives can experience genuine scope change. That mechanism is out of canonical scope for this study.

*Staffed-time tracking.* Two separate clocks advance for each staffed initiative. The lifetime staffed-time clock counts every week the initiative has had a team assigned, across all assignments over its entire life. This clock is used for completion detection, progress tracking, and stagnation assessment. The assignment-relative clock counts weeks since the current team was assigned and is used only for the ramp productivity calculation. These clocks serve different purposes and must not be confused.

*Progress tracking.* The simulation tracks how far each initiative has progressed relative to its original plan — not the revised estimate, but the commitment made at the start. An initiative that has consumed all its originally planned time shows as 100% complete against the original estimate, even if the underlying work is not actually finished. This signals to governance that the initiative has overrun its plan. For initiatives with no defined timeline (open-ended work), no progress fraction is reported.

All evidence generated this week is recorded and becomes the basis for belief updates in the next step.

**4. Value realization is deferred.** No value is realized at this point in the weekly cycle. All value realization — both one-time completion payoffs and ongoing returns from persistent mechanisms — happens later in the week, after beliefs have been updated and completions detected. This ensures that the value accounting reflects the full end-of-week state rather than a partial mid-week snapshot.

**5. The organization updates its beliefs about each initiative.**

*Strategic quality belief.* The organization's running estimate of how promising an initiative is moves toward the new evidence, weighted by several factors working together:

- A base learning rate that governs how quickly beliefs can change in general
- A staffing intensity factor — when the team assigned to an initiative is larger than the minimum required, the extra capacity accelerates learning with diminishing returns. How strongly additional staffing accelerates learning is a per-initiative study parameter expressing a modeled hypothesis, not an empirical truth. When this parameter is set to zero (the default), team size above the minimum has no effect on learning speed, preserving the simpler assumption that a team either meets the staffing threshold or it does not.
- A ramp adjustment — newly assigned teams learn less effectively during their transition period (see the section on ramp penalties below)
- A dependency adjustment — initiatives with more external dependencies are harder to learn about, regardless of team quality or attention level

This update is modulated by executive attention and initiative dependencies because strategic quality is difficult to observe and its clarity depends on how much focused leadership inquiry is applied.

The belief is bounded between zero (no strategic value) and one (maximum strategic value). It starts at a neutral midpoint of 0.5 — the organization begins with no opinion either way.

*Execution belief.* Separately, the organization's estimate of schedule fidelity adjusts toward what the observed progress implies about how long the initiative will actually take. This update is simpler: it depends only on the execution evidence and its own learning rate. It is not affected by executive attention, dependencies, or team ramp — consistent with the attention asymmetry principle described above.

Execution belief is a belief about schedule fidelity relative to the original plan, not a direct estimate of completion time. A value of 1.0 means governance currently believes the initiative will finish on schedule. A value of 0.5 means governance believes it will take roughly twice as long as planned. The derived quantity that governance actually reasons about — the implied completion time — translates this belief into business-interpretable weeks.

Execution belief starts at 1.0 — the organization initially assumes the initiative will run on plan. This initialization creates a boundary effect worth understanding. Because noise is symmetric, roughly half the time the weekly execution evidence will suggest the initiative is running better than on-plan. But the belief cannot exceed 1.0, so those favorable signals are effectively clipped — they cannot push the belief higher than the starting point. Unfavorable signals, however, are not clipped and pull the belief downward freely. The result is that genuinely on-plan initiatives show a slight systematic tendency to look like they are slipping, even when they are on track. This effect is consistent across all governance regimes sharing the same simulated world and does not distort the comparison between them. It is documented as a known modeling property rather than corrected.

**5b. Review track record is updated before governance acts.**

After beliefs are updated and before governance makes its end-of-week decisions, the simulation updates each initiative's review track record.

For every initiative that is both active and currently staffed, the simulation counts that initiative as reviewed this week. Its cumulative review count increments by one.

For reviewed initiatives where leadership can see a ceiling on potential value (a bounded opportunity), the simulation tests whether the expected payoff — the organization's current belief about strategic quality multiplied by the visible ceiling — falls below the governance threshold for what that opportunity needs to justify. If it does, a consecutive below-threshold counter increments. If the expected payoff is adequate, the counter resets to zero.

Initiatives that were not reviewed this week — because they are unstaffed, already completed, or already stopped — have their consecutive below-threshold counter reset to zero. A gap in reviews breaks the streak. This reflects the principle that patience tracking is a property of continuous active evaluation, not of calendar time passing.

Governance sees these updated counters when it makes its end-of-week decisions, which means governance can act on the same review that causes a counter to reach its trigger threshold. If this week's review is the Nth consecutive below-threshold review and the patience window is N reviews, governance can stop the initiative this week.

**5c. Completions are detected and organizational capability is updated.**

For every initiative that has accumulated enough staffed weeks to reach its true completion point, the simulation executes the full completion sequence:

- The initiative is marked as completed
- A completion record is created capturing the initiative's identity, the week of completion, its true underlying quality, and the total labor invested
- If the initiative produces a one-time completion payoff, that value is realized exactly once at this moment
- If the initiative is a right-tail bet that turns out to be a major win — determined by whether its true quality exceeds the major-win threshold, a fact that was hidden until this moment — a structured major-win discovery event is recorded
- If the initiative produces an ongoing value mechanism (a persistent return stream), that mechanism activates now
- The team is released for reassignment starting next week — the completing initiative's team becomes available at the start of the following week's governance cycle

Whether a right-tail initiative turns out to be a major win is determined at the moment the initiative was created and remains hidden until completion. There is no intermediate discovery state. The initiative either crosses the finish line and reveals itself as transformational, or it does not. The simulation records the discovery event but does not spawn follow-on work or price the full downstream economics of that discovery within the study horizon.

**Capability update.** When initiatives with capability contribution complete — primarily enablers — they improve the organization's ability to evaluate all future work. The size of the contribution depends on both the initiative's configured capability scale and its true underlying quality. A high-quality enabler contributes more organizational learning improvement than a low-quality one.

If multiple initiatives complete in the same week, their capability contributions are aggregated. The update follows a deliberate sequence: existing organizational capability above the baseline erodes first (the accumulated advantage decays continuously, reflecting that organizational capabilities degrade if not maintained), and then the new gains from this week's completions are added on top. This means newly completed enabler work takes full effect immediately — the organization does not lose this week's gains to this week's decay. But previously accumulated advantage does erode continuously. Capability cannot fall below the baseline of 1.0 or rise above a maximum ceiling.

The updated capability takes effect next week — all initiatives staffed from next week onward benefit from enabler completions that happened this week. This is consistent with the general principle that consequences of events within a week take effect at the start of the following week.

Residual value activation, however, takes effect immediately. An initiative that completes and activates an ongoing value stream contributes that stream to the same week's residual value pass.

**The measurement horizon is a boundary, not an event.** When the six-year clock runs out, nothing special happens. No initiatives are stopped. No forced completions occur. Initiatives still active at the horizon remain active. Their terminal state — current beliefs, staffed progress, team assignments, active residual streams, current organizational capability — is recorded as a snapshot of what the governance regime was building at the end of the measurement window. Two regimes may show similar cumulative value while one has three healthy long-term initiatives still running and the other has none. That difference is analytically significant and must be visible in the output.

Ongoing value mechanisms do not activate at the horizon for initiatives that have not actually completed. An initiative still in progress at the end of the window does not receive credit for the value stream it might have produced had it finished.

**6. Ongoing value streams produce this week's returns.** Every initiative whose persistent value mechanism has been activated — regardless of whether a team is still assigned — produces its weekly contribution. These streams continue running after the team has moved on to other work. This pass happens after completion detection so that a mechanism activated this week contributes in the same week it starts.

One-time completion value is realized only once at the completion moment in the step above and does not repeat here.

**7. Everything is recorded** and the simulation advances to the next week. Governance sees the updated beliefs, any completion or major-win events, and the full end-of-week portfolio state when it performs its review. Its decisions, formed at the end of this week, take effect at the start of next week.

**How dependency affects learning.** An initiative's dependency level directly reduces how efficiently the team can learn about its strategic quality. Learning efficiency decreases in direct proportion to the dependency level. An initiative with no external dependencies converts evidence into updated beliefs at full efficiency. An initiative with maximum dependency converts evidence at zero efficiency — no amount of work produces useful learning, because outcomes depend entirely on factors outside the team's control. In practice, this captures the reality that highly interconnected initiatives — those that depend on other teams' deliverables, external vendor timelines, regulatory approvals, or technology dependencies — generate ambiguous signals because it is difficult to separate the initiative's own quality from the noise introduced by its dependencies.

## Portfolio capability and strategic signal noise

### Academic
Portfolio capability ($C_t$) accumulated from completed enabler initiatives is a
portfolio-level organizational capability scalar initialized at $1.0$ and bounded
above by $C_{\max}$. Beginning at $t{+}1$ after an enabler completes, higher portfolio
capability reduces effective strategic signal noise for all staffed initiatives by
entering the effective signal st\_dev formula ($\sigma_{\text{eff}}$) as a divisor. At baseline
portfolio capability $1.0$, the formula is unchanged.

Portfolio capability has no other canonical mechanical effect in this study. It does not change
the learning-rate multiplier $L(d)$, execution-belief updates, or completion timing.
Specifically: $C_t$ does not enter the execution-progress signal generation
($z_t$), does not modulate the learning rate ($\eta$), and does not affect the
completion condition (`staffed_tick_count >= true_duration_ticks`). Its sole
mechanical role is as a divisor in $\sigma_{\text{eff}}$, reducing the variance of strategic
quality observations for all staffed initiatives simultaneously.

Canonical capability decay law:

$$\text{excess\_capability}_t = C_t - 1.0$$

$$\text{excess\_capability}_{t+1,\,\text{pre-completion}} = \text{excess\_capability}_t \cdot \exp(-\text{capability\_decay})$$

with completion gains then added on tick $t$ as defined in step 5c. This means
the baseline capability level $1.0$ does not decay away; only the accumulated
organizational advantage above baseline erodes over time.

The decay dynamics produce a characteristic trajectory: without ongoing enabler
completions, $C_t$ declines exponentially toward the baseline of $1.0$. Each
enabler completion adds a step increase, but previously accumulated excess
continues to erode between completions. The long-run steady-state capability
depends on both the frequency of enabler completions and the decay rate
$\text{capability\_decay}$. At $\text{capability\_decay} = 0$, there is no erosion and
capability accumulates monotonically (bounded by $C_{\max}$). At high decay rates,
each enabler completion produces a transient pulse that fades before the next
completion can build on it.

### Business
Organizational capability is a portfolio-level measure of how well the organization can evaluate its initiatives. It starts at a baseline of 1.0 and increases when enabler initiatives complete successfully. Higher capability reduces the noise in the strategic signals that all staffed initiatives produce — making it easier for governance to distinguish promising work from unpromising work across the entire portfolio simultaneously.

This is the only mechanical effect of organizational capability in the study. It does not change how quickly the organization learns from individual signals (the learning rate), it does not affect execution progress signals, and it does not change how long initiatives take to complete. Its sole effect is to make the strategic evidence cleaner — as though the organization has invested in better instrumentation, more rigorous evaluation processes, or stronger analytical infrastructure that helps everyone see more clearly.

Capability is bounded above by a maximum ceiling. And it does not accumulate indefinitely without replenishment — the organizational advantage above baseline erodes over time if not refreshed by further enabler completions. This decay reflects the reality that analytical infrastructure, evaluation processes, and institutional knowledge degrade without ongoing investment. The baseline capability level itself never decays; only the accumulated advantage above baseline erodes. An organization that completed several enablers early in the study but none in later years will see its capability advantage gradually fade back toward baseline.

The decay and replenishment dynamics work as follows: each week, the existing advantage above baseline shrinks by a fixed proportion (exponential decay). When an enabler completes, its capability contribution is added after that week's decay has been applied. This means new enabler gains take full effect immediately — the organization does not lose this week's investment to this week's erosion — while previously accumulated advantage continues to erode in the background.

## Effective noise $\sigma_{\text{eff}}(d,a,C_t)$ and attention shape $g(a)$

### Academic
The observation model for strategic quality decomposes the effective signal
standard deviation into four multiplicatively interacting components:
initiative-level base uncertainty ($\sigma_{\text{base}}$), dependency-driven noise
amplification ($1 + \alpha_d \times d$), attention-modulated noise scaling ($g(a)$), and
portfolio-level capability reduction ($1/C_t$). Because the components interact
multiplicatively, their effects compound: high dependency combined with low
attention and low capability produces observation noise that can substantially
exceed any single factor's contribution. Conversely, improving any one factor
yields proportional noise reduction across the product.

The effective signal st\_dev ($\sigma_{\text{eff}}$) captures how immutable dependency,
executive attention, and portfolio capability shape strategic-signal clarity. We define:

$$\sigma_{\text{eff}}(d, a, C_t) = \frac{\sigma_{\text{base}} \cdot (1 + \alpha_d \cdot d) \cdot g(a)}{C_t}$$

- $\sigma_{\text{base}}$ is the initiative-level base signal st\_dev. It is a fixed
  property of the initiative, set at generation, and does not change over the
  initiative's lifetime.
- $\alpha_d \geq 0$ scales how much immutable dependency $d$ increases noise. When
  $\alpha_d = 0$, dependency has no effect on signal clarity regardless of $d$.
  As $\alpha_d$ increases, initiatives with higher dependency produce progressively
  noisier strategic signals.
- $C_t \geq 1.0$ is the current portfolio capability scalar. Higher capability
  reduces effective strategic signal noise.

Because $C_t$ enters as a divisor of the entire noise expression, portfolio
capability improvements reduce effective noise uniformly across all staffed
initiatives. A doubling of portfolio capability halves $\sigma_{\text{eff}}$ for every
initiative, regardless of its dependency level or attention allocation.

We define $g(a)$ (attention noise modifier) through a raw shape $g_{\text{raw}}(a)$ and a clamp to preserve both a noise floor and a practical ceiling:

$$g_{\text{raw}}(a) = \begin{cases} 1 + k_{\text{low}} \cdot (a_{\min} - a) & \text{if } a < a_{\min} \\ \dfrac{1}{1 + k \cdot (a - a_{\min})} & \text{if } a \geq a_{\min} \end{cases}$$

$$g(a) = \operatorname{clamp}\!\bigl( g_{\text{raw}}(a),\; g_{\min},\; g_{\max} \bigr)$$

Parameters:
- $a_{\min} \in [0,1]$ — minimum attention threshold below which noise increases.
- $k_{\text{low}} \geq 0$ — controls how rapidly noise increases as $a$ falls below $a_{\min}$.
- $k > 0$ — curvature for diminishing returns above $a_{\min}$.
- $g_{\min} > 0$ — **floor** so noise cannot be driven to zero.
- $g_{\max}$ — ceiling so noise does not explode numerically. If $g_{\max}$ is `None`,
  the upper clamp is omitted and only the floor $g_{\min}$ is applied.

Behavioral properties of $g(a)$:
- $g_{\text{raw}}(a)$ is continuous on $[0, \infty)$ and monotonically decreasing (strictly
  decreasing where not clamped). Below $a_{\min}$, $g_{\text{raw}}$ increases linearly as
  $a$ decreases; above $a_{\min}$, $g_{\text{raw}}$ decreases hyperbolically as $a$
  increases. The clamp creates constant regions at the floor and ceiling.
- $g(a) = 1$ at $a = a_{\min}$ (before clamping): attention is neutral at the
  threshold. The observation noise at $a = a_{\min}$ equals the initiative's
  dependency-amplified base noise $\sigma_{\text{base}} \times (1 + \alpha_d \times d)$, unscaled by
  attention.
- $g(a) > 1$ for $a < a_{\min}$ (before clamping): sub-threshold attention
  actively increases observation noise beyond the dependency-amplified baseline.
  The rate of increase is governed by $k_{\text{low}}$.
- $g(a) < 1$ for $a > a_{\min}$ (before clamping): above-threshold attention
  reduces observation noise with diminishing returns governed by $k$. The
  infimum of $g_{\text{raw}}(a)$ as $a \to \infty$ is $0$, but the clamp at $g_{\min}$ prevents
  noise from being driven arbitrarily close to zero.
- The $g_{\max}$ ceiling, when set, prevents numerically unbounded noise at very
  low attention values. When $g_{\max}$ is not set (`None`), $g_{\text{raw}}(a)$ at $a = 0$
  evaluates to $1 + k_{\text{low}} \times a_{\min}$, which may be large but is finite.

Design notes:
- $g_{\text{raw}}(a_{\min}) = 1$, so $g(a)$ is continuous at $a_{\min}$ before clamping.
- The clamp ensures $g(a) \geq g_{\min}$ (noise floor). When $g_{\max}$ is set, it also
  protects against numerically large $g(a)$ at low attention.

The governance implication of the multiplicative structure is that signal clarity
is endogenous to the decision-maker's allocation choices — executive attention
is an input to the observation model, not merely a resource cost. A policy that
allocates sub-threshold attention to an initiative degrades its own future
information quality for that initiative, compounding any dependency-driven noise
amplification. The decision-maker is embedded in the signal generation mechanism,
not a passive observer of an exogenous process.

### Business
How clearly leadership can read the strategic signals coming from an active initiative is not a fixed property of the initiative itself. It depends on four things interacting simultaneously, and understanding each one matters because governance decisions are only as good as the signals they are based on.

**The initiative's inherent uncertainty.** Every initiative arrives with a baseline level of signal noise — how hard it is, by its nature, to tell whether it is strategically sound. A straightforward product extension in a well-understood market produces relatively clean signals. A speculative entry into an unfamiliar domain produces noisy ones. This baseline is a property of the initiative and does not change over time.

**How dependent the initiative is on factors outside the team's control.** Some initiatives can be evaluated largely on the basis of what the team itself does. Others depend heavily on external partners, regulatory outcomes, platform decisions, or market conditions that the team cannot influence. The more an initiative depends on these external factors, the harder it is to read the strategic signal clearly — because what leadership observes is a mixture of the initiative's true quality and the noise introduced by uncontrollable dependencies. The model treats dependency as a fixed characteristic of each initiative. A heavily dependent initiative does not become less dependent over time; its signal remains noisier throughout. The degree to which dependency amplifies noise is governed by a single scaling parameter — when that parameter is zero, dependency has no effect on signal clarity; as it increases, dependent initiatives become progressively harder to evaluate.

**How much executive attention the initiative is receiving.** This is the governance lever with the most complex behavior. The relationship between executive attention and signal clarity has three distinct regions:

- *Below a minimum engagement threshold*, shallow attention actively degrades signal quality. An executive who spends fifteen minutes scanning a dashboard or skimming a weekly status email may leave the initiative harder to evaluate than if leadership had stayed entirely uninvolved. Half-formed attention generates noise without generating insight — it produces the appearance of oversight without the substance of it. The further attention falls below this threshold, the worse the degradation. How steeply signal quality deteriorates in this region is controlled by a separate parameter, reflecting that some organizational contexts may be more or less vulnerable to the damage caused by superficial engagement.

- *At the minimum threshold*, attention is neutral — it neither helps nor hurts. This is the crossover point, and the transition from "attention is hurting" to "attention is helping" is smooth and continuous, not a cliff edge. There is no sudden jump in signal quality at any particular level of engagement.

- *Above the threshold*, deeper engagement improves signal clarity, but with diminishing returns. The first additional hours of real engagement produce meaningful improvement. The fifth and sixth hours still help, but less. The curvature of this diminishing-returns relationship is governed by its own parameter. No amount of attention can eliminate uncertainty entirely — there is a hard floor on how clear signals can ever become, regardless of how deeply leadership engages. Even the most attentive, capable executive cannot reduce strategic uncertainty to zero through involvement alone; some uncertainty is intrinsic to the initiative and the environment.

- There is also a practical ceiling on how much noise shallow attention can introduce. This prevents the model from producing scenarios where minimal attention creates effectively infinite uncertainty — a numerically useful bound, but also a reasonable one: even a completely disengaged executive does not make an initiative infinitely harder to evaluate. If this ceiling is not explicitly set, only the noise floor applies, and very low attention levels can produce very high noise without an upper limit.

**The organization's accumulated learning capability.** Everything described above is then modulated by how capable the organization has become at evaluating initiatives — the portfolio-wide capability that grows as enabler initiatives are completed. Higher organizational capability reduces the effective noise on strategic signals for every active initiative simultaneously. An organization that has invested in better evaluation infrastructure — analytics platforms, experimentation tools, structured review processes — will read the same initiative more clearly than one that has not, all else being equal. Capability enters as a divisor: doubling the organization's capability halves the effective noise, making every signal across the portfolio proportionally clearer.

**How these factors combine.** The four factors interact multiplicatively. An initiative that is inherently uncertain, heavily dependent on external factors, receiving shallow executive attention, and operating in an organization with low learning capability will produce signals so noisy that governance decisions based on them are barely better than guessing. Conversely, a low-dependency initiative receiving focused attention in a capable organization will produce signals clear enough to support confident and timely decisions. The governance implication is that signal clarity is not something leadership passively observes — it is something leadership actively shapes through attention allocation and, over the longer term, through investment in organizational capability.

## Value formulas (explicit and channel-specific)

### Academic
The simulator maintains three analytically distinct output channels that must
remain separable throughout the run and in all reporting. Channel separation is
a structural requirement, not a convenience: collapsing completion-lump value,
residual value, and major-win events into a single aggregate would obscure the
mechanistic differences between governance regimes that are the primary object
of study. Two regimes with similar aggregate value may differ sharply in channel
composition — one dominated by completion lumps, the other by residual
accumulation — and that compositional difference is evidence about governance
structure, not noise.

The simulator supports two realized value channels: completion-lump value and
residual value produced by previously activated mechanisms. Major-win discovery
events are analytically important outputs, but they are distinct from realized
economic value in the canonical study and must be recorded separately.

#### 1. Completion-lump value

Applicable when the initiative's completion-lump channel is enabled.

*Realized lump (once completed)*:

$$v_{\text{lump,realized}} = \text{configured completion-lump value}$$

This value is realized exactly once, at the tick where the initiative completes.

*Expected lump value (pre-completion used by governance)*:

$$\mathbb{E}[v_{\text{lump}}] = c_t \times \text{configured completion-lump value}$$

The expected value is a governance-facing estimate weighted by the current quality
belief. Whether the initiative actually completes — and what it actually pays
out — depends on latent quality and whether governance sustains investment
through completion. Governance never observes latent quality directly; it
reasons about expected values derived from belief scalars.

#### 2. Major-win event

Applicable when the initiative's major-win-event channel is enabled.

When a right-tail initiative completes and `value_channels.major_win_event.is_major_win == true`, the engine must emit a structured `MajorWinEvent` containing at least:

- `initiative_id`
- `tick`
- latent quality
- `observable_ceiling`
- quality belief at completion
- `cumulative_labor_invested`
- `cumulative_attention_invested`
- `observed_history_snapshot`

This event record is required for later analysis of major-win probability, time to major win, and labor-to-major-win efficiency. **Scoping note:** when a major win is surfaced, the simulator records the event but does **not** spawn a follow-on initiative or require pricing the full downstream economics of that win within the horizon.

The study measures governance's ability to preserve the option value of
transformational discovery — the rate at which major wins are surfaced, the
elapsed time and labor investment required to surface them, and the relationship
between governance patience and discovery probability. Pricing the downstream
economic value of a surfaced major win is excluded because it depends on
organization-specific factors (competitive dynamics, execution capability,
market timing) that are outside the model's scope and would add
parameterization burden without improving the governance comparison.

Whether an initiative is a major win is determined at generation by a
deterministic threshold function of latent quality
($\text{is\_major\_win} = (q \geq q_{\text{major\_win\_threshold}})$) and hidden from governance
throughout the run. There is no intermediate discovery state and no
probabilistic revelation mechanism — the flag is binary, immutable, and
revealed only at completion through the emitted `MajorWinEvent`.

#### 3. Residual value

Applicable when the initiative's residual channel is enabled and `residual_activated == true`.

Residual value is realized in a separate pass because it can continue after the initiative is no longer staffed.

Canonical residual realization rule:

$$v_{\text{residual,realized},t} = \operatorname{max}\!\bigl( \text{residual\_rate}_t ,\; 0 \bigr)$$

Canonical residual decay law:

$$\tau_{\text{residual}}(t) = t - \text{residual\_activation\_tick}$$

$$\text{residual\_rate}_t = \text{residual\_rate} \cdot \exp\!\bigl(-\text{residual\_decay} \cdot \tau_{\text{residual}}(t)\bigr)$$

where $\text{residual\_decay} \geq 0$ is the initiative-local per-tick exponential decay
rate and $t$ is the simulation tick (calendar tick), not `staffed_tick_count`.
Because the residual pass occurs after completion detection on the same
tick, an initiative whose residual activates at tick $t$ has
$\tau_{\text{residual}}(t) = 0$ on that activation tick and therefore realizes its full
configured `residual_rate` before decay begins on subsequent ticks.

This timing is intentional. It treats the configured `residual_rate` as the
activation-tick rate and avoids the awkward semantics in which a mechanism is
born already partially decayed.

Each initiative's `residual_decay` rate is set at generation and is
initiative-specific — different initiatives may have residual streams with
different durability characteristics. The decay operates on calendar time from
activation, not on staffed time, because the residual mechanism operates
autonomously once activated, independent of any team assignment or governance
attention.

**Notes on use:**
- Governance uses expected values (which depend on quality belief) when making
  stop/continue and assignment decisions at reviews.
- Review-driven patience semantics are defined over **consecutive reviews**, not
  over calendar ticks. A pause or unstaffing breaks the streak by resetting
  `consecutive_reviews_below_tam_ratio` to zero.

### Business
The simulation tracks three distinct value channels, each representing a different way that initiatives create organizational value. These channels are kept separate throughout the simulation because they represent fundamentally different phenomena, and collapsing them into a single number would obscure the structural differences between governance regimes.

**1. Completion-lump value — the one-time payoff at completion.**

When an initiative finishes, it may produce a one-time economic payoff — a product launch, a deal closed, a capability delivered. This value is realized exactly once, at the moment of completion, and does not recur.

Before completion, governance uses an expected value estimate when deciding whether to continue or stop an initiative: the organization's current belief about the initiative's quality multiplied by the configured completion value. This is what governance thinks the initiative is worth completing based on what it currently knows. Whether the initiative actually completes — and what it actually pays out — depends on its true underlying quality and whether governance sustains investment long enough.

**2. Major-win discovery — the transformational outcome.**

Some right-tail initiatives, upon completion, turn out to be genuinely transformational. Whether an initiative is a major win is determined at generation and hidden until the initiative completes — governance cannot know in advance. When a major win is surfaced, the simulation records a detailed discovery event capturing the initiative's identity, the week of discovery, its true quality, the visible ceiling, what governance believed about its quality at the time, how much labor was invested, how much executive attention was devoted, and the full observation history.

This event record is essential for analyzing how effectively different governance regimes preserve the option value of transformational discovery — how many major wins they surface, how long it takes, and how much organizational effort each one requires.

When a major win is surfaced, the simulation records the discovery but does not attempt to price the full downstream value. The study measures governance's ability to find transformational outcomes, not the economics of exploiting them afterward. The practical reasoning is that the downstream value of a major win depends on so many organization-specific factors — competitive position, execution capability, market timing — that pricing it within the simulation would add complexity without adding insight.

**3. Residual value — the ongoing return from completed work.**

Some initiatives, once completed, activate persistent value mechanisms that continue producing returns after the team has moved on. A distribution network, an automation system, a marketplace platform — the team that built it redeployed months ago, but the mechanism keeps generating value every week.

Residual value is realized in a separate accounting pass because it operates independently of staffing. Completed initiatives with activated residual streams contribute value every week, whether or not anyone is paying attention to them. These streams accumulate across the portfolio over time.

Each residual stream starts at its full configured rate on the week it activates and then decays gradually over time. The decay rate is specific to each initiative — some mechanisms are durable and decay slowly, others are more ephemeral. The decay is measured in calendar time from activation, not in staffed time, because a distribution network deteriorates according to its own clock, not according to whether a team is assigned to it.

The timing of activation is deliberate: an initiative that completes and activates a residual stream in a given week begins contributing returns that same week at its full rate, before any decay has occurred. This treats the configured rate as the mechanism's starting output and avoids the counterintuitive result of a mechanism being born already partially degraded.

**How governance uses these channels.** When making stop/continue and assignment decisions, governance reasons about expected values — estimates weighted by the organization's current belief about initiative quality. These are the governance-facing quantities that inform the decision. Realized value depends on the true underlying quality, which governance never sees directly.

The patience mechanics for bounded opportunities — the consecutive-review tracking that determines when governance concludes an initiative's upside is too small to justify continued investment — operate over consecutive reviews, not calendar time. If an initiative is unstaffed for a period and then restaffed, the consecutive below-threshold counter resets to zero. A gap in active evaluation breaks the streak.

## Belief update nuance

### Academic
- The model tracks only the quality belief scalar. Implicit variance is represented
  via the effective signal st\_dev and $L(d)$. This choice simplifies the engine and
  isolates governance effects.

The belief update maintains a point estimate ($c_t \in [0, 1]$) without
an associated precision measure or posterior variance. A belief of $0.6$ after 2
observations is representationally identical to a belief of $0.6$ after 200
observations. The decision-maker cannot condition on estimation precision within
the model.

The effective signal standard deviation ($\sigma_{\text{eff}}$) and the dependency-adjusted
learning efficiency ($L(d)$) serve as implicit proxies for belief convergence
rate: high-$\sigma_{\text{eff}}$ and low-$L(d)$ initiatives have beliefs that evolve slowly
and remain poorly resolved for longer. But these are properties of the
observation channel, not direct measures of accumulated evidence.

The stagnation window ($W_{\text{stag}}$) provides a coarse implicit proxy for belief
convergence: an initiative whose belief has not moved by more than $\varepsilon_{\text{stag}}$
over $W_{\text{stag}}$ staffed ticks may have converged to a stable estimate near the
latent quality, or may be trapped in a region where observation noise prevents
resolution. The model does not distinguish these two states. A full Bayesian
treatment would maintain a posterior distribution over latent quality (e.g., a
conjugate Beta posterior under appropriate signal-model assumptions), with
posterior variance serving as the natural precision measure and entering the
stopping rule directly. This simplification is deliberate: it keeps the engine
focused on the governance decision comparison rather than on inference
mechanics, at the cost of preventing governance from conditioning on how much
evidence underlies its current estimate.

### Business
The model tracks only a single running estimate of each initiative's strategic quality — a point estimate, not a confidence interval. It does not separately track how much evidence underlies that estimate or how reliable it should be considered.

This means the organization cannot formally distinguish between an estimate based on two weeks of noisy data and one based on two years of consistent signals. Both are represented as a single number. In practice, the effective signal noise and the dependency-adjusted learning efficiency serve as implicit proxies for how quickly beliefs can change — a high-noise initiative with heavy dependencies will have beliefs that move slowly and remain uncertain for longer — but the model does not maintain an explicit measure of estimation confidence.

The stagnation window provides a partial indirect signal: an initiative whose belief has not moved meaningfully over a sustained period of active work may be one where the evidence has converged, or one where the evidence is too noisy to resolve. Governance cannot tell which. This is a deliberate simplification that keeps the model focused on governance effects rather than on the mechanics of Bayesian inference.

## Ramp penalties on reassignment

### Academic
When a team is newly assigned to an initiative, its effective learning efficiency is
reduced for a ramp period. The ramp multiplier is computed as:

Let $t_{\text{elapsed}} = \text{ticks\_since\_assignment}$
(reset to $0$ on each new assignment).
Let $R = \text{ramp\_duration\_ticks}$ (from `InitiativeConfig` or `WorkforceConfig` default).
Let $\text{ramp\_fraction} = \operatorname{min}\!\bigl((t_{\text{elapsed}} + 1) \,/\, R,\; 1.0\bigr)$.

**Linear shape** (`ramp_multiplier_shape = "linear"`):

$$\text{ramp\_multiplier} = \text{ramp\_fraction}$$

**Exponential shape** (`ramp_multiplier_shape = "exponential"`):

$$\text{ramp\_multiplier} = 1 - \exp(-k \cdot \text{ramp\_fraction})$$

where $k = 3.0$ (fixed constant; gives ${\sim}95\%$ of full efficiency at $t_{\text{elapsed}} = R$).

In both cases:

- $\text{ramp\_multiplier} \in (0, 1]$ for $t_{\text{elapsed}} \in [0,\, R{-}1]$
- $\text{ramp\_multiplier} = 1.0$ for $t_{\text{elapsed}} \geq R{-}1$

This indexing convention is intentional. On the first staffed tick after a new
assignment ($t_{\text{elapsed}} = 0$), the team contributes positive but partial learning
efficiency rather than zero. The first staffed tick therefore counts as ramp time,
not as a zero-productivity placeholder tick.

$$\text{is\_ramping} = (t_{\text{elapsed}} < R - 1)$$

Here $t_{\text{elapsed}}$ is the pre-production-increment value of
`ticks_since_assignment` ($0$ on the first staffed tick). The belief update in
step 5 must read this pre-increment value. Implementations must not use the
post-increment value, which is $1$ on the first tick and would silently produce
$\text{ramp\_fraction} = 2/R$ rather than $1/R$.

The ramp multiplier applies to learning efficiency:

$$L_{\text{ramped}}(d) = \text{ramp\_multiplier} \times L(d)$$

When $\text{is\_ramping} = \text{false}$, $\text{ramp\_multiplier} = 1.0$ and the formula reduces to its unramped form.

**Scope of ramp effects.** The ramp multiplier affects only the quality belief
learning rate via $L_{\text{ramped}}(d)$. It does not enter the execution belief update
($c_{\text{exec}}$ is independent of ramp state), does not alter signal generation
($\sigma_{\text{eff}}$ is independent of ramp), does not delay completion (the initiative's
`staffed_tick_count` still increments during ramp), and does not reduce realized
value at any channel. The scope restriction ensures that ramp represents
strictly a transient learning-efficiency penalty from team reassignment, not a
broader productivity loss. When ramp and dependency interact (both $d > 0$ and
$\text{ramp\_multiplier} < 1$), the penalties compound multiplicatively:
$L_{\text{ramped}}(d) = \text{ramp\_multiplier} \times (1 - d)$.

`ticks_since_assignment` is assignment-relative state only. It must not be used
for completion detection, for progress-fraction denominators, or for the
stagnation window. Those all use the lifetime `staffed_tick_count`.

The cumulative labor consumed during ramp periods across all initiatives is a
first-class run output (`cumulative_ramp_labor` and `ramp_labor_fraction`; see
the reporting specification). Cross-regime comparison of ramp labor measures the
total switching cost each governance policy incurs through its reassignment
behavior. A governance regime that frequently reassigns teams across
initiatives pays a compounding learning-efficiency penalty: each reassignment
resets the ramp clock, and the affected initiative's belief trajectory stalls
during the transition. This cost does not appear in simple labor accounting —
the team is staffed and the initiative's `staffed_tick_count` increments — but
it manifests as slower belief convergence, delayed stop/continue resolution, and
degraded signal quality during the ramp window.

### Business
When a team is newly assigned to an initiative, it does not immediately operate at full productivity. There is a transition period — the ramp — during which the team's ability to generate useful learning about the initiative is reduced. This reflects the reality that newly assigned teams need time to understand the initiative's context, build relationships with stakeholders, learn the domain, and develop the working patterns that make their observations informative.

**How the ramp works.** The ramp has a configured duration — for example, a certain number of weeks. During this period, the team's learning efficiency is multiplied by a ramp factor that starts low and increases steadily toward full productivity.

Two shapes are available:

- *Steady improvement*: the team's effectiveness increases at a constant rate from partial productivity on the first week to full productivity at the end of the ramp period.
- *Front-loaded improvement*: the team's effectiveness improves quickly at first and then levels off, reaching approximately 95% of full productivity by the end of the ramp period.

In both cases, the team contributes positive but partial learning from the very first week — they are not completely unproductive on day one. This is a deliberate design choice: the first week counts as ramp time with reduced output, not as a zero-productivity placeholder.

**What ramp affects and what it does not.** Ramp reduces only the team's contribution to learning about strategic quality. It multiplies the dependency-adjusted learning efficiency, so a newly assigned team working on a highly dependent initiative experiences both penalties simultaneously. Ramp does not affect anything else — it does not slow completion, change execution evidence, or reduce the initiative's value.

**Ramp versus lifetime clocks.** The ramp clock resets to zero every time a new team is assigned to an initiative. It tracks only how long the current team has been on this initiative. All other clocks — total staffed time, completion progress, stagnation assessment — use the initiative's lifetime staffed-time clock, which never resets on reassignment. This distinction matters: an initiative that has been staffed for two years but recently received a new team is experienced (in terms of accumulated evidence and progress) but is in early ramp (in terms of the current team's familiarity with the work).

**Why this matters for governance.** Ramp is the direct cost of reassignment. A governance regime that frequently reshuffles teams across initiatives pays a productivity tax each time — the new team spends its first weeks learning the initiative rather than generating useful evidence about it. This cost is invisible in simple headcount accounting but shows up in slower learning, noisier beliefs, and delayed resolution of whether an initiative is worth continuing. The simulation tracks cumulative ramp labor separately so that different governance regimes can be compared on how much of their total capacity was consumed by transition overhead.

## Deterministic behavior & reproducibility

### Academic
The simulation is deterministic given its inputs: identical `world_seed` and
`SimulationConfiguration` produce identical run outputs. This is a hard
requirement, not a desirable property. The common random numbers (CRN)
variance reduction technique requires that two governance regimes sharing a
world seed face identical observation sequences for every initiative, so that
outcome differences can be attributed to governance decisions rather than to
sampling variation. CRN is the foundational identification strategy for the
study's comparative analysis.

- All random draws are seeded via `world_seed`. The runner resolves any generator into a fixed list of initiatives prior to engine start (provenance recorded).
- At pool generation time, the runner instantiates two per-initiative RNG streams per
  architecture invariant 9. The streams are stored in `InitiativeState` and passed to
  the engine alongside the resolved initiative list. Quality signal draws use
  `quality_signal_rng`; execution signal draws use `exec_signal_rng`. These streams
  must not be shared across initiatives: each initiative's draws are independent of
  every other initiative's governance history across regimes.

The engine is agnostic to how the resolved initiative list was produced. Whether
it originated from a hand-crafted scenario, a named environment archetype, or
a parameter sweep has no bearing on engine behavior — the engine consumes only
the realized initiative attributes and their associated RNG streams. Provenance
metadata is recorded in the run manifest for reproducibility and attribution
but does not enter any engine computation.

Per-initiative stream isolation is the mechanism that preserves CRN
comparability across divergent governance trajectories. When two regimes sharing
a world seed make different decisions about initiative `i` — one stops it, the
other continues — both regimes still receive identical observation draws for
all initiatives `j ≠ i`. The comparison therefore identifies the causal effect
of governance policy on portfolio outcomes, holding the stochastic environment
constant. A single global RNG stream would violate this property: once regimes
diverge in which initiatives are active, a shared stream would also diverge,
contaminating the comparison with sampling artifacts unrelated to governance.

### Business
The simulation is designed to be fully reproducible. Given the same configuration and the same world seed, it produces identical results every time. This is essential for the study's comparative method — two governance regimes being compared must face not just the same initial conditions but the same sequence of weekly evidence for every initiative.

Before the simulation begins, the runner resolves all configuration into a fixed, concrete list of initiatives with all attributes determined. How that list was produced — from a hand-crafted scenario, a named environment archetype, or a parameter sweep — is recorded for provenance but has no effect on the engine.

Each initiative receives two dedicated random streams at generation — one for strategic quality signals and one for execution progress signals — seeded deterministically from the world seed and the initiative's identity. These streams are never shared across initiatives. This per-initiative isolation is critical for the common random numbers technique: when two governance regimes make different decisions about one initiative (one stops it, the other continues), those different decisions must not alter the signals produced by any other initiative. With per-initiative streams, two regimes facing the same world seed receive identical weekly evidence for a given initiative regardless of what they have done with every other initiative in the portfolio. The comparison reflects governance differences, not sampling differences.

## Additional implementation notes

### Academic
- The engine must maintain channel-separated cumulative totals for completion-lump value and residual value, and must record major-win events separately from realized economic value.
- The engine must maintain terminal portfolio capability separately from residual value totals.
- The residual-value pass must iterate over all residual-activated initiatives, not only over currently staffed initiatives.
- `review_count` increments exactly once per end-of-tick governance invocation for
  each initiative that is both active and staffed on that tick.
- `consecutive_reviews_below_tam_ratio` is updated before governance is invoked on
  that tick, using the current review's strategic belief and `observable_ceiling`.
- For initiatives not reviewed on a tick (for example paused, unassigned,
  stopped, or completed initiatives), `consecutive_reviews_below_tam_ratio`
  resets to zero rather than persisting through the gap.
- `staffed_tick_count` is a lifetime staffed-time clock and never resets on
  reassignment.
- `ticks_since_assignment` is the assignment-relative ramp clock and resets to 0
  on each new assignment.
- Governance decisions at end-of-tick $t$ may use the updated belief state $c_{t+1}$ and the completion or major-win events emitted at tick $t$, but those decisions do not take effect until the start of tick $t{+}1$.
- The stagnation window $W_{\text{stag}}$ is defined over **staffed ticks**, not calendar ticks.
  The engine maintains `staffed_tick_count` per initiative for this purpose. The prior
  belief used to compute $\Delta_c$ is the strategic quality belief $W_{\text{stag}}$ staffed ticks
  ago, not $W_{\text{stag}}$ calendar ticks ago. Idle periods between staffing assignments do
  not count toward the window and do not contribute to stagnation detection.
- The engine maintains a per-initiative ring buffer
  `belief_history: deque[float]`
  with `maxlen =` $W_{\text{stag}}$. It is initialized as an empty deque at initiative activation.
  At the end of each staffed tick, after the belief update step (step 5), the engine
  appends the current end-of-tick quality belief to `belief_history`. Once `len(belief_history) ==` $W_{\text{stag}}$,
  the oldest retained quality belief is `belief_history[0]`, and the stagnation
  comparison is $\Delta_c = |c_t - \text{belief\_history}[0]|$. Before that threshold, the
  stagnation condition
  cannot fire regardless of $\Delta_c$.
- `age_ticks` and `ticks_since_assignment` must not be substituted for
  `staffed_tick_count` in stagnation logic.
- **Engine-driven team release timing**: team releases triggered by engine-detected
  lifecycle transitions (initiative completion at step 5c)
  follow the same timing convention as governance-driven releases: the release is
  effective at start of tick $t{+}1$, consistent with architecture invariant 4. The
  completing initiative's team is available for the governance step of
  tick $t{+}1$.
- The engine must maintain execution belief separately from quality belief. These
  are independent belief scalars updated by independent observation streams. They
  must be reported separately in per-tick logs and in `GovernanceObservation`. The
  derived observable `implied_duration_ticks` must be recomputed each tick when
  execution belief is available.

### Business
Several operational details govern how the simulation tracks state and maintains consistency. While these are implementation-level concerns, they have direct consequences for the accuracy and interpretability of the governance comparison.

**Value accounting is channel-separated.** The simulation maintains separate running totals for one-time completion value and ongoing residual value, and records major-win discovery events in their own dedicated log. These are never collapsed into a single aggregate during the run. Terminal organizational capability is also maintained separately from any value total. This separation ensures that the structural character of each governance regime's value creation is visible — not just the total, but how the total was composed.

**Ongoing value mechanisms run independently of staffing.** The weekly residual value pass iterates over every initiative whose persistent mechanism has activated, regardless of whether a team is currently assigned. A distribution network does not stop producing returns because the team that built it has moved to another project.

**Review counting is precise.** An initiative's review count increments exactly once per week for each initiative that is both active and staffed. Initiatives that are unstaffed, completed, or stopped are not reviewed and their review count does not change.

**Patience tracking resets on gaps.** The consecutive below-threshold counter — which tracks how many reviews in a row an initiative's expected value has fallen below the patience threshold — resets to zero for any initiative not reviewed in a given week. This includes initiatives that are temporarily unstaffed, not just those that are stopped or completed. A gap in active evaluation breaks the streak.

**Lifetime versus assignment clocks.** The lifetime staffed-time clock counts every week an initiative has had a team assigned, across all assignments over its entire life. It never resets on reassignment. The assignment-relative clock counts weeks since the current team was assigned and resets to zero on each new assignment. These serve different purposes: lifetime staffed time governs completion detection, progress tracking, and stagnation assessment; the assignment clock governs only the ramp productivity calculation.

**Governance acts on current beliefs with delayed effect.** At the end of each week, governance sees the fully updated belief state — including any belief changes, completion events, or major-win discoveries from that same week — and makes its decisions accordingly. Those decisions take effect at the start of the following week.

**Stagnation is measured in active working time, not calendar time.** The stagnation window — which asks whether the organization's belief about an initiative has meaningfully changed over a sustained period of active work — counts only weeks when the initiative was staffed and being actively evaluated. Weeks when the initiative sat unstaffed do not count toward the stagnation window and cannot trigger a stagnation stop. This reflects the logic that stagnation is about information throughput: if no evidence is being generated, the question of whether new information is being learned does not apply.

The simulation tracks the belief history needed for stagnation assessment by recording the quality belief at the end of each staffed week. Once enough staffed weeks have accumulated to fill the stagnation window, the simulation compares the current belief against the belief from the start of the window. If the net movement falls below the stagnation threshold, the initiative qualifies for a stagnation stop (subject to additional patience conditions). Before enough staffed weeks have accumulated, the stagnation condition cannot fire regardless of how little the belief has changed.

Calendar age and assignment-relative time must not be substituted for lifetime staffed time in stagnation logic. An initiative that has existed for two years but was staffed for only three months has three months' worth of evidence for stagnation purposes, not two years.

**Team release timing is consistent.** When a team is released — whether because governance stopped its initiative or because the initiative completed naturally — the team becomes available for reassignment at the start of the following week. This timing is consistent regardless of whether the release was a governance decision or an engine-detected completion. The release week is the initiative's last active week; the team is available starting the next week.

**Strategic and execution beliefs are independent.** The organization's belief about an initiative's strategic quality and its belief about execution fidelity are separate estimates updated by separate evidence streams. They are tracked independently, reported independently, and must not be confused. The implied completion time — the governance-facing quantity that translates execution belief into projected weeks — is recalculated each week whenever execution belief is available.

## Idle capacity counting rules

### Academic
Idle capacity is a first-class analytical output, not an edge case. Two
governance regimes that produce similar cumulative value may differ sharply in
idle team-ticks, and that difference is evidence about governance selectivity —
how aggressively the regime deploys against the remaining opportunity set versus
holding capacity in reserve when it judges the remaining pool unattractive.
Cross-regime comparison of idle capacity profiles is therefore required for a
complete governance characterization.

The following rules define precisely when a team-tick is counted as idle and how
different idle causes are distinguished. These rules govern the
`cumulative_idle_team_ticks` and `unassignable_team_ticks` metrics in the run
summary (see `review_and_reporting.md`).

1. **Definition**: a team-tick is idle when the team has no assigned initiative at
   the start of that tick (`team.assigned_initiative_id is None` at step 1 of the
   tick loop).

2. **Governance-driven releases** (Stop action applied at end of tick $T$): the team
   becomes idle starting at tick $T{+}1$, per the action-timing invariant. The stop
   tick itself is the last active tick; idleness begins the following tick.

3. **Engine-driven releases** (completion at step 5c):
   same timing — the team is idle starting at tick $T{+}1$, consistent with the
   engine-driven release timing established for AP-8.

4. **Immediate reassignment**: if a team is released at end of tick $T$ and
   reassigned in the same governance action cycle (within tick $T$'s action vector),
   it is idle for zero ticks. Both the release and the reassignment take effect at
   $T{+}1$ simultaneously; the team is never unassigned at the start of any tick.

5. **Ramp**: a team in ramp is not idle. It is assigned and working at reduced
   efficiency. Ramp ticks are productive ticks, not idle ticks, even when
   `ramp_multiplier` is low.

6. **Idle-by-mismatch** (`unassignable_team_ticks`): if no unassigned initiative
   in the pool has a `required_team_size` that the free team can satisfy, the team
   is idle for that tick due to structural incompatibility rather than governance
   judgment. These ticks are counted separately in `unassignable_team_ticks` and
   must not be merged with governance-driven idle ticks in
   `cumulative_idle_team_ticks`. The distinction is analytically significant:
   idle-by-mismatch signals a configuration issue, while idle-by-governance signals
   deliberate selectivity.

7. **Mid-tick ramp transitions**: ramp completion takes effect at the start of the
   next tick. A team that completes ramp at tick $T$ is fully productive starting at
   tick $T{+}1$. There are no partial-tick ramp transitions.

### Business
When a team has no assigned initiative at the start of a given week, that team-week is counted as idle capacity. The simulation tracks idle capacity carefully because it is analytically significant: two governance regimes that produce similar total value may differ sharply in how much of their workforce sat unused, and that difference is evidence about governance selectivity and resource efficiency.

The following rules define precisely when idle capacity is counted and how different causes of idleness are distinguished.

**1. What counts as idle.** A team is idle for a given week if it has no assigned initiative at the start of that week. The team has no work to do and produces no evidence, no learning, and no value for that week.

**2. Idle after a governance stop.** When governance stops an initiative at the end of a given week, the team becomes idle starting the following week. The stop week itself is the initiative's last active week — the team was still working that week. Idleness begins the week after.

**3. Idle after a natural completion.** When an initiative completes during the normal course of work, the same timing applies — the team becomes idle starting the following week. The completion week is the team's last active week on that initiative.

**4. Immediate reassignment avoids idle time.** If governance stops an initiative and reassigns the freed team to a new initiative in the same set of end-of-week decisions, both actions take effect simultaneously at the start of the following week. The team transitions directly from one initiative to the next and is never idle — it is assigned at the start of every week. The same applies when a team is freed by completion and reassigned in the same governance cycle.

**5. Ramp is not idle.** A team in its transition period on a newly assigned initiative is not idle. It is assigned and working at reduced efficiency. Ramp weeks are productive weeks, not idle weeks, even when the team's learning effectiveness is low. The distinction matters: idle capacity reflects a governance choice to leave resources undeployed, while ramp capacity reflects the unavoidable cost of putting resources to work on something new.

**6. Idle due to structural mismatch is tracked separately.** If a team is available but no unassigned initiative in the pool can accommodate it — because every remaining initiative requires a team of a different size — the team is idle for that week due to a structural incompatibility between the team configuration and the initiative pool. These team-weeks are counted separately from governance-driven idle time and must not be merged. The distinction is analytically significant: idle-by-mismatch signals that the organizational structure (team sizes) was mismatched with the opportunity pool, while governance-driven idle time signals that governance judged the remaining opportunities unattractive enough that deploying against them would be worse than deploying nothing.

**7. Ramp completion takes effect the following week.** When a team reaches the end of its ramp period during a given week, it becomes fully productive starting the following week. There are no partial-week transitions within the ramp period.
