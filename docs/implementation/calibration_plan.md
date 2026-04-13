# Calibration Plan: Realistic workforce and initiative sizing

**Created:** 2026-03-28
**Context:** The simulation engine is working correctly and results are
internally consistent. The issue is calibration — the default presets
use unrealistic workforce and initiative parameters that produce
artifacts rather than governance findings. This plan recalibrates the
three baseline environment families to reflect realistic organizational
scale.

---

## Problem statement

Three calibration issues, all related:

1. **Pool composition.** balanced_incumbent has 35% right-tail
   initiatives (40 of 200). With average duration 142 ticks, right-tail
   churn creates a throughput bottleneck so severe that Patient Moonshot
   produces near-zero priced value — a model artifact, not a governance
   finding. A real balanced incumbent organization has 10-15% speculative
   bets, not 35%.

2. **Team size = 1 everywhere.** The workforce is 8 teams of 1 person.
   Every initiative requires 1 person. This makes all team assignments
   equivalent and eliminates the governance architecture dimension
   entirely. Real organizations have teams of 4-40 people and
   initiatives that require different-sized teams.

3. **Flywheel duration spread.** Flywheels range 20-60 ticks. A
   flywheel completing at tick 289 earns half the residual of one
   completing at tick 62 — a timing artifact that swamps the governance
   signal.

## Design principle

These are calibration changes to preset parameters. No engine logic
changes. The engine already supports arbitrary workforce decomposition
(`WorkforceConfig.team_size` accepts a tuple of varying sizes) and
initiative-level `required_team_size` matching. These mechanisms have
just never been exercised with realistic values.

---

## Change 1: Workforce — 200 people, mixed team sizes

### Current

8 teams × 1 person = 8 total labor.

### Proposed

200 total labor, mixed team decomposition. Proposed default:

| Team size | Count | Labor | Role |
|-----------|-------|-------|------|
| 5         | 20    | 100   | Small project squads — quick-wins, enablers, small right-tails |
| 10        | 8     | 80    | Medium teams — flywheels, larger enablers |
| 20        | 2     | 40    | Large program teams — large right-tail bets |
| **Total** | **30**| **220**|  |

Note: 220 total labor (not 200) to avoid making the two size-20 teams
a structural bottleneck. The extra 20 provides headroom for the
large-bet governance trade-off without distorting the overall scale.
If 200 is a hard constraint, use 18×5 + 8×10 + 2×20 = 210, or drop
one size-5 team.

This decomposition creates genuine governance trade-offs:
- Assign a size-10 team to a flywheel (required_team_size=8) with
  surplus, or use it on two initiatives it can't split across?
- Use a size-20 team on one big right-tail bet, or is that too much
  labor on speculation? With two size-20 teams, Patient Moonshot can
  pursue two large bets concurrently — but at what cost?
- When a size-10 team finishes, do you reassign it to a flywheel or
  an enabler?

### Governance architecture variation

Different archetypes could vary the decomposition:
- Aggressive Stop-Loss might prefer more small teams (higher throughput)
- Patient Moonshot might consolidate into fewer large teams (deeper
  investment per initiative)

For the first pass, use the same workforce across all archetypes within
an environment family (consistent with the current design — workforce is
environment, not policy). Architecture variation is a follow-up.

### Files to change

- `presets.py`: `make_baseline_workforce_config()` — change team_count
  and team_size (tuple of varying sizes)
- `docs/design/environment_families.md`: update workforce table

---

## Change 2: Initiative required_team_size — realistic team needs

### Current

All initiatives: `required_team_size = 1`.

### Proposed

| Family     | required_team_size | Rationale |
|------------|-------------------|-----------|
| Quick-win  | 5                 | Small focused sprint squad. Any size-5+ team can handle it. |
| Enabler    | 5-8 (drawn)       | Infrastructure work. Modest team, some need more. |
| Flywheel   | 8-10 (drawn)      | Core business investment. Needs a cross-functional team. Capped at 10 so size-10 teams can always staff them — the size-20 teams are reserved for large right-tail bets. |
| Right-tail | 5-15 (drawn)      | Speculative bets vary widely. Small exploratory probes (5) through large ambitious programs (15). Size 5-10 can be staffed by any size-10+ team; size 11-15 requires a size-20 team. |

The range for right-tails is 5-15, drawn uniformly. Of the 11 possible
values, 6 (size 5-10) can be staffed by any of the 10 medium-or-large
teams, while 5 (size 11-15) require one of the 2 size-20 teams. This
means roughly 45% of right-tails compete for size-20 slots — enough to
create the "one big bet vs. several small bets" governance trade-off
without making size-20 teams the binding constraint for most of the
pool.

A 15-person right-tail consumes ~7% of total labor by itself. With a
10-15% portfolio cap on right-tails, governance must choose between
two 5-person exploratory probes (fitting within a 10% cap) or one
15-person ambitious program (nearly saturating the cap alone).

