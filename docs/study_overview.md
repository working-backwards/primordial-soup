# Governance of Long-Term Value Creation

## Role of this document

This document is authoritative about the **phenomena in scope** for the canonical Primordial Soup study, the practitioner-facing interpretation of those phenomena, and the deliberate simplifying assumptions used to make the study tractable.

It is not the source of truth for simulator implementation details such as:

- exact state-field definitions,
- tick ordering,
- update equations,
- governance action schemas, or
- interface contracts.

Those operational semantics are defined in `initiative_model.md`, `core_simulator.md`, `governance.md`, and `interfaces.md`. Downstream documents must remain consistent with both this conceptual layer and that technical layer.

The corpus also includes several companion documents that preserve rationale and
support implementation without changing the authority structure above.
`design_decisions.md` records the major tradeoffs and reasons behind the
canonical design choices. `analysis_and_experimentation.md` describes how the
study's outputs are intended to support deterministic analysis, AI-assisted
exploration, and follow-on experiment design without changing the simulator
itself. `implementation_guidelines.md` and `engineering_standards.md` describe
how to implement the study in a way that preserves model integrity, supports
reproducibility, and keeps future optimization-oriented integration feasible.

Some organizations repeatedly produce transformative new businesses while others struggle to create even modest growth beyond their existing operations. The difference is rarely explained by intelligence, effort, or even the occasional brilliant leader. Many organizations employ talented people who work extremely hard and still fail to generate meaningful long-term growth. Yet a small number of organizations consistently discover new opportunities, build compounding mechanisms, and create value far beyond what their initial businesses would suggest.

One plausible explanation is governance. Organizations differ dramatically in how they govern uncertain initiatives: how willing they are to pursue risky opportunities, how long they persist before stopping work, how actively senior leaders engage with nascent ideas, and how resources are reallocated as evidence accumulates. Some governance regimes encourage experimentation, tolerate the cost of blind alleys, and actively cultivate large but uncertain opportunities. Others emphasize predictability, incremental improvement, and rapid termination of uncertain efforts. These differences may shape not only which initiatives survive but also the kinds of opportunities organizations are willing to pursue in the first place.

This study examines how governance regimes influence long-term value creation by simulating portfolios of initiatives evolving under different governance policies. The model represents several distinct mechanisms through which organizations create value. Some surface rare but potentially transformative major wins. Others build mechanisms — flywheels, platforms, distribution networks — that continue producing value after active work ends. Still others improve organizational learning capability by reducing effective strategic signal noise for future work. Governance determines how resources are allocated across these competing mechanisms and when work is continued, stopped, or redirected.

## High-level system behavior

At a high level, the simulator works like a **controlled, step-by-step system**: given the organization's current situation and the decisions leadership makes, it determines what happens next. The important point is that everything that affects the future is captured in the current state of the system.

There are two kinds of "state" involved. The first is the **business state**—things like which initiatives are active, what leadership currently believes about them, how teams are assigned, and how much capability the organization has built up. This is the part that represents how the organization is actually evolving over time.

The second is the **controlled randomness inside the simulation**—the mechanism that generates uncertain outcomes and signals. This randomness is not part of the organization itself; it is how the simulator introduces uncertainty in a repeatable way.

When you combine these two pieces, the system behaves in a very disciplined way: **if you fix the starting business state, the controlled randomness, and the decisions, the outcome is always the same**. This makes it possible to run fair comparisons between different governance approaches and understand cause and effect.

From a leadership perspective, the key takeaway is this:

> The simulator makes decisions based only on what is currently known, not on hidden future information. Leadership sees imperfect signals and must decide whether to continue, stop, or redirect work under uncertainty.

This mirrors the real-world challenge. Leaders never know in advance which initiatives will succeed—they must learn over time and allocate resources accordingly. The simulator is designed to capture that dynamic faithfully, while ensuring that all the factors that matter for the future are explicitly tracked.

The most important thing to get right is not where randomness lives in the system, but whether the model is keeping track of **everything that actually drives outcomes over time**. If something that influences the future is missing, the results can become misleading. If everything that matters is captured, the system remains reliable, interpretable, and useful for understanding how governance decisions shape long-term outcomes.

## Simulation approach

The study is implemented as a stochastic discrete-time simulation evaluated through Monte Carlo experimentation. Each governance regime defines a policy x that maps observable initiative state to governance decisions such as staffing, continuation, reassignment of teams, or stopping work.

A single simulation run produces an outcome f(x, ξ) where x represents the governance policy, ξ represents the random elements of the simulated world (including initiative quality, execution signals, and discovery events), and f represents the resulting portfolio performance.

Because outcomes depend on stochastic realizations, the performance of a governance regime cannot be determined from a single run. The simulator is therefore executed repeatedly with different random draws, and results are aggregated across runs to estimate the expected performance and distribution of outcomes for each governance regime.

The simulator is intentionally neutral about who analyzes those outputs next. The
study is designed so that its outputs can be consumed by a human analyst, an AI
analyst, or a hybrid human-AI workflow without changing simulator behavior or
privileging one interpretation path. This is a deliberate feature of the study
design rather than an implementation afterthought: the same evidentiary base
should support multiple analyst modalities while preserving reproducibility,
auditability, and provenance.

## Experimental structure

Each experiment begins with a fixed pool of initiatives and a fixed world configuration. The same initiative pool and random seeds are used across governance regimes so that differences in outcomes reflect governance decisions rather than differences in opportunities or environmental conditions.

Although regimes begin from a common initial world, the study does not force them to face the same evolving future. Governance choices change which initiatives are completed, which are abandoned, how capability accumulates, how residual value compounds, and therefore what options remain available later in the run. This divergence is not merely a nuisance of simulation; it is one of the central mechanisms the study is designed to observe. The purpose of the study is not to declare a universally superior governance posture in advance, but to identify the conditions under which different postures produce different strengths, weaknesses, and tradeoffs.

Results should therefore be interpreted conditionally: under some environmental and organizational conditions one regime may outperform another on one dimension while underperforming on another, and those relationships may reverse under different conditions.

Initiatives themselves are immutable. What evolves over time are beliefs about each initiative's strategic potential and execution difficulty as new signals are observed. During each review period the governance policy observes these beliefs and decides whether work on each initiative should continue or stop, and how teams should be reassigned.

