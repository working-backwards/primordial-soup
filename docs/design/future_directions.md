# Primordial Soup: Future Directions

This document organizes potential next steps following the current evaluation
phase. The organizing principle is sequencing: some work strengthens the
current study before its conclusions are finalized; some work bridges
evaluation to optimization; some work is optimization proper; and some work
represents genuinely separate future studies that extend the model itself.
Mixing these categories creates sequencing errors — model extensions should
not be attempted before baseline evaluation is complete, and optimization
should not be attempted before the fragility landscape is understood.

---

## A. Evaluation-phase additions


### Academic
These are things that belong in the current study, not deferred work. They
take advantage of an unusual property of this simulator: ground truth is
observable. Real organizations can never know whether a stopped initiative
would have succeeded. This simulator can. That advantage should be fully
exploited in the current evaluation.

#### A.1 Empirical grounding of generator parameters

**This is an immediate task.**

Generator parameters — initiative quality distributions, signal noise levels,
duration structures, team sizes, ramp periods — were set by intuition during
early design. Before evaluation findings carry any credibility for external
audiences, there must be
a principled account of the parameter space.

This does not require fitting the model to data. It requires a calibration
argument: connecting each parameter range to a named real organizational
phenomenon and explaining why the chosen values are reasonable representations
of that phenomenon. For example:

- Why does the right-tail initiative quality distribution have its current
  shape? What real distribution of speculative bets does it represent?
- Why is the base signal standard deviation set where it is? What does that
  noise level correspond to in terms of a real organization's ability to
  evaluate strategic quality in a quarter?
- Why is the ramp period parameterized as it is? What empirical evidence
  about team onboarding costs supports that range?

The output of this task is a calibration note — a companion document that
justifies the baseline parameter choices and identifies which parameters the
results are most sensitive to. That sensitivity information also feeds
directly into Bucket B.

#### A.2 Ground-truth diagnostic metrics

The following metrics should be added to the current evaluation reporting.
They require no model changes — only reporting additions — and they are
the most important outputs the simulator can produce that a real organization
never could.

**False-stop rate on eventual major wins.** Among right-tail initiatives
whose latent quality would have surfaced a major win at completion, what
fraction were terminated before completion? Reported by governance regime
and environment family.

Formally, this is the conditional probability P(stopped | is_major_win = 1),
estimated per regime-environment pair. This is the primary diagnostic metric
in the evaluation: it directly quantifies the opportunity cost of governance
impatience as a rate of premature termination of the initiatives the study is
most concerned with preserving.

**Survival curve to revelation.** For right-tail initiatives, what fraction
remain alive by staffed tick *t*? Plotted separately for all right-tail
initiatives and for the latent subset that would have become major wins if
completed. This reveals whether the regime is killing future winners early
or late, and whether the kill pattern is concentrated around the typical
belief-maturation window.

Concentration of stop events at a specific phase distinguishes two failure
modes. If stops are concentrated at a particular point in the learning cycle,
the diagnosis is a structural governance design problem: the regime's threshold
parameters interact with the typical belief trajectory to produce systematic
premature termination at a predictable phase. If stops are dispersed across
the learning cycle, the diagnosis is more likely a calibration problem in
signal noise parameters, where the signal-to-noise ratio is insufficient for
beliefs to mature reliably regardless of timing.

**Belief-at-stop distribution.** When eventual major-win initiatives are
stopped, what was their strategic belief at the stop event? This separates
regimes that kill future winners at obviously weak belief states (a
calibration failure) from those that kill them in genuinely ambiguous states
(a harder structural problem).

Concretely: if the belief-at-stop distribution concentrates at low values
(c_t ≈ 0.2), the effective signal noise is severe enough that high-quality
right-tail initiatives routinely present as strategically weak — a generator
calibration problem addressable by adjusting σ_base or the attention curve
parameters. If the distribution concentrates at moderate values
(c_t ≈ 0.4–0.5), the regime is terminating in a zone of genuine ambiguity
where additional observation time might have resolved the belief toward the
correct classification. This second case is a governance design problem that
calibration alone cannot fix — it requires either more patient thresholds or
deeper attention to accelerate belief maturation.

**Attention-conditioned false negatives.** False-stop rate as a function of
executive attention depth. This directly tests the attention/termination
confounding identified in RQ7: stop decisions are made on beliefs that prior
attention allocation has already shaped.

The formal structure is a confound in the causal chain: attention a enters
σ_eff, which determines signal noise, which determines the belief trajectory
c_t, which determines the stop decision. Low prior attention produces noisier
beliefs, which produce higher false-stop rates — conditional on the same
latent quality q. The attention allocation and the termination decision are
not statistically independent. This metric quantifies the strength of the
a → σ_eff → c_t → stop coupling and tests whether stop decisions and
attention decisions can be evaluated independently or must be analyzed jointly.

**Hazard of stop by staffed tick and time-to-completion.** If stop events
cluster just before the typical belief-maturation window for right-tail
initiatives, that is direct evidence of the cliff mechanism described below.

Specifically, this pattern indicates that the regime invests enough labor to
generate substantial sunk cost but terminates before the belief-maturation
process resolves the initiative's latent quality — the worst-case timing for
a stop decision. The hazard function by staffed tick, stratified by latent
quality class, reveals whether the stop rule's threshold parameters place the
regime systematically in this region. If so, the regime's realized cost per
major-win discovery is maximized: cost is incurred but information is not
obtained.

These metrics are particularly important because the study already separates
major-win discovery rate as a distinct output dimension rather than pricing
it into a scalar. The diagnostic metrics give that separation empirical
content. They explain not just how many major wins each governance regime
discovers, but the specific mechanisms by which it fails to discover the ones
it misses — whether through calibration failure, governance threshold
placement, attention-induced confounding, or cliff-region termination timing.

<!-- specification-gap: formal statistical methodology for comparing diagnostic metrics across regimes is not specified — the OR reader would expect discussion of confidence interval construction for the false-stop rate (a ratio of potentially small counts), appropriate survival curve estimators (e.g., Kaplan-Meier with stratification), and test procedures for detecting significant differences across regime-environment pairs given the simulation's sample size structure -->

### Business
These are things that belong in the current study, not deferred work. They take advantage of a property that no real organization has: the ability to know, after the fact, whether a stopped initiative would have succeeded if it had been allowed to continue. In practice, when an executive kills a program, that decision is final — nobody ever learns whether that program would have been the next AWS or the next Fire Phone. The simulation knows. That advantage should be fully exploited before any conclusions are drawn.

#### A.1 Empirical grounding of the model's starting assumptions

**This is an immediate task.**

The model's starting assumptions — what kinds of initiatives exist, how uncertain they are, how long they take, how large the teams are, how long new teams need to ramp up — were initially set based on judgment rather than systematic evidence. Before any evaluation findings are presented to an external audience, there must be a principled account of why each assumption is reasonable.

This does not require fitting the model to match a specific company's data. It requires a calibration argument: connecting each assumption to a recognizable organizational reality and explaining why the chosen values are reasonable representations of that reality. For example:

- Why does the distribution of speculative initiative quality have its current shape? What real population of exploratory bets does it represent — early-stage corporate ventures? R&D pipeline projects? New market entries?
- Why is the level of uncertainty in strategic signals set where it is? What does that noise level correspond to in terms of how well a real leadership team can evaluate whether an initiative is strategically sound after one quarter of active work?
- Why is the ramp-up period for newly assigned teams set where it is? What empirical evidence about onboarding costs, team formation dynamics, and time-to-productivity supports that range?

The output of this task is a calibration note — a companion document that justifies the baseline assumptions and identifies which assumptions the results are most sensitive to. That sensitivity information feeds directly into the robustness work described in Section B.

#### A.2 Ground-truth diagnostic metrics

The following metrics should be added to the current evaluation reporting. They require no changes to the simulation itself — only additions to what is reported — and they are the most important outputs the simulation can produce precisely because no real organization could ever produce them.

**How often does each governance regime kill future breakthroughs?** Among exploratory initiatives whose underlying quality was high enough to produce a major win if completed, what fraction were terminated before they got there? This is the single most important diagnostic the simulation can produce. It directly measures the cost of impatience in terms that matter — transformational opportunities destroyed — and it is a number that no real executive will ever see for their own portfolio. Reported by governance regime and organizational environment.

**When do the kills happen?** For exploratory initiatives, what fraction are still alive after each period of active work? Plotted separately for all exploratory initiatives and for the subset that would have produced major wins if they had been allowed to finish. This reveals whether a governance regime is killing future winners early in their life — before the organization has invested enough to learn anything — or late, after extended investment that ultimately fails to reveal their quality. It also reveals whether kill decisions cluster around a specific point in the learning cycle, which would indicate a structural problem in the governance design rather than a calibration issue.

**What did leadership believe when it killed a future winner?** When an initiative that would have been a major win is stopped, what was the organization's current belief about its strategic quality at the moment of the stop decision? This separates two very different governance failures. If future winners are killed when the organization's belief is very low — say, 0.2 on a 0-to-1 scale — that may indicate a calibration problem: the signals are so noisy that genuinely good initiatives routinely look bad. If future winners are killed when the organization's belief is moderate — say, 0.45 — that is a harder problem: the governance regime is terminating initiatives in a zone of genuine ambiguity where more patience might have resolved the picture.

**Does executive attention predict which future winners get killed?** The rate at which future breakthroughs are incorrectly terminated, broken down by how much executive attention the initiative was receiving. This directly tests one of the study's most important hypotheses: that stop decisions are corrupted by the attention allocation that preceded them. If an executive paid too little attention to an initiative early in its life, the organization's beliefs about that initiative will be noisier and more likely to trigger a stop — even if the underlying initiative was actually worth pursuing. The attention allocation and the termination decision are not independent. This metric measures how strongly they are coupled.

**Do kill decisions cluster just before the picture would have cleared up?** If stop events are concentrated in the period just before an initiative's quality would typically have become clear — just before the learning process would have resolved the ambiguity — that is direct evidence of a cliff mechanism. It means governance is pulling the plug at precisely the wrong moment: after investing enough to generate substantial cost but before investing enough to learn whether the cost was justified.

These metrics are particularly important because the study already treats major-win discovery as a separate outcome dimension rather than folding it into a single value number. The diagnostic metrics give that separation concrete empirical content — they explain not just how many major wins each governance regime discovers, but the specific mechanisms by which it fails to discover the ones it misses.

---

## B. Post-evaluation, pre-optimization


### Academic
This bucket covers work that should be completed after the evaluation phase
produces stable findings but before any optimization is attempted. The purpose
is to understand the structure of the policy surface well enough that
optimization does not exploit artifacts or settle on brittle policies.

#### B.1 Robustness analysis and fragility mapping

Before optimizing over governance parameters, the policy surface needs to be
characterized — specifically, where it is stable and where it is fragile.

The key prediction is that stop-threshold response curves may not be smooth.
The model contains the exact ingredients that often produce nonlinear threshold
behavior in bandit-like systems: hidden latent quality, noisy learning, rare
right-tail successes, delayed revelation, completion-gated value realization,
stop rules acting on beliefs rather than truth, attention-dependent signal
quality, and switching costs. The combination of these factors means that a
small increase in stopping aggressiveness could push the system past the point
where right-tail initiatives survive long enough to reveal themselves — causing
major-win discovery to collapse suddenly rather than smoothly.

The practical consequence is that an optimizer unaware of this structure could
learn the wrong lesson: slightly tougher stopping may appear to increase
average short-horizon value while silently crossing into a region where
major-win discovery is near zero. A policy surface with this structure means
that a gradient-based or local search method could converge to a parameter
vector that appears to dominate on the primary value objective while sitting
on the wrong side of a discontinuity in the major-win constraint.

Fragility mapping should examine the following interactions:

**Stop threshold × attention breadth/depth.** The same stop rule may be
acceptable under deep, concentrated attention (which produces cleaner beliefs)
and catastrophic under broad, low-touch attention (which produces noisier
beliefs). This is the most important structural interaction in the design.

Stop-threshold and attention-allocation parameters must be evaluated jointly;
marginal sensitivity analysis over either parameter alone may produce
misleading conclusions. A policy that tightens the stop threshold without
simultaneously increasing attention depth may increase the false-stop rate on
high-quality initiatives — the noise increase from reduced attention outweighs
the disciplining effect of the tighter threshold. Formally: the partial
derivative ∂(false-stop rate)/∂(stop threshold) is itself a function of
attention depth, and the sign may reverse across the attention range.

**Stop threshold × environment family.** The cliff location should shift
depending on right-tail incidence, initiative duration structure, dependency
noise, and learning rate. Regimes that are safe in a clean fast-learning
environment may be fragile in a noisy slow-learning environment. Findings that
appear robust in one environment family may be artifacts of that family's
parameter configuration rather than genuine governance insights. The fragility
map should therefore be produced independently for each named environment
family, and findings should be reported as robust only when they hold across
all families.

**Stop threshold × cost-overrun tolerance.** Transformative initiatives may
be disproportionately likely to exceed planned execution estimates. An
execution-overrun filter can create a second cliff layered on top of the
strategic-quality threshold. The two interact: a regime can be double-exposed
to premature termination of its best opportunities.

The mechanism is specific: right-tail initiatives with long true durations will
accumulate execution belief erosion (c_exec drifts below 1.0 as the implied
duration exceeds the plan), and simultaneously their strategic belief c_t
matures slowly due to high σ_base. A regime that applies both a strategic
confidence threshold and an execution-overrun threshold creates two
independent stop paths, either of which can terminate the initiative. The
joint probability of surviving both paths may be substantially lower than
the probability of surviving either path alone, particularly for the
highest-quality right-tail initiatives whose duration and uncertainty are
both maximal.

The output of this step is a sensitivity map — regions of the governance
parameter space where outcomes are stable and regions where they are fragile.
This map is a precondition for responsible optimization.

