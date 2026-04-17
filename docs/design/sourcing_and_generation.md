# Initiative sourcing and generation

## Key rule

### Academic
Initiative types/labels (e.g., flywheel, right-tail, enabler) are **only** used:
- to define priors/parameter presets for the pool generator, and
- to tag initiatives for reporting and analysis.

The **engine receives resolved initiative records** that contain the concrete immutable attributes. The generator and label system run *before* the engine.

More precisely, each label maps to a named parameter profile — a collection of distribution families, parameter ranges, and structural flags — that the generator consumes when sampling initiative attributes. The `flywheel` label instructs the generator to draw `latent_quality` (q) from a high-mean, low-variance Beta distribution, set low `base_signal_st_dev` (σ_base), and enable a completion-gated residual value channel with slow decay. The `right_tail` label instructs the generator to draw from a Beta distribution with non-negligible upper-tail density, set high σ_base, assign an `observable_ceiling` from a prize distribution, and compute the hidden `is_major_win` flag via a deterministic threshold rule on the realized quality draw. The full canonical mapping for all four families is given in the attribute ranges table below.

The engine's state-transition kernel and observation model operate on the resolved attribute vector — `latent_quality`, `base_signal_st_dev`, `dependency_level`, value channel configuration, `true_duration_ticks`, etc. — identically for all initiatives regardless of `generation_tag`. This is formalized as canonical invariant #1 (type-independence) in `canonical_core.md`. The `generation_tag` field is carried through on each `ResolvedInitiativeConfig` as metadata available for post-hoc disaggregation in reporting and, at the policy's discretion, for portfolio composition logic.

Consequently, modifying the type taxonomy — adding, removing, or renaming a label, or changing the parameter profile a label maps to — requires changes only in the generator and the reporting/analysis layer. No modification to the engine is required.

### Business
Initiative type labels — flywheel, right-tail, enabler, quick-win — serve exactly two purposes in the simulation:

- They define the default characteristic profiles used when generating the initial portfolio of initiatives. A "flywheel" label tells the generator to produce an initiative with the structural characteristics typical of compounding, persistent-return work: high underlying quality, moderate uncertainty, long duration, and an ongoing value stream activated at completion. A "right-tail" label tells the generator to produce an initiative with high uncertainty, a visible opportunity ceiling, and a chance — determined at creation and hidden from governance — of being a genuine major win. The labels are instructions to the portfolio generator, not rules for the simulation engine.

- They tag each initiative for post-run reporting and analysis. When the study reports major-win discovery rates or residual-stream accumulation by initiative type, the tag is what makes that disaggregation possible.

The simulation engine itself never sees or uses these labels to apply different rules. It receives fully resolved initiative records — concrete, immutable descriptions of each initiative's characteristics — and operates on those characteristics identically regardless of how the initiative was labeled at creation. The labeling and generation system runs entirely before the engine begins. This means that changing the type taxonomy — adding a new initiative category, renaming an existing one, or adjusting the characteristic profiles that labels map to — affects only the portfolio generator and the reporting layer. It never requires changes to the simulation engine itself.

## Canonical scope: deterministic pool with dynamic frontier

### Academic
In the canonical study, the initiative pool is deterministically seeded
from `world_seed`. An initial pool is resolved at run start from the
`initiative_generator`. As the run progresses, the runner materializes
additional initiatives from family-specific frontier distributions when
a family's unassigned pool falls to or below its
`replenishment_threshold` (default 3); the runner fills the pool back
up to `threshold + 1`. This runner-side inter-tick frontier
materialization is documented in `dynamic_opportunity_frontier.md`.

For families using a declining frontier (flywheel, quick-win, enabler),
quality degrades as more initiatives are resolved. Selected observable
attributes may also thin for later frontier initiatives: the
`planned_duration` range grows for flywheel and quick-win
(`duration_thinning_rate` and `duration_thinning_ceiling`), and the
`capability_contribution_scale` upper bound shrinks for enabler
(`capability_scale_thinning_rate` and `capability_scale_thinning_floor`).
These give governance visible signals that the remaining frontier is
less attractive, alongside the latent quality decline. Thinning is
opt-in per family: defaults of `None` leave observable attributes
untouched. Right-tail is exempt from observable thinning; stopped
right-tail initiatives instead make their observable ceiling available
for re-attempt with fresh latent quality (prize-preserving refresh).
The engine never generates initiatives; the runner owns all
materialization.

The realized pool for a given seed and governance trajectory is fully
reproducible. Different governance trajectories may produce different
realized pools because pool depletion and initiative stopping affect
frontier state. Paired-seed comparability is preserved: for a given seed,
the frontier's stochastic draws are deterministic given the governance-
driven depletion history.

