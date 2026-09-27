# BATS as the agent's body

**Status:** Proposed. A pitch written 2026-09-27 for the owner's team, to be sent when the owner
chooses; revised the same day through the CO3DEX editorial pipeline
([the plan](../reviews/2026-09-27-pitch-editorial-plan.md) records what changed and what was rejected).
The same text lives as a shared document the owner can edit. The board row "The agent loop as
research" and the decision log entry of the same name hold the working detail behind it.

Date: 2026-09-27. Author: the owner.

AI agents think well and persist badly. The harness that reads a repository, plans, edits, tests and
opens a pull request is the brain, and it gets better every quarter without our effort. What it lacks
is a body: something that starts work on a schedule, runs it on the machine with the DCC on it, and
tells a person when it is done. BATS already is most of that body. Three small additions finish it, and the point of finishing it is
not the machinery. It is a week that reads differently.

## A week with it

Before the architecture, the days it changes, in the order I want them rather than the order they
arrive. Every case keeps a person in the loop: the agent proposes and runs, the person reads and
decides, and nothing merges or ships without a human. Three of the six (Tuesday, Friday, Wednesday)
come from the week of work proposed below. Monday needs a job catalogue the orchestrator is already
due. The first two are a year further out and need pieces named under "Around the corner"; they are
the reason to start.

**Thursday, on the train.** You send "produce a character: <a paragraph describing it>". A workflow
starts: concept images, a blockout, a textured model, a turntable rendered in the DCC or in the
editor, each step a job. At every gate the result reaches your phone and waits. The generative step
never decides alone: it proposes four, you pick one. If none of the four is right, the sentence you
send back is the next job's brief and the workflow waits; a bad generator costs you a round, never a
decision. You approve the concept, send the blockout back with one sentence, approve the rest, and
the final turntable is waiting when you reach your desk. The machine can do each step; the judgement
at each step is yours, and it should not need your chair.

**Saturday, on holiday.** "Show me the witch's hut" returns an in-editor render of a named view.
"Warm the light and move the cart left" starts a workflow: four proposals, your pick, the texture
cook and the bake, the editor loads and places the result, and the same view renders again onto your
phone. The instruction channel is your phone's own markup on the picture plus a sentence, read by a
vision model. Direction happens on a picture; this one arrives where you are.

**Tuesday, away from the desk.** A shader change needs the Maya gate. "Run the IBL check on the 2015
model" from your phone; the resident worker runs it while you are out and the picture comes back.
"Again with the sheen up" is a second job. The machine has the DCC, the GPU and the licence; you do
not always have the desk. Verification stops waiting for you to sit down.

**Friday, 4 p.m.** Three lines and a link, of this shape: CI got 40 seconds slower this week and the
commit that did it; the Maya check was run by hand three times and is a one-line job now; the export
experiment from August never proved out and is still described as current in two documents. Monday
opens with that list. A review is the one task nobody books for themselves, and it has to read the
week whole, which no single session sees from inside. Every report opens with last week's items and
whether you acted on them, which is what makes it more than a dashboard.

**Monday, a new person or a new agent.** "What can this pipeline do?" is a question the running
orchestrator answers with its jobs, their parameters and what each produces. A week of reading and
asking becomes one call.

**Wednesday, 9 a.m.** A pull request is waiting that you did not write: the smallest ready item on
the project's board, built overnight behind an allowlist, with its tests. Your morning is a review,
not a blank editor. If it is wrong you say so and it is gone; nothing landed.

Those six days are the whole case. The rest of this memo says why they are not possible today, what
makes them possible, and what it costs to find out.

## Why

Every team that has put a coding agent to work hits the same wall next: the agent lives inside a
chat session. When the session ends, so do the schedule, the process it was driving and the thread to
the person who asked.

