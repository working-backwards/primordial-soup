# Generator Validity Memo

## Purpose


### Academic
This document records the empirical calibration evidence and validation
criteria used to define the named environment families in the Primordial
Soup study. It preserves the link between external evidence and the
generator-level parameter choices so that future researchers can assess
whether the families remain well-calibrated as new evidence becomes
available.

The environment families are defined in `src/primordial_soup/presets.py`
and validated using `scripts/validate_environment_families.py`.

The study defines three named environment families —
`balanced_incumbent`, `short_cycle_throughput`, and `discovery_heavy` —
each specifying a distinct opportunity landscape parameterized by the
composition of the initiative pool and the distributional properties of
right-tail initiatives. The families differ in three respects: the count
of right-tail initiatives in the 200-initiative pool, the Beta
distribution governing right-tail `latent_quality`, and the
`true_duration_range` and `planned_duration_range` for right-tail
initiatives. All other generator parameters — quality distributions,
durations, residual rates, capability contribution scales, and signal
noise for flywheel, enabler, and quick-win families — are held constant
across environment families. This isolation ensures that cross-family
governance comparisons reflect differences in the right-tail opportunity
landscape, not differences in non-exploratory initiative characteristics.

The document is organized as a calibration narrative. Section 1 records
the major-win incidence calibration, including the v2 structural
collapse (63-run baseline campaign, zero major wins across all regimes
and families) that necessitated recalibration. Section 2 records the
right-tail duration structure and its interaction with the 313-tick
horizon. Section 3 defines the three families with their validation
criteria. Section 4 states the procedural discipline that prevents
post-hoc parameter selection from contaminating the governance
comparison.

### Business
This document records why each organizational environment in the study is parameterized the way it is, what external evidence supports those choices, and what criteria must hold before an environment is considered valid for governance comparison.

The study defines three named organizational environments — balanced incumbent, short-cycle throughput, and discovery-heavy — each representing a distinct opportunity landscape that a real organization might face. These environments differ in how many exploratory initiatives are available, how often those initiatives turn out to be transformational, and how long they take to reach resolution. Everything else — the characteristics of flywheel, enabler, and quick-win initiatives — is held constant across environments so that findings can be attributed to the opportunity landscape and governance response, not to differences in the non-exploratory initiative mix.

This document preserves the chain of reasoning from external evidence to specific parameter choices so that a reader can assess whether the environments remain well-grounded as new evidence becomes available. It also records the calibration history — including a significant early failure where the original parameters made transformational breakthroughs structurally impossible — so that the rationale for the current parameters is transparent and auditable.

### Recalibration note (March 2026)

A March 2026 recalibration changed workforce scale (8 total labor with
uniform size-1 teams to 210 total labor with mixed team sizes 5/10/20),
pool composition (balanced_incumbent right-tails reduced from 40 to 20,
flywheels increased from 40 to 70; short_cycle flywheels to 50,
right-tails to 16; discovery_heavy flywheels to 40), flywheel duration
tightened (20-60 to 25-45 ticks), initiative team sizes introduced
(5-15 range by family), and portfolio mix targets activated. Right-tail
calibration (Beta distributions, thresholds, duration ranges) was
unchanged. See `docs/design/calibration_plan.md` for full rationale.

## 1. Major-Win Incidence (`is_major_win`)


### Academic
#### Canonical generation rule

At generation time, each right-tail initiative receives an immutable
`is_major_win` flag determined by a threshold rule:

$$
\text{is\_major\_win} = (\text{latent\_quality} \geq q_{\text{major\_win\_threshold}})
$$

where `latent_quality` is drawn from a family-specific Beta distribution
and $q_{\text{major\_win\_threshold}}$ is a family-level parameter. The flag is
hidden from governance; governance can only discover whether an
initiative was a major win by pursuing it to completion.

This information asymmetry is the core experimental structure for the
major-win discovery outcome family. Governance must choose how long to
persist with each right-tail initiative — how much attention to allocate,
how many staffed ticks to tolerate before applying a stopping rule —
without observing whether the initiative's `latent_quality` exceeds
$q_{\text{major\_win\_threshold}}$. The study measures whether governance patience
and attention allocation affect the rate at which threshold-quality
initiatives are surfaced, conditional on an opportunity landscape that
produces them at a known but unobservable rate.

