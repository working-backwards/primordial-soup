# Primordial Soup: Study Brief

## Purpose of this note

This note gives you enough of the model structure — latent state, observation
model, belief dynamics, policy interface, and experimental design — to react
to the three questions I raised. It describes what is currently built and
running, not future analysis plans.

A single run produces f(x, ξ), where x is the governance policy, ξ is the
stochastic world, and f is portfolio performance. The current goal is to
compare governance regimes under common random numbers across named environment
families and understand how differences in governance drive differences in outcomes.

---

## What the study is

Formally, the simulator is a discrete-time, partially observable Markov
decision process. Governance is a pure decision function mapping the current
observation bundle to an action vector. It never sees latent initiative truth.
Latent state is hidden and must be inferred from noisy signals that accumulate
as teams work.

**Endogenous information quality.** Executive attention modulates strategic
signal noise. Below a minimum threshold, shallow attention actively degrades
signal clarity — it does not merely fail to help. Above that threshold, more
attention reduces noise with diminishing returns. The decision-maker is
embedded in the signal generation mechanism, not a passive observer of an
independent process.

**Autonomous residual mechanisms.** Some completed initiatives activate
persistent value streams that continue producing output after the team has
redeployed. These streams accumulate and compound across the portfolio
independently of further governance attention. A governance regime that treats
absence of near-term return as a stop signal will systematically underinvest
in the initiative types that produce them.

---

## What the study measures

The study evaluates governance regimes along three outcome families.

**1. Realized economic performance**
- Cumulative value created over the horizon, decomposed into completion-lump
  value and residual value. The decomposition matters: a regime that generates
  most of its value through early quick-win lumps is doing something
  structurally different from one that accumulates compounding residual
  streams, even if terminal totals are similar.
- Value trajectory over time, not just terminal level, because compounding
  mechanisms take time to build.

**2. Major-win discovery performance**
- Surfaced major-win count and probability of discovering high-quality
  right-tail opportunities before governance terminates them.
- Time to first major win and labor per major win, where sample sizes support
  it.

Major wins are recorded as discovery events, not priced as realized economic
value within the horizon. The study measures governance's ability to preserve
and surface rare major opportunities, not the full downstream value of
capturing them.

**3. Organizational capability development**
- Terminal portfolio capability (C_T) — the accumulated stock of
  enabler-driven learning improvement available to the organization for future
  work.
- Because C_t enters the effective signal standard deviation as a divisor,
  higher terminal capability means future initiatives would be evaluated with
  less noise. A regime that systematically underinvests in enabler work leaves
  the organization with degraded learning infrastructure, an effect invisible
  in realized economic value during the horizon but visible in terminal
  capability.

Two regimes may produce similar cumulative economic value while leaving the
organization in very different capability states. Terminal-value-only
comparisons would miss this distinction entirely.

---

## Initiative families and value channels

Four families are included because they correspond to distinct payoff
structures and learning dynamics. Family labels are generator-side metadata
and reporting tags only. The engine operates entirely on resolved initiative
attributes; it never branches on labels.

| Family | Primary value channel | Outcome family | Key learning dynamic |
|---|---|---|---|
| **Quick win** | One-time completion lump | Realized economic — lump | Low noise, short duration, fast resolution |
| **Flywheel** | Residual stream activated at completion; persists after team redeploys | Realized economic — residual | Moderate noise; value invisible during execution |
| **Enabler** | Portfolio capability contribution at completion; reduces σ_eff for all future staffed initiatives | Organizational capability | Moderate noise; value indirect and deferred |
| **Right-tail** | Major-win event at completion; is_major_win is a hidden generator-assigned flag | Major-win discovery | High noise; rare but potentially transformational |

---

## Latent state, observation model, and belief dynamics

### Latent variables (hidden from governance, fixed at generation)

- **`latent_quality` (q)** — true strategic quality, drawn from a
  family-specific Beta distribution. Governs value realization and whether a
  right-tail initiative is a major win.
- **`true_duration_ticks`** — latent completion time. Hidden from governance;
  inferred only through execution progress signals.
- **`latent_execution_fidelity` (q_exec)** — derived from
  `planned_duration_ticks / true_duration_ticks`, bounded at 1.0. The fixed
  latent quantity the execution belief tracks.
- **`dependency_level` (d)** — friction that amplifies strategic signal noise
  and slows learning. Fixed per initiative.
- **`is_major_win`** — deterministic threshold function of latent quality,
  assigned at generation: `is_major_win = (q >= q_major_win_threshold)`.
  Hidden until completion.

### Observable attributes (visible to governance from creation)

- `planned_duration_ticks` — observable plan reference
- `observable_ceiling` — bounded prize ceiling for right-tail initiatives
- `capability_contribution_scale` — expected portfolio capability yield for
  enablers
- `sigma_base` — base strategic signal noise
- `generation_tag`, `required_team_size`, `initial_belief_c0`,
  `initial_c_exec_0`

### Signal generation (each staffed tick)

