# Architecture & Non-Negotiable Invariants

This file defines the canonical architectural invariants, top-level execution model, and system boundaries that all other design files must obey. It is the highest-level technical contract for the simulation.

The simulation is a discrete-time Monte Carlo study of governance over a portfolio of initiatives whose true quality is latent and only gradually inferable from noisy signals. A single governance policy, represented as a parameterized decision rule, acts at review points over evolving initiative, team, and capability state. The same simulated worlds are evaluated under multiple governance regimes so that outcome differences can be attributed to policy differences rather than to different opportunity pools.

## Academic framing


### Academic
The Primordial Soup simulator can be understood as a **controlled stochastic process that is Markov on the full augmented execution state**. At each time step, the next state of the system depends only on the current state, the governance action, and a source of randomness. Formally, there exists an augmented state representation under which the system satisfies the Markov property:

\[
(S_{t+1}, R_{t+1}) = f(S_t, A_t, \theta, R_t)
\]

where \(S_t\) denotes the modeled world state, \(A_t\) the governance action, \(\theta\) fixed configuration parameters, and \(R_t\) the internal random number generator (RNG) state. Under this representation, the transition is deterministic given its inputs, and all stochasticity arises through the evolution of \(R_t\).

It is important to distinguish between **modeled state** and **execution state**. The modeled state \(S_t\) captures the phenomena of interest—initiative beliefs, execution estimates, capability accumulation, team assignments, and other variables that define the organization's evolving condition. By contrast, the RNG state \(R_t\) is not part of the modeled world; it is part of the simulation machinery that generates stochastic observations. Nevertheless, it must be included in the full execution state for the Markov property to hold.

Concretely, \(S_t\) comprises: per-initiative state (belief scalars `quality_belief_t` and `execution_belief_t`, lifecycle positions, team assignments, staffed-tick counters, assignment-relative ramp clocks, review counters, stagnation history buffers, observable histories, cumulative accounting, and residual activation state for completed initiatives), team state (assignment status and derived idle/assigned classification), portfolio-level capability stock \(C_t\), and all derived counters required by governance decision rules (e.g., `consecutive_reviews_below_tam_ratio`, `belief_history`). Residual value persistence is encoded in initiative state (completed initiatives with `residual_activated` and per-tick residual accounting) and the engine's residual pass, not in a separate residual object on `WorldState`. The RNG component \(R_t\) consists of the per-initiative random streams — two per initiative, one for strategic quality signals and one for execution progress signals — whose internal state determines the sequence of future stochastic observations.

From the perspective of governance, the process is **partially observable**. Decision-makers do not observe latent initiative quality or execution difficulty directly; instead, they act on noisy signals and derived beliefs. The resulting decision problem is therefore most naturally described as a **partially observable Markov decision process (POMDP)**. While the system exhibits exploration–exploitation dynamics reminiscent of multi-armed bandit problems, it departs from classical bandit formulations due to shared resource constraints, action-dependent information quality, lifecycle dynamics, and portfolio-level coupling.

To be precise about these departures: (1) initiatives share scarce resources — teams and executive attention — creating allocation interdependencies absent in standard multi-armed bandits; (2) the quality of information the decision-maker receives about each initiative depends on the decision-maker's own attention allocation, making information quality endogenous to the policy rather than exogenous; (3) initiatives have finite lifecycles that progress toward completion or termination, unlike the indefinite-horizon arms in classical formulations; and (4) outcomes across the portfolio are coupled through shared organizational capability \(C_t\), which enters the observation model for all initiatives simultaneously and evolves as a function of which initiatives complete.

The key implication is that the Markov property is not a restrictive modeling assumption but a **design discipline**: all variables that influence future evolution must be represented in the state. The primary risk is not the separation of RNG from the modeled state, but the omission of relevant state variables altogether. If any future-relevant driver—such as a belief, counter, buffer, or latent transition variable—is not represented, the implemented process ceases to be Markov on the represented state.

The consequence of a violated Markov property is not merely theoretical. If the system's future trajectory depends on a variable not tracked in \((S_t, R_t)\), then identical augmented states can produce different future trajectories — destroying both the reproducibility guarantee (identical inputs no longer produce identical outputs) and the common-random-numbers comparability (outcome differences between governance regimes may arise from untracked state divergence rather than from policy differences). The Markov property on the augmented state is therefore the engineering foundation on which the study's entire comparative analysis rests.

### Business
The Primordial Soup simulation models an organization managing a portfolio of initiatives over time, where every aspect of how the world evolves from one week to the next is fully determined by three things: the current state of the organization and its portfolio, the governance decisions made that week, and the specific random draws that generate the week's evidence. Nothing else matters. No hidden memory, no unmodeled influence, no accumulated context outside the represented state affects what happens next.

This property — that the future depends only on the present, not on the path that led there — is fundamental to the simulation's design discipline. It means that the simulation's complete operational state at any given week contains everything needed to determine all future weeks. That state includes two conceptually distinct parts:

The first is the **modeled organizational state**: the portfolio of initiatives with their current beliefs, execution estimates, lifecycle positions, and team assignments; the organization's accumulated capability; the active residual value streams; and all the counters, histories, and derived quantities that governance uses to make decisions. This is the state that represents the phenomena under study — the evolving condition of the organization as governance acts on it.

The second is the **random number generator state**: the internal machinery that produces the weekly stream of noisy evidence about each initiative's strategic quality and execution progress. This is not part of the modeled organization — it is part of the simulation infrastructure that generates the uncertainty governance must navigate. But it must be tracked as part of the complete execution state because the specific sequence of evidence an initiative produces depends on where its random stream currently stands.

From governance's perspective, the process is **partially observable**. Leadership cannot see the true underlying quality of any initiative, cannot see the true execution difficulty, and cannot see whether a right-tail initiative will turn out to be a major win. Governance acts on noisy signals and evolving beliefs — observable proxies for hidden truths. The resulting decision problem shares characteristics with well-studied problems in decision theory where a decision-maker must balance learning (gathering information to improve future decisions) against acting (deploying resources based on current, imperfect knowledge). However, it departs from classical formulations of such problems because initiatives share scarce resources (teams and executive attention), because the quality of information governance receives depends on its own attention allocation decisions, because initiatives have lifecycles that progress and terminate, and because outcomes across the portfolio are coupled through shared organizational capability.

The practical implication of this design is not abstract. It is a **concrete engineering discipline**: every variable that could influence what happens next must be explicitly represented in the state. If any relevant driver — a belief, a counter, a rolling history buffer, a latent attribute — is omitted from the represented state, the simulation's behavior becomes dependent on information that is not tracked, which means it cannot be reliably reproduced, audited, or compared across governance regimes. The primary risk is not the conceptual separation of random machinery from modeled state (that distinction is clean), but the accidental omission of a state variable that turns out to matter. If an initiative's future trajectory depends on something that is not in the state, the simulation has a hidden dependency — and hidden dependencies destroy the reproducibility and comparability that the entire study rests on.

## Non-negotiable invariants


### Academic
1. **Type-independence**
   - Initiative *labels* (e.g., flywheel, right-tail, enabler, quick-win) are **metadata** used for:
     - generation presets (priors) before simulation start, and
     - reporting/aggregation after simulation.
   - The core simulator and `SimulationConfiguration` must not branch on labels. All type-specific parameterization must be resolved into concrete initiative attributes before the engine receives them.
   - This invariant has a direct extensibility consequence: new initiative families can be introduced, existing families renamed or reorganized, and none of these changes require any modification to the engine — provided the new or modified families are expressible as combinations of the existing immutable attributes and canonical value-channel mechanisms defined in `initiative_model.md`.

2. **Attribute-based engine**
   - The engine evolves initiative **attributes** and **mutable state** (beliefs, lifecycle, assignments). Initiative behaviour must be expressible entirely using attributes (latent_quality, dependency_level, value channels, etc.).
   - This is the implementation-level consequence of type-independence: the engine's vocabulary consists of resolved attributes (`latent_quality`, `dependency_level`, `base_signal_st_dev`, `value_channels`, `observable_ceiling`, `capability_contribution_scale`, etc.) and mutable state (`quality_belief_t`, `lifecycle_state`, `staffed_tick_count`, etc.), not labels or taxonomic categories.

