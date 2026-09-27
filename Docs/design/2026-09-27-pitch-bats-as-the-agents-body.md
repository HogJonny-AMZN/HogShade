# BATS as the agent's body

**Status:** Proposed. A pitch written 2026-09-27 for the owner's team, to be sent when the owner
chooses; the same text lives as a shared document the owner can edit. The board row "The agent loop
as research" and the decision log entry of the same name hold the working detail behind it.

Date: 2026-09-27. Author: the owner.

AI agents now do the thinking well and the durability badly: nothing schedules them, nothing runs
them on the machine with the DCC on it, and nothing tells a person the work is done. BATS already
owns two thirds of that, and three small additions make it the durable body every agent in the
pipeline runs on.

## Why

The thinking half of agentic tooling is solved well enough to stop building it. A coding harness
reads a repository, plans, edits, tests and opens a pull request, and it does so better each
quarter. Every team that has tried it hits the same wall next: the agent lives inside a chat
session. When the session ends, so do the schedule, the process it was driving and the thread to
the person who asked.

So each team rebuilds the same three pieces by hand: a heartbeat that starts work without a person
typing, a way to run that work where the DCCs and the GPUs are, and a channel that tells a person
the result and takes an answer back. Built per project, they are fragile scripts. Built once, they
are infrastructure.

The cost of not having them is paid in small pieces and never shows on a timesheet: a check that
only runs when someone remembers, a Maya session launched by hand for every verification, a report
nobody read because nothing told them it existed. Generation is cheap now. Reading and following up
is the expensive half, and it is the half nothing owns.

## Why BATS

BATS already is the execution half. It runs resident DCC workers (Maya headless and GUI, Blender,
Houdini, a plain Python environment) behind a queue, takes a job as a script or as a Python module
with an entry point, carries a manifest per job that says what it needs and what it produces, and
exposes the same operations to an AI agent through an MCP server. A project keeps its own worker
profile and launcher; downstream users never need it.

The evidence from one shader project, this week:

| What was needed | Without the orchestrator | Through it |
| --- | --- | --- |
| Prove a DirectX 11 effect loads and lights in Maya 2026 | A scripted Maya launch per attempt: about a minute of startup, a startup crash one launch in three, idle sessions left behind by a launcher bug, two GUI sessions crashing each other | One job on a resident GUI worker with the viewport device forced by the profile; the technique list and Maya's own compile log came back in the result. The gate had failed for a day the other way and passed on the first job |
| The same check for a second shading model | A second campaign of the same hazards | The same job with one parameter, 37 seconds |
| A new session, human or agent, running any of it | Rediscover worker types, environment layering and one inheritance trap that costs a restart | The profile and environment files are generated and committed; a session reads one page and submits |
| An agent driving the DCC | An ad hoc bridge per session with no queue, no manifest and no history | The MCP tools submit to the same durable queue people use, and every job leaves a manifest and a log |

The honest rows are there too: a GPU test suite and a shader build run in-process and gained
nothing from the orchestrator. It earns its place where a session is expensive to start, where a
step must be repeatable, and where a record must outlive the person who ran it.

## What

An agent loop has four parts, and no single substrate has all four. Cloud-hosted agent routines can
clone repositories, run a project's skills and open pull requests on a schedule, but they cannot
reach a workstation, so nothing that needs Maya, a GPU or a bake. BATS reaches the workstation but
has no heartbeat and no channel to a person. The split falls out cleanly:

| Part of the loop | Repository-only work | Work that needs the workstation |
| --- | --- | --- |
| Trigger | A cloud routine on a schedule, or a CI workflow on a cron | A scheduled-job type in BATS: a heartbeat is a job that submits jobs |
| Context | The project's own documents: journal, board, handoff, decision log | The same, plus the orchestrator's state and the manifests of every job |
| Act | A skill committed in the repository | The coding harness in headless mode, run as a BATS job on a Python worker, behind a permission allowlist |
| Report and nudge | A branch and a pull request | The same, plus a message to the person with the verdict and the link, and their reply coming back as a submitted job |

So BATS is three small pieces short of the whole loop: a scheduled-job type, the harness as a
worker job, and a messaging bridge. The brain stays the harness, which is the part that improves
every quarter without our effort. BATS is the body: durable, repeatable, discoverable, and already
ours.

The first consumer is a weekly review: a Friday job reads the week's journal, board, pull requests
and CI history, writes a report on what to streamline and which experiments did not prove out,
opens it as a pull request, and sends one message with the three-line verdict. Each report opens
with last week's items and whether they were acted on, because a report nobody reads is worse than
none.

## How

Design first, then the three pieces in the order that keeps risk lowest, each behind a gate.

1. **Design lock, half a day.** One page that answers the permission model (an allowlist per job,
   never the harness's skip-all flag), the blast radius (a job may write a branch and a report and
   nothing else, enforced by the worker's environment), the cost ceiling per run, and which channel.
   Nothing is built before this is agreed.
2. **The messaging bridge, one day.** One job any other job can call to send a message, and a
   poller that turns a reply into a submitted job. Telegram first: a free bot token, one HTTPS call
   out, long polling in, two-way. SMS through a carrier API is the alternative if a phone number is
   required, at the cost of sender registration. Gate: a job sends a message and a reply submits a
   job.
3. **A scheduled-job type, half a day.** A job that submits jobs on a cron, with a missed-start
   policy so a heartbeat missed while the machine slept fires on wake instead of being lost. Gate: a
   schedule fires twice on time and once after a missed window.
4. **The harness as a worker job, one to two days.** Headless mode on a Python worker, the
   repository cloned fresh, an allowlist, a branch and a pull request as the only outputs. This is
   the risky piece and the last one. Gate: a run that tries something outside its allowlist is
   refused and the refusal is in the log.
5. **The weekly review, one to two days.** The skill, the report contract, the follow-through loop.
   First run measured: duration, cost, whether the report was read.

Repository-only work keeps its cloud lane; the workstation lane is for anything that needs a DCC or
a GPU. Total: about a week of one person's time, spread over the design conversation and four small
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
  not "report ready", and every report opens with last week's items. If that loop does not close
  after a month, the schedule is stopped rather than left running.

It does not replace the coding harness, does not put the agent's judgement in the orchestrator, does
not merge anything, and does not make BATS a dependency for anyone downstream. Everything a job runs
also runs by hand from a committed script.

## The ask

Agreement to run the design lock and the first three pieces as a bounded experiment, about a week of
one person's time, with the weekly review as the first consumer and a measured first run before
anything is scheduled for good. The result either way is a written answer to a question every
pipeline team is about to face: where does an agent live when it is not in a chat window?
