# Calibration / model revision — carryover for new sessions

**Purpose:** Preserve peer-review consensus and next-step intent across chat
sessions. This is **not** settled design corpus; it records **direction**
pending explicit design choices and doc updates.

**Last updated:** 2026-03-25

---

## Peer verdict (summary)

The external review endorsed the synthesis that separates **architectural
invariants** from **revisable domain assumptions**. Directionally: take the
package seriously; do not preserve v1 business assumptions only because they are
written down; **convert this into explicit design choices** (family-by-family
where needed), not an informal “good synthesis.”

---

## Architectural core (preserve)

- Determinism / reproducibility and `world_seed` discipline.
- Observation boundary: governance does not see latent truth (e.g. `q`,
  `true_duration_ticks`) unless explicitly exposed as observables.
- Action timing: end-of-tick decisions, start-of-next-tick effects.
- **Runner vs engine:** engine does not generate initiatives; runner
  materializes between ticks; frontier is environment-side.
- **Do not spawn on assignment:** replenishment tied to resolution/depletion and
  inter-tick materialization—not to the act of choosing—matches current docs and
  semantics.

---

## Agreed fixes / directions (pending formal spec)

### 1. Buffered frontier replenishment

- **Problem:** Multiple teams freeing in one cycle can create temporary thinness
  per family under “threshold 0, materialize one” rules.
- **Fix:** Resolve the open spec gap in `dynamic_opportunity_frontier.md`:
  **threshold + target buffer** per family (not assignment-triggered spawning).
- **Note:** Design doc already anticipates small-buffer strategy; quantity per
  replenishment was explicitly unresolved.

### 2. Idle vs “always staff the portfolio”

- **Distinction:** (A) no literal unused capacity vs (B) always assign to a
  modeled portfolio initiative—these differ.
- **Preferred direction:** **Evergreen baseline-work** (or equivalent) so teams
  are not “idle” in the literal sense without forcing the worst speculative
  initiative over maintenance / internal work / non-portfolio use of time.
- **Caution:** Baseline-work is arguably the **most consequential semantic
  change** in the set: it redefines what non-assignment to the strategic pool
  means. Name and scope it explicitly in design docs.

### 3. Ex ante rankability / intake signal

- **Problem:** Shared default `quality_belief_t` (e.g. 0.5) when
  `initial_quality_belief` is unset collapses “sourcing” into post-staffing
  learning—mismatches study overview language on meaningful selection among
  differentiated opportunities.
- **Direction:** Use existing `ResolvedInitiativeConfig.initial_quality_belief`
  (or equivalent) for a **noisy, informative prior** correlated with latent
  quality—**but document semantically** as intake / business-case / screening
  signal, not “just belief,” so `quality_belief_t` meaning stays clear.

### 4. Observable frontier thinning

- **Direction:** Later opportunities should be observably thinner where the
  business story requires it—not **only** latent degradation.
- **Caution:** Degrade a **small** set of observables, **family-specific**, tied
  to planning meaning; avoid “everything worsens in every dimension”
  (overdetermined rankings, cartoonish late frontier).

---

## Sequencing and provenance

- **Implementation sequencing** (suggested): buffered replenishment → informative
  ex-ante prior → baseline-work sink → selective observable thinning (with
  family-specific tables).
- **Epistemic / provenance:** Sole author may change baseline without backward
  compatibility pressure; still record **which baseline** produced a result
  (short calibration log, manifest flag, or archived pre-revision spec).
  **Intelligibility for future you** matters more than compatibility.

---

## Next explicit deliverable (before large code churn)

1. **Per family:** which ex ante observables carry planning signal vs held
   constant.
2. **Baseline-work initiative:** schema, observation fields, value/learning
   semantics, and how governance selects it vs portfolio work.
3. **Replenishment policy:** numeric defaults (threshold, target buffer) per
   family.
4. **Prior / intake rule:** functional form, noise, and independence from policy.

Then update authoritative design docs (`dynamic_opportunity_frontier.md`,
`interfaces.md`, `initiative_model.md`, `governance.md`, `review_and_reporting.md`,
`canonical_core.md` as needed) before treating implementation as canonical.

---

## Related open implementation note

See **§8 — Quick-win selection priority** in
`docs/implementation/open_implementation_issues.md` (ranking / default belief
ties)—overlaps ex-ante rankability theme.

---

## Resolved design decisions (locked for implementation)

**Purpose:** Fix numbers and semantics for the four revision items. These
decisions are authoritative for implementation. They supersede the "Agreed
fixes / directions" section above where they overlap. Authority-chain docs
(`dynamic_opportunity_frontier.md`, `interfaces.md`, `initiative_model.md`,
`governance.md`) will be updated to match in Step 2.