The declining frontier encodes an ordering assumption: the initial pool contains the highest-value opportunities within each family (by construction), so subsequent frontier draws sample from a quality distribution whose effective α parameter has been reduced as a function of the family's cumulative resolved count (`n_resolved`). This makes pool depletion a modeled phenomenon — declining expected quality of newly available opportunities — rather than an implementation artifact of exhausting a pre-enumerated list.

The prize-preserving refresh for right-tail is structurally distinct from the declining frontier. When a right-tail initiative is stopped without completing, its `observable_ceiling` — a fixed environmental attribute representing the persistent prize — returns to the available prize descriptor set. A subsequent attempt against that prize draws fresh `latent_quality` from the right-tail quality distribution and recomputes `is_major_win` via the deterministic threshold rule. The environmental feature (the prize) is persistent; the latent realization (the approach quality) is resampled. A prize is consumed only when an attempt completes, regardless of whether a major win was surfaced.

Cross-regime pool divergence is environment-side state evolution, not a governance action. Frontier materialization is runner-owned, occurs between ticks, and is outside the policy's action space. All regimes sharing a `world_seed` begin from identical initial pools and face identical frontier distributions; their realized pools diverge only through the downstream effects of governance-driven depletion histories on frontier state.

### Business
The canonical study uses a deterministically seeded opportunity supply. An initial pool of initiatives is fully resolved at the start of each run from the configured generator using the world seed. Every governance regime facing the same world seed begins with an identical pool of opportunities.

As the run progresses, the orchestration layer may generate additional initiatives between weeks when a particular type of opportunity has been fully consumed from the available pool. When all flywheel opportunities have been assigned or stopped, for example, and no unassigned flywheel initiatives remain, new flywheel initiatives are drawn from a family-specific frontier distribution. This dynamic frontier mechanism is documented in the dynamic opportunity frontier design specification.

The frontier behaviors differ by initiative type, reflecting how opportunity landscapes work in practice:

- For flywheel, quick-win, and enabler families, the frontier applies a **declining quality model**: as the organization resolves more opportunities of a given type — whether by completing them or stopping them — the remaining frontier offers lower average quality. This encodes the realistic pattern that the most promising opportunities in any domain tend to be identified and pursued first. Later opportunities drawn from the same domain are, on average, less attractive than the initial set.

- For right-tail initiatives, a distinct **prize-preserving refresh** mechanism applies. When an exploratory initiative is stopped without completing, the underlying market opportunity — the visible prize — remains available. A new attempt can be made against the same opportunity with a fresh approach and fresh underlying quality. The prize persists; only the approach is new. This models the reality that a failed attempt at a large market opportunity does not make the opportunity disappear — it remains available for a different team or strategy to pursue.

The simulation engine never generates initiatives. All materialization — whether from the initial pool or from the frontier — is owned by the orchestration layer. The engine consumes only fully resolved initiative records, regardless of their origin.

The realized pool for a given world seed and governance trajectory is fully reproducible. Different governance regimes may produce different realized pools over time because their stopping and assignment decisions affect which families become depleted and when frontier draws are triggered. That divergence is intentional and is treated as part of the modeled environment dynamics, not as a governance action. Paired-seed comparability is preserved: for a given seed, the frontier's draws are deterministic given the governance-driven depletion history.

## Generator contract

### Academic
- The runner accepts either:
  - `initiatives`: explicit list of resolved initiatives, or
  - `initiative_generator`: a parameter block with mixture priors and counts.
- If `initiative_generator` is supplied, the runner deterministically resolves the explicit initiatives list with `world_seed`.
- The runner stores both the generator parameters and the resolved list in the manifest for provenance.

**Generator invariant — residual-on-completion requires duration**: any initiative
whose residual channel activates on completion (`residual.activation_state == "completed"`)
must have `true_duration_ticks` set at generation time. Generators must enforce this as
a construction invariant, not rely on the runner to catch it at validation. Flywheel
generators are the primary affected type.

**Generator invariant — capability-on-completion requires duration**: any initiative
with `capability_contribution_scale > 0` must also have `true_duration_ticks` set at
generation time. In the canonical model, enabler effects are realized only at the
completion transition, so generators must not emit capability-bearing initiatives
without a completion path.

A "resolved" initiative has its complete attribute vector determined: `latent_quality` drawn from the family-specific quality distribution, `true_duration_ticks` drawn from the family duration range, `dependency_level`, `base_signal_st_dev`, all value channel parameters (completion lump value, residual rate, residual decay, activation state), `observable_ceiling` where applicable, `capability_contribution_scale`, `required_team_size`, `is_major_win` flag (for right-tail), and initial belief states. The generator is the sole site at which stochastic draws from the type-specific prior distributions occur; the engine consumes only the deterministic resolved attribute vector.