3. **No team splitting**
   - Teams are indivisible units. A team may only be assigned to at most one initiative at a time. No fractional splitting across initiatives.
   - Teams cannot be aggregated to satisfy a staffing requirement. If an initiative requires `required_team_size = k` and no single available team has `team_size >= k`, the initiative remains unstaffed. The engine does not combine multiple smaller teams to meet the threshold. This constraint means the team decomposition (the partition of total labor endowment into discrete teams) has direct consequences for the effective opportunity set — which initiatives in the pool are staffable.

4. **Action timing**
   - Governance computes actions at the end of tick T. Actions become effective at **start-of-tick T+1** (unless an explicit exception is stated).
   - Stopping an initiative frees its team at start-of-T+1.
   - Attention allocated at end-of-tick T governs signal quality during tick T+1. There is no same-tick feedback from actions to observations unless a specific documented exception is defined.

5. **Fixed workforce (canonical scope)**
   - Canonical experiments assume a fixed labor endowment and a fixed realized
     team pool within a run. Hiring/firing or dynamic team counts are
     experiment-level options, not core behaviour.
   - How that labor endowment is decomposed into teams is an upstream
     governance-architecture choice, not an engine concern.
   - Any future experiment introducing dynamic workforce changes must be explicitly designed and documented as a variant, not folded into the baseline model.

6. **Engine observability**
   - Governance and policies see only observable fields and belief states — never latent ground truth (e.g., latent_quality).
   - The engine must preserve an observation boundary: latent attributes exist but are hidden from policies.
   - The latent variables hidden from governance include `latent_quality` (q), `true_duration_ticks`, `latent_execution_fidelity` (q_exec), and the `is_major_win` flag. If the policy could condition on any of these, the study would be evaluating differential information access rather than differential policy performance — invalidating the causal identification strategy that attributes outcome differences to governance decisions under a shared stochastic environment.

7. **Deterministic runner responsibility**
   - If `initiative_generator` is used, the runner deterministically resolves it (using `world_seed`) to a fully resolved `initiatives` list prior to simulation. The runner records the resolved list and generator parameters in the run manifest.
   - The resolution must be deterministic: the same generator specification and the same `world_seed` must always produce the same pool. The engine always receives a resolved list and is agnostic to how it was produced.

8. **Belief belongs to the initiative, not the team**
   - Quality belief (observable as `quality_belief_t` in initiative state) is initiative
     state, not team state. It persists across team reassignments: a new team
     assigned to an initiative inherits the initiative's current belief. An
     initiative that is unassigned retains its accumulated belief. The engine owns
     and updates this value; no policy or team object holds a private copy.
   - Belief does not reset on reassignment and does not transfer with the departing team. An initiative between team assignments retains its full accumulated belief trajectory. This reflects the modeling assumption that organizational assessment of an initiative is institutional knowledge, not private knowledge of the currently assigned team.

9. **Per-initiative random streams (CRN invariant)**
   - Each initiative has two dedicated random streams, seeded deterministically from
     `world_seed` and `initiative_id` at pool generation time:
     ```
     quality_signal_rng(initiative_id)  = RNG(seed_from(world_seed, initiative_id, "q"))
     exec_signal_rng(initiative_id)     = RNG(seed_from(world_seed, initiative_id, "exec"))
     ```
     where `seed_from(a, b, tag)` derives a 64-bit integer seed from
     SHA-256(`f"{a}:{b}:{tag}"`), using the first 8 bytes of the digest.
   - Quality signal draws use `quality_signal_rng`; execution signal draws use
     `exec_signal_rng`.
   - A single global stream seeded by `world_seed` is **prohibited**. After any tick
     where two regimes differ in their active initiative set, a global stream diverges
     between regimes, destroying the common-random-numbers (CRN) property that makes
     comparative results attributable to governance differences rather than sampling
     differences.
   - Per-initiative streams ensure that governance decisions affecting which initiatives
     are active in a given tick do not shift the observation draws for any other
     initiative. Two runs sharing the same `world_seed` receive identical observation
     noise for each initiative regardless of governance regime.
   - **RNG abstraction requirement:** the implementation must isolate all seed
     derivation and stream construction behind a single module-level abstraction so
     that a future migration to stream-based RNG (e.g., MRG32k3a streams/substreams
     as used by SimOpt) can be done by replacing that abstraction without touching
     engine or policy code.

### Business
These are the foundational rules that the simulation must never violate. They are not guidelines or preferences — they are structural commitments that, if broken, would invalidate the study's ability to produce meaningful governance comparisons. Every implementation decision must be consistent with all nine.

**1. Type-independence.** Initiative type labels — flywheel, right-tail, enabler, quick win — are organizational vocabulary, not operational categories. They serve two purposes: they are used when designing scenarios (setting up the initiative pool with the right mix of characteristics) and when interpreting results (aggregating outcomes by type to understand what happened). But the simulation engine itself must never apply different rules, different logic, or different treatment based on which label an initiative carries. All type-specific characteristics — the fact that flywheels tend to have persistent value streams, that right-tail initiatives tend to have high noise and major-win potential, that enablers contribute organizational capability — must be fully resolved into concrete attribute values before the engine sees them. If a new type were defined tomorrow, or an existing type renamed, the engine would not need to change.

**2. Attribute-based engine.** The engine operates on initiative attributes and evolving state — beliefs, lifecycle positions, team assignments, value channel configurations — not on labels, categories, or type classifications. Every aspect of how an initiative behaves in the simulation must be expressible through its concrete attributes: its true quality, its dependency level, its value channels, its signal noise, and the other properties defined in the initiative model. This is the implementation-level consequence of type-independence: the engine's vocabulary is attributes and state, not organizational taxonomy.

**3. No team splitting.** Teams are indivisible. A team can be assigned to at most one initiative at a time. It cannot be fractionally deployed across multiple initiatives, and multiple teams cannot be combined to satisfy a single initiative's staffing requirement. This constraint is not an implementation shortcut — it reflects a deliberate modeling choice about how organizations deploy cohesive working units.

**4. Action timing.** Governance makes decisions at the end of each week based on what it has observed. Those decisions take effect at the start of the following week. This one-week delay between decision and effect is a hard rule, not an approximation. When governance stops an initiative, the team becomes available for reassignment at the start of the next week. When governance allocates attention, that attention governs the next week's signal quality. There is no same-week course correction unless a specific, documented exception is stated.

**5. Fixed workforce (canonical scope).** The canonical study assumes a fixed total labor endowment and a fixed team structure throughout each run. There is no hiring, firing, or mid-run team restructuring. How the total workforce is divided into teams is a governance-architecture choice made before the run begins — it is an upstream organizational design decision, not something the engine manages. Any future experiment that introduces dynamic workforce changes would need to be explicitly designed and documented as a variant, not silently folded into the baseline.

**6. Engine observability.** Governance sees only what the observation boundary permits: observable initiative attributes, evolving belief summaries, resource state, and governance configuration. It never sees latent ground truth — not the true quality of any initiative, not the true execution difficulty, not whether a right-tail initiative is destined to be a major win. The engine maintains these hidden truths because they are needed to generate outcomes and noisy evidence, but they are structurally invisible to any governance logic. This is not a visibility preference. It is a hard architectural wall. If governance could see hidden truth, the study would be measuring omniscience, not governance.

**7. Deterministic runner responsibility.** If an initiative generator is used (rather than a hand-specified list), the runner must resolve it into a fully materialized, concrete list of initiatives before the simulation begins, using the world seed. This resolution must be deterministic — the same generator specification and the same seed always produce the same pool. The runner records both the resolved list and the generator parameters in the run manifest. The engine always receives a resolved list and is agnostic to how it was produced.

**8. Belief belongs to the initiative, not the team.** The organization's evolving belief about an initiative's strategic quality is a property of the initiative, not of the team currently working on it. When a new team is assigned to an initiative, it inherits the initiative's current belief — the accumulated organizational assessment of that initiative's promise. The belief does not reset, does not transfer with the departing team, and does not start fresh with the new team. An initiative that sits unassigned between team assignments retains its accumulated belief. The engine owns and updates this value; no governance policy or team holds a private copy. This reflects the organizational reality that institutional knowledge about an initiative's prospects lives in the organization's records and collective assessment, not in the heads of the specific people currently assigned to it.

