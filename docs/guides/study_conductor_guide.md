# Primordial Soup: Study Conductor Guide

This document is for the person conducting the study. Its purpose is to explain what the simulation is, what decisions the study conductor is actually making, what the simulator holds fixed, what happens during a run, what is observed versus hidden, which metrics matter, and how to think about the outputs. It is not intended to replace the lower-level technical docs. Instead, it is meant to give the operator a coherent mental model of the whole study so that runs can be designed, executed, and interpreted consistently.

Primordial Soup is a discrete-time Monte Carlo study of governance over a fixed portfolio of initiatives. At the start of a run, the study defines a fixed opportunity pool, a realized workforce, a governance policy, and a set of world and model assumptions. During the run, governance repeatedly decides which staffed initiatives to continue or stop and which free teams to assign to unstaffed opportunities. The study is designed to compare governance choices under uncertainty, not to simulate hiring markets, politics, morale, or dynamic idea generation. The central question is how governance decisions shape discovery, durable value creation, capability building, and portfolio outcomes over time.

The simulation advances in discrete ticks, where one tick represents one calendar week. The canonical horizon is 313 ticks, approximately six years — a reasonable long-term planning horizon for large incumbent firms. Different organizational contexts may warrant shorter or longer horizons.

The study is organized around three layers. The first is **environmental conditions**, which define the opportunity pool, the time horizon, and the basic world assumptions. The second is **governance architecture**, which defines how leadership organizes the workforce and, when desired, how it wants active work distributed across initiative categories. The third is **operating policy**, which defines how governance actually makes per-tick decisions once the run is underway. If the study conductor loses track of which choice belongs to which layer, the experiment becomes hard to interpret, so it is worth keeping these distinctions explicit.

The environment layer defines which kinds of initiatives exist in the world at the start of the run and how many of them exist. In the current study, the opportunity pool is fixed at run start. The study does not continuously create new initiatives during the run. That means the quality of experiment design depends heavily on how the initial pool is constructed. If the portfolio intent of the study requires sustained right-tail activity, for example, the initial pool must contain enough right-tail opportunities to support that question. Pool exhaustion is therefore not merely an implementation detail. It is often an experiment-design problem.

The governance architecture layer defines total labor endowment and workforce decomposition. The conductor decides how many total people or labor units exist, how many teams there are, how large each team is, and how quickly teams ramp when switched. Teams are atomic and unsplittable. A team can work on at most one initiative at a time, and a partially staffed team is not a modeled concept. Team decomposition matters because it determines both the breadth of simultaneous work and the depth of staffing available for any one opportunity. It also matters because the simulator now treats larger assigned teams as affecting learning when an initiative’s minimum staffing requirement has been exceeded.

The governance architecture layer may also include portfolio-mix targets. These are not engine-enforced quotas. They are policy-side preferences about how active work should be distributed across initiative families such as flywheel, right-tail, enabler, and quick win. In the current implementation, these targets are keyed by canonical `generation_tag` labels and are used as a soft secondary assignment preference when new teams are assigned. They do not create permanent team reservations and they do not force the policy to leave teams idle when no suitable candidate exists.

The operating-policy layer defines the decision rules governance uses each tick. In practical terms, the policy decides which active staffed initiatives to continue or stop, and it decides which free teams to assign to which unassigned initiatives. In the current study, policy can vary in patience, stop-loss aggressiveness, confidence thresholds, stagnation handling, and attention posture. Different named policies implement different combinations of those settings. The engine does not make governance decisions itself. It only applies the consequences of the decisions the policy returns.

## The initiative families

The canonical study uses four initiative families. These are generation and reporting categories, but they matter because they correspond to different economic and strategic roles.

**Flywheel initiatives** are compounding work. They do not generate meaningful direct value during execution. Their main payoff comes after completion, when they begin contributing residual value over time. In the current v1 semantics, flywheels are residual-only. They are intended to model things like installed bases, distribution improvements, automation, and durable operational mechanisms whose benefits continue after the original team is redeployed.

**Right-tail initiatives** are exploratory bets. They do not produce ordinary direct value during exploration. Their success condition in the canonical study is not ordinary completion revenue but the surfacing of a major win. A major win is recorded as a distinct event rather than priced as ordinary direct value inside the study horizon. If a right-tail initiative is not a major win, then its output is information, not revenue. Right-tail work is therefore valuable partly because it can discover transformational opportunities and partly because it can be stopped once the evidence turns against it.