Both construction invariants above are enforced at generation time as structural preconditions, not deferred to runner-level validation. A completion-gated payoff mechanism (residual activation or capability contribution) on an initiative without a completion condition (`true_duration_ticks` not set) is a structurally malformed configuration — the initiative can never reach the lifecycle transition that would trigger its intended value realization. This is not a recoverable input error; it is a definition that violates the mechanism's precondition. Enforcing at the generator ensures all downstream code can rely on the invariant without defensive checking.

Storing both the generator parameters and the resolved list provides two-level provenance: any reported finding is traceable to both the concrete initiative attributes that governance operated on and the generative specification (distribution families, parameter ranges, composition constraints) from which those attributes were drawn.

### Business
The simulation accepts initiative portfolios in one of two forms:

- An **explicit list of fully resolved initiatives**, where every initiative's characteristics — quality distribution draws, duration, dependency level, value channels, team requirements — have already been determined.
- An **initiative generator specification** — a parameter block defining the mixture of initiative types, the count of each type, and the characteristic distributions from which each type's attributes are drawn.

If a generator specification is supplied, the orchestration layer resolves it into a concrete list of initiatives deterministically using the world seed. The same seed and generator specification always produce the same initiative pool. Both the generator parameters and the resolved list are recorded in the run manifest for complete provenance — so that any future analysis can trace exactly how the portfolio was constructed and verify that two governance regimes faced the same starting pool.

Two construction invariants must be enforced at generation time, not deferred to later validation:

**Ongoing value streams require a completion path.** Any initiative designed to activate an ongoing value stream upon completion — primarily flywheels and quick wins with residual tails — must have its true completion timeline set at the moment it is generated. An ongoing value stream that activates at completion is meaningless if the initiative has no defined completion condition. The generator must enforce this as a structural guarantee, not rely on downstream validation to catch it.

**Capability contributions require a completion path.** Any initiative that contributes to organizational learning capability upon completion — primarily enablers — must also have its true completion timeline set at generation time. In the canonical model, capability improvements are realized only at the completion transition. An enabler without a completion condition would not be a different kind of enabler — it would be a malformed initiative definition that can never deliver its intended value.

## Labeled priors (for generation)

### Academic
- Labels map to distributions over immutable attributes:
  - Example: `flywheel` → Beta(α_fw, β_fw) for latent_quality (q), low base_signal_st_dev (σ_base), low dependency_level (d).
  - Example: `right-tail` → Beta(α_rt, β_rt) for latent_quality (q), high base_signal_st_dev (σ_base), possibly lump value mechanism.
- Changing or adding labels modifies only the generator/presets; it must not change the engine.

<!-- inconsistency: The existing text states right-tail has "possibly lump value mechanism," but the canonical attribute table in this document specifies completion_lump.enabled = false and residual.enabled = false for right-tail. The Business source states "Right-tail initiatives produce no ongoing value streams and no one-time completion payoff in the canonical model." The canonical right-tail value channel is the major-win discovery event only. -->

Each label defines a complete parameter profile over the full attribute vector of a `ResolvedInitiativeConfig`. The profile specifies: the quality distribution (family and parameters), the `base_signal_st_dev` range, the `dependency_level` range, which value channels are enabled and their parameter ranges (completion lump, residual, major-win discovery), whether `observable_ceiling` is drawn and from what distribution, the `capability_contribution_scale` distribution (positive for enablers, zero otherwise), the `true_duration_ticks` range, `required_team_size`, and the `is_major_win` generation rule (right-tail only).

These label-to-profile mappings constitute the **complete interface** between the type taxonomy and the simulation. No other mechanism connects initiative labels to engine behavior. The engine's transition kernel, observation model, belief update equations, and value realization logic are functions of the resolved attribute vector alone and are invariant to the label.

The canonical profiles for all four families are fully specified in the attribute ranges table below.

<!-- specification-gap: The specific Beta(α, β) parameter values for flywheel, enabler, and quick-win quality distributions are described qualitatively ("high mean, low variance," "moderate mean," etc.) but not specified as numerical (α, β) pairs. The right-tail family has per-environment Beta parameters given in the calibration section (e.g., Beta(0.8, 2.0) for balanced_incumbent), but the remaining families lack equivalent numerical specification. This is consistent with the Tier 2 (qualitatively anchored) calibration designation, but a reader expecting a complete generative specification would need numerical Beta parameters or at least defensible ranges to reproduce the canonical initial pool. -->

