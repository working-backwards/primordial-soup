# Intake Discipline — Findings and Incremental Plan

**Status:** diagnostic; 2026-04-18
**Authors:** Claude + user, from the first end-to-end run under the Phase 2
single-run report.

## Purpose

Capture what we observed on the first real run of the single-run report
after the exec-usability work, diagnose the root cause, and lay out an
incremental implementation path where the simplest first change already
yields a usable simulator. The point is that any stopping place below is a
working answer — each subsequent step improves it.

This document does not change code. It records findings and proposes the
sequence of changes for the next implementation session.

## Triggering run

- Bundle: `results/2026-04-18_154448_balanced_incumbent_balanced/`
- Preset: `templates/presets/balanced_incumbent_balanced.yaml`
- Seeds: 42, 43, 44
- Horizon: 313 weeks (~6 years)
- Value unit: `units` (default; baseline_value_per_team_week not set)

The run surfaced a large gap between simulated governance behaviour and
what a new executive auditing a six-year record would call "appropriate
project-starting decisions." This document captures that gap.

## Headline observations (per-seed means across the cohort)

Per the governance-actions table in `report/report.md`:

| Family | Started (mean) | Completed | Stopped | Never started |
|---|---|---|---|---|
| Quick-wins  | 113.3 | 81.0 | 28.0 | 4.0 |
| Flywheels   | 70.0  | 30.3 | 0.0  | 37.0 |
| Enablers    | 30.0  | 10.3 | 1.3  | 18.0 |
| Right-tails | 309.7 | 18.3 | 267.7 | 3.3 |

Aggregate: 297 stops / 140 completions per seed. 268 of 297 stops
(~90%) are right-tail, driven by the right-tail refresh mechanism.

Narrative line from the report: *"Governance stopped 297 initiatives and
completed 140. Quick-wins: 28 stopped / 81 completed; Flywheels: 0 stopped
/ 30 completed; Enablers: 1 stopped / 10 completed; Right-tails: 268
stopped / 18 completed."*

## Event-log diagnosis: which stop rules fired?

From `outputs/event_log.parquet` (across 3 seeds, 891 stop events):

| Family      | Total | confidence_decline | tam_adequacy | stagnation |
|-------------|-------|-------------------|--------------|------------|
| quick_win   | 84    | 84                | 0            | 0          |
| enabler     | 4     | 3                 | 0            | 1          |
| right_tail  | 803   | 538               | 232          | 33         |
| flywheel    | 0     | —                 | —            | —          |

Every QW stop was confidence-decline. No other stop rule fired on QWs.

## Intake-prediction accuracy

From `outputs/initiative_outcomes.parquet`, comparing governance's
`initial_quality_belief` (the post-screening intake belief) to `true_quality`
(latent) for activated initiatives:

| Family | Pearson r(belief, truth) | Stopped: belief → truth | Completed: belief → truth |
|---|---|---|---|
| quick_win  | **+0.94** | 0.116 → 0.112 | 0.645 → 0.633 |
| flywheel   | +0.43 | (none stopped) | 0.917 → 0.829 |
| enabler    | +0.61 | 0.265 → 0.244 | 0.660 → 0.587 |
| right_tail | +0.61 | 0.283 → 0.237 | 0.780 → 0.750 |

**Key reading.** Governance is **not** poor at predicting quality. For
QWs the correlation is +0.94 — essentially prescient. The stopped QWs had
an intake belief of 0.116 and an actual quality of 0.112. Governance saw
these were bad and activated them anyway.

For right-tails: 803 of the 858 activated RTs were stopped, with mean
intake belief 0.28 (matching actual 0.24). Governance knew most were
unlikely to pan out at the moment it chose to activate them.

Completed initiatives show a small "winner's curse" bias — belief is
0.01–0.09 above truth — a standard selection effect, not a calibration
bug.

## Range-anchor discrepancies

Four headline metrics fell well outside the curated anchors (from
`src/primordial_soup/report_ranges.py`):

| Metric | Value | Anchor | Delta |
|---|---|---|---|
| Value from completions | 8% | 40–70% | Sharply low |
| Value from residual    | 92% | 30–55% | Sharply high |
| Ramp overhead          | 106.2% | 3–8% | An order of magnitude high |
| Initiatives stopped    | 297 | 40–100 | ~3× anchor |

The first two are the same finding expressed two ways: residual streams
dominate, completions are a small share. That matches the FW/EN
under-utilization (few completions contributing lumps) combined with
residual-heavy QWs + FWs that did complete.

