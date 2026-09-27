# S1 spec: the schema files and `hogshade.material`'s load, validate, resolve and convert

**Status:** Proposed. Drafted 2026-09-27 from the locked design; the owner approves it, then the plan
runs. S1 is the first increment of the material schema and needs nothing from gate G4.

Date: 2026-09-27. Design: [../../design/2026-09-27-material-schema.md](../../design/2026-09-27-material-schema.md)
(locked 2026-09-27, all ten questions). Decision: [ADR-009](../../decisions/ADR-009-hogshade-owns-the-material-schema.md).
Plan: [../plans/s1-material-schema.md](../plans/s1-material-schema.md). Vocabulary:
[../../glossary.md](../../glossary.md), "Materials".

## Deliverable

A Python package, `hogshade.material`, importable inside Maya's and Blender's Pythons (numpy only,
no MaterialX, no PySide6, no engine imports), that ships four material-type schema files as package
data and can load a material document, validate it against its type, resolve its parent chain into
the full parameter set, and convert a document of one type into a document of another through a
conversion table that says what is lost. Nothing renders in S1; S2 adds the Maya generator, S3 the
wgpu binding, S4 the library of materials.

## Package layout

```text
hogshade/material/
  __init__.py            # load, validate, resolve, convert, the types; nothing else public
  schema/                # package data: one file per material type, plus the conversion tables
    hogshade-standard.material-type.json
    hogshade-legacy-v2.material-type.json
    hogshade-legacy-v1.material-type.json
    hogshade-lambert.material-type.json
    conversions/
      hogshade-legacy-v2-to-hogshade-standard.json
      hogshade-legacy-v1-to-hogshade-standard.json
      hogshade-lambert-to-hogshade-standard.json
  types.py               # ParameterDef, MaterialType, Document, Resolved, Finding, Loss (dataclasses)
  schema.py              # load a material-type file; the meta-check of its shape; the registry by name
  document.py            # load(): parse, path rules, version check, migrations; raw Document
  validate.py            # validate(): a raw document against its type, or a resolved one
  resolve.py             # resolve(): the parent chain, defaults, ext merged child over parent
  convert.py             # convert(): a conversion table applied, losses reported
tests/material/          # the tests, and fixtures/ with sample documents and a broken set
```

`pyproject.toml` gains `[tool.setuptools.package-data] hogshade.material = ["schema/*.json", "schema/conversions/*.json"]`
so a pip install carries the files; the code reads them through `importlib.resources`.

## The material-type schema file

```json
{
  "material_type": "hogshade-standard",
  "version": 1,
  "title": "HogShade standard material (OpenPBR names)",
  "groups": ["base", "specular", "emission", "geometry", "surface"],
  "parameters": {
    "base_color": {
      "type": "color3", "default": [0.8, 0.8, 0.8], "range": [0.0, 1.0], "group": "base",
      "widget": "color", "semantic": "base_color_linear", "colour_space": "srgb",
      "overridable": true, "tier": 1, "doc": "Albedo for dielectrics, reflectance for metals."
    },
    "specular_roughness": {
      "type": "float", "default": 0.5, "range": [0.0, 1.0], "group": "specular",
      "widget": "slider", "semantic": "roughness_perceptual", "colour_space": "raw",
      "overridable": true, "tier": 1, "doc": "Perceptual roughness before any bias."
    }
  },
  "migrations": []
}
```

Rules of the file, checked by `schema.py`'s meta-check and a test on every shipped file:

- `type` is one of `float`, `int`, `bool`, `enum`, `color3`, `vector3`, `texture`. A parameter that
  may be textured (colour, float, vector) carries `colour_space`; `enum` carries `choices`;
  `texture`-only parameters (a normal map, a height map) carry `colour_space` and `semantic` and no
  `default` factor.
- Every parameter has every field the design lists (`type`, `default` where it applies, `range`
  for numbers with `soft: true` when a UI may exceed it, `group` from the file's `groups`,
  `widget`, `semantic`, `overridable`, `tier`, `doc`); an unknown field is a finding.