### Business
Each initiative type label maps to a set of probability distributions over the immutable characteristics that define an initiative. These distributions serve as the default profiles that the generator uses when creating a portfolio.

For example, the "flywheel" label maps to a quality distribution centered on high values with low variance — reflecting the idea that flywheel initiatives extend proven mechanisms whose strategic quality is relatively well-understood — combined with low baseline signal noise and low-to-moderate dependency on external factors. The "right-tail" label maps to a quality distribution where most draws are mediocre but a small fraction are very high — reflecting the hit-or-miss nature of exploratory work — combined with high signal noise and a visible opportunity ceiling.

These mappings are the complete connection between labels and the simulation. Changing or adding a label modifies only the generator's preset profiles. It does not and must not change anything about how the simulation engine operates. The engine has no knowledge of labels during a run — it works entirely with the resolved characteristics that the generator produced.

## Composition constraints

### Academic
- The generator may accept portfolio composition constraints (e.g., `% right-tail = 20%`). The generator should honor those constraints probabilistically and record the resolved mix.

Portfolio composition — the family-level distribution of initiative types in the initial pool — is an environmental parameter. It is fixed before the run begins and held constant throughout. The policy cannot alter the portfolio's type composition during a run; it can only make continue/stop, attention allocation, and team assignment decisions within the realized pool.

This classification is required for causal identification. If portfolio composition could vary across governance regimes within an experimental comparison, observed outcome differences would confound governance effects with portfolio-structure effects. Composition constraints enable the study to evaluate governance performance across structurally different initial portfolios as distinct experimental treatments — for example, comparing regime behavior on a portfolio with high right-tail share versus one dominated by low-variance families — while ensuring that within each treatment, all governance regimes share the same realized composition for a given `world_seed`.

### Business
The generator may accept portfolio composition constraints — for example, a requirement that twenty percent of the initial pool should be right-tail initiatives, or that at least a certain number of enablers should be included. The generator honors these constraints when drawing from the type-specific distributions and records the resolved portfolio mix in the run manifest.

This allows the study to test governance regimes against portfolios with different structural compositions — a portfolio heavy on exploratory work versus one dominated by incremental compounding initiatives — while maintaining the discipline that the composition is an environmental parameter chosen before the run begins, not a governance decision made during the run.

## Provenance

### Academic
- All draws are seeded by `world_seed`. The runner records the resolved `initiatives` list and the generator parameters in the run manifest.

This dual recording provides complete provenance: any reported finding is traceable to both the concrete initiative attributes that governance operated on (the resolved pool) and the generative specification from which those attributes were drawn (distribution families, parameter ranges, composition constraints, family-specific frontier specifications). This is a prerequisite for reproducibility, for verifying that paired-seed comparisons across governance regimes began from identical initial conditions, and for auditing whether the realized pool conforms to the generator's declared distributional assumptions.

### Business
All random draws used to generate the initiative pool are seeded by the world seed, ensuring that the same seed always produces the same portfolio. The orchestration layer records both the resolved initiative list — the concrete portfolio that the simulation operates on — and the generator parameters that produced it in the run manifest. This provides complete provenance: any finding can be traced back to both the specific initiatives that governance operated on and the generation rules that created them.

## Canonical initiative type attribute ranges


### Academic
The table below gives the reference parameter ranges for each initiative type as
configured by the canonical generator. These ranges inform the default priors the
generator uses when resolving `initiative_generator` into a concrete initiative
list. All numeric ranges are recommendations; the generator may accept explicit
overrides. The `generation_tag` field on each resolved initiative records which
row below was used and is available for post-run disaggregation in reporting.

Under the product launch model, `streaming.enabled` does not exist in the schema.
All four initiative types realize value only at a lifecycle transition.

