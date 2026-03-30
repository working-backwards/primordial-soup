# Initiative model

## Purpose

### Academic
Defines the canonical initiative schema that the engine consumes. Initiative *types* (flywheel/right-tail/...) are metadata for generation and reporting only. The engine operates entirely on resolved initiative attributes and mutable state.

This document specifies the complete per-initiative data model: immutable attributes fixed at generation, mutable state evolved by the engine during the run, the lifecycle state machine governing transitions, and the composable value-channel structure through which initiatives produce output. Each attribute is classified by its observation status — latent (hidden from governance throughout the run, accessible only to the engine for ground-truth computations) or observable (exposed to governance through `InitiativeObservation`). This classification enforces the partial observability boundary that is structural to the study's POMDP formulation.

### Business
Defines the complete description of what an initiative is within the simulation — what properties it carries, what the organization can and cannot see about it, and how it creates value. Initiative type labels — flywheel, right-tail, enabler, quick win — are organizational shorthand used when setting up scenarios and interpreting results. The simulation engine itself operates entirely on each initiative's concrete attributes and evolving state. It never applies different rules based on which label an initiative carries.

## Attribute space (in scope)


### Academic
The attribute space for initiatives is defined by the following core dimensions in-scope for the study:

- **Latent quality** (q in equations): fixed, unobservable, governs how the initiative would perform given sufficient investment.
- **Quality belief** (quality_belief_t; c_t in equations): governance-visible estimate of latent quality, updated via learning.
- **Signal noise / clarity parameters**: govern how quickly beliefs can improve and how noisy observations are. The per-initiative base noise (`σ_base`) interacts multiplicatively with dependency-driven amplification (`1 + α_d × d`), the attention noise modifier (`g(a)`), and portfolio capability (`1/C_t`) to determine the effective signal standard deviation (`σ_eff`) at each tick. These parameters collectively define the information environment within which governance forms and updates beliefs. The canonical decomposition is specified in `core_simulator.md`.
- **Dependency level** (dependency_level; d in equations): static friction that increases noise and slows learning.
- **Market ceiling / TAM (optional)**: observable ceiling used when translating belief into expected value for some initiatives.

Other structural distinctions are implemented as composable initiative attributes and lifecycle/state transitions, not as hard-coded type branching. The canonical mechanism basis for this study is: completion lump value, post-completion residual value, completion-time major-win discovery events, and completion-time capability contributions. Human-facing initiative labels are generator-side shorthand over these resolved attributes.

A single initiative may use one, multiple, or none of the canonical mechanism channels. The initiative families used in the study — flywheel, right-tail, enabler, quick win — are common combinations of these mechanisms and structural characteristics, defined at the generator level for scenario design and carried as reporting tags. They do not enter any engine-side branching logic.

### Business
Every initiative in the simulation is defined by a set of core characteristics that determine how it behaves, how it can be evaluated, and what kind of value it can create. These characteristics fall into five foundational dimensions:

- **True underlying quality.** Every initiative has a fixed, hidden strategic quality that represents how valuable it would actually turn out to be if pursued to completion. Leadership cannot observe this directly — it can only be inferred from imperfect evidence that accumulates as teams work.

- **The organization's current belief about that quality.** This is leadership's running best estimate of strategic quality, updated week by week as new evidence comes in. It is the central quantity governance uses when deciding whether to continue or stop an initiative.

- **How noisy the evidence is.** A set of parameters governs how quickly the organization can learn about an initiative's true quality — how much noise is in the weekly signals, how that noise is affected by executive attention, and how inherently uncertain the initiative is. These parameters determine the information environment governance operates in.

- **Dependency level.** A fixed characteristic of each initiative that represents how much its outcomes depend on factors outside the team's control — external partners, regulatory approvals, platform decisions, market conditions. Higher dependency makes evidence harder to interpret and slows the organization's ability to form a confident view, regardless of how much attention leadership devotes or how capable the team is.

- **Visible opportunity ceiling (where applicable).** Some initiatives have a visible upper bound on their potential value — a bounded market, a fixed-scope contract, a capturable revenue pool. Leadership can see this ceiling from the start. It does not reveal whether the initiative will succeed, but it calibrates how long it is worth trying to find out.

Beyond these five dimensions, initiatives differ in how they create value. Rather than encoding value creation as a property of the type label, the simulation uses composable value mechanisms that can be attached to any initiative independently. The four mechanisms available in the canonical study are: a one-time completion payoff, an ongoing value stream that persists after completion, a completion-time major-win discovery event, and a completion-time contribution to organizational learning capability. An initiative may use one, several, or none of these mechanisms. The type labels that the study uses — flywheel, right-tail, enabler, quick win — are organizational shorthand for common combinations of these mechanisms and characteristics. They are set during scenario design and carried through for reporting, but the simulation engine treats every initiative the same way: it reads the concrete attributes and value mechanisms, not the label.

## Immutable attributes (set at generation)

### Academic
These fields are set once when the initiative is created and never changed by the engine:

- `initiative_id` (string)
- `created_tick` (integer)
- `required_team_size` (integer, default 1) — minimum team size needed to staff
  this initiative. The canonical default is 1 for all initiative types unless
  explicitly overridden by the generator.
- `latent_quality ∈ [0,1]` — ground-truth strategic quality, fixed at creation,
  hidden from governance
- `dependency_d ∈ [0,1]` — dependency_level: friction that slows learning / raises noise

  Dependency enters the observation model multiplicatively (amplifying `σ_eff`
  via `1 + α_d × d`) and the belief update multiplicatively (attenuating
  learning efficiency via `L(d) = 1 - d`). These effects are independent of
  attention allocation, staffing intensity, and portfolio capability — at
  `d = 1`, the observation carries zero information about intrinsic quality
  regardless of how much attention or staffing is applied.