So each team rebuilds the same three pieces by hand: a heartbeat that starts work without a person
typing, a way to run that work where the DCCs and the GPUs are, and a channel that tells a person the
result and takes an answer back. Built per project, they are fragile scripts. Built once, they are
infrastructure.

The cost of not having them never shows on a timesheet; Tuesday and Friday above are what it looks
like. Generation is cheap now. Reading and following up is the expensive half, and nothing owns it.

## Why BATS

BATS already is the execution half. It runs resident DCC workers (Maya headless and GUI, Blender,
Houdini, a plain Python environment) behind a queue, takes a job as a script or as a Python module
with an entry point, carries a manifest per job that says what it needs and what it produces, and
exposes the same operations to an AI agent through an MCP server. A project keeps its own worker
profile and launcher; downstream users never need it.

This week's evidence is one afternoon. A DirectX 11 effect had to be proven to load and light in
Maya 2026, and a day of scripted Maya launches could not do it: a minute of start-up per attempt,
crashes on some launches, idle sessions left behind by a launcher bug, two GUI sessions crashing each
other. The same check, submitted as a job to a resident GUI worker, passed the first time.

| What was needed | Without the orchestrator | Through it |
| --- | --- | --- |
| Prove the effect loads and lights in Maya 2026 | A scripted launch per attempt: about a minute of start-up, a start-up crash on some launches, idle sessions, two GUI sessions crashing each other | One job on a resident GUI worker with the viewport device forced by the profile; the technique list and Maya's own compile log came back in the result |
| The same check for a second shading model | A second campaign of the same hazards | The same job with one parameter, 37 seconds |
| A new session, human or agent, running any of it | Rediscover worker types, environment layering and one inheritance trap that costs a restart | The profile and environment files are generated and committed; a session reads one page and submits |
| An agent driving the DCC | An ad hoc bridge per session with no queue, no manifest and no history | The MCP tools submit to the same durable queue people use, and every job leaves a manifest and a log |

The honest rows are there too: a GPU test suite and a shader build run in-process and gained nothing
from the orchestrator. It earns its place where a session is expensive to start, where a step must be
repeatable, and where a record must outlive the person who ran it.

The strongest alternative is not a chat window. It is a self-hosted CI runner on the workstation,
which already has a schedule, secrets, notifiers and the machine. What it does not have is a resident
session: a runner starts cold, so every job pays the Maya start-up the table measures, and it offers
an agent no queue to inspect, no manifest per job, and no way to hand a live session a second task.
BATS keeps the DCC open between jobs. That is the whole difference, and it is the one the numbers
above are about.

## What

An agent loop has four parts, and no single substrate has all four. Cloud-hosted agent routines can
clone repositories, run a project's skills and open pull requests on a schedule, but they cannot
reach a workstation, so nothing that needs Maya, a GPU or a bake. BATS reaches the workstation but
has no heartbeat and no channel to a person. The split falls out cleanly:

| Part of the loop | Repository-only work | Work that needs the workstation |
| --- | --- | --- |
| Trigger | A cloud routine on a schedule, or a CI workflow on a cron | A scheduled-job type in BATS: a heartbeat is a job that submits jobs |
| Context | The project's own documents: its journal, board and handoff | The same, plus the orchestrator's state and the manifest of every job |
| Act | A skill committed in the repository | The coding harness in headless mode, run as a BATS job on a Python worker, behind a permission allowlist |
| Report and nudge | A branch and a pull request | The same, plus a message to the person with the verdict and the link, and their reply coming back as a submitted job |

So BATS has the middle of those three pieces and is three small additions short of the other two: a
scheduled-job type, the harness as a worker job, and a messaging bridge. The brain stays the
harness. BATS is the body: durable, repeatable, discoverable, and already ours.

The channel already has one half. A harness's remote-session feature puts a live session on the
workstation into your phone: you submit a job and walk away. That session ends when you close it, so
the bridge covers the other half, the job that finishes at 3 a.m. with nobody watching and the worker
that is not the harness at all. BATS sits under both as the part that persists, which is what makes
"almost anything from the phone" a routing question rather than a new system. The first consumer of
the whole loop is the weekly review in step 5 below.

