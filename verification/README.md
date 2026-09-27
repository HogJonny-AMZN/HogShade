# verification

Evidence, not documentation: the pictures, logs and mirrored application histories that plan tasks cite
when they are ticked. Prose about them lives in `Docs/`; the tools that write them live in `tools/`;
the comparison framework (roadmap, track E) grows here with `baselines/` and `reports/`.

Layout, one directory per capture, files named by role only:

    <host>[-<version>]/<check>/<variant>/<role>.<ext>

    maya-2026/ibl-check/studio_small_09/{main.png, debug-28.png, check.log, maya-history.log}
    wgpu/shader-ball/studio_small_09/{forward.png, deferred.png}   (metal/ for the variant)
    core/gpu-tests.log

A file name never repeats the host, version, check or variant. Logs are committed on purpose
(`.gitignore` allows `verification/**/*.log`); large captures move under LFS when they grow.