Initiatives do not generate value while work is still in process. In the canonical study, economically meaningful effects are completion-gated. Depending on the initiative's resolved attributes, completion may realize a one-time lump of value, activate a residual value stream that continues after active work ends, emit a major-win discovery event, or increase portfolio-level capability. These effects accumulate over time to produce portfolio-level measures of long-term value creation.

The canonical study does not rely on a single intuitively chosen opportunity environment. Instead, it evaluates governance regimes across a small set of named environment families representing different plausible organizational worlds. These families differ in initiative mix, right-tail incidence, and duration structure, and are grounded by independent empirical calibration where available — including triangulation from incumbent new-business-building research, internal venture and exploratory-innovation evidence, and industry analogues with measurable long-shot hit rates. Families are defined and frozen before the comparative campaign begins so that governance findings can be interpreted as holding within, across, or conditional on those environments rather than as artifacts of one hand-tuned generator configuration.

The purpose of the study is not to prescribe a single optimal governance policy
but to reveal the structural dynamics through which governance choices shape
discovery, compounding mechanisms, capability development, and long-term value —
so that leaders can recognize those dynamics in their own organizations and make
better-informed decisions about how to allocate the two things they can never
get back: their people's time and their own.

This study also makes a methodological claim about how such evidence should be
produced. The simulator does not assume a privileged downstream analyst. Its
output contract is designed to make rigorous interpretation possible for humans,
AI systems, or hybrid workflows operating over the same deterministic,
machine-readable record of what occurred.

The detailed rationale for major canonical design choices is preserved separately
in `design_decisions.md`. This overview remains focused on the study's scope,
phenomena, and practitioner-facing interpretation rather than carrying the full
history of design tradeoffs inline.

The study uses a three-layer framing for what is fixed versus what leaders
choose. **Environmental conditions** are the exogenous facts of the run that
leaders must take as given. **Governance architecture** is the up-front design
choice about how labor is organized and what standing portfolio guardrails
exist. **Operating policy** is the recurring tick-by-tick decision logic that
acts within that chosen architecture. In the canonical study, total labor
endowment is environmental, while team decomposition and diversification targets
are governance-architecture choices that are fixed within a run and varied
across runs only when the experiment is explicitly about architecture.

---

## Relationship to Portfolio Optimization Theory

The resource allocation problem at the center of this study has surface similarities
to financial portfolio optimization. Both involve distributing scarce resources across
assets with uncertain returns, both must balance exploitation of known opportunities
against exploration of uncertain ones, and both must decide when to exit a losing
position and redeploy capital. A reader familiar with modern portfolio theory, the
Kelly criterion, or multi-armed bandit formulations will recognize the general shape
of the problem.

The similarities are real but limited. The structural differences between this model
and financial portfolio theory are not refinements — they are the reason a new model
is needed.

In financial portfolio theory, the investor and the asset are independent. Owning a
stock does not change its value, and the quality of information available to the
investor does not depend on how much capital is deployed. In this model they are not
independent. Executive attention actively shapes the quality of signals governance
receives about each initiative. Allocating insufficient attention below a minimum
threshold actively degrades information quality rather than merely failing to improve
it. The decision-maker is not a passive observer of an independent process — the
decision-maker is embedded in the signal generation mechanism. Standard portfolio theory
has no equivalent structure.

In financial portfolio theory, assets do not consume shared productive capacity in a
rivalrous way. Owning one stock does not prevent owning another except through budget
constraints. In this model, teams are indivisible and rivalrous. Assigning a team to
one initiative categorically prevents that team from working on another. The
opportunity cost of every staffing decision is not financial — it is organizational.
This constraint compounds over time in ways that budget constraints in financial
models do not.

In financial portfolio theory, assets do not improve each other. A bond position does
not increase the productivity of equity positions. In this model, enabler initiatives
increase a shared portfolio-level learning capability state that reduces effective
strategic signal noise for every other staffed initiative in future ticks. The return
on an enabler is not the enabler's own direct output — it is the aggregate improvement
in the quality of future organizational learning
across the portfolio. This interdependency is structural and has no standard analogue
in portfolio theory.

In financial portfolio theory, learning about an asset is separable from investing in
it. You can observe price signals and update your beliefs without committing
additional capital. In this model, the act of staffing an initiative is what generates
the signals that update belief. An unstaffed initiative produces no new information.
Exploration and exploitation are therefore not separable decisions — every investment
decision is simultaneously a resource allocation decision and an information
acquisition decision. This coupling is closer to the economics of active
experimentation than to passive portfolio observation.

Finally, financial portfolio theory has no equivalent of the flywheel mechanism. An
asset does not, when you divest it, continue generating returns independent of your
ownership. The accumulation of autonomous residual value streams from completed
initiatives — each adding a small increment that persists for the remainder of the
simulation horizon — is a fundamentally organizational phenomenon with no financial
instrument equivalent. The study's central question about how governance regimes
differ in their ability to build these compounding mechanisms cannot be reduced to a
portfolio optimization problem.

These differences are also where the study's contribution is concentrated. The
interaction between attention-dependent signal quality, indivisible rivalrous teams,
portfolio-level capability interdependency, and autonomous residual accumulation
creates a class of governance dynamics that portfolio theory cannot address. The
study is designed to reveal the structural logic of those dynamics — not to extend
portfolio theory, but to characterize a different problem that organizations actually
face.

## Initiatives

An initiative is a bounded effort through which an organization allocates labor and executive attention to pursue value under uncertainty. Initiatives generate informational signals over time, while economic effects in the canonical study are realized only at completion; governance observes only the signals and must infer the initiative's underlying quality when deciding whether to continue or stop investment.

The difficulty of governance arises from uncertainty. The true quality of an initiative cannot be known in advance, and forecasts are only hypotheses about what might occur. As work progresses, initiatives produce signals that update the organization's belief about their underlying quality, but those signals are noisy and incomplete. Governance must therefore allocate resources and make continuation decisions without ever directly observing the true quality of the work.

## The Initiative Types

In practice, initiatives tend to follow different patterns of value realization, which shape the governance decisions surrounding them. Not all work is the same, and treating it as though it were is one of the most common and costly mistakes in organizational design.

