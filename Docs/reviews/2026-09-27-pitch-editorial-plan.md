# Editorial plan: the pitch "BATS as the agent's body"

**Status:** Accepted (the plan was applied the day it was written; kept as the record of what changed and what was rejected)
**Piece:** [../design/2026-09-27-pitch-bats-as-the-agents-body.md](../design/2026-09-27-pitch-bats-as-the-agents-body.md)
**Pipeline:** CO3DEX `EDITORIAL_PIPELINE.md` (structure, facts, voice, rhythm, reach, adversarial, scorecard, author review), applied 2026-09-27 at the owner's ask.
**Audience, named before editing:** a memo for the owner's team and manager, people who know a DCC pipeline and have not followed this work. Not a blog post; not edited into one (standing rule 4). No corpus voice profile applies; the memo's register is the owner's plain formal, contractions rare.

Resumable cold: every finding below carries its diagnosis and the rewrite that was applied or rejected.

## Layer 1: structural findings, ranked by cost

| # | Finding | Diagnosis | Action |
| --- | --- | --- | --- |
| 1 | **Ungrounded image.** The title says "body" and the lead never earns it; the brain-and-body frame first appears at the end of *What*. | A reader meets the metaphor cold and carries a question for 700 words. | The lead now grounds it in two sentences: the harness is the brain, what it lacks is a body, BATS is most of the body. Applied. |
| 2 | **Competing theses.** Three sentences each claim the point: the body (lead), "reading and following up is the half nothing owns" (*Why*), "a Python worker can do anything Python can do" (*Around the corner*). | Each is good; together they dilute. | The body is the thesis. The other two stay as supporting lines inside their sections and the ask carries one portable test, not three. Applied. |
| 3 | **Overloaded section, and a promise not kept.** *What* carried the four-part table, a bolted-on two-channel paragraph (a late addition), and the weekly review, which *How* step 5 repeats. *How* says "three pieces" then lists five steps and "four small pull requests". | Seams visible; the numbers disagree. | The two-channel paragraph shortened into one paragraph under the table; the weekly review left to *How* with a one-line pointer; *How* now says "the design lock, the three pieces, then the first consumer: five steps". Applied. |
| 4 | **Buried best material.** The one story a manager will repeat (the gate that failed for a day by hand and passed on the first job) sits inside a table cell. | A table cell is where a story goes to be skimmed. | Told in two sentences before the table; the table keeps the numbers. Applied. |
| 5 | **Missing steelman.** The memo argues against "a chat window", the weak alternative. The strong one is a self-hosted CI runner on the workstation, which has a schedule, secrets, notifiers and the machine. | A reader who knows CI will raise it first and stop reading if the memo has not. | A steelman paragraph at the end of *Why BATS*: the runner starts cold, so every job pays the Maya start-up the table measures, and it has no resident session, queue or manifest. Applied. |
| 6 | **The ask does not ask.** "Agreement to run..." and a closing question. | A manager wants the decision, the cost, the person and the exit condition in the first sentence. | First sentence: one person, about a week, a go or no-go after the measured first run. Applied. |
| 7 | **Internal vocabulary.** "the owner", "the board", "the journal", "the decision lock" read as jargon to the audience. | Curse of knowledge. | "the owner" became "you" or "we" where the reader is in the room; board and journal explained in passing as "the project's own documents". Applied. |
| 8 | **Endings that fire twice.** *Around the corner* closes on a claim, then three more sections. | Acceptable for a memo whose sections are scanned; the memo's real close is the ask. | Not changed. Recorded as a deliberate trade. |

## Layer 2: rejected proposals

- **Cut *Around the corner* to five bullets.** Rejected: the owner asked for it to be "super forward looking" and to "make guesses"; the section is the differentiator for this audience. Each bullet lost a clause instead.
- **Drop the brain-and-body metaphor for a plainer "the execution layer".** Rejected: the owner's own framing, and the one line a reader will repeat. Grounded instead (finding 1).
- **Turn the four-row evidence table into prose.** Rejected: the table is the credibility; the story before it is the hook.

## Layer 3: fact check

Sources are this repository's own record; no external URL is load-bearing.