- `observable_ceiling` (optional numeric, e.g., TAM)

  Observable bounded-prize ceiling for the initiative. When set, represents a
  governance-visible upper bound on the initiative's potential value — the
  maximum payoff if the initiative were to complete at maximum quality.
  Governance-visible from creation. Does not reveal latent quality; it constrains
  the scale of the prize, not the probability of capturing it.

  Governance role: `observable_ceiling` enters the bounded-prize patience rule.
  The effective TAM patience window scales linearly with ceiling magnitude:

  ```
  effective_tam_patience_window = max(1, ceil(T_tam × observable_ceiling / reference_ceiling))
  ```

  where `T_tam` is `base_tam_patience_window` and `reference_ceiling` is the
  normalization constant from `ModelConfig`. Higher ceilings yield proportionally
  longer evaluation windows before the TAM adequacy stop condition can fire.
  `None` for initiatives without a bounded-prize channel. See `governance.md` for
  the complete stop-rule semantics.

- `generation_tag` (optional string used for human-facing type label; for
  reporting and policy-side portfolio classification. The engine does not
  branch on this field. See interfaces.md InitiativeObservation for the
  observation-boundary rationale.)
- `sigma_base` (base_signal_st_dev: base observation noise for the strategic quality signal)
- `initial_belief_c0` (optional explicit prior mean for strategic quality belief;
  defaults to `ModelConfig.default_initial_belief_c0` when absent)

  **Screening signal mechanism.** When a type spec provides
  `screening_signal_st_dev` (sigma_screen), the generator draws an
  ex ante screening signal at initiative creation:

      screening_signal = clamp(q + Normal(0, sigma_screen), 0, 1)
      initial_belief_c0 = screening_signal

  This models the organization's intake evaluation process: business
  cases, feasibility studies, and strategic fit assessments that produce
  a noisy but informative prior about each initiative's quality before
  a team is assigned. The screening signal is correlated with true
  latent quality but with meaningful noise controlled by sigma_screen:

  - Low sigma_screen (e.g., 0.10 for quick wins): intake screening is
    quite informative. These initiatives are well-scoped and relatively
    easy to evaluate upfront.
  - Moderate sigma_screen (e.g., 0.15-0.20 for flywheels/enablers):
    screening is informative but imperfect.
  - High sigma_screen (e.g., 0.30 for right-tail): exploratory moonshots
    whose true quality is inherently hard to assess at intake.

  When sigma_screen is not set, initial_belief_c0 defaults to the global
  `ModelConfig.default_initial_belief_c0` (the uninformative prior),
  preserving backward compatibility.

  **Canonical default-prior rationale:** the canonical study uses
  `default_initial_belief_c0 = 0.5` as the fallback when no screening
  signal is configured. This is the neutral symmetric baseline for
  the bounded strategic-belief state. The canonical presets now provide
  per-type screening signals, so this fallback only applies when
  screening_signal_st_dev is None.
- `true_duration_ticks` (optional integer) — latent ground-truth completion time if
  the initiative is pursued without interruption. Fixed at creation, hidden from
  governance. When set, the engine derives the normalized schedule-fidelity scalar
  (latent_execution_fidelity; q_exec in equations):
  `q_exec = min(1.0, planned_duration_ticks / true_duration_ticks)`.
  Must be set together with `planned_duration_ticks`.
- `planned_duration_ticks` (optional integer) — the organization's observable prior
  estimate of completion time. Set at generation and visible to governance through
  `GovernanceObservation`. May differ substantially from `true_duration_ticks`.
  Must be > 0 when set.
- `initial_c_exec_0 ∈ (0, 1]` (optional float, default 1.0) — the starting value of
  the execution belief (execution_belief_t; c_exec_t in equations). Represents the
  planning prior, not certainty. 1.0 means governance begins with the belief that
  the initiative will run on plan. Lower values represent initiatives where
  leadership begins with reduced confidence in the original schedule. Per-initiative
  configurability allows the generator to assign different execution priors to
  initiative types with different planning reliability (e.g., novel hardware
  programs versus familiar software-only work). Defaults to 1.0 when not specified.
- `capability_contribution_scale ∈ [0, ∞)` (float, default 0.0) — the observable
  scale factor governing how much portfolio capability this initiative contributes
  on completion. Realized capability gain at completion is
  `latent_quality_i × capability_contribution_scale_i`, capped at `C_max` from `ModelConfig`.
  A value of 0.0 means the initiative contributes no portfolio capability on
  completion. The generator sets positive values for initiatives intended to function
  as enablers; all other initiative types default to 0.0.

  This attribute is observable to governance (surfaced in `InitiativeObservation`),
  allowing policies to compute expected capability yield as
  `quality_belief_t × capability_contribution_scale`. The actual realized contribution depends
  on latent quality and is not directly observable by governance until the initiative
  completes — consistent with the existing pattern of observable ceiling versus
  latent quality.

  **Durability note:** enabler effects are durable but not permanent in the
  canonical study. The initiative config controls only the completion-time gain
  magnitude. Decay of the portfolio capability stock is a model-level mechanism,
  parameterized in `ModelConfig` rather than per initiative, because it governs
  the evolution of shared portfolio state rather than the properties of a single
  initiative.

  **Completion eligibility invariant:** if `capability_contribution_scale > 0`,
  the initiative must have a valid completion condition. In the canonical model,
  that means `true_duration_ticks` must be set. This is not optional bookkeeping:
  capability is realized only at the completion transition, so a capability-bearing
  initiative without a completion path would silently encode an effect that can
  never occur.