#### Calibration evidence

Subsequent calibration research drew on three independent evidence
angles: practitioner and empirical work on incumbent new-business
creation, evidence on internal venture and exploratory-innovation
outcomes, and high-measurement long-shot analogues such as
blockbuster-stage outcome distributions in domains with observable
funnels. Across those lenses, company-level breakthrough outcomes
appear to be rare but non-zero among completed exploratory efforts,
supporting a low / mid / high working band of approximately
**0.3% / 1.5% / 4%** for major wins among completed right-tail
initiatives. The same evidence also supports a business-facing duration
anchor of roughly 3 / 5 / 10 years to stable resolution for right-tail
initiatives in incumbent firms.

The evidence base defines "major win" as a governance-triggering scale
event — an outcome of sufficient magnitude to force resource
reallocation or strategic redirection decisions — not merely a positive
return on investment. This definition aligns with the study's focus on
governance's ability to surface transformational outcomes rather than to
accumulate incremental returns.

The systematic parameter analysis identified $\text{Beta}(0.8, 2.0)$ with
$q_{\text{major\_win\_threshold}} = 0.80$ as the distributional parameterization
that produces approximately 3% major-win incidence among generated
right-tail initiatives — the mid-case anchor within the empirically
supported range. Corporate venturing evidence, when filtered for
outcomes at the scale this study models, corroborates the 1–3% band.

These values are used as family-level calibration anchors rather than
exact truths. The families are designed to span the defensible range
rather than to pin a single point estimate.

#### Calibration history

**2026-03-12 (v1 — repaired validation baseline):** $\text{Beta}(2.0, 3.0)$ with
$q_{\text{major\_win\_threshold}} = 0.5$, yielding ~31% major-win rate. A mechanism-
reactivation repair after an earlier zero-major-win failure. Never
intended as the canonical study baseline.

**2026-03-15 (v2 — named environment families):** Three families with
family-specific distributions: $\text{Beta}(1.4, 6.6)/0.82$, $\text{Beta}(1.2, 7.0)/0.85$,
$\text{Beta}(1.7, 5.8)/0.78$. Grounded by external calibration research. However,
a 63-run baseline campaign showed zero major wins across all archetypes
and families, revealing that $P(q \geq \text{threshold})$ was near zero for all
three families (~0.003% for balanced_incumbent). This was a generator-
collapse artifact, not a governance finding.

The consequence for the experimental design was that the policy
comparison was degenerate with respect to the major-win discovery
outcome family. When $P(\text{is\_major\_win} = \text{true}) \approx 0$ across all seeds, the
major-win discovery rate is zero under every governance policy, and the
experiment cannot discriminate between patient and impatient regimes on
this dimension. The policy space, observation model, and stopping logic
were all functioning correctly — the experiment was operating in a
parameter region where one of the three primary outcome families was
structurally unreachable. Expected major-win-eligible initiatives per
40-initiative pool: ~0.001. Approximately 900 seeds would be required
before a single eligible initiative appeared by chance.

**2026-03-17 (v3 — current, post-Project 3 recalibration):** Unified
threshold at 0.80 with recalibrated Beta distributions: $\text{Beta}(0.8, 2.0)$
for balanced (~3%), $\text{Beta}(0.6, 2.5)$ for short-cycle (~1%), $\text{Beta}(1.2, 1.8)$
for discovery (~5–8%). Duration ranges adjusted to reflect multi-year
exploratory timelines. See `docs/design/calibration_note.md` for the
full evidence chain and parameter derivation.

The unified threshold is a deliberate experimental design choice that
isolates the source of cross-family variation. All three families share
$q_{\text{major\_win\_threshold}} = 0.80$, so `is_major_win` has identical
semantics everywhere: it flags the same quality boundary. What varies
across families is the Beta shape and therefore $P(q \geq 0.80)$. This
means cross-family governance comparisons test whether findings are
robust to different tail probabilities under a common definition of
the threshold event, rather than confounding distributional variation
with definitional variation. Families differ in how the latent quality
mass is distributed relative to a fixed decision boundary, not in the
boundary itself.

