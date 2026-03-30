# Core design principles

## Role of this document

### Academic
This document states the **structural principles** of the Primordial Soup study: the abstractions, design principles, and scope boundaries that define the study's identity and make its controlled comparison meaningful.

It is not a substitute for the full technical design. Mechanics, equations, and interface contracts live in the technical specification documents. This document answers: *What are the commitments that define this study's identity?* Changes to these principles require explicit design decisions with documented rationale, because they affect the study's ability to attribute outcome differences to governance.

### Business
This document states the **structural commitments** that make this study what it is: the core concepts, design principles, and boundary lines that enable meaningful findings.

It is not a substitute for the full design. The detailed mechanics — how beliefs update, how signals are generated, how value is realized — live in the technical documents. This document answers a more fundamental question: *What are the commitments that define what we are studying?*

Think of it as the equivalent of a research charter. The detailed methodology can evolve. These principles can also be revised — but changes here require explicit design decisions, because they affect the study's experimental methodology and the interpretability of its findings.

## What the study is

### Academic
Primordial Soup is a **discrete-time Monte Carlo study of governance over a portfolio of initiatives** whose true quality is latent and only gradually inferable from noisy signals. A single governance policy acts at review points over evolving initiative, team, and capability state. The same simulated worlds are evaluated under multiple governance regimes so that outcome differences can be attributed to policy differences rather than to different opportunity pools.

The central object of study is the **effect of governance decisions** on discovery, value realization, persistent mechanisms, and portfolio capability over time — not culture, politics, morale, or dynamic labor-market adjustment.

### Business
Primordial Soup is a **controlled simulation experiment that tests how different governance approaches affect what an organization discovers, builds, and becomes over a six-year horizon** — when leadership cannot directly observe which initiatives are truly valuable and must instead rely on imperfect, accumulating evidence.

A single governance regime — a consistent set of rules for allocating attention, assigning teams, and deciding when to stop or continue initiatives — operates across the full portfolio over the entire horizon. The same simulated organizational reality is then run under different governance regimes so that differences in outcomes can be attributed to differences in governance decisions, not to differences in the opportunities that were available.

The central object of study is the **effect of governance decisions** — how leadership allocates scarce executive time, how it staffs initiatives, and when it decides to persist or cut losses — on four outcomes: whether transformational opportunities are discovered before governance terminates them, how much direct economic value is realized, whether the organization builds lasting mechanisms that continue generating returns after teams redeploy, and how much the organization's capacity to evaluate future work improves or degrades over the horizon.

What the study deliberately excludes from its scope is equally important. It does not model organizational politics, morale, executive personalities, hiring and firing, cultural dynamics, or external economic shocks. These are real forces in real organizations, but including them would make it impossible to isolate the effect of governance decisions — which is the entire point. The study holds everything else constant so that governance is the only thing that varies.

## Abstractions that define the study

### Academic
- **Initiatives** are stateful entities with latent attributes (e.g. latent_quality, dependency_level) and mutable state (beliefs, lifecycle, assignments). Behavior is expressible entirely via resolved attributes and value channels; initiative *labels* (flywheel, right-tail, enabler, quick-win) are metadata for generation and reporting only, not for engine branching.

- **Governance** is a pure decision function from observation and configuration to actions. It sees only observables and belief summaries — never latent ground truth. It does not own mutable state across ticks.
  Governance may also use policy-side portfolio summaries and risk controls, but
  these must be expressed in observable portfolio primitives such as quality
  belief, labor exposure, patience-state, learning-state, and concentration —
  not in initiative labels or engine-enforced diversification rules.

- **Teams** are indivisible assignment units. A team is assigned to at most one initiative at a time. No fractional splitting.

- **Value** is realized at lifecycle transitions (completion-gated), not as a continuous stream during execution. Channels are completion-lump, residual, major-win event, and capability; they remain separable in reporting and analysis.

- **Randomness** is explicit and reproducible. Each initiative has dedicated random streams (quality signal, execution signal) seeded from `world_seed` and `initiative_id` so that common-random-numbers comparability holds across governance regimes.

### Business
Five core abstractions define the study. Each represents a deliberate modeling choice about what matters for the governance question being asked.

- **Initiatives** are the units of work the organization invests in. Each initiative has hidden attributes that determine what it is actually worth and how long it will actually take — but leadership cannot see those directly. What leadership can see are observable characteristics (the stated plan, the visible ceiling on potential upside, the expected capability contribution) and evolving belief estimates that update as work progresses and evidence accumulates.

  Critically, the simulation engine treats every initiative identically based on its resolved attributes — its actual uncertainty level, duration, value channels, and dependency structure. The labels used to describe initiative types (flywheel, right-tail, enabler, quick-win) exist only for the purpose of generating realistic portfolios and for reporting results. The engine never applies different rules to an initiative because of its label. This is a deliberate design choice: it ensures that any difference in how governance treats different types of work is a governance decision, not a mechanical artifact of the simulation.