The ramp-overhead number is mathematically sound but its definition
(`cumulative_ramp_labor / total_team_ticks`) permits values > 100% when
teams reassign more than once — which they do, heavily, under right-tail
churn. Display intent and definition need reconciling.

## Business-audit interpretation (new-exec framing)

Treating the six-year record as a real business history, three failures
stand out:

1. **Greenlit quick wins you already knew would fail.** ~19 QWs started
   per year, ~5 killed. Intake belief for the killed ones was 0.11 —
   governance correctly predicted they were bad bets and started them
   anyway. By definition a "quick win" is a sure thing; if a quarter of
   them fail, the category label is misleading or the discipline is
   missing.

2. **Churned through moonshots.** ~50 RT attempts per year, ~45 killed
   per year. Implausibly high for a mature incumbent. Only ~3 surfaced
   breakthroughs per year.

3. **Left compounding work on the table.** 37 of 70 flywheels and 18 of
   30 enablers never started. These are the compounding investments. Six
   years of under-investment shows up as a terminal productivity
   multiplier of 1.53× — ordinary, not compounded.

**Root cause.** The simulator activates low-quality initiatives because
the balanced policy has no mechanism to refuse. It rank-orders by belief
and greedy-fills labor. Once labor is free and nothing higher-ranked is
left in the pool, it activates the best of what's available — even if
that is a 0.12-belief QW it already correctly predicts will fail. There
is no:

- Minimum-belief intake floor (go/no-go threshold)
- Portfolio mix target biasing allocation toward FW/EN
- Opportunity cost for keeping a team idle (`baseline_value_per_tick`
  defaults to 0.0)

## Incremental implementation plan

Philosophy: **start with the smallest change that produces a plausible
answer.** Each subsequent step is a refinement. If we stop at any step,
the simulator still runs, still produces a report, and the output is
more plausible than where we are today.

Each step below is independent and can land in its own commit.

### Step 1 — Intake belief floor on the operating policy

**What.** Add `intake_belief_threshold: float | None` to `GovernanceConfig`.
At the per-tick activation step, if a candidate initiative's post-screening
belief is below the threshold, the policy declines to activate and the team
stays idle. Default `None` preserves current behaviour.

Preset values (starting guesses, subject to calibration in Step 4):
- `balanced`: 0.35
- `aggressive_stop_loss`: 0.50
- `patient_moonshot`: 0.20

**Why first.** Directly addresses the root cause observed above. One
configuration field, one policy-step change. Every subsequent step
works better with this in place; none of them are prerequisites for this.

**Effect.** QWs below ~0.35 stop getting activated. RT churn drops. FW
and EN activation pressure increases (because labor that used to go to
marginal QWs/RTs is now free). Terminal value and completion share both
rise. The "discipline gap" closes.

**Watch for.** Over-tightening: threshold too high can starve the
portfolio. Validate on a 10-seed cohort before locking the preset values.

### Step 2 — Enable `portfolio_mix_targets` in the canonical presets

**What.** The field already exists on `GovernanceArchitectureSpec` and
plumbs into policy. It's null in all nine preset YAMLs. Set targets
aligned to the environment family:
- `balanced_incumbent`: QW 40%, FW 30%, EN 20%, RT 10%
- `short_cycle_throughput`: QW 55%, FW 25%, EN 15%, RT 5%
- `discovery_heavy`: QW 25%, FW 25%, EN 20%, RT 30%

**Why second.** Even with an intake floor, without mix targets governance
will over-index on the family with the highest belief distribution (QWs).
Mix targets push the policy to reserve capacity for flywheels and
enablers, correcting the "50%+ never started" finding.

**Effect.** FW and EN activation rates rise to target levels. Terminal
productivity multiplier rises as enablers complete more often. The
long-cycle compounding mechanism becomes visible.

**Watch for.** Over-specifying the targets without the intake floor
just forces bad FW/EN activation. Do Step 1 first.

### Step 3 — Positive `baseline_value_per_team_week` in calibrated presets

**What.** Set `architecture.baseline_value_per_team_week: 0.1` (the
previously calibrated value) in the canonical balanced preset and any
other presets we want to show with realistic baseline accrual. The field
already landed on the authoring surface in Phase 1.

