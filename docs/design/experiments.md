# Experiments and recommended baselines

## Goals

### Academic
The study evaluates governance regimes on four outcome dimensions that together
span the value-creation mechanisms available to the modeled organization. The
comparison is structured to distinguish regimes that differ in mechanism mix and
portfolio trajectory, not merely in terminal aggregates.

- Compare governance regimes by:
  - cumulative value across channels,
  - probability/time-to-major-win for right-tail opportunities,
  - surfaced major-win counts and labor-per-major-win efficiency,
  - portfolio learning-capability development if enablers are in scope.

The decomposition of cumulative value across channels — completion-lump payoffs,
accumulated residual streams, and capability contributions — is analytically
essential. Two policies may produce comparable terminal cumulative value through
structurally different mechanism mixes: one dominated by high-throughput
completion lumps, the other by a smaller number of completed flywheel initiatives
whose residual streams compound over the remaining horizon. These represent
distinct portfolio value trajectories with different sustainability properties
beyond the study horizon. The value trajectory over time, not merely the terminal
level, is a required output, because residual-stream accumulation accelerates as
the portfolio of completed flywheel initiatives grows.

Major-win discovery performance includes both the probability of surfacing at
least one major win within the horizon and the expected time to first major win,
conditional on the regime's stopping and attention-allocation behavior. Where
ensemble sizes support it, the surfaced major-win count distribution and its
confidence interval should be reported.

Labor-per-major-win efficiency measures the opportunity cost of discovery in the
study's scarce resource unit: total labor-ticks consumed per surfaced major win.
This separates regimes that surface major wins as a byproduct of broad portfolio
management — leaving labor capacity available for other value channels — from
regimes that achieve comparable surfacing rates only by concentrating the labor
endowment on right-tail initiatives at the expense of other mechanisms.

Terminal portfolio capability `C_T` — the accumulated enabler-driven noise
reduction at horizon end — represents the system's investment in learning
infrastructure. Because `C_t` enters the effective signal standard deviation
`σ_eff` as a divisor, terminal capability governs the precision of strategic
quality inference for all future initiatives. Two regimes with similar cumulative
realized value may leave the system in materially different capability states.
This distinction is invisible to any metric confined to realized value within
the study horizon but is load-bearing for any assessment of the system's capacity
to evaluate future opportunity pools.

### Business
The study compares governance regimes on four dimensions that together capture the full range of ways an organization creates long-term value:

- **Cumulative economic value across all channels.** Total value created over the six-year horizon, decomposed by source — one-time completion payoffs, ongoing compounding streams, and any other value mechanisms in scope. The decomposition matters as much as the total, because two regimes can produce similar headline numbers through structurally different means.
- **Major-win discovery performance.** How likely the governance regime is to surface a genuinely transformational opportunity among its exploratory initiatives, how long that takes, how many major wins are surfaced in total, and how much organizational effort is required per major win. This measures governance's ability to preserve access to the largest potential outcomes rather than terminating them prematurely.
- **Labor efficiency in pursuing transformational outcomes.** How much total workforce investment is consumed per major win discovered. A regime that surfaces major wins but requires the entire organization's effort to do so is doing something different from one that surfaces them while also pursuing other valuable work.
- **Portfolio learning-capability development.** How much the governance regime invests in — or neglects — the organizational infrastructure that makes future initiative evaluation faster and more accurate. This dimension is included whenever enabler initiatives are part of the portfolio, because two regimes with similar economic results can leave the organization in very different states of readiness for what comes next.

## Experimental methodology


### Academic
The study uses a parameter sweep across the governance configuration space as its
primary methodology. Because individual simulation runs complete in subsecond time
on commodity hardware, the study can evaluate thousands of governance regimes across
multiple environmental configurations within a single workstation session. Named
archetypes are anchor points in the parameter space — recognizable reference
configurations that make findings interpretable — not the complete experimental
universe.

The sweep approach allows the study to map the response surface of long-run value
creation as a continuous function of governance parameters, estimate main effects,
surface candidate interaction patterns for later targeted follow-up, and determine
which governance configurations are robust across environmental conditions versus
which are highly tuned to a specific opportunity structure.

The study now distinguishes three layers when defining experiments:

- **Environmental conditions** vary the world the regime faces.
- **Governance architecture** varies the pre-run structural organization of
  labor and standing portfolio guardrails.
- **Operating policy** varies the recurring tick-by-tick decision logic.

The canonical baseline sweep varies **operating policy** across fixed
environmental conditions and a fixed governance architecture. Architecture
variation is a separate experiment family unless it is explicitly promoted into
the canonical design.

Portfolio-governance controls should be treated as a targeted follow-up
experiment family unless and until they are consciously promoted into the
canonical governance sweep. The canonical baseline sweep should not silently
expand in dimensionality merely because the interface makes those controls
available.

The same caution applies to workforce architecture. Team count, team size, and
other decomposition choices should not silently become sweep dimensions in the
canonical operating-policy study merely because the repo can represent them.

### Business
The study's primary method is a systematic sweep across the governance decision space — not a comparison of three or four hand-picked governance philosophies, but a structured exploration of how outcomes change as governance parameters are varied continuously. Because individual simulation runs complete in less than a second on ordinary hardware, the study can evaluate thousands of distinct governance configurations across multiple organizational environments in a single session. The three named archetypes (Balanced, Aggressive stop-loss, Patient moonshot) serve as recognizable anchor points that make results interpretable to practitioners, but they are reference marks in a much larger landscape, not the complete experiment.

This sweep approach allows the study to map how long-run value creation responds to governance choices as a continuous surface rather than a small set of discrete comparisons. It can estimate which governance parameters matter most, identify where governance choices interact in unexpected ways, surface regions of the decision space worth examining more closely, and determine which governance configurations are robust across different organizational environments versus which perform well only under specific conditions.

