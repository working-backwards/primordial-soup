# Repo Improvement Plan (2026-06-10)

## What we are solving, and why

The study asks: under what governance structures do organizations
discover, invest in, and sustain the mix of work that produces
long-run value? The 2026-06-09 evaluation found that the current
simulator cannot yet answer that question, for three distinct
reasons. Every phase in this plan exists to remove one of them.

**Problem 1: results are not attributable to governance.** The three
archetypes differ on every threshold, patience window, and portfolio
target simultaneously, so when outcomes differ we cannot say which
governance choice caused it. Meanwhile two mechanical artifacts —
greedy intake with no belief floor, and an infinite constant-quality
supply of right-tail re-attempts — dominate the outcome variance, so
much of what the reports show is artifact, not governance. The plan
fixes this by building the smallest model that contains the research
question (Phase 1), then layering mechanisms back one rung at a time
so each one's effect is measured in isolation (Phase 2).

**Problem 2: the simulated organization does not face the decision
the study is about.** The screening signal is informative enough that
major-win-eligible initiatives enter at belief ~0.82 while everything
else enters at ~0.28 — governance never has to kill anything that
might have been a breakthrough (verified: 0 of 33 eligible right-tails
stopped). The central governance dilemma — stop or continue under
genuine uncertainty — never occurs. Phase 1.3 recalibrates screening
so that dilemma exists from the smallest model up.

**Problem 3: the value ledger is not believable over a long
horizon.** There is no time-discounting, so 92% of value arriving as
late residual streams is mathematically correct but strategically
meaningless, and roughly half the eventual major wins are censored
in-flight at the horizon. Phase 3.1 adds a discounted ledger so
long-run claims survive contact with a CFO or a referee.

The plan follows the build-simple-first principle: the prior draft of
this plan ordered full-model repairs first, which repeated the
original mistake of building the complex model before exploiting a
simple one. This version makes the model ladder the spine. At every
stopping point we hold a working model with a defensible answer, and
each new rung is checked against the previous one.

## Branch and verification policy

**All work in this plan happens on a dedicated branch, not on
`main`.**

- Create `feature-model-ladder` off `main` before any change.
- One logical change per commit, design docs updated before code
  (per the Design Revision Process in CLAUDE.md).
- **Merge into `main` only after verification:**
  1. The full pytest suite passes (currently 1055 tests; new
     behavior gets new tests).
  2. The canonical smoke run (`balanced_incumbent_balanced`)
     completes and its headline metrics are compared against the
     pinned pre-change baseline (Phase 0.1). Every delta must be
     explained by an intended change — no unexplained drift.
  3. The rung-comparison table (Phase 2) has been reviewed.
  4. Owner reviews the final headline report and approves the merge.

Pre-change reference numbers (verified 2026-06-09, deterministic):
`balanced_incumbent_balanced`, seeds [42, 43, 44]: avg cumulative
value 3066.74; 17 major wins; 92% residual value share; 12.1% ramp
overhead; 929 right-tail attempts with 33 major-win-eligible, 0
eligible stopped, 16 eligible censored in-flight at horizon. Model 0
reference: Throughput 1228 > Balanced 833 > Exploration 622, zero
major wins.

## Phase 0 — Iteration tooling (the loop must be fast and clear)

Goal: every subsequent change is evaluable with one command ending in
headline metrics plus deltas against a reference. Zero new
dependencies.

- **0.1 Pinned smoke baseline.** Commit the canonical preset's
  expected headline numbers (above) as a reference file. Add a
  `--smoke` mode (or small script) that runs the canonical preset and
  prints pass/drift per metric.
- **0.2 Bundle compare command.** `scripts/compare_bundles.py <A> <B>`
  (or `run_design.py --compare-with <bundle>`): prints headline-metric
  deltas between two bundles, paired by world seed so CRN makes the
  deltas attributable to the change rather than noise.
- **0.3 `--quickstart` wizard on `run_design.py`** (optional, can
  defer): five-question interactive flow that writes a valid YAML and
  offers to run it.

0.1 and 0.2 are the measuring instruments for everything below; do
them first.

## Phase 1 — Build the simple model (M1) and exploit it fully

M1 is the smallest model that contains the actual research question:
governance choosing what to start and what to stop under genuine
uncertainty. It is Model 0 (which exists and has a known answer) plus
hidden quality, screening signals, stop rules, and an intake floor —
and nothing else. No frontier replenishment, no attention, no ramp,
no dependency, no staffing response. Per expert review, those
parameters are *removed* from the first version, not merely deferred,
and return only when understanding of the simpler model justifies
them.