| Claim | Where | Verdict | Source, or the fix |
| --- | --- | --- | --- |
| Maya's scripted launch costs about a minute of start-up | *Why BATS* table | Verified | Decision log, "Driving Maya during development"; `tools/README.md` |
| "a startup crash one launch in three" | *Why BATS* table | **UNVERIFIED** | The record says "exit 127 or 139 in the first seconds" and "run it again"; no frequency was ever counted. Softened to "a start-up crash on some launches". |
| Two GUI Mayas crash each other; a launcher bug left idle sessions; a retry loop killed a worker | *Why BATS* table | Verified | Decision log, "Rules learned the hard way"; journal session 01 |
| The gate had failed for a day the other way and passed on the first job | *Why BATS* | Verified | Handoff of 2026-09-26 (gate open); PR #18 (passed as a job the same day) |
| The v1 check was the same job with one parameter, 37 seconds | *Why BATS* table | Verified | `verification/maya-2026/ibl-check/legacy-v1/studio_small_09/maya-history.log`: "completed in 36.74s" |
| One inheritance trap costs a restart | *Why BATS* table | Verified | Knowledge file, "How the orchestrator's configuration layers" |
| The MCP exposes the same operations; twenty tools | *Why BATS* | Verified | Knowledge file, "Rules learned the hard way" (MCP validated 2026-09-26) |
| Cloud routines clone repositories, run skills, open PRs, cannot reach a workstation, have no notification of their own | *What* | Verified, second-hand | SpriteJammer `docs/design/devblog.md`, "What the cloud can and cannot do", checked against the product docs 2026-09-13 |
| A harness's remote-session feature connects a phone app to a live local session | *What* | Verified | The owner's own use of it; the harness's tool documentation |
| Telegram: free bot token, one HTTPS call out, long polling in | *How* | Asserted from standing | General knowledge of the Bot API; not load-bearing for the decision (the bridge could be any channel) |
| SMS needs sender registration | *How* | Asserted from standing, hedged in the text | US A2P rules; "verify before choosing" is in the decision log |
| One person built and maintains BATS | *Risks* | Verified | The owner |

## Layer 4: voice

Tells checked against the pipeline's list: em dashes 0 before and after; no participle clauses doing fake depth (checked each "-ing"); register consistent formal, contractions absent throughout by choice for a memo; no "It is important to note" openers; one rule-of-three that is content ("a heartbeat, a way to run, a channel": the three pieces are three). "Durable, repeatable, discoverable" kept: the owner's three words. Reader put in the room: "your morning", "you".

## Layer 5: rhythm

Paragraph mass measured, not counted. Before: 24 paragraphs, mean 62 words, longest 118 (the two-channel paragraph), three consecutive over 80 in *What*. After: mean 58, longest 96, no run of three heavy paragraphs; the one-line verdicts sit after the heavy blocks (end of *Why*, end of *Why BATS*), not after light ones. Zero word changes in this layer.

## Layer 6: reach

SUCCESs, before and after (each score names its evidence):

| Trait | Before | After | Evidence |
| --- | --- | --- | --- |
| Simple | 6 | 8 | One thesis (the body); the lead states it in four sentences |
| Unexpected | 7 | 8 | "any Python worker can do anything Python can do"; "wake up to pull requests" |
| Concrete | 7 | 8 | 37 seconds, a day, the exact Maya failures; the story before the table |
| Credible | 6 | 8 | The honest rows, the steelman, the falsification condition |
| Emotional | 5 | 6 | The gate story; the 3 a.m. job; still a memo |
| Stories | 4 | 6 | One story told, in two sentences |
| Total | 35 (strong) | 44 (strong) | |

Portable test restated in the closer: "if a step needs time, a machine, a queue, or a memory that outlives a chat window, it needs a body." Trigger: every time someone opens a chat window to run something by hand.

## Layer 7: adversarial