The study distinguishes three layers when defining what is varied in an experiment:

- **Environmental conditions** vary the world the organization faces — the mix of initiative types available, how uncertain they are, how often transformational opportunities arise, and how the attention-to-learning relationship is shaped.
- **Governance architecture** varies how the organization is structured before the run begins — how the workforce is divided into teams, what standing portfolio guardrails are set, and what concentration limits are in place.
- **Operating policy** varies the recurring week-by-week decision logic — how aggressively to stop underperforming work, how to allocate executive attention, how patient to be with uncertain initiatives.

The canonical baseline sweep varies **operating policy** while holding environmental conditions and governance architecture fixed. This isolates the effect of governance decisions from the effect of operating in a different environment or having a different organizational structure. Architecture variation — changing team count, team size, or workforce decomposition — is a separate experiment family and should not be folded into the operating-policy sweep unless explicitly promoted into the canonical design.

This separation is a deliberate guard against scope creep. Portfolio-governance controls — such as concentration limits and low-confidence labor caps — should be treated as a targeted follow-up experiment rather than silently added to the main governance sweep. Otherwise the sweep grows in dimensionality without anyone making a conscious decision to expand it, and the results become harder to interpret. The same caution applies to workforce architecture. The fact that the system can represent different team structures does not mean those structures should become experimental variables in the governance study without an explicit decision to include them.

## Named anchor archetypes


### Academic
The following three archetypes are the primary reference configurations. Each is a
specific, complete `GovernanceConfig` that anchors a recognizable governance
philosophy. They are used for initial validation, for interpreting sweep results,
and for producing findings legible to a practitioner audience. See
`study_overview.md` for the practitioner-facing description of each archetype.

1. **Balanced**: Moderate stop thresholds and broadly even attention distribution.
   Intended to exercise both realized-value channels and the canonical stop rules
   without strongly biasing toward either early stopping or extreme patience. The
   recommended starting point for implementation validation and the study's
   reference baseline.
2. **Aggressive stop-loss**: Tight stop thresholds, relatively rapid redeployment
   after negative signals, and less patience for bounded-prize inadequacy.
3. **Patient moonshot**: High attention concentration and patient stop thresholds
   that tolerate sustained strategic uncertainty, preserving candidates that may
   eventually surface major wins.

The Balanced archetype is designed to exercise all four value-creation channels
(completion-lump, residual, major-win discovery, and capability contribution) and
all four canonical stop paths at moderate parameter settings. Sweep results are
interpreted relative to the Balanced configuration's performance on each outcome
dimension.

The Patient moonshot archetype accepts a specific cost: sustained allocation of
labor and attention to initiatives whose latent quality may be low. The patient
stop thresholds preserve right-tail candidates long enough for the belief process
to accumulate sufficient observations for convergence, but the regime cannot
distinguish high-quality from low-quality right-tail initiatives any faster than
the observation model allows. Initiatives that are ultimately low-quality consume
resources until the belief process reaches a stop condition or the horizon ends.

**Attention allocation breadth is a sweep dimension, not an archetype distinction.**
The Concentrated/high-touch and Broad/low-touch postures described in
`study_overview.md` define the ends of a continuous attention-breadth axis. That
axis is swept parametrically via the Latin hypercube sample across `attention_min`
and `attention_max`. The three named archetypes above vary stop behavior and
initiative mix; attention breadth is varied continuously across the sweep.

In the canonical study, `attention_min` is required and non-null. This is
deliberate rather than incidental. The study's attention mechanism is built around
the claim that shallow positive attention below a minimum threshold degrades
signal quality. Canonical sweeps therefore vary the location of that threshold but
do not treat "no threshold exists" as part of the baseline design space. A
no-floor regime, if studied at all, belongs in an explicit sensitivity analysis
rather than in the canonical sweep.

**Observation-boundary note:** the named archetypes are practitioner-facing
descriptions of governance posture, not claims that the policy has access to
hidden initiative labels or latent uncertainty classes. Canonical archetype
implementations must be expressible using the observation interface defined in
`interfaces.md` and the parameters in `GovernanceConfig`. If an archetype
description would require hidden type access, it must be rephrased in terms of
observable quantities such as `quality_belief_t`, `observable_ceiling`,
`execution_belief_t`, attention allocation, and stop thresholds.

**Perfect-information calibration (post-hoc analysis only):** a perfect-information
performance bound is not a canonical governance archetype in this study. The
equivalent diagnostic is available post-hoc: for any run, inspect
`latent_quality_distribution_of_stopped` against the known pool quality distribution.
If the archetype is stopping high latent_quality initiatives at rates inconsistent
with the pool distribution, this signals belief accuracy failure without requiring
any policy to access latent state.

The diagnostic has a natural directional interpretation. If the empirical quality
distribution of a regime's stopped initiatives is significantly lower than the pool
distribution, the regime is making accurate stop decisions — preferentially
terminating low-quality initiatives. If the stopped set includes a
disproportionate share of high-quality initiatives relative to the pool, the
regime is destroying option value through premature termination. The comparison
can be formalized as a two-sample test (e.g., Kolmogorov–Smirnov or Mann–Whitney)
between the stopped-initiative quality distribution and the pool quality
distribution, with the direction of divergence indicating whether the regime
exhibits systematic under-stopping or over-stopping of high-quality work.

### Business
Three governance archetypes serve as the primary reference configurations for the study. Each represents a complete, specific set of governance decision rules that anchors a recognizable governance philosophy. They are used to validate the simulation during development, to provide interpretable landmarks when analyzing sweep results, and to produce findings that practitioners can relate to governance postures they have seen or operated under.