- **1.1 Engine-side intake belief floor.**
  `GovernanceConfig.intake_belief_threshold` per
  `intake_discipline_findings_and_plan.md` Step 1 (authoritative).
  Representation-agnostic and rung-agnostic: it serves M1, every
  later rung, and the existing full-model presets. Governance must be
  able to refuse work it predicts will fail.
- **1.2 Define M1, and settle the representation question
  empirically.** Expert review suggests unbounded
  quality/signal/belief scales (positive and negative, terminate on
  sufficiently negative belief) instead of the current [0, 1] clamp.
  The owner's scope decision cuts against this: the study measures
  whether transformational opportunities are *surfaced*, not their
  magnitude — post-discovery scale-up is out of scope because it is
  governance-invariant (once an opportunity is proven, every regime
  scales it; the governance-relevant variation is upstream of
  revelation). Resolution: (a) write the discovery-boundary scope
  statement into `study_overview.md` first; (b) build M1 in both the
  clamped and an unclamped variant — M1 is the cheapest possible
  place to do this — and diff regime orderings and stop/discovery
  patterns. Match → the clamp is demonstrably innocuous and stays,
  with evidence. Diverge → the representation is load-bearing and
  gets a design decision record before any higher rung is built.
- **1.3 M1 calibration: the hard decision must exist.** Tighten the
  quick-win quality Beta (fewer than ~10% of draws below the intake
  floor — "quick win" should mean well-understood). Widen right-tail
  screening noise so major-win-eligible initiatives are NOT obvious
  at intake (verified problem: eligible enter at belief ~0.82 vs
  ~0.28 for the rest). Target: meaningful belief overlap and a
  nonzero kill-a-gem error rate under at least one archetype,
  counting BOTH forms of the error: false rejects (eligible
  right-tails never staffed — the omission error the intake floor
  creates at the door) and mid-flight false stops (eligible
  right-tails stopped while active). [Criterion revised 2026-06-10:
  M1 measurement showed mid-flight false stops are structurally
  near-impossible under EMA learning with level-threshold stop rules
  — a gem's belief mean-reverts upward toward its high latent quality
  and never crosses the threshold — so the gem-killing error
  concentrates at intake. This is a model property worth reporting,
  not a calibration defect; window/derivative-based stop rules or the
  unclamped representation (1.2 experiment) could restore the
  mid-flight form.]
- **1.4 Reporting fixes (rung-agnostic).** Split right-tail stops
  into first-attempt vs refresh-churn; fix the `ramp_labor_fraction`
  definition/label; document the default per-family initiative counts
  prominently (per expert review, for a stylized model the documented
  defaults and their rationale ARE the calibration record). The
  false-stop metric itself was verified correct on 2026-06-09 — no
  change needed.
- **1.5 Exploit M1.** Run the canonical three-regime comparison;
  run one-lever-at-a-time sweeps (cheap at this scale); add the
  benchmark index policy here if feasible (M1 is where a
  Gittins/Weitzman-style upper bound is most tractable). Record the
  M1 answer in the phase log — it is the standing approximate answer
  everything later is checked against.

## Phase 2 — Ladder up, one mechanism per rung

At each rung, run the canonical comparison and diff headline metrics
and regime ordering against the previous rung (Phase 0.2 tooling). A
rung that changes the answer is load-bearing and must be justified; a
rung that doesn't is a candidate for permanent simplification.
Maintain the rung-by-rung delta table in a tracked doc — it is both
the debugging instrument and the ablation study a referee would
require.

- **2.1 M2 = M1 + frontier replenishment**, with refresh quality
  degradation > 0 and a plausible replenishment rate target (~5–8
  first right-tail attempts/year for a balanced incumbent, not ~50).
  The M2-vs-M1 diff quantifies how much of the full model's behavior
  was churn.
- **2.2 M3 = M2 + executive attention**, in the reduced two-parameter
  form per expert review — `c1 * exp(-c2 * a)`, or `c1 / (1 + a^c2)`
  if the exponential decays too fast — replacing the current
  five-parameter curve. Attention allocation rules differ across
  regimes (concentrated/single-threaded vs spread); attention is the
  study's novel mechanism and is evaluated in isolation on this rung.
- **2.3 Backport into the full model.** Carry validated mechanisms
  and calibrations into the nine full-model presets: intake floor
  (already engine-side from 1.1), refresh degradation, screening
  recalibration, enabled `portfolio_mix_targets` (currently `None`
  everywhere — the lever the study claims to test is off). Ramp,
  dependency, and staffing response return only if the M1–M3 results
  show they are needed to answer the research question.

## Phase 3 — Interpretability upgrades

- **3.1 Discounted-value ledger.** Add an NPV-adjusted value column
  to reports at every rung (reporting-side; the engine stays
  undiscounted). The 92% residual share must be readable against a
  discounted counterpart.