*The four types described below are not rigid categories — they are convenient labels for recognizable clusters of initiative attributes. Each label describes a distinct combination of uncertainty, value generation pattern, market ceiling, and the nature of the information the work produces. The simulation itself operates on initiative attributes and their current state, not on the type label. This means the model does not assume governance correctly identifies what kind of initiative it is dealing with. An initiative that leadership believes to be a proven mechanism may, as knowledge accumulates, reveal attributes that look more like an experiment. The study may also reveal that other meaningful clusters exist or that the boundaries between these clusters matter more than the clusters themselves, but these four define the initial design space.*

The four initiative families in the study are not arbitrary labels. They correspond
to distinct economic payoff structures through which organizations create value.
Quick wins represent bounded one-time payoffs after completion. Flywheels represent
initiatives that, once completed, create mechanisms that continue producing value
over time. Right-tail initiatives represent highly uncertain efforts whose value is
concentrated in rare major successes rather than typical outcomes. Enablers
represent investments that improve the organization's future capability rather than
producing substantial standalone value directly. The simulator therefore classifies
initiatives by payoff structure and learning dynamics, not by surface labels or
management vocabulary.

*All four initiative types are included in the simulation because they represent distinct economic mechanisms through which organizations create value. Flywheels and right-tail initiatives represent two well-known pathways to value creation — compounding mechanisms and surfacing rare major opportunities. Enablers represent investments that improve the organization's future learning capability. Quick wins represent bounded opportunities that produce real but non-compounding value. Together these four types define the design space within which governance decisions operate.*

**Flywheel initiatives** are investments in proven mechanisms. The organization
already understands why they work — the question is not whether the mechanism is
sound but whether the team can successfully add another turn to it. No direct value
is generated while the team is working. Instead, each completed initiative adds a
small increment of autonomous momentum to the flywheel mechanism, which then
produces value independently at every future tick regardless of whether anyone is
still actively working on it. The power of flywheel investment is cumulative and
non-obvious: any single initiative looks unremarkable during execution, and its
individual contribution after completion is modest. But an organization that
completes many flywheel initiatives over time accumulates a growing portfolio of
self-sustaining value streams that compounds into a significant and durable
advantage. A governance regime that consistently diverts resources away from
flywheel work — because it produces no visible return during execution — forgoes
this compounding effect entirely.

Some flywheel mechanisms persist longer and contribute more than others depending
on the quality of execution. Examples include installed bases, distribution networks,
automation systems, and logistics capabilities that continue operating after the
original team has redeployed.

**Right-tail initiatives** are experiments. The organization does not yet know whether the opportunity is real. Teams invest time and effort not to generate revenue but to discover whether the initiative represents a genuinely major opportunity. No value is produced during this exploratory phase. In the canonical study, the relevant modeled success condition is whether completion surfaces a major win: a rare strategic outcome significant enough that, in a real organization, leadership would plausibly launch a much larger follow-on effort outside the fixed-labor system modeled here. The rarity of major wins among completed exploratory initiatives is grounded by external evidence on breakthrough incidence in incumbent exploratory work; across multiple independent evidence sources, such outcomes appear to be in the low-single-digit percentage range among completed efforts. The simulation records that event as a distinct outcome rather than attempting to price the full downstream economics of a transformational success within the study horizon. If the initiative does not turn out to be a major win, the output is information, not revenue, and the right move is to stop and redirect the resources.

**Enabler initiatives** neither generate direct value nor test a market hypothesis. Instead they improve the organization's ability to learn about other work. In spirit, they are investments in the operating system of the organization itself. As W. Edwards Deming argued, organizational performance is largely a property of the system rather than of isolated individual effort. In the canonical study, this effect is represented through a single portfolio-level capability scalar rather than through multiple subtype-specific mechanisms. Completing an enabler increases that scalar, which then reduces effective strategic signal noise for staffed initiatives in future ticks. This is a deliberate simplifying assumption: it gives enablers a measurable downstream effect without separately modeling the different operational pathways through which DevOps improvements, experimentation infrastructure, dependency reduction, hiring systems, or decision-making processes might help in practice.

**Quick wins** are one-time opportunities with low uncertainty and small ceilings. They are real and completable, but they don't compound and they don't transform. Their primary risk is that they look attractive relative to the harder, slower work of flywheels and experiments, and they can quietly consume resources that should be deployed elsewhere.

Taken together, these initiative types represent the primary mechanisms through which organizations create long-term value. Some initiatives realize one-time value at completion. Others create mechanisms that continue producing value after the work is complete. Still others improve the organization's ability to learn effectively about future work. Over time, the organization therefore evolves not only through the outcomes of individual initiatives but also through the accumulation of capabilities that change how clearly future initiatives can be evaluated.

Quick wins are especially important because they provide the natural short-horizon
benchmark in the study. A governance regime focused on maximizing near-term value
should be expected to favor bounded, lower-uncertainty initiatives that realize
value quickly. The central governance question is therefore not whether quick wins
create value — they do — but what a regime gives up when it systematically favors
them over compounding mechanisms, rare major opportunities, and capability-building
work whose benefits emerge later.

This means the organization's value-generating capacity is not static during the simulation. As initiatives succeed, they may create mechanisms that continue generating value or improvements that increase the clarity with which future opportunities can be evaluated. Governance therefore shapes long-run outcomes not only by choosing which initiatives succeed or fail, but also by determining whether the organization accumulates the capabilities and mechanisms that make future value creation easier.

At the same time, neither residual mechanisms nor capability improvements should be
understood as permanent in practice. Real organizational advantages erode unless
they are renewed: flywheels lose momentum without continued reinforcement, process
improvements drift, and dependency reduction is gradually undone as new complexity
accumulates. The study therefore treats these as durable but not conceptually
infinite effects. In the canonical technical specification, both are modeled with
exponential decay, while keeping separate parameters for residual mechanisms and
portfolio capability so the model does not imply they erode at the same speed.

---

## The Two Mechanisms for Reducing Uncertainty

Leadership cannot make good stop or continue decisions without a sufficiently clear picture of whether an initiative is working. In this model, governance operates under two distinct and separable forms of uncertainty, each resolved through different mechanisms.

**Strategic quality uncertainty** concerns whether the initiative's underlying idea is sound — whether it will create value if executed competently. This uncertainty is not directly observable. It resolves through signals that accumulate as teams work over time, but those signals are noisy, and the noise depends on how much executive attention the initiative receives.

