# Team and resources model

## Teams

### Academic
Each team is a discrete, fixed-capacity resource entity in the simulation's workforce model. Teams are the atomic unit of staffing allocation: governance assigns whole teams to initiatives, and the engine neither subdivides nor recombines teams during a run.

Per-team state:

- `team_id` (string)
- `team_size` (integer)
- `assigned_initiative_id` or `null`
- `availability_state` ∈ {idle, assigned, transitioning}
- `cumulative_utilization` (tracking metric)

`team_size` is immutable within a run. It is set at initialization and does not change — there is no mechanism for mid-run hiring, attrition, or team resizing (see "Hiring / firing / global resource changes").

`availability_state` is a derived quantity determined by the team's current assignment and ramp status:

- **idle**: `assigned_initiative_id is None`. The team consumes no labor and produces no observations. Idle team-ticks are counted in the idle capacity metrics (see `core_simulator.md`, idle capacity counting rules).
- **transitioning**: `assigned_initiative_id is not None` and the team is within its ramp period (`ticks_since_assignment < ramp_duration_ticks - 1`). The team is fully staffed — `staffed_tick_count` increments and labor is consumed at the full team rate — but learning efficiency is attenuated by `ramp_multiplier` (see "Ramp / transition penalty").
- **assigned**: `assigned_initiative_id is not None` and the ramp period has completed (`ticks_since_assignment >= ramp_duration_ticks - 1`). The team operates at full learning efficiency.

State transitions are driven by governance actions (`AssignTeam`, `ContinueStop`) and engine events (completion at step 5c of the tick sequence). The team never autonomously changes its own assignment.

`cumulative_utilization` is a per-team analytical output recording how each team's total ticks across the run decompose into fully productive (assigned, post-ramp), ramp (transitioning), and idle categories. It is used exclusively for cross-regime comparison and does not enter any governance decision or engine computation.

<!-- specification-gap: cumulative_utilization is described as a decomposition of ticks into productive, ramp, and idle categories, but no formal aggregation formula (single ratio, vector of counts, or weighted measure) is specified. The relationship between this per-team metric and the run-level idle_capacity_profile metrics (cumulative_idle_team_ticks, idle_team_tick_fraction) defined in review_and_reporting.md is not stated. -->

### Business
Each team in the simulation is a discrete organizational unit with a fixed set of properties:

- **Identity.** Every team has a unique identifier that distinguishes it throughout the run.
- **Size.** Each team has a fixed headcount — the number of people on that team. Team size does not change during the simulation. A team of eight remains a team of eight from the first week to the last.
- **Current assignment.** At any given moment, a team is either assigned to a specific initiative or unassigned. There is no partial assignment — a team is fully committed to one initiative or fully available.
- **Availability state.** A team is in one of three states: *idle* (available for assignment, not currently working on anything), *assigned* (actively working on an initiative), or *transitioning* (assigned to a new initiative but still in its ramp-up period, working at reduced effectiveness).
- **Cumulative utilization.** The simulation tracks each team's total productive time over the course of the run — how many weeks the team was assigned and working, versus how many weeks it sat idle or was consumed by transition overhead. This is a tracking metric used in cross-regime comparison, not an input to any governance decision.

## No team splitting

### Academic
- A **team is atomic**. It cannot be split across multiple initiatives in a tick.
- Assignment is accepted only when `team_size >= initiative.required_team_size`.

Teams cannot be aggregated to satisfy a staffing requirement. If an initiative requires `required_team_size = 6` and no single available team has `team_size >= 6`, the initiative remains unstaffed — the engine does not combine multiple smaller teams to meet the threshold. An unstaffed initiative remains in the unassigned pool indefinitely until either a sufficiently large team becomes available or governance stops it. This constraint means that the team decomposition (the partition of total labor endowment into discrete teams of specific sizes) has direct consequences for which initiatives in the pool are staffable, and therefore for the effective opportunity set governance can access.

### Business
A team is an indivisible unit. It cannot be split across multiple initiatives in the same week. When a team is assigned to an initiative, the entire team works on that initiative — there is no mechanism for sending half a team to one project and the other half to another. This reflects an organizational design choice: the simulation models teams as cohesive working units, not as pools of interchangeable individual contributors.

Assignment requires a minimum fit. A team can only be assigned to an initiative if the team's size meets or exceeds the initiative's minimum staffing requirement. An initiative that requires a team of at least six people cannot be staffed by a team of four. If no available team is large enough to meet an initiative's requirement, that initiative remains unstaffed until one becomes available — the simulation does not combine smaller teams to fill the gap.