- **Governance** is a consistent decision-making function that takes in what leadership can currently observe — belief estimates, staffing status, time elapsed, portfolio composition — and produces decisions: which initiatives to continue, which to stop, how much executive attention to allocate to each, and which teams to assign where.

  Governance never sees the hidden truth about an initiative's actual quality. It operates entirely on observable evidence and the beliefs that evidence has produced. It does not carry private memory from one review cycle to the next — its decisions are based on the current state of the portfolio as visible through the observation boundary, plus whatever standing rules and thresholds define the regime.

  Governance may also use portfolio-level summaries and risk controls — for example, monitoring concentration of investment, tracking how much labor is committed to initiatives showing weak signals, or applying patience rules based on how much has been learned. But these controls must be expressed in terms of observable portfolio characteristics (current beliefs, labor committed, learning velocity, patience state) — never in terms of initiative labels. A governance regime that says "keep all flywheels regardless of evidence" is not permitted; one that says "keep initiatives with strong compounding residual indicators and belief above threshold" is. The distinction matters because it forces governance to earn its conclusions from evidence rather than from taxonomic shortcuts.

- **Teams** are indivisible. A team is assigned to one initiative at a time, or it is unassigned. There is no fractional splitting of a team across multiple initiatives simultaneously. This reflects the real organizational principle that a team working on two things at once is not half as effective on each — it is substantially less than half, because of context-switching costs, divided accountability, and fragmented attention. The model enforces full commitment rather than attempting to simulate partial attention.

- **Value is realized at completion, not during execution.** An initiative that is in progress has not yet created value — it has consumed resources. Value is created at the moment of completion, through one or more of four distinct channels: a one-time completion payoff, activation of an ongoing value stream that persists after the team redeploys, a major-win discovery event (for initiatives that turn out to be genuinely transformational), and a contribution to the organization's portfolio-wide capability. These channels remain separable in measurement and analysis, which is essential: a governance regime's total value number is less informative than understanding which channels are driving that total.

  The most consequential implication of completion-gated value is that stopping an initiative forfeits everything it might have produced. There are no partial credits. An initiative stopped at 90% completion generates zero value — no residual stream, no capability contribution, no major-win discovery. This is a deliberate modeling choice that makes the stop decision genuinely consequential: every termination is a bet that the remaining investment is not worth what completion would have delivered.

- **Randomness is explicit and reproducible.** Every source of uncertainty in the simulation is driven by dedicated random streams that are seeded deterministically from the world configuration and the initiative's identity. This is what makes the controlled comparison possible: two governance regimes facing the same world seed receive exactly the same sequence of noisy signals for any given initiative, regardless of what decisions they have made about other initiatives. If regime A stops initiative #47 while regime B continues it, both regimes still see identical signals from initiative #48. The comparison reflects governance differences, not sampling differences.

## Structural principles

### Academic
1. **Type-independence** — The engine and configuration do not branch on initiative labels. All type-specific parameterization is resolved into concrete attributes before the engine receives initiatives.

2. **Observation boundary** — Governance and policies never see latent ground truth (e.g. latent_quality). Latent attributes exist only to generate outcomes and observations; the engine hides them from the policy.

3. **Action timing** — Governance computes actions at end of tick T. Actions become effective at start of tick T+1 (unless an explicit exception is stated). Stopping an initiative frees its team at start of T+1.

4. **Belief belongs to the initiative** — Strategic quality belief (quality_belief_t) and related counters are initiative state, maintained by the engine. The policy does not hold private evolving memory across ticks.

5. **Deterministic resolution** — If an initiative generator is used, the runner resolves it deterministically (using `world_seed`) to a fully resolved initiative list before simulation. The engine always receives a resolved list.

6. **Deterministic pool** — The initiative pool is deterministically
   seeded from `world_seed`. Initiatives are drawn from family-specific
   frontier distributions whose parameters may shift as the run
   progresses. The realized pool for a given seed and governance
   trajectory is fully reproducible. Different governance trajectories
   may produce different realized pools because pool depletion and
   initiative stopping affect frontier state. Paired-seed comparability
   is preserved: for a given seed, the frontier's stochastic draws are
   deterministic given the governance-driven depletion history. The team
   pool is the realized decomposition of labor endowment; how that
   decomposition was chosen is governance architecture (see
   `team_and_resources.md`).

