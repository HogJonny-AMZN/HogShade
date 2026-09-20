# Phase 1 spec: repo hygiene

Date: 2026-09-20. Design: [../design/2026-09-20-modernization-direction.md](../design/2026-09-20-modernization-direction.md),
roadmap track B. Plan: [../plans/phase-1-hygiene.md](../plans/phase-1-hygiene.md).

## Deliverable

`HogJonny-AMZN/HogShade` is a small, licensed, documented repo whose only shader content is the two
legacy shaders, unchanged, proven to compile and to load in Maya, ready for phase 2 to build beside
them.

## Exact scope

1. **Layout.** `legacy/v1.0/` and `legacy/v2.0/` hold the 2015 and 2017 shaders byte-for-byte as
   they were under `src/Shaders/HLSL/`. `Docs/` holds the roadmap, design, specs and plans. Nothing
   else under source control except `LICENSE`, `README.md`, `.gitignore` and `.gitattributes`.
2. **Licence.** Apache 2.0, the verbatim text from apache.org. No `NOTICE` file yet; the README's
   acknowledgements carry the credits.
3. **History.** Rewritten with `git-filter-repo` to drop `testFiles/`, `images/` and
   `ShaderDevProj/` from every commit. Author, dates and messages of the surviving commits are
   untouched. Force-pushed to `master` on HogShade. Since HogShade is a fork, the GitHub repo is
   detached from the fork network afterwards (owner action, GitHub support or the "leave fork
   network" setting) so the object store actually shrinks; until then the clone is small but the
   server-side size is not.
4. **Test content.** One shader-ball scene and one licence-clean HDR under Git LFS, in
   `content/`. Which HDR is the owner's call; until it is made, the LFS set is the scene only and
   the README says so.
5. **README.** The getting-started guide the legacy repo's open issue asks for: DX11 viewport, plug-in,
   material creation, light binding, debug views, the fxc compile line. Credits carried forward.
6. **Verification.** The two legacy entry shaders compile under
   `fxc /T fx_5_0 /D _MAYA_=1` with no errors. The v2 shader loads in Maya 2026 through
   `dx11Shader` with a non-empty technique list, proven by a scripted GUI launch whose log is
   committed under `Docs/verification/`. Maya 2024 the same, when the owner runs it.
7. **The archived v3 folder.** Salvage attempted and recorded in the design doc; nothing taken;
   folder removed from the tree. The archive stays outside the repo.
8. **Legacy repo pointer.** A pull request from HogShade to `hogjonny/Maya-PBR-BRDF-VP2` that
   replaces the top of its README with a pointer to HogShade. Merging it is the owner's action from
   the legacy account. This is how the 37 stargazers and 12 forkers learn about the update.

## Out of scope

- Any change to shader source, including warnings fxc reports. Phase 2 ports; phase 1 preserves.
- Tooling, CI, `pyproject.toml`. Phase 2.
- Transferring the legacy repo. Recorded as an owner option in the roadmap; not required.

## Acceptance gate

- `git clone` of HogShade is under 5 MB excluding LFS.
- `fxc` compiles both legacy entry shaders, exit code 0.
- `Docs/verification/maya-2026-v2-load.log` shows `RESULT: OK` with at least one technique.
- The README's steps, followed on a clean Maya 2026, produce a shaded sphere.
- The pointer PR exists on the legacy repo.