- **3.2 Orthogonalized archetype experiments at full-model scale.**
  Extend the one-lever-at-a-time sweeps from 1.5 to the full model:
  vary one governance dimension at a time against a fixed base, so
  every finding reads "changing X alone did Y."
- **3.3 Benchmark index policy at full-model scale** (if not already
  landed in 1.5): results read "regime X captures N% of attainable
  value."
- **3.4 Statistical power.** Move canonical campaigns to 20–30 seeds;
  report paired-CRN confidence intervals on regime deltas. Reports
  lead with relative statements (regime deltas and rankings), not
  absolute value totals — relative comparisons are what a stylized
  model can credibly support.

## Design corpus updates required

Per the Design Revision Process, each change updates its
authoritative design doc before code. The corpus carries both a
business view (practitioner-facing, primarily `study_overview.md`)
and an academic view (technical specs); every item below states what
each view needs. Where a change touches a structural principle,
`canonical_core.md` review is required.

- **`study_overview.md`** (conceptual authority) — the
  discovery-boundary scope statement (1.2). Business view: "the study
  measures whether your governance surfaces the transformational
  opportunity; once proven, every competent company scales it, so the
  story ends at revelation; attention concentration is how leaning
  into an emerging winner appears in-model." Academic view: the
  truncation is identical across treatments and therefore cannot bias
  the comparison; discovery count is a sufficient statistic for the
  governance question; horizon censoring of in-flight eligible
  initiatives is reported, not hidden.
- **`governance.md`** (technical authority) — the intake floor
  primitive (1.1): semantics, default values per archetype, and its
  position in the decision order. Business view: "an investment
  committee has a bar." Academic view: the floor moves archetypes
  along the omission/commission error axis and must be stated as a
  treatment dimension. Also: clarify portfolio-mix-target semantics
  (soft preference vs hard constraint) — currently ambiguous in both
  views.
- **`initiative_model.md`** (technical authority) — screening-noise
  and quick-win Beta recalibration (1.3); the unclamped M1 variant
  spec for the 1.2 experiment (clearly marked as an experimental
  alternative until decided). Business view: "leaders can size up
  routine work accurately but genuinely cannot tell which moonshots
  will hit." Academic view: signal-to-noise targets stated ex ante
  with the intended belief-overlap property.
- **`dynamic_opportunity_frontier.md`** — refresh degradation > 0 and
  the replenishment rate target (2.1). Business view: "a failed
  moonshot makes the next attempt at the same prize harder, and new
  transformational opportunities are rare." Academic view: stopping
  must carry real option cost or stop-rule comparisons are
  meaningless.
- **`calibration_note.md`** — default per-family counts and their
  rationale (1.4) as the explicit calibration record; for a stylized
  model, experience-grounded defaults are the calibration evidence,
  so they must be stated, not buried in preset code.
- **`analysis_and_experimentation.md`** (supporting) — the model
  ladder as the project's experimentation methodology, including the
  rung-delta table format.
- **`exec_intent_spec.md`** — the attention input mapping when the
  two-parameter form lands (2.2). Business view: hours-per-week of
  executive attention and how it is concentrated. Academic view: the
  functional form and its two parameters.
- **`canonical_core.md`** (core principles) — touched ONLY if the 1.2
  experiment shows the representation is load-bearing and the scale
  changes; that requires evaluating whether controlled cross-regime
  comparison is preserved, with a documented design decision.

## Deferred / out of scope

- **GUI front end** — deferred until the input surface stabilizes
  (post Phase 3). Phase 0.3's wizard covers the immediate usability
  need with zero dependencies.
- Sunk-cost escalation, milestone gates, budget cycles — candidate
  governance mechanisms for a later design revision, not this plan.
- Post-discovery scale-up / variable headcount — out of scope by the
  discovery-boundary decision (see 1.2); revisit only if a future
  study question requires it.

## Phase log

(Record each landed step here: date, commit, headline deltas vs
previous step, decision notes.)

- **2026-06-10 — Phase 0.1 landed.** `scripts/smoke_check.py` +
  pinned `scripts/smoke_baseline.json` (seeds 42/43/44 via the
  canonical YAML preset; mean value 3066.74, major wins 5.7/seed,
  residual share 0.919, ramp 0.121). Finding recorded during
  implementation: `presets.make_balanced_config()` and the
  `balanced_incumbent_balanced.yaml` template resolve to materially
  different configurations (factory path: mean value 5431, 2.3 major
  wins/seed, ramp 0.176). The smoke check guards the YAML path because
  that is what real runs use. The divergence between the two
  "canonical balanced" entry points should be reconciled or documented
  when the full-model presets are revisited in Phase 2.3.
