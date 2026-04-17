# Primordial Soup design decisions and tradeoffs

## Role of this document


### Academic
This document is the durable home for the major design decisions, tradeoffs, and
rationale behind the canonical Primordial Soup study.

It is not the source of truth for simulator mechanics, equations, schemas, tick
ordering, or interface contracts. Those belong in the technical documents. It is
also not a temporary checkpoint artifact. Its purpose is to preserve the
institutional memory of why the canonical design took its current form, so that
future revisions can distinguish deliberate simplifications from accidental
omissions.

Use this document when a future reader asks questions such as:

- Why was this modeling choice made rather than a nearby alternative?
- Which alternatives were considered and rejected?
- Which simplifications are load-bearing for the study's interpretability?
- Which issues are genuinely open research extensions versus already-settled
  canonical choices?

The intended pattern across the corpus is:

- `study_overview.md` explains what the study is about.
- The technical docs explain how the study is implemented.
- This document explains why the major canonical choices were made — the
  reasoning, the tradeoffs, and the alternatives that were considered and
  rejected.

---

### Business
This document is the permanent record of why the major design choices behind the Primordial Soup study were made the way they were.

It is not the place to look for how the simulation works mechanically — what calculations run in what order, what data flows where, or how the technical contracts are structured. Those details live in the technical documents. Nor is it a status update or a working artifact that will be replaced. Its purpose is to preserve the reasoning behind the study's design so that anyone who comes to this project later can tell the difference between a deliberate simplification and an accidental gap.

This is the document to consult when a future reader asks questions like:

- Why was this particular approach chosen when there were other reasonable options?
- What alternatives were considered and why were they set aside?
- Which simplifications are load-bearing — meaning, which ones are part of what makes the study's conclusions trustworthy and interpretable, rather than just shortcuts?
- Which questions are genuinely open for future work versus already settled by design?

The three core documents of the study serve different purposes:

- The study overview explains what the study is about — the organizational phenomena it investigates, the practitioner-relevant interpretation, and the simplifying assumptions it makes deliberately.
- The technical documents explain how the study is implemented — the precise mechanics, data structures, and computational contracts.
- This document explains why the major design choices were made — the reasoning, the tradeoffs, and the alternatives that were considered and rejected.

---

## How to read these decisions


### Academic
The canonical study is intentionally a reduced-form model of governance, not a
maximally realistic organization simulator. This is a methodological choice, not
a concession. A high-fidelity organization simulator with many interacting
subsystems would make it difficult to attribute variation in outcomes to the
treatment variable — governance policy — rather than to confounding interactions
among auxiliary model components. Reduced-form design preserves identification.

Many decisions below therefore have
the same structure:

1. preserve the phenomenon the study is trying to learn about,
2. keep the simulator implementable and auditable,
3. avoid hidden state or ambiguous semantics,
4. make outputs answer the stated research questions without excessive
   reconstruction,
5. keep major extensions available for future work rather than overfitting the
   base study.

Where a choice was made mainly for tractability, this document says so
explicitly. Where a choice reflects a substantive view about governance, this
document says that too. The reader should always be able to tell which kind of
decision they are looking at.

---

### Business
The study is deliberately a simplified model of governance, not a maximally realistic organization simulator. That is a feature, not a limitation. An organization simulator that tried to capture everything would be so complex that its results would be nearly impossible to interpret — you could never tell whether a finding was driven by the governance variable you were studying or by an interaction among dozens of other moving parts.

The decisions below therefore follow a consistent logic:

1. Preserve the organizational phenomenon the study is designed to reveal — the thing we are actually trying to learn about governance.
2. Keep the model simple enough to build correctly and audit completely.
3. Avoid hidden assumptions or ambiguous rules that could silently shape results.
4. Make the outputs directly answer the study's research questions without requiring analysts to reconstruct critical information after the fact.
5. Keep the door open for future extensions rather than building in complexity that belongs in later versions of the work.

Where a choice was made primarily to keep the study tractable, this document says so explicitly. Where a choice reflects a substantive view about how governance actually works in organizations, this document says that too. The reader should always be able to tell which kind of decision they are looking at.

---

## 1. Why the study uses a two-level authority structure


### Academic
#### Decision

The corpus uses a two-level authority structure:

- `study_overview.md` is authoritative about the phenomena in scope, the
  practitioner-facing interpretation, and the deliberate simplifying assumptions.
- The technical docs are authoritative about operational semantics: state,
  equations, timing, schemas, and action contracts.

#### Why this choice was made

This split exists to prevent two opposite failure modes.

If conceptual intent is mixed directly into implementation detail everywhere, the
model becomes difficult to audit because the same idea is restated in multiple
places at different levels of abstraction. But if the overview is too thin, then
the technical docs can become internally precise while drifting away from the
actual governance phenomena the study meant to represent.

The two-level structure keeps the overview focused on what the study is trying to
say about organizations, while keeping the technical layer precise enough for
implementation. It also makes disagreements easier to resolve: if a mechanism is
technically precise but conceptually wrong, the repair is to make the technical
layer implement the intended phenomenon more faithfully rather than to let the
overview become a pseudo-code document.

#### Alternative rejected

A single-document design spec was rejected because it would either become too
abstract to implement safely or too operational to remain readable as a
conceptual statement of the study.

---

### Business
#### Decision

The study's documentation is organized into two levels of authority:

- The study overview is authoritative about what organizational phenomena are in scope, how the findings should be interpreted in practitioner terms, and which simplifications were made deliberately.
- The technical documents are authoritative about the precise mechanics: the state tracked, the calculations performed, the timing of events, the data contracts, and the rules governing governance actions.

#### Why this choice was made

This split exists to prevent two opposite failure modes that are common in complex projects.

The first failure mode is mixing strategic intent into technical detail everywhere. When the "why" is scattered across dozens of technical specifications, it becomes very difficult to audit the study because the same idea is restated in multiple places at different levels of precision. You cannot tell whether two slightly different phrasings represent the same concept or a genuine disagreement.

The second failure mode is the opposite: making the strategic overview too thin. When the conceptual document is sparse, the technical specifications can become internally precise and self-consistent while gradually drifting away from the organizational phenomena the study was actually meant to investigate. The technical layer becomes a well-built machine that no longer points at the right question.

The two-level structure keeps the overview focused on what the study is trying to say about organizations, while keeping the technical layer precise enough for correct implementation. It also makes disagreements easier to resolve. If a mechanism is technically precise but does not faithfully represent the intended organizational phenomenon, the fix is to revise the technical layer to better implement the intended concept — not to let the overview degrade into an implementation document.

#### Alternative rejected

A single combined document was rejected because it would inevitably become either too abstract to implement from or too technical to serve as a clear statement of what the study is about. These are two different jobs, and trying to do both in one place means doing neither well.

---

## 2. Why initiative labels are explanatory, not causal


### Academic
#### Decision

The four initiative families — flywheel, right-tail, enabler, and quick win —
are used for initialization, generation, and reporting, but engine behavior is
defined in terms of resolved attributes and canonical mechanisms rather than the
label itself.

#### Why this choice was made

The study is trying to represent different payoff structures and learning
dynamics, not claim that real organizations can always correctly classify work at
intake. By making labels generator-side and explanatory, the model preserves the
usefulness of recognizable practitioner categories without making the engine
depend on a potentially fragile surface taxonomy.

This also reduces the risk of stale semantics. If the engine were keyed directly
to human labels, every refinement to the conceptual taxonomy would risk breaking
mechanics. By instead operationalizing the model through resolved initiative
attributes, the simulation stays stable even if later work refines or expands the
descriptive labels.

The engine operates on resolved characteristics — uncertainty, duration, value
mechanism, signal behavior — not on the label string. This means the label
classification does not need to be correct for the engine to behave correctly,
which is important given that ex-ante classification of initiative type is often
ambiguous in practice and in the model's own generation process.

#### Alternative rejected

Making the engine branch directly on initiative type was rejected because it
would hard-code a surface classification into the mechanics and make the study
more brittle than necessary.

---

### Business
#### Decision

The four initiative types — flywheel, right-tail, enabler, and quick win — are used for setting up the portfolio, generating realistic initiative characteristics, and reporting results. But the simulation engine itself operates entirely on the resolved attributes of each initiative — its uncertainty, duration, value mechanism, and other characteristics — not on the label.

#### Why this choice was made

The study is trying to represent different value-creation structures and learning dynamics, not to claim that real organizations can always correctly classify their work at intake. In practice, the line between a flywheel and a right-tail bet is often unclear at the moment of investment. A corporate venture that looks like an exploratory moonshot may turn out to be a steady compounding business. An automation initiative that looks like a quick win may reveal itself as a deep capability enabler.

By making labels descriptive rather than mechanically controlling, the model preserves the usefulness of recognizable categories — leaders do think in terms of "this is a quick win" or "this is a long-term bet" — without making the simulation dependent on getting that classification perfectly right. The engine does not care what you call an initiative. It cares about its actual characteristics: how uncertain it is, how long it takes, what kind of value it produces, and how its signals behave.