1. **Balanced.** Moderate stop thresholds and broadly distributed executive attention. This archetype is designed to exercise all value-creation channels and all stop rules at moderate settings, without strongly favoring either early termination or extreme patience. It is the recommended starting point for implementation validation and serves as the study's neutral reference baseline — the governance posture against which the other archetypes and sweep results are compared.

2. **Aggressive stop-loss.** Tight stop thresholds, rapid redeployment of teams after negative signals, and less patience for bounded-prize initiatives that are not demonstrating adequate expected value. This archetype represents the governance philosophy of cutting losses quickly to free resources for the next opportunity — a posture common in organizations that prioritize capital efficiency and throughput over persistence with uncertainty.

3. **Patient moonshot.** Concentrated executive attention and patient stop thresholds that tolerate sustained strategic uncertainty. This archetype preserves initiative candidates that might eventually surface transformational outcomes, at the cost of potentially maintaining investment in work that will ultimately not pay off. It represents the governance philosophy of accepting prolonged investment under ambiguity in exchange for access to the largest possible discoveries.

**How executive attention breadth is studied.** The question of whether leadership should go deep on a few initiatives or spread attention broadly across many is not an archetype distinction — it is a continuous dimension that the study sweeps across all governance configurations. The "concentrated, high-touch" and "broad, low-touch" postures define the ends of this axis, and the sweep varies the minimum and maximum per-initiative attention levels to map how outcomes change along it. The three named archetypes vary stop behavior and initiative patience; attention breadth is varied independently across the entire sweep.

In the canonical study, a minimum attention threshold is required for every governance configuration — it is not optional. This is a deliberate design choice, not a default that happens to be set. The study's attention mechanism is built around the substantive claim that shallow positive attention below a minimum engagement level actively degrades the quality of the evidence leadership receives. The canonical sweep therefore varies where that minimum threshold sits, but every configuration in the sweep has a threshold. A "no threshold" configuration — where any positive attention level is treated as valid — belongs in an explicit sensitivity analysis, not in the main sweep. The question the main sweep answers is "where should the engagement floor be?" not "should there be one?"

**These archetypes describe governance posture, not privileged information access.** The archetype descriptions use practitioner-facing language — "prioritize capital efficiency," "tolerate sustained uncertainty" — but the actual governance implementations must operate using only the information that the observation interface provides. No archetype is permitted to use hidden information about an initiative's true quality, its actual duration, or whether it will turn out to be a major win. If describing an archetype in practitioner terms would require the governance logic to access hidden information, the description must be rephrased in terms of what governance can actually observe: its current belief about strategic quality, the visible opportunity ceiling, the execution progress estimate, how much attention the initiative has been receiving, and the configured stop thresholds.

**Assessing governance accuracy after the fact.** A perfect-information governance regime — one that could see the true quality of every initiative and make optimal decisions — is not included as a canonical archetype. The study does not give any governance regime access to hidden truth during a run. However, the equivalent diagnostic is available after the run completes: by examining the true quality distribution of initiatives that a governance regime stopped and comparing it to the quality distribution of the full pool, the study can assess whether a regime is systematically terminating high-quality initiatives. If a regime's stopped initiatives have a quality distribution that is significantly worse than the pool as a whole, that is evidence that the regime is making accurate stop decisions. If the stopped initiatives include a disproportionate number of high-quality opportunities, that is evidence that the regime is destroying value through premature termination. This diagnostic does not require any governance regime to access hidden information — it uses the hidden truth only in post-hoc analysis, where it serves as a benchmark for governance accuracy.

## Deterministic pool with dynamic frontier (canonical scope)


### Academic
The canonical study uses a deterministically seeded opportunity supply. An
initial initiative pool is resolved at run start from the configured initiative
list or `initiative_generator` using `world_seed`.

As the run progresses, the runner may **materialize additional initiatives
between ticks** from family-specific frontier distributions when a family's
unassigned pool is depleted (or below its replenishment threshold). This is an
environment-side mechanism documented in `dynamic_opportunity_frontier.md`. The
engine boundary does not change: the engine consumes only resolved initiative
records.

The frontier distributions for flywheel, quick-win, and enabler families apply a
declining quality model: the effective `alpha` parameter of the family's quality
Beta distribution decreases as a function of the number of resolved initiatives
in that family. This encodes the modeling assumption that higher-quality
opportunities are exploited earlier in the frontier sequence, so that later draws
are stochastically dominated by the initial pool. The right-tail family uses a
distinct prize-preserving refresh mechanism documented in
`dynamic_opportunity_frontier.md`.

Governance selects only from initiatives currently in the `unassigned` lifecycle
state. Governance does not "source" initiatives as an action; it only allocates
labor and decides stop/continue/assignment within the available pool.
Initiative generation is an environmental process, not a governance action.

This convention preserves paired-seed comparability while allowing governance to
create different futures. Regimes that begin from the same `world_seed` share
the same initial pool and frontier RNG streams, but may realize different
additional initiatives over time because depletion and stopping history affect
frontier state. That divergence is intentional and is treated as part of the
modeled environment dynamics, not as a governance-side lever.

Concretely, a regime with patient stop thresholds keeps right-tail initiatives
staffed longer, depleting that family's unassigned pool more slowly and delaying
frontier draws. A regime with tight stop thresholds cycles through the unassigned
pool faster, triggering earlier frontier materialization — and therefore
encountering the frontier's quality degradation sooner. Both effects are
governance-driven consequences that the study is designed to measure. With the
dynamic frontier mechanism, family-level depletion triggers new initiative
materialization rather than hard pool exhaustion, but the quality degradation
associated with frontier draws is itself a phenomenon that should be monitored
in analysis output rather than treated as invisible.

