# Environment families and effective parameter inventory

This document makes the default environment definitions and governance
archetype parameters legible to an external reviewer. It answers two
questions:

1. What is the initiative pool composition for each environment family?
2. How many parameters are effectively active in the baseline presets?

Created as part of the post-expert-review presentation clarity pass
(post_expert_review_plan.md Step 2).

---

## 1. Initiative pool composition by family

All families share a total pool of **200 initiatives** drawn before the
simulation begins. Enabler count (30) is fixed across all families.
Flywheel and right-tail counts vary by family; quick-win count fills
the remainder.

| Type        | balanced_incumbent | short_cycle_throughput | discovery_heavy |
|-------------|-------------------:|----------------------:|----------------:|
| flywheel    |                 70 |                    50 |              40 |
| right_tail  |                 20 |                    16 |              56 |
| enabler     |                 30 |                    30 |              30 |
| quick_win   |                 80 |                   104 |              74 |
| **Total**   |            **200** |               **200** |         **200** |

**What varies across families:** The right-tail type spec changes
(count, quality distribution, duration range) and the flywheel count
varies by family (70/50/40). All other type specs (enabler, quick-win)
use identical parameters across all three families. Quick-win count
fills the remainder to 200. This ensures family differences are
interpretable as differences in right-tail opportunity structure,
flywheel representation, and initiative mix.

### Right-tail parameters by family

| Parameter                    | balanced_incumbent    | short_cycle_throughput | discovery_heavy       |
|------------------------------|----------------------:|----------------------:|----------------------:|
| Count                        |                    20 |                    16 |                    56 |
| Quality distribution         | Beta(0.8, 2.0)        | Beta(0.6, 2.5)        | Beta(1.2, 1.8)        |
| Quality mean                 |                 0.286 |                 0.194 |                 0.400 |
| Tail above threshold (0.80)  |               ~3%     |               ~1%     |             ~5-8%     |
| true_duration_range (ticks)  |             104 - 182 |              80 - 156 |             130 - 260 |
| true_duration_range (years)  |           2.0 - 3.5   |           1.5 - 3.0   |           2.5 - 5.0   |
| planned_duration_range       |             125 - 220 |              96 - 187 |             156 - 312 |
| q_major_win_threshold        |                  0.80 |                  0.80 |                  0.80 |
| observable_ceiling dist.     | LogNormal(4.0, 0.5)   | LogNormal(4.0, 0.5)   | LogNormal(4.0, 0.5)   |
| screening_signal_st_dev      |                  0.30 |                  0.30 |                  0.30 |
| required_team_size_range     |              5 - 15   |              5 - 15   |              5 - 15   |

### Shared type specs (identical across all families)

**Flywheel** (70/50/40 initiatives by family): Beta(6.0, 2.0) quality
(mean ~0.75). Duration 25-45 ticks (6-10 months). Required team size
8-10 (only size-10+ teams can staff all flywheels). Residual-dominant
value channel (rate 0.5-2.0, decay 0.005-0.02). Low signal noise
(0.05-0.15), low dependency (0.1-0.4). Screening signal st_dev=0.15
(moderate). Frontier: degradation_rate=0.01.

**Enabler** (30 initiatives): Beta(4.0, 4.0) quality (mean 0.5).
Duration 10-30 ticks. Required team size 5-8 (any size-5+ team can
handle enablers). Capability contribution on completion (scale
0.1-0.5). No residual or lump. Low dependency (0.0-0.2). Screening
signal st_dev=0.20 (slightly noisier). Frontier: degradation_rate=0.005.

**Quick-win** (80/104/74 initiatives): Beta(5.0, 3.0) quality (mean
~0.625). Duration 3-10 ticks. Required team size 5 (any team can handle
quick wins). Completion-lump-dominant (1.0-5.0) with small residual
tail (rate 0.01-0.10, decay 0.10-0.30). Low dependency (0.0-0.2).
Screening signal st_dev=0.10 (informative). Frontier:
degradation_rate=0.02.