---

### D1. Buffered frontier replenishment

**Confirmed:** Never spawn on assignment. Materialization is triggered by
depletion checks at the inter-tick boundary (runner step 1), not by the
act of choosing or assigning.

**Rule:** When a family's unassigned count ≤ `replenishment_threshold`,
materialize until the count reaches `target_buffer`.

**Config change:** Add `target_buffer: int` to `FrontierSpec`.

**Defaults (uniform across families):**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `replenishment_threshold` | 2 | Trigger before empty; governance retains ≥2 candidates |
| `target_buffer` | 4 | After replenishment, 4 options per family for meaningful selection |

**Behavior details:**

- Materialization count per event = `target_buffer - current_unassigned`
  (always ≥1 when triggered).
- Right-tail families: draw from available prize descriptors first; if
  prizes are exhausted and general frontier is enabled, draw from general
  frontier.
- Deterministic ordering: families processed in `generation_tag`
  alphabetical order; within a family, sequential `initiative_id`
  assignment.
- Initial pool is not affected — threshold/buffer govern frontier
  replenishment only.
- Resolves both spec-gap comments in `dynamic_opportunity_frontier.md`
  (lines 188–191).

---

### D2. Baseline work

**Definition:** Productive non-portfolio work that teams perform when not
assigned to a strategic initiative. Maintenance, operational improvements,
tech-debt reduction, training. Always available; never exhausted.

**Governance interface:** Baseline is the **default** when governance does
not assign a team. Governance does not "assign to baseline" — it leaves
the team unassigned. An unassigned team produces baseline value
automatically.

**Semantics table:**

| Dimension | Baseline | Portfolio initiative |
|-----------|----------|---------------------|
| Value per tick | `baseline_value_per_tick` (default 0.1) | Value-channel-dependent |
| Quality signals | None | quality_belief_t updated |
| Execution signals | None | execution_belief_t updated |
| Capability contribution | None | q × capability_contribution_scale at completion (enablers) |
| Labor cost | Same as portfolio | Same |

**Config:** Add `baseline_value_per_tick: float = 0.1` to
`SimulationModelConfig`.

Default 0.1 is deliberately modest — well below a completed quick-win
lump (1.0–5.0 one-time) or flywheel residual rate (0.5–2.0/tick), but
not zero. It makes "leave on baseline" a rational choice when the
marginal portfolio initiative has low expected value.

**Runner accounting:**

- Each tick, the runner credits `baseline_value_per_tick` per unassigned
  team to a `cumulative_baseline_value` accumulator.
- Baseline value is reported separately in the manifest / run summary.
- The engine does not model baseline work. It is runner-side accounting.

**Observation boundary:**

- Teams on baseline: `assigned_initiative_id = None` (already visible).
- `baseline_value_per_tick` is a known config parameter (governance can
  reason about it as a reservation price).
- `PortfolioSummary` will include `teams_on_baseline: int`.

**What baseline is NOT:**

- Not an initiative — no initiative_id, lifecycle, or signals.
- Not "idle" — the team is working; the metric name should be
  `teams_on_baseline`, not `idle_teams`.
- Not capability-building — maintains but does not extend strategic
  capability.

**Policy implication:** Existing archetypes assign every available team.
They will need a comparison: "Is the expected value of the next-best
unassigned initiative > baseline_value_per_tick × expected_duration?"
Implementation detail deferred to Step 3.

---

### D3. Intake signal (ex-ante prior)

**Semantic contract:** `initial_quality_belief` is the organization's
**pre-execution assessment** of initiative quality — based on business-case
review, market analysis, and expert judgment. It is an intake screening
signal, NOT a posterior from observing execution. The learning process
starts from this prior.

**Formula:**

```
initial_quality_belief = clamp(
    latent_quality + Normal(0, sigma_intake),
    0.05,
    0.95
)
```

- `sigma_intake`: per-type-spec noise controlling screening accuracy.
- Clamp [0.05, 0.95]: prevent extreme priors that dominate learning.
- Noise drawn from the initiative's quality-signal RNG stream
  (deterministic, reproducible).

**Config:** Add `intake_signal_noise: float` to `InitiativeTypeSpec`.
When set, overrides the flat `default_initial_quality_belief`.

**Per-family defaults:**

| Family | sigma_intake | Rationale |
|--------|-------------|-----------|
| quick_win | 0.10 | Short, bounded scope — easiest to screen |
| flywheel | 0.15 | Compounding potential partially predictable |
| enabler | 0.15 | Capability needs assessable from technical landscape |
| right_tail | 0.25 | Speculative — hardest to evaluate pre-execution |

