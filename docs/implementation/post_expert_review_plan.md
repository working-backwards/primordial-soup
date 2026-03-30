# Post-Expert-Review Implementation Plan

**Created:** 2026-03-27
**Context:** An external simulation expert reviewed the study brief. Key
recommendations: simplify first ("VW Beetle"), inspect trajectories,
consider unclamping. After peer review and synthesis, the agreed direction
is: trajectory validation → presentation clarity → ex ante rankability →
defer belief geometry redesign.

---

## Step 1: Initiative trajectory diagnostic script

**Goal:** Produce detailed per-initiative traces showing latent quality,
belief evolution, signal draws, stop decisions, and value realization.
The reviewer explicitly requested this. It is the foundation for every subsequent
conversation.

**What to build:** A script (e.g., `scripts/initiative_trajectories.py`)
that runs a single seed with `record_per_tick_logs=True` and produces
text or CSV output for a handful of representative initiatives:

- One flywheel (moderate q, completes)
- One right-tail (high q, major-win candidate)
- One right-tail (low q, correctly stopped)
- One enabler (capability contributor)
- One quick-win (fast completion)

**Per-initiative output per tick:**
- `tick`, `lifecycle_state`, `quality_belief_t`, `latent_quality` (post-hoc),
  `exec_attention_a_t`, `effective_sigma_t`, `execution_belief_t`,
  `is_ramping`, `ramp_multiplier`

These fields already exist on `PerInitiativeTickRecord` (reporting.py:49-72).

**Per-initiative event output:**
- Stop event (if stopped): tick, triggering_rule, belief at stop
- Completion event (if completed): tick, value realized
- Major-win event (if applicable): tick, quality at completion

**Implementation notes:**
- Use `run_single_regime()` with `record_per_tick_logs=True`,
  `record_event_log=True`
- Filter `per_initiative_tick_records` by selected initiative IDs
- Cross-reference with `stop_event_log` and `major_win_event_log`
- Select initiatives by examining `resolved_initiatives` from the
  manifest to find representatives of each family

**Effort:** ~1 session. Pure read from existing data structures.

---

## Step 2: Presentation clarity — family mixes and effective parameters

**Goal:** Make the default environment definitions legible to an external
reviewer. The reviewer immediately noticed the missing family mix counts.

### 2a. Document family mix counts

For each canonical environment family (`balanced_incumbent`,
`short_cycle_throughput`, `discovery_heavy`), document the initiative
type counts from `InitiativeTypeSpec.count` in the environment preset.

**Where:** Add a summary to `docs/study_overview.md` or a new
`docs/design/environment_families.md` showing the initiative type
composition of each environment.

**Data source:** `presets.py` — the `make_*_environment_spec()` functions.

### 2b. Clarify effective parameter count

Document which parameters are active vs inactive in baseline presets:

- `staffing_response_scale` = 0.0 everywhere (lambda_staff disabled)
- `max_attention_noise_modifier` = None in all presets (no upper cap)
- `staffing_response_scale_range` = None on all type specs (no draw)

The attention noise modifier has 5 parameters in the code
(`attention_noise_threshold`, `low_attention_penalty_slope`,
`attention_curve_exponent`, `min_attention_noise_modifier`,
`max_attention_noise_modifier`) but `max_attention_noise_modifier` is
always None, making the effective active parameters 4. The reviewer suggested
a 2-parameter form. The current above-threshold branch
`1 / (1 + k * (a - a_min))` is already a 2-parameter rational function
(threshold + curvature). The below-threshold branch adds a third
parameter (penalty slope). Whether to collapse these is a simplification
decision deferred -- under consideration.

**Effort:** ~0.5 session. Documentation only, no code changes.

---

## Step 3: Ex ante rankability — informative screening signals

**Goal:** Introduce differentiated initial beliefs so governance can
prioritize among competing initiatives before evidence accumulates.

### Current state

- `ResolvedInitiativeConfig.initial_quality_belief` exists (config.py:368).
  Nullable; when None, runner uses `model.default_initial_quality_belief`
  (always 0.5).
- Runner already respects per-initiative initial belief (runner.py:287-289
  and 737-739).
- Generator always sets `initial_quality_belief=None` (pool.py:279).
- `InitiativeTypeSpec` has no screening signal configuration.

### Design

Add a **screening signal** mechanism to the generator. At generation
time, each initiative receives a noisy ex ante signal about its latent
quality, which sets its `initial_quality_belief`. The signal is
informative but imperfect — correlated with true quality but with
significant noise.

**Option A: Noisy quality signal**
```
screening_signal = clamp(q + Normal(0, σ_screen), 0, 1)
initial_quality_belief = screening_signal
```
where `σ_screen` is a new per-type-spec parameter controlling screening
accuracy. High `σ_screen` = poor screening (nearly uniform beliefs).
Low `σ_screen` = good screening (beliefs close to true quality).

**Option B: Quantile-based differentiation**
Draw initial beliefs from a distribution centered near the type's
quality distribution mean, with noise. This preserves the property
that governance does not know true quality but has a type-level prior.