- **2026-06-10 — Phase 1.1 landed (intake belief floor).**
  `GovernanceConfig.intake_belief_threshold` + `passes_intake_floor`
  primitive + filter in `_assign_freed_teams`; preset floors: balanced
  0.35, aggressive_stop_loss 0.50, patient_moonshot 0.20. Smoke
  baseline intentionally rewritten. Canonical-preset deltas (seed
  means, before → after): stops 268 → 10 (refresh churn blocked at
  the door); total value 3067 → 6479 (labor concentrates on
  high-belief flywheels, residual compounds); major wins 5.7 → 0.7
  (the 0.35 floor blocks most right-tail attempts, which enter at
  ~0.28 mean belief); **idle team-ticks 0.3% → ~50%** (the floor
  refuses work and the frontier supplies mostly below-floor
  candidates). Interpretation: the floor works as designed and
  exposes the two known downstream dependencies — baseline value
  accounting for idle labor (intake findings Step 3; currently
  baseline_value_per_tick = 0, so refused work earns nothing) and
  frontier replenishment recalibration (Phase 2.1). Discovery-vs-
  discipline is now a real tradeoff in the simulator: the archetype
  floors (0.50 / 0.35 / 0.20) place the three regimes on the
  omission/commission axis. One preset test updated:
  `test_aggressive_stops_more_than_balanced` assumed strictness can
  only appear as more stops; with the floor, Aggressive admits less
  junk and therefore stops less (11 vs 12 at seed 42).
- **2026-06-10 — Phases 1.2 + 1.3 landed (Model 1 built and
  calibrated).** `make_model1_*` presets (M0 pool + screening + stops
  + intake floor, 160-tick horizon), `scripts/model1_campaign.py`
  (3 archetypes x 30 seeds, ~23s), and
  `scripts/model1_calibration_check.py`. All four acceptance criteria
  pass: QW discipline 8.5% below floor; eligible right-tails enter at
  mean belief 0.67 (vs 0.82 in the full model) with 50% overlap into
  the non-eligible field; kill-a-gem errors occur (false rejects
  8/11/9 per archetype out of 26 eligible) alongside 15-16 major wins
  per archetype; regime value spread 9.3%. Two findings recorded in
  calibration_note.md §8: (1) mid-flight false stops are structurally
  ~impossible under EMA learning with level-threshold stops — the
  gem-killing error concentrates at intake, so criterion (c) was
  revised to count both error forms; (2) the [0,1] clamp piles 10 of
  26 eligible right-tails at belief exactly 1.0 — direct evidence for
  the clamped-vs-unclamped experiment (1.2 pre-ladder decision).
- **2026-06-10 — Phase 1.6 landed (M1 exploited: lever sweep).**
  `scripts/model1_lever_sweep.py`: 7 conditions x 30 seeds, each
  differing from the M1 Balanced base in exactly one parameter.
  THE M1 ANSWER: (1) Intake floor None -> 0.20 -> 0.35 -> 0.50 moves
  mean value 2092 -> 2096 -> 2120 -> 2179 (+4.2%) while right-tail
  stop churn halves (14.4 -> 5.8) and idle labor rises 0.9% -> 14.1%.
  Refusing to staff junk beats staffing it EVEN with idle labor
  earning nothing (baseline_value_per_tick = 0) — discipline pays for
  its own idleness. (2) Confidence-decline 0.08 -> 0.30 -> 0.40 moves
  value 2041 -> 2120 -> 2190 (+7.3%) with major wins FLAT
  (0.53/0.53/0.57). Faster stopping costs nothing in discovery at
  this rung — the structural corollary of the calibration finding
  that level-threshold stops cannot kill mean-reverting gems.
  Hypothesis for the ladder: patience acquires its payoff only when a
  mechanism makes stopping destructive (M2 frontier degradation) or
  holding informative (M3 attention). If M2/M3 do not flip this
  ordering, "patient moonshot" governance has no value mechanism in
  the model and the study's framing must say so.
- **2026-06-10 — Phase 1.4 experiment complete (clamped vs unclamped).
  [GATE: owner ratification pending.]** Minimal unclamped M1 variant
  on branch `experiment-unclamped-m1` (same Beta draws, same CRN
  streams, same thresholds; only the three [0,1] clamps removed).
  90 paired runs: value deltas < 1.5% everywhere, major wins
  identical, regime ordering unchanged, belief error slightly worse
  unclamped (+0.007 — unbounded beliefs overshoot a [0,1] truth). The
  ceiling pile-up artifact is decision-irrelevant. RECOMMENDATION:
  keep the clamp, with the evidence recorded as design decision 26
  (proposed). On ratification, delete the experiment branch.
  Comparison bundles: clamped 2026-06-10_103203, unclamped
  2026-06-10_104553.
