# Primordial Soup: Study Brief

## Purpose of this note

This note explains how the Primordial Soup simulation works, what it measures,
and what it is designed to reveal — written for a business audience rather than
a technical one.

The study uses a Monte Carlo simulation to run a controlled experiment that
would be impossible to run in the real world: taking the same organization, the
same pool of initiatives, and the same uncertain environment, and asking what
happens under different governance approaches. Because the simulation can run
thousands of scenarios quickly, it can reveal structural patterns in how
governance choices shape long-run outcomes — patterns that would take decades
to observe in practice and would be nearly impossible to isolate from all the
other things changing at the same time.

-----

## What the study is

The simulator models an organization managing a portfolio of initiatives over
six years. Each initiative has a true underlying quality — how strategically
valuable it actually is — but leadership cannot observe that quality directly.
They can only observe imperfect signals as work progresses, form beliefs about
whether an initiative is worth continuing, and make decisions accordingly.

This mirrors reality. Leaders never know in advance which bets will pay off.
They must allocate scarce people and attention, watch for evidence, and decide
when to persist and when to cut their losses — all without being able to see
the ground truth underneath.

Two features of the model deserve particular attention because they shape
everything else.

**Leadership attention changes what you learn, not just how fast.** One of
the most consequential decisions an executive makes — often implicitly rather
than explicitly — is how many hours per week they personally engage with
active initiatives. In practice, this ranges widely: some CEOs are essentially
hands-off, spending close to zero hours per week in direct initiative
involvement; others spend up to 20 hours per week. The model treats this as
a genuine governance variable with real consequences in both directions.

Deeper involvement improves the quality of the signals an initiative produces
— not just the speed of learning, but the clarity of what is learned. However,
this relationship is not linear. Below a minimum threshold of involvement,
shallow attention actively degrades signal quality rather than simply failing
to help: an executive who glances at a weekly status update may actually leave
the team harder to evaluate than if leadership had stayed entirely out of it,
because half-formed attention generates noise without generating insight. Above
that threshold, deeper involvement improves clarity, but with diminishing
returns. And because attention is a fixed weekly budget — time spent going deep
on one initiative is time unavailable for everything else — the allocation
decision is genuinely consequential. The study is designed to map where those
tradeoffs live.

**Completed work keeps producing value on its own.** Some initiatives, once
completed, activate ongoing value streams that continue running after the team
has moved on to something else. Think of a distribution network, an
automation system, or a marketplace platform: the team that built it redeployed
years ago, but the mechanism keeps generating returns. These streams accumulate
across the portfolio over time. Whether and how much to invest in this kind of
work — versus faster, more immediately visible opportunities — is one of the
central governance tradeoffs the study is designed to examine.

-----

## What the study measures

The study evaluates governance regimes along three outcome families.

**1. Realized economic performance**

Cumulative value created over the six-year horizon, broken into two types:
one-time value realized when an initiative completes, and ongoing value from
the compounding mechanisms that completed initiatives leave behind. The
breakdown matters. A regime that generates most of its value from quick
completions is doing something fundamentally different from one that builds
a growing base of self-sustaining mechanisms — even if both show similar
total numbers at the end. The trajectory of value creation over time is as
important as the terminal level, because compounding takes time to build and
accelerates once it gets going.

**2. Major-win discovery performance**

How often does the governance regime successfully identify and pursue a
genuinely transformational opportunity all the way to completion? The study
tracks how many major wins are surfaced, how long they take to reach, and
how much organizational effort they require. Major wins are rare — the model
grounds them at roughly 1–4% of exploratory initiatives, consistent with
external evidence on breakthrough incidence in incumbent firms. A governance
regime that is too impatient will terminate these initiatives before the
picture becomes clear. The study measures how much of that option value
different regimes preserve or destroy.

Note that the model records major wins as discovery events rather than pricing
their full economic value. The study is designed to measure whether governance
preserves the ability to find transformational outcomes, not to simulate the
full downstream consequences of a company-scale breakthrough.

**3. Organizational capability development**