This also protects the study from a common failure in organizational taxonomy. If the simulation engine were wired directly to the type labels, then every time the conceptual framework was refined — splitting a category, combining two categories, adding a new one — the entire engine would need to be reworked. By operating on resolved attributes instead, the simulation remains stable even as the descriptive vocabulary evolves.

#### Alternative rejected

Making the engine behave differently based on initiative type labels was rejected because it would hard-code a surface-level classification into the core mechanics, making the study more fragile than necessary and implying a false precision about how well organizations can categorize their work at inception.

---

## 3. Why economically meaningful effects are completion-gated


### Academic
#### Decision

In the canonical study, economically meaningful effects are completion-gated.
Work in progress produces signals and consumes resources, but value is realized
only at completion through one-time lump value, residual activation, major-win
surfacing, or capability gain.

#### Why this choice was made

This is a deliberate simplification to keep the value semantics crisp and the
engine unambiguous. Many real initiatives produce partial value before formal
completion, but allowing in-flight value realization would create a large number
of partial-credit edge cases:

- what share of the value is recoverable if an initiative is stopped near the end,
- whether residual mechanisms activate gradually or discretely,
- how partial completion interacts with reassignment and pause states,
- how to compare near-complete work with earlier-stage work in stop logic.

Each of these is a legitimate modeling question, but none is what the canonical
study is about. The canonical study is about governance under uncertainty, not about fine-grained
project accounting. Completion-gated value therefore keeps the study focused on
the governance question rather than on valuation conventions for partially
finished work.

#### Cost of this choice

Stopping one tick before completion is more all-or-nothing in the model than in
many real organizations. That is a real limitation and should be acknowledged in
any write-up.

More specifically, the model overstates the cost of a late-stage stop and
understates the cost of an early-stage one, relative to a counterfactual in which
partial value is recoverable. The directional bias is symmetric across governance
regimes and does not distort comparative findings, but it does affect the
absolute magnitude of stop-related costs in the output.

---

### Business
#### Decision

In the study, all economically meaningful effects are gated on completion. Work in progress generates signals and consumes resources, but no value is realized until an initiative reaches completion — whether that value takes the form of a one-time payoff, activation of an ongoing return stream, surfacing of a major-win discovery, or a gain in organizational capability.

#### Why this choice was made

This is a deliberate simplification to keep the value accounting clean and unambiguous. In reality, many initiatives produce partial value before formal completion — a half-built distribution network still distributes some things, a partially automated process still saves some labor. But allowing in-flight value realization would create a large number of partial-credit judgment calls that have nothing to do with the governance question the study is designed to answer:

- What share of the value is recoverable if an initiative is stopped at 80% completion versus 40%?
- Do ongoing return mechanisms activate gradually as work progresses, or only at the point of completion?
- How does partial completion interact with team reassignment — does an initiative that is paused at 90% retain the value it has generated so far?
- How should governance compare near-complete work with early-stage work when deciding what to stop?

Each of these is a legitimate question about project economics, but none of them is what this study is about. The study is about governance under uncertainty — how different governance approaches affect the organization's ability to discover, persist with, and complete the right mix of work. Completion-gated value keeps the study squarely focused on that question rather than on the accounting conventions for partially finished projects.

#### Cost of this choice

This means that stopping an initiative one week before it would have completed looks the same in the model as stopping it on day one — all investment is lost. That is more all-or-nothing than what most organizations actually experience, and it should be acknowledged in any interpretation of the results. The practical implication is that the model slightly overstates the cost of a late-stage stop and slightly understates the cost of an early-stage one, relative to a world where partial value is recoverable.

---

## 4. Why capability is represented as a single portfolio-level scalar


### Academic
#### Decision

Enabler initiatives increase a single portfolio-level capability state that
reduces effective strategic signal noise for future staffed initiatives.

#### Why this choice was made

This is a reduced-form representation of a family of real organizational
improvements: experimentation infrastructure, dependency reduction, DevOps,
decision quality, measurement systems, and related enablers. The canonical study
is trying to answer whether governance systematically underinvests in
capability-building work at all. It is not trying to separately model every
mechanism through which such work helps.

A one-stock representation keeps enablers measurable and consequential without
exploding the model into many subtype-specific state variables whose interactions
would be difficult to validate and interpret. It also preserves the conceptual
point emphasized by the Deming framing: much of organizational performance is a
property of the system rather than of isolated initiatives.

The single-stock `C_t` enters `σ_eff` as a divisor, so its effect is global: an
organization that has completed several enablers evaluates its entire active
portfolio with less noise simultaneously. This is a deliberate modeling choice —
capability is a system-level property, not an initiative-local one.

#### Alternative rejected

Multiple distinct enabler stocks were rejected for the canonical study because
they would add realism at the cost of tractability and interpretability before
the base governance questions had been answered. If the base study finds that
governance systematically underinvests in capability-building work, future
extensions can decompose which dimensions of capability matter most. That
question only becomes meaningful after the base finding is established.

---

### Business
#### Decision

When enabler initiatives are completed, they increase a single organization-wide capability measure that improves the quality of information the organization receives about all future active initiatives.

#### Why this choice was made

This is a simplified representation of a broad family of real organizational investments: experimentation platforms, data and analytics infrastructure, DevOps pipelines, dependency reduction between teams, measurement systems, process improvements that speed up piloting, and similar enablers. All of these share a common structural property — they make the organization better at evaluating and learning from its portfolio of work — even though they operate through very different mechanisms.

The central question the study is designed to answer about enablers is whether governance systematically underinvests in this kind of work. It is not trying to separately model every channel through which capability-building helps. A single-stock representation keeps enablers measurable and consequential in the simulation without requiring a separate state variable for every type of organizational improvement, each with its own interactions that would be difficult to validate and nearly impossible to interpret clearly.

This approach also preserves an important conceptual point: much of organizational performance is a property of the system as a whole rather than a property of any individual initiative. An organization that has invested in its evaluation infrastructure makes better decisions across its entire portfolio, not just on the specific initiative that prompted the investment. A single capability measure captures this system-level property directly.

#### Alternative rejected

Tracking multiple distinct types of organizational capability — separate measures for, say, experimentation infrastructure, decision-support quality, and execution visibility — was rejected for the initial study because it would add substantial complexity before the basic governance question had been answered. If the study finds that governance systematically underinvests in capability-building work, future extensions can explore which dimensions of capability matter most. But that question only becomes meaningful after the base finding is established.

---

## 5. Why residual value and capability both decay over time


### Academic
#### Decision

Residual effects and capability/enabler effects are both durable but not
permanent. In the canonical study, both decay exponentially over time.

Residual effects use initiative-local decay parameters.
Capability uses a model-level decay parameter.

The two mechanisms share the same functional family, but not the same parameter
value.

#### Why this choice was made

Conceptually, both mechanisms represent organizational advantage that erodes if
it is not renewed.

- A flywheel loses momentum through friction.
- A process improvement drifts as the organization changes.
- Dependency reduction helps, but new dependencies slowly accumulate.

The choice of exponential decay reflects gradual proportional erosion rather than
an abrupt cliff. It is also conservative from an implementation standpoint:
simple to express, easy to audit, and easy to reason about over long horizons.

Using the same functional family for both residual value and capability creates a
single modeling language for erosion over time. Using separate parameters avoids
the false claim that initiative-local tails and organization-level capability
must erode at the same speed.

#### Alternatives rejected

Hard-cutoff horizons were rejected as the canonical default because they imply
that an advantage remains fully intact until a threshold and then vanishes
suddenly, which did not match the intended organizational story.

Using one shared decay rate for both residual and capability was rejected because
there is no substantive reason they should erode at the same pace.

Using different decay families for the two mechanisms was rejected because it
would add complexity without improving the study's central governance logic.

---

### Business
#### Decision

Both ongoing value streams from completed initiatives and organizational capability improvements are durable but not permanent. Both erode gradually over time in the model.

Ongoing value streams erode at rates specific to each initiative. Organizational capability erodes at a single rate that applies across the portfolio.

The two use the same type of gradual decay — proportional erosion over time — but at different speeds.

#### Why this choice was made

Both mechanisms represent organizational advantages that deteriorate if they are not renewed. This is a basic fact of organizational life:

- A distribution network that was a powerful competitive advantage five years ago gradually loses its edge as competitors build their own and as the market evolves.
- An automation system that dramatically reduced costs when it was built slowly becomes less effective as the processes around it change, as the technology ages, and as new requirements emerge.
- A process improvement that transformed decision quality when it was introduced drifts as the organization changes, as the people who championed it move on, and as new dependencies accumulate.

The choice of gradual proportional erosion — rather than a sudden cliff — reflects how organizational advantage actually fades. A flywheel does not operate at full strength for exactly five years and then stop overnight. It loses a small fraction of its effectiveness each period, so that an advantage built three years ago is weaker than one built last year but still meaningfully present.

Using the same type of erosion for both ongoing value streams and organizational capability creates a consistent language for how advantages fade over time. Using different speeds for the two avoids the false claim that initiative-level returns and organization-level learning improvements must erode at the same pace — there is no reason to assume they do.

