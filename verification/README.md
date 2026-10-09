# verification

Evidence, not documentation: the pictures, logs and mirrored application histories that plan tasks cite
when they are ticked. Prose about them lives in `Docs/`; the tools that write them live in `tools/`;
the comparison framework (roadmap, track E) grows here: `cases/` holds its case tables (`tools/compare.py validate` checks
them, `tools/compare.py run` renders them into `captures/`, which git ignores because the EXRs are large), `accepted.json`
the differences a person accepted, and `baselines/` and `reports/` come with the regression and parity increments.

Layout, one directory per capture, files named by role only:

    <host>[-<version>]/<check>/<variant>/<role>.<ext>

    maya-2026/ibl-check/studio_small_09/{main.png, debug-28.png, check.log, maya-history.log}
    wgpu/shader-ball/studio_small_09/{forward.png, deferred.png}   (metal/ for the variant)
    core/gpu-tests.log

A file name never repeats the host, version, check or variant. Logs are committed on purpose
(`.gitignore` allows `verification/**/*.log`); large captures move under LFS when they grow.

## Pictures: the rule, and the gallery

The pictures here are proof, and this is a generate-visuals project, so pull requests carry them; the
rule keeps that from becoming a never-ending string of images:

- PNG, at most 1024 on a side, at most 1 MiB. Plain git, not LFS (`.gitattributes` holds only
  `content/**`); at these sizes history costs well under a megabyte per re-render.
- Fixed names, overwritten in place, never a dated copy. The tree always holds the latest capture of
  each path; git holds the before. Compare across versions with `git show <rev>:<path>`.
- The pictures that matter are listed in `gallery.json` (sections by need, pairs for side-by-side, grids for a
  matrix of rows by columns, every cell a listed picture), and
  `Docs/gallery.md` is generated from it by `tools/generate_gallery.py --write`; `--check` runs in CI and
  fails on a rule broken, a missing file or a stale page. A capture nobody lists is still evidence, but
  the gallery is the showcase and the comparison, and the manual reuses its pictures by reference.
- A picture that is no longer reproducible by any current command is removed, not kept (the first was
  `wgpu/shader-ball/studio_small_09/legacy-v1/metal/forward.png`, from a flag the S3 viewport retired).
