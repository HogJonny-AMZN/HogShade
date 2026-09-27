# ADR-009: HogShade owns the core material schema and data; the editor lives elsewhere

**Status:** Accepted (owner, 2026-09-27: "let's not build the material editor here, but let's own the core generalized material schema / data")
**Date:** 2026-09-27
**Deciders:** the owner

## Context

Board gate G3 asked where the material data model and the editor live: a base here extended in
LargeWorlds and again per game, or a shading-only repo with the data model elsewhere. The
recommendation on record (decision log, 2026-09-26) was that the contract is the shader's API and
belongs with the shader, while an editor is Qt widgets, node graphs, asset browsing and live links,
which belong with the engine tooling.

## Decision

HogShade owns the generalised material schema and its data:

- The parameter schema, one machine-readable definition per parameter (name, type, range, default,
  UI group, semantic, colour space), from which every host's UI is generated and never hand-edited
  (roadmap C3).
- The authored form, an OpenPBR-in-MaterialX document, and the glTF game-profile mapping with its
  conversion table.
- The texture conventions the schema references.
- A Python library that loads, validates and converts a material document and produces a host's
  uniform and texture binding set; importable inside Maya and Blender, so no PySide6 and no engine
  imports.
- Namespaced extension blocks: HogShade validates its core block and passes unknown namespaces
  through, so an engine adds its fields (layers, light channels, tier caps, streaming hints) and a
  game adds its own, in one document format, without forking the schema.

HogShade does not build a material editor. LargeWorlds owns the editor and the engine-side material
assets and instances, consuming this schema; a game extends the LargeWorlds editor, never this repo.
Dependency direction is one way: LargeWorlds depends on HogShade (the Python library as a package,
the core WGSL vendored); HogShade never imports LargeWorlds. The grey zone stays narrow: HogShade's
viewer and comparison tool may show a minimal generic parameter panel generated from the schema,
nothing beyond it.

## Consequences

- Phase C3's parameter schema has a home and can be designed; its pre-spec design is the next
  unblocked item on the board. C3 itself still waits on G4 (the calibration capture before OpenPBR).
- Parity across hosts depends on the schema being defined once; a host UI hand-edited against it is
  a finding.
- The schema's versioning is HogShade's versioning; an engine field lives in the engine's namespace,
  so the core block can change without breaking a game's block and the reverse.
- SpriteJammer's materials design (Material Type, Prime, Material, Instance) consumes this schema
  through LargeWorlds or directly; that is its ADR to write, not this one.

## Revisit if

An editor concern turns out to need schema knowledge the extension blocks cannot express, or a
second engine needs a different core block rather than a namespace.