- A group that is an opt-in feature carries an `enabled` parameter of type `bool` whose name is
  `<group>_enabled`; `surface` opt-ins in version 1: `ambient_occlusion` (texture), `cavity`
  (texture), `specular_occlusion` (float and texture; question 8), `height` (texture, for the
  parallax that exists in the Maya shell). Version 1 declares no triplanar, detail or layering
  groups; they arrive with phase 4.
- `version` is an integer from 1; `migrations` is a list of `{"from": n, "to": n+1, "ops": [...]}`
  with `rename`, `default` and `remove` ops; empty at version 1 (question 6).
- Names are OpenPBR's where OpenPBR has the parameter (`base_color`, `base_metalness`,
  `specular_weight`, `specular_color`, `specular_roughness`, `specular_ior`, `specular_anisotropy`,
  `specular_rotation`, `emission_luminance`, `emission_color`, `geometry_opacity`,
  `geometry_normal`); `alpha_mode` (enum `opaque`, `mask`, `blend`, default `mask`) is the one
  non-OpenPBR parameter of the standard type, per the alpha decision. Emission is in nits
  (question 5).

**The legacy types** carry the parameters the core's legacy models take today, named as the Maya
shell names them without the prefix (`base_color`, `roughness`, `metalness`, `specular`,
`specular_tint`, `ior`, `bump_intensity`, the maps and their use flags as textures, `rough_is_gloss`
and the Disney lobes for v1), so the S2 generator reproduces the shell's material block from the
file. `hogshade-lambert` carries `base_color`, `ambient_occlusion`, `emission_color`.

## The material document

```json
{
  "material_type": "hogshade-standard",
  "material_type_version": 1,
  "parent": "base/steel.material.json",
  "values": {
    "base_color": {"factor": [0.18, 0.21, 0.24], "texture": "steel_basecolor.png", "blend": "multiply"},
    "specular_roughness": {"factor": 0.32}
  },
  "ext": {"spritejammer": {"tier_cap": 2}}
}
```

Rules, checked by `validate()`:

- `material_type` names a shipped type; `material_type_version` is at most the shipped version
  (newer is an error, older is migrated on load through the type's list).
- A `values` key is a parameter of the type; a value is `{factor}`, `{texture}` or both, and `blend`
  only with both, one of `multiply` (default), `lerp`, `overlay` where the parameter's `widget` is
  `color` or `slider`. `factor` matches the parameter's `type` and, unless the range is `soft`, its
  `range`. A `texture` value on a parameter that has no `colour_space` is a finding.
- `parent` and every `texture` are relative paths, normalised with `PurePosixPath`, rejected when
  absolute or when the joined path resolves outside the document's package root (the directory
  passed to `load`, default the document's own directory); `..` components are rejected outright.
- `ext` keys are namespaces; contents are not validated.
- A parameter with `overridable: false` set in a child document is a finding (a child sets only
  what its type allows children to set).

## The library

| Function | Contract |
| --- | --- |
| `load(path, root=None) -> Document` | Parse the JSON, apply the path rules, check the version and migrate an older document through the type's list. The result is raw: `parent` is a normalised relative path, values are as written. Raises `MaterialError` on a malformed file, an unknown type, a newer version or an escaping path. |
| `validate(doc_or_resolved) -> list[Finding]` | Raw: unknown keys, types, ranges, colour spaces, `blend`, overridable, paths. Resolved: completeness (every parameter has a value or a default) and the cross-parameter rules (`alpha_mode` `blend` with `geometry_opacity` textured is allowed; `mask` without an opacity source is a finding). Never raises; a `Finding` has `path`, `parameter`, `message`. |
| `resolve(doc, root=None) -> Resolved` | Follow `parent` through `load` until a document has none; reject a cycle and a parent of another type; apply values child over parent, then the type's defaults; merge `ext` blocks child over parent per namespace key. `Resolved` carries `material_type`, `version`, `values` (every parameter, `{factor, texture, blend}` with `texture` `None` when unbound), `ext`, and `chain` (the documents' paths, child first). |
| `convert(doc_or_resolved, to_type) -> tuple[Document, list[Loss]]` | Resolve if needed, apply the conversion table from the source type to `to_type`: each entry maps a source parameter to a target parameter with a transform (`identity`, `invert`, `scale` by a constant, `clamp`, `constant`), a `dropped` entry names what has no counterpart and why. Returns a raw document of the target type carrying the converted values as `factor`s and textures, and the `Loss` list (parameter, reason). No table for the pair is `MaterialError`. |

