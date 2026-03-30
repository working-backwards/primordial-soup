# Calibration Note — Generator Parameter Grounding

## Purpose


### Academic
This document records the empirical calibration of initiative-generator
parameters for the Primordial Soup study. It preserves the evidence chain
from external research to the specific Beta distributions, thresholds,
and duration ranges used in the three named environment families.

The calibration was performed in March 2026 after a 63-run baseline
campaign showed zero major wins across all archetypes and families,
indicating a structural collapse in right-tail major-win eligibility
rather than a governance finding.

The scope extends beyond the right-tail recalibration. This document also
records the evidence basis and parameter choices for all four initiative
families — including duration ranges, signal noise, residual rates,
capability contribution scales, and frontier supply mechanics — so that
the full generator specification can be audited against its empirical and
structural justifications.

The document is organized as a diagnostic narrative: Section 1 traces the
right-tail collapse, the evidence used to correct it, and the resulting
parameters. Sections 2–4 record the remaining generator parameters with
their calibration basis. Section 5 ranks parameters by expected sensitivity.
Section 6 catalogues the limitations of the evidence chain.

---

### Business
This document records why and how the study's initiative parameters were
grounded in external evidence, and what changed when early test runs revealed
a fundamental problem with the original settings.

The most important thing a reader should understand about this document is
that it exists because of a failure. In March 2026, the study ran 63
simulations across every governance regime and every organizational
environment. The result: zero major wins discovered. Not a single
transformational breakthrough surfaced under any governance approach, in any
environment, across any of those runs.

This was not a finding about governance. It was a modeling error. The
parameters governing how often exploratory initiatives could turn out to be
genuinely transformational had been set so conservatively that the outcome
was structurally impossible — like studying hiring policy in a world where no
qualified candidates exist in the applicant pool. The simulation was
faithfully modeling the governance question, but operating in an environment
where the phenomenon it was designed to study could never occur.

This document traces the diagnosis, the external evidence used to correct
it, and the resulting parameter choices for all three organizational
environments. It also records the evidence basis for every other initiative
parameter — how long different types of work take, how uncertain they are,
what kind of value they produce — so that a reader can assess whether the
study's inputs are grounded in organizational reality.

---

## 1. Right-Tail Parameters: Evidence, Diagnosis, and Fix


### Academic
#### 1.1 Diagnosis

The pre-calibration right-tail configuration for `balanced_incumbent`
used Beta(1.4, 6.6) with `q_major_win_threshold = 0.82`. The 99th
percentile of Beta(1.4, 6.6) is approximately 0.55 — no draws
reach 0.82 in any practical sample. The analytical probability:

    P(q >= 0.82 | Beta(1.4, 6.6)) ≈ 0.003%

Expected major-win-eligible initiatives per 40-initiative pool: ~0.001.
One eligible every ~900 seeds. The same structural problem existed in
all three families: Beta(1.2, 7.0) with threshold 0.85
(`short_cycle_throughput`) and Beta(1.7, 5.8) with threshold 0.78
(`discovery_heavy`) also produced near-zero tail probabilities.

This is a calibration failure, not a governance finding. The generator
was structurally incapable of producing the phenomenon the study exists
to investigate.

The consequence for the experimental design is that the policy comparison
was degenerate with respect to the major-win discovery outcome family.
When `P(is_major_win = true)` is effectively zero across all seeds,
the major-win discovery rate is zero under every governance policy, and
the study cannot discriminate between patient and impatient regimes on
this dimension. The experiment was well-posed — the policy space, the
observation model, and the stopping logic were all functioning correctly —
but it was operating in a parameter region where one of the three primary
outcome families was structurally unreachable.

#### 1.2 Evidence basis

Three independent evidence sources were triangulated:

1. **Incumbent new-business-building research (Project 1).**
   Company-level breakthrough outcomes among completed exploratory
   initiatives: 0.3–4% incidence (midpoint ~1.5%). Duration to stable
   resolution: 3–10 years (midpoint ~5 years). "Major win" defined as
   a governance-triggering scale-decision event, not merely a positive
   return.

2. **Internal venture and exploratory-innovation evidence (Project 1).**
   Corroborates the rare-but-nonzero range. Hit rates in structured
   corporate venturing programs align with the 1–3% band when filtered
   for outcomes at the scale the study models.

3. **Parametric analysis (Project 3).** Systematic evaluation of Beta
   family parameters against the threshold rule
   `is_major_win = (q >= q_major_win_threshold)`. Beta(0.8, 2.0) with
   threshold 0.80 produces ~3% major-win incidence — squarely in the
   empirically supported mid-case range.

#### 1.3 Calibrated parameters

All three families now use a unified `q_major_win_threshold = 0.80`.
Family-specific Beta distributions are tuned to produce different
major-win incidence levels spanning the empirical range:

| Family | Beta(α, β) | P(q ≥ 0.80) | Design intent |
|--------|-----------|-------------|---------------|
| `balanced_incumbent` | Beta(0.8, 2.0) | ~3% | Mid-case |
| `short_cycle_throughput` | Beta(0.6, 2.5) | ~1% | Scarce major wins |
| `discovery_heavy` | Beta(1.2, 1.8) | ~5–8% | Rich major wins |

The design uses a common threshold with family-varying distributional
shape rather than family-varying thresholds. This isolates the
experimental variation: families differ in how the latent quality mass
is distributed relative to a fixed decision boundary, not in the
boundary itself. Findings that hold across all three families are
robust to uncertainty in the tail probability; findings conditional on
a single family are conditional on the opportunity landscape.

#### 1.4 Duration calibration

Right-tail initiatives represent multi-year exploratory efforts.
Project 1 supports a business-facing duration anchor of 3 / 5 / 10
years to stable resolution. With one tick = one week:

| Family | `true_duration_range` | Calendar equivalent | Design intent |
|--------|----------------------|---------------------|---------------|
| `balanced_incumbent` | (104, 182) | 2.0–3.5 years | Mid-case |
| `short_cycle_throughput` | (80, 156) | 1.5–3.0 years | Shorter cycles |
| `discovery_heavy` | (130, 260) | 2.5–5.0 years | Longer exploration |

`planned_duration_range` is set to (1.2×, 1.2×) of the true range
(rounded), reflecting the systematic overestimate typical of
exploratory work planning:

| Family | `planned_duration_range` |
|--------|-------------------------|
| `balanced_incumbent` | (125, 220) |
| `short_cycle_throughput` | (96, 187) |
| `discovery_heavy` | (156, 312) |

The 1.2× planning bias multiplier is a structural assumption grounded
in the well-documented tendency toward optimistic duration estimates in
exploratory work, where the scope of required learning is itself
uncertain at the outset. This produces `latent_execution_fidelity`
values (`planned / true`) clustered near 0.83 for right-tail
initiatives, meaning the execution belief will converge toward a
value below 1.0 even for initiatives proceeding at their true pace.

The 313-tick horizon (6 years) means many right-tail initiatives will
not complete, especially under less patient governance. This is
intentional: the study measures governance's ability to persist through
uncertainty. The duration range is calibrated so that patient governance
has a feasible path to right-tail completion within the horizon, while
impatient governance faces a genuine tradeoff between early termination
and continued investment under ambiguous signals.

#### 1.5 What was NOT changed

Pool size (200), flywheel/enabler/quick-win quality distributions,
residual rates, capability scales, signal noise, learning rates, ramp
period, and frontier degradation rates were all unchanged by the
right-tail recalibration. Pool composition is an environmental
condition, not a calibration target. (Pool counts, flywheel duration,
workforce structure, and portfolio mix targets were subsequently
revised in a separate calibration pass — see `environment_families.md`
for current values.)

The right-tail recalibration was narrowly targeted at the parameters
that were preventing the major-win mechanism from activating. All
other generator parameters were already producing the intended
structural dynamics and required no adjustment.

---

### Business
#### 1.1 Diagnosis

The original parameters for exploratory initiatives made transformational
breakthroughs essentially impossible. In the mid-case organizational
environment, the quality distribution for right-tail initiatives was set so
that even the very best outcomes — the 99th percentile — fell far short of
the threshold required to qualify as a major win. The probability of any
single exploratory initiative reaching major-win quality was approximately
0.003 percent. In a pool of 40 exploratory initiatives, the expected number
of major-win-eligible initiatives was roughly one-thousandth of one. An
organization would need to run approximately 900 complete simulations before
a single eligible initiative appeared by chance.

The same structural problem existed in all three organizational environments.
Every environment's quality distribution and threshold combination produced
near-zero probabilities of transformational outcomes.

This matters because the entire purpose of the study is to understand how
governance affects an organization's ability to discover and pursue
transformational opportunities. If the simulation cannot produce such
opportunities regardless of governance, it cannot distinguish between patient
governance and impatient governance on this dimension. The study was asking
the right question in a world that structurally prevented the answer from
existing.

#### 1.2 Evidence basis

Three independent evidence sources were used to establish how often
exploratory initiatives actually produce transformational outcomes in real
organizations:

1. **Research on new-business-building in large incumbent firms.** Studies of
   company-level breakthrough outcomes among completed exploratory initiatives
   show an incidence of roughly 0.3–4 percent, with a midpoint around 1.5
   percent. Time from launch to stable resolution — meaning the point where
   the organization can confidently assess whether the initiative has
   succeeded at scale — ranges from 3 to 10 years, with a midpoint around 5
   years. Critically, "major win" in this evidence means a governance-scale
   event: a breakthrough large enough to trigger organizational decisions
   about scaling, not merely a positive financial return.

2. **Corporate venturing and exploratory-innovation evidence.** Independent
   evidence from structured corporate venture programs corroborates the
   rare-but-nonzero range. When filtered for outcomes at the scale this study
   models — not small successes, but outcomes that fundamentally change the
   organization's trajectory — hit rates align with the 1–3 percent band.

3. **Systematic parameter analysis.** A formal evaluation of how different
   quality distributions interact with the major-win threshold to produce
   specific breakthrough incidence rates. This analysis identified the
   parameter combination that produces approximately 3 percent major-win
   incidence — squarely in the middle of the empirically supported range.

#### 1.3 Calibrated parameters

All three organizational environments now use a single, unified quality
threshold for major-win eligibility. What differs between environments is how
the underlying quality of exploratory initiatives is distributed — which
determines how often initiatives reach that threshold.

| Environment | Major-win incidence | Design intent |
|---|---:|---|
| **Balanced incumbent** | ~3% | Mid-case: a typical large organization with a normal mix of exploratory bets |
| **Short-cycle throughput** | ~1% | Scarce major wins: an environment where transformational outcomes are rare and most exploratory work yields modest results |
| **Discovery-heavy** | ~5–8% | Rich major wins: an environment with a richer vein of transformational opportunity, perhaps an emerging market or platform shift |

These three incidence rates span the empirically supported range. Findings
that hold across all three are structurally robust. Findings that hold in
only one environment are conditional on the opportunity landscape.

#### 1.4 Duration calibration

Exploratory initiatives are multi-year efforts. The external evidence supports
a business-facing duration anchor of 3 / 5 / 10 years to stable resolution,
depending on the type of organization and the nature of the exploration. The
study translates these into initiative durations for each environment:

| Environment | Actual duration range | Design intent |
|---|---|---|
| **Balanced incumbent** | 2.0–3.5 years | Mid-case |
| **Short-cycle throughput** | 1.5–3.0 years | Shorter innovation cycles, faster-moving market |
| **Discovery-heavy** | 2.5–5.0 years | Longer exploration horizons, deeper uncertainty |

