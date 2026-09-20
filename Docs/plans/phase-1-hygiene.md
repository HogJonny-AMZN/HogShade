# Phase 1 plan: repo hygiene

Spec: [../specs/phase-1-hygiene.md](../specs/phase-1-hygiene.md). Branch: `chore/hygiene`, then a
separate force-push for the history rewrite. Tick a task only when its verification ran.

## Tasks

- [x] 1. Compile both legacy entry shaders with fxc. Verified: exit 0, warnings only, 2026-09-20.
- [x] 2. Salvage check on the archived v3 includes. Verified: 6 of 11 compile, all reformats, nothing
      taken; recorded in the design doc.
- [x] 3. `git mv` v1.0 and v2.0 to `legacy/`; delete the untracked v3.0 folder. Verified: 23 renames,
      no content diff.
- [x] 4. `LICENSE` from apache.org, verbatim. Verified: 202 lines, header intact.
- [x] 5. `.gitignore` rewritten for shaders, Maya, Blender, editors. Verified by inspection.
- [x] 6. README with the getting-started guide and carried-forward credits.
- [x] 7. `Docs/` split into roadmap, design, specs, plans with a `Docs/README.md` explaining the layers.
- [x] 8. Scripted Maya 2026 GUI launch loads v2 through `dx11Shader`; log committed to
      `Docs/verification/maya-2026-v2-load.log` with `RESULT: OK`. First run found the viewport on
      OpenGL Core Profile (no techniques); the launch sets `MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11`
      so the check does not depend on, or change, the user's preferences. **Verified 2026-09-20:**
      `TECHNIQUES: ['TessellationOFF']`, `RESULT: OK`; log committed; script at `tools/maya_load_check.py`.
- [x] 9. `chore/hygiene` merged as PR #2 (31f65e1) after Copilot review, 2026-09-20.
- [ ] 10. Pointer PR to `hogjonny/Maya-PBR-BRDF-VP2`: README top points at HogShade (#2 there, open). Owner merges.
- [x] 11. History rewrite done 2026-09-20 on a fresh clone after PR #2 merged: 55 commits to 48,
      `.git` 128 MB to 1 MB, `legacy/` tree hash identical (`f19e94f`), no `testFiles/`, `images/`
      or `ShaderDevProj/` in any commit; `master` force-pushed (new head `35afa7c`). **Still on the
      owner:** GitHub reports the old size until (a) the repo leaves the fork network (Settings, or
      GitHub support "detach fork"), and (b) the `legacy-pointer` branch, which is the head of the
      pointer PR on the legacy repo and holds the old history, is deleted once that PR merges.
      Anyone with an older clone must re-clone. **Dry run earlier the same day:** `.git` 128 MB to 1 MB; `legacy/` tree hash identical
      before and after (`b003388`); 47 commits to 40, the seven dropped ones touched only the
      removed binaries ("adding test files", "new screenie", "whoops" and four more). Command:
      `uvx git-filter-repo --path testFiles --path images --path ShaderDevProj --invert-paths`.
- [ ] 12. `content/` with the shader-ball scene under LFS (`.gitattributes`), HDR when chosen.
- [x] 13. ~~Maya 2024 load check~~ Dropped: Maya 2026 is the only supported version (owner, 2026-09-20).
- [ ] 14. Close the getting-started issue on the legacy repo with a link to the README.
- [ ] 15. Roadmap track B ticked; `Docs/README.md` status for phase 1 set to done.
- [x] 16. `THIRD_PARTY_NOTICES.md` written from a grep of the legacy tree for copyright and licence text.
- [x] 17. Owner confirmed `legacy/v1.0/propertyNames.fxh` is theirs; the studio copyright line was a mistake and the company is defunct. Line replaced with a note; notice updated. Verified: fxc still compiles v1 (header-only change).
- [ ] 18. Copilot review findings on PR #2 addressed: gitignore exception, README entry file and map guidance, debug-mode count, stale roadmap wording; log re-run against `V2_uv0bn-pbs_IBLenv.fx`.