Over time, some initiatives — when completed — improve the organization’s
ability to evaluate future work. These are enabler initiatives: investments
like data and analytics infrastructure, experimentation platforms, automated
testing pipelines, dependency reduction between teams, or process improvements
that make it faster and cheaper to run pilots. They do not generate direct
value themselves. Their value is entirely indirect — they make everything else
the organization does better.

The specific mechanism in the model is this: a completed enabler reduces the
noise in the signals that future initiatives produce. In practical terms, this
means the organization reaches confident conclusions about those future
initiatives faster and with less wasted investment. Teams that would previously
have needed 18 months of work before leadership could assess whether an
initiative was worth continuing may now need only 12. Initiatives that would
previously have been terminated too early — because the signal was too noisy
to read clearly — survive long enough for their true quality to become visible.
Initiatives that should have been stopped sooner get stopped, because the
signal is cleaner.

The cumulative effect is compounding. An organization that has completed
several enabler initiatives evaluates its entire portfolio with higher
precision than one that has neglected them. This advantage is invisible in
any single initiative review but shows up materially in major-win discovery
rates and in the quality of stop/continue decisions across the portfolio over
time.

The study tracks how much of this organizational learning infrastructure a
governance regime builds or neglects. A regime that crowds out enabler work
in favor of more immediately visible returns may look comparable on economic
metrics during the six-year window while leaving the organization meaningfully
less capable of evaluating future opportunities.

Two regimes can produce similar cumulative economic value while leaving the
organization in very different capability states. A measure that looks only
at returns during the study horizon will miss this distinction entirely.

-----

## Initiative families and value channels

Four types of initiative are included because they represent distinct
mechanisms through which organizations create long-term value. The simulation
engine treats them identically — it does not apply special rules by type.
The types differ only in their underlying characteristics: how uncertain they
are, how long they take, and what kind of value they produce.

|Type          |How it creates value                                             |What outcome it drives    |What makes it hard to evaluate                                            |
|--------------|-----------------------------------------------------------------|--------------------------|--------------------------------------------------------------------------|
|**Quick win** |One-time payoff at completion                                    |Near-term economic returns|Low uncertainty; the risk is opportunity cost, not strategic ambiguity    |
|**Flywheel**  |Ongoing returns that persist and compound after the team moves on|Long-term economic returns|Value is invisible during execution; only appears after completion        |
|**Enabler**   |Improves the organization’s ability to learn about future work   |Organizational capability |No direct return; value is indirect and shows up later in better decisions|
|**Right-tail**|Rare but potentially transformational discovery at completion    |Major-win discovery       |High uncertainty throughout; most will not be major wins, but some will   |

Each type creates real value, and each type creates real risk. A governance
regime that concentrates too heavily on quick wins captures near-term value
but may leave compounding mechanisms and transformational opportunities
unpursued. A regime that concentrates too heavily on right-tail bets may
leave readily available value on the table while waiting for breakthroughs
that may not arrive within the horizon. A regime that is too slow to stop
underperforming work keeps teams occupied on initiatives that will never
succeed. The study is not designed to declare one posture universally
superior — it is designed to reveal the conditions under which different
postures create different tradeoffs.

-----

## How the simulation learns — and what leadership can see

### What is hidden

Every initiative in the simulation has a true underlying quality — how
strategically valuable it actually is — that leadership cannot directly
observe. Similarly, every initiative has a true execution difficulty — how long
it will genuinely take — that also cannot be observed directly. These hidden
truths govern what actually happens, but governance can never see them.

Whether a right-tail initiative turns out to be a major win is also determined
at the moment the initiative is created and hidden until completion. Governance
can only increase the probability of surfacing major wins by keeping
high-quality right-tail initiatives alive long enough to complete.

### What leadership can see

From the moment an initiative is created, leadership can see its stated plan
(how long it is expected to take) and how much it might contribute to
organizational capability. For some initiatives, leadership can also see a
visible ceiling on the potential upside — what the model calls a bounded
opportunity.

A bounded opportunity is one where leadership has a reasonable estimate of
the maximum value the initiative could ever create. A contract with a fixed
scope, a market segment with a known and finite size, a product enhancement
targeting a specific customer base whose total spend is estimable — these are
bounded. Leadership knows roughly how large the prize could be, even if they
don’t yet know whether the initiative is good enough to capture it.