Flywheel required_team_size is capped at 10 (not 12 as initially
proposed) to ensure that all 8 size-10 teams can handle any flywheel.
This avoids a bottleneck where flywheels compete with right-tails for
the scarce size-20 team slots.

### Implementation

`InitiativeTypeSpec` already has a `required_team_size_range` field
pattern (other ranges like `true_duration_ticks_range` exist). Need to
verify whether `required_team_size_range` exists on `InitiativeTypeSpec`
or needs to be added. If the type spec only supports a fixed
`required_team_size`, we may need to add a range field and draw from it
during pool generation, similar to how `true_duration_ticks_range`
works.

### Files to change

- `config.py`: Add `required_team_size_range` to `InitiativeTypeSpec`
  if not already present
- `pool.py`: Draw `required_team_size` from range during generation
- `presets.py`: Set per-family team size ranges in all environment
  families
- `docs/design/environment_families.md`: document new team size ranges

---

## Change 3: Pool composition — reduce right-tail share in balanced_incumbent

### Current

| Family     | balanced_incumbent | short_cycle_throughput | discovery_heavy |
|------------|-------------------:|----------------------:|----------------:|
| flywheel   |                 40 |                    40 |              40 |
| right_tail |                 40 |                    24 |              56 |
| enabler    |                 30 |                    30 |              30 |
| quick_win  |                 90 |                   106 |              74 |
| **Total**  |            **200** |               **200** |         **200** |

### Proposed

| Family     | balanced_incumbent | short_cycle_throughput | discovery_heavy |
|------------|-------------------:|----------------------:|----------------:|
| flywheel   |                 70 |                    50 |              40 |
| right_tail |                 20 |                    16 |              56 |
| enabler    |                 30 |                    30 |              30 |
| quick_win  |                 80 |                   104 |              74 |
| **Total**  |            **200** |               **200** |         **200** |

Key changes:
- **balanced_incumbent:** Right-tail drops from 40→20 (20%→10%).
  Flywheel rises from 40→70 (20%→35%). This reflects a real incumbent:
  mostly core business with some exploratory bets. Quick-win drops
  slightly to 80 to keep the total at 200.
- **short_cycle_throughput:** Right-tail drops from 24→16 (12%→8%).
  Flywheel rises to 50. This environment emphasizes throughput — more
  core business, fewer long bets.
- **discovery_heavy:** Unchanged. This is where right-tail
  concentration should be high. 56 right-tails (28%) is the point of
  this environment.

### Files to change

- `presets.py`: Update `InitiativeTypeSpec.count` in each environment's
  make function
- `docs/design/environment_families.md`: update composition table

---

## Change 4: Tighten flywheel duration range

### Current

Flywheel `true_duration_ticks_range`: 20-60 (5-14 months).

### Proposed

Flywheel `true_duration_ticks_range`: 25-45 (6-10 months).

This narrows the 3:1 spread to a 1.8:1 spread. Residual value
accumulation becomes more consistent across the cohort, so governance
regime differences are more cleanly attributable to policy rather than
to which flywheels happened to get staffed early.

### Files to change

- `presets.py`: Update flywheel type spec `true_duration_ticks_range`
- `docs/design/environment_families.md`: update duration table

---

## Change 5: Activate portfolio mix targets

### Current

`portfolio_mix_targets = None` in all three governance presets. The
`PortfolioMixTargets` mechanism, `_rerank_for_mix_targets()`, and
`compute_current_portfolio_mix()` all exist and work — they are just
never activated.

### Proposed

Set per-archetype portfolio mix targets as a governance differentiator:

| Bucket     | Balanced | Aggressive Stop-Loss | Patient Moonshot |
|------------|----------|---------------------|-----------------|
| flywheel   | 40%      | 35%                 | 25%             |
| right_tail | 10%      | 5%                  | 25%             |
| enabler    | 15%      | 10%                 | 15%             |
| quick_win  | 35%      | 50%                 | 35%             |
| tolerance  | 10%      | 10%                 | 15%             |

These are soft targets (tolerance allows drift). The key governance
signal: Patient Moonshot allocates 25% to right-tails (willing to make
big speculative bets), while Aggressive Stop-Loss caps at 5% (minimal
speculation, maximize throughput).

With ~220 total labor:
- Balanced: ~22 people on right-tails (2-4 concurrent size-5-to-15
  right-tail teams)
- Aggressive Stop-Loss: ~11 people (1-2 concurrent)
- Patient Moonshot: ~55 people (4-11 concurrent, including large bets)