**Effects:**

- `rank_unassigned_initiatives` produces non-arbitrary ordering at t=0
  for non-bounded initiatives (partially addresses GitHub Issue #21).
- "Leave on baseline" decision (D2) becomes meaningful — low-belief
  initiatives may have expected value below baseline rate.
- All regimes see the same intake signals for the same pool (intake is
  environment-side, generated at pool construction).

**Design doc naming:** Rename semantic references from "default belief" to
"intake assessment" or "screening signal" in `interfaces.md`,
`initiative_model.md`, and `study_overview.md`.

---

### D4. Selective observable frontier thinning

**Principle:** When the frontier generates new initiatives, a small number
of **observable** attributes may degrade alongside latent quality.
Degradation is family-specific and tied to planning meaning. Unaffected
attributes are drawn from base ranges.

**Functional forms** (parallel to quality degradation formula):

For attributes where **higher is worse** (duration):
```
effective_range = base_range * min(obs_ceiling, 1.0 + obs_rate * n_resolved)
```

For attributes where **lower is worse** (capability scale):
```
effective_upper = base_upper * max(obs_floor, 1.0 - obs_rate * n_resolved)
# Lower bound stays at base value.
```

**Per-family specification:**

#### Flywheel — `planned_duration_ticks` range grows (easy loops done first)

| Parameter | Value |
|-----------|-------|
| Base planned range | [25, 70] |
| `duration_thinning_rate` | 0.005 / resolved |
| `duration_thinning_ceiling` | 1.4 (max +40%) |
| Example @ 40 resolved | multiplier 1.2 → [30, 84] |
| Fixed | residual_rate, residual_decay, signal_st_dev, dependency |

#### Enabler — `capability_contribution_scale` upper bound shrinks (high-impact platforms done first)

| Parameter | Value |
|-----------|-------|
| Base scale range | [0.1, 0.5] |
| `capability_scale_thinning_rate` | 0.008 / resolved |
| `capability_scale_thinning_floor` | 0.5 (upper bound ≥ 50% of base = 0.25) |
| Example @ 30 resolved | multiplier 0.76 → [0.1, 0.38] |
| Fixed | planned_duration, signal_st_dev, dependency |

#### Quick win — `planned_duration_ticks` range grows (truly quick wins done first)

| Parameter | Value |
|-----------|-------|
| Base planned range | [4, 12] |
| `duration_thinning_rate` | 0.008 / resolved |
| `duration_thinning_ceiling` | 1.5 (max +50%) |
| Example @ 50 resolved | multiplier 1.4 → [6, 17] |
| Fixed | completion_lump_value, residual_rate, signal_st_dev, dependency |

#### Right-tail — no observable thinning (v1)

Right-tail uses prize-preserving refresh: `observable_ceiling` is fixed
per prize (same market opportunity, different approach). Per-attempt
quality degradation already exists via `right_tail_refresh_quality_degradation`.
Observable thinning for right-tail would require enabling general frontier
draws (currently disabled: `frontier_degradation_rate = 0.0`), which is a
separate design decision.

**Config changes:** Add to `FrontierSpec`:

```python
# Observable thinning — planned_duration range grows.
# min(ceiling, 1.0 + rate * n_resolved) applied to both bounds.
duration_thinning_rate: float | None = None
duration_thinning_ceiling: float | None = None

# Observable thinning — capability_contribution_scale upper bound shrinks.
# max(floor, 1.0 - rate * n_resolved) applied to upper bound only.
capability_scale_thinning_rate: float | None = None
capability_scale_thinning_floor: float | None = None
```

**Observable vs latent interaction:** Intake signals (D3) and observable
thinning (D4) work together. A frontier enabler with thinned capability
scale (say 0.3 instead of 0.5) also gets a noisy intake belief correlated
with its (degraded) latent quality. Governance sees both: a smaller scale
AND a lower intake belief. The frontier initiative is observably less
attractive on two dimensions — matching the business intuition that "the
next similar project looks worse."

---

### Implementation sequencing (confirmed)

1. Buffered replenishment (D1) — `FrontierSpec` + `runner.py` + tests
2. Intake prior (D3) — `InitiativeTypeSpec` + `pool.py` + tests
3. Baseline work (D2) — `SimulationModelConfig` + `runner.py` + reporting + tests
4. Observable thinning (D4) — `FrontierSpec` + `pool.py` + tests

D1 before D3 because replenishment is a pure infrastructure change. D3
before D2 because intake beliefs make the baseline tradeoff meaningful.
D4 last because it builds on D1 (frontier materialization) and D3
(intake signals).