## Around the corner: what a body makes possible

Guesses, labelled by confidence, and the point of the experiment is to find out which are right.
The common thread: a Python worker can do anything Python can do, so "DCC job runner" is the first
use, not the shape of the thing. What a chat session cannot give an agent is time, a machine, a
queue and a memory that outlives the window. Once it has those, the following stop being ideas. The
six days above are the ones that already earned their place; these are the ones behind them.

**Likely within a quarter of the three pieces landing**

- **Every shader change verified in every host before a human looks.** A pull request that touches
  the core fires a job that renders the calibration scene in Maya, wgpu and Blender on the
  workstation and posts the diff report back to the PR. The comparison framework becomes a service.
- **Overnight sweeps nobody would run by hand.** Roughness by metalness by environment across the
  shader ball, thousands of captures, a perceptual-difference atlas in the morning with the outliers
  ranked. The agent proposes the sweep, the worker runs it in idle hours, the agent files the
  findings.
- **Cross-repo grooming.** One weekly agent reads four repositories' journals and boards, finds the
  belief in one that a measurement in another has since contradicted, and files it. Today that
  contradiction waits for a human to remember both.

**Plausible within a year**

- **Workflows with human gates as data.** The Thursday and Saturday workflows are lists of jobs with
  edges, and a gate is a message out and a reply in. Once jobs carry typed inputs and outputs, a
  workflow is data the orchestrator runs, pauses at each gate, and resumes on your word from
  anywhere. This is the piece the two best days above are waiting on.
- **Look-dev by optimisation.** An agent adjusts material parameters toward a reference photograph
  by measuring a perceptual metric on each render, iterating through the resident Maya session. A
  closed loop with the DCC inside it, which a cloud agent cannot have.
- **A local model as a worker type.** A GPU worker hosting a vision or language model becomes a job
  type: read the markup on a Saturday render, caption every capture, judge a diff, triage a log, at
  no API cost and with private data never leaving the machine. The harness keeps the hard reasoning;
  the local model takes the volume.
- **Agents as jobs, jobs as agents.** A reviewer, a verifier and a writer are worker roles that hand
  off through the queue, each leaving a manifest and a log. Every hand-off is durable, inspectable
  and replayable, so two runs of the same task can be diffed. Multi-agent work, and reproducibility
  for it, on infrastructure that already exists.

**Long shots worth naming**

- **The editor, and the engine, as workers.** An editor or a runtime with a command bus registered as
  a worker type, so an agent can load and place an asset in a named view, run the game, drive the
  camera and capture profiles. Saturday's day waits on this one.
- **In-context annotation.** Once the marks people make on a Saturday render are known, a tool that
  understands the view's depth and objects turns a stroke into a placement or a light move directly.
  The generation after phone markup, not before it.
- **The same body at home and at work.** Worker types, manifests and jobs are the contract. A job
  proven on a home orchestrator runs unchanged on a studio one, so experiments happen where the risk
  is small and results land where they are needed.

**Infrastructure the days stand on**

None of these is a headline. Each is a piece the headlines need, and the record keeps them.

- **The phone as a console.** "Status" returns the pool; "render the ball in v1 with sheen at one"
  returns the picture. The routing every gated workflow reuses.
- **Wake up to pull requests.** The nightly job that builds the smallest ready item behind the
  allowlist is the same worker job the Thursday workflow runs, exercised on the safest work first.
- **Replay and diff two agent runs.** Every agent action is a job with inputs, a manifest and a log;
  two runs of the same task can be diffed. The property that makes a gated workflow auditable.
- **A failure-modes ledger that writes itself.** A failed job gets a diagnosis job, a proposed
  ledger entry and a fix as a pull request. How the body learns from its own runs.