7. **Portfolio controls remain governance-side** — The engine may expose
   portfolio-summary aggregates as convenience observations, but it does not
   enforce diversification, risk budgets, or labor-share constraints unless the
   design corpus explicitly states otherwise. Those remain governance-policy
   choices.

These principles exist because the study's controlled comparison depends on them. They can be revised, but changes require evaluating whether the study can still attribute outcome differences to governance decisions rather than to artifacts of the simulation design.

### Business
Seven structural principles define how the study works. They exist because the entire experimental design depends on them — without these commitments, the study cannot meaningfully compare governance regimes. They are not arbitrary constraints; each one serves a specific purpose in making the comparison valid.

1. **No special rules by initiative type.** The simulation engine and its configuration do not apply different logic based on what kind of initiative something is labeled as. A flywheel and a right-tail initiative that happen to have the same resolved attributes (same uncertainty, same duration, same value channels) are treated identically by the engine. All type-specific characteristics — higher noise for exploratory work, longer durations for capability-building, compounding residual streams for flywheels — are expressed as concrete attribute values before the engine ever sees the initiative. This ensures that any difference in outcomes across initiative types is driven by the attributes themselves and the governance decisions made about them, not by hidden mechanical advantages or penalties the engine applies by label.

2. **Leadership never sees the ground truth.** Governance decisions are made entirely on the basis of observable evidence and the beliefs that evidence has produced. The true underlying quality of an initiative, its actual completion time, and whether it will turn out to be a major win are all hidden from governance throughout the run. They exist in the simulation to determine what actually happens — what signals are generated, what value is realized at completion — but they are never visible to the decision-maker. This is the most fundamental structural guarantee in the study. Without it, the governance comparison is meaningless: a regime that could see the truth would simply keep good initiatives and stop bad ones, and the interesting questions about patience, attention allocation, and learning under uncertainty would disappear.

3. **Decisions take effect the following period.** When governance reviews the portfolio and makes decisions — stop this initiative, assign that team, allocate attention here — those decisions take effect at the start of the next period, not immediately. A team freed by stopping an initiative becomes available at the start of the next period. This one-period delay is not an implementation detail; it reflects the real organizational reality that decisions require time to propagate. It also prevents governance from making decisions and immediately observing their consequences within the same review cycle, which would create feedback loops that do not exist in real organizations operating at this cadence.

4. **Beliefs belong to the initiative, not to governance.** The organization's current best estimate of an initiative's strategic quality, and the counters that track how that estimate has evolved, are properties of the initiative's state — maintained by the simulation engine as evidence accumulates. Governance does not hold its own private, evolving memory about initiatives across review cycles. It reads the current belief state and acts on it. This means two governance regimes that have made identical decisions about an initiative up to a given point will see identical belief states for that initiative at that point. Any divergence in beliefs between regimes comes from divergence in decisions (different attention allocation producing different signal quality, for instance), not from governance carrying private information.

5. **Resolved inputs before simulation begins.** If the study uses a generator to create the initiative pool (drawing from distributions of quality, duration, uncertainty, and so on), that generator must run to completion before the simulation starts. The engine always receives a fully resolved list of initiatives with concrete attribute values — it never draws from distributions or generates initiatives during the run. This ensures that the initiative pool is fixed and known before governance decisions begin, which is necessary for the controlled comparison to be valid.

6. **The initiative pool is reproducible and deterministic.** The pool of initiatives available to the organization is seeded deterministically from the world configuration. In the canonical study, new initiatives can emerge over time from family-specific opportunity frontiers whose quality may shift as the organization consumes opportunities — but this emergence is fully reproducible given the same world seed and the same sequence of governance decisions. Different governance regimes may face different pools of later-emerging opportunities because their decisions about which initiatives to stop or complete affect how quickly the frontier is consumed and what quality of opportunities remain. This is intentional: it reflects the real phenomenon that an organization's past choices shape what future opportunities look like. What is guaranteed is that for a given seed, the same governance trajectory always produces the same pool — the comparison is controlled even though the pools may diverge across regimes.

   The team pool — how the organization's total labor capacity is divided into discrete teams — is a governance architecture choice made before the run begins and held fixed throughout. The study does not model how leadership arrived at that team structure; it takes it as given and examines what governance does with it.

7. **Portfolio controls are governance choices, not engine mechanics.** The simulation engine may calculate and expose portfolio-level summaries for governance to consult — how concentrated investment is across families, how much total labor is committed to weak-signal initiatives, what the current capability trajectory looks like. But the engine does not enforce diversification targets, risk budgets, or labor-share constraints on its own. If governance chooses to ignore enabler work entirely and concentrate everything on quick wins, the engine permits it. The consequences show up in the outcomes, not in a mechanical guardrail that prevents the decision. This is essential to the study's purpose: it is testing what governance choices produce, not what happens when the system prevents certain governance choices from being made.