**9. Per-initiative random streams (common random numbers).** Each initiative has two dedicated random streams — one for strategic quality signals and one for execution progress signals — seeded deterministically from the world seed and the initiative's unique identifier at the moment the pool is created. A single shared random stream for the entire simulation is explicitly prohibited. The reason is fundamental to the study's comparative method: once two governance regimes make different decisions about which initiatives to staff, a shared stream would diverge between regimes, meaning the two regimes would receive different evidence for the same initiative — destroying the ability to attribute outcome differences to governance rather than to different luck. With per-initiative streams, two regimes sharing the same world seed receive identical weekly evidence for any given initiative regardless of what they have done with every other initiative in the portfolio. The comparison reflects governance differences, not sampling differences.

The seed derivation for each stream follows a deterministic, auditable formula: the world seed, the initiative identifier, and a stream-type tag are combined through a standard cryptographic hash to produce the stream's seed. The implementation must isolate all seed derivation and stream construction behind a single module-level abstraction, so that any future change to the random number generation technology can be made by replacing that abstraction without touching any engine or governance code.

## Notation (canonical)

### Academic
Equations in the design corpus use the following compact symbols. In prose, schema commentary, and code, prefer the descriptive names from `docs/study/naming_conventions.md`.

- `q` — latent_quality (latent initiative quality, true-world scalar)
- `c_t` — quality_belief_t (organization's posterior mean estimate of latent quality at tick t)
- `d` — dependency_level (initiative dependency in [0,1])
- `σ_base` — base_signal_st_dev (base observation noise for an initiative)
- `α_d` — dependency scaling of observation noise
- `g(a)` — attention_noise_modifier; parameters: `a_min`, `k_low`, `k`, `g_min`, `g_max`
- `L(d)` — learning efficiency; canonical default `L(d)=1-d`
- `η` — learning_rate (base learning rate)

(Equations keep compact symbols; implementation and explanatory prose use the descriptive names.)

In this document, equations and formal definitions use the compact symbols listed above. All explanatory prose, pseudocode, and schema references use the descriptive names. Where both forms appear in the same passage, the compact symbol is parenthetical: e.g., "the strategic quality belief (`c_t`) is updated each staffed tick."

### Business
The design corpus uses two parallel naming systems. Equations and mathematical formulas use compact symbols for conciseness: `q` for true quality, `c_t` for the organization's quality belief at a given point in time, `d` for dependency level, `σ_base` for baseline signal noise, and so on. Code, configuration, reporting, and all explanatory prose use full descriptive names: `latent_quality`, `quality_belief_t`, `dependency_level`, `base_signal_st_dev`. The canonical mapping between the two systems is maintained in the project's naming conventions reference.

In this document and throughout the business-register design corpus, descriptive names are used exclusively. Where a concept has a corresponding mathematical formula in the technical specification, the descriptive name is used in prose and the formula is expressed in terms of what it governs and what organizational consequences it produces, rather than reproduced in symbolic form.

## Purpose of the architecture


### Academic
This architecture exists for two reasons. The first is analytical clarity. It should let a reader understand exactly what system is being simulated, what mechanisms are present, what mechanisms are intentionally absent, and which outputs can legitimately be interpreted as evidence about governance. The second is implementation clarity. It should give a coding model a precise top-level contract for how the simulator is structured and where each kind of logic belongs.

This is not a general organizational simulation. It is a deliberately scoped model of governance over a portfolio of initiatives under uncertainty. The central object of study is not culture, politics, morale, or dynamic labor-market adjustment. The central object of study is the effect of governance decisions on discovery, value realization, persistent mechanisms, and portfolio capability over time.

The deliberate narrowness of scope is what makes the study's findings attributable. A model that incorporated behavioral dynamics (morale effects, political maneuvering, endogenous proposal quality degradation) alongside the governance mechanisms under study would produce results confounded with those uncontrolled dynamics. By excluding them, the architecture ensures that outcome differences across governance regimes can be attributed to the policy mapping from observations to actions — the object of study — rather than to interaction effects with mechanisms outside the study's scope.

### Business
The architecture exists for two reasons, both of which matter equally.

The first is **analytical clarity**. The architecture should let a reader — whether a governance practitioner, a research collaborator, or an analyst reviewing findings — understand exactly what the simulation models, what mechanisms are present, what mechanisms are deliberately absent, and which outputs can legitimately be interpreted as evidence about governance. If a mechanism is not in the model, no finding should be attributed to it. If a mechanism is in the model, a reader should be able to trace exactly how it works and what it affects.

The second is **implementation clarity**. The architecture should give the engineering team a precise contract for how the simulator is structured and where each kind of logic belongs — what the engine owns, what governance controls, what the runner is responsible for, and how these boundaries are enforced. Ambiguity in ownership leads to bugs that are difficult to diagnose and, worse, to silent violations of the study's observation boundary or reproducibility guarantees.

This is not a general organizational simulation. It does not attempt to model corporate culture, office politics, employee morale, executive personalities, or the dozens of other factors that shape real organizational outcomes. It is a deliberately scoped model of one specific phenomenon: the effect of governance decisions — how leadership allocates attention, assigns teams, and decides when to continue or stop — on discovery, value realization, persistent value mechanisms, and organizational capability development over time. The deliberate narrowness of scope is what makes the findings interpretable. A model that tried to include everything would produce results that could not be attributed to anything in particular.

## Architectural overview


### Academic
At the highest level, the simulator consists of five layers.

The first layer is the **runner**, which resolves configuration, seeds random number generators, materializes the initiative pool when generation is configured, and ensures that each policy regime is evaluated against the same world seed.

The second layer is the **engine**, which owns all mutable simulation state and advances the world by one discrete tick at a time according to canonical ordering rules. Its responsibilities include applying governance actions, generating stochastic observations, updating belief scalars, detecting lifecycle transitions (completion, residual activation, capability update, major-win events), realizing value, and maintaining every counter, buffer, and derived quantity that governance or reporting requires. The engine is the single source of truth for the current state of the world.

The third layer is the **domain state**, which consists of initiatives, teams, capability state, persistent value mechanisms, and any experiment-level bookkeeping required for metrics and provenance.

The fourth layer is the **governance policy**, which is a pure decision function from the current observation bundle and configuration parameters to an action vector. The policy does not own mutable simulation state. It does not maintain private memory across ticks. Its decisions are fully determined by its inputs — a property that makes governance regimes comparable, since every decision is fully explained by the observation available at the decision point.

The fifth layer is the **reporting layer**, which records time-series outputs, terminal outputs, manifests, and experiment comparisons. Reporting logic observes and records; it does not influence the simulation's state transitions or governance decisions.

These layers are intentionally separated so that state mutation, decision logic, and reporting logic cannot become entangled. This separation is a structural requirement for reproducibility and auditability, not an organizational convenience.

### Business
At the highest level, the simulation consists of five layers, each with a distinct responsibility. The separation is not an organizational convenience — it is a structural requirement that prevents state mutation, decision logic, and reporting logic from becoming entangled in ways that would compromise reproducibility and auditability.

**The runner** is the orchestration layer. It resolves configuration, seeds all random number generators, materializes the initiative pool when a generator specification is used rather than a hand-specified list, and ensures that each governance regime being compared is evaluated against the same simulated world. The runner is responsible for everything that must happen before the simulation begins and everything that must happen to ensure comparisons are valid.

**The engine** owns all mutable simulation state and advances the world one week at a time according to the canonical ordering rules defined in the core simulator specification. It applies governance decisions, generates evidence, updates beliefs, detects completions, realizes value, and maintains every counter, buffer, and derived quantity that governance or reporting needs. The engine is the single source of truth for what the state of the world is at any given moment.

**The domain state** consists of the concrete entities the engine operates on: initiatives with their attributes and evolving state, teams with their assignments and availability, the organization's accumulated capability, active persistent value mechanisms, and any experiment-level bookkeeping required for metrics and provenance. This is the organizational reality that the simulation represents — the portfolio, the people, and the institutional knowledge that governance acts upon.

**The governance policy** is a pure decision function. It receives the current observation snapshot — what governance can see about the portfolio — and the governance configuration — the regime's decision rules and thresholds — and produces a complete set of decisions for the week. It does not own mutable simulation state. It does not maintain private memory across decision points. It computes its decisions from what it is given and returns them. This purity is what makes governance regimes comparable: every decision is fully explained by what the regime could see at the moment it decided.

**The reporting layer** records everything the study needs for analysis: per-week time-series outputs, terminal state snapshots, provenance manifests, and the structured event logs that enable cross-regime comparison. Reporting logic observes and records; it never influences what happens in the simulation.

## Simulation worldview


### Academic
The canonical worldview is discrete-time and policy-driven. A single governance policy is invoked at every tick. For every active staffed initiative, the policy must emit an explicit ContinueStop decision; there is no abstain option and silence on an active staffed initiative is a protocol violation. Differences in effective review depth arise from policy behavior — specifically, from how carefully the policy examines each initiative before deciding — not from any engine-level cadence gate. Initiatives and teams are not autonomous agents. They are stateful entities whose trajectories are generated by update equations, assignment state, and stochastic observations. There is no independent initiative agency and no emergent strategic behavior outside the mechanisms explicitly modeled.

To be explicit about the absence of behavioral adaptation: there is no mechanism by which an initiative's signal generation responds to governance attention (beyond the explicit `g(a)` modulation of `σ_eff`), no mechanism by which a team's productivity adapts to governance scrutiny, and no mechanism by which an initiative anticipates termination and adjusts its observable outputs. The phenomena captured in the model — learning dynamics, signal clarity, capability accumulation — operate exclusively through the mechanisms specified in the design corpus. Any behavioral response not formalized as a state transition or signal-generation rule is absent from the model by construction.

The same resolved initiative pool must be run under multiple governance archetypes with shared world seeds. That requirement is fundamental to causal interpretability. A policy comparison is valid only if the policies face the same underlying opportunity distribution and stochastic environment. If any element of the stochastic environment — the initiative pool, the latent quality draws, the execution difficulties, or the per-initiative observation sequences — differs across regimes being compared, outcome differences cannot be attributed to governance policy. They may instead reflect differences in the realized opportunity environment, which would confound the causal identification strategy.

### Business
The simulation operates in discrete time — one governance cycle per week — and is driven entirely by governance policy decisions. A single governance policy is invoked at every decision point. For every active, staffed initiative, the policy must produce an explicit continue-or-stop decision. There is no abstain option. Silence about an active staffed initiative is a protocol violation, not a default continuation. If a governance regime wants to vary how deeply it scrutinizes different initiatives — paying close attention to some and giving others only a cursory glance — it does so through how it computes its decision, not by skipping initiatives.

Initiatives and teams are not autonomous agents. They do not make strategic decisions, they do not adapt their behavior, and they do not exhibit emergent agency. They are stateful entities whose trajectories are fully determined by the simulation's update mechanics, their assignment state, and the stochastic evidence they produce each week. There is no independent initiative behavior outside the mechanisms explicitly modeled. An initiative does not "try harder" when it senses it might be stopped. A team does not "work smarter" when governance pays more attention. The organizational phenomena captured in the model — learning, signal quality, capability accumulation — operate through the specific mechanisms defined in the design corpus, not through implicit behavioral responses.

The requirement that the same resolved initiative pool must be run under multiple governance regimes with shared world seeds is fundamental to the study's causal interpretability. A governance comparison is valid only if every regime faces the same underlying opportunity distribution, the same initiative qualities, the same execution difficulties, and the same sequence of weekly evidence. If any of these differ, outcome differences cannot be attributed to governance choices — they might simply reflect better or worse luck with the draw.

## Top-level entities


### Academic
The architecture assumes the following top-level conceptual entities.

`SimulationConfiguration` is the full declarative specification of a run or experiment. It includes horizon, tick semantics, initiative presets or generator settings, workforce settings, governance parameters, stop criteria thresholds, value mechanism parameters, and output controls.

At the implementation boundary, the engine consumes a **realized**
configuration. The upstream builder/preset/campaign layer may distinguish
environmental conditions, governance architecture, and operating policy, but
those distinctions are compiled into the declarative `SimulationConfiguration`
before simulation begins.

`RunManifest` is the exact record of what was executed. It includes the resolved configuration, world seed, policy identifier, resolved initiative list, and any runner-level derivations that were computed before the simulation began. The manifest is the canonical provenance artifact: given a manifest, any analyst must be able to reproduce the exact run and obtain identical outputs.

`WorldState` is the complete mutable state owned by the engine during execution. It contains all initiatives, teams, capability state, persistent mechanisms, active assignments, tick counters, and accumulated metrics buffers required for later reporting. It is the single source of truth for the state of the simulated world at any tick.

`InitiativeState` is the mutable per-initiative state, including lifecycle position, assignment status, belief state, observable history, and derived counters needed by governance rules. Specifically, this includes: the consecutive-review counter (`consecutive_reviews_below_tam_ratio`), the stagnation belief history buffer (`belief_history`), the review count, staffed-tick and assignment-relative clocks, cumulative value and labor accounting, and residual activation status.

`GovernanceObservation` is the policy-visible projection of the world. It is a read-only structure derived by the engine from `WorldState` at the end of each tick and contains only observable fields plus permitted belief summaries. It is the information boundary: everything governance is permitted to observe, and nothing beyond.

`GovernanceActions` is the action vector produced by the policy each tick. It specifies stops, assignments, reassignments, attention settings, and any other supported control actions.

`SimulationEngine` is the imperative shell that owns the tick loop and applies all state transitions.

`GovernancePolicy` is the pure decision rule that maps observation plus config to actions.

### Business
The architecture is organized around a small number of clearly defined entities, each with a specific role and ownership boundary.

**SimulationConfiguration** is the complete, declarative specification of a run. It includes the time horizon, the initiative pool or generator specification, workforce structure, governance parameters, stop-rule thresholds, value mechanism parameters, and output controls. At the simulation boundary, this configuration is a single resolved object — the engine does not know or care whether it was assembled from an environment archetype, a parameter sweep, or hand-crafted for a specific scenario. The upstream process that produced the configuration — distinguishing environmental conditions, governance architecture, and operating policy — compiles those distinctions into the declarative configuration before the simulation begins.

**RunManifest** is the exact provenance record of what was executed. It captures the resolved configuration, the world seed, the governance regime identifier, the fully materialized initiative list, and any runner-level derivations computed before the simulation began. This is the artifact that makes any finding reproducible: given the manifest, any analyst can recreate the exact run.

**WorldState** is the complete mutable state that the engine owns and evolves during execution. It contains every initiative with its current beliefs and lifecycle state, every team with its assignment status, the organization's accumulated capability, all active persistent value mechanisms, and the metrics buffers that accumulate evidence for reporting. This is the single source of truth for the state of the simulated world at any moment.

**InitiativeState** is the mutable per-initiative state within the world. It includes the initiative's lifecycle position (unassigned, active, stopped, completed), its current team assignment, the organization's evolving belief about its strategic quality, the full observation history, and all derived counters needed by governance rules — consecutive review trackers, stagnation buffers, review counts, and staffed-time clocks.

**GovernanceObservation** is the policy-visible projection of the world. It is a read-only snapshot that the engine constructs at the end of each week from the full world state, containing only observable fields and permitted belief summaries. This is the information boundary — everything governance is allowed to know, and nothing it is not.

**GovernanceActions** is the complete set of decisions that governance produces each week: which initiatives to continue or stop, which teams to assign where, and how to allocate executive attention across the portfolio.

**SimulationEngine** is the imperative shell that owns the weekly cycle — applying governance decisions, generating evidence, updating beliefs, detecting completions, realizing value, and advancing the clock.

**GovernancePolicy** is the pure decision function that maps the observation snapshot plus the governance configuration to a complete action vector.

## Ownership of mutable state


### Academic
The engine owns all mutable simulation state. This includes not only latent initiative attributes and operational state, but also belief state and any derived counters or sufficient statistics that governance needs in order to make decisions.

This point is important because belief-tracking and stop rules can easily tempt an implementation toward hidden policy memory. That is not the intended design. The policy is not a stateful controller in the sense of owning private evolving memory across ticks. Instead, the evolving memory of the system is part of `WorldState`, especially `InitiativeState`, and is surfaced to the policy through the observation boundary in an explicit and replayable way.

Concretely, `c_t` belongs to initiative state, not to the policy object. Rolling or consecutive-review counters used by stop criteria also belong to initiative state, not to the policy object. If the policy needs stagnation windows, TAM adequacy streaks, or review-age summaries, those should exist as engine-maintained state or as deterministic functions over engine-maintained history.

This design preserves reproducibility, unit-testability, and the functional-core / imperative-shell separation.

The scope of engine-owned state extends to every quantity that a governance rule may depend on: `quality_belief_t`, `execution_belief_t`, `consecutive_reviews_below_tam_ratio`, the `belief_history` ring buffer used for stagnation detection, `review_count`, `staffed_tick_count`, `ticks_since_assignment`, and cumulative accounting fields. A design that allowed the policy to maintain private mutable copies of any of these quantities would create governance state invisible to the engine, invisible to the reporting layer, and impossible to reproduce from the manifest alone.

The ownership invariant preserves three specific properties. **Reproducibility:** any run can be exactly replayed from its manifest because all state is engine-owned and deterministically evolved from the resolved run input. **Unit-testability:** governance policies can be tested by constructing a `GovernanceObservation` with known values and verifying the resulting `GovernanceActions`, without simulating the full state evolution that produced the observation. **Architectural separation:** the engine is the functional core that owns and evolves state; governance is a pure function that transforms observations into actions; the runner is responsible for orchestration and provenance. These three responsibilities are separated by construction.

### Business
The engine owns all mutable simulation state. This is not a preference — it is a structural requirement that prevents a category of subtle, difficult-to-diagnose bugs from entering the system.

The ownership rule covers not only the obvious things — latent initiative attributes, team assignments, lifecycle positions — but also the less obvious ones: the organization's evolving belief about each initiative's strategic quality, the consecutive-review counters used by patience rules, the stagnation history buffers, and every other derived quantity that governance relies on when making decisions.

This point deserves emphasis because belief-tracking and stop rules can easily tempt an implementation toward hidden governance memory. It would be natural — and wrong — to let the governance policy maintain its own private records of how beliefs have evolved, its own running tallies of how many times an initiative has fallen below threshold, or its own assessment of which initiatives are stagnating. That design would create governance state that is invisible to the engine, invisible to the reporting layer, and impossible to reproduce from the manifest alone.

The intended design is different. The evolving memory of the system — every belief, every counter, every history buffer — lives in the engine-owned world state, specifically in the per-initiative state. That state is surfaced to governance through the observation boundary in an explicit, auditable, and replayable way. Governance reads these values when making decisions but does not own them, does not update them, and does not maintain private copies that diverge from the engine's authoritative values.

Concretely: the organization's belief about an initiative's strategic quality belongs to the initiative's state, not to the governance policy object. The consecutive-reviews-below-patience counter belongs to the initiative's state, not to the governance policy object. The stagnation history buffer, the review count, and every other running tally belongs to the engine. If governance needs any of these values to make a decision, the engine maintains them and surfaces them through the observation snapshot.

This design preserves three critical properties. Reproducibility: any run can be exactly replayed from its manifest because all state is engine-owned and deterministically evolved. Testability: governance policies can be unit-tested by constructing an observation snapshot and verifying the resulting decisions, without needing to simulate the full state evolution that produced the snapshot. Architectural clarity: the engine is the functional core that owns and evolves state; governance is a pure decision function that transforms observations into actions.

## Policy purity and observation boundary


### Academic
The governance policy is a pure function over the current observation bundle and the relevant governance configuration.

Canonical interface:

```python
class GovernancePolicy(Protocol):
    def decide(
        self,
        observation: GovernanceObservation,
        config: GovernanceConfig,
    ) -> GovernanceActions:
        ...
```

The policy may compute rankings, thresholds, scores, and derived decisions from the observation it is given. It may not access latent fields, mutate world state directly, or rely on hidden private memory from prior ticks.

This is the intended interpretation of invariant 6. The observation boundary is not merely a visibility preference. It is a hard architectural boundary. Latent initiative truth exists in the simulation because it is needed to generate outcomes and noisy observations, but policies never see it directly. Policies act only on what governance could plausibly know: observables, belief summaries, resource state, and configuration.

The boundary exists because the study's entire causal identification strategy depends on it. The study attributes outcome differences between governance regimes to differences in how they map observations to actions. If the policy could condition — intentionally or inadvertently — on latent state (`latent_quality`, `true_duration_ticks`, `is_major_win`) or on transition-kernel parameters (the `ModelConfig` block governing signal generation, belief dynamics, capability accumulation, and value realization), the comparison would evaluate differential information access rather than differential policy performance. Leakage of transition-model parameters into the policy boundary would invalidate the causal attribution.

The latent fields explicitly hidden from governance are: `latent_quality` (true strategic quality), `true_duration_ticks` (true completion time), `latent_execution_fidelity` (derived from the ratio of planned to true duration), `is_major_win` (the deterministic threshold function of `latent_quality`), and the internal state of the per-initiative RNG streams. The policy observes only the outputs of the observation process — belief scalars, derived counters, observable initiative attributes, and resource state — never the parameters governing how those outputs are generated.

### Business
The governance policy is a pure function. Given the same observation snapshot and the same governance configuration, it always produces the same decisions. It does not maintain hidden memory from prior weeks. It does not accumulate private knowledge that the engine cannot see. It does not access any information beyond what the observation boundary permits.

The observation boundary is not a visibility preference or a soft guideline. It is a hard architectural wall. On one side is the engine, which knows everything — the true quality of every initiative, the true execution difficulty, whether each right-tail initiative is destined to be a major win, and the complete internal state of every random stream. On the other side is governance, which knows only what the observation snapshot contains: observable attributes, belief summaries, review counters, patience trackers, resource state, and configuration parameters.

This boundary exists because the study's entire causal identification strategy depends on it. The study attributes outcome differences between governance regimes to differences in how they process observable information and make decisions. If governance could see hidden truth — even inadvertently, through a leaked field or a configuration parameter that reveals transition-model mechanics — the comparison would be measuring differential information access, not differential governance quality. The boundary ensures that what governance can act on is precisely what a real leadership team could plausibly know: evidence that has accumulated through work, beliefs that have been updated from that evidence, and the structural parameters that define the regime's decision rules.

Governance may compute rankings, thresholds, scores, and derived assessments from the information it is given. It may apply sophisticated logic to determine which initiatives to continue, which to stop, where to allocate attention, and which teams to assign. What it may not do is access latent fields (true quality, true duration, the major-win flag), mutate world state directly, or rely on private memory that was not provided through the observation snapshot.

## Sufficient statistics vs. raw history


### Academic
The architecture allows two legitimate ways for the engine to support governance decisions that depend on history.

The first is to maintain raw observable history on each initiative, such as a sequence of review records, confidence values, and observed signal summaries.

The second is to maintain explicit sufficient statistics or derived counters, such as:

- `consecutive_reviews_below_tam_ratio`
- `stagnation_window_size`

Both approaches are compatible with a stateless policy. The recommended implementation is to maintain explicit derived fields whenever doing so reduces ambiguity or repetitive recomputation. This study values clarity and implementation determinism more than extreme state minimalism.

For example, the `consecutive_reviews_below_tam_ratio` counter is maintained by the engine and surfaced directly to governance through `InitiativeObservation`, rather than requiring the policy to scan the full review history and compute the streak. Similarly, the `belief_history` ring buffer — a rolling deque of length `W_stag` containing recent quality beliefs at each staffed tick — is maintained by the engine for stagnation detection, rather than requiring the policy to access the complete lifetime belief trajectory. In both cases, the information lives in engine-owned `InitiativeState` and is surfaced through the observation boundary in an explicit, deterministic, and auditable form.

<!-- specification-gap: `stagnation_window_size` is listed as an example derived counter but is not a field defined in `InitiativeState` or `InitiativeObservation` in the canonical interfaces. The stagnation-relevant fields are `belief_history` (ring buffer) and `stagnation_window_staffed_ticks` (from `GovernanceConfig`). The reference should be to one of these rather than to an undefined `stagnation_window_size`. -->

### Business
Governance decisions sometimes depend on what has happened over time — not just the current snapshot, but patterns of change across weeks. The stagnation rule, for example, needs to know whether the organization's belief about an initiative has meaningfully shifted over a sustained window of active work. The bounded-prize patience rule needs to know how many consecutive reviews have fallen below a threshold.

The architecture supports two legitimate approaches for making historical information available to governance without violating the stateless-policy requirement.

The first is to maintain the raw observable history on each initiative — the sequence of weekly belief values, review records, and observation summaries that have accumulated over the initiative's life. Governance could then compute any historical pattern it needs from the raw data.

The second is to maintain explicit derived quantities — pre-computed counters and summary statistics that the engine updates each week. For example, the consecutive-reviews-below-patience counter is maintained by the engine and surfaced directly to governance, rather than requiring governance to scan the full review history and count the streak itself. Similarly, the stagnation belief history buffer is maintained by the engine as a rolling window of recent belief values, rather than requiring governance to access the complete lifetime belief trajectory.

Both approaches are compatible with a stateless governance policy, because in both cases the information lives in engine-owned initiative state and is surfaced through the observation boundary. The recommended approach is to maintain explicit derived quantities whenever doing so reduces ambiguity or eliminates the need for governance to recompute the same historical pattern every week. This study values clarity and implementation determinism — knowing exactly what the engine is tracking and exactly what governance receives — over extreme state minimalism.

## Time model and event ordering


### Academic
Time advances in discrete ticks. A tick represents one unit of modeled organizational time, to be fixed in configuration and documented consistently across experiments.

The canonical event ordering is:

1. start-of-tick application of actions decided at the end of the prior tick;
2. initiative execution and state advancement during the tick;
3. signal generation and observation construction;
4. belief update and derived-state update inside the engine, including lifecycle transitions (completion detection, residual activation, capability update, and completion-time major-win events);
5. value realization for the tick using end-of-tick state (completion-lump value at the completion transition; residual value in a separate pass);
6. end-of-tick governance decision, producing actions for the next tick.

This ordering makes the existing action-timing invariant explicit. Governance never makes a decision and receives the operational consequence in the same instant unless a narrower exception is defined elsewhere and documented explicitly.

The ordering is deterministic and the steps are not interchangeable. Each step's inputs and outputs are defined precisely in `core_simulator.md`. Key dependencies between steps:

- Step 1 (action application) determines which initiatives are staffed and what attention levels they receive for the tick, controlling the inputs to step 3 (signal generation).
- Steps 2–3 produce the raw stochastic observations (`y_t`, `z_t`) that drive step 4 (belief update).
- Step 4 must complete — including all lifecycle transitions, completion-lump value realization at the completion transition, and capability update — before step 5 (residual value pass), because residual streams activated at step 4's completion transition contribute in the same tick's residual pass.
- Step 6 (governance) observes the fully updated end-of-tick state, including any completions, major-win events, and belief changes from the current tick. Its decisions shape the following tick via step 1.

This one-tick separation between observation and intervention is the minimal temporal structure required to ensure that governance acts on observed state, not on consequences of actions it has not yet seen realized. It corresponds to the one-period information delay in the POMDP formulation: the policy is measurable with respect to the observation filtration at tick `t`, and its actions alter the system only at tick `t+1`.

### Business
Time advances in discrete weekly periods. Each week represents one unit of modeled organizational time, with the specific real-world mapping (weekly, monthly, or otherwise) fixed in the configuration and documented consistently across experiments.

Within each week, events unfold in a strict, deterministic order. This ordering matters because it determines what information is available when, what consequences follow from which events, and where value is actually realized. The canonical sequence is:

**1. Last week's decisions take effect.** Governance actions decided at the end of the prior week — stops, team assignments, attention allocations — are applied at the start of this week. These actions control the operating state for the entire week.

**2. Initiatives generate evidence and advance.** Every staffed initiative produces its weekly strategic quality signal and execution progress signal. Teams do their work, staffed-time clocks advance, and the raw observations that will drive belief updates are generated.

**3. Evidence is processed into updated knowledge.** The engine constructs the observation from the raw signals and updates the organization's beliefs about each initiative's strategic quality and execution progress.

**4. Beliefs are updated and lifecycle transitions are detected.** The engine updates both belief scalars, detects any completions, activates residual value mechanisms, records major-win discoveries, and updates organizational capability — all using the end-of-week state. This includes all the consequential lifecycle events: completion-lump value realization at the completion transition, residual activation, and capability contribution from completed enablers.

**5. Value is realized for the week.** Using end-of-week state, the engine realizes the week's value: completion-lump value at the completion transition (exactly once per completion), and residual value from all previously activated persistent mechanisms in a separate pass.

**6. Governance makes its decisions for the coming week.** With the fully updated state in hand — including any completions, major-win discoveries, and belief changes from this week — governance produces its action vector for the next week.

This ordering makes the action-timing invariant concrete. Governance never makes a decision and sees the operational consequence in the same week. Decisions made at the end of this week shape next week's reality. This one-week separation between observation and intervention is the minimal temporal structure needed to ensure that governance is acting on what it has observed, not on consequences of actions it has not yet seen play out.

## Value channels


### Academic
The simulation supports channel-separated accounting of organizational outcomes.

1. **Completion-lump channel**
   - Represents one-time realized value at completion.
   - This is a completion-gated economic channel, not a streaming channel.

2. **Residual channel**
   - Represents value that continues after the creating initiative completes.
   - Residual streams are activated at the configured lifecycle transition.
   - Once activated, the stream produces value each tick according to the residual decay law (exponential decay from the activation-tick rate), independent of team assignment or governance attention.

3. **Major-win event channel**
   - Represents a surfaced right-tail major opportunity at completion.
   - This is a first-class analytical event output, not by default a priced
     realized-value channel in the canonical study.
   - The study measures governance's ability to surface transformational outcomes — surfaced major-win count, time to discovery, labor per discovery — not the downstream economic value of exploiting them.

4. **Capability channel**
   - Represents persistent portfolio-level learning capability from completed enablers.
   - Higher portfolio capability `C_t` reduces effective strategic signal noise `σ_eff` for all staffed initiatives simultaneously by entering as a divisor, improving the precision of the governance observation process across the entire portfolio.

These channels must remain separable in reporting and analysis.

Channel separation is a structural requirement, not a convenience. Two governance regimes with similar aggregate cumulative value may differ sharply in channel composition — one dominated by completion-lump value, the other by residual accumulation — and that compositional difference is evidence about governance structure. Collapsing channels into a single aggregate would destroy the study's ability to distinguish governance regimes that achieve similar totals through fundamentally different mechanisms.

### Business
The simulation tracks organizational outcomes through four distinct channels, each representing a fundamentally different mechanism by which initiatives create long-term value. These channels must remain separable throughout the simulation and in all reporting — collapsing them into a single aggregate would obscure the structural differences between governance regimes that are the primary object of study.

**1. Completion-lump value.** The one-time economic payoff realized when an initiative completes. This channel represents the direct harvest from completed work — a product launch, a deal closed, a capability delivered. Value is realized exactly once, at the completion transition, and does not recur. This is a completion-gated channel, not a streaming channel — no value flows during active work.

**2. Residual value.** The ongoing returns produced by persistent mechanisms that completed initiatives leave behind. A distribution network, an automation system, a marketplace platform — once activated at completion, these mechanisms continue generating value every week after the team has moved on. This channel represents the compounding base of self-sustaining value that a governance regime builds over time.

**3. Major-win discovery events.** The surfacing of genuinely transformational outcomes when right-tail initiatives complete and reveal themselves to be major wins. This is a first-class analytical output — the study measures how many major wins different governance regimes discover, how long discovery takes, and how much investment each one requires. In the canonical study, major-win events are recorded as discovery events, not priced as realized economic value. The study measures governance's ability to find transformational outcomes, not the full downstream economics of exploiting them.

**4. Organizational capability.** The persistent portfolio-level improvement in the organization's ability to evaluate future work, contributed by completed enabler initiatives. Higher capability reduces the noise in strategic signals across the entire portfolio, making it easier for governance to distinguish promising initiatives from unpromising ones. This channel represents the long-term learning infrastructure that governance builds — or neglects — through its investment choices.

These four channels must remain analytically distinct because two governance regimes with similar total value can differ sharply in how that value was composed — one dominated by quick completion payoffs, the other by compounding residual streams — and that compositional difference is evidence about governance structure, not noise.

## Core state partitions


### Academic
For architectural purposes, world state should be thought of as partitioned into the following domains.

**Latent initiative attributes** include true quality `q`, dependency `d`, latent market ceiling, value-mechanism parameters, and any other hidden drivers resolved before the run starts. These are fixed at generation, hidden from governance throughout the run, and accessible only to the engine for ground-truth computations (signal generation, completion detection, value realization). They serve as the reference against which governance beliefs and decisions are evaluated in post-hoc analysis.

**Mutable initiative state** includes lifecycle state, staffing state, progress state, posterior belief `c_t`, observable history, stop-rule counters, and any persistent outputs attributable to the initiative. This encompasses all derived governance-rule state: `consecutive_reviews_below_tam_ratio`, `belief_history` (ring buffer for stagnation detection), `review_count`, `staffed_tick_count`, `ticks_since_assignment`, and cumulative labor, attention, and value accounting.

**Team state** includes team identity, assignment status, reassignment timing, and ramp effects. Teams are the atomic units of staffing allocation; their state determines which resources governance can deploy and what ramp penalties are in effect.

**Portfolio capability state** includes the current level of portfolio-wide capability or productivity modifiers accumulated from enabler work and other persistent improvements. `C_t` enters the effective signal standard deviation `σ_eff` as a divisor, reducing strategic observation noise for all staffed initiatives simultaneously. It is a shared resource: improvements benefit the entire portfolio, and decay erodes the accumulated advantage.

**Persistent mechanism state** includes active mechanisms that continue to generate value after originating work completes. These mechanisms operate independently of team assignments and governance attention, producing value each tick according to their configured decay law.

**Metrics state** includes time-series accumulators and event logs needed for reporting and experiment comparison. This is the evidentiary record from which all downstream analysis proceeds. It must not influence any state transition or governance decision.

### Business
For architectural purposes, the complete state of the simulated world should be understood as partitioned into six distinct domains, each serving a different role.

**Latent initiative attributes** are the hidden truths about each initiative that are fixed at creation and never change: the initiative's true strategic quality, its dependency level, its true completion time, its value mechanism parameters, and whether it is destined to be a major win. These exist in the simulation because they are needed to generate outcomes and noisy evidence, but they are structurally invisible to governance. They are the ground truth against which governance's beliefs and decisions are ultimately evaluated in post-hoc analysis.

**Mutable initiative state** is everything that evolves about an initiative during the run: its lifecycle position (unassigned, active, stopped, completed), which team is assigned to it, how far work has progressed, the organization's current belief about its strategic quality and execution progress, the full observable history, and all the derived counters that governance rules depend on — consecutive-review trackers, stagnation buffers, review counts. This is the organizational knowledge that accumulates about each initiative as evidence is gathered and governance decisions are made.

**Team state** tracks each team's identity, current assignment status, availability for reassignment, and ramp-up position. Teams are the atomic units of productive capacity, and their state determines what resources governance can deploy.

**Portfolio capability state** tracks the organization's accumulated portfolio-wide learning capability — the institutional improvement in evaluation precision that comes from completing enabler initiatives. This is a shared resource that benefits every active initiative simultaneously by reducing the noise in strategic signals.

**Persistent mechanism state** tracks the active residual value streams that completed initiatives have left behind. These mechanisms operate independently of team assignments and governance attention, producing value every week regardless of what else is happening in the portfolio.

**Metrics state** includes all the time-series accumulators, event logs, and running tallies needed for reporting and cross-regime comparison. This is the evidentiary record that the simulation builds as it runs — the raw material from which all downstream analysis proceeds.

## Runner responsibilities


### Academic
The runner has responsibilities that are intentionally outside the engine.

It resolves `initiative_generator` inputs deterministically into a fully materialized initiative list before the engine starts. It clones comparable worlds across policy regimes. It binds seeds, policy IDs, and configuration snapshots into the run manifest. It also enforces that experiment comparisons are valid by preventing silent differences in resolved initiative pools across regimes.

The same architectural rule applies to workforce construction. If a future
builder-layer `WorkforceArchitectureSpec` or broader governance-architecture
specification is used, the runner or builder layer must resolve it into a
concrete `WorkforceConfig` before the engine starts. Workforce generation is an
upstream concern, not an engine concern.

The engine should therefore be written as if it always receives a fully resolved run input. Generation-time randomness is a runner concern, not an engine concern.

To be explicit about the runner's role in ensuring valid comparisons: the runner guarantees that two regimes designated for comparison face the same resolved initiative pool — the same initiative attributes, the same latent quality draws, the same true duration values, and the same per-initiative RNG stream seeds. Any generation-time stochasticity — drawing from quality distributions, determining true durations, assigning `is_major_win` flags, constructing per-initiative RNG streams — is fully resolved by the runner before the engine receives the first tick. The engine consumes a fully resolved run input consisting of concrete initiatives with all attributes determined, concrete teams with all properties set, and concrete random streams ready to produce observations.

### Business
The runner is the orchestration layer with responsibilities that are intentionally separated from the engine. The engine's job is to advance the world one week at a time according to fixed rules. The runner's job is to ensure that the engine receives the right inputs, that those inputs are valid and fully resolved, and that the comparison between governance regimes is structurally sound.

The runner resolves initiative generator specifications deterministically into fully materialized initiative lists before the engine starts. It ensures that the same resolved initiative pool is used across governance regimes in comparative experiments. It binds world seeds, governance regime identifiers, and complete configuration snapshots into the run manifest — the provenance artifact that makes every finding traceable and reproducible. It also enforces that experimental comparisons are valid by preventing silent differences in resolved initiative pools across regimes — if two regimes are supposed to face the same world, the runner guarantees that they do.

The same principle applies to workforce construction. If a future organizational-architecture specification layer is used to generate team structures from higher-level parameters, the runner or builder layer must resolve it into a concrete workforce configuration before the engine starts. Team generation — how the total labor endowment is partitioned into discrete teams of specific sizes — is an upstream concern. The engine receives a realized team structure and operates with it.

The engine should therefore be written as if it always receives a fully resolved run input: concrete initiatives with all attributes determined, concrete teams with all properties set, and concrete random streams ready to use. Any generation-time randomness — drawing from quality distributions, determining true durations, assigning major-win flags — is a runner concern that is fully resolved before the engine sees the first week of the simulation.

## Scope boundaries


### Academic
Several mechanisms are intentionally outside canonical scope.

The architecture does not model politics, morale, executive personalities, hiring markets, layoffs, cultural contagion, or exogenous macro shocks as core behavior. It does not model autonomous strategic adaptation by teams or initiatives. It does not permit fractional team assignment in the canonical design. These omissions are deliberate. They keep the simulator interpretable as a study of governance structure rather than a sprawling organizational twin.

Specifically, the exclusions ensure that outcome differences across governance regimes can be cleanly attributed to the policy mapping from observations to actions. A model that incorporated behavioral dynamics — morale effects, political maneuvering, endogenous labor-market adjustments — alongside the governance mechanisms under study would produce confounded results. The findings would depend on interaction effects between governance and those uncontrolled dynamics, and the study would have no mechanism to separate governance effects from behavioral effects. By holding these factors constant or absent, the architecture isolates the phenomenon it is designed to measure.

Extensions may be introduced experimentally later, but they must not weaken the canonical invariants above. Two specific extensions have been identified as potentially load-bearing for the study's external validity: (1) an endogenous proposal quality mechanism, in which aggressive early-stopping governance gradually depresses the quality or ambition of future proposals (modeling the feedback loop from governance culture to intake pipeline); and (2) a dynamic workforce mechanism, in which the labor endowment or team decomposition can change mid-run in response to portfolio conditions. Both must be designed as explicit experimental variants with their own specifications and documented departures from the baseline model.

### Business
Several mechanisms are intentionally excluded from the simulation's canonical scope. These exclusions are deliberate design choices, not oversights or deferrals.

The simulation does not model organizational politics, employee morale, executive personalities, hiring markets, layoffs, cultural contagion, or exogenous macroeconomic shocks. It does not model teams or initiatives that autonomously adapt their behavior in response to governance pressure — teams do not "try harder" when governance pays more attention, and initiatives do not "game the system" by presenting misleadingly positive evidence. It does not permit fractional team assignment, where part of a team works on one initiative and part on another.

These omissions keep the simulator interpretable as a study of governance structure — specifically, how governance decisions about resource allocation, attention distribution, and stop/continue thresholds affect long-run value creation, discovery, and capability development. A simulation that attempted to capture office politics, morale dynamics, and labor market effects alongside governance mechanics would produce results that could not be cleanly attributed to governance. The findings would always be entangled with uncontrolled behavioral dynamics. By holding these factors constant (or absent), the study isolates the phenomenon it is designed to measure.

Extensions may be introduced experimentally in the future — for example, an endogenous proposal quality mechanism where aggressive early-stopping governance gradually discourages ambitious proposals, or a dynamic workforce model where leadership can adjust team structure mid-run. But any such extension must be designed as an explicit experimental variant, documented in its own specification, and must not weaken the canonical invariants that the core study depends on.

## Architectural consequences for other documents


### Academic
The other design files should be read as refinements of this architecture, not independent specifications.

`initiative_model.md` should define latent attributes, mutable initiative state, and the exact sufficient statistics maintained by the engine. This includes both hidden attributes (latent quality, true duration, is_major_win) and observable attributes (observable_ceiling, capability_contribution_scale, generation_tag), as well as the precise set of engine-maintained counters and history buffers required by governance decision rules.

`core_simulator.md` should define the tick loop, event ordering, and belief-update mechanics. This includes the signal generation formulas (`y_t`, `z_t`), the belief update equations for both strategic and execution channels, the effective signal standard deviation decomposition (`σ_eff`), the completion detection logic, the residual value realization rule, and the capability update sequence.

`governance.md` should define the observation schema, the action schema, and the policy decision rules without introducing hidden mutable policy state. Every piece of information governance requires must be traceable to a field in the `GovernanceObservation` contract; every decision governance can make must be expressible through the `GovernanceActions` vector.

`team_and_resources.md` should define assignment, reassignment, atomicity, and ramp semantics. This includes the indivisibility constraint, the surplus-staffing learning multiplier, and the ramp-up transition penalty and its interaction with dependency-adjusted learning efficiency.

`interfaces.md` should expose the configuration and manifest contracts needed to implement all of the above unambiguously. This includes the complete parameter specification for `SimulationConfiguration` (organized into `TimeConfig`, `WorkforceConfig`, `ModelConfig`, `GovernanceConfig`, and `ReportingConfig`), all validation rules, and the `RunManifest` schema sufficient for exact replay.

`review_and_reporting.md` should define outputs in a way that preserves the separation between direct value, persistent mechanism value, and capability effects. Channel-separated accounting must be maintained throughout the output surface.

### Business
The architecture described here defines the top-level contract. The other design documents should be read as refinements that implement specific aspects of this architecture, not as independent specifications that can be understood in isolation.

The **initiative model** document defines the concrete attributes each initiative carries (both hidden and observable), the mutable state the engine maintains for each initiative, and the exact counters and history buffers needed for governance rules.

The **core simulator** document defines the weekly cycle — the precise ordering of events within a tick, the belief update mechanics, the signal generation formulas, the completion detection logic, and the value realization rules.

The **governance** document defines what governance can see (the observation schema), what governance can do (the action schema), and the canonical decision rules that governance regimes apply — all without introducing hidden mutable governance state. Every piece of information governance needs must come through the observation boundary; every decision governance makes must be expressible through the action vector.

The **team and resources** document defines how teams are assigned and reassigned, why teams are indivisible, and how the ramp-up transition period works when a new team is assigned to an initiative.

The **interfaces** document exposes the configuration and manifest contracts — the complete parameter specifications and validation rules needed to implement all of the above unambiguously and to ensure that every run is fully reproducible.

The **review and reporting** document defines what outputs the simulation produces, in what form, and with what precision — preserving the separation between one-time completion value, persistent mechanism value, major-win discovery events, and organizational capability effects throughout.

## Canonical implementation sketch


### Academic
The following sketch is illustrative rather than normative, but it captures the intended ownership model.

```python
@dataclass
class WorldState:
    tick: int
    initiatives: list[InitiativeState]
    teams: list[TeamState]
    capability_state: CapabilityState
    persistent_mechanisms: list[PersistentMechanismState]
    metrics: MetricsState


@dataclass
class InitiativeState:
    latent: InitiativeLatentState
    quality_belief_t: float     # canonical c_t
    observed_history: list[ObservationRecord]
    consecutive_reviews_below_tam_ratio: int
    lifecycle_state: LifecycleState
    assignment_state: AssignmentState
    progress_state: ProgressState


class SimulationEngine:
    def run(self, resolved_input: ResolvedRunInput) -> RunResult:
        ...


class GovernancePolicy(Protocol):
    def decide(
        self,
        observation: GovernanceObservation,
        config: GovernanceConfig,
    ) -> GovernanceActions:
        ...
```

This sketch is included to remove any ambiguity about the intended ownership of state. Mutable simulation memory belongs to the engine-owned world state. Policy logic belongs to the policy. Run comparability belongs to the runner.

To elaborate on the ownership model: `WorldState` is the engine's complete representation of the simulated system at a given tick. It contains the current tick, the full list of initiatives with their evolving state (including latent attributes, belief scalars, observable histories, and all derived governance-rule counters), all teams with their assignments and availability, portfolio capability stock, active residual value streams, and the metrics buffers that accumulate the evidentiary record for reporting. `InitiativeState` contains the hidden ground truth (latent attributes), the organization's current strategic and execution beliefs, the full observable history, the consecutive-review counter, the stagnation belief-history buffer, the lifecycle position, the team assignment, and the progress tracking — everything needed to determine the initiative's next-tick evolution and to construct its projection into `InitiativeObservation`.

`SimulationEngine` takes a fully resolved `ResolvedRunInput` and produces a complete `RunResult`. It owns the tick loop, all state transitions, and all state maintenance. `GovernancePolicy` takes a `GovernanceObservation` and `GovernanceConfig` and produces a `GovernanceActions` vector. It owns no state. It maintains no memory. Its decisions are fully determined by its inputs.

This three-way separation — engine owns state, policy owns decisions, runner owns provenance and comparability — is enforced by construction and must not be entangled in implementation.

### Business
The following illustrates the intended ownership model — which entities exist, who owns what state, and how the boundaries are drawn between engine, governance, and domain objects. This is not a normative code specification, but it captures the structural commitments that any implementation must honor.

The **world state** is the engine's complete representation of the simulated organization at a given moment. It contains the current week, the full list of initiatives with their evolving state, all teams with their assignments and availability, the organization's accumulated capability, the active persistent value mechanisms, and the metrics buffers that accumulate the evidentiary record.

Within that world state, each **initiative's state** contains the hidden ground truth (its latent attributes), the organization's current belief about its strategic quality, the full observable history, the consecutive-review counter used by the patience rules, the lifecycle position, the team assignment, and the progress tracking — everything needed to determine what happens next and what governance can see.

The **simulation engine** takes a fully resolved run input and produces a complete run result. It owns the weekly cycle, all state transitions, and all state maintenance.

The **governance policy** takes an observation snapshot and a governance configuration and produces an action vector. It owns no state. It maintains no memory. Its decisions are fully determined by its inputs.

This ownership model removes any ambiguity about where state lives. Mutable simulation memory — every belief, every counter, every history buffer — belongs to the engine-owned world state. Decision logic belongs to the governance policy. Run comparability and provenance belong to the runner. These three responsibilities are separated by design and must not be entangled in implementation.