- **Synthetic datasets with ground truth.** The debug views already expose the intermediate
  channels; a worker renders thousands of labelled views overnight. Training data for the local
  vision model above, from the same shader the game ships.
- **A home compute grid.** Workers on every machine in the house, the target-spec one included, so
  benchmarks run nightly on the hardware the game is budgeted against. The queue does not care which
  box answers.

Each of these is a guess about value, and most need the design lock's answers before they are safe.
The claim is narrower than the list: none of them is possible without a durable body, and all of them
are ordinary Python once there is one.

## How

The design lock, the three pieces in the order that keeps risk lowest, then the first consumer: five
steps, each behind a gate.

1. **Design lock, half a day.** One page that answers the permission model (an allowlist per job,
   never the harness's skip-all flag), the blast radius (a job may write a branch and a report and
   nothing else, enforced by the worker's environment), the cost ceiling per run, and which channel.
   Nothing is built before this is agreed.
2. **The messaging bridge, one day.** One job any other job can call to send a message, and a poller
   that turns a reply into a submitted job. Telegram first: a free bot token, one HTTPS call out, long
   polling in, two-way. SMS through a carrier API is the alternative if a phone number is required,
   at the cost of sender registration. Gate: a job sends a message and a reply submits a job.
3. **A scheduled-job type, half a day.** A job that submits jobs on a cron, with a missed-start policy
   so a heartbeat missed while the machine slept fires on wake instead of being lost. Gate: a schedule
   fires twice on time and once after a missed window.
4. **The harness as a worker job, one to two days.** Headless mode on a Python worker, the repository
   cloned fresh, an allowlist, a branch and a pull request as the only outputs. This is the risky
   piece and the last one. Gate: a run that tries something outside its allowlist is refused and the
   refusal is in the log.
5. **The weekly review, one to two days.** A Friday job reads the week's journal, board, pull
   requests and CI history, writes a report on what to streamline and which experiments did not prove
   out, opens it as a pull request, and sends one message with the three-line verdict. Each report
   opens with last week's items and whether they were acted on. First run measured: duration, cost,
   whether the report was read.

Repository-only work keeps its cloud lane; the workstation lane is for anything that needs a DCC or a
GPU. Total: about a week of one person's time, spread over the design conversation and four small
pull requests on the orchestrator.

## Risks, and what this does not do

- **Unattended execution on a workstation is a different risk class from a cloud routine writing to
  a branch.** The allowlist, the branch-and-PR-only rule and the refusal log are the whole answer,
  and they are the gate on step 4. Until they exist, no agent runs unattended on a machine with
  production access.
- **The workstation has to be up.** A missed heartbeat fires on wake, and repository-only work has
  the cloud lane, so an off machine costs a delay, not a lost run.
- **Cost per run is unknown until measured.** Step 5's first run is measured before a schedule is
  committed to.
- **A report nobody reads is the failure mode this exists to end.** The message carries the verdict,
  not "report ready", and the first run measures whether the report was read.
- **One person built and maintains BATS.** The jobs are scripts that also run by hand from a
  committed file, so nothing built here is locked to it; but the orchestrator itself has one
  maintainer, and this experiment adds three features to it.

What would end it: if a month of scheduled runs costs more babysitting than the manual path it
replaced, or the weekly report goes unread for a month, the schedule stops and the pieces stay as
ordinary tools. It does not replace the coding harness, does not put the agent's judgement in the
orchestrator, does not merge anything, and does not make BATS a dependency for anyone downstream.

## The ask

One person, about a week, and a go or no-go after the measured first run: that is the whole
commitment. The result either way is a written answer to a question every pipeline team is about to
face: where does an agent live when it is not in a chat window?

The test to carry out of this memo is short. If a step needs time (Friday), a machine (Tuesday), a
queue (Thursday), or a memory that outlives a chat window, it needs a body. Today that body is
rebuilt by hand, per project, or not at all.