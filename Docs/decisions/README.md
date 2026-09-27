# Architectural decision records

**Status:** Living. The index; every ADR has a row here (`tools/check_docs.py` fails otherwise).

An ADR captures a decision at a moment, with the information available then. It is append-only:
to change a decision, write a new ADR and add `Superseded by:` to the old one's status. Every ADR
has a *Revisit if* section, the conditions under which to stop trusting it. The pattern is
LargeWorlds' and SpriteJammer's.

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-001](ADR-001-wgsl-is-the-core-source.md) | WGSL is the core's source language, translated by naga; Slang the fallback | Accepted |
| [ADR-002](ADR-002-resources-as-parameters-and-the-prefix-rule.md) | Resources are function parameters; every core name carries its module prefix; constants mirrored | Accepted |
| [ADR-003](ADR-003-the-model-interface.md) | The five-function model interface, `EnvironmentSamples`, if-chain dispatch on the model ID (no `switch` on a texture-derived value) | Accepted |
| [ADR-004](ADR-004-numpy-twin-and-gpu-test.md) | Every core function has a NumPy twin and a GPU test | Accepted |
| [ADR-005](ADR-005-the-gbuffer-layout-contract.md) | The G-buffer encode and decode take the layout as a parameter; SpriteJammer's ADR-002 is the first | Accepted |
| [ADR-006](ADR-006-shader-specialisation-by-override-constants.md) | Shader specialisation by `override` constants over the uber core as the record | Proposed |
| [ADR-007](ADR-007-the-orchestrator-is-the-developer-track.md) | Job_Orchestrator is the developer track and never a dependency | Accepted |
| [ADR-008](ADR-008-lfs-and-hygiene.md) | LFS only for what cannot be generated; 8K masters never; the hygiene rule | Accepted |

Decisions that are not yet ADRs live in the decision log
(`../design/2026-09-26-decision-log-and-working-knowledge.md`); one becomes an ADR when the
standards pass or a phase close formalises it. Candidates: the material contract split (board gate
G3), the colour-management choice (G2), the comparison framework's design (G4).