#### Alternatives rejected

A hard cutoff — where advantages remain fully intact for a fixed period and then vanish completely — was rejected because it does not match how organizational advantages actually erode. It would create an artificial cliff that has no real-world analogue.

Using a single shared erosion rate for both ongoing value and capability was rejected because there is no substantive reason they should fade at the same speed. A completed automation initiative and a completed enabler investment face very different forces of organizational entropy.

Using different mathematical forms of erosion for the two mechanisms was rejected because it would add complexity to the model without improving its ability to answer the governance questions the study is designed to investigate.

---

## 6. Why capability decays on excess stock above baseline


### Academic
#### Decision

Capability decay is applied only to the excess capability stock above the
baseline level of `1.0`, not to the baseline itself.

#### Why this choice was made

The baseline capability level represents ordinary organizational functioning, not
a special advantage earned by enabler work. What should erode over time is the
accumulated improvement above that baseline.

If the entire capability stock decayed toward zero, the model would imply that an
organization can lose its baseline ability to observe and reason about work
entirely, which is not the intended interpretation. The study is about building
and losing marginal organizational advantage, not about the existence of
organizational cognition as such.

Formally, this means the decay equation operates on `(C_t - 1.0)` rather than on
`C_t`, so `C_t` has a floor at `1.0` even under sustained decay with no new
enabler completions.

---

### Business
#### Decision

Capability erosion applies only to the accumulated improvement above the organization's baseline functioning level, not to the baseline itself.

#### Why this choice was made

The baseline capability level represents the organization's ordinary ability to evaluate and reason about its work — the default state of organizational cognition before any enabler investments have been made. What erodes over time is the accumulated improvement above that baseline: the additional precision, speed, and clarity that completed enabler work has created.

If the entire capability stock could erode toward zero, the model would imply that an organization can lose its fundamental ability to observe and assess its own work — that it can literally forget how to evaluate initiatives at even a basic level. That is not the phenomenon the study is investigating. The study is about building and losing marginal organizational advantage through deliberate investment — the difference between an organization that has invested heavily in its evaluation infrastructure and one that has not — not about whether organizations can function at all.

---

## 7. Why existing capability decays before new completion gains are added


### Academic
#### Decision

On a tick where enablers complete, existing capability advantage decays first,
then new completion gains are added, producing the next-tick capability state.

#### Why this choice was made

This update order avoids the awkward semantics in which newly earned enabler
gains are immediately penalized before they ever take effect.

The intended story is:

- older accumulated advantage erodes with time,
- newly completed enabler work creates fresh advantage,
- that new advantage is fully present when it first becomes operative on the next
  tick.

This ordering is both more natural conceptually and easier to defend to a reader
who is reasoning about organizational improvements in calendar time.

To see why the ordering matters concretely: under the rejected alternative (add
then decay), a capability gain `δ` earned at tick `t` would enter the next-tick
state as `δ × (1 - λ_cap)` rather than `δ`, because the decay step would
immediately erode it. The organization would never observe the full magnitude of
its most recent enabler completion. Under the canonical ordering (decay then
add), `δ` enters at full strength and first experiences decay at the end of tick
`t+1`.

---

### Business
#### Decision

In any period where enabler initiatives complete, existing capability advantage erodes first, and then the newly completed enabler gains are added. This determines the capability level that takes effect for the next period.

#### Why this choice was made

This ordering avoids a counterintuitive result in which newly completed enabler work is immediately penalized by erosion before it ever takes effect. Consider the alternative: if new gains were added first and then erosion applied to the total, an enabler initiative that completes this week would arrive already partially degraded next week. That would mean the organization never receives the full benefit of its most recent capability investment, which does not match how organizational improvements work in practice.

The intended logic is straightforward:

- Older accumulated advantages erode with the passage of time, just as they do in any organization.
- Newly completed enabler work creates fresh advantage.
- That new advantage is fully present when it first becomes operative the following week.

This ordering is both more natural when reasoning about organizational investment in calendar time and easier to explain to a reader who thinks in terms of "we just finished building this — it should be at full strength when we start using it."

---

## 8. Why the default strategic prior is 0.5


### Academic
#### Decision

The canonical default prior for strategic belief is `initial_belief_c0 = 0.5`,
implemented through a schema-level default.

#### Why this choice was made

`0.5` is the neutral symmetric baseline in the bounded belief space. It keeps
early stop/continue behavior from being pre-biased toward optimism or pessimism
before any initiative-specific evidence has been observed.

This matters because the study compares governance regimes partly through how
they respond to early uncertainty. If the canonical baseline started with an
optimistic or pessimistic prior, that choice would silently shape the apparent
aggressiveness or patience of all regimes.

The mechanism is specific: an optimistic prior `c_0 > 0.5` would increase the
number of negative observations required for belief to cross a downward stop
threshold, inflating the apparent patience of every regime under study. A
pessimistic prior `c_0 < 0.5` would reduce it, inflating apparent aggressiveness.
Either direction confounds the measurement of the governance treatment effect
with a hidden initial-conditions effect.

A neutral midpoint ensures that the study's findings about governance patience
and aggressiveness reflect the actual governance policies being tested, not a
hidden assumption baked into the initial conditions.

Systematic intake optimism or pessimism is still meaningful to study, but it
belongs in sensitivity analysis rather than in the canonical baseline. The
baseline should be neutral so that departures from neutrality can be studied as
deliberate experimental variables.

#### Alternative rejected

Leaving the default as a vague "runner-configured value" was rejected because it
creates ambiguity exactly where the study needs a neutral, shared baseline. If
different runs start with different priors and this is not carefully controlled,
variation in outcomes cannot be cleanly attributed to governance policy versus
initial-conditions differences.

---

### Business
#### Decision

Every initiative enters the portfolio with a neutral starting belief about its strategic quality — the organization's initial assessment is neither optimistic nor pessimistic, sitting at the exact midpoint of the scale.

#### Why this choice was made

This neutral starting point prevents the study from silently biasing every governance regime toward early action or early inaction before any initiative-specific evidence has been collected.

This matters directly for the study's core comparisons. The study evaluates governance regimes partly through how they respond to early-stage uncertainty — how patient or impatient they are in the first weeks of an initiative's life, before much evidence has accumulated. If every initiative started with an optimistic prior (say, "we believe this is probably good"), then all governance regimes would appear more patient than they actually are, because they would need more negative evidence before triggering a stop. If every initiative started with a pessimistic prior, all regimes would appear more aggressive. Either way, the baseline assumption would silently shape the apparent character of every governance regime in the study.

A neutral midpoint ensures that the study's findings about governance patience and aggressiveness reflect the actual governance policies being tested, not a hidden assumption baked into the initial conditions.

Systematic intake optimism — the tendency of some organizations to assume new initiatives are better than they turn out to be — and systematic intake pessimism are both real organizational phenomena worth studying. But they belong in sensitivity analysis (varying the starting belief to see how it changes results) rather than in the baseline design. The baseline should be neutral so that departures from neutrality can be studied as the deliberate variables they are.

#### Alternative rejected

Leaving the starting belief as an unspecified value to be set differently in each simulation run was rejected because it creates ambiguity exactly where the study needs a shared, neutral reference point. If different runs start with different priors and this is not carefully controlled, it becomes impossible to tell whether differences in outcomes reflect differences in governance or differences in starting assumptions.

---

## 9. Why attention omission means zero, not persistence


### Academic
#### Decision

If a policy omits an initiative from the attention map on a tick, that
initiative's attention on that tick is exactly `0.0`. Prior attention does not
persist.

#### Why this choice was made

This makes the policy output a complete statement of governance intent for the
tick. It keeps the simulator from owning hidden attention state and avoids a
subtle failure mode where a policy accidentally continues to influence an
initiative by forgetting to mention it.

The failure mode is worth specifying. Under persistent attention, an initiative
that the policy has mentally deprioritized but not explicitly zeroed would
continue receiving its prior attention level, potentially for many ticks. The
signals it produces would continue to benefit from that attention — `σ_eff` would
remain lower than intended — and downstream belief updates and stop decisions
would be based on higher-quality information than the policy actually intended to
invest in producing. The policy's actual information-allocation strategy would
diverge from its stated intent without any signal in the output.

This is both a technical and conceptual choice. Technically, it simplifies the
engine and the reporting layer. Conceptually, it matches the idea that executive
attention is an actively allocated resource, not a sticky property that stays in
place unless explicitly revoked.

#### Alternative rejected

Persistent attention state was rejected because it is harder to reason about,
harder to audit, and easier to mis-specify in ways that produce accidental policy
behavior. It would also obscure a finding the study is designed to surface: the
consequences of attention gaps and inconsistency in governance engagement.

---

### Business
#### Decision

If governance does not actively allocate executive attention to an initiative in a given week, that initiative receives exactly zero attention that week. Attention from the previous week does not carry over automatically.

#### Why this choice was made

