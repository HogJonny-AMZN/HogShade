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
- [ ] 8. Scripted Maya 2026 GUI launch loads v2 through `dx11Shader`; log committed to
      `Docs/verification/maya-2026-v2-load.log` with `RESULT: OK`.
- [ ] 9. Commit and push `chore/hygiene`; open the PR; merge after review.
- [ ] 10. Pointer PR to `hogjonny/Maya-PBR-BRDF-VP2`: README top points at HogShade. Owner merges.
- [ ] 11. History rewrite on a fresh clone with `git-filter-repo`, dropping `testFiles/`, `images/`,
      `ShaderDevProj/`. Verify: clone size under 5 MB, legacy files byte-identical to before, commit
      count unchanged. Force-push `master`. Owner detaches the fork network afterwards.
- [ ] 12. `content/` with the shader-ball scene under LFS (`.gitattributes`), HDR when chosen.
- [ ] 13. Maya 2024 load check, owner-run, log committed beside the 2026 one.
- [ ] 14. Close the getting-started issue on the legacy repo with a link to the README.
- [ ] 15. Roadmap track B ticked; `Docs/README.md` status for phase 1 set to done.