- `staffing_response_scale ∈ [0, ∞)` (float, default 0.0) — controls how additional
  staffing above `required_team_size` accelerates learning. When 0.0, staffing
  intensity has no effect on learning rate. When positive, larger assigned teams
  produce faster learning with diminishing returns. The learning-rate multiplier
  saturates toward `1.0 + staffing_response_scale` as team surplus grows. Per
  `opportunity_staffing_intensity_design_for_claude_v2.md`.
- `prize_id` (str | None) — links right-tail frontier re-attempts back to the
  original prize descriptor. `None` for initial pool initiatives and non-right-tail
  frontier draws. When set, the runner uses this to locate the corresponding
  `PrizeDescriptor` in the world state for attempt tracking and prize-preserving
  refresh. Per `dynamic_opportunity_frontier.md` §2.

- `value_channels` — structured, composable description of how value may be created:
  - `completion_lump`:
    - `enabled` (bool)
    - `realized_value` (numeric, required when `enabled == true`)
      Must be `>= 0`. If `enabled == false`, this field is ignored and may be
      absent.
  - `residual`:
    - `enabled` (bool)
    - `activation_state` ∈ {`completed`}
    - `residual_rate` (numeric)
    - `residual_decay` (numeric; per-tick exponential decay rate, `>= 0`)
  - `major_win_event`:
    - `enabled` (bool)
    - `is_major_win` (hidden bool, immutable, generator-assigned)

      Determined at generation as a deterministic threshold function of latent
      quality: `is_major_win = (q >= q_major_win_threshold)`. Hidden from
      governance throughout the run. There is no stochastic revelation mechanism
      and no intermediate discovery state — the flag is binary, immutable, and
      revealed only at completion through the emitted `MajorWinEvent`.

#### Notes on `value_channels`

Under the canonical completion-gated model, value is realized only at the
`completed` transition, never tick-by-tick during execution. There is no
streaming channel and no pre-completion discovery realization. The available
channels are `completion_lump`, `residual`, and `major_win_event`; a single
initiative may use one, multiple, or none of them. `major_win_event` records
that completion surfaced a major win and is analytically distinct from realized
economic value. The engine branches on these resolved channel attributes only,
never on human-facing initiative labels. Channel structure is declarative — it
determines whether a channel exists and when it activates, but does not embed formulas. Canonical equations belong in
`core_simulator.md`, not in per-initiative instance data.

For residual channels, `residual_decay` is the initiative-local decay parameter
for the canonical exponential law. It controls how quickly the residual stream
erodes after activation; higher values imply faster erosion. The configured
`residual_rate` is the activation-tick rate before decay has had time to act.

**Residual requires completability:** if `value_channels.residual.enabled == true`
and `value_channels.residual.activation_state == "completed"`, then
`true_duration_ticks` must be set on the initiative. Without a completion
condition, the activation trigger can never fire, and the residual channel would
silently encode an unreachable effect — the same structural issue that the
capability completion eligibility invariant addresses.

### Business
Every initiative arrives in the simulation with a set of properties that are fixed at the moment it is created and never change during the run. These properties define what the initiative fundamentally is — its true quality, its inherent uncertainty, what kind of value it can produce, and how long it would actually take to complete. Some of these properties are visible to leadership from the start. Others are hidden and can only be inferred from evidence that accumulates as teams work.

**Identity and basic structure.**

Each initiative has a unique identifier and a record of when it was created. It also has a minimum team size required to staff it — the smallest team that can meaningfully work on this initiative. The default is a single team unit for all initiative types unless the scenario design explicitly specifies otherwise.

**True underlying quality.** Every initiative has a true strategic quality, ranging from zero (no value) to one (maximum value). This is the ground truth that governs what the initiative would actually deliver if pursued to completion. It is fixed at creation and completely hidden from governance throughout the run. Leadership can never observe it directly — only infer it through noisy weekly evidence.

**Dependency level.** Each initiative has a fixed dependency level, ranging from zero (completely self-contained) to one (completely dependent on external factors). This represents how much the initiative's outcomes depend on things the team cannot control — vendor timelines, regulatory decisions, platform dependencies, market conditions. Higher dependency makes the weekly strategic evidence harder to interpret and slows the organization's ability to form a confident view, regardless of how much attention leadership pays or how talented the team is. Dependency does not change during the initiative's life. A heavily interconnected initiative remains heavily interconnected throughout.

**Visible opportunity ceiling.** Some initiatives have a visible ceiling on their potential value — a total addressable market, a fixed contract scope, an estimable revenue pool. This ceiling is visible to leadership from the moment the initiative is created. It does not reveal whether the initiative will succeed, but it plays a critical role in governance: it calibrates how patient governance should be. An initiative with a large visible ceiling earns more runway before governance concludes the investment is not justified. An initiative with a small visible ceiling reaches that conclusion faster. The patience relationship is direct and proportional: a ceiling twice as large earns proportionally more patience.

**Type label.** Each initiative may carry a human-readable type label — flywheel, right-tail, enabler, quick win — set during scenario design. This label is carried through for reporting and, in some governance regimes, for portfolio classification purposes such as maintaining a target mix of initiative types. The simulation engine itself never applies different rules based on this label. It is organizational metadata, not an operational input. This distinction is the same one that applies to the visible ceiling and the capability contribution scale: all three are set at creation, visible to governance, and available for governance to use in its decision-making — but the engine treats every initiative identically based on its concrete attributes.