This makes governance's weekly decisions a complete and self-contained statement of intent. Every week, the attention allocation starts from a blank slate. If an initiative appears on the list, it receives the specified level of attention. If it does not appear, it receives none. There is no hidden momentum or inertia in the system.

This prevents a subtle but consequential failure mode: a governance regime that accidentally continues to influence an initiative simply by failing to explicitly remove it from the attention list. Under persistent attention, an initiative that leadership has mentally deprioritized but not formally dropped would continue receiving the same level of engagement as the previous week, potentially for many weeks. The signals it produces would continue to benefit from that engagement, and governance decisions about it would be based on better-quality information than the regime actually intended to invest in producing.

Conceptually, this matches the reality that executive attention is an actively allocated resource, not a sticky property that stays in place unless explicitly revoked. A CEO who decides to spend four hours this week on a particular initiative has made an active choice. If they do not make that choice next week — because they are traveling, or because other priorities have intervened, or because they simply forgot — the initiative does not continue receiving four hours of CEO time by default.

#### Alternative rejected

Persistent attention — where last week's allocation carries forward unless explicitly changed — was rejected because it is harder to reason about, harder to audit, and easier to mis-specify in ways that produce accidental governance behavior. It would also obscure a key finding the study is designed to surface: the consequences of attention gaps and inconsistency in governance engagement.

---

## 10. Why `attention_min` is required and non-null in the canonical study


### Academic
#### Decision

The canonical study requires a non-null `attention_min`.

#### Why this choice was made

The study makes a substantive claim about the attention-to-signal relationship:
below a minimum threshold, shallow positive attention makes things worse rather
than better. If that threshold were optional in the canonical study, the study
would no longer consistently instantiate the very mechanism it is trying to
investigate.

Requiring a non-null floor also resolves a technical awkwardness in the fallback
semantics. The model's rationale for falling back to the minimum attention level
after an infeasible allocation is that zero attention would produce artificial
signal collapse from a budgeting error rather than from intended governance. That
rationale only works cleanly if a nonzero meaningful floor actually exists.

#### Alternative rejected

Keeping `attention_min = None` as part of the canonical study was rejected
because it weakened both the conceptual interpretation of the attention curve and
the internal consistency of the fallback logic.

The no-floor case remains a possible sensitivity analysis, not part of the
baseline design.

---

### Business
#### Decision

The study requires that a minimum attention threshold be specified. This threshold cannot be set to zero or left undefined.

#### Why this choice was made

The study makes a substantive claim about how executive attention works in organizations: below a minimum threshold of engagement, shallow involvement makes the information environment worse, not just fails to improve it. An executive who skims a status report and asks one off-the-cuff question may actually make an initiative harder to evaluate than if leadership had stayed entirely uninvolved — because the half-formed engagement generates noise without generating insight, and the team may redirect effort toward managing upward rather than doing the work.

If the minimum attention threshold were optional in the baseline study, the study would no longer consistently test the very mechanism it is designed to investigate. The attention-to-signal relationship is one of the most consequential dynamics in the model. Making it optional in the canonical design would be like designing a study of drug effectiveness but making the drug dosage optional.

Requiring a defined minimum also resolves a practical issue in the model's fallback logic. When a governance regime specifies an attention allocation that turns out to be infeasible — perhaps because the total exceeds the available budget — the model falls back to the minimum threshold. The rationale for that fallback is that an initiative should not suffer from artificial information collapse just because of a budgeting error in the governance policy. That rationale only works if the minimum threshold is a meaningful, nonzero level of engagement.

#### Alternative rejected

Making the minimum threshold optional was rejected because it weakened both the study's ability to investigate the attention mechanism and the internal consistency of the fallback logic.

Testing what happens when there is no minimum threshold at all — where any amount of engagement, no matter how shallow, is assumed to be at least neutral — remains available as a sensitivity analysis. It is not part of the baseline design, where the minimum threshold is a load-bearing element of the study's core dynamics.

---

## 11. Why execution signals are not attention-modulated


### Academic
#### Decision

Executive attention affects the strategic signal path but not the execution
signal path.

#### Why this choice was made

The canonical distinction is that strategic quality is inferred indirectly and is
therefore highly sensitive to interpretation quality, whereas execution progress
is more directly observable through elapsed time, milestones, and delivery
signals.

This separation helps the study compare governance regimes that differ in how
they respond to strategic uncertainty versus execution overrun. If attention also
changed execution observability in the same way, the model would blur two
distinct governance problems:

- whether the idea is good,
- whether the execution is going according to plan.

Keeping the two signal paths separable in the model preserves the ability to
attribute governance outcomes to specific governance choices — whether a regime
succeeds or fails because of its strategic judgment versus its cost discipline.

#### Cost of this choice

In real organizations, low attention can delay recognition of schedule slips. The
model therefore gives execution-overrun-sensitive governance somewhat cleaner
execution information than many organizations actually have. Specifically,
schedule slippage that in practice might go undetected until severe is immediately
visible in the model regardless of leadership engagement. That should remain
visible as a limitation, and it implies that findings about the effectiveness of
cost-sensitive stopping rules likely represent an upper bound.

---

### Business
#### Decision

Executive attention affects the quality of strategic signals — the evidence about whether an initiative is fundamentally worth pursuing — but not the quality of execution signals — the evidence about whether the work is tracking to plan.

#### Why this choice was made

The reasoning reflects a real organizational distinction. Whether an initiative is strategically sound — whether the underlying idea is good, whether the market opportunity is real, whether the competitive position is defensible — requires judgment, interpretation, and the kind of deep engagement that executive attention provides. A leader who is closely involved in an initiative's strategic review process will form a more accurate picture of its quality than one who glances at a quarterly summary.

Whether execution is tracking to plan, by contrast, is more directly observable. Elapsed time, milestones delivered, budget consumed, headcount utilized — these are concrete, operational facts that do not depend on executive interpretation in the same way. A project that has burned 18 months of a 12-month plan is visibly behind schedule regardless of how much CEO attention it is receiving.

This separation is important for the study because it allows clean comparison of governance regimes that differ in how they respond to two fundamentally different governance problems: the problem of strategic uncertainty (is this the right thing to do?) and the problem of execution overrun (is this taking too long and costing too much?). If executive attention affected both signal paths in the same way, the model would blur these two problems together, making it harder to attribute governance outcomes to specific governance choices.

#### Cost of this choice

In real organizations, inattentive leadership absolutely can delay recognition of schedule slips. A project that is quietly falling behind may not surface that fact until the overrun is severe, precisely because no one in leadership is watching closely enough to notice. The model assumes that execution tracking is always visible, which means governance regimes that stop initiatives for cost overruns will appear somewhat more effective in the simulation than they would be in practice. This should be kept in mind when interpreting any findings about cost-sensitive governance approaches.

---

## 12. Why execution-overrun stops are first-class in reporting


### Academic
#### Decision

Pure execution-overrun stops are recorded as
`triggering_rule = "execution_overrun"` rather than being folded into
`"discretionary"`.

#### Why this choice was made

The model already represents execution-fidelity belief and cost-overrun
tolerance as meaningful governance dimensions. If the reporting layer then folded
pure overrun-driven stops into a generic discretionary bucket, it would blur a
distinction that the study is explicitly trying to compare.

This is especially important for RQ8 and for any practitioner-facing conclusion
about cost-sensitive governance. A reader should not have to reconstruct overrun
behavior indirectly from other fields when the model already knows it directly.

The reporting distinction enables direct measurement of how frequently each
governance regime terminates work for cost reasons versus strategic conviction
reasons — a comparison that would otherwise require error-prone post-hoc
inference from belief trajectories and stop timing.

#### Alternative rejected

Using only `"discretionary"` for overrun-driven stops was rejected because it
needlessly weakens the study's ability to say anything crisp about cost-sensitive
governance.

---

### Business
#### Decision

When governance stops an initiative primarily because execution has overrun badly — because the work is taking far longer than planned, regardless of whether the underlying idea still looks promising — that stop is recorded as a distinct event in the study's outputs, clearly labeled as a cost-driven termination rather than being folded into a generic "discretionary stop" category.

#### Why this choice was made

The model already treats execution tracking and cost-overrun tolerance as meaningful governance dimensions — governance regimes differ in how much they weight schedule slippage when making stop decisions. If the reporting layer then grouped cost-driven stops into a generic bucket alongside other discretionary stops, it would blur a distinction that the study is explicitly designed to compare.

This matters particularly for any practitioner-facing conclusion about cost-sensitive governance. One of the study's research questions asks directly about the relationship between cost-overrun tolerance and governance outcomes. If a reader wanted to understand how often a particular governance regime terminated work for cost reasons versus strategic conviction reasons, they should not have to reverse-engineer that information from other data fields when the model already knows the answer directly.

#### Alternative rejected

Labeling all non-rule-based stops as "discretionary" was rejected because it needlessly weakens the study's ability to say anything precise about a governance dimension — cost sensitivity — that the study is explicitly investigating.

---

## 13. Why `effective_sigma_t` is logged directly


### Academic
#### Decision