| Attribute | Flywheel | Right-tail | Enabler | Quick-win |
|-----------|----------|------------|---------|-----------|
| `quality_distribution` | Beta, high mean, low variance — extends proven mechanisms | Beta with right tail; most draws mediocre, small fraction very high | Beta, moderate mean | Beta, moderate-to-high mean, low variance |
| `sigma_base_range` | Low (0.05–0.15) | High (0.20–0.40) | Low-to-moderate (0.05–0.20) | Low (0.05–0.15) |
| `d_range` | Low-to-moderate (0.1–0.4) | Moderate-to-high (0.2–0.6) | Low (0.0–0.2) | Low (0.0–0.2) |
| `major_win_event.enabled` | false | true | false | false |
| `is_major_win` | — | true if latent_quality (q) >= q_major_win_threshold (default 0.7); assigned at generation, immutable | — | — |
| `observable_ceiling` | not set | set (draws from TAM distribution) | not set | not set |
| `completion_lump.enabled` | false | false | false | true |
| `completion_lump_value` | — | — | — | Moderate (1.0–5.0); primary quick-win value channel |
| `residual.enabled` | true | false | false | true (small secondary tail) |
| `residual.activation_state` | `completed` | — | — | `completed` |
| `residual_rate` | Moderate-to-high; persistent flywheel momentum | — | — | Low (0.01–0.10); bounded secondary tail, not the dominant value channel |
| `residual_decay` | Low but positive exponential decay | — | — | High (0.10–0.30) exponential decay; residual tail approaches zero quickly |
| `capability_contribution_scale` | 0.0 | 0.0 | > 0 (draws from positive distribution) | 0.0 |
| `typical_true_duration_ticks` | Long (25–45) | Long (40–220, varies by family); major win surfaced at completion | Moderate (10–30) | Short (3–10) |
| `initial_c_exec_0` | 1.0 (default) | 1.0 (default) | 1.0 (default) | 1.0 (default) |
| `screening_signal_st_dev` | 0.15 (moderate) | 0.30 (high) | 0.20 (moderate) | 0.10 (low) |

Table columns `sigma_base_range` and `d_range` correspond to base_signal_st_dev range and dependency_level range; see `docs/study/naming_conventions.md`.

**Notes on screening signal**: the screening signal models the organization's
intake evaluation process. At generation time, each initiative receives a noisy
ex ante signal about its latent quality: `clamp(q + Normal(0, sigma_screen), 0, 1)`.
This sets the initiative's `initial_quality_belief`, giving governance a rough
ranking before any team is assigned. Quick wins (sigma_screen=0.10) are easy to
evaluate upfront; right-tail moonshots (sigma_screen=0.30) are inherently hard to
screen. See initiative_model.md for the full specification.

<!-- inconsistency: The is_major_win row lists q_major_win_threshold with "(default 0.7)," but the right-tail specifics section below gives the canonical unified value of 0.80. The "(default 0.7)" is stale from an earlier iteration. -->

**Notes on initial execution belief**: all four families initialize `c_exec_0 = 1.0`, the on-plan prior. This is a neutral starting point: governance must accumulate execution-progress evidence (negative `z_t` draws) to detect schedule overruns. No family starts with a built-in expectation of delay or early completion. The consequence is that the execution-overrun stop path (`execution_belief_t < exec_overrun_threshold`) is unreachable at tick 0 and can only fire after sufficient negative execution signals have accumulated to drive `c_exec_t` below the threshold.

**Notes on quick-win value mechanism**: quick wins are completion-lump-dominant.
Their primary value is realized as a one-time completion lump at the completion
transition. They may also produce a small residual tail (low rate, high decay),
but this is a secondary channel, not the dominant value mechanism. The structural
distinction from flywheels is that flywheels are residual-dominant with slow
decay (persistent compounding), while quick wins are lump-dominant with at most a
bounded residual tail that approaches zero quickly. The short `true_duration_ticks`
means completion and value realization occur early.

**Notes on enabler value mechanism**: enablers realize portfolio value through
`capability_contribution_scale` at completion, not through a direct value channel.
Their realized capability gain is `latent_quality_i × capability_contribution_scale_i`, capped
at max_portfolio_capability (C_max). Enablers have no residual channel in the
canonical study; their effect on portfolio productivity is captured entirely through
portfolio_capability_t (C_t) dynamics. In the canonical study, that capability
stock also decays exponentially over time at the model level, so enabler effects
are durable but not permanent.

Because that effect is completion-gated, canonical enablers must always have
`true_duration_ticks` set. An enabler without a completion condition would not be
an alternate kind of enabler; it would be a malformed initiative definition.

**Notes on right-tail value mechanism**: right-tail initiatives have no economic value channels in the canonical study (`completion_lump.enabled = false`, `residual.enabled = false`). Their contribution to the study is measured entirely through the major-win discovery outcome family — surfaced major-win count, time to first discovery, and labor expended per discovery — not through realized economic value within the horizon. This is a deliberate design choice: the study measures governance's capacity to preserve and surface rare high-value opportunities, not the full downstream economic consequences of capturing them. The right-tail family is therefore the only family whose study-relevant output is exclusively non-economic.

**Generator invariant reminder**: any initiative with `residual.activation_state ==
"completed"` must have `true_duration_ticks` set at generation time. This applies
to all flywheel and quick-win initiatives. See the generator invariant note above
and the validation rule in `interfaces.md`.