## Surplus team capacity and staffing intensity

### Academic
When a team is assigned to an initiative it satisfies but exceeds the minimum staffing requirement (`team_size > required_team_size`), the surplus capacity has a configurable effect on learning governed by the initiative's `staffing_response_scale` parameter.

- If `team_size > required_team_size`, the team can be assigned. When the
  initiative's `staffing_response_scale` is 0.0, surplus members produce no
  additional benefit (the original canonical behavior).
- When `staffing_response_scale > 0`, additional staffing above the minimum
  threshold accelerates learning with diminishing returns. The staffing
  multiplier applied to the learning rate is:
  ```
  staffing_multiplier = 1.0 + staffing_response_scale
                            * (1.0 - required_team_size / assigned_team_size)
  ```
  At threshold staffing (assigned == required), the multiplier is exactly 1.0.
  As assigned team size grows, the multiplier saturates toward
  `1.0 + staffing_response_scale`.
- In v1, this multiplier affects the quality belief learning rate only, not
  execution progress or any other engine variable.
- `staffing_response_scale` is a study parameter expressing a modeled hypothesis
  about how strongly learning responds to additional staffing on a given class
  of opportunity. It is not an empirical truth the simulator asserts.
- Per opportunity_staffing_intensity_design_for_claude_v2.md.

Domain and boundary conditions: `staffing_response_scale >= 0`. For all valid assignments (`assigned_team_size >= required_team_size > 0`), the ratio `required_team_size / assigned_team_size` lies in `(0, 1]`, so the staffing multiplier is bounded within `[1.0, 1.0 + staffing_response_scale]`. When `staffing_response_scale = 0`, the multiplier is identically `1.0` for all valid assignments regardless of surplus.

Regardless of `staffing_response_scale`, the full team is considered staffed for labor accounting. Surplus members consume labor even when `staffing_response_scale = 0` and they contribute no additional learning. A team of size 8 assigned to an initiative with `required_team_size = 5` consumes 8 team-member-ticks of labor per tick, not 5, irrespective of whether the surplus accelerates learning. This means two regimes that assign differently sized teams to identical initiatives incur different labor costs for the same learning output under the default `staffing_response_scale = 0`. The labor cost of surplus staffing is visible in per-initiative `cumulative_labor_invested` and in aggregate labor utilization metrics.

The staffing multiplier does not affect execution progress signals, completion timing, signal generation (`σ_eff`), or any value channel. A larger team does not complete the initiative faster or produce more realized value — it accelerates only the rate at which the quality belief resolves uncertainty about the initiative's latent strategic quality.

### Business
When a team is larger than the initiative's minimum staffing requirement — for example, an eight-person team assigned to an initiative that requires only five — the surplus capacity can either go to waste or accelerate learning, depending on the study configuration.

**Default behavior: surplus has no effect.** When the staffing response parameter is set to zero (the default), a team that exceeds the minimum requirement provides no additional benefit beyond meeting the threshold. An eight-person team assigned to a five-person initiative learns at the same rate as a five-person team would. The three extra members are effectively along for the ride — staffed and consuming labor, but not contributing additional learning. This is the simpler assumption: either you meet the staffing threshold or you do not.

**Optional behavior: surplus accelerates learning.** When the staffing response parameter is set above zero, additional staffing above the minimum threshold accelerates the rate at which the organization learns about the initiative's strategic quality. The acceleration follows a diminishing-returns pattern: the first few extra people above the threshold contribute meaningfully, but each additional person adds less. At threshold staffing (team size exactly equals requirement), the learning rate is unchanged. As the team grows larger relative to the requirement, the acceleration approaches a ceiling governed by the staffing response parameter.

This acceleration affects only the learning rate for strategic quality beliefs — the speed at which the organization resolves uncertainty about whether the initiative is worth pursuing. It does not affect execution progress signals, completion timing, or any value realization. A larger team does not finish the initiative faster or produce more value; it helps the organization reach a confident assessment sooner.

**This is a study parameter, not an empirical claim.** The staffing response parameter expresses a modeled hypothesis about how strongly learning responds to additional staffing on a given class of opportunity. Different initiative types or organizational contexts might exhibit different staffing response characteristics. The simulation does not assert that surplus staffing always helps or never helps — it provides the parameter so the study can explore both assumptions and their consequences for governance outcomes.

## Team freeing & timing

### Academic
- When an initiative is stopped (action applied), its assigned team becomes available at the **start of the next tick**. The engine can apply `AssignTeam` at start-of-next-tick to move the team to a new initiative for that tick.