Practically, the existing `scripts/ramp_period_study.py` and
`scripts/exec_belief_sensitivity.py` are examples of the infrastructure
needed. A more systematic sweep script covering stop threshold, attention
budget, and overrun tolerance jointly would implement this step.

<!-- specification-gap: methodology for the fragility mapping is not specified — the OR reader would expect a named sensitivity analysis approach (e.g., Morris elementary effects for screening, Sobol indices for variance decomposition, or systematic grid sweeps with discontinuity detection). The definition of "cliff" in the response surface — what constitutes a discontinuity vs. a steep but smooth gradient — also requires formal specification, as do sample size requirements for detecting such features given Monte Carlo noise -->

#### B.2 Multi-objective objective function design

Single-metric optimization is architecturally inconsistent with the study
design. The study already separates three outcome dimensions: cumulative
realized value from compounding mechanisms, major-win discovery rate, and
terminal portfolio capability from enabler investment.

Before running any optimizer, the objective function must be specified in a
way that preserves this structure. The natural formulation is constrained
optimization:

```
max_{x}  E_ξ[V(x, ξ)]

s.t.     E_ξ[M(x, ξ)]   >= m_floor
         E_ξ[C_T(x, ξ)]  >= c_floor
```

where x is the governance policy parameter vector, ξ is the stochastic world
(shared across regimes under CRN), V(x, ξ) is cumulative realized value
(completion-lump plus residual), M(x, ξ) is the count of surfaced major wins,
and C_T(x, ξ) is terminal portfolio capability. Expectations are taken over
replications under common random numbers.

- Maximize cumulative realized value
- Subject to major-win discovery rate staying above a floor
- Subject to terminal capability staying above a floor

The choice of floors is a research judgment, not a technical one, and should
be motivated by the calibration argument from A.1. A regime that achieves
high cumulative value by systematically suppressing major-win discovery is not
a good governance policy; it is a policy that has traded an unpriced future
for a measured present.

Any optimization framework that does not build in the major-win and capability
constraints will reward exactly the governance behavior the study is designed
to diagnose: short-horizon value maximization at the expense of
transformational discovery and organizational learning infrastructure.

<!-- specification-gap: the constrained optimization formulation above uses expected values, but the OR reader would want to know whether chance constraints, CVaR formulations, or worst-case (minimax) robustness across environment families are being considered — particularly given the cliff structures identified in B.1, where expected-value objectives may mask tail-risk failures in major-win discovery -->

### Business
This section covers work that should be completed after the evaluation phase produces stable findings but before any attempt to systematically improve governance policies. The purpose is to understand how the governance landscape is structured — specifically, where governance settings produce stable outcomes and where small changes in settings can produce dramatically different results — so that any subsequent improvement effort does not exploit artifacts of the model or settle on governance approaches that are brittle.

#### B.1 Understanding where governance settings are stable and where they are fragile

Before attempting to find better governance settings, the landscape of possible settings needs to be mapped — specifically, where outcomes respond smoothly to changes in governance parameters and where they respond abruptly.

The key concern is that the relationship between governance aggressiveness and outcomes may not be gradual. The study's structure contains all the ingredients that typically produce sudden threshold behavior in resource allocation under uncertainty: the true quality of an initiative is hidden, learning is noisy, transformational outcomes are rare, value is only realized upon completion, stop decisions are made on beliefs rather than ground truth, the quality of those beliefs depends on how much leadership attention was allocated, and reassigning a team to a new initiative carries switching costs. The combination of these factors means that a modest increase in stopping aggressiveness — tightening the threshold by what looks like an incremental amount — could push governance past the point where exploratory initiatives survive long enough for their quality to become clear. The result would not be a modest decline in major-win discovery. It would be a collapse.

The practical consequence is that a naive effort to improve governance by optimizing a single metric could learn exactly the wrong lesson: slightly tougher stopping may appear to increase average near-term value while silently crossing into a region where transformational discovery has been effectively eliminated. A leader looking at the near-term numbers would see improvement. The destruction of the organization's ability to find and develop its best long-term opportunities would be invisible until years later — if it were ever detected at all.

The fragility mapping should examine the following interactions:

**How stopping aggressiveness interacts with executive attention strategy.** The same stop rule may work well when leadership is deeply engaged with a small number of initiatives — because deep engagement produces clearer beliefs and fewer false stops — and may be catastrophic when leadership spreads its attention thinly across many initiatives — because thin attention produces noisy beliefs and a much higher false-stop rate. This is the most consequential interaction in the study's design. It means that a governance regime's stopping policy cannot be evaluated independently of its attention strategy. An organization that tightens its stop thresholds without simultaneously deepening its engagement with the initiatives it is evaluating may be destroying its best opportunities while believing it is imposing discipline.

**How stopping aggressiveness interacts with the organizational environment.** The point at which tighter stopping becomes destructive should shift depending on how common transformational opportunities are, how long initiatives take to resolve, how dependent initiatives are on factors outside the team's control, and how quickly the organization learns. A governance approach that is safe in a fast-learning environment with clean signals may be fragile in a slower-learning environment with noisier signals. Findings that appear robust in one environment may be artifacts of that environment's characteristics.

**How stopping aggressiveness interacts with cost-overrun tolerance.** Transformational initiatives may be disproportionately likely to exceed their original cost and timeline estimates — not because they are poorly managed, but because their scope is genuinely harder to estimate in advance. A governance regime that applies both a strategic-quality stop threshold and a cost-overrun stop threshold may be double-exposed to premature termination of its best long-term opportunities: the initiative looks ambiguous on strategic quality (because the signals are noisy) and looks like it is running over budget (because the original estimate was inherently unreliable). Either trigger alone might be tolerable. Together, they can be devastating.

The output of this work is a sensitivity map — a characterization of which regions of the governance parameter space produce stable outcomes and which regions are fragile. This map is a precondition for any responsible effort to improve governance settings, because it identifies the zones where small changes in governance could produce large, unintended consequences.

#### B.2 Defining what "better governance" means across multiple outcome dimensions

Optimizing governance against a single metric is fundamentally inconsistent with the study's design. The study already separates three outcome dimensions: cumulative realized value from compounding mechanisms, the rate at which transformational opportunities are discovered, and the level of organizational learning capability built over the study horizon.

Before any systematic improvement is attempted, the definition of "better" must be specified in a way that preserves this structure. The natural approach is to seek governance settings that maximize cumulative realized value subject to maintaining major-win discovery above a minimum acceptable rate and maintaining organizational capability development above a minimum acceptable level.

The choice of those minimum acceptable levels is a judgment call, not a technical calculation, and should be grounded in the calibration argument from Section A.1. The critical insight is this: a governance regime that achieves high cumulative value by systematically suppressing major-win discovery is not a good governance policy. It is a policy that has traded away an unpriced future for a measured present. Any optimization framework that does not build in this constraint will reward exactly the governance behavior the study is designed to diagnose.

---

## C. Optimization proper