Planning estimates are set at approximately 1.2 times the actual duration,
reflecting the systematic optimism typical of exploratory work planning. When
a team says an exploratory initiative will take two years, it will more likely
take two and a half. This is not a flaw in planning — it is a well-documented
characteristic of work where the scope of what needs to be learned is itself
uncertain.

The study's six-year horizon means that many exploratory initiatives will not
complete, especially under governance regimes that are less willing to persist
through ambiguity. This is intentional. One of the central questions the study
is designed to answer is precisely whether — and when — governance patience
allows transformational opportunities to be realized that impatient governance
would have terminated.

#### 1.5 What was NOT changed

The right-tail recalibration was narrowly targeted. The total size of the
initiative pool (200 initiatives) and all parameters for flywheel, enabler,
and quick-win initiatives — their quality distributions, residual value rates,
capability contributions, signal noise, learning rates, and frontier
degradation rates — were left unchanged by the right-tail recalibration.
(Pool counts, flywheel duration, workforce structure, and portfolio mix
targets were subsequently revised in a separate calibration pass — see
`environment_families.md` for current values.)

This distinction matters. The pool composition is an environmental condition
— it defines the world in which governance operates. The calibration corrected
only the parameters that were preventing the study from producing the
phenomenon it exists to investigate. Everything else was already functioning
as designed.

---

## 2. Frontier and Supply Parameters


### Academic
#### 2.1 Frontier degradation mechanism

Governance regimes consume opportunities from the available pool at
different rates. A regime that aggressively starts and stops initiatives
cycles through available opportunities faster than one that commits
deeply to fewer concurrent bets. The frontier supply mechanism must
prevent artificial exhaustion — a confound in which a regime appears
to underperform not because of its governance decisions but because
it depleted the opportunity pool.

The generator implements two mechanisms to manage opportunity supply
over the 313-tick horizon:

**Quality degradation.** As initiatives are drawn from each family's
pool, the expected quality of remaining opportunities declines at a
family-specific rate, modeling the selection effect whereby the
highest-value opportunities tend to be identified and staffed first.
Degradation rates are ordered by the structural durability of each
family's opportunity landscape:

| Family | `frontier_degradation_rate` | Rationale |
|--------|---------------------------|-----------|
| Quick-win | 0.02 | Bounded, well-understood opportunities are exhausted fastest |
| Flywheel | 0.01 | Established compounding mechanisms degrade moderately |
| Enabler | 0.005 | Infrastructure needs are durable; slow degradation |
| Right-tail | 0.0 | Exploratory opportunities are not diminished by prior attempts |

<!-- specification-gap: the functional form by which frontier_degradation_rate enters the quality draw for newly materialized initiatives is not specified here — whether it shifts the Beta distribution parameters, applies a multiplicative discount to drawn quality, or operates through another mechanism -->

**Pool replenishment.** When a family's available pool is completely
exhausted, new initiatives are materialized.
`replenishment_threshold = 0` — replenishment triggers only when the
pool is fully empty, not before. This prevents the generator from
maintaining an artificially comfortable opportunity supply regardless
of consumption rate.

#### 2.2 Right-tail re-attempt semantics

Right-tail uses prize-preserving refresh with
`right_tail_refresh_quality_degradation = 0.0` (fresh draw from
same distribution on re-attempt). When a right-tail initiative is
re-staffed after a previous team was withdrawn, it receives an
independent draw from the same family-specific Beta distribution.
The rationale is that in exploratory domains, re-approaching a problem
with a different team constitutes a substantially independent attempt
rather than a continuation of the prior effort. The `is_major_win`
flag is re-determined by the threshold rule applied to the new draw.
Project 4 flagged potential
fragility in attempt-count tracking but confirmed the current
design is sound for the baseline study.

<!-- specification-gap: the re-attempt semantics for non-right-tail families are not specified — whether stopped flywheel, enabler, or quick-win initiatives can be re-staffed, and if so, whether they retain their original latent quality or receive fresh draws -->

#### 2.3 Assessment

No changes to frontier parameters. The current configuration provides
adequate opportunity supply without exhaustion artifacts. Frontier
sensitivity is a future experiment, not a calibration concern.

No governance regime in the current archetype set consumes
opportunities at a rate that approaches pool exhaustion within the
313-tick horizon. Whether frontier degradation rates interact with
governance findings is a question for future sensitivity analysis,
not a baseline calibration concern.

---

### Business
#### 2.1 How the opportunity pipeline works

Over the course of a six-year simulation, governance regimes consume
opportunities at different rates. A regime that aggressively starts and stops
initiatives cycles through the available pool faster than one that commits
deeply to fewer bets. The model needs to ensure that the opportunity pipeline
does not artificially run dry — creating a situation where a regime looks bad
not because of its governance decisions, but because it exhausted all
available opportunities.

The model handles this through two mechanisms. First, the quality of
remaining opportunities in each category degrades gradually over time as the
best opportunities are picked off first — mimicking how real organizations
find that the most obvious bets are taken early and later opportunities
require more work to evaluate. The degradation rates differ by initiative
type: quick-win opportunities degrade fastest (the low-hanging fruit
disappears quickly), flywheel opportunities degrade moderately, enabler
opportunities degrade slowly (infrastructure needs tend to be durable), and
exploratory opportunities do not degrade at all (genuinely novel
opportunities are not diminished by earlier ones having been attempted).

Second, when a category's pipeline is completely exhausted, it replenishes
— but only when fully empty, not before. This prevents the model from
creating an artificially comfortable environment where opportunities are
always abundant regardless of how aggressively governance consumes them.

For exploratory initiatives specifically, when a right-tail opportunity is
re-attempted after a previous team was pulled off, it receives a fresh draw
from the same quality distribution. The rationale is that re-approaching an
exploratory opportunity with a new team and fresh perspective is more like
a new attempt than a continuation of the old one. The potential for
transformational outcomes is preserved, not degraded by previous failed
attempts.