The same timing applies to engine-driven team releases. When an initiative completes at step 5c of tick `t`, the engine sets `team.assigned_initiative_id = None` effective at the start of tick `t+1`. The completing initiative's team is available for the governance step of tick `t+1`. This is consistent with the canonical action-timing invariant: effects of events within tick `t` take hold at the start of tick `t+1`.

In both cases — governance-driven stop and engine-driven completion — the release tick is the initiative's last active tick (the team was staffed, `staffed_tick_count` incremented, and observations were produced). Idleness begins the following tick.

**Immediate reassignment (zero-idle-tick transition).** If governance includes both a release (explicit stop or anticipated completion) and a new `AssignTeam` action for the same team in the same end-of-tick action vector, both actions take effect simultaneously at the start of tick `t+1`. The team transitions directly from one initiative to the next — `assigned_initiative_id` is non-null at the start of every tick and the team is never idle. This is the mechanism by which governance avoids unnecessary idle capacity when releases are predictable. The newly assigned initiative begins its ramp clock (`ticks_since_assignment = 0`) at the start of `t+1`.

### Business
When governance stops an initiative, the team currently assigned to it does not become available immediately. The stop decision takes effect at the end of the current week, and the freed team becomes available for reassignment starting at the beginning of the following week. The week in which the stop is ordered is the initiative's last active week — the team was still working that week and the initiative still generated evidence. Starting the next week, governance can assign that team to a new initiative as part of its regular decisions.

This one-week delay is consistent with the simulation's general timing principle: all governance decisions made at the end of a week take effect at the start of the next week. The same timing applies to teams freed by natural completion — when an initiative finishes, the team becomes available for reassignment the following week. If governance anticipates a completion or plans a stop, it can include the reassignment in the same set of end-of-week decisions, and the freed team transitions directly to the new initiative with no idle gap.

## Ramp / transition penalty

### Academic
- Newly-assigned teams may be subject to a *ramp period* `R` ticks. During ramp:
  - ramp state is tracked using the assignment-relative clock
    `ticks_since_assignment`
  - Learning efficiency `L(d)` is multiplied by `ramp_multiplier(t)` ∈ (0,1]
  - no other canonical engine variable is changed by ramp

The canonical ramp formula, including the first-tick partial-productivity
convention, is defined in `core_simulator.md` and should be treated as the source
of truth if wording here is shorter or less explicit.

- Ramp parameters are in `SimulationConfiguration`.

**Scope of ramp effects.** The ramp multiplier attenuates only the quality belief learning rate via:

```
L_ramped(d) = ramp_multiplier × L(d) = ramp_multiplier × (1 - d)
```

When both dependency (`d > 0`) and ramp (`ramp_multiplier < 1`) are active, the penalties compound multiplicatively. Ramp does not enter the execution belief update (`c_exec` is independent of ramp state), does not alter signal generation (`σ_eff` is independent of ramp), does not delay completion (`staffed_tick_count` increments during ramp), and does not reduce realized value at any channel.

**Staffing status during ramp.** A team in ramp is fully staffed. The initiative's `staffed_tick_count` increments each tick, labor is consumed at the full team rate, and the team is counted as assigned (not idle) for all capacity accounting purposes. The sole mechanical consequence of ramp is the transient attenuation of learning efficiency via `ramp_multiplier`.

**Clock distinction.** The assignment-relative clock `ticks_since_assignment` — which governs the ramp multiplier computation — resets to 0 on each new team assignment. The lifetime clock `staffed_tick_count` — which governs completion detection, progress fraction, and the stagnation window — never resets on reassignment. These clocks serve different purposes and must not be substituted for one another. An initiative with `staffed_tick_count = 100` and `ticks_since_assignment = 0` has accumulated 100 ticks of evidence and progress but has a newly assigned team at the start of its ramp period. The ramp formula reads the pre-increment value of `ticks_since_assignment` to compute `ramp_multiplier` for the current tick (see `core_simulator.md` step 2).

**Cumulative ramp labor as analytical output.** The total labor consumed during ramp periods across all initiatives (`cumulative_ramp_labor` and `ramp_labor_fraction`) is a first-class run output. Cross-regime comparison of ramp labor measures the total switching cost each governance policy incurs through its reassignment behavior. Frequent reassignment resets the ramp clock repeatedly, producing compounding learning-efficiency penalties that do not appear in simple labor accounting — the team is staffed and `staffed_tick_count` increments — but manifest as slower belief convergence, delayed stop/continue resolution, and degraded signal quality during the ramp window.