Why does the ceiling matter? Because it changes how patient governance should
be. An initiative with a large visible upside has earned more runway before
governance concludes the investment is not worth continuing. An initiative with
a small visible upside reaches that conclusion faster, because even a
successful outcome would not justify extended investment. The model makes this
explicit: patience scales linearly with the size of the visible opportunity.
Knowing the ceiling does not reveal whether the initiative will succeed — that
is still hidden — but it calibrates how long it is worth trying to find out.

As work progresses, leadership sees two streams of evidence accumulating week
by week. The first is evidence about whether the initiative is strategically
sound. The second is evidence about whether execution is tracking to plan.
Both are imperfect — they reflect the underlying truth plus noise — and
leadership’s job is to form the best possible judgment from what they can see.

### How the organization updates its beliefs

The model tracks two separate running estimates for each initiative: how
strategically promising it appears to be (the organization’s current best
guess about its true quality), and how well execution is tracking relative
to the original plan.

The strategic estimate updates week by week as new evidence comes in. The
update is weighted: how much the new signal moves the estimate depends on
how noisy the signal is, how dependent the initiative is on factors outside
the team’s control, how recently the team was assigned (new teams need a
ramp-up period), and how much executive attention the initiative is receiving.

The execution estimate updates separately, in a simpler way — it adjusts
toward what the observed progress implies about how long the initiative will
actually take, independent of how much executive attention it is receiving.

Leadership never sees the underlying truth. They see only these two running
estimates, along with how long the initiative has been running, how many times
it has been reviewed, and whether it has persistently fallen below threshold
on recent evaluations.

**One important limitation:** leadership’s current belief is a single number.
The model does not track how confident that estimate should be based on how
much evidence underlies it. A belief of 0.6 based on two weeks of noisy data
looks identical to a belief of 0.6 based on two years of consistent signals.
This is a known simplification.

-----

## What governance controls

The study distinguishes three layers of what is chosen versus what is given.

|Layer                       |What belongs here                                                                                                                                                                                     |Who controls it                                          |
|----------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------|
|**The environment**         |The pool of available initiatives, their underlying quality, how long they actually take, how uncertain they are, how large their potential upside is, the total labor available, the six-year horizon|Fixed before the run — governance must take this as given|
|**Organizational structure**|How the total workforce is divided into teams, what portfolio guardrails are set (diversification targets, concentration limits), how the organization is architected before the run begins           |Chosen before the run starts; held fixed within the run  |
|**Operating governance**    |Which initiatives to continue or stop each week, how much executive attention to give each initiative, which teams to assign or reassign                                                              |Chosen by the governance regime each week                |

The study’s primary experiment varies **operating governance** while holding
the environment and organizational structure constant. This isolates the effect
of governance decisions from the effect of having a better opportunity pool or
a different organizational design.

### What governance can do each week

At the end of each week, governance makes three types of decisions that take
effect the following week:

- **Continue or stop** each active initiative. Stopping an initiative frees
  its team immediately but forfeits all future value from that initiative —
  including any residual stream it might have activated and any major win it
  might have surfaced. There are no partial credits.
- **Allocate executive attention** across active initiatives. This is a
  genuinely scarce resource. Attention given to one initiative is unavailable
  for another, and the model enforces a hard weekly budget.
- **Assign teams** to unassigned initiatives from the available pool.
  The simulation never auto-assigns teams — governance silence means an
  initiative sits unstaffed.

### When governance stops an initiative

The model allows governance to stop an initiative for four distinct reasons,
each representing a different governance philosophy:

1. **Strategic conviction has dropped below threshold.** The organization’s
   current belief about the initiative’s quality has fallen low enough that
   continued investment is no longer justified.
1. **The bounded opportunity looks too small relative to the investment.**
   For initiatives where leadership can see a ceiling on potential value,
   governance tracks whether the expected payoff — given current confidence
   in the initiative’s quality — has persistently fallen below a threshold
   relative to that ceiling. If it has, across enough consecutive reviews,
   governance terminates. Larger visible opportunities earn more patience
   before this trigger fires; smaller ones earn less.