#### 2.2 Assessment

The current opportunity supply parameters are adequate. No governance regime
in the study consumes opportunities fast enough to create artificial
exhaustion effects. Whether and how frontier degradation rates affect
governance findings is a question for future sensitivity analysis, not a
calibration concern for the baseline study.

---

## 3. Flywheel, Enabler, and Quick-Win Parameters


### Academic
The non-right-tail families are parameterized to implement distinct
payoff structures and learning dynamics. Each family's parameters are
chosen to faithfully represent its defining value-creation mechanism
rather than fitted to external data.

#### 3.1 Flywheel

- **Quality:** Beta(6.0, 2.0), mean ≈ 0.75. Flywheel initiatives are
  high-mean, low-variance: established business models with known
  compounding dynamics. The high mean reflects that organizations
  generally have good ex-ante visibility into flywheel quality.
- **Duration:** 25–45 ticks (6–10 months). Flywheel execution is
  incremental, not exploratory — shorter than right-tail by design.
- **Residual:** Rate 0.5–2.0, decay 0.005–0.02. Moderate-to-high
  residual with slow decay models persistent flywheel momentum.
- **No completion lump:** Value comes from durable streams, not
  one-time events.

The Beta(6.0, 2.0) shape places ~97% of the probability mass above
0.40 and ~73% above 0.70, producing a quality landscape where most
flywheels are genuinely good bets but a small fraction underperform.
The variance (σ² ≈ 0.021) is the lowest of any family, reflecting
that the strategic uncertainty in flywheel work is primarily about
execution, not about whether the underlying compounding mechanism is
sound.

#### 3.2 Enabler

- **Quality:** Beta(4.0, 4.0), mean = 0.50. Enablers have symmetric
  uncertainty — they may or may not deliver as promised.
- **Duration:** 10–30 ticks (2–7 months). Infrastructure-style work
  with bounded scope.
- **Capability contribution:** Scale 0.1–0.5. The sole value channel
  — enablers improve future organizational capability.
- **No direct value channels:** Enablers do not produce lump or
  residual value. Their contribution is indirect through capability.

The Beta(4.0, 4.0) symmetric distribution reflects genuine ex-ante
uncertainty about enabler delivery. Unlike flywheels, there is no
strong prior that most enablers succeed — approximately half will
deliver meaningful capability improvement, half will fall short.

The absence of direct value channels is a deliberate design choice
with consequences for the experimental comparison. Enabler value
enters the model exclusively through the portfolio capability term
C_t, which reduces effective signal noise σ_eff for all future
staffed initiatives. Governance policies that evaluate initiatives
on direct realized value (lump or residual) will systematically
undervalue enabler work relative to policies that account for
capability accumulation. This asymmetry is a feature of the
experimental design: it tests whether governance regimes that
invest in indirect capability improvement produce measurably
different long-run outcomes.

#### 3.3 Quick-win

- **Quality:** Beta(5.0, 3.0), mean ≈ 0.625. Moderate-to-high quality,
  low variance. Quick wins are well-understood opportunities.
- **Duration:** 3–10 ticks (3–10 weeks). Short execution cycles.
- **Completion lump:** 1.0–5.0. The dominant value channel.
- **Small residual tail:** Rate 0.01–0.10, decay 0.10–0.30. Bounded
  and secondary to the lump.

Quick wins have the shortest execution cycle of any family. Combined
with moderate-to-high quality and a lump-dominant payoff structure,
they represent the lowest-uncertainty, fastest-resolution initiative
type. The high decay rate on the residual tail (0.10–0.30 per tick)
ensures that the residual contribution is bounded and secondary: it
attenuates to negligible levels within 10–30 ticks of completion.

#### 3.4 Calibration basis

These parameters are qualitatively grounded in the study's conceptual
framework (see `study_overview.md`) rather than fitted to external
data. They represent archetypes of organizational initiative types
defined by their value-creation mechanism:

- Flywheels create value through compounding duration
- Quick wins create value through rapid completion
- Enablers create value through capability improvement
- Right-tail initiatives create value through rare breakthroughs

The parameters implement this taxonomy without requiring empirical
precision. The study's governance findings are relative (regime A vs.
regime B in the same environment), so absolute parameter values matter
less than structural relationships between families.

The critical structural relationships that must hold for the governance
comparison to be valid are:

- Flywheel quality distribution is left-skewed (most are good bets);
  right-tail quality distribution is right-skewed (most are not major
  wins, but a tail fraction are)
- Quick-win duration is an order of magnitude shorter than right-tail
  duration
- Enabler value is exclusively indirect (enters through C_t, not
  through lump or residual channels)
- Flywheel residual decay is slow relative to quick-win residual decay

If these structural orderings hold, the governance comparison will
surface real tradeoffs between families regardless of the exact
parameter values. What would distort findings is not imprecise absolute
values but structurally wrong relationships — for instance, if
flywheels were accidentally parameterized to behave like quick wins.

---

### Business
Each of the four initiative types is parameterized to faithfully represent a
distinct mechanism through which organizations create long-term value. The
parameters are not fitted to data from any specific organization — they are
designed to capture the structural characteristics that define each type.

#### 3.1 Flywheel initiatives

Flywheel initiatives represent established business models with known
compounding dynamics — distribution networks, marketplace platforms,
subscription ecosystems, automation systems. Organizations generally have
good visibility into whether these will work before they begin; the question
is execution, not strategic uncertainty.

- **Quality visibility:** High. Flywheels are the most predictable initiative
  type. Organizations can assess with reasonable confidence before starting
  whether the compounding mechanism is sound. The quality distribution
  reflects this: most flywheels are genuinely good bets, with relatively
  few that turn out to be poor investments.
- **Duration:** 6–10 months. Flywheel execution is incremental — building on
  established models — not exploratory. Significantly shorter than right-tail
  work by design.