---

## 2. Shared environment parameters

All families share these environment-level settings:

| Component       | Parameter                    | Value       | Notes                          |
|-----------------|------------------------------|-------------|--------------------------------|
| TimeConfig      | tick_horizon                 | 313         | ~6 years at 1 tick/week        |
|                 | tick_label                   | "week"      |                                |
| WorkforceConfig | team_count                   | 30          | Mixed-size teams               |
|                 | team_size                    | 20×5, 8×10, 2×20 | 220 total labor          |
|                 | ramp_period                  | 4           | Ticks                          |
|                 | ramp_multiplier_shape        | LINEAR      |                                |
| ModelConfig     | exec_attention_budget        | 40.0        | Conservatively high            |
|                 | base_signal_st_dev_default   | 0.15        |                                |
|                 | dependency_noise_exponent    | 1.0         |                                |
|                 | default_initial_quality_belief | 0.5       | Uninformative prior            |
|                 | reference_ceiling            | 50.0        |                                |
|                 | learning_rate                | 0.1         | eta                            |
|                 | execution_signal_st_dev      | 0.15        | sigma_exec                     |
|                 | execution_learning_rate      | 0.1         | eta_exec                       |
|                 | max_portfolio_capability     | 3.0         | C_max                          |
|                 | capability_decay             | 0.005       |                                |

---

## 3. Governance archetype parameter comparison

Three named archetypes vary **governance parameters only**. The
environment (pool, timing, workforce, model) is identical across
archetypes for a given family.

| Parameter                            | Balanced | Aggressive | Patient  |
|--------------------------------------|----------|------------|----------|
| confidence_decline_threshold         |     0.30 |       0.40 |     0.08 |
| tam_threshold_ratio                  |     0.60 |       0.70 |     0.40 |
| base_tam_patience_window             |       10 |          5 |       15 |
| stagnation_window_staffed_ticks      |       15 |          8 |       20 |
| stagnation_belief_change_threshold   |    0.020 |      0.020 |    0.015 |
| attention_min                        |     0.15 |       0.15 |     0.15 |
| attention_max                        |     None |       None |     None |
| exec_overrun_threshold               |     0.40 |       0.50 |     0.35 |
| low_quality_belief_threshold         |     None |       None |     None |
| max_low_quality_belief_labor_share   |     None |       None |     None |
| max_single_initiative_labor_share    |     None |       None |     None |

**Parameters that actually vary:** 6 of the 11 stop/attention governance
parameters differ across archetypes: confidence_decline_threshold,
tam_threshold_ratio, base_tam_patience_window,
stagnation_window_staffed_ticks, stagnation_belief_change_threshold, and
exec_overrun_threshold. Additionally, all 5 portfolio mix target
parameters (4 bucket targets + tolerance) vary across archetypes
(see table below).

**Parameters that are constant across all archetypes:** attention_min
(0.15), attention_max (None), and all three portfolio-risk controls
(all None).

### Portfolio mix targets by archetype

Each archetype specifies target labor-share fractions by initiative
type, enforced as soft constraints via the portfolio mix mechanism.

| Bucket     | Balanced | Aggressive | Patient  |
|------------|----------|------------|----------|
| flywheel   |     0.40 |       0.35 |     0.25 |
| right_tail |     0.10 |       0.05 |     0.25 |
| enabler    |     0.15 |       0.10 |     0.15 |
| quick_win  |     0.35 |       0.50 |     0.35 |
| tolerance  |     0.10 |       0.10 |     0.15 |

Balanced governance allocates labor roughly in proportion to the
initiative mix, with a conservative 10% right-tail cap. Aggressive
governance minimizes right-tail allocation and maximizes quick-win
throughput. Patient governance allocates 25% to right-tail speculative
bets, reflecting willingness to make large exploration investments,
with a wider tolerance band (15%) for flexible allocation.