### Business
The canonical study uses a deterministically seeded opportunity supply. An initial pool of initiatives is fully resolved at the start of each run from the configured initiative list or generator, using the world seed. Every governance regime facing the same world seed begins with an identical pool of opportunities.

As the run progresses, the orchestration layer may generate additional initiatives between weeks when a particular type of opportunity has been fully consumed from the available pool — all flywheel opportunities have been assigned or stopped, for example, and no unassigned flywheel initiatives remain. When this happens, new initiatives of that type are drawn from a family-specific frontier distribution that may offer declining average quality over time, reflecting the realistic pattern that the best opportunities in any domain tend to be pursued first. This mechanism is an environment-side feature, documented in the dynamic opportunity frontier design. The simulation engine's boundary does not change — it still consumes only fully resolved initiative records, regardless of whether they were part of the original pool or materialized later from the frontier.

Governance selects only from initiatives that are currently available and unassigned. Governance does not create or source new initiatives — it only allocates teams, decides whether to continue or stop active work, and distributes executive attention within the existing available pool. Initiative generation is an environmental process, not a governance action.

This design preserves the study's controlled comparison while allowing governance to create different futures. Regimes that begin from the same world seed share the same initial pool and the same frontier dynamics, but they may end up with different realized initiative pools over time because their stopping and assignment decisions affect which families become depleted and when new initiatives are drawn from the frontier. A patient regime that keeps right-tail initiatives alive longer will deplete that family's available pool more slowly than an aggressive regime that stops them quickly and triggers earlier frontier draws. That divergence is intentional — it is part of the modeled environment dynamics, not a governance-side lever. The comparison remains valid because the divergence is a consequence of governance decisions, which is exactly what the study is designed to measure.

## Parameter sweep design


### Academic
The governance parameter space is defined by eight continuous and integer
parameters in `GovernanceConfig`. The following table identifies each parameter
with its compact equation symbol and descriptive schema name:

| Compact symbol | Descriptive name | Domain | Role in governance |
|---|---|---|---|
| `θ_stop` | `confidence_decline_threshold` | [0, 1] or None | Minimum strategic quality belief below which governance terminates |
| `θ_tam_ratio` | `tam_threshold_ratio` | [0, 1] | Minimum fraction of `observable_ceiling` that expected prize must exceed |
| `T_tam` | `base_tam_patience_window` | ℤ⁺ | Consecutive below-threshold reviews tolerated at `reference_ceiling` |
| `W_stag` | `stagnation_window_staffed_ticks` | ℤ⁺ | Staffed-tick window over which belief movement is assessed for stagnation |
| `ε_stag` | `stagnation_belief_change_threshold` | [0, 1] | Minimum belief change over `W_stag` to avoid stagnation classification |
| — | `attention_min` | (0, 1] | Per-initiative attention floor; below this, positive attention is infeasible |
| — | `attention_max` | (0, 1] or None | Per-initiative attention ceiling |
| — | `exec_overrun_threshold` | [0, 1] or None | Execution belief level below which governance may flag execution concern |

The governance parameter space is defined by the continuous and integer parameters
in `GovernanceConfig`: `theta_stop`, `theta_tam_ratio`, `T_tam`, `W_stag`,
`epsilon_stag`, `attention_min`, `attention_max`, and `exec_overrun_threshold`.
A Latin hypercube sample across this space, with each sample point treated as a
distinct governance regime, maps the response surface without requiring a dense
grid. The three named archetypes above should be included as fixed points in every
sweep so that sweep results can be anchored to interpretable reference regimes.

In the canonical post-review design, `T_tam` is a base patience parameter rather
than an absolute patience count. Realized bounded-prize patience is determined
jointly by:

- `T_tam`,
- the initiative's `observable_ceiling`,
- and the model-level `reference_ceiling`.

Comparisons involving the base TAM patience parameter therefore depend on the
ceiling distribution of the environment being studied. This is intentional. The
study is measuring prize-relative patience, not a one-size-fits-all bounded-prize
stop window.

Naming note:

Where equations or older prose use compact notation such as `T_tam`,
`theta_stop`, or `epsilon_stag`, implementation and analysis discussions should
prefer the descriptive equivalents:

- `base_tam_patience_window`
- `confidence_decline_threshold`
- `stagnation_belief_change_threshold`

Because omission from `SetExecAttention` means `0.0` attention on that tick rather
than persistence of prior attention, the sweep is over explicit per-tick
attention-allocation policies, not over hidden engine-maintained attention states.
This keeps the meaning of sampled governance regimes operationally crisp: the
policy output for a tick is the complete attention allocation for that tick.

**`exec_attention_budget` treatment in sweeps**: `exec_attention_budget` is an
environmental parameter (residing in `ModelConfig`), not a governance parameter.
It must not appear as an independent axis in the governance parameter sweep. In
the canonical governance sweep, fix `exec_attention_budget` at a single
representative value for all runs and choose it conservatively enough that
attention-feasibility violations are rare. The canonical intent is that realized
attention in the main sweep is determined by governance policy, not silently
overridden by engine-side rejection/clamping.

Recommended procedure:

1. Choose provisional archetypes / sweep bounds for `attention_min` and `attention_max`.
2. Set `exec_attention_budget` using a conservative upper-envelope rule derived from
   those bounds.
3. Run a short pilot sweep and confirm that
   `attention_feasibility_violation_event` frequency is negligible.
4. If violations are common, increase `exec_attention_budget` before running the
   canonical governance sweep.

Sensitivity to `exec_attention_budget` is analyzed separately as an environmental
parameter study: sweep `exec_attention_budget` while holding governance archetype
fixed, in a dedicated experiment distinct from the governance sweep.

**LHS design specification**: minimum sample size is 10 × dimensionality of the
governance parameter space (8 parameters → 80 LHS points minimum; 200 recommended
for robustness in low-density regions).

