# Review rubric (canonical)

The single source of truth for the local standards reviewer. Nine generic metrics from SpriteJammer's
rubric, plus one for HogShade's WGSL core contract, scored only when the scope touches `core/`.

## Metrics

Score each metric **1 to 10**. Mark a metric `n/a` when it does not apply to the code under review;
do not score it.

| Metric | Focus |
| --- | --- |
| Design | Interface and API shape, cohesion, single-purpose units, YAGNI |
| Architecture | Fit with existing patterns; the package boundaries (`core/`, `hogshade/`, `hosts/`, `tools/`); coupling; reuse over reinvention |
| Readability | Naming, structure, matches the surrounding style |
| Maintainability | Cost of change, testability, isolation; a job is never the only way to run something |
| Performance | Obvious waste; per-texel and per-pixel cost in the core and the cook; allocations in hot loops |
| Security | Input trust boundaries, paths from environment variables, no `eval`/`exec`, no secrets, nothing that reads outside the repo root without saying so |
| Error handling | Specific exception types, context on re-raise across layers, empty and None paths; a check writes its log before its pictures so a crash leaves evidence |
| Logging | Consistent `_LOGGER` use, appropriate levels, no stray `print()` outside a script's own entry point; no emoji |
| Coding standards | 120 columns, absolute imports, type hints, module header, `pathlib` for paths with `str()` only at an API boundary, reST docstrings |
| Core contract | *When `core/` is in scope*: the prefix rule, parameters not globals, NumPy twin and GPU test, mirrored constants, if-chain dispatch and single returns, generated artifacts current, kept quirks documented |

## Baseline

**7/10 per metric is the bar** a change should clear. Call out every metric scoring **below 7** with a
concrete fix and a `file:line` anchor. **Do not inflate scores to be agreeable**: an honest 5/10 with a
clear path to 8 is more useful than a polite 7. Prefer the repository's discovered standards over
generic preference; where they are silent, apply idiomatic defaults for the language.

Two findings are hard regardless of score: a new hygiene-grep match outside `legacy/`, and a stale
generated artifact after a core change.

## Output template

Return exactly this shape (drop *Below baseline* if nothing is under 7):

```
## Local Standards Review — <mode> (<target>)

| Metric | Score | Notes |
|--------|:-----:|-------|
| Design | 8/10 | <one line> |
| Architecture | 7/10 | <one line> |
| Readability | 9/10 | <one line> |
| Maintainability | 7/10 | <one line> |
| Performance | n/a | <why not applicable> |
| Security | 8/10 | <one line> |
| Error handling | 6/10 | <one line> |
| Logging | 8/10 | <one line> |
| Coding standards | 7/10 | <one line> |
| Core contract | n/a | <why not applicable> |

### Hard findings
- <hygiene or stale artifact, or "none">

### Below baseline (< 7)
- **Error handling** (`path/to/file.py:42`) — <what is wrong> → <concrete fix>

### Verdict
<pass | needs work> — <1–2 sentence summary>. Lowest applicable metric: <x>/10.
```