- **Value mechanism:** Ongoing returns that persist and compound after the
  team moves on. Moderate-to-high initial returns with slow decay, modeling
  the persistent momentum of a well-built flywheel. A completed distribution
  network or automation system continues generating value for years after the
  team that built it has redeployed.
- **No one-time completion payoff.** Flywheel value comes entirely from
  durable, compounding streams, not from a single event at completion.

#### 3.2 Enabler initiatives

Enablers represent investments in organizational infrastructure — data and
analytics platforms, experimentation capabilities, automated testing
pipelines, dependency reduction between teams. They produce no direct
economic return. Their entire value is indirect: they make everything else the
organization does better by reducing the noise in the signals that future
initiatives produce.

- **Quality visibility:** Moderate and symmetric. Enablers have genuine
  uncertainty about whether they will deliver as promised. Unlike flywheels,
  there is no strong prior that most enablers succeed — roughly half will
  deliver meaningful capability improvement and half will fall short.
- **Duration:** 2–7 months. Infrastructure-style work with bounded scope.
- **Value mechanism:** Capability contribution only. A completed enabler
  improves the organization's ability to evaluate all future work. The
  contribution scale ranges from modest (a small improvement in signal
  clarity) to substantial (a meaningful reduction in the noise that
  governance must filter through when making stop/continue decisions).
- **No direct economic value.** Enablers do not produce lump payoffs or
  ongoing revenue streams. This is a deliberate design choice that captures
  the real challenge of enabler work: its value is entirely indirect and
  shows up later in better decisions across the portfolio, making it
  chronically difficult to justify in governance regimes that evaluate
  initiatives on direct returns.

#### 3.3 Quick-win initiatives

Quick wins represent well-understood opportunities with short execution
cycles — contract fulfillment, product enhancements targeting known customer
segments, process optimizations with clear scope.

- **Quality visibility:** Moderate-to-high with low variance. Quick wins are
  the most well-understood initiative type. There is relatively little
  strategic ambiguity about whether they will succeed.
- **Duration:** 3–10 weeks. The shortest execution cycle of any initiative
  type.
- **Value mechanism:** A one-time payoff at completion, ranging from modest
  to meaningful. This is the dominant value channel. Quick wins may also
  generate a small residual tail — minor ongoing returns — but this is
  bounded and secondary to the completion payoff.

#### 3.4 Calibration basis

These parameters are grounded in the study's conceptual framework rather than
fitted to external data. Each initiative type is defined by its
value-creation mechanism:

- Flywheels create value through compounding duration — the longer the
  mechanism runs, the more it produces
- Quick wins create value through rapid completion — the faster they finish,
  the sooner the return is captured
- Enablers create value through capability improvement — they make the
  organization better at evaluating everything else
- Right-tail initiatives create value through rare breakthroughs — most will
  not produce transformational outcomes, but some will

The parameters implement this taxonomy faithfully. Because the study produces
relative comparisons — governance regime A versus regime B in the same
environment — the absolute parameter values matter less than getting the
structural relationships between types approximately right. If flywheels are
genuinely parameterized to compound, quick wins are genuinely fast, enablers
genuinely contribute capability, and right-tail work is genuinely uncertain
and long-duration, the governance comparison will surface real structural
tradeoffs regardless of the exact numbers.

---

## 4. Signal Noise, Learning Rate, and Ramp


### Academic
#### 4.1 Signal noise

- `base_signal_st_dev_default = 0.15` (ModelConfig). Per-type ranges
  vary: flywheel (0.05–0.15), enabler (0.05–0.20), quick-win
  (0.05–0.15), right-tail (0.20–0.40).
- Right-tail has the highest noise floor, reflecting that exploratory
  work generates noisier signals about underlying quality.

The noise ordering across families is consequential for the
experimental comparison. Recall the strategic signal model:

    y_t ~ Normal(q, σ_eff²)

where σ_eff incorporates the family-specific `sigma_base`, dependency
level, attention modifier, and portfolio capability. Higher σ_base
means more observations are required before `quality_belief_t`
converges to a reliable estimate of `latent_quality`. The per-family
noise ranges implement the following information structure:

| Family | σ_base range | Implication for belief convergence |
|--------|-------------|----------------------------------|
| Flywheel | 0.05–0.15 | Fast convergence; governance can form reliable quality assessments within a few months of staffed work |
| Quick-win | 0.05–0.15 | Fast convergence; short duration means the initiative often completes before belief converges fully, but this is acceptable because the lump payoff is bounded |
| Enabler | 0.05–0.20 | Moderate convergence; the indirect value channel means governance must evaluate enabler quality from noisier signals than flywheel or quick-win work |
| Right-tail | 0.20–0.40 | Slow convergence; early observations from a high-quality right-tail initiative may be indistinguishable from those of a mediocre one |

The right-tail noise floor is the most consequential noise setting
in the model. It directly determines how much staffed time —
and how much executive attention (through the g(a) modifier in
σ_eff) — governance must invest before it can reliably discriminate
between right-tail initiatives that merit persistence and those
that should be stopped. This is the primary mechanism through which
governance patience acquires informational value: under high noise,
premature stopping destroys option value because the belief estimate
has not yet converged.

#### 4.2 Learning rate

- `learning_rate = 0.1` (η in the design docs). Controls how quickly
  quality_belief_t converges toward latent_quality.
- `execution_learning_rate = 0.1` (η_exec). Controls execution belief
  convergence.
- Both are moderate: fast enough to produce meaningful belief
  evolution within the 313-tick horizon, slow enough that governance
  patience matters.

The choice of η = 0.1 places the experiment in the regime where the
policy comparison is informative. Consider the two degenerate
alternatives:

- **η → 1 (instantaneous learning):** `quality_belief_t` converges
  to `latent_quality` within a few ticks regardless of noise.
  All governance policies reach the same beliefs and make the same
  stop/continue decisions. The policy comparison collapses — patience
  has no informational advantage because there is no learning to be
  patient for.