**Strategic quality signal:**

```
y_t ~ Normal(q, σ_eff(d, a, C_t)²)

σ_eff(d, a, C_t) = [σ_base × (1 + α_d × d) × g(a)] / C_t
```

`C_t` is portfolio capability (initialized at 1.0, increased by enabler
completions, bounded by C_max). Higher C_t reduces effective noise for all
staffed initiatives simultaneously.

`g(a)` is the attention noise modifier:

```
g_raw(a) = 1 + k_low × (a_min - a)       if a < a_min   [noise increases]
           1 / (1 + k × (a - a_min))      if a >= a_min  [diminishing returns]

g(a) = clamp(g_raw(a), g_min, g_max)
```

`g_raw(a_min) = 1` so the function is continuous at threshold. Below `a_min`,
shallow attention actively worsens signal clarity.

**Execution progress signal** (only when `true_duration_ticks` is set):

```
z_t ~ Normal(q_exec, σ_exec²)
where q_exec = min(1.0, planned_duration_ticks / true_duration_ticks)
```

**Intentional asymmetry:** the execution signal is not modulated by executive
attention or dependency level. Execution progress is directly observable from
elapsed time, milestone delivery, and resource consumption regardless of
leadership involvement. Strategic quality is not. This is a deliberate design
choice. Its downstream consequence is that cost-sensitive stopping rules likely
appear somewhat more effective in the model than in real organizations, where
schedule slips often go undetected until severe. You identified this directly —
I wanted to confirm the choice is explicit and its implication documented.

### Belief updates

**Strategic quality belief:**

```
c_{t+1} = clamp(c_t + η × λ_staff × λ_ramp × L(d) × (y_t - c_t), 0, 1)
```

where `η` is the base learning rate, `L(d) = 1 - d` is the
dependency-adjusted learning efficiency, `λ_ramp` reduces learning efficiency
during the ramp period after a new team assignment, and `λ_staff` captures
diminishing returns from surplus staffing. Initialized at 0.5 (neutral
symmetric baseline).

**Execution belief:**

```
c_exec_{t+1} = clamp(c_exec_t + η_exec × (z_t - c_exec_t), 0, 1)
```

No attention or dependency modulation. Initialized at 1.0 (on-plan prior).

**Governance sees:** `quality_belief_t`, `execution_belief_t`, and the derived
`implied_duration_ticks = round(planned_duration_ticks / max(c_exec_t, ε))`
in business-interpretable units. Governance does not see latent quality, true
duration, or the observation noise draws.

**One important limitation:** governance sees only the current scalar belief,
not the observation count underlying it. A belief based on two noisy draws is
indistinguishable from one based on forty. The stagnation window provides an
implicit precision proxy, but it is coarser than formal posterior variance
tracking.

---

## What governance controls

| Tier | What belongs here | Who controls it |
|---|---|---|
| **Environmental conditions** | Realized initiative pool, world seed, family initiative mix, latent draws, attention-to-signal curve shape, executive attention budget, total labor endowment, simulation horizon | Fixed before the run |
| **Governance architecture** | Workforce decomposition into teams, standing portfolio guardrails, diversification targets, labor-share mix targets | Chosen before the run; held fixed within the run |
| **Operating policy** | Continue/stop decisions, executive attention allocation, team assignment and reassignment | Chosen by the governance policy each tick |

The canonical sweep varies **operating policy** across fixed environmental
conditions and fixed architecture.

### Governance action space

The policy emits an action vector at the end of each tick, effective at the
start of the next tick:

- **ContinueStop**: required for every reviewed active staffed initiative.
  A stop never activates residual value and never grants capability
  contribution — completing and stopping are semantically distinct and
  load-bearing in the study design.
- **SetExecAttention**: sets executive attention for the next tick. Omission
  means zero, not persistence of prior attention. Total must not exceed the
  executive attention budget.
- **AssignTeam**: assigns an available team to an unassigned initiative. The
  engine never auto-assigns.

### Stop logic

Governance may stop an initiative on four named paths:

1. **Confidence decline**: `quality_belief_t < confidence_decline_threshold`
2. **Prize inadequacy**: for bounded-prize initiatives, expected prize value
   (`quality_belief_t × observable_ceiling`) has remained below the
   prize-relative threshold for `effective_tam_patience_window` consecutive
   reviews. Patience scales linearly with `observable_ceiling`.
3. **Stagnation**: conjunctive — informational stasis (net belief movement
   `|c_t - c_{t-W_stag}| < ε_stag` over a staffed-tick window) AND failure
   to earn continued patience under the relevant rule for the initiative's
   state.
4. **Execution overrun**: `execution_belief_t < exec_overrun_threshold`. This
   is a pure policy-side check. The engine does not auto-stop for execution
   overrun. Regimes differ in whether and how heavily they weight this signal.

---

## Experimental design and common random numbers

Regimes are compared under a shared realized world so that outcome differences
can be attributed to governance rather than to different opportunity pools.