## Scope boundaries

### Academic
The following are intentionally outside the current study scope:

- Politics, morale, executive personalities, hiring/firing, cultural contagion, exogenous macro shocks.
- Autonomous strategic adaptation by teams or initiatives.
- Fractional team assignment.
- Mid-run initiative injection by engine or policy (frontier materialization
  is runner-side only, per `dynamic_opportunity_frontier.md`).

Extensions may be introduced if they preserve the study's ability to attribute outcome differences to governance decisions.

### Business
The following are deliberately excluded from the current study. Each exclusion is a judgment that including the phenomenon would either make it impossible to isolate the effect of governance decisions, or would introduce dynamics that are better studied in a separate, purpose-built experiment.

- **Organizational politics, morale, and culture.** Real governance operates in an environment where people have career incentives, teams have morale that rises and falls, and organizational culture shapes what proposals are brought forward and how aggressively they are pursued. The study excludes these dynamics because they would make it impossible to attribute outcome differences to governance structure rather than to second-order cultural effects. This is a known limitation: as noted elsewhere, a governance regime that consistently kills speculative work early would, in a real organization, gradually receive fewer ambitious proposals — but the model does not represent that feedback loop.

- **Executive personalities and leadership transitions.** The governance regime in each run is a consistent decision function, not a personality. There are no leadership changes, no shifts in risk appetite driven by a new CEO's preferences, no political dynamics among an executive team. This is a deliberate simplification that isolates governance structure from the people who happen to be executing it.

- **Hiring, firing, and workforce changes.** The total labor available to the organization and its decomposition into teams are fixed for the duration of each run. The study does not model mid-run hiring surges, layoffs, attrition, or reorganizations. This holds the resource base constant so that governance decisions — not resource availability — drive outcome differences.

- **Exogenous macro shocks.** There are no market crashes, regulatory changes, competitor disruptions, or technology shifts during a run. The environment is uncertain (initiative quality is hidden, signals are noisy) but stable in its structure. This ensures that governance is responding to endogenous uncertainty — the difficulty of evaluating initiatives under imperfect information — rather than to external events.

- **Teams that autonomously adapt their own strategy.** In the model, teams execute. They do not independently decide to pivot, redefine scope, or pursue a different approach than what governance has sanctioned. Strategic adaptation is a governance function, not a team function. This is a simplification — real teams do adapt — but it is necessary to maintain the study's focus on governance as the unit of analysis.

- **Fractional team assignment.** A team works on one initiative or it is unassigned. There is no modeling of teams splitting their time across multiple initiatives. As discussed above, this reflects the judgment that partial commitment is qualitatively different from full commitment and is better excluded than poorly approximated.

- **Mid-run initiative creation by the engine or by governance.** New initiatives can emerge from the opportunity frontier during a run, but this emergence is handled by the orchestration layer between review cycles — not by the simulation engine during a tick, and not by governance requesting that new initiatives be created. Governance decides what to do with the initiatives that exist; it does not create new ones. This preserves the separation between the environment (which determines what opportunities are available) and governance (which determines what to do with them).

Any of these exclusions could be relaxed in a future version. An extension that, for example, introduces mid-run hiring should still preserve the study's ability to attribute outcome differences to governance — governance should not see latent quality, decisions should take effect with appropriate delay, and the comparison across regimes should remain controlled.

## Relationship to other documents

### Academic
- **Authority** — `study_overview.md` is authoritative about phenomena and scope; the technical docs are authoritative about mechanics and interfaces. This document distills the structural principles and abstractions that both layers presuppose.
- **Changes** — Changes to the principles or scope boundaries defined here require explicit design decisions with documented rationale. They may be warranted by calibration evidence, expert feedback, or implementation experience — but they affect the study's experimental methodology and should be made deliberately.

### Business
- **Authority.** This document occupies a specific position in the project's authority structure. The study overview is authoritative about what phenomena the study examines and why — the conceptual framing, the practitioner-facing interpretation, and the deliberate simplifying assumptions. The technical documents are authoritative about the detailed mechanics — equations, state variables, interface contracts, and tick ordering. This document distills the structural principles and abstractions that both of those layers presuppose. It answers the question that sits beneath both: *What commitments define the study's methodology?*

- **Changes.** Changes to the principles in this document are possible and may be warranted by calibration findings, expert review, or the need to simplify. But they should be made as explicit design decisions, not as incidental implementation changes, because they affect the study's ability to produce interpretable results. Document the rationale for any change so future readers understand why it was made.