### Business
#### How transformational breakthroughs are determined

At the moment each exploratory initiative is created, the simulation determines whether it has the potential to be a major win — a genuinely transformational breakthrough. This determination is based on the initiative's true underlying quality: if it exceeds a threshold, the initiative is flagged as a major win. If it falls short, it is not. The flag is set at creation and never changes.

Critically, governance cannot see this flag. Leadership has no way of knowing at the outset — or at any point during execution — whether a given exploratory initiative is a major win. They can only discover this by pursuing the initiative to completion. This is the fundamental asymmetry the study is designed to explore: governance must decide how long to persist with uncertain exploratory work without knowing which initiatives, if any, harbor transformational potential.

#### What the external evidence says

The calibration research drew on three independent evidence sources to establish how often exploratory initiatives actually produce transformational outcomes in real organizations:

1. **Research on new-business creation in large incumbent firms.** Studies of company-level breakthrough outcomes among completed exploratory initiatives show an incidence of roughly 0.3–4 percent, with a midpoint around 1.5 percent. Time from launch to stable resolution — meaning the point where the organization can confidently assess whether the initiative has succeeded at scale — ranges from 3 to 10 years, with a midpoint around 5 years. "Major win" in this evidence means a governance-scale event: a breakthrough large enough to trigger organizational decisions about scaling, not merely a positive financial return.

2. **Corporate venturing and exploratory-innovation evidence.** Independent evidence from structured corporate venture programs corroborates the rare-but-nonzero range. When filtered for outcomes at the scale this study models — not small successes, but outcomes that fundamentally change the organization's trajectory — hit rates align with the 1–3 percent band.

3. **Systematic parameter analysis.** A formal evaluation of how different quality distributions interact with the major-win threshold to produce specific breakthrough incidence rates. This analysis identified the parameter combination that produces approximately 3 percent major-win incidence — squarely in the middle of the empirically supported range.

These values are used as calibration anchors for the three organizational environments rather than as exact truths. The environments are designed to span the defensible range rather than to pin a single point estimate.

#### Calibration history — and why it matters

The current parameters are the result of three iterations, the middle one of which revealed a fundamental modeling failure.

**First iteration (March 12, 2026): Mechanism repair.** An earlier version of the model had failed to produce any major wins at all. The first fix reactivated the mechanism by setting parameters that produced a roughly 31 percent major-win rate — far too high to be realistic, but sufficient to confirm that the simulation machinery was working. This was never intended as the study baseline; it was a diagnostic step.

**Second iteration (March 15, 2026): Evidence-grounded parameters — and structural collapse.** Three organizational environments were defined with parameters grounded in external calibration research. Each environment received its own quality distribution and major-win threshold combination, chosen to reflect different opportunity landscapes. A 63-run baseline campaign was then conducted across all governance regimes and all three environments.

The result: zero major wins. Not a single transformational breakthrough surfaced in any environment, under any governance approach, in any of those 63 runs.

This was not a finding about governance. It was a parameter failure. The quality distributions had been set so conservatively — and the thresholds so demandingly — that the probability of any single exploratory initiative reaching major-win quality was approximately 0.003 percent. In a pool of 40 exploratory initiatives, fewer than one in a thousand simulations would contain even a single eligible initiative. The study was faithfully modeling the governance question in an environment where the phenomenon it existed to investigate was structurally impossible.

**Third iteration (March 17, 2026): Current parameters.** The recalibration unified all three environments around a single quality threshold for major-win eligibility, with environment-specific quality distributions tuned to produce different incidence rates spanning the empirically supported range:

| Environment | Major-win incidence | Design intent |
|---|---:|---|
| **Balanced incumbent** | ~3% | Mid-case: a typical large organization with a normal mix of exploratory bets |
| **Short-cycle throughput** | ~1% | Scarce major wins: an environment where transformational outcomes are rare and most exploratory work yields modest results |
| **Discovery-heavy** | ~5–8% | Rich major wins: an environment with a richer vein of transformational opportunity |