**Per-initiative random streams.** Each initiative has two dedicated MRG32k3a
substreams — one for strategic quality signals, one for execution progress
signals — seeded deterministically at pool generation from the world seed and
initiative ID. A single global stream is explicitly prohibited: once regimes
diverge in which initiatives are active, a global stream would also diverge
between regimes, destroying comparability. With per-initiative streams, two
regimes sharing a world seed receive identical observation noise for a given
initiative regardless of which other initiatives they have activated or
stopped. MRG32k3a was chosen specifically because it supports the stream and
substream structure SimOpt uses.

**Divergence is intentional.** Regimes begin from identical initial conditions
but may face different evolving futures because governance choices change which
initiatives complete, which residual streams accumulate, and how capability
develops. That divergence is a phenomenon under study. The comparison
identifies what governance policy causes, holding the stochastic world constant.

---

## Calibration: three tiers of confidence

**Tier 1 — Empirically anchored (right-tail incidence and duration).**
Three independent evidence sources were triangulated: incumbent new-business-
building research on breakthrough incidence, internal venture and exploratory-
innovation evidence, and high-measurement long-shot analogues with observable
funnels. These support a major-win incidence range of approximately 0.3%–4%
among completed right-tail initiatives and a duration anchor of 3 / 5 / 10
years to stable resolution. The three named environment families span this
defensible range rather than pinning a point estimate.

An early baseline campaign (63 runs) diagnosed a structural collapse: the
pre-calibration Beta/threshold combination placed the major-win threshold so
far into the tail that P(q >= threshold) was approximately 0.003%. No major
wins were possible in any practical sample. That was a calibration failure,
not a governance finding. The current parameters:

| Family | Beta(α, β) for right-tail q | P(q >= 0.80) | Design intent |
|---|---|---:|---|
| `balanced_incumbent` | Beta(0.8, 2.0) | ~3% | Mid-case |
| `short_cycle_throughput` | Beta(0.6, 2.5) | ~1% | Scarce major wins |
| `discovery_heavy` | Beta(1.2, 1.8) | ~5–8% | Rich major wins |

Duration ranges: right-tail `true_duration_ticks` is 80–260 ticks (1.5–5.0
years) depending on family, with `planned_duration_ticks` set at roughly 1.2×
to reflect systematic overestimate in exploratory planning. At a 313-tick
(6-year) horizon, many right-tail initiatives will not complete under
impatient governance. This is intentional — the study measures governance's
ability to persist through uncertainty.

**Tier 2 — Qualitatively anchored (flywheel, enabler, quick-win parameters).**
This makes relative findings more robust than absolute level claims, but it
does not eliminate the need to get the family relationships approximately right.

**Tier 3 — Structural assumption (attention-to-signal curve).**
The g(a) shape parameters (`a_min`, `k_low`, `k`, `g_min`, `g_max`) are
structural assumptions, not empirically calibrated values. The shape is
motivated by organizational behavior intuitions, but the specific curvature
and threshold location are not grounded in external data. This is the weakest
calibration tier, and I would welcome your view on whether sensitivity
analysis across the attention parameter space is the right approach here.

The comparative structure reduces the burden on absolute calibration:
systematic errors that affect all regimes equally do not contaminate relative
findings. The burden is on getting structural properties right, not matching
point estimates.

---

## Known limitations

1. **Attention asymmetry.** As noted above, execution signals are not
   attention-modulated. Cost-sensitive stopping rules likely appear more
   effective than in real organizations.

2. **Scalar belief without posterior variance.** Governance cannot distinguish
   a belief based on two noisy observations from one based on forty.

3. **EMA clamping biases.** The [0, 1] clamp produces asymmetric behavior near
   both boundaries — downward drift for on-plan initiatives near the execution
   belief ceiling, and downward equilibrium bias for high-quality initiatives
   near the upper strategic belief boundary. Both are symmetric across regimes
   and do not affect comparative findings.

4. **Non-right-tail calibration is archetypal.** Governance findings for
   flywheels, enablers, and quick wins rest on qualitatively motivated rather
   than empirically fitted parameters.

5. **Endogenous proposal quality degradation is not modeled.** Aggressive
   early-stopping governance does not depress the ambition or quality of future
   proposals. Comparative findings likely understate the real organizational
   cost of aggressive stop-loss governance.

---

## What I would most value your reaction to

1. Is the latent-state and observation-boundary structure sound for the problem
   being studied? In particular, is the EMA-style belief update — rather than
   maintaining a formal posterior — a reasonable simplification for the
   governance comparison question?

2. Is the CRN implementation, with per-initiative MRG32k3a substreams, the
   right discipline here? Are there comparability risks I have not anticipated?

3. Is the three-tier calibration approach reasonable given the nature of the
   evidence? For Tier 3 specifically, is sensitivity analysis across the
   attention parameter space the right answer, or is there a better approach?

4. Are there aspects of the observation model, belief dynamics, or stopping
   logic that look materially under-specified or likely to distort comparative
   findings?