**Inherent signal noise.** Each initiative arrives with a baseline level of strategic signal noise — how hard it is, by its nature, to tell whether the initiative is strategically sound. A straightforward product extension in a well-understood market produces relatively clean signals. A speculative entry into an unfamiliar domain produces noisy ones. This baseline is a property of the initiative and does not change over time. It enters the effective noise calculation alongside dependency, executive attention, and organizational capability (see the section on effective noise in the core simulator document).

**Starting belief about strategic quality.** Each initiative may specify an explicit starting point for the organization's belief about its strategic quality. When not specified, the initiative defaults to the study's canonical starting belief of 0.5 — the neutral midpoint of the zero-to-one belief scale.

The choice of 0.5 as the default is deliberate. It represents maximum prior uncertainty: the organization begins with no information favoring either optimism or pessimism about the initiative before any evidence has been observed. This keeps early governance behavior from being pre-biased in either direction. Organizations that systematically over-estimate or under-estimate the quality of their intake pipeline are meaningful to study, but that belongs in sensitivity analysis through explicit variation of the starting belief rather than in the baseline scenario.

**True completion time.** Some initiatives have a defined true completion time — how long the work would actually take if pursued without interruption. This is hidden from governance. It is the ground truth that the organization's execution evidence gradually reveals. When set, the simulation uses it to derive the initiative's true execution fidelity: the ratio of planned time to actual time, capped at one. An initiative planned for 12 months that would actually take 18 months has a true execution fidelity of approximately 0.67, meaning it will take roughly 50% longer than planned. This fidelity is the hidden quantity that the execution belief tracks.

The true completion time must be specified together with a planned completion time. You cannot have a hidden truth about execution without an observable plan to compare it against.

**Planned completion time.** The organization's observable estimate of how long the initiative will take. This is set at creation and visible to governance from the start. It may differ substantially from the true completion time — some initiatives are planned optimistically, others conservatively. The planned time serves as the reference point against which execution progress is measured and reported.

**Starting belief about execution.** Each initiative may specify how confident the organization is at the outset about the initiative's schedule. The default is 1.0, meaning governance initially believes the initiative will run exactly on plan. Lower values represent initiatives where leadership begins with reduced confidence in the original schedule — for example, novel hardware programs or initiatives in domains where planning accuracy is historically poor, versus familiar software-only work where schedules are typically more reliable. This per-initiative configurability allows the scenario to reflect the reality that different kinds of work arrive with different levels of schedule credibility.

**Capability contribution scale.** Each initiative carries a visible indicator of how much it would contribute to the organization's learning capability if completed. This is the organizational capability yield — how much completing this initiative would improve the organization's ability to evaluate all future work. The default is zero: most initiatives contribute no organizational capability on completion. Initiatives intended to function as enablers — analytics infrastructure, experimentation platforms, process improvements — carry positive values.

Leadership can see this scale from the start and can estimate the expected capability yield by multiplying it by the current belief about the initiative's quality. The actual realized contribution at completion depends on the initiative's true quality, which remains hidden until the work is done — consistent with the general pattern where leadership sees the potential (the ceiling, the capability scale) but not the underlying truth about whether the initiative is good enough to realize it.

**Durability of capability effects.** Enabler effects are durable but not permanent. The initiative's capability contribution scale controls only how large the gain is at the moment of completion. How quickly the organization's accumulated capability advantage erodes over time is a portfolio-level property, not a per-initiative property, because capability decay governs the evolution of shared organizational state rather than the characteristics of any single initiative.

**Capability requires completability.** If an initiative is configured to contribute organizational capability on completion, it must have a defined completion condition — meaning it must have a true completion time. This is not optional bookkeeping. Capability is realized only at the completion transition. An initiative configured to contribute capability but with no path to completion would encode an effect that can never occur, silently distorting the scenario design.

**Staffing intensity effect on learning.** Each initiative carries a parameter that controls how much additional staffing above the minimum required accelerates learning. When this parameter is zero (the default), team size above the minimum has no effect on how quickly the organization learns — a team either meets the staffing threshold or it does not. When positive, assigning a team larger than the minimum accelerates learning with diminishing returns: the first additional capacity helps substantially, further additions help progressively less. The maximum acceleration approaches a level determined by the parameter's value as team surplus grows. This is a per-initiative study parameter expressing a modeled hypothesis about how strongly learning responds to additional staffing, not an empirical truth.

**Prize descriptor link.** For right-tail initiatives generated through the dynamic opportunity frontier — where a stopped attempt at a persistent market opportunity can be retried with a fresh approach — each re-attempt carries a link back to the original prize descriptor. This allows the simulation to track how many attempts have been made at a given opportunity and to apply any configured quality degradation for repeated attempts. Initial pool initiatives and non-right-tail frontier draws do not carry this link.

**Value channels — the composable description of how value is created.** Every initiative specifies which value-creation mechanisms it uses. These are configured independently and can be combined freely:

*One-time completion payoff.* When enabled, the initiative produces a single economic payoff at the moment it completes. The configured payoff value must be non-negative, and must be explicitly specified — the simulation does not silently default to zero for an enabled payoff channel, because a missing value likely indicates a configuration error rather than an intentional choice.

*Ongoing value stream (residual).* When enabled, the initiative activates a persistent value mechanism upon completion that continues producing returns every week after the team has moved on. The mechanism starts at its configured rate on the activation week and then decays over time at a rate specific to that initiative. Some mechanisms are highly durable — a marketplace platform that degrades very slowly — while others are more ephemeral. The configured rate represents the mechanism's starting output before any decay has occurred.