The `attention_min <= attention_max` constraint must be respected by construction
rather than by rejection after sampling. The canonical sweep should therefore
sample an attention-floor parameter and a nonnegative attention-span parameter,
then derive `attention_max` from that pair, rather than sampling
`attention_min` and `attention_max` independently and discarding infeasible
draws.

If portfolio-risk controls are studied, they should initially be treated as a
separate targeted experiment family rather than folded immediately into the main
Latin hypercube design. Examples include:

- `low_quality_belief_threshold`
- `max_low_quality_belief_labor_share`
- `max_single_initiative_labor_share`

This keeps the canonical baseline sweep interpretable while still allowing a
focused study of portfolio-risk posture.

The three named archetypes (Balanced, Aggressive stop-loss, Patient moonshot) are
**fixed supplemental design points**, not random draws and not constrained LHS
cells. The canonical design is therefore:

- one ordinary LHS sample over the governance parameter space, plus
- three additional fixed archetype points appended to that sample.

This avoids ambiguity about constrained-LHS construction and preserves a simple,
reproducible design description.

For prize-relative bounded-prize patience, `reference_ceiling` should be fixed as
an environmental parameter for a given experiment batch and recorded in the
manifest. The preferred canonical default is a representative central value for
the expected bounded-prize ceiling distribution, with the median as the default
choice when a single summary statistic is needed.

For each governance configuration, run `N_world` distinct `world_seed` values,
generating `N_world` independent initiative pools / stochastic worlds. Under the
current canonical architecture, once `world_seed` and the resolved configuration
are fixed, the run is deterministic. Therefore repeated executions with the same
`world_seed` are replay duplicates and do **not** count as additional independent
observations. Total independent runs per governance-environment cell:
`N_world`. Recording the full environmental configuration alongside governance
parameters in the manifest is required so that outcome differences can be
correctly attributed to governance versus environment in sweep analysis.

Changing `world_seed` samples different worlds from a fixed environment
configuration. Claims about environmental contingency require separate sweeps of
the environmental parameters themselves, not merely additional `world_seed`
replications within one environment setting.

### Business
The governance decision space that the study sweeps across is defined by eight parameters that together capture the essential dimensions of how a governance regime makes decisions:

- **Confidence decline threshold** — how low the organization's strategic conviction about an initiative must fall before governance terminates it.
- **Bounded-prize adequacy ratio** — what fraction of the visible opportunity ceiling the expected prize value must exceed to pass the adequacy test.
- **Base bounded-prize patience window** — how many consecutive below-threshold reviews an initiative earns when its visible opportunity ceiling equals the reference value. Larger visible opportunities earn proportionally more patience.
- **Stagnation window** — how many staffed weeks of informational stasis governance requires before declaring that an initiative has stopped generating useful evidence.
- **Stagnation belief change threshold** — how little the organization's belief must have moved over the stagnation window for the initiative to be considered informationally stagnant.
- **Minimum per-initiative attention level** — the engagement floor below which positive attention is not permitted, reflecting the study's claim about the harmful shallow-attention region.
- **Maximum per-initiative attention level** — the ceiling on how much executive attention any single initiative can receive on a given week.
- **Execution overrun threshold** — how far execution must fall behind plan before governance may flag execution concern, independent of strategic conviction.

Rather than testing every possible combination of these parameters on a dense grid — which would require an impractically large number of runs — the study uses a structured sampling technique that spreads sample points efficiently across the entire eight-dimensional space, ensuring that every region of the governance decision landscape is represented. Each sample point is treated as a distinct governance regime and run through the simulation. The three named archetypes are included as fixed additional points in every sweep, so that sweep results can always be anchored to recognizable reference configurations.

**How bounded-prize patience works in the sweep.** The base patience window is a calibration parameter, not an absolute patience count. The actual patience an initiative earns depends jointly on the base patience window, the initiative's visible opportunity ceiling, and an environment-level reference ceiling value. This means that comparisons involving bounded-prize patience are inherently tied to the opportunity ceiling distribution of the environment being studied. This is intentional — the study is measuring prize-relative patience, where larger visible opportunities earn proportionally more runway, not a one-size-fits-all stop window applied uniformly regardless of opportunity size.

**Executive attention as a complete weekly decision.** Each week's attention allocation is a complete specification — governance states exactly how much attention each initiative receives that week. Not mentioning an initiative means it receives zero attention that week, not that last week's allocation persists. This keeps the meaning of each sampled governance regime operationally precise: the governance output for a week is the entire attention allocation for that week, with no hidden state carrying over.

**The total executive attention budget is an environmental parameter, not a governance parameter.** It represents a fixed organizational constraint — how many hours per week the executive has — not a governance choice. It must not appear as an independent dimension in the governance sweep. In the canonical sweep, the total budget is fixed at a single representative value across all runs, chosen conservatively enough that governance policies rarely run up against the hard limit. The intent is that the realized attention allocation in the main sweep is determined by governance decisions, not silently constrained by the budget ceiling.

The recommended procedure for setting the attention budget is:

1. Choose provisional governance configurations and sweep bounds for the minimum and maximum per-initiative attention levels.
2. Set the total attention budget using a conservative upper-envelope rule derived from those bounds — high enough that the governance regimes being studied can implement their intended attention strategies without running into the ceiling.
3. Run a short pilot sweep and confirm that attention-budget violations are rare.
4. If violations are common, increase the total budget before running the canonical sweep.

Sensitivity to the total attention budget itself — the question of how outcomes change when the executive simply has more or less time available — is analyzed separately as an environmental parameter study: vary the budget while holding the governance regime fixed, in a dedicated experiment distinct from the governance sweep. This keeps the main sweep focused on governance decisions rather than entangling governance effects with environmental constraint effects.