Two mechanisms accelerate the resolution of strategic quality uncertainty. **Continued investment** is the base mechanism. As teams work over time, they naturally accumulate observations that sharpen the picture of whether the initiative is strategically sound. Time spent working is the primary way the organization learns. But continued investment is not free — every period of active work consumes labor that could be deployed elsewhere, and an initiative that is neither generating value nor generating new information is consuming resources without returning either. **Executive attention** is a separate mechanism that can accelerate clarity, but its effect is not simply proportional to the amount of attention applied. There is a minimum threshold of involvement below which shallow attention actively makes things worse, not better. Above that threshold, deeper involvement reduces noise and accelerates clarity, but with diminishing returns. Executive time is finite and budgeted, and time spent going deep on one initiative is time unavailable for everything else.

**Execution fidelity uncertainty** concerns whether the initiative is proceeding according to plan — whether it will complete within its original time and cost estimate. This uncertainty is distinct from strategic quality. An initiative can be strategically sound while simultaneously proving harder and more expensive to execute than anticipated. The Kindle program is an illustrative example: the strategic thesis was correct and the market was real, but execution took substantially longer and cost substantially more than the original plan reflected. Execution fidelity uncertainty resolves differently from strategic quality uncertainty. Execution progress is more directly observable from elapsed time, delivery milestones, and resource consumption than strategic quality is from outcome signals. As a consequence, executive attention does not modulate the execution signal in the same way it modulates the strategic signal — execution progress accumulates through direct observation regardless of leadership's depth of involvement.

These two forms of uncertainty matter because governance regimes differ in how they respond to each. A regime with high strategic conviction and high cost tolerance will continue investing through deteriorating execution signals as long as the strategic thesis remains intact. A cost-sensitive regime treats execution overruns as stopping signals even when strategic belief is high. Neither philosophy is presupposed to be correct. The study is designed to measure how these different responses affect long-run value creation across environments with different joint distributions of strategic quality and execution difficulty.

---

## What Governance Actually Decides

Governance is the complete set of rules, explicit or implicit, by which leadership decides what to start, what to continue, what to stop, how much to personally get involved, and how to redeploy freed resources. In the current formulation of the model, governance decisions for an active initiative are limited to continue or stop. These decisions operate through three mechanisms that determine how leadership interacts with the initiative pool and the information those initiatives produce: sourcing, catalysts, and filters.

## Sourcing (Portfolio Selection)

Sourcing governs which initiatives enter the active portfolio. It represents the organization's primary act of selection: choosing which opportunities from the available pool receive labor and attention. These choices determine the initial distribution of initiative quality within the portfolio and shape the organization's strategic posture by balancing incremental, lower-uncertainty work against speculative initiatives with more uncertain outcomes.

## Catalysts (Clarity Acceleration)

Catalysts are mechanisms that increase the rate or precision of learning about an initiative's latent quality. Two mechanisms are available. Executive attention allocation can reduce signal noise by improving evaluation and interpretation of initiative outcomes. Continued investment allows additional signals to accumulate over time, enabling belief updates through observation of ongoing performance.

## Filters (Decision Logic)

Filters (Decision Logic) covers the decision logic applied when governance reviews the portfolio. Filters process the organization's accumulated beliefs about each initiative's latent quality formed from noisy performance signals over time and determine whether an initiative continues or is stopped and how the freed resources are reassigned.

In this model, governance is implemented through a specific set of enumerable decisions. Any two implementations of this study should agree on this list as the complete universe of governance levers:

**Initiative mix (Sourcing).** The composition of the organization's active initiative portfolio across the four initiative types. This determines the portfolio's initial distribution of beliefs about initiative quality by balancing proven, incremental growth against speculative, transformative experiments. It determines how much of the organization's labor is deployed against certain incremental value versus uncertain transformative value at any given time.
The pool of available initiatives is deterministically seeded and dynamically materialized from family-specific frontier distributions as governance frees capacity, so the opportunity set evolves within a run while remaining reproducible across runs.
The frontier is an environmental parameter, not a governance lever.
What differs between regimes is which initiatives they choose to activate through explicit staffing decisions and, consequently, how quickly each family's frontier is consumed.

**Executive attention allocation (Catalyst).** How the executive's finite time budget is distributed across active initiatives during each review period to increase signal precision. This includes both the number of initiatives receiving any attention and the depth of involvement in each. Because there is a threshold below which shallow involvement increases noise, the allocation decision determines whether each initiative receives enough involvement to update the organization's beliefs effectively, or so little that the involvement is counterproductive.

**Stop criteria (Filter).** The conditions under which governance terminates an
initiative. Filters process the organization's accumulated beliefs about each
initiative's latent quality, formed from noisy performance signals over time, to
determine when continued investment is no longer justified. Stop criteria apply
to all initiatives and operate only on observable signals and the organization's
current beliefs about initiative quality. Because governance does not directly
observe true quality, the same decision logic must be definable over observables
even when some initiative attributes — such as an observable bounded prize
ceiling — make particular stop paths applicable only to a subset of initiatives.

Four distinct conditions can trigger a stop:

- *Confidence decline*: the organization's accumulated understanding of the initiative's strategic quality has fallen below a threshold that no longer justifies continued investment. This condition operates on the strategic quality belief only.

- *Prize inadequacy*: for initiatives with an observable bounded prize, the
  initiative's visible upside influences how much persistence governance grants
  before concluding that the bounded opportunity is no longer earning continued
  investment. Larger visible bounded opportunities earn more review patience than
  smaller ones, while still being evaluated through the organization's current
  strategic belief. This rule is implemented as a patience window rather than an
  immediate threshold crossing: a single below-threshold evaluation does not
  trigger termination. Termination is recommended only after the initiative has
  remained persistently below the threshold for a configurable number of
  consecutive evaluations. A recovery in expected value resets the patience
  window.