The per-tick reporting layer includes `effective_sigma_t`, the actual strategic
signal noise scale used by the engine for that initiative on that tick.

#### Why this choice was made

RQ7 is specifically about the interaction between attention strategy and stop
decisions through the corruption of information quality. The engine already knows
the effective noise scale exactly. Omitting it from logs would force analysts to
infer a quantity the simulator already computes deterministically.

The causal pathway under investigation is specific: low attention allocation →
elevated `σ_eff` → noisier strategic signals → less accurate belief updates →
belief more likely to cross a stop threshold → termination of a potentially
high-quality initiative. An initiative may be stopped not because its latent
quality is low, but because governance did not invest enough attention to reduce
`σ_eff` to the level needed for the belief to converge accurately. Logging
`effective_sigma_t` directly makes every link in this causal chain auditable in
the output: what attention was allocated, what `σ_eff` resulted, what belief was
formed, and what stop decision followed.

Including it directly makes the signal path auditable and avoids unnecessary
post-hoc reconstruction. That is good scientific hygiene and good operational
design.

#### Alternative rejected

Keeping `effective_sigma_t` implicit was rejected because it saved little and
made the most attention-sensitive research question harder to answer cleanly.

---

### Business
#### Decision

The study's per-week outputs include a direct record of the actual signal quality each initiative experienced that week — a measure of how noisy or clear the strategic evidence was for that initiative in that period, given the executive attention it received, the initiative's inherent complexity, and the organization's current capability level.

#### Why this choice was made

One of the study's most important research questions asks whether stop decisions get corrupted by the attention allocation that preceded them. The mechanism is specific: if leadership pays too little attention to an initiative early on, the strategic evidence that initiative generates will be noisier, leadership's belief about it will be less accurate, and that less-accurate belief is more likely to cross a stop threshold — even if the initiative is genuinely worth pursuing. The initiative gets killed not because it was bad, but because governance did not invest enough attention to see clearly.

Answering that question requires knowing exactly how clear or noisy the strategic signal was for each initiative in each period. The simulation engine already computes this quantity precisely. Omitting it from the outputs would force analysts to reconstruct it after the fact from other data — a reconstruction that is possible but unnecessary and error-prone.

Including actual signal quality directly in the output makes the entire information pathway auditable: what attention was allocated, what signal quality resulted, what belief was formed, and what stop decision followed. That transparency is essential for any finding that connects attention strategy to stop outcomes.

#### Alternative rejected

Leaving signal quality implicit — forcing analysts to calculate it from the inputs rather than recording it directly — was rejected because it saved almost no output cost and made the study's most attention-sensitive research question harder to answer cleanly.

---

## 14. Why residual value is decomposed by label in primary outputs


### Academic
#### Decision

Primary outputs include `residual_value_by_label`.

#### Why this choice was made

The study wants to distinguish not only how much value is created, but which
mechanisms created it. Residual value is particularly important because it sits
near the conceptual boundary between compounding mechanisms and other forms of
long-run payoff.

Two governance regimes may produce similar cumulative value at the terminal tick
while having structurally different portfolios underneath — one built heavily on
compounding residual streams, the other on completion lumps. These represent
different trajectories with different implications for value creation beyond the
study horizon. The label-level decomposition makes this structural difference
visible in the primary output without requiring downstream reconstruction.

A label-level decomposition gives analysts most of the needed interpretability
without requiring a much heavier per-initiative residual trace in the canonical
schema. It is the right compromise between observability and output sprawl.

#### Alternative rejected

A fully granular per-initiative residual reporting layer was rejected for the
canonical baseline because it would add reporting weight that most analyses do
not need.

---

### Business
#### Decision

The study's primary outputs break down ongoing value streams by initiative type — showing how much of the total accumulating value comes from flywheels, how much from other sources, and so on.

#### Why this choice was made

The study wants to distinguish not only how much total value a governance regime creates, but which value-creation mechanisms produced it. This distinction is central to the study's purpose. Two governance regimes might produce similar total value at the end of six years while having dramatically different portfolios underneath: one built heavily on compounding return mechanisms, the other built heavily on one-time payoffs. Those are structurally different organizational trajectories that would lead to very different futures beyond the study horizon.

Ongoing value from completed initiatives sits at the conceptual boundary between compounding mechanisms and other forms of long-run payoff. Breaking it down by initiative type gives analysts the interpretability they need — which governance choices led to the accumulation of which kinds of ongoing value — without requiring the much heavier approach of tracking every individual initiative's contribution separately in the primary output.

#### Alternative rejected

A fully granular per-initiative breakdown of ongoing value was rejected for the baseline outputs because it would add substantial reporting weight that most analyses do not need. The type-level decomposition provides the right balance between visibility and manageability for the governance questions the study is designed to answer.

---

## 15. Why the experiments doc distinguishes world-seed variation from environmental contingency


### Academic
#### Decision

The experiments protocol states explicitly that changing `world_seed` samples
different worlds from a fixed environment configuration, whereas claims about
environmental contingency require separate sweeps of environmental parameters.

#### Why this choice was made

This is a causal-interpretation safeguard. Without this clarification, a reader
can easily slide from "this governance regime is robust across random draws in
one configured environment" to "this governance regime is robust across
environments," which is a much stronger and often false claim.

The study needs to distinguish:

- stochastic robustness within an environment (the finding is not an artifact of
  a particular realization of ξ),
- structural robustness across environments (the finding holds when environment
  parameters change — when major-win incidence is rarer or richer, when initiative
  duration distributions shift, when portfolio composition varies).

The first is established by replication across `world_seed` values within a fixed
environment family. The second requires separate sweeps across the named
environment families (`balanced_incumbent`, `short_cycle_throughput`,
`discovery_heavy`). A governance finding that holds within one family but fails
in another is a contingent result, not a general one. The protocol must make this
distinction explicit so that downstream analysis does not inadvertently overstate
the generality of within-family findings.

The added sentence is small, but it protects a very important interpretive
boundary.

---

### Business
#### Decision

The study's experimental protocol makes an explicit distinction between two kinds of variation: running the same organizational environment with different random draws (which produces different specific opportunities, signal sequences, and outcomes) versus running structurally different organizational environments (which changes the fundamental character of the opportunity landscape).

#### Why this choice was made

This distinction protects against a very common misinterpretation. Without it, a reader can easily slide from "this governance approach performed well across a hundred different random runs in one configured environment" to "this governance approach performs well across different kinds of organizations and opportunity environments." The first claim is about statistical reliability — the finding is not a fluke of one particular random draw. The second claim is about structural robustness — the finding holds even when the fundamental conditions change. The second claim is much stronger and often false.

The study needs to distinguish these clearly:

- **Reliability within an environment:** Does the governance finding hold consistently across many random scenarios drawn from the same type of organizational environment? Or is it an artifact of a lucky draw?
- **Robustness across environments:** Does the governance finding hold when the nature of the opportunity landscape changes — when major wins are rarer or more common, when initiative cycles are faster or slower, when the portfolio composition shifts?

A governance approach that looks good in one environment but fails in another is a contingent finding, not a general one. The study is designed to identify both — but only if the experimental protocol makes the distinction explicit. The clarification is small, but it protects a critically important interpretive boundary.

---

## 16. Why bounded-prize patience scales with visible upside


### Academic
#### Decision

For initiatives with an observable bounded prize, bounded-prize patience scales
linearly with visible upside relative to a model-level `reference_ceiling`.
Larger visible bounded opportunities therefore earn more review patience than
smaller ones.

The canonical intent is prize-relative patience with no hard cap. If a
governance regime gives excessive patience to large visible opportunities, the
model should allow that behavior and record its consequences rather than
preventing it with a paternalistic backstop.

#### Why this choice was made

The prior bounded-prize rule allowed the prize ceiling to cancel out of the
decision, which meant bounded opportunities of very different visible upside
could receive behaviorally identical patience. That did not match the business
logic the study is trying to represent.

Organizations often tolerate more experimentation on very large opportunities
because one success can pay for many failures. The canonical model therefore
needs a way for visible upside to buy more patience. Linear scaling is the
cleanest and most auditable form for that logic. An analyst can reconstruct the
patience earned by any bounded-prize initiative directly from its visible
ceiling and the shared reference ceiling.

No hard cap is used in the canonical rule because the model is intended to
measure governance mistakes rather than prevent them. If a regime grants
excessive patience to large visible opportunities, the simulation should record
the resulting labor consumption and foregone alternatives rather than suppressing
that behavior inside the mechanics.

#### Alternatives rejected

Keeping prize patience fixed and merely clarifying the prose was rejected because
it left a core portfolio-governance phenomenon invisible.

Using a hard cap on TAM-derived patience was rejected because it would embed a
protective judgment into the simulator rather than allowing governance regimes to
fail on their own terms.

Using a more complex nonlinear scaling rule was rejected for the canonical study
because it weakened auditability without a comparably large gain in insight.

---

### Business
#### Decision

For initiatives where leadership can see a ceiling on the potential upside — a bounded opportunity with an estimable maximum value — the amount of review patience the initiative earns scales proportionally with the size of that visible upside. Larger visible opportunities earn more patience before governance concludes they are not worth continuing. Smaller visible opportunities earn less.