**Enabler initiatives** improve the organization’s ability to learn and execute elsewhere. They do not produce direct value. Instead, they increase a portfolio-level capability scalar that reduces effective strategic signal noise for staffed initiatives in future ticks. The current study deliberately represents this with one portfolio capability mechanism rather than many separate operational pathways. In business terms, enablers make future initiatives easier to evaluate accurately by improving the organization’s instrumentation and signal quality. They are the investment in learning infrastructure — better data pipelines, sharper diagnostic tools, stronger evaluation frameworks — that lets leadership distinguish good bets from bad ones earlier and with more confidence. A governance regime that neglects enablers may save short-term capacity but gradually loses the ability to tell whether its other investments are working.

**Quick wins** are bounded one-time opportunities with low uncertainty and small ceilings. They are meant to be completion-lump-dominant. In the current intended v1 semantics, they produce a meaningful completion lump and at most a small residual tail. They are attractive because they are easy to understand and complete, but they can crowd out slower compounding or exploratory work if governance overweights immediate visible returns.

## What an initiative is

An initiative has two kinds of properties: latent properties that the simulator uses internally, and observable or reported properties that governance is allowed to see.

The most important **latent** properties are the initiative’s true underlying quality, its true execution characteristics, and any hidden randomness that drives observed signals. Governance does not see these directly. The observation boundary is a load-bearing part of the study. Governance should not have access to latent ground truth and should not be allowed to branch on hidden state.

The most important **observable** or policy-visible properties of an initiative include its identifier, lifecycle status, current quality belief and execution belief, the number of staffed ticks so far, whether it is currently staffed, the assigned team if any, any observable bounded-prize information such as a ceiling, capability-relevant attributes that are meant to be visible, `required_team_size`, and, in the current portfolio-mix design, `generation_tag` as a policy-visible metadata field for category targeting. Governance also sees the structured outputs of completed and stopped initiatives through the reporting surfaces.

An initiative also has value-channel semantics. In the current study, an initiative can contribute through one or more of the following: a completion lump, a residual stream after completion, a major-win event, or capability contribution. Not all channels apply to all initiative families. These channels remain separate in reporting because part of the purpose of the study is to understand not only how much value was created but what kind of value it was.

An initiative now also has a **minimum staffing threshold**, represented through `required_team_size`, and may have a **staffing-response scale**. The threshold says the smallest team that can work the opportunity at all. A team smaller than this threshold cannot be assigned. A team equal to the threshold works at baseline. A larger team can accelerate learning with diminishing returns. This is a modeled study hypothesis, not an asserted empirical fact. Different families or experiment configurations may use different staffing-response assumptions because the study is meant to test whether staffing intensity matters and how strongly.

## What the conductor decides before a run

Before starting a run, the study conductor is effectively making four types of choices.

First, the conductor chooses the **world**: which environment family to use, how large the initial opportunity pool should be, what the time horizon should be, and whether any family-specific assumptions such as right-tail abundance should be changed.

Second, the conductor chooses the **workforce architecture**: total labor, team count, exact team sizes, and ramp or switching-cost assumptions. This is one of the most important choices in the study because it shapes both breadth and depth. A large number of small teams favors portfolio breadth. A smaller number of larger teams favors deeper staffing.

Third, the conductor chooses any **portfolio-architecture preferences**, such as desired active-work mix across flywheel, right-tail, enabler, and quick win. These are governance-intent inputs, not engine constraints.

Fourth, the conductor chooses the **operating policy posture**. This determines how aggressively governance stops weak initiatives, how patient it is with potentially high-upside work, how it reacts to stagnation, and how it prioritizes assignments among available opportunities.

The conductor also chooses the seed strategy. Because this is a Monte Carlo study, many meaningful conclusions only emerge across multiple seeds. A single run can be illustrative, but it is usually not enough for a governance conclusion.

## How to start a simulation

A simulation run begins when the workbench or study script resolves all high-level inputs into concrete config objects and a fully resolved initiative pool. The engine should not receive abstract business-language requests. It receives resolved initiatives, a realized workforce, model parameters, governance parameters, and the horizon. The current study supports both workbench-style authoring and direct scripting. In practice, the conductor should think of a run as beginning only after these authoring choices have been fully resolved and inspected.