**Why third.** Gives idle labor a concrete opportunity cost. Makes the
intake floor have an economic interpretation ("don't greenlight below X
because baseline produces more"). Also surfaces as ~3–5% of total value in
the report (the spec's #4 metric), which currently reads 0% and under-
weights a real source of business value.

**Effect.** Small positive share under "Value from baseline work."
Supports Step 1's discipline rule intuitively: idle is productive, so the
policy isn't "wasting" teams by declining to activate marginal work.

### Step 4 — Calibration: QW Beta and RT refresh degradation

**What.**
- Narrow the QW quality Beta so < 10% of draws fall below the intake
  threshold set in Step 1. Current Beta produces ~25% below 0.3.
  Candidate: Beta(5, 2) with mean 0.71 or Beta(4, 2) with mean 0.67.
- Raise `right_tail_refresh_quality_degradation` from 0.0 to a value that
  makes each re-attempt progressively less attractive. The frontier
  design already supports this; the default just sets it off.

**Why fourth.** Once discipline mechanics are in place (Steps 1–3), the
remaining mismatch is the pool itself. Narrowing the QW Beta makes the
family match its business label. Raising RT refresh degradation brings
the moonshot-attempt rate down to plausible incumbent levels (target: 3–8
RT attempts per year, not 50).

**Effect.** The stops-per-year number falls from ~300 to the 40–100
range. The category labels match their practitioner semantics. The
balanced-incumbent preset models a balanced incumbent.

### Step 5 — Reporting: separate RT churn from first-attempt stops

**What.** In `tables.py` / `report_gen.py`, distinguish "initiative
stopped" events into two sub-categories:
- *First-attempt stops* — the prize had not been previously attempted.
- *Refresh attempts* — a re-attempt on a prize whose previous try was
  stopped.

Narrative then reads: *"Right-tails: 18 completed. 48 first-attempt
stops; 220 refresh attempts on prizes previously stopped."*

**Why fifth.** Even with Steps 1–4, the frontier refresh mechanism
produces multiple attempts per prize by design. The current "stopped"
count conflates governance decisions (stopping attempts) with structural
refresh (generating new attempts). Separating the two makes the
governance story legible.

**Effect.** The headline 297-stops number falls to something more like
"47 first-attempt stops, 250 refresh attempts." The governance-actions
paragraph reads plausibly at a glance.

### Step 6 — Ramp-overhead definition

**What.** Redefine `ramp_labor_fraction` from
`cumulative_ramp_labor / total_team_ticks` (unbounded) to
`ramp_team_ticks / total_team_ticks` (fraction of team-ticks spent in
any ramp state, bounded by [0, 1]). Or rename the current metric to
"Ramp labor intensity" to signal that > 100% is meaningful.

**Why sixth.** The current metric correctly represents labor cost of
switching but rendered as "106.2%" it's confusing. Either fix the
display or rename the metric. Low priority; fix with the reporting pass.

## Decisions deferred

**1. Where does activation discipline live — operating policy or
architecture?**

Step 1 above puts it on `GovernanceConfig` (policy-scope). Alternative:
it's a structural choice (`GovernanceArchitectureSpec`) like
`low_quality_belief_threshold`. A third option is both — architecture sets
a minimum floor, operating policy sets an additional stricter floor.

Recommend: start with policy-scope (Step 1), re-evaluate after Step 2
lands. Moving it to architecture later is a straightforward refactor.

**2. Is "exec generates new opportunities" in scope?**

A real exec under-supplied with good projects commissions new ones. Today
the initiative pool is fixed at run start (with frontier refresh, which
models "the environment supplies new opportunities," not "the exec
creates them"). The current scope per `canonical_core.md` treats the
pool as exogenous.

Recommend: leave out of scope for now. Revisit only if Steps 1–4 still
leave the model feeling unnatural.

**3. Should `balanced_incumbent` be renamed or recalibrated?**

The preset as it stands today models an undisciplined exploration-heavy
organization, not a balanced incumbent. After Steps 1–4, re-run and
check whether the outputs match the practitioner definition. If yes,
keep the name. If the calibration still feels off, have the design-doc
conversation about what "balanced incumbent" should mean.

## Working-session handoff

If someone (fresh model or user) picks this up:

1. Read this file.
2. Read `memory/project_status.md` for current state.
3. Read `docs/design/exec_intent_spec.md` and
   `docs/design/single_run_report_spec.md` for the feature context.
4. Start with Step 1. It's small, self-contained, and unblocks everything
   else.
5. Re-run `scripts/run_design.py templates/presets/balanced_incumbent_balanced.yaml`
   after each step and compare against the headline observations above.
6. If a step's results still show the discipline gap, diagnose before
   tweaking (per `memory/feedback_diagnose_before_fixing.md`): is it real
   finding / calibration / reporting / scope?
