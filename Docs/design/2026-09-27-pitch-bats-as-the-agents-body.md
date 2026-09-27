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

Before the architecture, the days it changes. Every case below keeps a person in the loop; the
agent proposes and runs, the person reads and decides, and nothing merges without a human.

**Thursday, on the train.** You send "produce a character: <a paragraph describing it>". A workflow
starts: concept images, a blockout, a textured model, a turntable rendered in the DCC or in the
editor, each step a job. At every gate the result reaches your phone and waits. You approve the
concept, send the blockout back with one sentence, approve the rest, and the final turntable is
waiting when you reach your desk. Why a workflow with gates: the machine can do each step; the
judgement at each step is yours, and it should not need your chair.

**Friday, 4 p.m.** Your phone shows three lines and a link: CI got 40 seconds slower this week and
the commit that did it; the Maya check was run by hand three times and is a one-line job now; the
export experiment from August never proved out and is still described as current in two documents.
You read it on the couch. Monday opens with that list instead of reconstructing the week from
memory. Why a schedule: a review is the one task nobody books for themselves, and it has to read the
week whole, which no single session can see from inside.

**Tuesday, away from the desk.** A shader change needs the Maya gate. You send "run the IBL check on
v1" from your phone; the resident worker runs it while you are out and the picture comes back. A
reply, "again with sheen at one", is a second job. Why remote: the machine has the DCC, the GPU and
the licence, and you do not always have the desk. Verification stops waiting for you to sit down.

**Wednesday, 9 a.m.** A pull request is waiting that you did not write: the smallest ready item on
the board, built overnight behind an allowlist, with its tests. Your morning is a review, not a blank
editor. If it is wrong you say so in the review and it is gone; nothing landed.

**Any day, thinking out loud.** You mention a feature in passing. It lands on the board with a cost,
not in the code, and next Friday's report opens with last week's items and whether you acted on them.
The follow-up is enforced by the report, not by anyone's memory.

**A new person, or a new agent, on Monday.** "What can this pipeline do?" is a question the running
orchestrator answers with its jobs, their parameters and what each produces, instead of a week of
reading and asking.

Those six days are the whole case. The rest of this memo says why they are not possible today,
what makes them possible, and what it costs to find out.

## Why

Every team that has put a coding agent to work hits the same wall next: the agent lives inside a
chat session. When the session ends, so do the schedule, the process it was driving and the thread to
the person who asked.

So each team rebuilds the same three pieces by hand: a heartbeat that starts work without a person
typing, a way to run that work where the DCCs and the GPUs are, and a channel that tells a person the
result and takes an answer back. Built per project, they are fragile scripts. Built once, they are
infrastructure.

The cost of not having them is paid in small pieces and never shows on a timesheet: a check that only
runs when someone remembers, a Maya session launched by hand for every verification, a report nobody
read because nothing told them it existed. Generation is cheap now. Reading and following up is the
expensive half, and nothing owns it.

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

So BATS is three small pieces short of the whole loop: a scheduled-job type, the harness as a worker
job, and a messaging bridge. The brain stays the harness. BATS is the body: durable, repeatable,
discoverable, and already ours.

The channel already has one half. A harness's remote-session feature puts a live session on the
workstation into your phone: you submit a job and walk away. That session ends when you close it, so
the bridge covers the other half, the job that finishes at 3 a.m. with nobody watching and the worker
that is not the harness at all. BATS sits under both as the part that persists, which is what makes
"almost anything from the phone" a routing question rather than a new system. The first consumer of
the whole loop is the weekly review in step 5 below.

## Around the corner: what a body makes possible

These are guesses, labelled by confidence, and the point of the experiment is to find out which are
right. The common thread: a Python worker can do anything Python can do, so "DCC job runner" is the
first use, not the shape of the thing. What a chat session cannot give an agent is time, a machine, a
queue and a memory that outlives the window. Once it has those, the following stop being ideas.

**Likely within a quarter of the three pieces landing**

- **Every shader change verified in every host before a human looks.** A pull request that touches
  the core fires a job that renders the calibration scene in Maya, wgpu and Blender on the
  workstation and posts the diff report back to the PR. The comparison framework becomes a service.
- **Overnight sweeps nobody would run by hand.** Roughness by metalness by environment across the
  shader ball, thousands of captures, a perceptual-difference atlas waiting in the morning with the
  outliers ranked. The agent proposes the sweep, the worker runs it in idle hours, the agent files
  the findings.
- **Wake up to pull requests.** A nightly job takes the smallest ready item on the board, builds it
  behind the allowlist, and opens the PR. Your morning starts with a review, not a blank editor. The
  allowlist makes this safe; the queue makes it auditable.