---

## 4. Effective parameter count and inactive parameters

Several parameters exist in the configuration schema but are
**inactive** (set to None or zero) in all baseline presets. An external
reviewer counting "free parameters" should exclude these.

### Inactive parameters (set to zero or None in all presets)

| Parameter                          | Value  | Effect when inactive              |
|------------------------------------|--------|-----------------------------------|
| staffing_response_scale            | 0.0    | Staffing intensity response off   |
| staffing_response_scale_range      | None   | No per-initiative draw            |
| max_attention_noise_modifier       | None   | No upper cap on g(a)             |
| dependency_learning_scale          | None   | Uses canonical L(d) = 1 - d      |
| low_quality_belief_threshold       | None   | Portfolio-risk guardrail off      |
| max_low_quality_belief_labor_share | None   | Portfolio-risk guardrail off      |
| max_single_initiative_labor_share  | None   | Portfolio-risk guardrail off      |
| attention_max                      | None   | No per-initiative attention cap   |

**Previously inactive, now active in all presets:**

| Parameter                          | Values              | Effect                            |
|------------------------------------|---------------------|-----------------------------------|
| screening_signal_st_dev            | 0.10 - 0.30        | Ex ante screening signal noise; sets initial quality belief dispersion at pool generation. Active in all type specs across all families. |
| required_team_size / required_team_size_range | 5 - 20   | Minimum team size to staff an initiative. Creates governance trade-offs in team assignment: small teams handle quick-wins and enablers, medium teams staff flywheels, large teams handle the biggest right-tail bets. Active in all type specs. |
| portfolio_mix_targets              | See §3 table        | Target labor-share fractions by initiative type (governance-side). All three archetypes specify distinct mix targets and tolerance bands. |

### Attention noise modifier: 5 code parameters, 4 effective

The attention noise modifier g(a) has 5 parameters in the code:

```
g_raw(a) = 1 + k_low * (a_min - a)         if a < a_min
g_raw(a) = 1 / (1 + k * (a - a_min))       if a >= a_min
g(a)     = clamp(g_raw, g_min, g_max)
```

| Code parameter                 | Symbol | Baseline value | Active? |
|--------------------------------|--------|----------------|---------|
| attention_noise_threshold      | a_min  |           0.15 | Yes     |
| low_attention_penalty_slope    | k_low  |            2.0 | Yes     |
| attention_curve_exponent       | k      |            0.5 | Yes     |
| min_attention_noise_modifier   | g_min  |            0.3 | Yes     |
| max_attention_noise_modifier   | g_max  |           None | No      |

With g_max = None, the effective active parameters are **4**, not 5.

**Structural note:** The above-threshold branch `1 / (1 + k * (a - a_min))`
is a 2-parameter rational function (threshold + curvature) similar to
the reviewer's suggested `c_1 / (1 + a^{c_2})` form. The below-threshold
branch adds a third parameter (k_low) for asymmetric penalty when
attention is below the threshold. The floor g_min adds a fourth. Whether
to simplify is a design decision deferred -- under consideration (see
post_expert_review_plan.md Step 4).

### Summary: effective active parameter counts

| Category                     | Schema params | Active in presets |
|------------------------------|---------------|-------------------|
| Environment (time, teams)    |             5 |                 5 |
| Model (signal, learning)     |            14 |                10 |
| Governance (stop, attention, mix) |        16 |  6 vary + 2 fixed + 5 mix |
| Per-type-spec generation     |  ~15 per type |         ~15/type  |
| **Total governing behavior** |               | **~13 governance** |

The study's comparative findings rest on 6 governance parameters that
vary across archetypes, plus 2 shared governance parameters
(attention_min and stagnation_belief_change_threshold in Patient) that
are constant across most archetypes, plus 5 portfolio mix target
parameters (4 bucket targets + tolerance) that vary across all three
archetypes. The environment and generation parameters are held fixed
within each family.