**How many governance configurations to sample.** The minimum sample size is ten times the number of governance parameters being swept — with eight parameters, that means at least 80 sample points. A sample of 200 is recommended for robustness, ensuring adequate coverage in sparse regions of the parameter space where important governance dynamics might otherwise be missed.

**Enforcing parameter constraints during sampling.** The minimum per-initiative attention level must be less than or equal to the maximum. This constraint must be built into the sampling procedure rather than enforced by discarding infeasible draws after the fact. The canonical approach samples the attention floor and a nonnegative attention span, then derives the maximum from the sum of the two. Sampling the minimum and maximum independently and throwing away draws where the minimum exceeds the maximum would waste samples and distort the coverage of the remaining parameter space.

**Portfolio-risk controls as a separate experiment.** If the study examines portfolio-risk governance parameters — such as the low-confidence labor threshold, the maximum low-confidence labor share, or the maximum single-initiative labor share — those should initially be studied as a targeted follow-up experiment rather than folded into the main sweep. This keeps the baseline sweep interpretable at eight dimensions while still allowing a focused investigation of portfolio-risk posture in a dedicated analysis.

**How the named archetypes fit into the sweep design.** The three archetypes (Balanced, Aggressive stop-loss, Patient moonshot) are fixed supplemental design points — they are always included as specific, predetermined configurations appended to the sweep sample. They are not random draws from the parameter space and they do not constrain or distort the sampling of the rest of the sweep. The canonical design is therefore one structured sample across the governance parameter space, plus three additional fixed archetype points. This keeps the design description simple and reproducible.

**Reference ceiling for bounded-prize patience.** The reference ceiling — the normalization value used when computing how much patience a bounded-prize initiative earns — should be fixed as an environmental parameter for a given experiment batch and recorded in the run manifest. The preferred default is a representative central value from the expected distribution of visible opportunity ceilings in the environment, with the median as the default choice when a single summary value is needed.

**How many independent worlds to simulate per governance configuration.** For each governance configuration in the sweep, the study runs a set of distinct world seeds, each generating an independent initiative pool and stochastic environment. Under the current architecture, once the world seed and the resolved configuration are fixed, the run is fully deterministic — repeating the same seed produces an exact replay, not a new independent observation. Only distinct world seeds count as independent samples. The total number of independent runs per governance-environment combination equals the number of distinct world seeds used.

Recording the full environmental configuration alongside the governance parameters in the manifest is required so that outcome differences can be correctly attributed to governance decisions versus environmental conditions in the sweep analysis.

**An important distinction about what different seeds tell you.** Changing the world seed samples a different simulated world drawn from the same environmental configuration. Running many world seeds under one environmental configuration tells you how robust a governance regime is across different realizations of that environment — different initiative pools, different underlying quality draws, different signal sequences. It does not tell you how the regime performs in a structurally different environment. Claims about whether governance conclusions depend on the type of environment — venture-like versus utility-like, for instance — require separate sweeps of the environmental parameters themselves, not merely additional world seeds within one environmental setting.

## Environmental configuration sweep


### Academic
Governance conclusions are environment-contingent. A regime that dominates in a
venture-like environment with many right-tail opportunities may perform poorly in
a utility-like environment where flywheel initiatives dominate. The study therefore
sweeps governance regimes across multiple environmental configurations as a
first-class experimental dimension, not as an afterthought.

Environmental axes to vary include: tail-heaviness of the `q` distribution for
right-tail initiatives, the dependency distribution across the initiative pool,
the mix of initiative types in the shared pool, ramp period `R`, and the
attention-to-signal curve parameters `a_min`, `k_low`, and `k`, plus
`reference_ceiling` when bounded-prize patience calibration itself is being
studied. Each combination
of governance regime and environmental configuration is a distinct experimental
cell.

These axes and their operational consequences are:

- **Right-tail quality distribution parameters.** The `Beta(α, β)` shape
  parameters for the right-tail family's latent quality distribution, which
  jointly determine `P(q ≥ q_major_win_threshold)` — the incidence rate of
  major-win-eligible initiatives. The canonical environments span approximately
  1% to 8% major-win incidence among completed right-tail initiatives.
- **Dependency distribution.** The distribution of `dependency_level` across the
  initiative pool. Higher dependency amplifies effective signal noise via the
  `(1 + α_d × d)` factor in `σ_eff` and reduces learning efficiency via
  `L(d) = 1 - d`, directly affecting belief convergence rates and the accuracy
  of stop decisions.
- **Initiative family mix.** The proportion of the pool allocated to each
  generation tag (quick-win, flywheel, enabler, right-tail). This is one of the
  most consequential environmental parameters because it determines which
  value-creation channels are available to governance and in what proportions.
- **Ramp period `R`.** Longer ramp periods increase the cost of team reassignment
  by extending the interval of reduced learning efficiency after each new
  assignment. This shifts the marginal cost of stop-and-reassign decisions and
  may alter the optimal tradeoff between patience and redeployment.
- **Attention-to-signal curve parameters** (`a_min`, `k_low`, `k`, `g_min`,
  `g_max`). These structural assumptions govern the shape of the `g(a)` noise
  modifier — the minimum engagement threshold, the penalty slope in the
  shallow-attention region, and the curvature of diminishing returns above
  threshold. Sensitivity analysis across these parameters tests the robustness of
  governance findings to the weakest calibration tier (Tier 3).
- **`reference_ceiling`** when the study is specifically examining how
  bounded-prize patience calibration interacts with the opportunity ceiling
  distribution.

All governance findings are conditioned on the environmental configuration.
A claim that one governance regime dominates another is meaningful only when
accompanied by the environmental conditions under which the dominance holds.
Findings that are robust across all canonical environment families carry
stronger inferential weight than those that hold in a single configuration.