- **η → 0 (no learning):** `quality_belief_t` remains near its
  initial value (0.5) indefinitely. Even patient governance cannot
  form a reliable quality estimate within the horizon. Patience has
  no informational payoff because belief evolution is too slow to
  affect decisions.

At η = 0.1, beliefs evolve meaningfully over the horizon — the EMA
half-life is approximately 7 ticks — but convergence is slow enough
that the accumulated observation count matters. A governance regime
that allocates more attention (reducing σ_eff and thus improving
signal-to-noise ratio) and persists longer (accumulating more
observations) will genuinely produce more accurate beliefs than
one that does not. This is the operating region where the three
research questions — patience effects on major-win discovery,
attention allocation effects on stop/continue quality, enabler
investment effects on capability trajectories — can be meaningfully
investigated.

<!-- specification-gap: the EMA half-life claim of ~7 ticks assumes a specific relationship between η and convergence rate; the exact convergence dynamics of the clamped EMA with noisy inputs are not formally derived here -->

#### 4.3 Ramp period

- `ramp_period = 4` ticks with linear shape. Represents a one-month
  switching cost when teams are reassigned.
- This is a structural governance cost, not a calibration target.
  Ramp-period sensitivity is a separate experiment dimension.

During the ramp period, the learning efficiency modifier λ_ramp
increases linearly from a reduced value to 1.0 over the 4-tick
window. This means that the effective learning rate for a newly
assigned team is lower than η during the ramp, slowing belief
convergence and reducing the informational value of the first month
of work. A governance regime that frequently reassigns teams pays
this switching cost repeatedly; one that commits teams for longer
stretches amortizes it.

The ramp period interacts with the signal noise and learning rate
parameters: under high-noise families (right-tail), the ramp cost
is proportionally more damaging because each lost tick of learning
is more valuable when convergence is already slow. However, this
interaction is secondary for the canonical governance sweep, which
holds workforce architecture (team count and size) constant across
regimes.

---

### Business
#### 4.1 How noisy the evidence is

Different types of work produce evidence of different clarity. The model
captures this by assigning each initiative type a range of signal noise —
how much static is mixed in with the genuine evidence about whether an
initiative is strategically sound.

- **Flywheel and quick-win initiatives** produce relatively clean signals.
  Because the underlying business model is well understood, each week of
  work generates evidence that is fairly informative about true quality.
  Signal noise ranges from low to moderate.
- **Enabler initiatives** produce slightly noisier signals. Infrastructure
  work generates evidence that is harder to interpret — whether a data
  platform is actually improving organizational capability is less directly
  observable than whether a product enhancement is succeeding.
- **Right-tail initiatives** produce the noisiest signals by a significant
  margin. This is the most consequential noise setting in the model.
  Exploratory work generates ambiguous evidence: early signals from a
  genuinely transformational initiative may look indistinguishable from early
  signals from a mediocre one. The high noise floor for right-tail work
  means that governance must accumulate substantially more evidence before
  it can form a reliable judgment — which is precisely why patience matters
  more for exploratory initiatives than for any other type.

#### 4.2 How fast the organization updates its beliefs

The learning rate controls how quickly the organization's estimate of an
initiative's quality moves toward the truth as new evidence arrives. The
model uses a moderate rate for both strategic quality beliefs and execution
tracking beliefs.

The rate is calibrated to produce a specific dynamic: fast enough that the
organization's beliefs meaningfully evolve over the six-year study horizon —
a governance regime that pays close attention and persists will genuinely
learn more than one that does not — but slow enough that patience has real
informational value. If learning were instantaneous, all governance regimes
would converge to the same decisions regardless of how patient they were,
and the study's central question would be moot. If learning were glacially
slow, even the most patient governance regime could not form reliable
judgments within the horizon.

The moderate rate ensures that the study operates in the interesting region:
the zone where governance choices about attention, patience, and persistence
genuinely affect how much the organization learns and how good its
stop/continue decisions become.

#### 4.3 Team switching cost

When a team is reassigned from one initiative to another, there is a
one-month ramp-up period during which the new team's ability to generate
useful evidence is reduced. Learning efficiency increases linearly over
this period from reduced effectiveness to full effectiveness.

This represents the real organizational cost of reassignment — the time it
takes a new team to understand the initiative's context, build relationships
with stakeholders, and reach productive velocity. It is a structural
governance cost, not a calibration target. A governance regime that
frequently reassigns teams pays this switching cost repeatedly; one that
commits teams for longer stretches avoids it.

Whether the specific duration of the ramp period (one month) materially
affects governance findings is a question for sensitivity analysis in future
experiments, not a concern for the baseline study.

---

## 5. Sensitivity Ranking


### Academic
Parameters ranked by expected impact on study findings. The ranking
reflects sensitivity with respect to the three primary outcome
families — realized economic performance, major-win discovery, and
organizational capability development — with emphasis on the
major-win discovery dimension, where the pre-calibration collapse
demonstrated that parameter sensitivity can be catastrophic.

1. **q_major_win_threshold and right-tail Beta parameters** — These
   jointly determine whether the major-win mechanism activates at all.
   The pre-calibration collapse demonstrated that this is the single
   most consequential calibration choice. The interaction is
   non-linear: P(q ≥ threshold) is highly sensitive to small changes
   in both the threshold value and the Beta shape parameters,
   particularly in the tail region. If the threshold is set too high
   relative to the distribution's support, or the distribution is too
   concentrated below the threshold, the study structurally cannot
   produce the phenomenon it exists to investigate — as the 63-run
   baseline demonstrated with zero major wins.