**Note on Patient Moonshot in balanced_incumbent:** With only 20
right-tail initiatives in the balanced_incumbent pool, the 25% target
(~55 people on right-tails) may be aspirational rather than
achievable. At average required_team_size of ~10, that implies 5
concurrent right-tails, but many will be low quality and quickly
stopped (even by Patient Moonshot), so the regime may not find enough
viable right-tails to saturate the target. This is fine conceptually
— Patient Moonshot in a balanced incumbent environment is swimming
against the current — but the verification should expect Patient
Moonshot's actual right-tail labor share to fall below its target in
balanced_incumbent. In discovery_heavy (56 right-tails), the target
should be closer to satisfiable.

This is where the right-tail team size variation (5-15) interacts with
the portfolio constraint to create the "one big bet vs. several small
bets" trade-off.

### Files to change

- `presets.py`: Set `portfolio_mix_targets` on each governance config
- `docs/design/environment_families.md`: add mix target table to
  governance archetype section

---

## Sequencing

All five changes are independent at the code level (different fields
in the same config structures), but should be validated together
because they interact at the simulation level.

```
1. Workforce (200 labor, mixed teams)     -- presets.py, config.py
2. Initiative team sizes (drawn ranges)   -- config.py, pool.py, presets.py
3. Pool composition (rebalanced)          -- presets.py
4. Flywheel duration (tightened)          -- presets.py
5. Portfolio mix targets (activated)       -- presets.py
   |
   v
6. Update design docs                     -- environment_families.md, calibration_note.md
7. Update/fix tests                       -- test_presets.py, others asserting old values
8. Validation run                          -- baseline_governance_campaign.py --seeds 5
```

Steps 1-5 can be implemented in one pass through presets.py (plus
config.py and pool.py for the team size range). Step 6 updates the
docs. Step 7 fixes any tests that assert specific preset values.
Step 8 is a validation run to verify the recalibrated simulation
produces sensible results.

---

## What does NOT change

- Engine logic (tick.py, runner.py, learning.py, etc.)
- Governance primitives (governance.py) — all mechanisms already exist
- Policy logic (policy.py) — mix target reranking already works
- Reporting pipeline (tables.py, figures.py, run_bundle.py)
- Bundle format and validation
- Observation boundary, CRN structure, belief updates

---

## Verification criteria

After recalibration, run `python scripts/baseline_governance_campaign.py --seeds 5`
and check:

1. **Balanced regime produces meaningful value.** Total priced value
   should be substantial, not dominated by Aggressive Stop-Loss.
2. **Patient Moonshot produces non-zero value.** It should produce
   less priced value than Balanced but more than near-zero, and surface
   more major wins.
3. **Portfolio mix targets are reflected in outcomes.** Aggressive
   Stop-Loss should have minimal right-tail labor; Patient Moonshot
   should have more.
4. **Team size creates governance trade-offs.** Initiatives requiring
   larger teams should take longer to get staffed (fewer eligible
   teams), creating a visible queue effect.
5. **Flywheel residual spread is narrower.** The difference between
   early-completing and late-completing flywheels should be smaller.
6. **Trajectory figures show realistic lifecycles.** Flywheels should
   complete in the first half of the horizon with substantial residual
   runway. Right-tails should show the exploration/exploitation tension.
7. **Pool exhaustion tick for each environment × policy combination.**
   If any combination exhausts the pool before tick 200, the
   late-horizon dynamics are driven by residual accumulation on a
   closed portfolio rather than active governance decisions — that
   changes what the study is measuring. Ideal: pool exhaustion in the
   final quarter (tick 230+) or not at all.

---

## Risks

- **Pool clearing too fast.** Going from 8 concurrent slots to 30 is
  a 3.75x increase in throughput capacity. Back-of-envelope: with
  30 teams and an average initiative duration of ~35 ticks across all
  families, theoretical throughput is ~(30 × 313) / 35 ≈ 268
  completions over 313 ticks — enough to clear the 200-initiative
  pool. However, this overestimates actual throughput because:
  (a) not all teams can staff all initiatives (team-size matching),
  (b) right-tails take 104-182 ticks and tie up teams,
  (c) ramp periods reduce effective throughput,
  (d) some initiatives will never get staffed (no eligible team free).
  Still, pool exhaustion before tick 200 is a real risk. If it occurs,
  the late-horizon dynamics become about residual accumulation on a
  closed portfolio rather than active governance. Mitigation: if the
  validation run shows early exhaustion, increase the pool size from
  200 to 250-300 initiatives or increase initiative durations.

- **Team size mismatch.** If the workforce decomposition doesn't have
  enough large teams for the initiatives that need them, some
  initiatives will be permanently unstaffable. Verify that every
  `required_team_size` in the pool has at least one team that can
  satisfy it. With the revised decomposition (20×5 + 8×10 + 2×20),
  all initiatives with required_team_size ≤ 20 are staffable. The
  binding constraint is that only 2 teams can handle size 11-20
  initiatives.

- **Test breakage.** Many tests in `test_presets.py` assert specific
  parameter values from the current calibration. These will need
  updating.