*Major-win discovery event.* When enabled, the initiative carries a hidden flag — set at creation, immutable, and invisible to governance — that determines whether completing this initiative would surface a major win. This flag is a deterministic consequence of the initiative's true underlying quality: initiatives whose quality exceeds the major-win threshold are major wins, and those below it are not. There is no randomness in the determination once quality is fixed.

**How value channels interact with the type-independence principle.** Under the canonical study design, no value is realized during execution. All value realization is gated on completion — there is no streaming value during active work and no pre-completion discovery. The available channels are the one-time completion payoff, the ongoing value stream, and the major-win discovery event. A single initiative may use one, several, or none of them. The major-win discovery event is analytically distinct from realized economic value — it records that completion surfaced a transformational outcome, but it does not price that outcome.

The simulation engine reads these channel configurations directly. It never asks "is this a flywheel?" or "is this a right-tail bet?" It asks "does this initiative have a residual channel enabled?" and "did this initiative complete with a major-win flag set to true?" This is what makes the type labels genuinely independent of the engine: new types can be defined, existing types can be renamed or reorganized, and none of it requires any change to how the simulation processes initiatives — as long as the new types can be expressed as combinations of the existing value mechanisms and initiative attributes.

For ongoing value streams, the per-initiative decay rate controls how quickly the stream erodes after activation. Higher decay means faster erosion. The configured starting rate is what the mechanism produces on the week it first activates, before any decay has had time to act.

## Mutable state (engine updates)

### Academic
These fields change during the run:

- `lifecycle_state` ∈ {unassigned, active, stopped, completed}
- `assigned_team_id` (or `null`)
- `exec_attention_a ∈ [0,1]` — last-applied executive attention (executive_attention_t)
- `quality_belief_t ∈ [0,1]` — organization's posterior mean estimate of strategic quality.
  This is the strategic belief only. It does not encode execution fidelity;
  that is tracked separately in `execution_belief_t`.
- `execution_belief_t ∈ [0, 1]` — organization's posterior belief about schedule fidelity
  relative to plan. Initialized to `initial_c_exec_0` (the planning prior, not
  certainty about execution). 1.0 means governance currently believes the initiative
  will run on plan; values below 1.0 reflect a projected overrun relative to
  `planned_duration_ticks`. Defined and updated only when `true_duration_ticks` is
  set on the initiative. Independent of `quality_belief_t`.
  The belief update formula clamps to `[0, 1]`, making zero admissible in state.
  Division-by-zero when computing `implied_duration_ticks` is guarded by the
  module-level constant `epsilon_exec = 0.05` defined in `interfaces.md`; the
  state bound and the computational guard are separate concerns.
- `staffed_tick_count` (integer) — cumulative lifetime count of ticks during which
  this initiative has been actively staffed. This counter never resets after
  reassignment. It is the clock used for:
  - completion detection for bounded-duration initiatives,
  - the stagnation window, which is defined over staffed ticks rather than
    calendar ticks,
  - cumulative progress tracking against the original plan.
- `ticks_since_assignment` (integer) — count of staffed ticks since the most recent
  team assignment to this initiative. This counter resets to 0 on each new team
  assignment and increments only while the initiative is staffed. It exists solely
  for assignment-relative logic such as ramp-up and must not be used for
  stagnation or completion detection.
- `cumulative_value_realized` (numeric) — aggregate across all value channels
- `cumulative_lump_value_realized` (numeric) — completion-lump channel only
- `cumulative_residual_value_realized` (numeric) — residual channel only
- `cumulative_labor_invested` (numeric) — total team-ticks consumed
- `cumulative_attention_invested` (numeric) — total executive attention consumed
- `age_ticks` (integer) — calendar ticks since creation, incremented each tick
  regardless of staffing state. Distinct from `staffed_tick_count`, which
  advances only while the initiative is staffed.
- `ramp_state` (if newly assigned, ramp ticks remaining)
- `observed_history` (sufficient statistics or time-series of observations, beliefs, and review-relevant summaries)
- `residual_activated` (bool) — whether any residual mechanism is now in effect
- `residual_activation_tick` (optional integer)
- `major_win_tick` (optional integer)
- `completed_tick` (optional integer)
- `consecutive_reviews_below_tam_ratio` (integer)

  Counter of consecutive end-of-tick reviews at which the bounded-prize adequacy
  test failed (`quality_belief_t × observable_ceiling < θ_tam_ratio × observable_ceiling`).
  Updated by the engine at step 5b before governance invocation. Resets to zero
  on any reviewed tick where the test passes, and resets to zero for any tick
  on which the initiative is not reviewed (unstaffed, stopped, or completed).
  A gap in active evaluation breaks the consecutive-review streak.

<!-- specification-gap: `review_count` (integer) is engine-tracked mutable state used by the governance observation boundary (exposed in `InitiativeObservation`) and required for the stagnation and TAM patience rules, but is not listed as a separate mutable state field in this section or in the business source. It should be specified here with its increment rule (once per end-of-tick governance invocation for each initiative that is both active and staffed). -->

#### Major-win discovery event state

If a completion-time discovery event fires, that outcome must not be represented only as a status flag. The engine must also emit a structured event record for downstream analysis.

Canonical major-win event payload:

- `initiative_id`
- `tick`
- `latent_quality`
- `observable_ceiling`
- `quality_belief_t_at_completion`
- `cumulative_labor_invested`
- `cumulative_attention_invested`
- `observed_history_snapshot`