There is no hard cap on how much patience a large visible opportunity can earn. If a governance regime grants excessive patience to very large opportunities, the model allows that to happen and records the consequences — the labor consumed, the alternatives forgone — rather than preventing it with a built-in limit.

#### Why this choice was made

The earlier version of this rule allowed the size of the visible opportunity to effectively cancel out of the patience calculation, which meant that bounded opportunities with very different visible upside could receive the same amount of governance patience. That did not reflect how organizations actually make portfolio decisions.

In practice, organizations routinely tolerate more experimentation and longer timelines on very large opportunities than on small ones. A team pursuing a $500M market opportunity will get more runway than one pursuing a $5M opportunity, all else being equal, because one success at scale can pay for many failures. This is not irrational — it is basic portfolio logic. The study needs to represent that logic.

Proportional scaling is the simplest and most transparent form of that logic. An analyst looking at the study's outputs can reconstruct exactly how much patience any bounded-prize initiative earned by knowing two things: the initiative's visible upside ceiling and the shared reference level that the study uses for comparison. No hidden parameters or complex curves are involved.

The decision to omit a hard cap is equally deliberate. The model is designed to measure the consequences of governance choices, not to prevent governance from making bad ones. If a regime grants too much patience to very large opportunities — spending years pursuing a large bounded prize that is never going to work — the simulation records that behavior: the teams tied up, the opportunities foregone, the value that was not created elsewhere. A built-in cap would suppress exactly the kind of governance failure the study is designed to observe.

#### Alternatives rejected

Keeping patience fixed regardless of visible upside was rejected because it made a core portfolio-governance phenomenon invisible — the study could not distinguish governance that calibrates patience to opportunity size from governance that does not.

Adding a hard cap on how much patience large opportunities could earn was rejected because it would embed a protective judgment into the simulation mechanics rather than allowing governance regimes to succeed or fail on their own terms.

A more complex nonlinear scaling relationship was rejected for the baseline study because it would reduce auditability — analysts would need to understand a more complicated curve — without a comparably large gain in insight.

---

## 17. Why non-TAM initiatives have a separate stagnation path


### Academic
#### Decision

Initiatives without an observable bounded prize have a separate non-TAM
stagnation path. Non-TAM stagnation fires when both conditions hold:

- informational stasis is present over the canonical stagnation window, and
- current strategic belief has not risen above the canonical neutral baseline.

This reuses the existing stagnation parameters and the canonical prior rather
than introducing a new parameter family.

#### Why this choice was made

Once bounded-prize patience scales with visible upside, bounded-prize
initiatives have a richer patience mechanism than flywheels and enablers. If
non-TAM initiatives were left with only confidence decline, the simulator could
fail to represent an important organizational pathology: long-running,
informationally exhausted non-TAM work whose belief never falls far enough to hit
the stop threshold but never earns stronger conviction either.

The canonical study should be able to diagnose that failure mode, especially for
patient governance regimes. A non-TAM stagnation path therefore exists to capture
"we are no longer learning anything useful and this work has not earned stronger
belief than where we began."

Patient governance regimes are asymmetrically vulnerable to this failure mode. An
impatient regime would have terminated the initiative earlier — possibly too early
— but a patient regime may allow it to persist indefinitely in this
informationally exhausted state, consuming labor and team capacity without
generating actionable evidence. The study needs to be able to diagnose that
pattern and measure its cost.

The neutral baseline plays the role of the second leg of the rule. A high-quality
stable flywheel whose belief has converged well above the baseline is not
stagnant. A mediocre flywheel whose belief is flat and has failed to rise above
the baseline is.

#### Alternatives rejected

Leaving stagnation bounded-prize-only was rejected because it made the model too
forgiving of stale non-TAM work and weakened one of the study's primary
comparisons around patient governance.

Adding a separate non-TAM parameter family was rejected because the problem could
be solved more cleanly by reusing the existing stagnation window and the
canonical prior.

---

### Business
#### Decision

Initiatives where leadership cannot see a ceiling on the potential upside — flywheels, enablers, and other work without a bounded prize — have their own distinct stagnation rule. This rule fires when two conditions are both true:

- The organization has stopped learning anything new about the initiative — its belief about the initiative's quality has not meaningfully shifted over a sustained window of active work.
- That belief has never risen above the neutral starting point — the organization's assessment of this initiative has never become more positive than where it started on day one.

This rule uses the same stagnation window and the same neutral starting point that already exist in the model, rather than introducing new parameters.

#### Why this choice was made

Once bounded-prize patience scales with the size of the visible upside, initiatives with observable ceilings have a richer and more calibrated patience mechanism. Their governance patience is proportional to their visible potential. But flywheels and enablers — which do not have visible prize ceilings — would be left with only the blunt instrument of conviction decline: governance can stop them if confidence drops far enough, but has no mechanism for addressing a more subtle and arguably more common organizational pathology.

That pathology is this: long-running work whose information environment has become stale. The organization has been investing in the initiative for months or years. The evidence is no longer moving in either direction — each new week of work produces signals, but they do not change the picture. And the picture was never very encouraging to begin with. Belief never dropped low enough to trigger a stop on conviction alone, but it also never rose high enough to justify continued confidence. The initiative sits in a kind of organizational limbo: not bad enough to kill, not good enough to champion, consuming resources without generating insight.

Patient governance regimes are especially vulnerable to this failure mode. An impatient regime would have killed the initiative earlier — perhaps too early — but a patient regime may allow it to persist indefinitely in this informationally exhausted state. The study needs to be able to diagnose that pattern.

The rule uses the neutral starting belief as the second leg of the test. This creates a meaningful distinction. A high-quality flywheel whose belief has converged well above the starting point is not stagnant — it has earned its continued investment through accumulated evidence. A mediocre flywheel whose belief has stayed flat and never risen above where it began is stagnant — the organization has been investing for a sustained period and has never seen evidence that the initiative is better than the neutral starting assumption.

#### Alternatives rejected

Leaving stagnation as something that only applies to bounded-prize initiatives was rejected because it made the model too forgiving of stale work in the non-bounded part of the portfolio and weakened one of the study's most important comparisons: how patient governance regimes handle work that has stopped generating useful information.

Introducing entirely new parameters for non-bounded stagnation was rejected because the problem could be solved more cleanly by reusing the existing stagnation window and the existing neutral starting point. Adding a new parameter family would have increased complexity without a corresponding gain in governance insight.

---

## 18. Why the model avoids normative judgments in names and outputs


### Academic
#### Decision

The canonical model accepts a governance regime and evaluates its consequences
under the shared mechanics. It does not label decisions or states as rational,
irrational, wise, foolish, productive, or wasteful inside the simulator itself.

Variable names, event schemas, and reporting fields should therefore describe
modeled state and rule conditions rather than embed evaluative judgment.

#### Why this choice was made

The study is designed to compare governance regimes, not to hard-code a theory
of which regime is correct. Evaluative conclusions belong in downstream analysis,
not in the simulator's state language.

The problem with embedded judgment is that the same policy action can receive
opposite evaluative labels depending on the counterfactual. A policy that stops
many initiatives early could be classified as either type I error (terminating
genuinely valuable work) or efficient resource reallocation (freeing capacity for
better opportunities) depending on what those freed resources were used for and
what the stopped initiatives would have produced if continued. Those are exactly
the questions the study is designed to answer. If the simulator pre-labels early
stops as "waste," it forecloses the analysis before it begins.

This matters both for scientific discipline and for future optimization-oriented
extensions. A simulator that already embeds judgment into names and outputs makes
it harder to distinguish descriptive mechanics from normative interpretation.
Keeping the mechanics neutral preserves the option to evaluate or later optimize
regimes without having the simulator itself prejudge them.

#### Alternatives rejected

Using variable names such as "economic inadequacy," "waste," or similar
judgment-laden labels was rejected because it smuggles analysis conclusions into
the simulation layer.

---

### Business
#### Decision

The model accepts a governance regime and evaluates its consequences under the shared mechanics. It does not label decisions, initiative states, or outcomes as good, bad, rational, irrational, efficient, or wasteful within the simulation itself.

All fields, events, and output categories describe what happened and under what conditions — not whether it was the right thing to do.

#### Why this choice was made

The study is designed to compare governance regimes, not to hard-code a theory of which regime is correct. If the model's own internal language used terms like "waste" for resources consumed on stopped initiatives, or "failure" for initiatives that did not complete, or "optimal" for particular attention allocations, it would be smuggling evaluative conclusions into the measurement instrument. The simulation would then confirm its own built-in judgments rather than revealing the actual tradeoff structure.

This matters practically as well as intellectually. A governance regime that stops many initiatives early might look "wasteful" from one perspective — all that sunk investment for nothing — and "disciplined" from another — resources freed up quickly for better opportunities. The right characterization depends on what those freed resources were used for and what the stopped initiatives would have produced if continued. Those are exactly the questions the study is designed to answer. If the model pre-labels early stops as waste, it forecloses the analysis before it begins.