Everything numeric goes through numpy so a caller can hand in arrays later; nothing in S1 depends
on it beyond scalars and triples.

## The conversion tables

One JSON file per pair under `schema/conversions/`:

```json
{
  "from": "hogshade-legacy-v2", "to": "hogshade-standard", "version": 1,
  "map": [
    {"from": "base_color", "to": "base_color", "transform": "identity"},
    {"from": "roughness", "to": "specular_roughness", "transform": "identity"},
    {"from": "metalness", "to": "base_metalness", "transform": "identity"},
    {"from": "specular", "to": "specular_weight", "transform": "identity"},
    {"from": "ior", "to": "specular_ior", "transform": "identity"},
    {"from": "normal_map", "to": "geometry_normal", "transform": "identity"},
    {"from": "ambient_occlusion_map", "to": "ambient_occlusion", "transform": "identity"},
    {"from": "emissive_map", "to": "emission_color", "transform": "identity"}
  ],
  "dropped": [
    {"from": "cavity_map", "reason": "the standard's cavity is a surface opt-in with its own semantics; v2 folded cavity into specular"},
    {"from": "bump_intensity", "reason": "normal strength is the geometry_normal texture's strength in the standard"}
  ]
}
```

A test asserts that every parameter of the source type appears exactly once, in `map` or in
`dropped`, so a conversion table cannot silently forget a parameter, and that every `to` exists in
the target type. The three tables shipped in S1 go from each legacy type to the standard; the
reverse direction is S2 or later, when a comparison view needs it.

## Tests (`tests/material/`)

- The four schema files pass the meta-check; every parameter has every field; every group is
  declared; names in the standard match the OpenPBR list the spec fixes above.
- Fixtures: a base document, a child with a texture and a `blend`, a grandchild; a set of broken
  documents (unknown parameter, wrong type, out of range, `..` in a path, an absolute path, a
  parent of another type, a cycle, a newer version, a child setting a non-overridable parameter).
- `load` on each fixture: the good ones parse raw; each broken one raises or returns the named
  finding, and `validate` names the parameter.
- `resolve` on the grandchild: every parameter present, child wins, `ext` merged per key, `chain` in
  order; the cycle fixture raises.
- `convert` v2 to standard on a fixture: the mapped values arrive, the `Loss` list names the dropped
  parameters, the result validates against the standard.
- A migration test: a version-1 document under a fake version-2 type with one `rename` op migrates
  on load.
- An import test: `hogshade.material` imports with `MaterialX` and `PySide6` absent from
  `sys.modules` after import.

## Acceptance gate

- `uv run pytest tests/material` green on CI; the package data present in a wheel
  (`uv build` and a check that the four files and three tables are in it).
- `hogshade.material` imports under Maya 2026's `mayapy` (a human run, stated in the PR, since CI
  has no Maya): the four types load.
- `tools/check_docs.py` and `tools/check_hygiene.py` clean; the glossary's nouns used throughout.

## Out of scope

- The generators (S2), the wgpu binding (S3), the library of materials (S4), MaterialX export and
  import (S5), the glTF game profile (S6).
- Any change to the core or the hosts. S1 is Python and JSON.
- A JSON Schema dependency: the meta-check is a hundred lines of our own over the file's shape.
