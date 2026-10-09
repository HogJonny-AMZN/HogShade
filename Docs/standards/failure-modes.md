# Failure modes

**Status:** Living. Append-only, like the ADRs.
**Last updated:** 2026-09-27 (seeded in the standards pass from this repository's own week)
**Read with:** [definition-of-done.md](definition-of-done.md), [../plan/BOARD.md](../plan/BOARD.md) "How this stays honest", [../journal/README.md](../journal/README.md)

**This is the ledger of how the work has gone wrong**, not the work. Every entry is a defect in
process this repository can prove from its own history, written as **Trigger, Do, Because** so it is
usable at the moment it applies. The shape is LargeWorlds' ledger, which took it from SpriteJammer.

It works by being read: `Docs/` is loaded before work starts, so retrieval is the enforcement.
Where a class can be mechanised, mechanise it and link the check here; the entry then says why the
check exists. Entries 3, 4, 6, 8 and 9 have checks today.

## The ledger

### 1 · A belief carried from a document instead of the record

**Trigger:** Porting, summarising or planning from a roadmap, a design doc or a README's description
of what code does.
**Do:** Read the source, the include graph, the log. Correct the document in the same change.
**Because:** The roadmap and the direction doc said the 2015 shader shipped three BRDFs. The effect
file included one; the other two could not have compiled. Found only when the port began (PR #19;
journal, session 01).

### 2 · A claim made before the evidence exists

**Trigger:** Writing "CI green", "tests pass", "carried on the board" or "passed on D3D12" into a
reply, a PR body or a review thread.
**Do:** Run the thing, read the result, then write the sentence. A checkbox ticked at open is
unticked until read.
**Because:** PR #13's D3D12 claim went out before the run finished and had to be corrected; PR #20's
CI box was ticked while CI was pending; a Copilot reply said a note was "carried on the board" before
the row existed. Each was true a few minutes later, which is not the same as true.

### 3 · A gate whose failure a pipe swallowed

**Trigger:** A command chain with `| tail`, `| head` or `| grep` after the command that decides.
**Do:** Capture the exit code (`cmd > log; rc=$?`) and test it before anything that commits or
pushes. The `review-and-pr` skill says so.
**Because:** The board's first commit went out with two failing checker tests because pytest's exit
code disappeared behind a `tail` and the chain kept going to `git push` (journal, session 01).

### 4 · A shell heredoc carrying a script it cannot quote

**Trigger:** Writing a Python script with backslashes (`\n` in strings, regex, Windows paths) inside
a Bash heredoc in an agent session.
**Do:** Write the script to a file with the Write tool and run the file.
**Because:** The Bash tool mangles backslashes inside heredocs; an edit script's anchor silently
missed and the failing state was committed (entry 3 caught the second half). LargeWorlds' ledger has
the same entry; it was re-learned here.

### 5 · A manifest nobody registered

**Trigger:** Adding a job, a model, a module, a host: anything with a registry beside it.
**Do:** Prefer discovery to a hand-kept list; where the list exists, the test that lists it fails
on a member missing from it.
**Because:** `hogshade.jobs.maya_ibl_check` carried a `MANIFEST` for a day while `JOB_MODULES`
listed only the cook, so the registry could not find it (Copilot on #19). The job-provider row on
the board is the mechanisation.

### 6 · A checker that cannot fail for part of a file

**Trigger:** Writing or trusting a check that skips regions (fenced code, excluded folders, a
`try` around a whole loop).
**Do:** Make the skip itself a finding when it swallows more than intended; test the edge (an
unclosed fence, a link above the root, a BOM).
**Because:** `tools/check_docs.py` dropped everything after an unclosed fence, so links and status
lines after a typo were unchecked and the file looked green; a `..` link resolved against whatever
sat beside the checkout. Both found by the checker's own local review (#21) and fixed with tests.

### 7 · A resident session that remembers

**Trigger:** Running a check on a long-lived DCC worker rather than a fresh process.
**Do:** Start every check from a new scene; release every file the check opened (history mirroring
off at the end); never assume the process state is yours.
**Because:** The v1 Maya check ran with the v2 sphere still in the scene, and the check left Script
Editor history mirroring on, so the worker kept the committed log open and growing; git could not
restore it (#19, #20).

### 8 · A test degeneracy blamed on the shader

**Trigger:** NaN or a wild value from a GPU test on a few rows.
**Do:** Check the harness's random inputs for coincidences (a view equal to the light after a facing
flip) before touching the shader; seed each vector family separately.
**Because:** `test_legacy_v1_gpu.py` produced NaN where the half vector was zero length; the fix was
a seed offset, not a shader change (journal, session 01).

### 9 · A path parameter that arrives from outside

**Trigger:** A job or environment parameter that becomes a directory or file name.
**Do:** Refuse `..` and anything that resolves outside the intended root, before `mkdir`; test the
climb.
**Because:** `output_dir` split the job's `variant` into path components and would have written
anywhere; the first guard only checked the resolved path and let a two-level climb land inside the
root because the probe was too weak (#20). `tests/tools/test_maya_session.py` holds the cases.

### 10 · A default assumed from another repository

**Trigger:** `gh pr create`, a branch name, a path convention, a CI leg count, carried from the last
repository worked in.
**Do:** Read the repository's own value (`git symbolic-ref refs/remotes/origin/HEAD`) and write it
into the skill that needs it.
**Because:** Two PR creates failed against `main`; this repository's default branch is `master`.
The `review-and-pr` skill now says so.

### 11 · Idea velocity outrunning landing velocity

**Trigger:** A day that adds more board rows than it strikes through; "next" unchanged for two
sessions.
**Do:** Say it out loud, then do the next landed increment before the next idea. The board exists so
the ideas keep; it does not exist so they queue forever.
**Because:** 2026-09-27 added nine Icebox rows and three design-first items while the standards pass
stayed "next" from the previous morning. The owner asked for verdicts on ideas the same day; this
entry is the verdict on the pattern.

### 12 · An author's additions that skip the review

**Trigger:** Adding a section to a reviewed document after its review pass, on the author's ask.
**Do:** Run the pass again over the additions before calling the document done; the additions
arrive with the most conviction and the least review.
**Because:** The pitch's six days and scaffolding group, added after the first editorial pass,
carried a promise the proposed week did not keep, a ledger this repository does not have, and
sample numbers reading as measurements. The second pass caught all three (`../reviews/`).

### 13 · A module named after the function it exports

**Trigger:** A package `__init__` that re-exports a function whose name equals one of its submodules
(`from pkg.validate import validate`).
**Do:** Name the module for the activity (`validation.py`) or the noun, never the verb the function
takes; a test that monkeypatches `pkg.module.name` catches it, as does `import pkg.module as m`.
**Because:** The S1 spec named `validate.py`, `resolve.py` and `convert.py` after the library functions;
Copilot's eight findings on the spec and the author both missed that `hogshade.material.validate` would
be the function once the package exported it. The tests' fake-type fixture found it on the first run
(`feat/s1-material-schema`); the rename then missed `types.py` against the exported `types()`, which the
local review caught, so the test that no exported name is a submodule's is the mechanised half.

### 14 · A reply that names a commit before the commit exists

**Trigger:** Posting a review reply, a PR comment or a status line from the same shell chain that makes
the change, with the steps joined by `;` or run after a `&&` chain that may have stopped.
**Do:** Make the change, confirm the new hash (`git log -1` differs from the previous head), and only then
compose and post anything that names it; join the steps with `&&` and `set -o pipefail`, and gate the reply
on the hash check.
**Because:** 2026-10-02, the S4 design PR (#40): a patch script failed on its first anchor, nothing was
committed, and five Copilot replies went out saying "Fixed in 3f105e6" (the previous head). Corrected on
every thread with the real commit. Entry 2 covers the claim-before-evidence class; this is the shape
where the chain itself is the claimant.

### 15 · A handoff whose header is rewritten while its reading order goes stale

**Trigger:** Updating the handoff's *Last updated* line or its sit rep without reading the lines above
them; any sentence in the handoff that names "the plan in flight" or "what is next".
**Do:** When the state changes, re-read the handoff from the top and fix every pointer, not only the
header and the sit rep; a pointer to a plan names the plan's status in the same breath (done, in flight,
none). A reader who sees "S2 is next" after S4a merged is sent to obsolete work.
**Because:** 2026-10-03, #47: the handoff said "nothing is in flight" in its sit rep while its reading order
still pointed at the S1 plan "done; S2 is next", a line last true before #34 and rewritten past five times
without being read. Copilot caught it. Mechanised half: none yet; a check that the handoff names no plan
whose status line says done is the candidate.

### 16 · A resident worker that remembers more than its scene

**Trigger:** Submitting a job to the resident GUI Maya after changing any Python the job imports, or
after another job ran with different environment variables, or with a relative path as a parameter.
**Do:** Treat the worker as a process that already ran yesterday's code: the submit stub reloads a job
module it already holds, a job drops the library modules it imports (`hogshade.material.*`) before the
check imports them, a job sets every environment key it owns and clears the ones it does not, and every
path parameter is absolute (the worker's cwd is not the repository).
**Because:** 2026-10-04, T3's build: the first gate run landed under `textures/gate/` because `HOGSHADE_CHECK`
leaked from the texture job; the five texture checks failed twice on `cannot import name maya_packed_slots`,
first because the worker held the previous job's `hogshade.material.binding`, then because it held the
previous job module itself, so the fix inside the job never ran; the gate's `fx=hosts/...` resolved against
the worker's cwd and loaded no effect. Entry 7's scene rule was kept and was not enough. Mechanised:
`tools/bats/submit.py` reloads the module, `hogshade.jobs.maya_texture_check` drops its library imports and
clears its keys; the board's environment row remains for the orchestrator side.

### 17 · A hash of a file git rewrites

**Trigger:** Recording the SHA-256 of a text file (a sidecar, a licence, a manifest) as an identity, or
comparing one across machines.
**Do:** Hash text inputs with line endings normalised (`hogshade.material.runtime.input_digest`), and pin
the files a cook or a host reads to `eol=lf` in `.gitattributes`; hash images and DDS as bytes. A hash that
passes locally and fails on the Windows runner is this, not a stale cook.
**Because:** 2026-10-04, #58: the T3 build's `content-runtime` passed on the author's machine (files written
LF by the tools) and failed on CI's Windows runner, where `core.autocrlf` checks every sidecar and
`LICENSE.md` out as CRLF, so twenty-nine inputs "changed since the cook" without a byte of content changing.
Mechanised: `input_digest` in the cook and the check, the `.gitattributes` rules, a test with CRLF inputs.

### 18 · A shell heredoc that rewrites the file it was meant to write

**When you notice** a script or a test file containing real newlines where the source had `\n`, a lost
backslash, or a `'` that ended a quoted block early, **do** write scripts and multi-line file contents with the
editor's write tool (or a file on disk) and run them from there; never pipe Python or file contents through a
bash heredoc on this Windows shell, however the heredoc is quoted.
**Because:** 2026-10-04, #62: three times in one session a quoted heredoc (`<<'EOF'`) turned `\n` inside Python
string literals into newlines or stopped at an apostrophe, once leaving a test file syntactically broken and
once silently skipping a docs patch. The fix each time was the same: the same text written as a file and run.
Not mechanised: it is the agent's tool choice, now a standing rule in the knowledge base.

### 19 · A write that fails after it has already emptied the file

**When you notice** a script that writes a file with a computed argument (an encoding, a `newline=`) you have not
run before, **do** write the new content to a temporary path first and move it over, or run the script on a copy;
and after any failed write, `git status` before the next step. Python opens a file for writing, which truncates it,
before it validates the `newline` argument, so a bad value raises with the file already empty.
**Because:** 2026-10-04, #62 and #67: a `Path.write_text(..., newline="\\n")` (a literal backslash and n, not a
newline) emptied a job test and then `tests/texture_cook/test_cook.py`; each came back from git and the lost edit was
redone. Not mechanised: it is a habit of the script author, and `git` was the safety net both times.

### 20 · A new word that never reaches the glossary

**When you notice** yourself writing a name for a concept the glossary does not hold (a module, a dataclass, an enum
value, a level or a kind, a CLI verb, a document type), **do** add its glossary row in the same change and before the
code that uses it, and end every design, spec and plan with the terms it introduces (or "none"). A word used in
three documents and a package without a row is a word whose meaning only the author holds; "oracle" already means
something else in LargeWorlds.
**Because:** 2026-10-08, the comparison framework: the design (#73), the C-2 spec (#74) and the build all used oracle,
control, capture set, capture level, verdict and a dozen more with no glossary row until the owner asked mid-build
("oracle is not a term in the glossary"). `AGENTS.md` already says "a new concept gets its word in the glossary first";
the rule was read at the start of the session and not at the moment of coining. **Mechanised** (the owner, 2026-10-08,
"best recommendations"): the docs check's `terms` check fails a design, spec or plan without a `## Terms introduced`
section or naming a term with no glossary row; the PR template has the checkbox; the review rubric names the finding.
It cannot see a word coined only in code, which is what the checkbox and the rubric are for.

### 21 · A hash of floats that pins one machine's arithmetic

**When you notice** yourself pinning the SHA-256 of an array's bytes that came out of floating-point arithmetic (a
matrix, a packed uniform, a rendered frame), **do** recompute the same value in the test by the original formula and
compare the two (exactly, on the same machine, or with a stated tolerance across them); keep a hash for bytes that are
read, never computed. A computed float's last bits depend on the numpy build, the CPU and the compiler, so a hash taken
on your machine fails on CI for no reason a reader can act on.
**Because:** 2026-10-08, #76: three tests pinned the SHA-256 of `Scene.frame_bytes` for the orbit camera, taken on the
owner's machine, and failed on the Windows CI leg with different bytes; they were replaced by the original look-at and
perspective written out in the test. Not mechanised: it is a habit, and CI is the check that caught it.

## How to add an entry

When process fails again, append in the same PR as the fix: a trigger you would notice, the action
it should cause, and the PR or commit that proves it. Mechanise the class when a check can, and
link the check. Never rewrite an old entry; add a new one that supersedes it.