<!-- specification-gap: Flywheel residual_rate is described as "moderate-to-high" and residual_decay as "low but positive" without numerical ranges. Quick-win residual parameters are specified numerically (rate 0.01–0.10, decay 0.10–0.30), but flywheel residual parameters are not. A reader implementing the canonical generator would need numerical bounds for flywheel residual_rate and residual_decay to produce a reproducible initial pool. -->

#### Right-tail specifics (canonical)

Right-tail initiatives do **not** have a separate pre-completion viability state in
the canonical model. Instead, the generator should set:

- `major_win_event.enabled = true`
- `major_win_event.is_major_win` to an immutable hidden boolean at generation time

Canonical generation rule for `is_major_win`: the flag is assigned at generation
time as a deterministic function of latent_quality using a threshold rule:

`is_major_win = (q >= q_major_win_threshold)`

where `q_major_win_threshold` is a generator-level parameter recorded in the run
manifest. The canonical value is `q_major_win_threshold = 0.80` for all
three families (unified threshold). This
preserves the interpretive meaning of governance's learning process: regimes
that learn to identify high latent_quality right-tail initiatives and persist
through uncertainty are the same regimes that will surface major wins. Alternative
generation models, such as probabilistic latent_quality–dependent rules, may be
used in sensitivity analysis but must be documented explicitly in the generator
parameters and manifest.

On completion:

- if `is_major_win == true`, the engine emits a structured `MajorWinEvent`
- if `is_major_win == false`, the initiative completes without surfacing a major win

There is no canonical `viable_discovered` lifecycle state, no pre-completion
discovery threshold, and no residual activation on `viable_discovered`.

### Business
The table below describes the reference characteristic profiles for each initiative type as configured by the canonical generator. These profiles define the default ranges the generator uses when creating a portfolio of initiatives. All ranges are recommendations that the generator uses as defaults; explicit overrides are permitted. The type tag recorded on each resolved initiative identifies which profile was used, enabling post-run reporting disaggregated by initiative type.

In the canonical model, all four initiative types realize value only at a lifecycle transition — either at completion or at a stop decision. No initiative produces a continuous stream of value while work is actively ongoing. Value events occur at defined moments, not continuously.

**Flywheel initiatives** represent extensions of proven strategic mechanisms — distribution networks, automation systems, platform enhancements — where the organization has strong prior conviction about strategic quality. Their characteristics reflect this:

- *Quality profile:* High average quality with low variance. The organization is extending something that already works, so most flywheels are genuinely good.
- *Signal clarity:* Low baseline noise. Because the underlying mechanism is proven, evidence about strategic quality accumulates relatively quickly and clearly.
- *Dependency:* Low to moderate. Flywheels may depend on some external factors, but less than exploratory work.
- *Value mechanism:* Ongoing compounding returns activated at completion. Once a flywheel initiative completes, it generates a persistent value stream with slow decay — the compounding mechanism keeps producing returns long after the team has moved on. This is the defining characteristic of the flywheel type. The initiative produces no one-time completion payoff; all of its value comes through the ongoing mechanism.
- *Duration:* Long — typically 25 to 45 weeks. Flywheel work is substantial and takes time to complete.
- *Major-win potential:* None. Flywheels do not surface transformational discoveries. Their value is in reliable, persistent, compounding returns.
- *Visible opportunity ceiling:* Not applicable. Flywheels are not bounded-prize initiatives and do not use the bounded-prize patience rule.
- *Capability contribution:* None. Flywheels contribute economic value, not organizational learning capability.

**Right-tail initiatives** represent exploratory bets where most attempts will be mediocre but a small fraction may prove genuinely transformational. Their characteristics reflect the high-uncertainty, high-potential-upside nature of exploratory work:

- *Quality profile:* A distribution where most draws produce mediocre quality, but a small fraction produce very high quality. This captures the structural reality of exploratory work: most bets do not pay off, but the ones that do can be transformational.
- *Signal clarity:* High baseline noise. Evidence about whether an exploratory initiative is genuinely promising accumulates slowly and ambiguously. This is what makes exploratory governance hard — the organization cannot tell early whether it is looking at a future breakthrough or an expensive disappointment.
- *Dependency:* Moderate to high. Exploratory initiatives tend to depend on factors outside the team's direct control — technology readiness, market timing, regulatory environment, partner ecosystem development.
- *Value mechanism:* Major-win discovery at completion. If the initiative completes and its hidden quality exceeds the major-win threshold, it surfaces a structured major-win event. If it completes but falls below the threshold, it completes without a major win. Right-tail initiatives produce no ongoing value streams and no one-time completion payoff in the canonical model — their value to the study is measured through the major-win discovery outcome dimension, not through economic value within the horizon.
- *Duration:* Long — typically 40 to 220 weeks, varying by organizational environment. Many right-tail initiatives will not complete within the six-year study horizon under impatient governance, which is precisely the phenomenon the study is designed to measure.
- *Visible opportunity ceiling:* Set at generation from a market-opportunity distribution. This gives governance a basis for calibrating bounded-prize patience — larger visible opportunities earn more patience before the inadequacy trigger fires.
- *Capability contribution:* None. Right-tail initiatives contribute potential transformational discovery, not organizational learning capability.