#### Pool sizing requirement

Canonical sweeps should size the initiative pool so that exhaustion is unlikely
to drive regime differences. A practical rule is to size the pool at least 50%
above the initiative-consumption level observed in pilot runs of the most
aggressive archetype under the same horizon and staffing configuration.

Pool exhaustion, if it occurs, must be logged and flagged for review rather than
silently treated as an ordinary run outcome. The goal of the canonical sweep is
to compare governance over a shared opportunity pool, not to let accidental pool
depletion dominate the result. The runner must record the full environmental configuration in the manifest
alongside the governance parameters so that results can be correctly attributed.

Under the dynamic frontier mechanism, family-level pool depletion triggers
runner-side materialization of new initiatives from the frontier distribution
rather than hard exhaustion. However, the quality degradation applied to frontier
draws (declining `effective_alpha` per resolved initiative) is itself an
environment-side phenomenon with potential effects on regime comparisons. Analysis
output should track frontier draw counts and effective quality parameters per
family so that the contribution of frontier degradation to outcome differences
can be assessed.

A finding that cannot be traced to a specific, fully recorded environmental
configuration is incomplete and should not be reported as a study result.

### Business
Governance conclusions are environment-contingent. A governance regime that dominates in an environment rich with transformational opportunities may perform poorly in an environment where most available work is incremental and compounding. A regime optimized for an organization with low-dependency initiatives may make systematically poor decisions when dependencies are high and signals are noisy. The study therefore sweeps governance regimes across multiple environmental configurations as a first-class experimental dimension, not as an afterthought.

The environmental axes that the study varies include:

- **The frequency of transformational opportunities** — how likely it is that an exploratory initiative turns out to be a genuine major win. This ranges from environments where major wins are extremely scarce (roughly one in a hundred completed exploratory initiatives) to environments where they are relatively abundant (roughly one in twelve).
- **The dependency structure of the initiative pool** — how much friction and cross-team dependency individual initiatives carry, which directly affects how noisy the strategic evidence they produce is and how slowly the organization learns about them.
- **The mix of initiative types** — the proportion of the portfolio allocated to quick wins, flywheels, enablers, and right-tail bets. This is one of the most consequential environmental parameters, because it determines what kinds of value-creation mechanisms are available to governance.
- **The ramp-up period** — how long a newly assigned team takes to reach full learning efficiency. Longer ramp periods increase the cost of reassignment and may shift the optimal balance between patience and redeployment.
- **The shape of the attention-to-signal relationship** — the minimum engagement threshold, the penalty for shallow attention, and the curvature of diminishing returns above the threshold. These are the structural assumptions about how executive engagement translates into organizational learning.
- **The reference ceiling for bounded-prize patience** — when the study is specifically examining how patience calibration should vary with opportunity size.

Each combination of governance regime and environmental configuration is a distinct experimental cell. The study's findings about governance are always conditioned on the environment — a finding that says "patient governance outperforms aggressive stop-loss" is meaningful only when accompanied by the environmental conditions under which that finding holds.

**Sizing the initiative pool to avoid artificial depletion.** The initiative pool for each environment must be large enough that running out of available initiatives does not become a primary driver of outcome differences between governance regimes. A practical rule is to size the pool at least fifty percent above the initiative-consumption level observed in pilot runs of the most aggressive archetype — the regime that cycles through opportunities fastest — under the same time horizon and staffing configuration.

If pool exhaustion does occur during a canonical sweep run, it must be logged and flagged for review rather than silently treated as an ordinary outcome. The purpose of the sweep is to compare governance decisions over a shared opportunity landscape, not to let an accidental shortage of available opportunities dominate the result. With the dynamic frontier mechanism, pool depletion triggers new initiative materialization from the frontier rather than hard exhaustion, but the quality degradation associated with frontier draws is itself a phenomenon that should be monitored and understood rather than ignored.

The run manifest must record the full environmental configuration alongside the governance parameters so that results can be correctly attributed. A finding that cannot be traced to a specific environmental configuration is incomplete.

## Reproducibility and ensemble sizing


### Academic
**Minimum ensemble size N_world per governance-environment cell**: the "100+ runs"
heuristic is insufficient for distinguishing regimes that differ by small major-win
probability margins. Use the following power analysis instead:

```
N_world ≥ (z_{α/2} + z_β)² × p(1−p) / δ²

where:
    p    = expected major-win probability under the archetype under test
    δ    = minimum detectable difference between archetypes (recommend δ = 0.02)
    α    = 0.05  (z_{α/2} = 1.96)
    β    = 0.20  (z_β = 0.84, targeting 80% power)

Reference values:
    p = 0.05  →  N_world ≥ 865
    p = 0.10  →  N_world ≥ 553
    p = 0.20  →  N_world ≥ 308
```

Use the most conservative `N_world` across the archetypes under study. The "100+ runs"
heuristic may be used only for quick implementation validation runs where major-win
probability differences are not the primary outcome of interest. Always report
confidence intervals.

- For regime comparisons, use paired runs sharing the same **set of distinct
  `world_seed` values** across all regimes so that outcome differences reflect
  governance differences rather than environmental differences.
- Record `world_seed`, policy version, and the full `GovernanceConfig` parameter
  values in the manifest for every run.
- The named anchor archetypes should be included in every sweep to provide
  continuity across experimental sessions.

**Important reproducibility note:** under the current canonical architecture,
repeating a run with the same `world_seed` and the same resolved configuration is
an exact replay, not a new sample. Such reruns are useful for debugging and
determinism checks, but they must not be counted toward statistical power.
Incorrectly counting replay duplicates as independent observations would inflate
apparent confidence intervals and could produce false claims of statistically
significant governance differences. Only distinct `world_seed` values generate
independent samples; the effective sample size for any governance-environment cell
is the number of distinct seeds used, not the number of times the simulation was
executed.