- **Steelman:** a self-hosted CI runner on the workstation. Answered in *Why BATS* on the one axis the table measures (a resident session) and conceded on the rest (schedule, secrets, notifiers, which a runner has today).
- **Falsification:** stated in *Risks*: a month of scheduled runs costing more babysitting than the manual path, or a report unread for a month, stops the schedule.
- **Concession that costs something:** one person built and maintains BATS; the memo says so and limits lock-in to "jobs are scripts that also run by hand".
- **Sequence honesty:** the conclusion (BATS as the body) came after the loop was split into four parts in conversation on 2026-09-27; the journal entry records the order. The memo does not claim the design preceded the evidence.

## Layer 8: scorecard

| Dimension | Before | After | Measurement |
| --- | --- | --- | --- |
| Opening hook | 6 | 8 | The metaphor grounded in the lead; the ask's decision in one sentence |
| Structural clarity | 6 | 8 | Findings 3 and 4 applied; section numbers agree |
| Thesis consistency | 5 | 8 | One thesis; two supporting lines subordinated |
| Argument integrity | 5 | 8 | Steelman and falsification added |
| Ending | 6 | 8 | The ask asks; the portable test closes |
| Evidence texture | 7 | 8 | One unverified frequency softened; the rest cited to the record |
| Em dash discipline | 10 | 10 | 0 and 0 |
| Register consistency | 8 | 9 | "the owner" removed from a memo addressed to the owner's team |
| Rhythm | 6 | 7 | Mean paragraph mass 62 to 58, longest 118 to 96 |
| Length (trend, not scored) | 1,930 words | 1,720 words | Grew in every pass of the day until this one |

## Layer 9: author review, and what it found

Owner, on the revised draft: "needs the best 'human in the loop' use cases early, which are all my
initial desires. Why would I want or need a cron job (and for what)? Why would I want a remote
interface? How does this make my life better?"