- **The phone as a console.** A message says "render the ball in v1 with sheen at one" and the
  picture comes back. "Status" returns the pool. A voice memo becomes a journal entry through a
  transcription job. Each is a job the bridge already routes.
- **Cross-repo grooming.** One weekly agent reads four repositories' journals and boards, finds the
  belief in one that a measurement in another has since contradicted, and files it. Today that
  contradiction waits for a human to remember both.

**Plausible within a year**

- **Look-dev by optimisation.** An agent adjusts material parameters toward a reference photograph by
  measuring a perceptual metric on each render, iterating through the resident Maya session. A
  closed loop with the DCC inside it, which is exactly what a cloud agent lacks.
- **Synthetic datasets with ground truth for free.** The models' debug views already expose every
  intermediate channel. A worker renders thousands of views with normals, roughness, AO and material
  IDs as separate outputs: a labelled dataset for a material-estimation model, produced overnight by
  the same shader the game ships.
- **A local model as a worker type.** A GPU worker hosting a vision or language model becomes a job
  type: caption every capture, judge a diff, triage a log, summarise the week, at no API cost and
  with private data never leaving the machine. The harness keeps the hard reasoning; the local model
  takes the volume.
- **Workflows with human gates.** The Thursday character above is a list of jobs with edges, and a
  gate is a message out and a reply in. Once jobs carry typed inputs and outputs, a workflow is data
  the orchestrator runs, pauses at each gate, and resumes on your word from anywhere.
- **Agents as jobs, jobs as agents.** A reviewer, a verifier and a writer are worker roles that hand
  off through the queue, each leaving a manifest and a log. The queue is the message bus, and every
  hand-off is durable, inspectable and replayable. Multi-agent work on infrastructure that already
  exists.
- **Replay and diff two agent runs.** Every agent action is a job with inputs, a manifest and a log,
  so two runs of the same task can be replayed and diffed. Reproducibility for AI work, which chat
  sessions cannot have, comes free.
- **The failure-modes ledger writes itself.** When a job fails, a diagnosis job reads the log,
  proposes the ledger entry and the fix, and opens both as a pull request.

**Long shots worth naming**

- **A home compute grid.** Workers on every machine in the house, including the target-spec one, so
  benchmarks run nightly on the hardware the game is budgeted against instead of the one it is
  developed on. The queue does not care which box answers.
- **The engine as a worker.** A game runtime with a command bus registered as a worker type, so an
  agent can run the game, drive the camera, capture profiles and file the regression before anyone
  plays a build. An agent that can play is an agent that can test.
- **A pipeline that improves while you sleep, on purpose.** The weekly review proposes, the nightly
  job builds the smallest proposals, the morning review accepts or reverses, and the ledger records
  what did not prove out. A year of that is a year of measured decisions the next person, or the next
  agent, can read.
- **The same body at home and at work.** Worker types, manifests and jobs are the contract. A job
  proven on a home orchestrator runs unchanged on a studio one, so experiments happen where the risk
  is small and results land where they are needed.

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

- **Unattended execution on a workstation is a different risk class from a cloud routine writing to a
  branch.** The allowlist, the branch-and-PR-only rule and the refusal log are the whole answer, and
  they are the gate on step 4. Until they exist, no agent runs unattended on a machine with production
  access.
- **The workstation has to be up.** A missed heartbeat fires on wake, and repository-only work has the
  cloud lane, so an off machine costs a delay, not a lost run.
- **Cost per run is unknown until measured.** Step 5's first run is measured before a schedule is
  committed to.
- **A report nobody reads is the failure mode this exists to end.** The message carries the verdict,
  not "report ready", and every report opens with last week's items.
- **One person built and maintains BATS.** The jobs are scripts that also run by hand from a committed
  file, so nothing built here is locked to it; but the orchestrator itself has one maintainer, and
  this experiment adds three features to it.

What would end it: if a month of scheduled runs costs more babysitting than the manual path it
replaced, or the weekly report goes unread for a month, the schedule stops and the pieces stay as
ordinary tools. It does not replace the coding harness, does not put the agent's judgement in the
orchestrator, does not merge anything, and does not make BATS a dependency for anyone downstream.

## The ask

One person, about a week, and a go or no-go after the measured first run: that is the whole
commitment. The result either way is a written answer to a question every pipeline team is about to
face: where does an agent live when it is not in a chat window?

The test to carry out of this memo is short. If a step needs time, a machine, a queue, or a memory
that outlives a chat window, it needs a body. Today that body is rebuilt by hand, per project, or not
at all.