### Business
When a team is newly assigned to an initiative, it does not operate at full learning effectiveness immediately. There is a transition period — the ramp — during which the team's ability to generate useful learning about the initiative's strategic quality is reduced. This reflects the organizational reality that newly assigned teams need time to understand context, build working relationships, learn the domain, and develop the familiarity required to produce informative observations.

**What ramp affects.** During the ramp period, the team's learning efficiency is multiplied by a ramp factor that starts low and increases toward full effectiveness. This ramp factor compounds with any dependency-related learning penalty — a newly assigned team working on a highly dependent initiative experiences both reduced learning from the ramp and reduced learning from dependencies simultaneously. Ramp affects only strategic quality learning. It does not slow completion, change execution evidence, reduce realized value, or alter any other aspect of the initiative's behavior. The team is fully staffed during ramp — it counts as assigned, the initiative's staffed-time clock advances, and labor is consumed — but the learning signal it produces is attenuated.

**Ramp tracking.** Ramp state is tracked using the assignment-relative clock, which counts weeks since the current team was assigned and resets to zero on each new assignment. This is distinct from the initiative's lifetime staffed-time clock, which never resets. The ramp period duration and the shape of the ramp curve (steady improvement versus front-loaded improvement) are configured in the simulation parameters.

The full specification of the ramp formula — including the convention that teams contribute positive but partial learning from their very first week, the two available ramp shapes, and the precise interaction between ramp and dependency penalties — is defined in the core simulator specification and governs all implementation. The treatment here is a summary of the same mechanics described in the ramp penalties section of that document.

## Hiring / firing / global resource changes

### Academic
Dynamic workforce changes — including hiring, firing, and mid-run team pool adjustments —
are out of canonical scope for this study. Workforce size is fixed for a given simulation
run, but the study now distinguishes two separate concepts:

- **Total labor endowment** is the environmental quantity. It is the aggregate
  productive capacity available to the organization for a run.
- **Team decomposition** is a governance-architecture choice. It determines how
  that fixed labor endowment is partitioned into discrete teams, and is fixed
  within a run once chosen.

The simulator consumes only the realized workforce representation. It does not
model how leadership arrived at that representation before the run began. Any
future extension admitting dynamic resourcing must be introduced as an explicit
experimental variant and documented in the run manifest.

The distinction between total labor endowment and team decomposition has a direct analytical consequence. Because both quantities are held constant across governance regimes within an experimental comparison, any observed differences in idle capacity, team-initiative staffing mismatches, or deployment bottlenecks are attributable to the interaction between the fixed team structure and the governance regime's operating decisions — not to differences in available resources or organizational design. The canonical sweep isolates operating policy effects from structural configuration effects by construction. Findings about idle capacity (see `core_simulator.md`, idle capacity counting rules) reflect governance selectivity, not resource inadequacy.

The team decomposition also constrains the effective opportunity set: the partition of labor into teams of specific sizes determines which initiatives in the pool are staffable given the atomicity and minimum-fit constraints (see "No team splitting"). Two different team decompositions applied to the same initiative pool and the same governance policy may produce different outcomes purely through staffability differences. This interaction is a property of the governance-architecture tier, not of operating policy, and is held constant within the canonical sweep by design.

### Business
The simulation does not model hiring, firing, or any mid-run changes to the size of the workforce. The total number of people available to the organization is fixed for the entire six-year run. This is a deliberate scoping choice: the study isolates the effect of how governance deploys a fixed pool of resources, not the effect of having more or fewer resources to deploy.

Within that constraint, the study distinguishes two separate concepts that are often conflated in organizational discussions:

- **Total labor endowment** is the environmental given — the aggregate productive capacity available to the organization. Think of it as the total headcount budget that has been approved and funded. It is a constraint governance inherits, not a choice governance makes.
- **Team decomposition** is a governance-architecture choice — how that fixed headcount is organized into discrete teams. An organization with sixty people could field six teams of ten, ten teams of six, or a mix of different sizes. This choice is made before the run begins and held fixed throughout. It determines which initiatives can be staffed (because team size must meet the initiative's minimum requirement) and how flexibly governance can redeploy capacity across the portfolio.

The simulation consumes only the realized team structure. It does not model the process by which leadership decided to organize its workforce in a particular way — that decision is taken as given. The consequence is that any findings about idle capacity, team-initiative mismatches, or deployment bottlenecks reflect the interaction between the chosen team structure and the governance regime's operating decisions, not a failure to hire or restructure.

Any future extension that introduces dynamic workforce changes — mid-run hiring, team restructuring, or workforce reductions — would need to be introduced as an explicit experimental variant with its own documentation, not folded silently into the baseline model.