A good operational habit is to validate the scenario before running it. That means checking at least the following. Does the pool contain enough initiatives of the relevant categories to support the experiment? Does the team decomposition sum to the stated total labor? Do the portfolio targets sum properly? Are staffing-response assumptions aligned with the intended hypothesis? Is the horizon long enough to observe the effects of compounding or exploration? These are experiment-design questions, not mere syntax checks.

## Calibrating executive attention budget

The `exec_attention_budget` parameter controls how much total executive attention is available each tick for reviewing active initiatives. Getting this parameter right matters because it determines whether attention allocation is a meaningful governance lever or an irrelevant formality.

The attention budget should be high enough that attention is not binding in every governance regime, but low enough that attention allocation still matters. If the budget is so generous that every initiative always receives maximum attention regardless of policy, then differences in attention-allocation strategy across regimes cannot produce observable effects. If the budget is so tight that every regime is always fully constrained, then the study is measuring rationing behavior rather than prioritization behavior.

The canonical posture for the main governance sweep is that `exec_attention_budget` should be non-binding: set conservatively enough that governance policy determines realized attention, not engine-side budget clamping. Sensitivity to `exec_attention_budget` as an environmental parameter is analyzed separately, in a dedicated experiment distinct from the governance sweep (see `docs/design/experiments.md`).

The conductor should verify the budget through pilot runs before committing to a full campaign. The key diagnostic is whether realized attention allocation routinely hits the ceiling. If it does in most regimes, the budget is too tight for a governance-comparison sweep. If it never binds in any regime, it may be set higher than necessary but is not causing harm.

As an initial pilot heuristic, start with `exec_attention_budget` around `team_count * 1.2` and adjust based on what the pilot shows. This number is a starting point for calibration, not a modeled assumption. Do not treat it as a recommended setting — the correct budget depends on the specific team decomposition, policy posture, and study question. Use `scripts/attention_calibration_check.py` to systematically check budget-binding status across archetypes and seeds before finalizing the budget for a campaign. The script runs each governance archetype across multiple seeds and reports realized attention utilization, near-binding tick counts, and a summary verdict.

## What happens at each tick

Each tick follows a fixed rhythm.

At the start of the tick, the world has a current initiative state, team state, capability state, and belief state. Some initiatives are staffed and active, some are complete, some are stopped, and some remain unassigned.

The policy observes the current world through the allowed observation surface. It sees current initiative beliefs, staffing state, portfolio summaries, and any policy-visible metadata such as category tags used for portfolio-mix preferences. It does not see latent truth.

For each active staffed initiative, the policy must decide whether to continue or stop. If an initiative is stopped, the stop takes effect at the start of the next tick, and the team becomes free at that time.

For free teams, the policy determines assignment. It ranks candidate unassigned initiatives according to its internal rules and then applies any portfolio-mix preferences as a soft secondary ordering. A category that is under target can be favored for the next assignment, but the policy is not required to leave a team idle if no suitable candidate exists.

Once assignments for the tick are determined, the simulator applies the consequences. Staffed initiatives update their learning and execution-related state. In the current staffing-intensity design, assigned team size affects learning when the assigned team exceeds the initiative’s minimum staffing threshold, with diminishing returns. Completed initiatives may trigger direct value channels, residual activation, major-win events, or capability contributions depending on their configuration. Capability then affects future signal quality at the portfolio level. Residual value streams continue to produce value in later ticks without further staffing. This is why free value per tick is an important metric: it measures value being generated by completed mechanisms without deploying new labor.

The tick then advances, and governance will act again at the next review.

## The governance decisions in complete form

For the study conductor, the full set of governance-relevant choices can be understood in two groups: ex ante architecture choices and per-tick operating choices.

The ex ante architecture choices are: total labor endowment, team count, exact team sizes, ramp or switching-cost assumptions, category-level portfolio-mix targets, and the choice of operating policy family.

The per-tick operating choices are: for each active staffed initiative, continue or stop; for each newly free team, whether to assign it and to which unassigned initiative; and, through the policy’s ranking logic, which opportunities to prioritize when there are more candidates than available teams.

That is the full practical governance surface in the current study. Anything beyond that, such as creating new initiatives during a run or fractionally splitting teams across work, is out of scope for the canonical simulation as it currently stands.

## Canonical governance lever set (frozen)

The following governance decision surface is frozen for the current study. These are the levers that governance regimes can vary, and no additional governance semantics should be added without an explicit design decision.