The decision to use a single, unified quality threshold across all three environments — rather than varying both the threshold and the quality distribution — is a deliberate design choice. It isolates the experimental variation: environments differ in how the underlying quality of exploratory initiatives is distributed relative to a fixed definition of "transformational," not in the definition itself. This means that when the study compares governance findings across environments, the comparison is clean. A major win means the same thing everywhere; what changes is how often the opportunity landscape produces initiatives capable of reaching that bar.

Duration ranges were also adjusted to reflect multi-year exploratory timelines grounded in the external evidence. The full derivation is recorded in the calibration note.

## 2. Right-Tail Duration Structure


### Academic
#### Canonical posture

Right-tail initiatives represent exploratory efforts whose resolution
timeline is measured in years, not months. The generator assigns
`true_duration_ticks` from a family-specific range that is materially
longer than quick-win or enabler durations.

#### Criticality of duration calibration

Duration calibration is as consequential as quality calibration for the
validity of the major-win discovery comparison. A necessary condition
for any governance regime to surface a major win is that at least some
right-tail initiatives complete within the simulation horizon. Formally:

$$
\text{completion is feasible} \iff \text{true\_duration\_ticks} \leq T - t_{\text{staff}}
$$

where $T = 313$ is the horizon length in ticks and $t_{\text{staff}}$ is the tick
at which the initiative is first staffed (assuming continuous staffing
thereafter; interruptions extend the effective completion time). If the
`true_duration_range` places all right-tail initiatives above this
bound, no governance policy can produce a non-zero major-win discovery
rate regardless of patience, and the policy comparison collapses on
this dimension — analogous to the quality-side collapse diagnosed in
the v2 calibration failure.

The duration ranges must therefore satisfy two competing constraints:
long enough to represent multi-year exploratory timescales consistent
with external evidence, and short enough that patient governance has a
feasible completion path within the horizon.

#### Calibration evidence

External calibration research supports a business-facing duration
anchor of approximately **3 / 5 / 10 years** for right-tail initiatives
in incumbent firms when measured to stable resolution rather than full
strategic materiality. For the current 313-week (six-year) study horizon,
family-specific tick distributions are therefore lengthened materially
relative to the original repaired baseline (which used
`true_duration_range=(20, 80)`) while still allowing some completions
under patient governance.

Family-specific duration ranges translate the evidence anchors as
follows:

| Family | `true_duration_range` (ticks) | Calendar equivalent | `planned_duration_range` (ticks) | Design intent |
|---|---|---|---|---|
| `balanced_incumbent` | (104, 182) | 2.0–3.5 years | (125, 220) | Mid-case |
| `short_cycle_throughput` | (80, 156) | 1.5–3.0 years | (96, 187) | Shorter innovation cycles |
| `discovery_heavy` | (130, 260) | 2.5–5.0 years | (156, 312) | Longer exploration horizons |

`planned_duration_range` is set at approximately $1.2\times$ the
`true_duration_range` (rounded to integer ticks), reflecting the
systematic optimistic bias in planning estimates for exploratory work
where the scope of required learning is itself uncertain at the outset.
This produces `latent_execution_fidelity` values
($\text{planned\_duration\_ticks} / \text{true\_duration\_ticks}$) clustered near 0.83
for right-tail initiatives, meaning the execution belief $c_{\text{exec},t}$
will converge toward a value below 1.0 even for initiatives proceeding
at their true pace. The $1.2\times$ multiplier is a structural assumption,
not an empirically fitted value.

The implication for the 313-tick horizon is that many right-tail
initiatives will not complete within the simulation window, especially
under less patient governance regimes. This is intentional: the study
measures governance's ability to persist through uncertainty, not
whether all right-tail initiatives conveniently resolve within the
observation period.