### Academic
Optimization should be attempted only after the evaluation phase is complete,
the fragility landscape is understood (B.1), and the objective function is
specified (B.2).

#### C.1 Policy parameter search via simulation optimization (primary method)

The natural optimization approach is policy parameter search using Monte Carlo
simulation — the SimOpt framework this simulator was already designed for. The
governance policy is parameterized by a compact vector:

```
x = (stop_threshold, attention_depth, reassignment_rate, overrun_tolerance)
```

where stop_threshold governs the aggressiveness of confidence-based
termination, attention_depth controls the breadth-vs-depth allocation of
executive attention across active initiatives, reassignment_rate governs
willingness to redeploy teams from underperforming initiatives to new
opportunities, and overrun_tolerance sets the execution-belief floor below
which cost-overrun stops are triggered.

The optimizer searches over this parameter space using simulation as the
objective function evaluator. Appropriate algorithms include Bayesian
optimization, evolutionary search, and SPSA (Simultaneous Perturbation
Stochastic Approximation).

This approach is well-suited to the problem structure because:

- The state space is too large for exact dynamic programming
- The policy space is too large for brute-force grid search
- The governance policy is naturally low-dimensional and interpretable
- The MRG32k3a random number generator (RNG) choice (over PCG64) was made specifically to support
  SimOpt integration via common random numbers

The primary goal of optimization is not to find the single best parameter
vector, but to characterize the efficient frontier across the three outcome
dimensions — and to understand how that frontier shifts across environment
families. This reframes the study as a search problem rather than an
evaluation problem, which is the planned long-run direction.

Characterizing the efficient frontier transforms the study's output from
point comparisons between named archetypes ("regime A vs. regime B") to a
structural characterization of the governance tradeoff surface: what are the
fundamental tradeoffs in governance design, and how do organizational
conditions shape them? The frontier itself is the finding — it identifies
which outcome combinations are achievable, which require sacrifice on another
dimension, and how the feasible set changes across environment families.

<!-- specification-gap: parameter space bounds, constraints, and any known infeasible regions are not formally specified. The OR reader would also expect discussion of algorithm selection criteria (noise level in the objective, dimensionality, budget constraints on simulation replications) and convergence criteria for declaring a frontier point sufficiently characterized -->

#### C.2 Reinforcement learning (benchmark upper bound only)

RL can, in principle, learn governance policies directly from simulator
experience. However, RL is not recommended as a primary method for this
study, for a reason that is specific to the research goal.

The stated purpose of the study is to show that effective governance
is expressible as transferable policy — that what Bezos institutionalized
can be described in terms that other organizations can adopt. A neural
network that outperforms named archetypes provides no such description.
An opaque policy that works is less valuable here than a transparent policy
that works and can be explained.

RL is worth running as a benchmark: the performance ceiling it establishes
tells you how much room there is between the best parameterized policies and
the best achievable policy. That gap is itself a finding. But RL should not
be the research vehicle for producing interpretable governance recommendations.

The interpretation of the gap matters. If the gap between the best
interpretable policy vector and the RL ceiling is small, then low-dimensional
parameterized policies capture nearly all achievable value — the governance
problem is effectively low-rank in policy space, and the search in C.1 is
sufficient. If the gap is large, there exist governance strategies whose
decision logic has not yet been articulated in the parameterized policy
space — a signal to investigate what the RL agent is doing differently and
whether those behaviors can be formalized as additional interpretable policy
parameters. The gap diagnosis is therefore a research input, not an endpoint.

#### C.3 Academic positioning relative to Restless Multi-Armed Bandit (RMAB) and Partially Observable Markov Decision Process (POMDP) literature

The governance problem in this study has a formal structure that connects it
to two well-developed literatures. Recognizing these connections matters for
academic positioning, not as a practical guide to methods.

A **Markov Decision Process (MDP)** is a mathematical framework for sequential
decision-making under uncertainty, where outcomes depend partly on the
decision-maker's actions and partly on random transitions between states.
A **Partially Observable** MDP (POMDP) extends this by assuming the decision-maker
cannot directly observe the true state — only noisy signals about it — and so
must act on beliefs rather than facts. A **Restless Multi-Armed Bandit** is a
related problem where resources are allocated across multiple options (arms)
that evolve over time even when not selected, making the allocation problem
significantly harder than the classical bandit case.

The problem in this study is most precisely characterized as a
**partially observable restless bandit with coupled arms**. Each initiative
is an arm; staffing an initiative pulls the arm; arms evolve even when
unstaffed (restless); governance observes beliefs rather than true quality
(partial observability); and enabler completions improve a portfolio-level
capability scalar that reduces signal noise for all staffed arms (coupling).
The arm coupling is the most unusual structural feature relative to the
standard RMAB formulation, and it is the mechanism through which enabler
investments produce portfolio-wide effects.

This connection is relevant for two purposes. First, it situates the study
within a known hardness class (restless bandits are PSPACE-hard — meaning no known algorithm can solve them efficiently in the general case, placing them among the most computationally demanding class of problems in theoretical computer science),
which justifies the simulation optimization approach rather than exact methods.
Second, it creates a natural framing for the methodology paper: this study is
evaluating governance policies in a system whose structure is known to resist
exact analytical solutions, which is why simulation-based policy evaluation
is the appropriate method.

The PSPACE-hard classification has a direct implication for the study's goals:
the objective is not to find the mathematically optimal governance policy —
which provably cannot be computed for instances of this size — but to identify
governance principles that are robust, interpretable, and transferable across
environment families. The simulation-based approach in C.1 is the appropriate
method precisely because exact methods are intractable and the study values
interpretability over optimality.

Index policies — where each initiative is assigned a score and resources flow
to highest-scoring initiatives — are the bandit theory's natural heuristic
approach. They are worth acknowledging in the academic paper as a theoretical
bridge. However, the governance parameters in this study (stop thresholds,
attention bounds, overrun tolerance) do not map cleanly onto index functions,
so index policies are not a practical optimization path here.

The governance action space is multi-dimensional per tick (continue/stop,
attention allocation, team assignment), and the decisions interact — a stop
decision depends on beliefs shaped by prior attention, and attention
allocation depends on which initiatives remain active after prior stop
decisions. Collapsing this to a single index per initiative would require
discarding the interaction structure that is central to the study's research
questions.

### Business
Systematic improvement of governance settings should be attempted only after the evaluation phase is complete, the fragility landscape is understood (B.1), and the definition of "better governance" across multiple outcome dimensions is specified (B.2).

#### C.1 Systematic search for better governance settings (primary method)

The natural approach is to search over the space of governance settings using the simulation itself to evaluate each candidate. The governance policy is defined by a small number of interpretable settings:

- How aggressively the organization stops initiatives that have lost strategic conviction
- How deeply versus broadly leadership allocates its attention across active initiatives
- How readily the organization reassigns teams from underperforming initiatives to new opportunities
- How tolerant the organization is of cost and timeline overruns on initiatives with remaining strategic promise