- **Sourcing**: which opportunities to pursue from the pool (assignment ranking and selection)
- **Executive attention allocation**: how much attention each active initiative receives, subject to the budget
- **Stop/continue criteria**: when to terminate initiatives based on strategic and execution signals
- **Cost-overrun tolerance**: how governance responds to initiatives that exceed planned execution cost
- **Review discipline**: attention as a function of portfolio state (attention posture)
- **Reassignment**: which freed teams go where when initiatives are stopped or completed

This lever set defines the complete governance decision surface. Extensions — such as mid-run initiative sourcing, dynamic budget adjustment, or protected-initiative designations — are out of scope for the canonical study and require an explicit design decision before implementation.

## What is tracked during and after a run

A run tracks both outcome metrics and mechanism metrics.

At the highest level, the study tracks cumulative realized value. This should always be decomposed by value channel. The conductor should expect to see at minimum lump-sum value, residual value, and major-win counts. Because different initiative families are meant to realize value differently, it is often more important to look at value by channel than at total value alone.

Residual value should also be decomposed by initiative family where possible. In the current intended semantics, flywheels should dominate this channel, quick wins may contribute a small tail, enablers should contribute nothing directly, and right-tail should not ordinarily contribute through ordinary residual or lump value.

The study also tracks capability effects. Enablers raise a portfolio-level capability scalar, and the most important capability outputs are usually peak portfolio capability and terminal portfolio capability. Peak capability shows how much the organization’s learning environment improved at its best moment during the run. Terminal capability shows what remains at the end of the horizon after decay.

The study should also track lifecycle counts and flows: how many initiatives of each family completed, how many were stopped, when pool exhaustion occurred, and how much labor was consumed by each category. These are not merely descriptive. They often explain why total-value metrics moved.

The study should track at least one belief-quality metric such as mean absolute belief error or a related estimate-quality metric. Even if this is not always intuitive in business language, it is one of the clearest direct signals of whether the governance regime is learning effectively.

Idle team-tick percentage is also important. It measures unused organizational capacity. However, it should not be interpreted simplistically. Higher utilization is not always better if low-value work is being staffed for the sake of utilization. That is why it should be interpreted alongside value by channel and category-level completions.

For studies involving staffing intensity, the conductor should also care about mechanism metrics such as average assigned team size by family, time-to-completion by family, time-to-stop by family, and possibly average staffed duration before stop or completion. These are often more informative than top-line value when trying to understand why a staffing-intensity treatment changed outcomes.

## Reporting and interpretation

Reporting should separate outcome from mechanism. Outcome answers what happened. Mechanism answers why it happened.

The outcome layer should include total cumulative value, value by channel, major wins, capability endpoints, and overall portfolio summaries. The mechanism layer should include counts by family, lifecycle transitions, labor use by family, idle capacity, pool exhaustion, and belief-quality metrics. For staffing-intensity studies, a third lens is needed: how team size and category allocation interacted. Without this, the conductor can see a value lift but not know whether it came from better flywheel compounding, faster right-tail triage, stronger capability accumulation, or something else.

The conductor should interpret results as conditional comparisons rather than as proof of a single winning governance regime. Different governance postures can create different organizational futures because they change which opportunities remain available, how quickly capability accumulates, how much residual value is built, and how aggressively the organization redeploys its effort. As a result, the honest summary of a study is usually not "regime A is best," but rather "under conditions X, regime A outperforms regime B on dimension Y while underperforming on dimension Z; under conditions W, that relationship changes." This is not a weakness of the study. It is one of the main reasons to run it.

The conductor should not overinterpret a single seed. The study is stochastic by design. Any meaningful governance conclusion should be grounded in multiple seeds, and ideally in sensitivity runs that isolate the relevant channel. For example, if staffing intensity appears to improve total value, the conductor should test whether the lift is robust across seeds, which initiative family drives it, and whether stronger staffing-response assumptions produce diminishing rather than explosive gains.

The conductor should also watch for experiment-design failure. Pool exhaustion is one example. If the study runs out of the kind of opportunities the scenario was meant to sustain, then the interpretation of later ticks becomes difficult. That does not necessarily mean the engine is wrong. It often means the experiment was not designed with enough supply of the relevant opportunity family.

## Elements that are easy to miss

Two additional elements are easy to overlook but matter a great deal.

The first is reproducibility. The study uses explicit random seeds and dedicated random streams so that the same underlying world can be compared under different governance regimes. This is not just a convenience. It is what allows differences in outcomes to be attributed to governance rather than to different opportunity pools.

