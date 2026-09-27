# Copilot review instructions for HogShade

Read [`AGENTS.md`](../AGENTS.md) first: the map and the non-negotiable rules. The standards are
[`Docs/standards/python.md`](../Docs/standards/python.md) and
[`Docs/standards/wgsl.md`](../Docs/standards/wgsl.md); the decisions are the ADRs in
[`Docs/decisions/`](../Docs/decisions/README.md); the definition of done is
[`Docs/standards/definition-of-done.md`](../Docs/standards/definition-of-done.md).

What a review here should check, in this order:

1. **The core contract** (`Docs/standards/wgsl.md`): every name in a `core/` module carries its
   prefix; no bindings or entry points in the core; every core function has a NumPy twin under
   `hogshade/reference/` and a GPU test under `tests/core/`; constants mirrored in
   `hogshade/core_constants.py`; if-chain dispatch and single returns; a legacy quirk kept on
   purpose is listed in the module header, not removed silently.
2. **Generated artifacts**: anything under `hosts/*/generated/` and `hosts/hlsl/hogshade_core.hlsl`
   is build output. A hand edit there is a finding; a stale artifact after a core change is a
   finding (`tools/build_shaders.py --check`).
3. **Hygiene**: any new match for `bluepoint`, `sony`, `bp_py` or `bp_color` outside `legacy/` is a
   hard finding. No AI attribution in commits or PR text.
4. **Claims after evidence**: a PR body or reply that says a test passed, CI is green or a picture
   was verified should point at the run, the log or the file under `verification/`.
5. **Docs in the same PR**: the plan task ticked with a verification note, the spec amended if an
   interface changed, the board row struck or added, the journal appended, the handoff current.
   `tools/check_docs.py` must pass.
6. **Python standards**: module header with `_MODULE_NAME`, absolute imports, complete type hints,
   `pathlib`, specific exceptions, no `print()` outside a script's entry point or a DCC-side script.

A job under `hogshade/jobs/` must also run without the orchestrator; the manifest's `outputs`
must match what the code writes; a path built from a parameter must refuse to climb.