- *Stagnation*: the initiative is generating no meaningful new strategic
  information and has not earned continued patience under the relevant rule for
  its observable state. For bounded-prize initiatives, this means informational
  stasis together with persistence below the bounded-prize patience condition.
  For initiatives without an observable bounded prize, this means informational
  stasis together with failure to raise strategic belief above the neutral
  baseline from which the organization began. An initiative with stable high
  belief is not stagnant — it is well understood and still appearing promising.
  An initiative that is below the relevant patience condition but still producing
  meaningful shifts in belief should continue, because new information may
  rehabilitate its assessment. The informational component of this test measures
  net change in strategic belief over a window of staffed ticks — ticks during
  which the initiative was actively assigned a team — rather than over calendar
  time.

- *Execution overrun*: the organization's belief about execution fidelity — its current estimate of whether the initiative is tracking to its original plan — has deteriorated below a governance-configured threshold. This condition is independent of strategic quality belief. A cost-sensitive regime stops initiatives whose execution has significantly overrun even when strategic conviction remains high. A cost-tolerant regime ignores or heavily discounts this signal, continuing as long as strategic belief is intact. Regimes may also specify a hard cap above which no amount of strategic conviction justifies further investment. This condition is present in the model as an explicit governance lever, not as an automatic rule, so that the study can compare regimes with different cost-escalation sensitivities.

**Cost-overrun tolerance (Filter).** The degree to which governance continues investing in an initiative whose execution is proving more expensive or time-consuming than originally planned, conditional on maintained strategic conviction. This lever is separate from the stop criteria above because it captures a distinct governance philosophy: some organizations treat rising projected cost as strong evidence against continuation regardless of strategic belief, while others treat it as a manageable operational reality that does not undermine the strategic thesis. Cost-overrun tolerance is parameterized by the threshold at which execution deterioration triggers a governance response and by the maximum total investment a regime is willing to make before strategic conviction alone is insufficient to justify further funding. Differences in this lever are among the primary treatment dimensions of the study.

**Review discipline.** How frequently and selectively governance chooses to evaluate initiative performance and act on what it finds. The engine invokes the policy every tick, so review frequency is a behavioral property of the policy rather than a separate engine parameter. A policy that reviews every initiative every tick and a policy that performs lighter scrutiny on most initiatives before deciding are both valid implementations. Differences in effective review frequency are observable in output logs and produce measurable effects through the attention-noise and belief-update dynamics that are already in the model.

**Reassignment rules.** How teams are redeployed when an initiative ends — whether by termination or stagnation — and how teams are reallocated from lower-performing active initiatives to better alternatives from the available pool. Reassignment is not frictionless: a team moved to a new initiative incurs a ramp-up period during which its learning efficiency is temporarily reduced. In the canonical study, economic effects remain completion-gated rather than flowing continuously during execution. This penalty applies regardless of which initiative type the team is moving from or to, and it means that frequent reassignment carries a real cumulative cost. One additional property governs how knowledge is handled at reassignment: the confidence the organization has built up about an initiative stays with the initiative, not with the team. A new team assigned to an initiative inherits the current state of understanding, and an initiative that is paused retains its accumulated knowledge if it is later reactivated.

---

## The Conditions Being Studied

The governance levers above are what leadership chooses. The environmental parameters below are what the simulation holds constant or varies as background conditions — the world the governance regime is operating in. Any two implementations of this study should agree that these parameters, and only these parameters, constitute the environmental inputs.

**Total labor endowment.** The aggregate productive capacity available to the
organization. This is fixed for a given simulation run and creates the binding
resource constraint on how much work can proceed in parallel.

**Governance architecture note.** The decomposition of that labor endowment into
teams — how many teams exist, how large they are, and what standing portfolio
guardrails leadership sets for diversification or concentration — is not an
environmental condition in the current study framing. It is a governance
architecture choice made before the run begins and then held fixed within the
run. The canonical baseline study compares operating governance regimes under a
common architecture unless an experiment explicitly varies architecture.

**Observable prize ceiling.** Some initiatives expose an observable bounded prize ceiling used in expected-value stop logic. This ceiling is observable to governance; it is not hidden the way an initiative's true quality is. Organizations can estimate the upside of a bounded opportunity. What they cannot directly observe is whether the initiative is good enough to actually capture it. The observable prize ceiling enters the stop criteria through the prize-adequacy condition, where it is combined with the organization's current confidence to estimate expected value relative to invested cost.

**Latent quality.** Each initiative has a true underlying quality that is not directly observable by governance. This quality is fixed at the time the initiative is created and governs how the initiative actually performs if given sufficient investment. The governance challenge is that this quality must be inferred from noisy signals over time rather than observed directly. The four initiative types draw their quality from different distributions — flywheel initiatives tend toward higher quality with lower variance, reflecting that they extend proven mechanisms; right-tail initiatives draw from a distribution with a long right tail, reflecting that most speculative opportunities are mediocre while a small number are genuinely transformative.

**Execution difficulty.** Each initiative has a true underlying execution difficulty that is not directly observable by governance. This represents how long the initiative will actually take to complete if pursued without interruption. It is fixed at the time the initiative is created and is independent of strategic quality: a strategically valuable initiative may be genuinely difficult to execute, and an easy initiative may have low strategic quality. Execution difficulty must be inferred from execution progress signals over time rather than observed directly. Initiative types may draw execution difficulty from different distributions — for example, novel hardware programs may be assigned higher average execution difficulty than familiar software-only work.

Each initiative also has an observable counterpart to execution difficulty: its **planned duration**, set at generation and visible to governance from the start. Planned duration represents the organization's initial expectation of how long the initiative should take. The gap between planned duration and the execution progress signals that accumulate over time is the primary source of cost-overrun information available to governance.

**Initiative pool.** The pool of available initiatives is deterministically seeded and dynamically materialized from family-specific frontier distributions as governance frees capacity. New initiatives appear during the run as earlier opportunities are consumed, but the frontier sequence is fixed by the world seed — governance decisions determine the rate at which the frontier is drawn down, not its content. The pool includes both active initiatives and those waiting to be staffed.

**Dependency level.** Each initiative has a dependency level reflecting how much its progress relies on factors outside its team's direct control — other teams, systems, or unresolved external conditions. High dependency increases the noise in the signals the initiative produces. Dependency is fixed per initiative and does not change during the run. Governance can respond to dependency by prioritizing lower-dependency initiatives or by investing in enabler work that improves future signal clarity across the portfolio.

**Learning rate.** The baseline rate at which continued investment reduces uncertainty about an initiative's true quality, absent dependencies and absent executive attention. This is the base speed of organizational learning.