1. **The initiative has stopped generating new information.** If the
   organization’s belief has not meaningfully shifted over a sustained
   window of active work, and the initiative has not otherwise earned
   continued patience, governance terminates.
1. **Execution has overrun badly enough to trigger a cost-based stop.**
   If the organization’s estimate of actual completion time has deteriorated
   far enough below the original plan, governance may stop even if strategic
   conviction remains high. Whether to apply this rule, and how strictly, is
   itself a governance choice — regimes differ in their cost-overrun tolerance.

-----

## Experimental design: making the comparison fair

The study compares governance regimes using a technique called common random
numbers. Every governance regime being compared faces exactly the same
simulated world: the same pool of initiatives, the same underlying quality
values, the same execution difficulties, the same sequence of noisy signals
week by week. The only thing that differs is how governance responds to what
it observes.

This is the simulation equivalent of a controlled experiment. Without it,
a governance regime that happened to face a better opportunity pool would
look superior even if its decision-making was worse. Common random numbers
eliminates that confound.

The implementation is careful. Each initiative has its own dedicated random
stream for strategic signals and a separate stream for execution signals, both
seeded from the world configuration. This means governance decisions about
one initiative — whether to stop it, staff it, or ignore it — cannot
accidentally change the signals that a different initiative produces. Two
regimes that make different decisions about initiative A still see identical
signals from initiative B. The comparison reflects governance differences,
not sampling differences.

**Divergence after the starting point is intentional.** Regimes begin from
identical conditions but are expected to evolve differently. A patient regime
and an impatient one will complete different initiatives, build different
residual streams, and accumulate different organizational capability over time.
That divergence is exactly what the study is designed to observe and measure.

-----

## Calibration: how the model parameters were grounded

A simulation is only as useful as its parameters are plausible. The study
uses three levels of empirical grounding depending on what evidence is
available.

**Level 1 — Grounded in external evidence (breakthrough incidence and
initiative duration).**

The most important parameters are how often exploratory initiatives turn out
to be genuinely transformational, and how long they take. These were grounded
by triangulating three independent evidence sources: research on new-business
creation in large incumbent firms, evidence on corporate venturing outcomes,
and analogues from domains where long-shot hit rates can be measured directly.
The evidence consistently supports a major-win rate of roughly 0.3%–4% among
completed exploratory initiatives, and duration-to-stable-resolution of
roughly 3–10 years.

Rather than picking a single point estimate, the study defines three named
organizational environments that span this range: a mid-case incumbent
environment, a scarcer-wins environment, and a richer-wins environment.
Findings that hold across all three are more robust than findings that hold
in only one.

An early version of the model had a calibration failure: the parameters for
breakthrough incidence were set in a way that made major wins essentially
impossible — the threshold was so demanding that no initiative in a realistic
pool could ever reach it. Sixty-three simulation runs produced zero major wins
across all governance regimes. That was a model failure, not a governance
finding. It was diagnosed and corrected before any comparative analysis
was conducted. The current parameters produce major-win rates of 1–8%
depending on the environment, consistent with the external evidence.

**Level 2 — Grounded in structural logic (flywheel, enabler, quick-win
parameters).**

The parameters for non-exploratory initiative types — how uncertain they are,
how long they take, what kind of value they produce — are set to reflect the
structural taxonomy rather than fitted to external data. Flywheels are
designed to be high-quality with persistent returns. Quick wins are designed
to be fast and bounded. Enablers are designed to contribute capability rather
than direct value. These are reasonable archetypes, and because the study
produces relative comparisons (regime A vs. regime B in the same environment),
the absolute parameter values matter less than getting the structural
relationships between types approximately right.

**Level 3 — Structural assumption (how executive attention affects signal
quality).**

The shape of the relationship between executive attention and signal clarity
is a modeling assumption rather than an empirically calibrated value. The
basic structure — that too little attention actively degrades signal quality,
and more attention above a threshold improves it with diminishing returns —
is grounded in organizational behavior intuition. But the specific shape of
that curve is not fitted to data. This is the weakest part of the calibration,
and the study plans to test how sensitive findings are to this assumption by
varying it systematically.