2. **Right-tail duration range** — Controls whether right-tail
   initiatives can complete within the horizon under any governance
   regime. If durations exceed the horizon, no governance regime
   can surface major wins. The range must be calibrated so that
   patient governance has a feasible completion path while impatient
   governance faces a genuine tradeoff between early termination and
   continued investment. Duration interacts with the 313-tick horizon
   as a hard constraint: an initiative with `true_duration_ticks` >
   313 cannot complete regardless of governance.

3. **confidence_decline_threshold (governance)** — The primary
   governance lever that the study varies. Not a generator parameter,
   but the most important downstream consumer of the right-tail
   calibration. The threshold must be calibrated relative to the
   right-tail quality distribution and the belief dynamics: if the
   threshold is set below the equilibrium belief for low-quality
   initiatives, governance never stops anything; if set above the
   equilibrium belief for high-quality initiatives, governance stops
   everything prematurely. The interaction between this governance
   parameter and the generator parameters in ranks 1–2 determines
   whether the experimental comparison operates in the informative
   regime.

4. **Learning rate** — Determines belief convergence speed. Too fast
   and all regimes converge to similar decisions; too slow and
   governance patience has no information advantage. The learning
   rate must be set so that the belief trajectory over the horizon
   is sensitive to governance choices (attention allocation, staffing
   persistence) but does not converge before those choices have time
   to differentiate.

5. **Signal noise (base_signal_st_dev)** — Higher noise makes belief
   formation harder and amplifies the value of patience. The noise
   level determines how many staffed ticks — and how much executive
   attention (through σ_eff) — are required before governance can
   reliably discriminate between high-quality and low-quality
   initiatives. This parameter interacts multiplicatively with the
   learning rate to determine overall convergence behavior.

6. **Pool size and composition** — Must be large enough to avoid
   exhaustion artifacts. Current 200 is well above the consumption
   level of the most aggressive archetype. Pool composition (the
   family mix) is an environmental condition that shapes the
   opportunity landscape governance faces but does not interact
   with calibration correctness.

7. **Frontier degradation rates** — Second-order effect: matters only
   when the initial pool is depleted for a family. Relevant for
   extreme governance regimes that cycle through opportunities at
   very high rates, but secondary for the canonical governance
   comparison where pool exhaustion does not occur.

8. **Ramp period** — Structural switching cost. Important for
   workforce-architecture experiments, secondary for the canonical
   governance sweep. The interaction between ramp period and
   right-tail noise is noted (Section 4.3) but is a second-order
   effect when workforce architecture is held constant.

---

### Business
Not all parameters matter equally to the study's findings. The following
ranking identifies which choices have the most leverage over what the study
will reveal, ordered from most consequential to least.

1. **How often exploratory initiatives can be transformational, and what
   quality threshold defines "transformational."** These jointly determine
   whether the major-win mechanism activates at all. The pre-calibration
   collapse — 63 runs, zero major wins — demonstrated that this is the
   single most consequential parameter choice in the entire study. If the
   threshold is too demanding or the quality distribution too conservative,
   the study structurally cannot produce the phenomenon it exists to
   investigate.

2. **How long exploratory initiatives take to complete.** If exploratory
   initiatives require longer than the six-year study horizon to reach
   completion under any governance regime, no regime can surface major wins
   regardless of how patient it is. The duration range must be short enough
   that patient governance has a genuine chance of seeing initiatives through,
   and long enough that impatient governance faces a real tradeoff between
   cutting losses and persisting.

3. **How quickly governance loses conviction and stops an initiative.** This
   is the primary governance lever the study varies — the threshold below
   which the organization's confidence in an initiative has declined far
   enough to trigger termination. It is not a generator parameter, but it is
   the most important downstream consumer of the right-tail calibration.
   If the quality threshold and conviction threshold are not properly
   calibrated relative to each other, the study will either never stop
   anything (if the conviction threshold is too low) or stop everything
   prematurely (if it is too high).

4. **How fast the organization learns from evidence.** The learning rate
   determines how quickly beliefs converge toward truth. If it is too fast,
   all governance regimes reach the same conclusions regardless of patience
   — there is nothing to learn from being more patient. If it is too slow,
   even patient governance cannot form reliable judgments within the horizon
   — patience has no informational payoff.

5. **How noisy the evidence is.** Higher noise makes it harder for the
   organization to form reliable beliefs, which amplifies the value of
   patience and attention. The noise level determines how much work —
   and how much executive attention — is required before governance can
   confidently distinguish a good initiative from a mediocre one.

6. **The size and composition of the initiative pool.** Must be large enough
   that no governance regime artificially runs out of opportunities. The
   current pool of 200 initiatives is well above the consumption rate of
   even the most aggressive governance archetype.

7. **How quickly the quality of remaining opportunities degrades.** A
   second-order effect that matters only when the initial pool for a given
   initiative type has been depleted. Relevant for extreme governance
   regimes that cycle through opportunities very rapidly, but secondary
   for the canonical governance comparison.

8. **The team switching cost (ramp period).** The structural cost of
   reassigning teams between initiatives. Important for experiments that
   vary organizational structure (how many teams, how large), but secondary
   for the canonical governance sweep that holds organizational structure
   constant.

---

## 6. Evidence Limitations


### Academic
1. **Right-tail incidence is calibrated to a range, not a point.**
   The 0.3–4% band from Project 1 spans an order of magnitude. The
   three families are designed to cover low/mid/high within this range,
   but exact Beta parameters are not fitted to empirical distributions.
   Findings that replicate across all three families are robust to
   uncertainty in the tail probability. Findings that hold in only one
   family are conditional on the opportunity landscape and should be
   interpreted with appropriate caution about the specific
   distributional assumptions.

2. **Duration evidence is duration-to-resolution, not duration-to-
   value.** Business-facing duration anchors measure time to stable
   resolution. The simulator's `true_duration_ticks` is a mechanical
   completion clock. The mapping is approximate. In practice, stable
   resolution — the point at which sufficient evidence exists to
   assess success or failure at scale — may occur after mechanical
   completion (the initiative delivered but its impact is not yet
   assessable) or before it (the strategic verdict became clear before
   the work was finished). The model collapses these into a single
   event: completion simultaneously triggers value realization,
   capability contribution, and major-win determination. This
   simplification is symmetric across governance regimes but
   introduces a structural conflation between "work done" and
   "outcome assessable."