**Noise level.** The degree of random variation in the signals that initiatives produce each period. High noise makes it harder to distinguish a genuinely good initiative from one that happened to produce a positive signal by chance, and vice versa. Noise is affected by initiative type, dependency level, and executive attention.

**Executive time budget.** The total attention the executive has available per review period to distribute across active initiatives. This is fixed and creates the binding constraint on executive involvement across the portfolio.

**Attention-to-signal curve.** The functional relationship between the amount of executive attention devoted to an initiative and the resulting change in signal clarity. Below a minimum threshold, attention increases noise. Above that threshold, noise decreases with diminishing returns. The shape of this curve is a fixed property of the simulated environment, not a governance choice. The governance decision is how to allocate the finite budget given this curve.

**Simulation horizon.** The number of time periods the simulation runs before final value is measured. One tick represents one calendar week. The canonical horizon is 313 ticks, approximately six years — a reasonable long-term planning horizon for large incumbent firms. Different organizational contexts may warrant shorter horizons (e.g. startups with faster capital cycles) or longer ones (e.g. construction, mining, or pharmaceutical companies with decade-scale project lifecycles).

External evidence on exploratory initiative duration supports reading this six-year horizon as a meaningful observation window for governance differences rather than as a claim that all strategically important right-tail initiatives fully mature within that period. In practice, many such initiatives require several years to reach a stable scale decision and longer still to become materially important at the company level.

---

## The Governance Archetypes Being Tested

Rather than testing every possible combination of governance levers, the study evaluates a small number of recognizable archetypes. Each archetype is a specific, complete configuration of all the levers enumerated above. The purpose of testing archetypes rather than sweeping the parameter space continuously is to produce results that are interpretable and recognizable — a leader should be able to read the findings and identify which archetype most closely resembles how their own organization currently operates.

**Concentrated, high-touch.** A small number of initiatives receive the large majority of executive attention and organizational resources. The executive is deeply involved in each. The initiative mix is narrow and deliberate. Stop decisions are made with high-quality signal. The opportunity cost is that much of the potential initiative pool goes unstaffed or unattended.

**Broad, low-touch.** Resources and attention are distributed widely across a large number of initiatives. The executive monitors rather than engages deeply. Clarity develops primarily through continued investment over time rather than through executive signal amplification. The opportunity cost is slower clarity per initiative and reduced capacity to unblock teams.

**Aggressive stop-loss.** Governance terminates initiatives quickly when early signals are unfavorable. The regime reviews frequently and acts decisively on negative signals, prioritizing the recovery and redeployment of resources over patience with uncertainty. Reassignment is fast and systematic.

**Patient moonshot.** Governance tolerates long periods of uncertainty and sustained investment in exchange for access to the largest possible outcomes. Initiatives are given substantial time and resources before termination. The regime accepts the risk of prolonged investment in initiatives that ultimately do not produce value.

**Balanced.** Mixed initiative portfolio, executive attention distributed evenly across active initiatives, moderate stop thresholds. Not a recognizable practitioner archetype — no leader describes their organization as "balanced by design" — but an essential reference baseline for the study. It exercises all channels at moderate settings, validates model mechanics during implementation, and anchors comparative findings by establishing a neutral midpoint against which the named archetypes can be measured.

The first two archetypes above — Concentrated/high-touch and Broad/low-touch — are not implemented as discrete named experimental regimes in the study. Attention breadth (the balance between depth and concentration of executive engagement versus breadth across many initiatives) is a continuous governance parameter. The experimental design sweeps it as a continuous axis using Latin hypercube sampling rather than comparing two fixed points. This produces stronger findings: instead of asking "does Concentrated beat Broad?" the experiment maps where on the concentration continuum outcomes shift and under what environmental conditions those shifts are largest. A practitioner can locate their organization anywhere on that continuum and read the relevant findings directly, rather than asking which of two discrete profiles they most resemble. The two named stop-behavior archetypes — Aggressive stop-loss and Patient moonshot — are implemented as fixed experimental anchor points alongside the Balanced baseline.

---

## What the Study Measures

### Discovery of Viable Opportunities

This study models value creation as the governance of a portfolio of initiatives whose true quality is unknown and can only be inferred gradually from noisy signals. For right-tail initiatives, the canonical study records whether completion surfaces a major win. That outcome is determined by a hidden generation-time property and is not triggered by a separate pre-completion viability threshold.

This major-win event represents the moment when governance has pursued a right-tail initiative all the way to completion and the hidden state of the world reveals that the initiative was in fact transformational. The simulation records when such events occur, how much labor was required to reach them, and whether major opportunities were prematurely terminated by governance rules.

The study evaluates governance regimes by measuring the following outcomes. These are the things the simulation produces that allow governance approaches to be compared.

**Cumulative value created over time.** The primary outcome measure. This is the total value generated by the organization across all initiative types over the simulation horizon. Because compounding matters, the trajectory of value creation over time is as important as the terminal value.

This measure captures not only value generated directly by active initiatives but also the long-run effects of mechanisms and capabilities created by earlier work. Governance regimes therefore differ not only in the value they extract from current initiatives but also in whether they accumulate durable mechanisms and portfolio improvements that increase the effectiveness of future initiatives.

Value in the simulation arises through two realized economic channels. Initiatives may realize one-time value at completion, or they may create mechanisms that continue generating value after the initial work is complete. For analytical purposes the simulation records the contribution of these channels separately. Major-win events are also recorded, but in the canonical study they are not by default priced as realized economic value within the simulation horizon.

This decomposition allows the study to distinguish environments and governance regimes not only by how much value they produce, but also by the mechanisms through which that value is created. Some environments may produce most of their value through incremental compounding work, while others may rely more heavily on discontinuous discoveries or persistent mechanisms established earlier in the simulation.

Because some initiatives improve the productivity of future work or create mechanisms that persist beyond the active life of the initiative, the state of the organization at the end of the simulation also contains information about its future prospects. Two governance regimes may produce similar cumulative value during the simulated horizon while leaving the organization in very different conditions for future value creation.

For this reason the simulation also records the organization's **terminal portfolio capability** at the end of the horizon. This captures the degree to which the organization has accumulated durable learning-capability improvements that change how clearly future initiatives can be evaluated.