The `observed_history_snapshot` is an immutable snapshot of the initiative's observation/belief trajectory through the completion tick. This is required so discovery efficiency and belief-path questions can be analyzed after the run without depending on later state changes.

The snapshot preserves the complete belief path — not only terminal values but
the full trajectory of belief evolution over staffed ticks. This supports
post-run analysis of discovery efficiency (labor and attention per major win),
near-termination events (ticks at which governance nearly stopped an initiative
that ultimately surfaced a major win), and belief convergence dynamics (how
many observations were required before the belief trajectory stabilized near
the latent quality).

### Business
While each initiative's fundamental character is fixed at creation, a substantial amount of state evolves as the simulation runs. This evolving state tracks everything the organization is learning, every decision governance has made, and every consequence that has accumulated — the full operational history of the initiative from the perspective of both governance and the simulation engine.

**Lifecycle state.** Each initiative is in exactly one of four states at any given time: unassigned (in the pool but not staffed), active (staffed and generating evidence), stopped (governance has terminated the initiative), or completed (the initiative has finished its work). The simulation tracks the current state and enforces legal transitions between them.

**Team assignment.** Which team, if any, is currently assigned to the initiative. An unassigned initiative has no team and generates no evidence. An active initiative always has an assigned team.

**Executive attention level.** The most recently applied level of executive attention for this initiative, ranging from zero (no attention) to one (maximum attention). This is the operational attention level that governs how much noise is in the strategic quality signals the initiative produces this week.

**Strategic quality belief.** The organization's current best estimate of the initiative's strategic quality, ranging from zero (no strategic value) to one (maximum value). This is the strategic belief only — it reflects the organization's assessment of how promising the initiative is. It does not incorporate any information about execution progress; that is tracked separately. This belief updates every staffed week based on the strategic evidence the initiative produces.

**Execution belief.** The organization's current estimate of how well the initiative is tracking relative to its original plan, ranging from zero to one. A value of 1.0 means the organization believes the initiative will finish on schedule. A value of 0.5 means the organization believes the initiative will take roughly twice as long as planned. This belief is initialized at the planning prior — typically 1.0, meaning the organization starts by assuming the plan is on track — and updates independently of the strategic quality belief based on separate execution evidence. It is defined and updated only for initiatives that have a specified true completion time.

The execution belief can reach zero, which is a valid state representing extreme loss of schedule confidence. When the simulation needs to translate this belief into an implied completion time, a floor is applied to prevent dividing by zero — this caps the implied duration at twenty times the original plan, an extreme but finite number. The state boundary (zero is allowed in the belief) and the computational guard (a floor prevents arithmetic failure) are separate concerns handled separately.

**Lifetime staffed-time count.** The cumulative count of weeks during which this initiative has had a team assigned, across all assignments over its entire life. This counter never resets when a new team is assigned — it is a lifetime clock. It serves three critical purposes: detecting whether the initiative has reached its true completion point, evaluating whether the organization's belief has stagnated over a sustained period of active work (the stagnation window counts staffed weeks, not calendar weeks), and tracking progress against the original plan.

**Assignment-relative time count.** The count of staffed weeks since the most recent team was assigned to this initiative. This counter resets to zero on each new team assignment and advances only while the initiative is staffed. It exists solely for computing the ramp productivity adjustment — how much the newly assigned team's learning efficiency is reduced during their transition period. It must not be used for stagnation assessment, completion detection, or progress tracking, all of which use the lifetime staffed-time clock.

**Cumulative accounting.** The simulation tracks running totals of: total value realized (across all channels), value realized from one-time completion payoffs, value realized from ongoing residual streams, total labor invested (team-weeks), and total executive attention invested. These cumulative figures enable cross-regime comparison of resource efficiency and value composition.

**Calendar age.** How many weeks the initiative has existed since creation, regardless of whether it was staffed.

**Ramp state.** When a team is newly assigned, the initiative tracks the remaining ramp period — how many more weeks until the current team reaches full learning productivity.

**Evidence history.** The full record of observations, belief updates, and review-relevant summaries accumulated over the initiative's life. This history is maintained by the simulation engine and serves as the basis for governance decisions and post-run analysis.

**Residual activation status.** Whether an ongoing value mechanism has been activated for this initiative, and if so, which week it was activated. Once activated, the mechanism continues producing value every week regardless of team assignment.

**Major-win discovery timing.** If the initiative was completed and turned out to be a major win, the week that discovery occurred.

**Completion timing.** If the initiative completed, the week it did so.

**Consecutive below-threshold review count.** For initiatives with a visible opportunity ceiling, the count of consecutive reviews at which the expected payoff (current belief multiplied by the ceiling) fell below the governance patience threshold. This counter is central to the bounded-opportunity patience rule: when it reaches the patience window threshold, governance may stop the initiative. It resets to zero whenever the expected payoff is adequate, and also resets to zero whenever the initiative is not reviewed in a given week — a gap in active evaluation breaks the streak.

**Major-win discovery event records.** When an initiative completes and turns out to be a major win, the simulation does not merely set a flag. It emits a detailed structured record capturing everything needed for post-run analysis of how governance discovered (or failed to discover) transformational outcomes. This record includes: which initiative it was, when the discovery happened, the initiative's true underlying quality, the visible opportunity ceiling, what governance believed about the initiative's quality at the moment of completion, how much total labor was invested, how much total executive attention was devoted, and a complete snapshot of the initiative's evidence and belief history through the completion week.