The second is the authority structure of the study. Conceptual documents define what the families are supposed to mean. The canonical preset parameterization defines how those meanings are instantiated in the executable model. Reporting and translation surfaces should follow those authorities, not quietly redefine them. When these layers drift, the study becomes hard to trust even if the code runs.

## Pre-study health checks

Before interpreting outcomes from any run or campaign, verify that the study design is sound. The following checklist addresses the most common experiment-design failures. Each item includes a specific verification method.

- [ ] **Pool / frontier supply: is the opportunity supply deep enough for the intended horizon and policy?** Check via `--dry-run` in `scripts/run_design.py` or by reviewing the `opportunity_supply` section in the YAML. The relevant YAML fields are: `frontier_degradation_rate` (per-family quality decline rate as opportunities are consumed), `right_tail_prize_count` (number of major-win prizes seeded in the right-tail frontier), and `right_tail_refresh_degradation` (quality decay applied when right-tail prizes are refreshed). After Stage 3, also check per-family frontier depth settings. If the frontier degrades too quickly relative to the number of resolved initiatives, late-run initiatives will be drawn from a depleted quality distribution and the study may be measuring frontier exhaustion rather than governance quality.

- [ ] **Attention binding: is the attention budget non-binding in the main sweep?** Run `scripts/attention_calibration_check.py` across all three archetypes and enough seeds (at least 3-5) to confirm that realized attention utilization does not routinely hit the ceiling. If it does in most regimes, the budget is too tight for a governance-comparison sweep and results may reflect rationing rather than prioritization. The canonical posture is that `exec_attention_budget` should be non-binding.

- [ ] **Seed count: are there enough seeds for the intended question?** Reference `docs/design/experiments.md` for power analysis guidance. Single-seed results are illustrative but rarely sufficient for governance conclusions. For the canonical governance comparison, use at least 5-7 seeds. For sensitivity studies testing a specific parameter, 3-5 seeds may suffice if the effect size is large.

- [ ] **Horizon adequacy: is the horizon long enough for the phenomenon in scope?** Right-tail durations in the canonical families range from 40-220 ticks depending on the family. Patient governance needs enough runway for long-duration initiatives assigned mid-run to complete before the horizon. If the longest right-tail durations in the family exceed half the horizon, patient governance is structurally disadvantaged regardless of its decision quality.

- [ ] **Category supply: does the pool / frontier contain enough of each family to support the intended portfolio posture?** If the study design requires sustained right-tail activity (e.g. for RQ3 or RQ7), verify that the initial right-tail count or frontier depth provides enough supply. Use the `right_tail_prize_count` override in the YAML `opportunity_supply` section to adjust if needed. Run `scripts/right_tail_abundance_study.py` to test how right-tail supply level affects outcomes before committing to a specific count.

- [ ] **Staffing-response alignment: are staffing-response assumptions consistent with the study hypothesis?** If the study intends to test staffing-intensity effects, verify that the `staffing_response` overrides in the YAML are set for the relevant families. If staffing intensity is not part of the study question, confirm that all families use the preset default of 0.0 (no staffing-intensity effect).

## Known limitations for reporting

When presenting study findings, the conductor should foreground the following limitation, especially when reporting on aggressive stop-loss regimes:

> "The model likely understates the real-world cost of aggressive stopping because the future proposal stream is held exogenous. In reality, a regime that aggressively stops work may also discourage future proposals, degrading the quality of the opportunity pipeline. This effect is not modeled."

Stage 3's dynamic frontier (specified in `docs/design/dynamic_opportunity_frontier.md`) partially addresses this within-family: the frontier degrades as the best opportunities within each family are consumed, so aggressive stopping that cycles through many initiatives will face lower-quality replacements. However, the frontier does not model the organizational-behavioral channel where aggressive stopping discourages future proposal creation altogether. The limitation remains relevant even after Stage 3.

This limitation is most material for findings about aggressive stop-loss governance. If the study shows that aggressive stopping produces comparable or superior total value, the conductor should note that this finding may overstate the real-world advantage because the model does not penalize the regime for its effect on future opportunity quality.

## Reading run-bundle outputs

When a comparative experiment is run via `scripts/run_experiment.py`, the output is a **run bundle** — a self-contained directory with all artifacts needed to understand, reproduce, and present the experiment. The conductor should know what each part of the bundle contains.