The duration ranges are calibrated to create a genuine policy
discrimination region. Patient governance — characterized by lower
`confidence_decline_threshold`, wider `stagnation_window_staffed_ticks`,
and sustained attention allocation — has a feasible completion path for
right-tail initiatives within the horizon. Impatient governance faces a
genuine tradeoff between early termination (forfeiting the option value
of a potentially threshold-quality initiative) and continued investment
under ambiguous signals (consuming staffed ticks and attention that
could be allocated to higher-certainty initiative families). If
durations were shortened to ensure completion under all regimes, the
policy comparison would lose discriminative power on the patience
dimension — the study's primary experimental axis.

<!-- specification-gap: the minimum patience configuration required for a right-tail initiative at the upper end of each family's duration range to have a non-trivial completion probability within the horizon is not formally characterized — specifically, how confidence_decline_threshold, stagnation_window_staffed_ticks, and attention allocation interact with the belief dynamics to determine whether governance terminates before completion -->

### Business
#### Why duration matters as much as quality

Even if the opportunity landscape contains initiatives with transformational potential, governance can only surface those breakthroughs if it persists long enough for the work to reach completion. Duration calibration is therefore just as consequential as quality calibration: if exploratory initiatives are parameterized to take longer than the study's six-year horizon allows, no governance regime can discover major wins regardless of how patient it is, and the study's central question becomes unanswerable.

#### What the evidence supports

Exploratory initiatives represent efforts whose resolution timeline is measured in years, not months. The external calibration research supports a business-facing duration anchor of approximately **3 / 5 / 10 years** to stable resolution for right-tail initiatives in incumbent firms — where "stable resolution" means the point at which the organization can confidently assess whether the initiative has succeeded or failed at scale, not merely whether initial milestones have been hit.

Each organizational environment translates this evidence into a specific duration range:

| Environment | Actual duration range | Design intent |
|---|---|---|
| **Balanced incumbent** | 2.0–3.5 years | Mid-case |
| **Short-cycle throughput** | 1.5–3.0 years | Shorter innovation cycles, faster-moving market |
| **Discovery-heavy** | 2.5–5.0 years | Longer exploration horizons, deeper uncertainty |

These ranges are materially longer than the durations used in the initial mechanism-repair iteration (which used roughly 5–18 months). The lengthening reflects the external evidence that exploratory work in incumbent organizations operates on multi-year timescales, and the study must respect those timescales to produce findings relevant to real governance decisions.

Planning estimates are set at approximately 1.2 times the actual duration for each environment, reflecting the systematic optimism typical of exploratory work planning. When a team says an exploratory initiative will take two years, it will more likely take two and a half. This is not a flaw in planning — it is a well-documented characteristic of work where the scope of what needs to be learned is itself uncertain at the outset.

#### The deliberate tension with the study horizon

The study's six-year horizon means that many exploratory initiatives will not complete within the simulation window — especially under governance regimes that are less willing to persist through ambiguity, or in the discovery-heavy environment where exploratory durations extend to five years and beyond.

This is intentional. The study is designed to measure governance's ability to persist through uncertainty, not to guarantee that all exploratory initiatives conveniently resolve within the observation period. The duration ranges are calibrated to create a genuine governance tradeoff: patient governance has a feasible path to right-tail completion within the horizon, while impatient governance faces a real choice between cutting losses early and continuing to invest under ambiguous signals. If durations were shortened to ensure comfortable completion under all regimes, the study would be unable to distinguish between patience and impatience — which is precisely the distinction it exists to investigate.

## 3. Named Environment Families


### Academic
#### Family definitions

| Parameter | `balanced_incumbent` | `short_cycle_throughput` | `discovery_heavy` |
|---|---|---|---|
| Right-tail count | 20 | 16 | 56 |
| Quality distribution | $\text{Beta}(0.8, 2.0)$ | $\text{Beta}(0.6, 2.5)$ | $\text{Beta}(1.2, 1.8)$ |
| $q_{\text{major\_win\_threshold}}$ | 0.80 | 0.80 | 0.80 |
| $P(q \geq \text{threshold})$ | ~3% | ~1% | ~5–8% |
| `true_duration_range` | (104, 182) | (80, 156) | (130, 260) |
| `planned_duration_range` | (125, 220) | (96, 187) | (156, 312) |
| Quick-win count | 80 | 104 | 74 |
| Flywheel count | 70 | 50 | 40 |
| Enabler count | 30 | 30 | 30 |
| Total pool | 200 | 200 | 200 |