### Business
**How many simulated worlds are needed to detect meaningful governance differences.** The commonly used heuristic of "a hundred or more runs" is insufficient when the outcome of interest is major-win discovery. Major wins are rare events — occurring in roughly one to eight percent of completed exploratory initiatives depending on the environment — and detecting a two-percentage-point difference in major-win probability between governance regimes requires substantially more statistical power than a hundred runs provides.

The required number of independent worlds per governance-environment combination depends on how rare the outcome is and how small a difference the study needs to detect. For the canonical study, where the minimum detectable difference is set at two percentage points with standard statistical confidence:

- When the expected major-win rate is around five percent, approximately 865 independent worlds are needed.
- When the expected rate is around ten percent, approximately 553 worlds are needed.
- When the expected rate is around twenty percent, approximately 308 worlds are needed.

The study should use the most conservative (largest) of these numbers across the archetypes and environments under study. The "hundred runs" heuristic is acceptable only for quick implementation validation where major-win probability differences are not the primary outcome of interest. All findings must report confidence intervals.

**Paired comparisons across governance regimes.** To ensure that outcome differences reflect governance decisions rather than differences in the simulated world, all governance regimes in a comparison must be run against the same set of distinct world seeds. This is the simulation equivalent of a paired experiment — every regime faces the same sequence of initiative pools, the same underlying quality distributions, and the same signal noise, so any difference in outcomes is attributable to how governance responded to what it observed.

**Manifest requirements.** Every run must record the world seed, the governance policy version, and the complete set of governance parameter values in its manifest. The named anchor archetypes should be included in every sweep to provide continuity and comparability across experimental sessions.

**Exact replays versus independent samples.** Under the current architecture, repeating a run with the same world seed and the same resolved configuration produces an exact replay — the same initiative pool, the same signals, the same beliefs, the same outcomes, down to the last decimal. Such replays are valuable for verifying that the simulation is deterministic and for debugging, but they are not new observations and must never be counted toward statistical power. Only distinct world seeds produce independent samples. This distinction matters because incorrectly counting replays as independent observations would inflate apparent statistical confidence and could lead to false claims about governance differences.

## Implementation sequencing


### Academic
Build and validate against a single regime before introducing parallelism. The
recommended sequence is: single regime (Balanced archetype) producing correct
per-tick traces and matching the output schema; two regimes with valid pairwise
comparison against shared world seeds; all three named archetypes as a complete
small study; parameter sweep harness added on top of that validated foundation.
Each milestone produces usable research output. The parallel execution layer should
be the last component added, after single-threaded correctness is confirmed.

Acceptance criteria for each stage:

1. **Single regime.** The Balanced archetype produces correct per-tick state
   traces across all state variables and matches the canonical output schema.
   This confirms end-to-end correctness of signal generation, belief updates,
   governance decision application, value realization, and capability
   accumulation.

2. **Pairwise comparison.** Two governance regimes run against a shared set of
   `world_seed` values. Verification confirms that both regimes receive identical
   initiative pools and identical per-initiative signal draws (CRN preservation),
   that outcome differences are attributable to governance decisions, and that
   the comparison output artifacts are structurally correct.

3. **Three-archetype study.** All three named archetypes run as a complete small
   experiment. This validates that the full range of governance parameterizations
   — moderate, tight, and patient — produces plausible and distinguishable outcome
   distributions across the four evaluation dimensions. The three-archetype
   comparison is itself a meaningful research output, not merely a validation
   stepping stone.

4. **Parameter sweep harness.** The LHS sampling infrastructure generates
   governance configurations across the eight-dimensional parameter space, runs
   each against the required `N_world` seeds, and produces sweep-level analysis
   artifacts (response surface estimates, main effects, interaction candidates).

5. **Parallel execution.** Distribution of batch runs across worker processes to
   reduce wall-clock time. This is the final component. Diagnosing whether a
   failure originates in the core simulation logic or in the parallelization and
   distribution machinery is substantially harder when both are under development
   simultaneously; the layered validation strategy ensures that the core logic
   has been independently verified before the orchestration layer is introduced.

### Business
Build and validate the experimental infrastructure incrementally, confirming correctness at each stage before adding the next layer of complexity.

The recommended sequence is:

1. **Single regime.** Run the Balanced archetype through the simulation and verify that it produces correct per-week traces matching the expected output structure. This confirms that the core simulation logic — signal generation, belief updates, governance decisions, value realization — is working correctly end to end.

2. **Pairwise comparison.** Run two governance regimes against the same set of world seeds and verify that the paired comparison infrastructure works: both regimes face the same initiative pools and signal sequences, outcome differences are attributable to governance decisions, and the comparison artifacts are correct.

3. **All three named archetypes.** Run all three reference configurations as a complete small study. This validates that the full range of governance postures — moderate, aggressive, and patient — produces plausible and distinguishable results, and that the comparison framework handles three-way comparisons correctly.

4. **Parameter sweep harness.** Add the structured sampling infrastructure that generates governance configurations across the eight-dimensional parameter space, runs each configuration against the required number of world seeds, and produces sweep-level analysis artifacts. This builds on the validated three-archetype foundation.

5. **Parallel execution.** Add the ability to distribute runs across multiple worker processes to reduce wall-clock time. This is the last component added, after single-threaded correctness has been fully confirmed.

Each milestone in this sequence produces usable research output — the three-archetype comparison is itself a meaningful study, not just a stepping stone. The parallel execution layer should not be started until the sequential sweep harness produces correct results, because diagnosing whether a failure originates in the core simulation logic or in the parallelization and distribution machinery is much harder when both are being developed simultaneously.