The **manifest** (`manifest.json`) identifies the bundle: experiment name, seed set, condition count, provenance (git commit, platform, command), and telemetry (timing, completion status). Start here to confirm the experiment ran as intended.

The **canonical Parquet tables** in `outputs/` are the analytical substrate:

- `seed_runs.parquet` — one row per seed run. Contains total value, major-win count, terminal capability, false-stop rate, idle percentage, and timing markers. This is the primary table for seed-level uncertainty analysis.
- `experimental_conditions.parquet` — one row per experimental condition. Aggregated from seed runs (mean, median, std, percentiles). This is the primary table for cross-condition comparison.
- `family_outcomes.parquet` — one row per initiative family per seed run. Contains completed/stopped/active counts, value by channel, and major-win counts per family. Use this to understand which families drove value under each regime.
- `yearly_timeseries.parquet` — one row per time bin (52 ticks = one study year) per seed run per family. Contains value, completions, stops, and capability per year. Use this for timing analysis: when did value accrue, when did stops cluster, when did capability peak?
- `initiative_outcomes.parquet` — one row per initiative per seed run. Contains true quality, beliefs, staffed ticks, outcome status, and belief-at-stop. Use this for initiative-level drill-downs.
- `diagnostics.parquet` — long-form diagnostic metrics per condition. Contains false-stop rate, belief-at-stop distribution, stop hazard by staffed-time bin, survival rates, and terminal capability summary.
- `event_log.parquet` — one row per event per seed run. Contains all starts, stops, completions, major wins, and enabler completions with tick, family, value delta, and capability delta.

The **derived tables** in `derived/` support interpretation:

- `pairwise_deltas.parquet` — metric differences between each condition and the baseline (typically the Balanced regime).
- `enabler_coupling.parquet` — per-seed enabler completions alongside terminal capability, false-stop rate, and late-period value. Use this to understand whether enabler investment predicts better downstream outcomes.
- `representative_runs.parquet` — which seed runs were selected as representative (median, max, min value) for drill-down.

The **HTML report** at `report/index.html` is the human-readable entry point. It contains headline comparison tables, all generated figures, study interpretation notes, and methods/reproducibility information. Open it in a browser. The companion markdown at `report/report.md` contains the same content in a diffable, portable format.

The **figures** in `figures/` are the visual outputs referenced by the report:

- `value_by_year_stacked.png` — priced value per year decomposed by initiative family
- `cumulative_value_by_year.png` — cumulative priced value over time, one line per condition
- `surfaced_major_wins_by_year.png` — cumulative major wins over time (surfaced, not priced)
- `tradeoff_frontier.png` — value vs. major wins scatter (point size = capability)
- `terminal_capability.png` — bar chart of terminal capability per condition
- `rt_survival_curves.png` — right-tail false-stop rate per condition
- `enabler_dashboard.png` — multi-panel enabler-related metrics per condition
- `seed_distributions.png` — boxplots of total value, major wins, and terminal capability
- `representative_timelines.png` — event timeline for the median-value seed run per condition
- `trajectory_beliefs_<condition_id>.png` — per-initiative belief evolution over time for representative initiatives, with latent quality reference, ramp shading, stop/completion markers, major-win stars, and attention as a secondary axis (requires `record_per_tick_logs: true`)
- `trajectory_overlay_<condition_id>.png` — overlaid belief trajectories for all representative initiatives on shared axes, for quick visual comparison of convergence patterns across families (requires `record_per_tick_logs: true`)

The conductor should not treat figures or the HTML report as the deepest source of truth. They are derived from the canonical Parquet tables. If a figure looks surprising, verify the underlying data in the corresponding table.

To load a Parquet table for ad hoc analysis:

```python
import pyarrow.parquet as pq
table = pq.read_table("results/<bundle>/outputs/seed_runs.parquet")
# Access columns directly:
values = table.column("total_value").to_pylist()
```

## Final operator guidance

The right way to conduct this study is to begin with the business question, translate it into environment, governance architecture, and operating policy choices, validate that the scenario is actually representable, and then look at outputs through both a value lens and a mechanism lens. If the study produces a surprising result, the next step is usually not to add a feature immediately. It is to ask whether the result reflects a real mechanism in the model, a weak experimental design, or a mismatch between the intended semantics and the implemented ones.

If the conductor keeps that discipline, Primordial Soup can be used not just as a simulator that produces numbers, but as a study that helps reason about real governance choices under uncertainty.