Non-right-tail type parameters (quality distributions, durations,
residual rates, capability scales) are identical across all three
families. Only counts and right-tail distributional parameters vary.

This isolation ensures that cross-family governance comparisons reflect
differences in the right-tail opportunity landscape — the count,
distributional shape, and duration structure of exploratory initiatives —
rather than differences in non-exploratory initiative characteristics.
Any governance finding that replicates across all three families is
therefore robust to the right-tail opportunity landscape within the
range spanned by the family definitions.

#### Design rationale

- **balanced_incumbent**: Mid-case environment. Multi-year right-tail
  durations. The canonical baseline for governance comparisons.
- **short_cycle_throughput**: Mature, quick-win-heavy world. Lower
  right-tail representation and shorter right-tail durations. Fewer
  exploratory bets, more predictable throughput work.
- **discovery_heavy**: Strong-builder / favorable-domain world. Higher
  right-tail representation and longer exploratory durations.
  Governance patience matters more in this environment.

**Experimental function of each family.** The three families are not
merely alternative parameterizations; they define distinct regions of
the opportunity landscape in which the governance comparison operates:

- `balanced_incumbent` is the primary comparison surface. Governance
  findings established in this family take precedence. The other two
  families serve as robustness checks testing whether those findings
  survive under alternative opportunity conditions.

- `short_cycle_throughput` tests whether governance conclusions that
  hold in the baseline survive when the opportunity cost of exploratory
  persistence is elevated. The pool is dominated by quick-win
  initiatives (104 of 200) with short durations and moderate-to-high
  quality. Right-tail representation is lower (16 vs. 20), with
  shorter duration ranges and ~1% major-win incidence. In this family,
  each staffed tick allocated to a right-tail initiative displaces a
  quick-win initiative with higher expected lump value per tick. A
  governance regime that persists with right-tail work in this
  environment pays a higher opportunity cost than the same regime in
  `balanced_incumbent`.

- `discovery_heavy` tests whether governance patience produces
  materially larger treatment effects when the opportunity landscape
  is favorable to exploration. Right-tail representation is higher (56
  vs. 20), with longer duration ranges and ~5–8% major-win incidence.
  If patient governance does not produce materially different outcomes
  in this family — which is specifically parameterized to reward
  persistence through ambiguity — that would bound the potential
  returns to governance patience under favorable conditions.

#### Validation criteria

A family is not canonical until the following conditions hold across
the three named governance archetypes for a modest seed panel:

1. **No pool exhaustion** — the pool of 200 initiatives is not
   exhausted before the end of the 313-tick horizon in any run.
2. **Non-zero major-win activation** — at least some right-tail
   major wins are surfaced across the seed panel.
3. **Low-single-digit conditional major-win rate** — for
   `balanced_incumbent`, the observed major-win rate among completed
   right-tail initiatives should be in the approximate range
   0.5%--5%. This is intentionally wider than the research midpoint
   because the simulator uses a simplified thresholded mechanism
   rather than a richer event model.
4. **Reasonable idle capacity** — governance regimes are not
   starved for work or flooded with more initiatives than they
   can meaningfully evaluate.

These criteria are checked by
`scripts/validate_environment_families.py`.

The v2 baseline campaign (63 runs, zero major wins across all regimes
and families) demonstrated that criterion 2 cannot be assumed from the
generator parameterization alone; it must be verified empirically. The
v2 families satisfied all formal parameter requirements but produced
$P(\text{is\_major\_win} = \text{true}) \approx 0$, rendering the policy comparison degenerate
on the major-win dimension.

Criterion 3 uses a wider tolerance band (0.5%–5%) than the external
evidence midpoint (~1.5%) because the simulator's binary threshold
mechanism is a simplified representation of a richer real-world
phenomenon. The criterion ensures that the model's major-win incidence
is within the defensible range without demanding precision that the
threshold mechanism cannot deliver.