The search explores combinations of these settings, running the simulation under each combination and evaluating outcomes across all three dimensions: cumulative value, major-win discovery rate, and organizational capability. This approach was anticipated from the beginning of the study's design — the choice of random number generator and the common-random-numbers architecture were made specifically to support this kind of systematic comparison.

The primary goal of this search is not to find a single optimal governance configuration. It is to characterize the efficient frontier — the set of governance configurations where improving one outcome dimension necessarily requires accepting worse performance on another — and to understand how that frontier shifts across different organizational environments. An organization operating in an environment rich with transformational opportunities faces a different set of tradeoffs than one operating in an environment where near-term, predictable returns dominate. The search is designed to map those differences.

This reframes the study from an evaluation exercise — "which governance regime is better?" — into a structural question: "what are the fundamental tradeoffs in governance design, and how do organizational conditions shape them?"

#### C.2 Machine learning as a performance ceiling (benchmark only)

In principle, machine learning techniques could learn governance policies directly from running the simulation thousands of times. A sufficiently powerful learning algorithm might discover governance strategies that outperform any of the named governance archetypes the study examines.

However, machine learning is not recommended as the primary method for this study, for a reason that goes to the heart of the research purpose.

The stated purpose of the study is to show that effective governance is expressible as transferable policy — that the governance practices that drive long-run value creation can be described in terms that other organizations can understand, adopt, and execute. A machine learning model that outperforms named governance archetypes provides no such description. It is an opaque decision-maker that cannot explain why it made the choices it made, and no leadership team can adopt a policy it cannot articulate.

The value of running a machine learning benchmark is different: it establishes a performance ceiling. The gap between the best interpretable governance policies and the best achievable performance — however opaque — is itself a finding. If the gap is small, it means that simple, describable governance rules capture nearly all the value available. If the gap is large, it means there are governance strategies whose logic the study has not yet articulated — and that is a signal to look harder for the interpretable principles underneath.

But the machine learning benchmark should not become the study's primary vehicle for producing governance recommendations. The study's audience is executives who need to understand what to do and why. An answer they cannot interpret is not useful, regardless of how well it performs in simulation.

#### C.3 Why this problem is hard, and what that implies for the approach

The governance problem in this study has a structure that makes it fundamentally resistant to exact analytical solutions. Understanding why it is hard clarifies why the simulation-based approach is not just convenient but necessary.

Consider what a governance team faces. They are managing a portfolio of initiatives, each of which has a true underlying quality they cannot observe. They learn about each initiative's quality through noisy signals that accumulate over time — but the quality of those signals depends on how much attention they allocate, which is itself a scarce resource. Meanwhile, every initiative in the portfolio is evolving whether or not anyone is working on it — market conditions shift, competitors move, technology changes. And some initiatives, when completed, improve the organization's ability to evaluate all future initiatives — creating dependencies across the portfolio that make each decision about one initiative affect the context for every other decision.

This combination of features — hidden quality, noisy learning, scarce attention, evolving conditions, and portfolio-level interdependence — places the problem in a class that mathematicians and computer scientists have proven cannot be solved exactly for any realistic portfolio size. There is no formula that a leadership team could apply to calculate the optimal governance policy. The problem is too complex, with too many interacting uncertainties, for exact methods.

This is why simulation-based evaluation is the appropriate method. The simulation can explore what happens under different governance approaches even though no formula can tell you the optimal approach in advance. It can reveal structural patterns — where governance is robust, where it is fragile, what tradeoffs are unavoidable — even though it cannot prove those patterns are optimal in any formal sense.

The practical implication for the study is important: the goal is not to find the mathematically optimal governance policy (which provably cannot be found for problems of this structure). The goal is to identify governance principles that are robust, interpretable, and transferable — and to understand how organizational conditions shape the tradeoffs between them.

One common approach in the academic literature on problems of this structure is to assign each initiative a score and allocate resources to the highest-scoring initiatives. This is worth noting for academic positioning, but it does not map well onto the governance decisions this study examines. Real governance involves stop thresholds, attention depth choices, and overrun tolerance — multi-dimensional decisions that cannot be collapsed into a single score per initiative without losing the structure that makes the governance question interesting.

---

## D. Model extensions (future studies)


### Academic
These are genuine extensions to the model — additions that would change what
the simulator represents. They should not be attempted before the baseline
study is complete. Each adds realism but also adds complexity that makes
results harder to attribute cleanly to governance rather than environment.
They are organized by the mechanism they add.

#### D.1 Endogenous opportunity generation

The current model treats the initiative pool as exogenous. In real
organizations, new opportunities are generated through prior investments,
technological breakthroughs, and accumulated expertise. A governance regime
that repeatedly kills uncertain work early may also, over time, reduce the
ambition of proposals that reach it — a cultural and pipeline effect that
the current model cannot capture.

The mechanism is specific: agents within the organization observe governance
outcomes and update their proposal strategies accordingly. If speculative
proposals are consistently terminated early, the expected payoff to proposing
speculative work decreases, and the distribution of incoming proposals shifts
toward lower-variance, lower-ceiling initiatives. The pool quality itself
becomes a function of governance history — an endogenous feedback loop between
the policy function and the distribution it operates over.

This omission means the current study likely understates the long-run cost
of aggressive stopping. Any finding that conservative, patient governance
performs only modestly better than aggressive governance should be treated as
a lower bound on the real organizational difference.

Future work could extend the model so that the rate and quality distribution
of incoming opportunities evolve as a function of past governance decisions.
Formally, this would replace the fixed exogenous pool with a generative
process whose parameters (right-tail incidence, quality distribution shape,
ceiling distribution) are functions of the regime's historical stop rate,
completion rate, and major-win surfacing rate — creating a feedback loop
between governance behavior and the opportunity environment that governance
faces.

#### D.2 Endogenous execution difficulty

The current model treats execution difficulty as fixed at initiative creation.
In practice, scope can genuinely change midstream — a software initiative
that discovers a hardware requirement, or an initiative whose market
requirements shift during execution. This is distinct from governance's
gradual inference about a fixed underlying difficulty.

The distinction is formally important: in the current model, the latent
execution fidelity q_exec = min(1.0, planned_duration / true_duration) is
fixed at generation. The execution belief c_exec_t tracks governance's
inference about this fixed quantity. Endogenous scope change would make
q_exec itself a stochastic process — the latent state evolves, not just the
belief about it. This is a fundamentally different modeling structure:
inference about a moving target rather than convergence toward a fixed one.

Future work could allow scope escalation as an endogenous process, with its
own signal and governance response. This would substantially enrich RQ8
(cost-projection sensitivity) by separating governance tolerance for
pre-existing difficulty from governance response to scope creep.
These require different governance responses — tolerance for a
difficult-but-stable initiative is a patience judgment, while response to
actively growing scope is a re-evaluation of whether the initiative's
fundamental premises still hold — but the current model cannot distinguish
them.

#### D.3 Dynamic attention budgets

The current model treats executive attention as a fixed resource. In practice,
leadership teams may temporarily expand or contract attention devoted to
specific initiatives depending on perceived urgency or strategic priority —
for example, a crisis in one initiative may draw attention that was previously
allocated elsewhere.