Keeping the model's language neutral also preserves the option for future work to layer optimization or normative evaluation on top of the simulation's outputs without fighting against the model's own vocabulary. A reader of the outputs should be able to form their own judgment about what constitutes good governance rather than having that judgment pre-embedded in the data labels.

#### Alternatives rejected

Using evaluative labels like "economic inadequacy," "waste," "failure," or similar judgment-laden terms in the model's internal language was rejected because it smuggles analysis conclusions into the simulation layer, pre-committing the study to evaluative positions that should be reached through analysis, not assumed in the design.

---

## 19. Why the output contract is analyst-agnostic


### Academic
#### Decision

The simulator is intentionally agnostic about who analyzes its outputs next. The
canonical output contract is designed to support human analysts, AI analysts, and
hybrid human-AI workflows without changing simulator behavior or privileging one
interpretation path.

#### Why this choice was made

The study is about accelerating learning from evidence. That goal should apply to
the study's own analysis workflow as well. A simulator designed only for human
chart reading leaves too much interpretive work implicit. A simulator designed
only for an automated pipeline is often too rigid to support exploratory follow-up.

Analyst-agnostic output design means the simulator produces machine-readable,
auditable, provenance-preserving outputs that can support different analyst
modalities over the same evidentiary base. Deterministic facts, derived metrics,
and downstream interpretations can then be separated more cleanly.

This is also part of what differentiates the study. The simulator does not assume
that one brilliant human reader must manually spot every pattern, nor that an AI
system should be trusted with raw interpretation. Instead it creates a shared,
structured evidence layer usable by both.

#### Alternatives rejected

Designing outputs mainly for static human reporting was rejected because it slows
iterative learning and follow-up experimentation.

Designing outputs mainly for unconstrained AI interpretation was rejected because
it weakens auditability and blurs the boundary between evidence and narrative.

---

### Business
#### Decision

The simulation is deliberately agnostic about who or what analyzes its outputs. The output design supports human analysts, AI-assisted analysis, and hybrid workflows without changing the simulation's behavior or privileging any one approach.

#### Why this choice was made

The study is fundamentally about accelerating learning from evidence. That goal should apply to the study's own analysis workflow, not just to the organizations it models. A simulation designed only for traditional human chart reading would leave too much interpretive work implicit — requiring analysts to manually spot patterns, reconstruct derived quantities, and maintain mental context across thousands of runs. A simulation designed only for an automated analysis pipeline would be too rigid to support the kind of exploratory follow-up questions that emerge once initial findings are in hand.

Analyst-agnostic output design means the simulation produces structured, machine-readable outputs that preserve full provenance — every output can be traced back to the inputs and decisions that produced it. This allows clean separation between what the simulation computed deterministically, what was derived from those computations, and what interpretive conclusions were drawn. Different analysts — human, AI, or collaborative — can then work from the same evidentiary base while bringing their own strengths to the interpretation.

This is also part of what differentiates the study. The simulation does not assume that a single brilliant analyst must manually inspect every run, nor that an automated system should be trusted with unconstrained interpretation. Instead, it creates a shared, structured evidence layer that both human judgment and computational analysis can use.

#### Alternatives rejected

Designing outputs primarily for static human reporting — charts, summary tables, and narrative-ready formats — was rejected because it slows iterative learning and makes it harder to ask follow-up questions of the data.

Designing outputs primarily for unconstrained automated interpretation was rejected because it weakens auditability and blurs the boundary between evidence and narrative. When you cannot tell which conclusions came from the data and which came from the analysis tool's own reasoning, the findings become harder to trust.

---

## 20. Why some limitations are kept visible rather than "fixed"


### Academic
#### Decision

Several known limitations are left explicit in the overview rather than being
patched away in the canonical model. Examples include:

- one-sided execution belief bias near the upper boundary,
- scalar belief without explicit observation-count precision,
- surfaced-not-priced right-tail wins,
- one-stock capability simplification,
- completion-gated value realization,
- independence of initiatives except through shared capability.

#### Why this choice was made

Not every limitation should be "solved" inside the canonical study. Some are the
price of keeping the model focused on the governance mechanisms it is actually
designed to illuminate.

If the base study tried to eliminate every realism gap at once, it would stop
being a tractable governance model and become a sprawling organization simulator
whose results would be harder to interpret and harder to trust.

Each additional mechanism adds not just implementation complexity but analytical
complexity: more interactions to control for, more potential explanations for any
observed finding, and more opportunities for a result to be driven by a modeling
artifact rather than by the governance dynamic under study. Reduced-form design
preserves identification — the ability to attribute outcome differences to the
treatment variable.

The canonical strategy is therefore:

- fix ambiguities that threaten internal consistency,
- expose quantities needed to answer the research questions,
- preserve known simplifications transparently when they are part of the study's
  tractability bargain.

By keeping limitations visible rather than hidden or patched, the study enables
readers to assess which findings are robust to those limitations and which might
be sensitive to them. That transparency is more useful than the appearance of
completeness.

---

### Business
#### Decision

Several known limitations of the model are left explicit and visible in the study documentation rather than being patched away in the design. These include:

- The tendency for the organization's execution assessment to drift slightly pessimistic even for initiatives that are genuinely on track.
- The fact that leadership's belief is a single number without any indication of how much evidence underlies it.
- The choice to record major-win discoveries as events rather than pricing their full economic value.
- The use of a single number for organizational capability rather than tracking multiple dimensions.
- The all-or-nothing nature of completion-gated value realization.
- The independence of initiatives from one another except through their shared effect on organizational capability.

#### Why this choice was made

Not every gap between the model and organizational reality should be closed in the baseline study. Some of these limitations are the deliberate price of keeping the model focused on the governance mechanisms it is actually designed to illuminate.

If the study tried to close every realism gap at once, it would stop being a tractable governance model and become a sprawling organization simulator whose results would be harder to interpret and harder to trust. Every additional mechanism adds not just complexity to the simulation but complexity to the analysis: more interactions to control for, more potential explanations for any finding, more opportunities for a result to be driven by a modeling artifact rather than by the governance dynamic the study is meant to reveal.

The strategy for the baseline study is therefore:

- Fix ambiguities that threaten the internal consistency of the model — if two parts of the model would produce contradictory results, that must be resolved.
- Include every quantity needed to answer the study's research questions directly — do not force analysts to reconstruct what the model already knows.
- Preserve known simplifications transparently when they are part of the study's fundamental bargain between tractability and realism.

By keeping limitations visible rather than hidden or hastily patched, the study makes it possible for readers to assess which findings are robust to those limitations and which might be sensitive to them. That is more honest and more useful than pretending the limitations do not exist.

---

## 21. What remains open after initial design


### Academic
At the point this document was created, the study design had reached
the stage where the remaining work was no longer about unresolved mechanics but
about implementation, calibration, and future extensions.

Questions that remain valid for future work include:

- whether the capability stock should later be split into multiple dimensions
  (e.g., separating experimentation infrastructure capability from
  decision-support capability from execution visibility),
- whether right-tail wins should receive a priced downstream value model rather
  than being recorded as discovery events,
- whether partial completion value should be introduced, allowing stopped
  initiatives to retain some fraction of realized value,
- whether belief precision should be represented explicitly — replacing the
  current scalar point estimate with a posterior distribution or at minimum an
  observation-count statistic, so that governance can distinguish a belief of 0.6
  based on two noisy observations from one based on forty,
- whether initiative interactions should be modeled beyond shared capability
  (e.g., completion dependencies, complementarities, or substitution effects
  across the portfolio),
- whether attention should affect the visibility of execution overruns, closing
  the asymmetry identified as a known limitation in the current information model.

These are not open issues in the canonical design. They are extension paths —
ways the study could be deepened in future versions once the baseline governance
questions have been answered.

---

### Business
At the point this document was created, the study's design had reached a stage where the remaining work was no longer about unresolved design questions but about implementation, running the experiments, analyzing the results, and identifying paths for future extensions.

Questions that remain valid for future work include:

- Whether the single organizational capability measure should later be split into multiple dimensions — for example, separating experimentation infrastructure capability from decision-support capability from execution visibility capability.
- Whether major-win discoveries should receive a priced downstream economic value rather than being recorded as events alone.
- Whether partial completion value should be introduced — allowing initiatives that are stopped before completion to retain some fraction of the value they have created.
- Whether the precision of leadership's beliefs should be tracked explicitly — so that governance can distinguish between a "60% confident" assessment based on two weeks of noisy data and the same assessment based on two years of consistent signals.
- Whether initiative interactions should be modeled beyond their shared effect on organizational capability — for example, whether completing one initiative makes a related initiative easier or harder to complete.
- Whether executive attention should affect the visibility of execution overruns — closing the gap identified as a known limitation in the current design.

These are not unresolved issues in the current design. The current design is complete and internally consistent. These are extension paths — ways the study could be deepened in future versions once the baseline governance questions have been answered.

---

## 22. Why frontier replenishment uses a threshold-plus-one fill

### Decision