Criterion 1 prevents a specific confound: if a governance regime
exhausts the initiative pool before the horizon, subsequent governance
decisions are constrained by supply rather than by policy, and the
regime's apparent performance reflects opportunity depletion rather
than governance quality.

<!-- specification-gap: criterion 4 ("reasonable idle capacity") lacks a formal definition — no threshold or metric is specified for what constitutes "starved" or "flooded" in terms of team utilization rates, idle tick fractions, or initiative queue depth relative to available teams -->

These four criteria are necessary conditions for the governance
comparison to be informative — they ensure that the experiment operates
in the parameter region where the three primary outcome families are
reachable and the policy space is non-degenerate. They are not
sufficient conditions for the parameter choices to be correct: a family
may satisfy all four criteria while producing dynamics that are
unrealistic in ways the criteria do not capture.

### Business
#### What the three environments represent

The study defines three organizational environments, each representing a distinct opportunity landscape that a real organization might face. They differ in the composition of the initiative pool — specifically, how many exploratory versus predictable-throughput opportunities are available — and in the characteristics of the exploratory work itself: how often it produces transformational outcomes and how long it takes to reach resolution.

Everything outside the exploratory initiative parameters is held constant across all three environments. Flywheel, enabler, and quick-win initiatives have identical characteristics regardless of which environment they appear in. Only the count of each initiative type and the right-tail distributional parameters vary. This design choice ensures that when the study compares governance findings across environments, the comparison isolates the effect of the opportunity landscape — not differences in how non-exploratory work behaves.

#### Environment composition

| | Balanced incumbent | Short-cycle throughput | Discovery-heavy |
|---|---|---|---|
| **Quick-win initiatives** | 80 | 104 | 74 |
| **Flywheel initiatives** | 70 | 50 | 40 |
| **Enabler initiatives** | 30 | 30 | 30 |
| **Right-tail initiatives** | 20 | 16 | 56 |
| **Total pool** | 200 | 200 | 200 |
| **Major-win incidence** | ~3% | ~1% | ~5–8% |
| **Exploratory duration range** | 2.0–3.5 years | 1.5–3.0 years | 2.5–5.0 years |
| **Planning estimate range** | 2.4–4.2 years | 1.8–3.6 years | 3.0–6.0 years |

All three environments contain 200 total initiatives. The pool size is held constant so that governance regimes face the same total volume of work; what changes is the mix.

#### What each environment is designed to test

**Balanced incumbent** is the canonical baseline. It represents a typical large organization with a normal mix of initiative types: substantial predictable-throughput work, a meaningful allocation of exploratory bets, and a mid-case rate of transformational opportunity. Multi-year exploratory durations. Most governance comparisons should be grounded against this environment first. Findings that hold here are the most broadly applicable.

**Short-cycle throughput** represents a mature, execution-focused organization operating in a market where most value comes from predictable, well-understood opportunities. The initiative pool is dominated by quick wins. Exploratory work is less represented (16 right-tail initiatives versus 20 in the baseline), with shorter innovation cycles and a lower rate of transformational outcomes (~1%). This environment tests whether governance conclusions that hold in the baseline survive in a world where exploratory work is scarcer and the opportunity cost of patience is higher — because every month spent on an uncertain exploratory initiative is a month not spent on a predictable quick win that was almost certainly going to succeed.

**Discovery-heavy** represents an organization operating in a domain with a rich vein of transformational opportunity — perhaps during a platform shift, market disruption, or technology transition. The initiative pool has significantly more exploratory work (56 right-tail initiatives versus 20 in the baseline), with longer durations and a higher rate of transformational outcomes (~5–8%). This environment tests whether governance patience produces materially different outcomes when the opportunity landscape is genuinely favorable to exploration. If patient governance does not outperform impatient governance even here — in an environment specifically designed to reward persistence through ambiguity — that would be a meaningful finding about the limits of organizational patience.

#### What must be true before an environment is considered valid

An organizational environment is not ready for governance comparison until the following conditions hold across the study's governance archetypes for a modest panel of simulation runs:

1. **The initiative pool does not run out.** No governance regime exhausts the pool of 200 initiatives before the end of the six-year horizon. If the pool runs dry, governance appears to underperform not because of its decisions but because it ran out of opportunities to pursue — a confound, not a finding.

2. **Transformational breakthroughs are possible.** At least some right-tail major wins are surfaced across the panel. The 63-run calibration failure — zero major wins across all regimes and all environments — demonstrated that this condition cannot be assumed; it must be verified. If the environment cannot produce the phenomenon the study exists to investigate, the governance comparison is degenerate on the major-win dimension.

3. **Breakthrough rates are in the empirically supported range.** For the balanced incumbent environment, the observed major-win rate among completed exploratory initiatives should fall in the approximate range of 0.5–5 percent. This range is intentionally wider than the external evidence midpoint because the simulation uses a simplified threshold mechanism rather than a richer model of how breakthroughs emerge. The criterion ensures that the model's breakthrough incidence is in the right neighborhood without demanding false precision.

4. **Governance regimes are neither starved for work nor overwhelmed.** The initiative pool and governance capacity should be balanced so that regimes face genuine allocation decisions — they have more opportunities than they can staff simultaneously, but not so many that most initiatives sit permanently unattended. Idle capacity that is too high or too low distorts the governance comparison by making the resource allocation problem trivially easy or structurally impossible.

These validation criteria are checked programmatically before any comparative governance analysis begins. They are necessary conditions for the governance comparison to be informative, not sufficient conditions for the parameter choices to be correct.

<!-- specification-gap: the Academic version references specific code paths (presets.py, validate_environment_families.py) that implement these families and validation criteria; the Business version does not specify where or how validation is operationalized, which may matter for a reader who wants to verify that these criteria were actually checked -->

## 4. What These Families Are Not


### Academic
The named families are not optimized configurations. They are
**plausible anchored environments** designed to span a defensible
range of organizational worlds. The exact Beta parameters and
thresholds are implementation starting points grounded by external
evidence, not fitted truths.

The protection against circularity is procedural: define families,
validate them against the criteria above, then finalize them before
the comparative governance campaign begins. Parameter choices should
not be adjusted after seeing governance results.

The procedural sequence is stated explicitly because violation would
compromise the entire comparative structure:

1. Choose family parameters based on external evidence and structural
   logic.
2. Verify that the validation criteria (Section 3) hold across
   governance archetypes for a modest seed panel.
3. Finalize the family definitions.
4. Conduct the comparative governance campaign.

Steps 1–3 must complete before step 4 begins. If parameters were
adjusted after observing governance results — selecting the conditions
under which preferred governance conclusions hold rather than testing
whether those conclusions are robust to the conditions the evidence
supports — the experiment would exhibit post-hoc parameter selection
bias, invalidating the comparative findings. The families define the
stochastic environment; governance operates within that environment.
The two must not be allowed to contaminate each other.

### Business
The three organizational environments are not optimized configurations. They are not designed to maximize any outcome or to produce the most interesting-looking governance findings. They are **plausible, evidence-anchored environments** designed to span a defensible range of organizational worlds that real companies might face.

The specific parameters — the quality distributions, the breakthrough thresholds, the duration ranges, the initiative mix — are implementation starting points grounded in external evidence, not fitted truths. They represent the study team's best judgment about where these values should sit given the available evidence, not a claim that these are the correct values for any specific organization or industry.

The protection against circularity is procedural, and it matters enough to state explicitly. The environments were defined and validated against the criteria described above **before** any comparative governance analysis was conducted. The sequence is: choose the parameters based on evidence, verify that the validation criteria hold, freeze the environments, and only then begin the governance comparison. Parameter choices are never adjusted after seeing governance results. If they were — if the study team looked at governance findings, didn't like what they saw, and went back to adjust the environment parameters — the entire comparative structure would be compromised. The study would be selecting the conditions under which its preferred governance conclusions hold, rather than testing whether those conclusions are robust to the conditions the evidence supports.

This procedural discipline is what gives the governance findings their credibility. The environments define the world. Governance must operate within that world. The two are never allowed to contaminate each other.