**Recommended: Option A.** It is simpler, more interpretable, and
directly connects initial belief to latent quality with explicit noise.
The `σ_screen` parameter has a clear business interpretation: how good
is the organization's intake screening process?

### Changes required

1. **config.py** — Add `screening_signal_st_dev: float | None = None`
   to `InitiativeTypeSpec`. When None, generator uses the current
   behavior (initial_quality_belief = None → global default).

2. **pool.py** — In `_generate_single_initiative()`, after drawing
   `latent_quality`, if `type_spec.screening_signal_st_dev` is not None,
   draw a screening signal and set `initial_quality_belief`:
   ```python
   if type_spec.screening_signal_st_dev is not None:
       raw_signal = latent_quality + draw_normal(rng, 0, type_spec.screening_signal_st_dev)
       initial_quality_belief = max(0.0, min(1.0, raw_signal))
   ```

3. **Design docs** — Update `initiative_model.md` and/or
   `core_simulator.md` to name the screening signal semantics. This is
   the "informative ex-ante prior / intake signal" from the calibration
   carryover document.

4. **Presets** — Set `screening_signal_st_dev` per type spec in each
   environment family. Quick-wins might have low screening noise (easy
   to evaluate upfront), right-tail might have high noise (inherently
   hard to screen).

5. **Tests** — Add tests verifying that screening signals produce
   differentiated initial beliefs, and that the existing behavior is
   preserved when `screening_signal_st_dev` is None.

### What does NOT change

- The belief update rule (EMA) is unchanged.
- Stop rules are unchanged — they still compare `quality_belief_t`
  against thresholds.
- The observation boundary is unchanged — governance sees
  `quality_belief_t`, not `latent_quality`.
- The runner's initialization logic is unchanged — it already reads
  `initial_quality_belief` from the config.

### Business interpretation

Organizations do not fund initiatives blindly. Before committing a team,
they evaluate business cases, conduct feasibility studies, and assess
strategic fit. These evaluations are imperfect — they cannot reveal the
true quality of an initiative — but they are informative enough to create
a rough ranking. The screening signal models this intake process.

A flywheel initiative with a strong business case starts with higher
organizational confidence than one with a weak case. A right-tail
moonshot with uncertain feasibility starts with lower confidence. This
is not foreknowledge of the outcome — it is the realistic starting
position that governance uses to prioritize its limited attention and
team assignments.

**Effort:** ~1-2 sessions. Small code change, meaningful calibration
and design doc work.

---

## Step 4: Attention noise modifier simplification (deferred)

**Goal:** Determine whether the current 5-parameter attention noise
modifier should be simplified.

### Current form (core_simulator.md, learning.py:59-130)

```
g(a) = 1 + k_low * (a_min - a)         if a < a_min
g(a) = 1 / (1 + k * (a - a_min))       if a >= a_min
g(a) = clamp(g_raw, g_min, g_max)
```

5 parameters: `a_min` (threshold), `k_low` (below-threshold slope),
`k` (above-threshold curvature), `g_min` (floor), `g_max` (cap, always
None in practice).

### Reviewer's suggested forms

`c_1 * exp(-c_2 * a)` — 2 parameters, monotone decreasing.
`c_1 / (1 + a^{c_2})` — 2 parameters, monotone decreasing with
diminishing returns.

### Assessment

The above-threshold branch `1 / (1 + k * (a - a_min))` is already a
2-parameter rational function similar to the reviewer's second suggestion. The
below-threshold branch adds the asymmetric penalty for low attention.
If the below-threshold behavior is not load-bearing for governance
comparison (i.e., if canonical policies never produce zero-attention
initiatives), then the below-threshold branch could be dropped,
reducing to 3 effective parameters (threshold, curvature, floor).

**Decision:** Deferred -- under consideration. If the below-threshold
penalty is not contributing to regime differentiation, simplify to a
2-parameter form. If it is (because some archetypes spread attention
thin while others concentrate), keep the piecewise form but document
that it is equivalent to the reviewer's suggestion above the threshold.

**Effort:** ~0.5 sessions if simplifying, 0 if documenting equivalence.

---

## Deferred: Belief geometry redesign (unbounded state)

**Status:** Not pursued now. Agreed across all reviewers that the
clamping artifact is symmetric under CRN and does not materially bias
relative governance comparisons. The redesign cost (new threshold
semantics, recalibration, new reporting interpretation) is not justified
at this stage.

**Framing:** This is a potential future model variant, not a refinement.
If pursued after the current study produces findings, it would be a
separate branch and a separate calibration effort.

---

## Sequencing

```
Step 1 (trajectory plots)          ~1 session    no dependencies
Step 2 (presentation clarity)      ~0.5 session  no dependencies
Step 3 (ex ante rankability)       ~1-2 sessions after Step 1 (trajectories
                                                  validate baseline behavior
                                                  before changing initialization)
Step 4 (attention simplification)  ~0.5 session   deferred
```

Steps 1 and 2 can run in parallel. Step 3 should follow Step 1 because
trajectory plots will validate baseline behavior before changing the
initialization. Step 4 is deferred.