**Probability of discovering high-quality opportunities.** Among all initiatives with high latent quality and sufficient market ceiling, what fraction did the governance regime successfully identify before termination? This measures whether the regime is capable of finding genuinely valuable opportunities.

**Time to major win.** For right-tail initiatives that surface a major win at completion, how long did the process take? This measures the efficiency and patience required to reach transformational outcomes.

**Distribution of initiative quality among outcomes.** Among initiatives that were stopped, what was the distribution of their true latent quality? Among right-tail initiatives that surfaced a major win at completion, what was the distribution? This allows analysis of whether the governance regime's decisions are well-calibrated to actual quality, or whether the regime is making systematic errors in either direction.

The analysis will examine how governance decisions correlate with each of these outcomes, and under which environmental conditions those correlations are strong or weak.

### Review Discipline and Information Timing

The governance policy is invoked at every tick and may act on any initiative at any time. This means effective review frequency is a policy choice, not an engine constraint. A regime that reviews every initiative every tick is behaviorally different from one that acts infrequently, and those behavioral differences produce measurable consequences through the mechanisms already in the model.

The underlying dynamic this study is designed to examine is the relationship between the rate at which governance acts and the rate at which meaningful information accumulates. If governance acts more frequently than the rate at which new signal becomes reliable, decisions will be driven more by noise than by genuine learning. If governance acts infrequently relative to the rate at which beliefs evolve, it may act on stale information. This mismatch between decision clock speed and information half-life is not modeled as a separate parameter — it is an emergent property of how the policy chooses to use the per-tick invocation and how attention allocation shapes signal clarity. The study examines this interaction through its effects on belief trajectories, stop decision quality, and long-run value creation.

## What the Study Is Designed to Learn

The simulation is designed to answer seven analytical questions. The first two concern the timing and discipline of governance decisions. How does the frequency and selectivity with which governance chooses to act interact with the information half-life of initiative signals to influence decision quality and long-run value creation? And how does the stop threshold map to long-run right-tail discovery rate: where is the inflection point between organizational patience and resource efficiency?

The next two concern the cost structure of attention and switching. What is the shape of the efficiency frontier between breadth and depth of executive attention, and how does it shift across environmental structures? At what ramp penalty magnitude does the optimal governance regime shift from aggressive reallocation to patient persistence?

The next two frame the study's primary contribution. Across governance regimes, what does the efficiency-exploration frontier between cumulative flywheel value and right-tail discovery probability look like, and which archetypes sit on or near it? And do governance conclusions hold across different economic environments — utility-like, venture-like, and mixed — or are they artifacts of a specific value structure?

The seventh concerns a structural interaction between the first two groups. Stop decisions are made on belief estimates that attention allocation has already shaped — shallow attention increases noise, which corrupts belief, which may trigger termination on initiatives a better-informed regime would continue. To what degree are stop decisions confounded by the attention strategy that preceded them, and does this interaction produce systematic errors in one direction?

---

## What This Study Does Not Address

Defining scope is as important as defining content. The following factors are real, consequential, and beyond dispute as influences on organizational performance. They are excluded from this study not because they don't matter, but because including them would prevent the structural governance dynamics — the thing this study is actually designed to illuminate — from being visible in the results.

Any implementation of this study should treat the following as explicitly out of scope:

**Individual autonomy and agency.** Teams in this model execute their assigned work. They do not choose their own initiatives, negotiate their assignments, or vary in their willingness to follow governance decisions. The study does not model what happens when talented people disagree with or circumvent governance.

**Employee morale and motivation.** The model does not include any mechanism by which repeated terminations, poor governance decisions, or resource starvation affect team performance or retention over time. Real organizations experience these effects; this model does not.

**Organizational culture.** The shared norms, beliefs, and behavioral defaults that shape how organizations actually operate are not modeled. Two organizations with identical governance rules can produce very different outcomes if their cultures differ. This study holds culture constant by not modeling it.

**Political dynamics and power.** Governance decisions in this model are made by a single executive applying a consistent rule set. The study does not model coalition formation, advocacy for particular initiatives, or the influence of organizational hierarchy on which initiatives survive review.

**Individual skill variation.** All teams are assumed to have equivalent capability. The study does not model what happens when some teams are significantly more skilled than others, or when skill levels change over time through learning, attrition, or hiring.

**Hiring, firing, and talent acquisition.** Total labor endowment and the realized team structure are fixed for the run. The study does not model the ability to grow the team, replace underperforming individuals, or compete for talent.

**Compensation and incentive structures.** How individuals are paid, rewarded, and recognized is not modeled. The study does not address whether incentive design reinforces or undermines governance decisions.

**External shocks and competitive dynamics.** The simulation does not include market disruptions, competitive moves, macroeconomic shifts, or other external events that change the value of in-progress initiatives. An initiative's market ceiling and latent quality are fixed at initialization and do not change in response to the external environment.

**Regulatory and legal constraints.** The study does not model any external rules that constrain which initiatives can be pursued or how they must be governed.

**Board governance and investor pressure.** The executive operates with full autonomy within the governance archetype being tested. The study does not model what happens when external stakeholders constrain or override governance decisions.

**Technology infrastructure and technical debt.** The study represents infrastructure improvement through an abstract portfolio-level learning-capability scalar that may be modified by enabler completions, but does not model the specific dynamics of accumulated technical debt, platform constraints, or infrastructure limitations.

**Geographic distribution and organizational structure.** The model treats the organization as a single unit. It does not model what happens when teams are distributed across locations, time zones, or organizational silos with different reporting structures.

**Ethics and social impact.** The study measures value creation in economic terms. It does not model reputational effects, stakeholder impact, or the long-run consequences of governance decisions that produce short-term value at the expense of broader considerations.

**Prize-ceiling uncertainty.** An initiative's observable bounded prize ceiling is treated as a fixed, observable input when that channel exists. The study does not model uncertainty in those estimates or the possibility that the addressable upside changes as the work progresses.

The study does model two distinct forms of initiative-level uncertainty: uncertainty about strategic quality and uncertainty about execution difficulty. Strategic quality uncertainty — whether the initiative's underlying idea is sound — is the primary driver of stop and continue decisions. Execution difficulty uncertainty — whether the initiative will proceed according to plan — is a separate signal that governance regimes may weight differently. The study is specifically designed to compare regimes that differ in their response to this second form of uncertainty. What is out of scope is a third form of uncertainty — whether the market opportunity itself is real and sized as estimated — which would require modeling TAM as a stochastic variable rather than a fixed parameter.