Future work could explore governance regimes in which attention budgets evolve
dynamically, including the interaction between dynamic attention and the
attention/termination confounding identified in RQ7.

A specific prediction follows from the model structure: if dynamic attention
policies tend to surge attention toward initiatives showing distress signals
(low c_t, execution overruns) and withdraw it from initiatives that appear
stable, the resulting attention pattern would systematically reduce σ_eff for
troubled initiatives while increasing it for stable ones. The downstream
effect on beliefs is that quietly progressing initiatives — receiving less
attention and therefore noisier signals — would have higher false-stop rates
than their latent quality warrants. This category includes many long-cycle
flywheel and right-tail initiatives, whose typical trajectory involves
extended periods of ambiguous signals before late-stage belief maturation.
Dynamic attention that is reactive to distress may therefore systematically
bias stop decisions against precisely the initiative types that the study
identifies as most valuable for long-run outcomes.

#### D.4 Organizational structure and decision layers

The current model treats the organization as a single decision-making unit.
Real organizations contain multiple governance layers, distributed decision
authority, and organizational silos that can delay or distort information flow.

Future work could examine how intermediate decision layers, delegation
structures, or silos influence the speed and quality of learning about
initiative performance. This extension would connect the simulation to the
organizational design literature in a way the current model cannot support.

Specific research questions this extension would enable: How much signal
quality is degraded when the decision-maker is separated from the initiative
team by multiple organizational layers — formally, how does σ_eff scale with
delegation depth? What happens when governance at different organizational
levels optimizes different objective functions — e.g., a division-level
governance layer that optimizes for division-specific value while a
portfolio-level layer optimizes across divisions? These principal-agent
structures could produce systematic distortions in information flow that
compound with the attention-dependent signal quality already in the model.
This extension would be particularly relevant for modeling governance in
large, complex organizations where the single-decision-maker assumption is
least tenable.

#### D.5 Execution quality, policy discipline, and replicability

**Research framing (relevant to the current study)**

The study's findings should stand independently of any particular company or
leader. The right sequencing is: first establish empirically which governance
policies generate long-run organizational value; then observe that a reader
will recognize these policies as learnable and executable. Only after that
foundation is laid should the study address the natural objection — "you had
Jeff Bezos / Bill Gates / Jensen Huang, and we don't."

The response to that objection is not to deny that exceptional leaders exist.
It is to separate what was genuinely non-replicable from what only appeared
to be. The non-replicable part is raw cognitive quality: the ability to hear a
comment and extract its essence, to see the right question when others don't,
to have insights in the room that no policy can manufacture. What looks like
non-replicable genius is, in many cases, the disciplined and uncompromising
application of principles that are themselves straightforward. The Amazon
Leadership Principle "Think Big," for example, produced a recognizable
behavioral pattern: when presented with an accomplishment or idea, the
question was always some form of "that's great — is there a way to make it
ten times bigger?" The insight behind that question is not mysterious.
What is hard is asking it every single time, without exception, under the
pressure of running a large organization.