The evidence history snapshot is frozen at the moment of completion. This ensures that analysts can study discovery efficiency and belief trajectories after the run without depending on any state changes that might occur later in the simulation. The snapshot captures the full path — not just where the organization ended up, but how its beliefs evolved over the course of active work — which is essential for understanding whether governance nearly terminated the initiative, how quickly it converged on the right view, and how much evidence was needed before the picture became clear.

## Lifecycle states and transitions

### Academic
- **unassigned** — in pool, not staffed

  The initiative exists in the available pool but has no assigned team. It
  generates no observations, produces no value, consumes no labor, and receives
  no executive attention. No belief updates occur. This is the initial state
  for all initiatives at pool creation and the state to which dynamically
  materialized frontier initiatives are added.

- **active** — staffed and producing observations/value

  A team is assigned. Per `core_simulator.md` step 3, the engine generates
  strategic quality signals (`y_t`) and, where applicable, execution progress
  signals (`z_t`) at each staffed tick. Both belief scalars update, lifecycle
  transitions are evaluated, and governance must emit an explicit `ContinueStop`
  action for each active staffed initiative at every governance invocation.
  This is the only lifecycle state in which observations, belief updates, and
  value production occur.

- **stopped** — governance has stopped the initiative; it no longer produces value

  The transition is irreversible within the run. A stopped initiative produces
  no further observations, realizes no further value of any kind, and does not
  activate any latent value channel — regardless of proximity to the completion
  threshold at the time of the stop decision. Specifically: stopping an
  initiative prior to completion forfeits any configured completion-lump value,
  prevents residual activation, precludes major-win discovery, and foregoes any
  capability contribution. The semantic distinction between `stopped` and
  `completed` is load-bearing for the study's comparative analysis: governance
  regimes that terminate initiatives prematurely forfeit not only the direct
  completion-time payoff but all downstream compounding effects (residual
  accumulation, capability development, major-win discovery) that completion
  would have generated.

- **completed** — initiative finished its lifecycle (optional)

  The initiative has reached its completion condition
  (`staffed_tick_count >= true_duration_ticks`). This transition triggers all
  enabled completion-time effects in the order defined in `core_simulator.md`
  step 5c: completion-lump value realization, major-win event emission, residual
  activation, and capability contribution. The team is released for reassignment
  effective at the start of tick `t+1`.

Transitions are triggered by:
- Governance actions (stop/continue, assignment)
- Completion rules based on initiative-specific completion conditions

The canonical transition graph is:

```
unassigned → active      (AssignTeam governance action)
active     → stopped     (ContinueStop = stop governance action)
active     → completed   (engine completion detection: staffed_tick_count >= true_duration_ticks)
```

No other transitions are valid. In particular: `stopped` and `completed` are
absorbing states — once entered, the initiative remains in that state for the
remainder of the run. There is no mechanism to restart a stopped initiative or
to revert a completion.

<!-- specification-gap: The state transition function is described narratively. An OR reader may expect a formal transition table specifying guards (preconditions), actions (what fires on transition), and post-conditions for each valid transition. The guards and effects are specified across `core_simulator.md` step 5c and `governance.md`, but are not consolidated into a single formal specification in this document. -->

#### Residual activation semantics

Residual value does not activate merely because an initiative once had a residual channel configured. It activates only when:

1. `value_channels.residual.enabled == true`, and
2. the initiative enters the configured `activation_state`.

Allowed canonical activation states are:

- `completed`

Once activated, the residual stream continues to produce value according to the residual parameters even if the initiative is no longer staffed. This is distinct from portfolio capability. Residual value is an ongoing value flow from a previously created mechanism; portfolio capability is a persistent state that changes the quality of future strategic learning across the portfolio.

Both residual value and capability contribution are consequences of completion,
but they operate through independent channels and produce structurally different
kinds of long-run advantage. Residual value contributes to the realized economic
performance outcome family. Portfolio capability contributes to the
organizational capability development outcome family and enters future ticks'
`σ_eff` computation as a divisor.

#### Completion-time discovery without follow-on initiative

For right-tail initiatives, the generator assigns an immutable hidden boolean `is_major_win` at creation when the `major_win_event` channel is enabled. A right-tail initiative can surface a major win only upon completion. On completion, if `is_major_win == true`, the engine records a structured `MajorWinEvent`. The engine does **not** automatically spawn a follow-on commercialization or exploitation initiative, and the canonical study does **not** require pricing the full downstream economics of that win within the simulation horizon. This is a deliberate scoping choice in the canonical study, not an omission.

The `is_major_win` flag is determined at generation as a deterministic threshold
function of latent quality (`is_major_win = (q >= q_major_win_threshold)`) and
remains hidden from governance throughout the run. There is no intermediate
discovery state and no probabilistic revelation mechanism. Governance can only
increase the probability of surfacing major wins by sustaining investment in
high-quality right-tail initiatives through completion.

The study measures governance's ability to preserve the option value of
transformational discovery — surfacing rate, time to discovery, and labor
efficiency — not the downstream economic value of exploiting a surfaced
major win. The downstream value depends on factors outside the model's scope
and would add parameterization burden without improving the governance
comparison.

### Business
Every initiative in the simulation exists in one of four states at any given time:

- **Unassigned** — the initiative is in the available pool but has no team working on it. It generates no evidence, produces no value, and does not consume labor or attention. It is an opportunity waiting to be pursued.

- **Active** — a team is assigned and working. The initiative generates weekly strategic and execution evidence, the organization's beliefs update accordingly, and governance must make explicit continue-or-stop decisions at each review. This is the only state in which work, evidence, and learning occur.