**Time discounting.** The simulation assumes infinite patience within the horizon — future value is not discounted relative to present value. This is a deliberate choice aligned with the focus on long-run organizational evolution rather than finite-tenure managerial decisions. Governance regimes optimized for near-term value capture are not modeled.

**Execution belief initialization bias.** Execution belief (execution_belief_t) initializes to 1.0 for all initiatives. For initiatives that are genuinely on plan, the belief update's clamp at 1.0 produces systematic downward drift, causing cost-sensitive governance to apply slightly more stopping pressure than a neutral initialization would. This bias is consistent across all governance regimes and does not differentially favor any archetype; comparative findings are not materially affected. However, in scenario tests involving a single on-plan initiative, cost-sensitive regimes will appear slightly more aggressive than intended.

**Endogenous proposal quality degradation.** The model captures within-family quality degradation through the dynamic opportunity frontier: as a family's opportunities are consumed, the frontier quality declines, so aggressive activation depletes the best opportunities first. However, the model does not represent cross-family or organizational-cultural channels through which consistent early termination of speculative work can reduce the quality, ambition, and diversity of future proposals across the entire portfolio. Governance archetypes that stop aggressively will therefore perform better in this model than in real organizations, where a track record of early stopping depresses the pipeline of high-quality speculative proposals over time. Comparative findings about risk-averse governance are therefore lower bounds on its real organizational cost.

**Dynamic strategic quality.** Latent quality is assigned at initiative creation
and does not change. The model does not represent initiatives whose strategic value
changes as markets evolve, competitors respond, or technology shifts. Findings about
patient governance for right-tail initiatives are valid only in environments where
strategic quality is stable over the measurement horizon. In competitive or rapidly
evolving environments, the value of waiting for additional signals is lower than this
model predicts.

**Completion-gated value realization.** In the canonical study, economically
meaningful effects are realized only at completion. An initiative that is stopped
one tick before completion realizes no partial lump value, no partial major-win
credit, and no partially activated residual stream. This is a deliberate modeling
simplification that keeps value semantics crisp and implementation unambiguous, but
it makes stopping decisions near completion more all-or-nothing than they are in
many real organizations, where partially completed work can still leave behind some
recoverable value.

**Surfaced-not-priced right-tail wins.** In the canonical study, right-tail
initiatives are evaluated primarily through whether completion surfaces a major
win, not through a fully priced model of the downstream economics of a
transformational success. This prevents a single modeled moonshot from mechanically
swamping all other value channels inside the base study, but it also means the
simulation is better interpreted as a study of governance's ability to preserve and
surface rare major opportunities than as a study that fully prices the value of
capturing them.

**One-stock capability simplification.** Enabler initiatives are represented
through a single portfolio-level capability scalar that reduces effective
strategic signal noise for future work. This is a reduced-form simplification, not
a claim that DevOps improvements, experimentation infrastructure, dependency
reduction, and other capability-building efforts are equivalent in practice. The
canonical study asks whether governance underinvests in capability-building work at
all; it does not separately model the many distinct mechanisms through which such
work might improve organizational performance.

**EMA boundary bias and belief precision.** The belief update clamps at [0, 1],
producing systematic downward bias for initiatives whose true quality is near 1.0:
an initiative with latent_quality = 0.9 and quality_belief_t ≈ 0.95 is pulled
down by negative noise draws but clamped on positive ones, generating a downward
bias in equilibrium belief. This may cause the model to understate the governance
value of patience for high-quality initiatives near the upper boundary,
particularly for Patient moonshot and Focused/high-attention archetypes.
Separately, governance cannot distinguish a quality_belief_t based on two noisy
observations from one based on forty: the policy sees only the scalar belief,
not the observation count underlying it. The implicit precision proxy via
effective_signal_st_dev_t and learning efficiency is coarser than a formal
sample count or posterior variance. Any archetype intended to be sensitive to belief
uncertainty should be interpreted with this limitation in mind.

**Cross-initiative value interactions.** Initiatives are independent in value
generation except through the shared portfolio_capability_t (C_t) capability scalar. Competitive
cannibalization (two initiatives addressing the same customer mechanism),
technological complementarity (one initiative making another cheaper to execute),
and diminishing marginal returns within a mechanism are all excluded. The
independence assumption may overstate the value of portfolio breadth strategies
and understate the value of concentration, systematically biasing findings about
the Broad/low-touch governance posture relative to Concentrated/high-touch.

**Attention-dependent execution visibility.** The model assumes execution progress
is directly observable from elapsed time and delivery signals regardless of
leadership attention. In practice, low attention is precisely what allows schedule
slips to go undetected until they are severe. This assumption makes the execution
signal cleaner than it is in real organizations and may cause the model to overstate
the governance value of cost-sensitive stopping rules — such rules perform well here
because overruns are always visible, but in real organizations the overruns that
trigger those rules may not surface until after significant sunk cost.

**Execution-belief calibration at the upper boundary.** Execution belief
initializes at the on-plan boundary and is then updated under a bounded process.
That choice keeps the execution signal interpretable, but it can create slight
asymmetry near the upper boundary: for genuinely on-plan initiatives, negative
noise draws move the belief away from the boundary while equally strong positive
draws are partially absorbed by the clamp. Comparative regime findings remain
useful because this assumption is shared across regimes, but cost-sensitive
governance may appear slightly more aggressive than intended in edge cases.

---

This is a simulation, not a case study. It does not model any specific company or industry. Its value is in revealing structural dynamics — the underlying logic of why certain governance choices produce certain outcomes — so that leaders can recognize those dynamics in their own organizations and make better-informed decisions about how to allocate the two things they can never get back: their people's time and their own.

The detailed rationale behind these canonical choices is preserved separately in
`design_decisions.md`. This overview remains focused on scope, modeled
phenomena, and practitioner-facing interpretation. The analysis workflow and
dual human/AI consumption model are described in
`analysis_and_experimentation.md`.



## Glossary

Canonical term definitions (with code/schema names, observation-boundary status, and design-doc citations) live in `docs/design/glossary.md`.