The comparative structure of the study reduces the risk from calibration
uncertainty. Errors that affect all governance regimes equally do not distort
the comparison between them. What matters is whether the structural
relationships are approximately right, not whether the absolute numbers match
a specific organization.

-----

## Known limitations

1. **Execution slippage is easier to observe in the model than in reality.**
   The model assumes that how well an initiative is tracking to plan can always
   be read from elapsed time and observable milestones, regardless of how much
   attention leadership is paying. In real organizations, exactly the opposite
   is often true: schedule slips go undetected until they are severe precisely
   because leadership is not paying close attention. Governance regimes that
   stop initiatives for cost overruns will therefore look somewhat more
   effective in the model than they would in practice.
1. **Leadership cannot tell how confident their estimates should be.**
   The model tracks a running belief about each initiative’s quality, but not
   how much evidence underlies that belief. A belief based on two weeks of
   noisy data looks identical to one based on two years of consistent signals.
   In practice, leaders do have some sense of how well-understood an
   initiative is; the model simplifies this away.
1. **Beliefs are slightly biased near the extremes.** The way the model
   updates beliefs means that very high-quality initiatives are slightly
   undervalued at equilibrium, and on-plan initiatives tend to show small
   projected overruns even when they are genuinely on track. Both effects are
   symmetric across governance regimes and do not distort the comparison
   between them, but they are worth knowing about.
1. **The parameters for non-exploratory initiatives are archetypes, not
   empirical fits.** The model’s flywheel, enabler, and quick-win parameters
   were set to faithfully represent the defining structural characteristics of
   each type rather than fitted to external data. Flywheels are parameterized
   to be high-quality with persistent compounding returns. Quick wins are
   parameterized to be fast, bounded, and low-uncertainty. Enablers are
   parameterized to contribute capability rather than direct value. These are
   deliberate design choices grounded in the conceptual taxonomy, not
   arbitrary numbers.

   The reason this does not undermine the study’s comparative findings is that
   every governance regime faces the same parameters. If the flywheel
   parameters are somewhat off, every regime faces the same somewhat-off
   flywheels. What would distort findings is not imprecise absolute values but
   structurally wrong relationships — for instance, if flywheels were
   accidentally parameterized to behave like quick wins. Those structural
   relationships were set deliberately and are easy to audit.

   The practical implication is that the absolute scale of value in the
   simulation output cannot be read as a claim about any specific organization’s
   numbers. The study does not say “your flywheels are worth X dollars.” What
   it does say is how governance choices affect the relative accumulation of
   lump value, residual streams, major-win discoveries, and organizational
   capability — and those relative findings are robust to reasonable variation
   in the absolute parameter values.
1. **A track record of killing things early does not discourage future
   proposals in the model.** In real organizations, a governance culture that
   consistently terminates speculative work early will gradually receive fewer
   ambitious proposals — people learn not to bring them. The model does not
   represent this feedback loop. Findings about aggressive stop-loss governance
   therefore likely understate its real organizational cost.

-----

## What the study is designed to learn

The simulation is designed to reveal the structural logic underneath several
practical governance questions that are difficult to study empirically:

- What does a governance regime give up when it consistently favors
  quick, predictable returns over slower, compounding work?
- How much does the breadth versus depth of executive attention matter — and
  does the answer change depending on what kind of opportunity environment
  the organization is operating in?
- Where is the inflection point between organizational patience and resource
  efficiency? When does staying the course stop being discipline and start
  being waste?
- Are governance conclusions robust across different kinds of organizational
  environments — ones with more or fewer transformational opportunities, with
  faster or slower initiative cycles — or are they artifacts of a particular
  set of conditions?
- To what degree do stop decisions get corrupted by the attention allocation
  that preceded them? If leadership paid too little attention to an initiative
  early on, its belief estimate will be noisier and more likely to trigger a
  stop — even if the underlying initiative was actually worth pursuing.

The goal is not to declare one governance approach universally superior. It is
to reveal the conditions under which different approaches create different
strengths, weaknesses, and tradeoffs — so that leaders can recognize those
dynamics in their own organizations and make better-informed decisions about
where to invest the two things they can never recover: their people’s time
and their own.