- **Stopped** — governance has terminated the initiative. The team is released. The initiative no longer produces evidence, value, or any other effect. Stopping is permanent within the run. Critically, a stopped initiative never activates any ongoing value mechanism and never contributes to organizational capability — even if it was close to completion when stopped. The distinction between stopping and completing is semantically load-bearing in the study design: governance regimes that stop initiatives too early forfeit not just the direct payoff but all downstream compounding effects those completions would have generated.

- **Completed** — the initiative has finished its work. This transition triggers all completion-time effects: any one-time payoff is realized, any ongoing value mechanism activates, any major-win discovery is revealed, and any capability contribution is recorded. The team is released for reassignment starting the following week.

Transitions between states are triggered by two mechanisms: governance actions (assigning a team moves an initiative from unassigned to active; stopping it moves it from active to stopped) and the simulation's completion detection (when an active initiative has accumulated enough staffed time to reach its true completion point, the engine transitions it to completed).

**When ongoing value mechanisms activate.** An initiative's ongoing value mechanism does not activate simply because the initiative was configured to have one. Activation requires two conditions: the mechanism must be enabled in the initiative's configuration, and the initiative must actually reach the configured trigger state — in the canonical study, that means completion. An initiative with a configured residual channel that is stopped before completing never activates its ongoing value mechanism. This is a fundamental property of the study design, not an edge case.

Once activated, the ongoing value mechanism operates independently. It continues producing weekly returns whether or not a team is assigned, whether or not governance is paying attention, and whether or not the initiative appears anywhere in governance's active portfolio. This is structurally distinct from organizational capability. Ongoing value is a self-sustaining economic mechanism left behind by completed work — a distribution network, an automation system, a marketplace platform. Organizational capability is a persistent change to the organization's ability to evaluate future work. Both are consequences of completion, but they operate through different channels and produce different kinds of long-run advantage.

**When major-win discoveries are recorded.** For right-tail initiatives, whether the initiative turns out to be a major win is determined at the moment the initiative is created — it is a deterministic consequence of the initiative's true underlying quality relative to the major-win threshold — and remains completely hidden until completion. There is no early warning, no intermediate discovery state, and no probabilistic revelation. The initiative either reaches completion and reveals itself as transformational, or it does not. Governance can only increase the probability of surfacing major wins by keeping promising right-tail initiatives alive long enough to finish.

When a major win is surfaced at completion, the simulation records the discovery event in full detail but does not spawn a follow-on commercialization initiative and does not attempt to price the full downstream economic value of the discovery within the study horizon. This is a deliberate scoping choice. The study measures governance's ability to find transformational outcomes — how many, how quickly, at what cost — not the full downstream consequences of exploiting them. The downstream value depends on organization-specific factors (competitive position, execution capability, market timing) that are outside the model's scope and would add complexity without improving the governance comparison.

## Generator contract (summary)

### Academic
The runner must provide the engine with either:
- an explicit `initiatives` list where each item is resolved with concrete immutable fields above; **OR**
- an `initiative_generator` specification that the runner deterministically resolves (given `world_seed`) into a concrete initiatives list before simulation start.

The engine **must not** accept type-based branching; any labeled priors must be resolved before the engine sees initiative records. New human-facing initiative labels may be added, changed, or removed without requiring engine changes so long as they are expressible using the existing mechanism basis above.

The engine is agnostic to how the resolved initiative list was produced. Whether
it originated from a hand-crafted scenario, a named environment archetype, or a
parameter sweep has no bearing on engine behavior — the engine consumes only the
realized initiative attributes and their associated RNG streams. Provenance
metadata is recorded in the run manifest for reproducibility and attribution but
does not enter any engine computation.

The initiative-type taxonomy — which families exist, how they are named, what
combinations of attributes and value channels they represent — is entirely a
matter of scenario design and reporting, decoupled from how the engine processes
individual initiatives. The engine's input contract is defined over the resolved
attribute and value-channel schema specified in this document, not over a fixed
set of type labels. This is the concrete implication of the type-independence
invariant (`canonical_core.md` invariant #1): new families can be introduced,
existing families can be redefined, and none of it requires any change to the
engine — so long as the new or modified families are expressible as combinations
of the existing immutable attributes and canonical value-channel mechanisms.

### Business
Before the simulation begins, the engine must receive a concrete, fully resolved list of initiatives where every attribute described above has been determined. There are two ways to produce this list:

The first is to provide the list directly — each initiative hand-specified with all of its immutable attributes, value channel configurations, and other properties explicitly set. This approach is useful for targeted scenarios and edge-case testing.

The second is to provide a specification for how to generate initiatives — a description of the desired portfolio composition, the distributions to draw from for each initiative type, and the parameters that govern quality, duration, noise, and value channels — and let the runner deterministically resolve that specification into a concrete initiative list using the world seed. The key word is deterministically: the same specification and the same seed always produce exactly the same initiative pool.

Regardless of which approach is used, the engine receives only the resolved list. It does not know or care how the list was produced.

**The engine must never apply different rules based on initiative type labels.** Any type-specific characteristics — the fact that flywheels tend to have residual value streams, that right-tail initiatives tend to have high noise and major-win potential, that enablers contribute capability — must be fully resolved into concrete attribute values before the engine sees them. The engine processes initiatives based on their attributes and value channel configurations, never based on what label they carry.

This contract has an important practical consequence: new initiative types can be defined, existing types can be renamed, type definitions can be reorganized — and none of it requires any change to the simulation engine. As long as the new or modified types can be expressed as combinations of the existing initiative attributes and value mechanisms described in this document, they work automatically. The organizational taxonomy of initiative types is entirely a matter of scenario design and reporting, decoupled from how the simulation processes individual initiatives.