Finding 9, ranked above every other: **the memo argued the architecture before it showed a single
day being better.** Diagnosis: the author's initial desires (a Friday review with a nudge, the Maya
gate from the phone, asking the orchestrator what it can do, ideas becoming board rows that get
followed up) were scattered through *What*, *Around the corner* and *How* as features, never as
days. A manager reads for the day, not the feature. Applied: a new section, "A week with it",
directly after the lead: five concrete moments (Friday's three-line verdict, the Tuesday gate from
the phone, Wednesday's waiting pull request, thinking out loud, a new person on Monday), each naming
why a schedule or a remote channel is the thing that makes it possible and what it buys. The lead
gained one sentence saying the machinery is not the point. Every case keeps the person deciding; the
agent never merges. Then the owner named the headline case the section had missed: "here is a character I want to
produce <description>", a workflow of jobs with a human gate at each step, reviewed from anywhere
before reaching the machine. Added as the first day, and workflows moved from the long-shot list to
"plausible within a year" as the shape the Thursday case takes. Word count 1,720 to 2,240; the
growth is the author's requested content, and it displaces nothing.

Then the owner's standing rule, "tell me when my ideas are awesome or push back when meh", applied
to the document itself: **the awesome cases lead, the good ones stay with their value named, the meh
ones go.** The week section now opens with the two gated workflows (the character on Thursday, scene
direction on Saturday, which had been a bullet), then the Tuesday gate, Friday with its follow-through
loop named as the part that makes it more than a dashboard, Monday's question to the orchestrator,
and the Wednesday pull request last. The forward-looking list lost the bullets the days already
show ("the phone as a console", "wake up to pull requests"), the small ones ("the failure-modes
ledger writes itself", "synthetic datasets", "a home compute grid"), merged "replay and diff" into
"agents as jobs", and gained the two the Saturday day depends on ("workflows with human gates as
data", "in-context annotation"). Then the owner corrected the heuristic: "meh is still context, is infrastructure towards a goal."
So the rule is that verdicts order, they do not delete. The six cut bullets came back as a labelled
group, "Infrastructure the days stand on", each one saying which headline it serves. Word count
2,240 to 2,160 to 2,330. Rejected: cutting the section to three bullets, because the audience is
being asked to fund a year of the plausible ones, and because scaffolding removed from the record is
scaffolding rebuilt later.

## Second pass: the pipeline re-run over the author's additions

Everything added after finding 8 (the six days, the scaffolding group, the new bullets) had not been
through layers 1 to 7. A fresh-eyes editing session ran them, read-only, and reported; this section
records what it found and what was applied.

**Structure.** Seven findings, in cost order. (1) A promise not kept: the two lead days need a
workflow engine and the editor as a worker, which the week does not buy, and the memo said so 900
words later; the week's intro now states which days the week buys, which need the catalogue already
due, and which are a year out and the reason to start. (2) *Why* paragraph 3 restated Tuesday and
Friday, and "three pieces" named two different triads; the paragraph now points at the days and
*What* says BATS has the middle piece and is three additions short of the other two. (3) The
follow-through loop appeared three times; the Risks bullet now says the first run measures whether
the report was read. (4) Day order read as a calendar; the intro names it as the order of desire.
(5) Jargon regressions in the days: "the board", "v1", "the cook and bake"; replaced. (6) The closer
named no day; it names three now. (7) The ending fires once; unchanged.

**Facts.** Friday's three numbers were illustrative and read as reportage: "of this shape" added. "The
failure-modes ledger writes itself" assumed a ledger HogShade does not have: "a ledger that". "Every
intermediate channel" unproven: "the intermediate channels". Tuesday's "sheen at one" named a
parameter the job does not take: "the sheen up". Monday's answer is intent, not possible today; the
intro's "already due" carries that.

**Voice.** Em dashes 0, contractions 0. Four tells fixed (a lazy extreme plus pull-quote in Saturday,
a here's-what setup in Friday, an adverb in the year list, a filler in the scaffolding intro). Kept
on purpose: "it should not need your chair" and "a review, not a blank editor" (the days' verdicts);
second person inside scenes and third person in argument, stated as the rule; twenty-one bold labels
as a memo's scanning device, the one formatting fingerprint.

**Rhythm.** Mean prose paragraph 54 words, longest 105, no run over 120; the days descend in mass by
design. Zero breaks.

**Reach.** SUCCESs 47 (was 44): Simple 8, Unexpected 8, Concrete 9, Credible 7, Emotional 7, Stories
8. Title kept; no subtitle.

**Adversarial.** The next objection a pipeline lead raises: the lead days need a workflow engine, the
editor as a worker and a generator that produces a usable blockout, none of which the week buys; and
"if all four proposals are bad, is Thursday four rejections on a phone?" Answered now where the days
appear (the intro) and in Thursday: a bad generator costs a round, never a decision.

**Scorecard**, before → after → now → applied:

| Dimension | History | Measurement |
| --- | --- | --- |
| Opening hook | 6 → 8 → 8 → 8 | Lead unchanged; the days prove its claim |
| Structural clarity | 6 → 8 → 7 → 8 | Duplicates removed; horizons and order stated in the intro |
| Thesis consistency | 5 → 8 → 8 → 8 | One thesis |
| Argument integrity | 5 → 8 → 7 → 8 | The week-versus-year objection answered where raised |
| Ending | 6 → 8 → 8 → 8 | Fires once; the closer names three days |
| Evidence texture | 7 → 8 → 7 → 8 | Friday marked illustrative; the ledger and "every" corrected |
| Em dash discipline | 10 → 10 → 10 → 10 | 0 |
| Register consistency | 8 → 9 → 8 → 8 | The rule stated: "you" in scenes, third person in argument |
| Formatting tells | — → — → 7 → 7 | Bold labels kept as a deliberate trade |
| Rhythm | 6 → 7 → 7 → 7 | Mean 54, longest 105 |
| Emotional pulse | 5 → 6 → 7 → 7 | Two days with a place and a time |
| Length (trend) | 1,930 → 1,720 → 2,330 → about 2,300 prose words | The rewrites removed about 45 and added about 90 |

Rejected this pass: a subtitle (a blog move); breaking Thursday's last sentence out (orphans the
day's verdict); one voice throughout (the mix is the device).

## Layer 9, first pass: for the author

Worth your attention: the steelman paragraph (it concedes that a CI runner covers schedule, secrets and notifiers), the falsification condition in *Risks*, the softened "one launch in three", and the ask's first sentence, which now commits one person for a week. Not worth it: the clause trims in *Around the corner*, recorded above as the alternative to cutting bullets.