The consistency, not the insight, is what separates exceptional outcomes from
ordinary ones. This is a testable claim within the simulation framework: if
the identified governance policies produce strong outcomes under perfect
execution fidelity (the model's current assumption), and if those same
policies degrade sharply under imperfect fidelity (the extension below), then
consistency of application is load-bearing and the study's practical
implications hinge on whether organizations can sustain it.

This framing also preserves the scope of the study's claims. Amazon is one
path to long-run value creation, not the only path. Gates, Jobs, and NVIDIA
represent different governance regimes that also generated exceptional
long-run value. They are not counterexamples to the study's findings; they
are parallel instances that the study's framework should be capable of
illuminating on their own terms.

**Model limitation**

The simulation models each governance regime as executing its policy
perfectly and consistently. It captures the policy ceiling — what a regime
achieves under idealized application — but not the organizational reality of
applying any policy imperfectly, inconsistently, or under pressure. The gap
between simulated outcomes and real-world outcomes is partly a function of
execution variance: the degree to which a real leadership team actually does
what its stated governance policy says it will do, meeting after meeting,
year after year.

This is arguably the most important gap between the model and reality. The
policies identified as value-generating by the study are not complicated.
What is hard is the discipline to never compromise on them.

The practical significance of this gap is amplified by the specific pressures
that would drive real governance teams away from their stated policies:
short-term performance shortfalls that incentivize tightening stop thresholds
to free resources for faster wins, competitive moves that incentivize
redirecting attention from long-cycle work to reactive responses, and
organizational politics that incentivize visible activity over patient
observation. Each of these pressures pushes in a specific direction — toward
shorter time horizons and less patience — rather than introducing random noise
around the stated policy.

**Model extension**

Future work could introduce execution quality as an explicit parameter —
a per-regime fidelity variable representing how consistently the regime
applies its own policy under realistic organizational pressure. Running the
same governance regime at varying fidelity levels would produce a family of
outcomes ranging from the idealized ceiling to a degraded floor, and would
allow the study to characterize how sensitive each regime's performance is
to execution discipline. Some regimes may be robust to occasional lapses;
others may depend critically on consistent application.

The sensitivity of a regime to execution fidelity is itself a finding of
practical importance: a governance approach that collapses when a stop
threshold is occasionally violated or an attention allocation is occasionally
skipped may be less transferable in practice than one that degrades
gracefully, even if the fragile regime achieves higher performance under
perfect execution. If the study can identify which governance approaches
are robust to imperfect execution, that may be as important a finding as
which approaches are optimal under perfect execution — because no real
organization executes perfectly.

**Outstanding questions**

- Is execution fidelity best modeled as a per-decision noise term (each
  governance decision deviates from policy with some probability), or as a
  systematic bias (the regime consistently drifts in a particular direction
  under pressure, e.g., toward shorter time horizons when quarterly results
  are poor)? Real organizations under pressure do not deviate randomly — they
  drift toward shorter time horizons, toward more visible near-term metrics,
  toward the choices that are easiest to defend externally. The direction of
  the drift may matter more than its frequency. A mean-zero noise model and
  a biased-drift model would produce different predictions about which regimes
  are robust to imperfect execution.
- Are some governance policies more forgiving of execution lapses than
  others? A regime that is fragile to occasional stop-threshold violations
  may be less transferable in practice than one that degrades gracefully.
- How should the study characterize the boundary between what is
  non-replicable (genuine insight quality) and what is replicable but
  difficult (disciplined adherence)? The non-replicable component — the
  ability to generate novel strategic insight in real time — cannot be
  parameterized or taught. The replicable-but-difficult component —
  disciplined adherence to sound governance principles, consistency under
  pressure, willingness to accept short-term cost for long-term value — can
  in principle be taught, systematized, and sustained by institutional
  practice even after the founding leader departs. This boundary matters for
  the practitioner-facing paper more than the academic methodology paper,
  but the simulation can contribute by characterizing how much of the
  performance difference between regimes is attributable to policy choice
  (replicable) versus execution quality (partially replicable) versus insight
  quality (non-replicable).

<!-- specification-gap: the fidelity parameter is described conceptually but not formally specified — the OR reader would want a concrete perturbation model (e.g., each governance decision is replaced by a random draw from an alternative policy with probability 1-φ, or each threshold is perturbed by additive noise with specified distribution, or the policy parameter vector drifts toward a specified "pressure attractor" at a specified rate). The choice of perturbation model would significantly affect which regimes appear robust -->

#### D.6 Strategic commitment and protected initiatives

Some organizations deliberately shield certain initiatives from normal
termination rules to allow long-term compounding mechanisms to mature. This
is one specific interpretation of the Bezos attention asymmetry that motivates
the study: minimal oversight to proven flywheel initiatives is a form of
protection from the normal governance cycle.

The distinction from patient threshold-based governance is formal: a protected
initiative is removed from the governance action space entirely — the
continue/stop decision is not made, not merely made with a lenient threshold.
This is a structural governance architecture choice (Tier 2 in the study's
three-tier framework) rather than an operating policy parameter (Tier 3).

Future work could model protected initiative status explicitly — as a
designated governance exception rather than an emergent outcome of a patient
stop threshold — and examine the conditions under which formal protection
produces better or worse outcomes than patient threshold-based governance.

Specific research questions this extension would enable:

- Under what conditions does formal protection (removal from the stop/continue
  action space) dominate patient thresholds (low stop_threshold applied within
  the action space)? The two are not equivalent: a patient threshold still
  exposes the initiative to noisy belief trajectories that may occasionally
  cross the threshold, while protection eliminates that exposure entirely.
- What criteria should trigger the transition from normal governance to
  protected status? Candidate triggers include: sustained high belief with
  low variance, activation of a residual value stream, strategic designation
  at creation.
- How does the presence of protected initiatives affect governance quality
  for the unprotected portfolio? Protection frees the attention and review
  bandwidth that would otherwise be spent on protected initiatives. This
  could improve the quality of stop/continue decisions on unprotected
  initiatives (more attention available per initiative) or could create an
  accountability gap (reduced scrutiny of a growing fraction of the
  portfolio).
- When should protection be revoked? A protected initiative whose
  environment has changed may no longer warrant exemption from governance
  review. The revocation decision is itself a governance design question.

### Business
These are genuine extensions to the model — additions that would change what the simulation represents. They should not be attempted before the baseline study is complete. Each adds realism to the model, but also adds complexity that makes it harder to cleanly attribute outcome differences to governance decisions rather than environmental factors. They are organized by the organizational mechanism they would add.

#### D.1 Allowing past governance decisions to shape future opportunity quality

The current model treats the pool of available initiatives as given — the organization receives a fixed set of opportunities at the outset. In real organizations, new opportunities are generated through prior investments, technological breakthroughs, partnerships, and accumulated expertise. More importantly, governance culture shapes the pipeline. A leadership team that repeatedly kills uncertain work early sends a signal throughout the organization: do not bring us ambitious proposals. Over time, the proposals that reach governance become more conservative, more predictable, and less likely to contain anything transformational — not because the opportunities do not exist in the world, but because the people who would champion them have learned not to bother.

This omission means the current study likely understates the long-run cost of aggressive stopping. If the simulation shows that a patient governance regime produces only modestly better outcomes than an aggressive one, that finding should be treated as a lower bound on the real organizational difference. In practice, the aggressive regime would also be degrading the quality of its own future pipeline in ways the current model cannot capture.

Future work could extend the model so that the rate and quality of new opportunities evolve as a function of past governance decisions — creating a feedback loop between governance behavior and the opportunity environment that governance faces.

#### D.2 Allowing initiative scope to change during execution

The current model treats each initiative's execution difficulty as fixed at the moment the initiative is created. Governance gradually learns about that fixed difficulty through observation, but the difficulty itself does not change. In real organizations, scope can genuinely shift midstream. A software initiative discovers a hardware dependency. A market entry encounters regulatory requirements that were not anticipated. A product development effort's target customer segment evolves during execution, changing what needs to be built.

This is fundamentally different from governance's gradual inference about a fixed underlying difficulty. It is a change in the underlying reality, not a change in governance's understanding of a fixed reality.

Future work could allow scope escalation as a process that unfolds during execution, with its own observable signals and governance responses. This would substantially enrich the study's analysis of cost-overrun governance by separating two very different situations: a governance team that tolerates a difficult-but-stable initiative versus a governance team that responds to scope that is actively growing. These require different governance responses, but the current model cannot distinguish them.

#### D.3 Allowing executive attention budgets to change over time

The current model treats executive attention as a fixed weekly budget. In practice, leadership teams can and do temporarily expand or contract the attention devoted to specific initiatives depending on perceived urgency or strategic priority. A crisis in one initiative — a key customer escalation, a competitive threat, a regulatory investigation — may draw attention that was previously allocated elsewhere. A positive surprise may cause leadership to pour attention into an initiative that was previously running on autopilot.

Future work could explore governance regimes in which attention budgets evolve dynamically, and could examine how dynamic attention interacts with the attention/termination coupling identified in the study's core research questions. If leadership tends to surge attention to initiatives in crisis and withdraw it from initiatives that appear stable, the attention pattern may systematically bias stop decisions against initiatives that are progressing quietly — precisely the category that includes many long-cycle compounding and exploratory initiatives.

#### D.4 Modeling organizational layers and delegation

The current model treats the organization as a single decision-making unit — a single governance function that sees everything and decides everything. Real organizations contain multiple governance layers: a CEO, a set of senior vice presidents, directors, and program managers, each with different information, different authority, and different incentives. Information is filtered, delayed, and sometimes distorted as it passes between layers. Decision authority is distributed, and the decisions made at one layer may conflict with or undermine the decisions made at another.

Future work could examine how intermediate decision layers, delegation structures, and organizational silos influence the speed and quality of learning about initiative performance. How much signal quality is lost when the person making the stop decision is three layers removed from the team doing the work? What happens when one division's governance incentives conflict with the portfolio-level view? This extension would connect the simulation to the organizational design literature in a way the current model cannot support, and would be particularly relevant for large, complex organizations where governance is necessarily distributed.

#### D.5 Execution discipline, policy consistency, and what is genuinely non-replicable

**Framing for the current study**

The study's findings should stand independently of any particular company or leader. The right sequencing is: first establish which governance policies generate long-run organizational value; then observe that a reader will recognize these policies as learnable and executable by any sufficiently disciplined leadership team. Only after that foundation is laid should the study address the natural objection — "you had Jeff Bezos / Bill Gates / Jensen Huang, and we don't."

The response to that objection is not to deny that exceptional leaders exist. It is to separate what was genuinely non-replicable from what only appeared to be. The non-replicable part is raw cognitive quality: the ability to hear a comment and extract its essence, to see the right question when others see none, to generate insights in the room that no process can manufacture. These are real, and they matter.

But what looks like non-replicable genius is, in many cases, the disciplined and uncompromising application of principles that are themselves straightforward. The Amazon Leadership Principle "Think Big," for example, produced a recognizable behavioral pattern: when presented with an accomplishment or idea, the question was always some form of "that's great — is there a way to make it ten times bigger?" The insight behind that question is not mysterious. What is hard is asking it every single time, without exception, through thousands of meetings, under the pressure of running a large organization with quarterly earnings, board scrutiny, and the relentless operational demands of a business at scale. The consistency, not the insight, is what separates exceptional outcomes from ordinary ones.

This framing also preserves the scope of the study's claims. Amazon is one path to long-run value creation, not the only path. Gates, Jobs, and NVIDIA represent different governance regimes that also generated exceptional long-run value. They are not counterexamples to the study's findings; they are parallel instances that the study's framework should be capable of illuminating on their own terms.

**What the current model cannot capture**

The simulation models each governance regime as executing its policy perfectly and consistently. Every stop decision follows the rule. Every attention allocation matches the strategy. Every team assignment is made exactly as the policy specifies. This captures the policy ceiling — what a governance approach achieves under idealized execution — but not the organizational reality of applying any policy imperfectly, inconsistently, or under pressure.

The gap between simulated outcomes and real-world outcomes is partly a function of execution variance: the degree to which a real leadership team actually does what its stated governance policy says it will do, meeting after meeting, quarter after quarter, year after year. When quarterly results disappoint and the board presses for near-term improvements, does the leadership team maintain its patience with long-cycle exploratory initiatives, or does it tighten stop thresholds to free up teams for faster wins? When a major competitor makes a surprise move, does the leadership team hold its attention strategy steady, or does it surge attention to competitive response at the expense of everything else?

This is arguably the most important gap between the model and reality. The governance policies identified as value-generating by the study are not complicated. They are describable in plain language. What is hard is the discipline to never compromise on them — especially when the pressure to compromise is coming from rational, well-informed people responding to real short-term pressures.

**Future model extension**

Future work could introduce execution discipline as an explicit variable — a per-regime parameter representing how consistently the regime applies its own stated policy under realistic organizational pressure. Running the same governance regime at varying discipline levels would produce a family of outcomes ranging from the idealized ceiling down to a degraded floor, and would reveal how sensitive each regime's performance is to inconsistent application. Some governance approaches may be robust to occasional lapses — a missed attention allocation or a stop decision that deviates from threshold. Others may depend critically on consistent application, such that even occasional departures from the stated policy substantially degrade outcomes.

**Outstanding questions**

- Is inconsistent governance execution better modeled as random noise — each decision has some probability of deviating from stated policy — or as systematic drift? Real organizations under pressure do not deviate randomly. They drift in a specific direction: toward shorter time horizons, toward more visible near-term metrics, toward the choices that are easiest to defend in the next board meeting. The direction of the drift may matter more than its frequency.
- Are some governance policies more forgiving of inconsistent execution than others? A governance approach that collapses when a stop threshold is occasionally violated may be less transferable in practice than one that degrades gracefully. If the study can identify which governance approaches are robust to imperfect execution, that is arguably as important a finding as identifying which approaches are optimal under perfect execution — because no real organization executes perfectly.
- How should the study characterize the boundary between what is genuinely non-replicable and what is replicable but difficult? The non-replicable part — raw cognitive quality, the ability to see what others cannot — cannot be taught or systematized. The replicable-but-difficult part — disciplined adherence to sound governance principles, consistency under pressure, willingness to accept short-term cost for long-term value — can be taught, can be systematized, and can be sustained by organizational culture and institutional practice even after the founding leader departs. This boundary matters more for the practitioner-facing implications of the study than for the academic methodology.

#### D.6 Protected initiatives and strategic commitment

Some organizations deliberately shield certain initiatives from normal governance review and termination rules. This is not neglect or inattention — it is an explicit governance choice to protect long-cycle work from the short-cycle pressures that normal governance imposes. The initiative is placed outside the regular portfolio review cadence, given a committed budget and timeline, and evaluated on its own terms rather than competing for resources against faster-payoff alternatives each quarter.

This is one specific interpretation of the governance asymmetry that motivates the study. When a leadership team provides minimal oversight to a proven compounding mechanism — a logistics network, a cloud platform, a marketplace — it is not simply being patient with a stop threshold. It is making a structural governance decision to protect that investment from the ordinary governance cycle entirely. The initiative is no longer subject to the same continue/stop evaluation as everything else in the portfolio.

Future work could model protected initiative status explicitly — as a designated governance exception rather than an emergent outcome of a patient stop threshold — and examine the conditions under which formal protection produces better or worse outcomes than simply having a patient governance regime. The questions this raises are practical and consequential: When should an organization formally protect an initiative from normal governance? What criteria should trigger protection? How does the presence of protected initiatives affect governance quality for the rest of the portfolio — does it free up attention for better decisions on unprotected initiatives, or does it create an accountability gap? And when should protection be revoked?

---

## Sequencing summary


### Academic
| Bucket | When | Gate condition |
|--------|------|----------------|
| A. Evaluation-phase additions | Now, before conclusions are finalized | None — these belong in the current study |
| B. Post-evaluation, pre-optimization | After evaluation findings are stable | Evaluation complete |
| C. Optimization proper | After fragility landscape is understood | B.1 and B.2 complete |
| D. Model extensions | After baseline study is published | Separate research effort |

The most important near-term action is A.1 (empirical grounding), because it
is a precondition for external credibility of the evaluation findings
themselves — not just the optimization work that follows.

Without a principled account of why the generator parameters are reasonable —
connected to named organizational phenomena rather than set by researcher
intuition — the evaluation findings are vulnerable to the objection that
observed differences between governance regimes are artifacts of the parameter
assumptions rather than genuine structural properties of the governance
problem. This is not a theoretical concern: a reviewer who doubts the
signal noise calibration, the right-tail quality distribution, or the
duration structure can dismiss any downstream finding as conditional on
unjustified assumptions. The calibration note is the study's defense against
this objection, and it must be completed before evaluation findings are
presented to any external audience.

### Business
| Phase | When | What must be true first |
|-------|------|------------------------|
| A. Evaluation-phase additions | Now, before conclusions are finalized | Nothing — these belong in the current study |
| B. Post-evaluation, pre-optimization | After evaluation findings are stable | Evaluation complete |
| C. Systematic governance improvement | After the fragility landscape is understood | B.1 and B.2 complete |
| D. Model extensions | After baseline study is published | Separate research effort |

The most important near-term action is A.1 (empirical grounding of the model's starting assumptions), because it is a precondition for external credibility of the evaluation findings themselves. Without a principled account of why the model's parameters are reasonable — grounded in recognizable organizational realities rather than arbitrary choices — the findings are vulnerable to the objection that the results are artifacts of the assumptions rather than genuine insights about governance. This grounding is not just a prerequisite for the later optimization work. It is a prerequisite for the current evaluation to be taken seriously by a practitioner audience.