**Whether a right-tail initiative is a major win is determined at creation, not during execution.** The generator assigns this hidden flag at the moment the initiative is created, based on a deterministic threshold rule applied to the initiative's true underlying quality: if the quality exceeds a unified threshold of 0.80, the initiative is flagged as a major win; otherwise it is not. This flag is hidden from governance throughout the run and revealed only at completion. All three environments share the same threshold; what varies across environments is the quality distribution, producing different major-win incidence rates (~3% for balanced incumbent, ~1% for short-cycle, ~5-8% for discovery-heavy) consistent with the study's calibration evidence.

This design preserves the interpretive meaning of governance's learning process: governance regimes that learn to identify high-quality exploratory initiatives and persist through uncertainty are the same regimes that will surface major wins. There is no separate "discovery" event before completion and no pre-completion viability state. The initiative either completes and reveals whether it was a major win, or it is stopped and the major-win potential is never realized. Alternative generation rules may be explored in sensitivity analysis but must be explicitly documented.

**Enabler initiatives** represent investments in organizational learning infrastructure — data and analytics platforms, experimentation systems, automated testing pipelines, dependency reduction between teams, process improvements that make future evaluation faster and cheaper. Their characteristics reflect this indirect, capability-building role:

- *Quality profile:* Moderate average quality. Enablers vary in how effective they turn out to be, but they are neither as reliably high-quality as flywheel extensions nor as uncertain as exploratory bets.
- *Signal clarity:* Low to moderate baseline noise. Enabler quality is somewhat easier to assess than exploratory work but not as immediately clear as extending a proven mechanism.
- *Dependency:* Low. Enablers tend to be internally focused with fewer external dependencies.
- *Value mechanism:* Portfolio capability contribution at completion. When an enabler completes, its realized contribution to organizational learning capability is determined by its true quality multiplied by its capability contribution scale, subject to the organizational capability ceiling. Enablers produce no direct economic value — no completion payoff and no ongoing value stream. Their entire value is indirect: they reduce the noise in strategic signals across the entire portfolio, making every future initiative evaluation faster and more accurate. In the canonical study, accumulated capability also decays over time, so enabler effects are durable but not permanent — the organization must continue investing in learning infrastructure to maintain its advantage.
- *Duration:* Moderate — typically 10 to 30 weeks. Enabler work is substantial but shorter than flywheel or right-tail initiatives.
- *Major-win potential:* None. Enablers do not surface transformational discoveries. Their value is in improving the organization's ability to find and evaluate future opportunities.
- *Visible opportunity ceiling:* Not applicable. Enablers are not bounded-prize initiatives.

Because enabler effects are realized only at completion, every enabler must have a defined completion timeline. An enabler without a completion condition would not be a different kind of enabler — it would be a malformed initiative that can never deliver its intended capability improvement.

**Quick-win initiatives** represent bounded, near-term opportunities where the organization can capture known value quickly. Their characteristics reflect the low-risk, fast-turnaround nature of this work:

- *Quality profile:* Moderate to high average quality with low variance. Quick wins are relatively predictable — the question is less whether they will succeed and more whether the organization allocates team capacity to capture them.
- *Signal clarity:* Low baseline noise. Evidence about quick-win quality accumulates rapidly, enabling confident governance decisions early.
- *Dependency:* Low. Quick wins are typically self-contained with few external dependencies.
- *Value mechanism:* Primarily a one-time completion payoff, with an optional small secondary residual tail. The structural distinction from flywheels is important: flywheels are ongoing-stream-dominant with slow decay (persistent compounding), while quick wins are payoff-dominant with at most a bounded residual tail that approaches zero quickly. Quick wins are about capturing immediate, known value — not building compounding mechanisms.
- *Duration:* Short — typically 3 to 10 weeks. Quick wins complete and realize value early in the horizon, freeing the team for reassignment.
- *Major-win potential:* None. Quick wins do not surface transformational discoveries.
- *Visible opportunity ceiling:* Not applicable. Quick wins are not bounded-prize initiatives.
- *Capability contribution:* None. Quick wins contribute immediate economic value, not organizational learning capability.