3. **Non-right-tail parameters are qualitatively grounded.** Flywheel,
   enabler, and quick-win distributions are archetypal rather than
   empirically fitted. This is acceptable because the study's
   governance findings are relative, but it means absolute value
   levels are not interpretable outside the simulation context.
   The simulation output does not support claims about the absolute
   scale of value from any specific initiative type. What it does
   support is how governance choices affect the relative accumulation
   of lump value, residual streams, major-win discoveries, and
   portfolio capability — and those relative findings are robust to
   reasonable variation in the absolute parameter values, provided
   the structural relationships identified in Section 3.4 are
   preserved.

4. **No feedback calibration.** Parameters were set by forward
   reasoning from evidence, not by fitting to target output
   distributions. This avoids overfitting but means that observed
   output distributions may deviate from practitioner expectations.
   The forward-reasoning approach eliminates the risk of tuning
   parameters until the output matches a target for reasons
   unrelated to model correctness, but it means that no validation
   step has confirmed that the generator produces output
   distributions consistent with any external empirical benchmark
   beyond the right-tail incidence rates in Section 1.

5. **Single-threshold major-win mechanism.** The real-world phenomenon
   of "major wins" is richer than a quality threshold. The binary
   threshold rule is a deliberate simplification that preserves
   tractability at the cost of mechanism fidelity. The model cannot
   capture situations where governance decisions themselves affect
   whether a threshold-quality initiative realizes its
   transformational potential — for instance, through post-completion
   scaling execution, competitive timing, or complementary
   investments. The `is_major_win` flag is determined entirely by the
   latent quality draw at generation and the fixed threshold; it is
   not a function of governance actions. This means the study
   measures governance's ability to surface and persist with
   threshold-quality initiatives, not its ability to convert
   promising initiatives into actual breakthroughs.

6. **Cross-family independence.** The three environment families are
   defined independently. In reality, organizations face correlated
   opportunity landscapes. Cross-family correlation is out of scope
   for v1. Governance findings should be interpreted within each
   family's environment specification, not as claims about
   organizations that face joint opportunity distributions spanning
   multiple family definitions. The correlation structure of
   real-world opportunity landscapes — where industry disruption may
   simultaneously affect the availability and characteristics of
   both exploratory and incremental opportunities — is not modeled.

### Business
A responsible reader should understand where the evidence is strong, where it
is approximate, and where the study is making structural assumptions rather
than empirical claims.

1. **Breakthrough incidence is grounded in a range, not a precise number.**
   The external evidence supports a major-win rate of roughly 0.3–4 percent
   among completed exploratory initiatives. That range spans an order of
   magnitude. The three organizational environments are designed to cover
   the low, middle, and high end of this range, but the specific parameters
   are not fitted to empirical distributions from any particular
   organization or industry. Findings that hold across all three
   environments are robust to this uncertainty. Findings that hold in only
   one should be treated with appropriate caution.

2. **Duration evidence measures time to resolution, not time to value.**
   The external evidence anchors how long exploratory initiatives take to
   reach stable resolution — the point where the organization can
   confidently assess success or failure at scale. The model's completion
   clock is a simpler mechanical concept: when the work is done. The
   mapping between these is approximate. In real organizations, resolution
   often comes after completion (the product launched, but did it succeed at
   scale?) or before it (the strategic verdict became clear before the work
   was finished). The model collapses these into a single event.

3. **Non-exploratory initiative parameters are archetypes, not empirical
   fits.** The flywheel, enabler, and quick-win parameters are designed to
   faithfully represent the structural characteristics of each type rather
   than fitted to data from any specific organization. This is acceptable
   because the study's governance findings are relative — every regime
   faces the same parameters — but it means that the absolute value levels
   in the simulation output are not interpretable as claims about any real
   organization's numbers. The study does not say "your flywheels are worth
   X dollars." It says how governance choices affect the relative
   accumulation of different value types.

4. **Parameters were set by forward reasoning, not by fitting to target
   outputs.** The study did not work backward from desired output
   distributions to choose parameters. Instead, parameters were set by
   reasoning forward from evidence and structural logic. This avoids
   overfitting — the risk of tuning parameters until the output looks right
   for reasons that have nothing to do with whether the model is correct —
   but it means that observed simulation outputs may not match a
   practitioner's intuitive expectations about absolute levels. Relative
   comparisons between regimes are unaffected.

5. **The definition of "major win" is a simplification.** In real
   organizations, transformational breakthroughs are rich, multi-dimensional
   phenomena: they involve market timing, organizational readiness,
   competitive dynamics, and scale-up capability, not just the underlying
   quality of the idea. The model reduces this to a single quality threshold
   — an initiative either crosses it or it does not. This is a deliberate
   simplification that preserves the study's ability to ask the governance
   question (does patience affect breakthrough discovery?) without requiring
   a full model of everything that makes breakthroughs happen. The tradeoff
   is that the model cannot capture situations where governance decisions
   themselves affect whether a threshold-quality initiative actually becomes
   a breakthrough — for instance, through superior scaling execution or
   market timing.

6. **The three organizational environments are independent of each other.**
   The balanced incumbent, short-cycle throughput, and discovery-heavy
   environments are defined independently. In reality, the opportunity
   landscape an organization faces is correlated across initiative types —
   an industry undergoing rapid disruption probably offers both more
   exploratory opportunities and different flywheel dynamics than a stable
   industry. Cross-environment correlation is out of scope for this version
   of the study. Governance findings should be interpreted within each
   environment, not as claims about organizations that face blended
   conditions across environment types.