When a family's unassigned pool falls to or below
`replenishment_threshold` (default 3), the runner materializes enough
new initiatives to bring the count back up to `threshold + 1`.
Materialization is triggered only by the inter-tick depletion check,
never as a direct consequence of a governance assignment.

### Why this choice was made

Governance must always have a meaningful selection choice within each
initiative family. A compact-pool model (materialize exactly one when
the pool hits zero) creates states in which a family has no available
candidates, forcing degenerate decisions driven by pipeline exhaustion
rather than by the governance regime being tested.

The threshold buffer also addresses a heterogeneous-team-size concern:
with mixed team sizes, a single unassigned initiative requiring a
large team cannot be started by a smaller free team, producing
artificial idleness. Holding several initiatives per family in the
unassigned pool gives any free team a better chance of finding
feasible work; the frontier team-size rule (frontier-generated
initiatives use the minimum of the type spec's team-size range)
complements this by keeping new supply broadly staffable.

Setting `threshold = 3` and fill-to-N+1 was tuned empirically against
run-time idle rates (reducing 34-38% → 1-10%). Uniform thresholds
across families are sufficient for v1; per-family tuning can be
added as an extension if family-specific pipeline dynamics prove
material.

### Alternatives rejected

Assignment-triggered spawning — where a new initiative is generated
whenever governance assigns a team to an existing one — was rejected
because it couples the opportunity environment to governance
behavior, violating the principle that the frontier is an
environmental feature of the study rather than a consequence of
governance action.

Compact-pool (threshold=0, generate one) was rejected because it
produces frequent zero-availability states and, combined with
heterogeneous team sizes, causes avoidable idleness.

A two-parameter threshold/target-buffer model (maintain between a
minimum and a maximum) was considered and rejected as unnecessary
complexity; a single threshold with fill-to-N+1 achieves the same
"always at least one candidate per family" invariant with one fewer
knob.

Per `dynamic_opportunity_frontier.md` §1.

---

## 23. Why unassigned teams can produce baseline value

### Decision

When `model.baseline_value_per_tick` is set on `ModelConfig`, unassigned
teams accrue that amount per team per tick as runner-side accounting.
The value is surfaced on `RunResult.cumulative_baseline_value`; the
engine itself does not consume it. The default is `0.0` (opt-in): only
studies that want to credit baseline work enable it explicitly.

### Why this choice was made

Without baseline value, governance is penalized for leaving teams
"idle" even when the remaining portfolio candidates are worse than
the organization's routine work. A regime that rationally holds back
from marginal initiatives scores lower than one that staffs everything
indiscriminately — which is the opposite of the substantive finding
the study is trying to surface.

Baseline value redefines "idle" as "on baseline." Teams are always
productive at some rate; the governance decision becomes whether a
portfolio initiative is worth the opportunity cost of pulling a team
off baseline, which is the decision organizations actually face.

Runner-side accounting keeps the engine unchanged: no extra state, no
extra signals, no learning. Baseline work has none of the mechanics
the engine models (uncertainty, signals, completion) and does not
belong in the initiative pipeline.

The default is `0.0` because making baseline value always-on would
silently change the scoring of every existing preset. Studies opt in
explicitly (calibrated value is 0.1/tick per `calibration_note.md`).

### Alternatives rejected

Modeling baseline work as a special initiative type was rejected as
over-engineering. It has no learning dynamics, no completion event,
no signals — routing it through the initiative engine adds complexity
without adding explanatory value.

Baking a nonzero default into `ModelConfig` was rejected because it
would silently alter comparisons against bundles produced before the
field existed. Opt-in preserves backward-compatibility of stored
results; studies that want baseline accounting declare it.

Per `governance.md` "Baseline work semantics".

---

## 24. Why the generator provides a screening signal for initial quality belief

### Decision

When `screening_signal_st_dev` is set on an `InitiativeTypeSpec`, the
generator draws
`initial_quality_belief = clamp(latent_quality + Normal(0, sigma_screen), 0, 1)`.
Per-family noise defaults express how accurately organizations can
assess strategic quality before execution begins:

| Family | `sigma_screen` | Rationale |
|--------|---------------|-----------|
| Quick-win | 0.10 | Bounded scope; easiest to screen pre-execution |
| Flywheel | 0.15 | Compounding potential partially predictable |
| Enabler | 0.15 | Capability needs assessable from technical landscape |
| Right-tail | 0.25 | Speculative; hardest to evaluate before staffing |

This is a pre-execution intake assessment, not a posterior formed
from observed signals. The clamp to `[0, 1]` is the natural range of
a quality belief; no margin off the boundary is imposed.

### Why this choice was made

Without a screening signal, all non-bounded initiatives enter the
portfolio with the default strategic prior (typically 0.5). Governance
has no basis for differentiating among available initiatives before
execution begins — an arbitrary t=0 ranking. The screening signal
models the organizational reality that intake processes provide
imperfect but nonzero information: a business case, market analysis,
sponsor assessment, technical feasibility review.

The screening signal also makes the baseline-value tradeoff
meaningful (decision 23). With a flat 0.5 prior, governance cannot
identify which candidates are likely worse than baseline before
committing a team. With screening, low-screening-belief initiatives
can be rationally held back in favor of baseline work.

Per-family noise levels reflect a substantive modeling claim: some
types of work are easier to evaluate at intake than others.
Quick-wins with well-defined deliverables are more evaluable than
right-tail bets whose payoff depends on unpredictable discovery.
This is a study-design choice, not a calibration convenience.

### Alternatives rejected

Perfect initial beliefs (intake signal equal to latent quality) were
rejected because they eliminate the study's core question: whether
governance learns to distinguish good from bad initiatives through
execution signals. If governance knows quality at intake, the
execution-learning mechanism is bypassed.

Uniform noise across all families was rejected because it ignores
evaluability differences. A process-automation quick-win and a
research moonshot are not equally hard to screen.

Per `initiative_model.md` and `sourcing_and_generation.md`.

---

## 25. Why later frontier opportunities thin observably, not just latently

### Decision

Alongside latent quality degradation of later-arriving frontier
initiatives, a small number of observable attributes degrade per
family as the frontier is consumed. Flywheel and quick-win planned
durations grow (rates 0.005 and 0.008; ceilings 1.4 and 1.5).
Enabler capability-contribution-scale upper bound shrinks (rate
0.008; floor 0.5). Right-tail initiatives receive no observable
thinning, preserving their prize-driven refresh dynamics.

### Why this choice was made

If the frontier degrades only in latent quality, governance cannot
observe that opportunities are becoming less attractive. That
creates an information asymmetry that does not match the
organizational phenomenon being modeled: in real organizations, the
decline of the remaining pipeline is partially visible at intake.
What's left visibly takes longer, offers smaller capability gains,
or has less favorable economics.

Observable thinning lets governance rationally respond to frontier
degradation rather than continuing to invest at the same rate in a
pipeline that has invisibly deteriorated. A regime that slows
investment as the pipeline visibly thins is making a qualitatively
different decision from one that continues investing because it
cannot see the decline — exactly the difference the study is
designed to distinguish.

The specific attributes chosen for thinning match family-level
economics. Flywheel and quick-win durations grow because the
low-hanging fruit has been picked; later opportunities require more
effort for comparable outcomes. Enabler capability contributions
shrink because the highest-leverage infrastructure investments are
made first. Right-tail initiatives are exempt because value comes
from rare prize events whose characteristics are per-draw, not
per-generation — the ceiling on a breakthrough does not shrink
just because earlier right-tail work has been done.

### Alternatives rejected

Degrading all observable attributes across all families was rejected
as overdetermined. If every visible characteristic worsens
simultaneously, the thinning signal becomes artificially uniform and
does not match how real pipelines degrade.

No observable degradation at all was rejected because it hides the
declining frontier from governance. A study that investigates
governance under declining opportunity but prevents governance from
seeing the decline is testing a different, less useful question.

Right-tail observable thinning was rejected because the right-tail
value mechanism is prize-based. The ceiling on a major discovery is
a property of the prize itself, not of the generation cohort.

Per `dynamic_opportunity_frontier.md` §observable-thinning.

---

## Final note


### Academic
This document should grow slowly. It is not intended to become a running meeting
log or a transcript of every design conversation. A decision belongs here only if
it is:

- consequential for interpreting the study,
- easy to forget later,
- likely to be reopened by a future reader who does not know the project history.

That is the standard for durable institutional memory in this corpus.

### Business
This document should grow slowly. It is not intended to become a running log of every design discussion or a transcript of evolving thought. A decision belongs here only if it meets three criteria:

- It is consequential for how the study's findings should be interpreted — a reader who does not know about this decision might draw the wrong conclusions.
- It is easy to forget — the reasoning is not obvious from the code, the data, or the technical specifications alone.
- It is likely to be revisited by a future reader who does not know the project history — someone who would otherwise need to reconstruct the reasoning from scratch.

That is the standard for what earns a place in this document: the durable institutional memory of why the study was designed the way it was, preserved so that future work can build on these choices rather than unknowingly relitigate them.