**A structural note on all initiative types.** All initiatives begin with an execution belief of 1.0 — the assumption that the initiative is on plan. This neutral starting point means governance must accumulate evidence to detect execution overruns rather than beginning with any preconceived expectation of delay.

**Construction invariant reminder.** Any initiative designed to activate an ongoing value stream or capability contribution at completion must have its true completion timeline defined at generation. This applies to all flywheel initiatives (ongoing value activation at completion), all quick-win initiatives with residual tails (ongoing value activation at completion), and all enabler initiatives (capability contribution at completion). The generator enforces this as a structural guarantee.

## Experimental variants (out of canonical scope)


### Academic
Mid-run initiative sourcing — in which governance adds new initiatives to the unassigned
pool during an active run — is explicitly out of canonical scope for this study. The
fixed-pool-at-run-start assumption is required for causal comparability across governance
regimes: if different policies could source different initiatives mid-run, observed outcome
differences could reflect sourcing differences rather than governance differences.

If a future researcher wishes to explore endogenous sourcing as an experimental treatment,
the runner must implement it as an opt-in variant gated behind an explicit configuration
flag (e.g., `allow_mid_run_sourcing: true`). In any comparative experiment using mid-run
sourcing, the sourcing rate and constraints must be held constant across governance regimes
so that sourcing remains an environmental parameter rather than a governance lever.

The distinction is fundamental to the study's identification strategy: the policy's action space is restricted to decisions about existing opportunities (continue/stop, attention allocation, team assignment). The availability of opportunities is determined by the environment (initial pool plus frontier-driven materialization). If the policy could also determine which opportunities exist — altering the state space of future decisions — the experimental design could not attribute outcome differences solely to how the policy maps observations to actions within a fixed opportunity structure.

#### SourceInitiatives (named experimental variant)

`SourceInitiatives` is a governance action that was considered for canonical scope and
explicitly removed. In a hypothetical implementation, it would allow a governance policy
to add new initiatives to the unassigned pool during an active run. It is retained here
as a named experimental variant for future reference.

If implemented, `SourceInitiatives` must be gated behind `allow_mid_run_sourcing: true`
in the run configuration. In any comparative experiment using this variant, the sourcing
rate, initiative type distribution, and pool size constraints must be held constant across
governance regimes. Without that constraint, observed outcome differences cannot be
attributed to governance behavior rather than to sourcing differences.

The requirement that sourcing parameters be held constant across regimes is an instance of the general CRN discipline: every aspect of the stochastic environment that is not the object of study must be identical across the comparison set. Sourcing rate and initiative type distribution, if allowed to vary across regimes, would be confounds with the same status as varying `ModelConfig` parameters — they change what the policy faces, not how the policy responds to what it faces.

### Business
Mid-run initiative sourcing — in which governance adds new initiatives to the available pool during an active run — is explicitly out of scope for the canonical study. The reason is fundamental to the study's experimental design: if different governance regimes could source different initiatives during a run, outcome differences would reflect a combination of governance decision quality and sourcing quality, and the study could not cleanly attribute results to governance behavior alone.

The canonical study requires that the initiative pool available to governance is determined by the environment — the initial pool plus any frontier-generated initiatives — not by governance action. Governance decides what to do with available opportunities; it does not decide which opportunities exist.

If a future researcher wishes to explore endogenous sourcing — testing what happens when governance can actively seek out new opportunities during a run — the implementation must treat sourcing as an explicit, opt-in experimental variant. In any comparative experiment that includes mid-run sourcing, the sourcing rate, the types of initiatives that can be sourced, and any constraints on pool size must be held constant across all governance regimes being compared. Without that constraint, the experiment would be comparing governance regimes that face different opportunity pools by construction, which would make the comparison meaningless for isolating governance effects.

#### SourceInitiatives (named experimental variant)

A governance action called "SourceInitiatives" — which would allow a governance policy to actively add new initiatives to the available pool during a run — was considered for inclusion in the canonical study and explicitly removed. It is documented here as a named experimental variant for future reference, not as a feature of the canonical design.

If implemented in a future study, this action must be gated behind an explicit configuration flag that defaults to off. In any comparative experiment using this variant, the sourcing rate, the distribution of initiative types that can be sourced, and any pool size limits must be held constant across governance regimes. The reason is the same as the general principle above: if one regime can source better or more opportunities than another, outcome differences cannot be attributed to governance decisions. Sourcing, if studied at all, must be treated as an environmental parameter — something that is the same for all governance regimes in a comparison — not as a governance lever that varies across regimes.
