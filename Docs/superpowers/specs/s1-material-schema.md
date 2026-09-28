# S1 spec: the schema files and `hogshade.material`'s load, validate, resolve and convert

**Status:** Accepted. Drafted 2026-09-27 from the locked design and built the same day on
`feat/s1-material-schema`; the build's amendments are the last section. S1 is the first increment of the
material schema and needed nothing from gate G4.

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

`pyproject.toml` gains, under `[tool.setuptools.package-data]`, the quoted dotted key
`"hogshade.material" = ["schema/*.json", "schema/conversions/*.json"]` (unquoted, TOML reads it as nested
tables and setuptools ships nothing), so a pip install carries the files; the code reads them through
`importlib.resources`, and task 8's wheel listing is the guard.

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
      "overridable": true, "tier": 1, "hosts": {},
      "doc": "Albedo for dielectrics, reflectance for metals."
    },
    "specular_roughness": {
      "type": "float", "default": 0.5, "range": [0.0, 1.0], "group": "specular",
      "widget": "slider", "semantic": "roughness_perceptual", "colour_space": "raw",
      "overridable": true, "tier": 1, "hosts": {"osl": "a closure parameter, not a texture sample"},
      "doc": "Perceptual roughness before any bias."
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
  `widget`, `semantic`, `overridable`, `tier`, `hosts`, `doc`); an unknown field is a finding.
  `hosts` is a map of host name to a note, `{}` when no host maps the parameter differently, or
  `{"<host>": "unsupported: <reason>"}` for a host that cannot carry it; the S2 generator and the
  later bindings read it. A normal-map parameter carries `"strength": true`, which admits the
  `strength` field in a document value (below).
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

**The legacy types** carry exactly the parameters the core's legacy models and the Maya shell take
today (`core/models/legacy_v2.wgsl` and `legacy_v1.wgsl`, the `Material` and `Samples` structs;
`hosts/maya_dx11/hogshade.fx`, the material, map, normal and parallax groups), typed as the shell
types them, so the S2 generator reproduces the shell's material block from the file. The shell's
`use<Map>` flags are not parameters: a `texture` parameter is in use when a document binds it, and
the generator emits the flag from that. Host-only parameters (the display gamma, the Maya shadow
group, the light slots) are not material and are not in any type.

`hogshade-legacy-v2`, version 1:

| Group | Parameters |
| --- | --- |
| `base` | `base_color` color3 (sRGB texture), `roughness` float [0, 1] (texture, green), `metalness` float [0, 1] (texture, green), `specular` float [0, 1] (texture, red), `specular_tint` float [0, 1], `ior` float [1, 3], `emission_color` color3 (sRGB texture), `emission_intensity` float [0, 100] soft |
| `geometry` | `normal_map` texture (raw, `strength: true`), `bump_intensity` float [0, 4] (the strength the shell exposes; the schema keeps both so the generator round-trips), `normal_flip` vector3 of +1 or -1, `flip_backface_normals` bool, `opacity` float [0, 1], `has_alpha` bool, `use_cutout_alpha` bool, `opacity_mask_bias` float [0, 1], `has_vertex_alpha` bool |
| `surface` | `ambient_occlusion_map` texture (raw, red), `cavity_map` texture (raw, red), `height_map` texture (raw, red), `use_vertex_color` bool, `use_vertex_ao` bool |
| `parallax` (opt-in, `parallax_enabled` bool) | `height_scale` float [0.001, 1], `min_samples` int [1, 64], `max_samples` int [1, 128], `self_shadow` enum `none`, `simple`, `self_shadow_strength` float, `self_shadow_multiplier` float |

`hogshade-legacy-v1`, version 1: `base` as v2's less `ior` and `emission_*`, plus the Disney lobes
`subsurface`, `anisotropic`, `sheen`, `sheen_tint`, `clearcoat`, `clearcoat_gloss` (floats [0, 1]);
`geometry` as v2's without `bump_intensity` and `opacity_mask_bias`; `surface` with
`ambient_occlusion_map` and `use_vertex_ao`; the v1 flags `rough_is_gloss` bool and
`use_specular_mask` bool; the maps v1 samples (`base_color`, `specular` rgba, `roughness`,
`metalness`, `normal_map`, `ambient_occlusion_map`). `hogshade-lambert`: `base_color` color3,
`ambient_occlusion_map` texture, `emission_color` color3. The full lists are the schema files; a
test asserts each legacy type's parameter set equals the union of its model's `Material` and
`Samples` fields plus the shell's material-block flags, so a field added to a struct without a
schema entry fails.

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
  `range`. A `texture` value on a parameter that has no `colour_space` is a finding. A parameter
  whose schema entry has `strength: true` (normal maps) admits `strength`, a float at or above 0,
  default 1.0, only with `texture`; on any other parameter `strength` is a finding.
- `parent` and every `texture` are relative paths, normalised with `PurePosixPath`, rejected when
  absolute or when the joined path resolves outside the document's package root (the directory
  passed to `load`, default the document's own directory); `..` components are rejected outright.
- `ext` keys are namespaces; contents are not validated.
- A parameter with `overridable: false` set in a child document is a finding (a child sets only
  what its type allows children to set).

## The library

| Function | Contract |
| --- | --- |
| `types() -> list[str]` | The names of the shipped material types, from the package data; `type_of(name) -> MaterialType` returns one. |
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
    {"from": "emission_color", "to": "emission_color", "transform": "identity"},
    {"from": "emission_intensity", "to": "emission_luminance", "transform": "scale", "by": 100.0},
    {"from": "bump_intensity", "to": "geometry_normal", "field": "strength", "transform": "clamp", "range": [0.0, 4.0]},
    {"from": "opacity", "to": "geometry_opacity", "transform": "identity"},
    {"from": "use_cutout_alpha", "to": "alpha_mode", "transform": "constant", "value": "mask"}
  ],
  "dropped": [
    {"from": "cavity_map", "reason": "the standard's cavity is a surface opt-in with its own semantics; v2 folded cavity into specular"},
    {"from": "specular_tint", "reason": "the standard has specular_color; a scalar tint has no lossless image"}
  ]
}
```

Transforms and their payloads, validated by the coverage test: `identity` and `invert` carry
nothing; `scale` carries `by` (a number); `clamp` carries `range` (two numbers); `constant` carries
`value` (of the target's type) and is the only transform whose `from` may be a `bool` or `enum`.
An entry may carry `field` to target a sub-field of the value (`strength` on a normal map) instead
of `factor`; the target parameter must admit that field. The `emission_intensity` scale of 100 is
the example's placeholder for the v2 intensity to nits mapping, fixed by measurement in S3 when the
wgpu binding renders both.

A test asserts that every parameter of the source type appears exactly once, in `map` or in
`dropped`, so a conversion table cannot silently forget a parameter; that every `to` exists in the
target type and every `field` is admitted by it; and that each entry's payload matches its
transform. The three tables shipped in S1 go from each legacy type to the standard; the
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

## Amendments made in the build (2026-09-27)

Each is a two-way door recorded in the PR's Decisions table; the text above is left as written so the
diff between the contract and the build stays readable.

- **Module names.** `validate.py`, `resolve.py` and `convert.py` became `validation.py`, `resolution.py`
  and `conversion.py`: the package re-exports functions named `validate`, `resolve` and `convert`, and a
  function bound on the package shadows the submodule of the same name (`hogshade.material.validate` was
  the function, so `monkeypatch.setattr("hogshade.material.validate.type_of", ...)` and
  `import hogshade.material.validate as v` both broke). `document.py` keeps its name; `load` does not clash.
- **Opt-in groups are inferred.** There is no `optional_groups` field: a group is opt-in when a bool named
  `<group>_enabled` exists in it (the meta-check enforces the bool and the group); `MaterialType.optional_groups`
  is derived. The standard's four `surface` opt-ins are textures (and one float) that are in use when bound,
  so the standard has no enabled flag; legacy v2's `parallax` is the one opt-in group.
- **Legacy v2 carries `specular_f0_map`** (texture, the shell's `specularF0Map`; the struct's
  `specular_f0_from_map` is derived from the binding, like the other `use<Map>` flags), which the spec's
  table omitted and the union test demanded. The parallax ranges are the shell's (`min_samples` 1 to 128,
  `max_samples` 1 to 256, `self_shadow_strength` 0.001 to 1), not the table's smaller ones. The shell's
  `shadowMultiplier` (declared with the material slider macro, part of the Shadows block) is host-only.
- **The v2 table maps `cavity_map` to `cavity`** (the standard has the opt-in), where the example dropped it;
  the parallax group is dropped with one reason; `specular_f0_map` maps to `specular_color`.
- **The resolved `mask` rule is narrower.** A finding only when `alpha_mode` is `mask`, `geometry_opacity`
  has no texture and its constant factor is below the 0.5 cut (nothing would render). With `mask` the
  type's default, the letter of the rule would have flagged every untextured material.
- **Standard library only.** The spec said everything numeric goes through numpy; the library uses none,
  so it imports under any DCC Python (the import test asserts `numpy` absent too). Arrays arrive with a
  caller that needs them.
- **A `constant` entry's `value` is checked against the target's type** in the coverage rule, as the
  spec's prose said and its test list did not.

### After the review round (local review, then Copilot on #31; same day)

- **`types.py` became `model.py`**: the same shadow as the three renamed modules (`types()` is an exported
  function), missed by the first rename; a test now asserts no exported name is a submodule's.
- **`validate()` on a raw document applies the string half of the path rule** (`path_findings`: non-empty,
  not absolute, no `..`) to `parent` and every `texture`, so a document built in memory is checked; root
  confinement still needs a base directory and stays in `load()`.
- **`load()` stores the normalised spelling** of `parent` and every `texture` (forward slashes, no `./`),
  as the document section promised; the raw values were kept as written before.
- **A conditional `constant`**: an entry may carry `when`, a value of the source's type; it fires only when
  the resolved source factor equals it, and a source may appear once per distinct `when` value (the
  coverage rule counts those as one appearance and refuses a mix with an unconditional entry). The
  shipped tables map `use_cutout_alpha` `true` to `alpha_mode` `mask` and `false` to `blend` (the shells
  blend through the transparency pass when cutout is off).
- **`resolve()` keeps a malformed known value** as a factor instead of dropping it for the default, and
  `validate()` on a resolved material type-checks every factor, so the malformation is reported there.
- **The meta-check** also checks `tier`, `semantic` and `soft`, each migration op's payload, the range
  shape of colours and vectors and their default components, and that an `int` default is an integer.
  A document's `material_type` is looked up in the shipped registry, never joined into a resource path.
- **Every module declares `_LOGGER`** (`Docs/standards/python.md`: a module that never logs still declares
  it); `schema.py` and `document.py` carry `__main__` smoke blocks; the `emission_luminance` semantic is
  the design's `emission_luminance_nits`.
- **Resolved values and converted documents are deep copies**: the first build aliased the cached type's
  default list into every resolved value, so mutating one mutated the schema for the rest of the process.

### After the second local review (2026-09-27 night, `fix/s1-review-round-2`)

The re-review of #31's head scored eight of nine metrics at or above 7; error handling stayed at 6 and one
design finding was new. Both fixed in a PR of their own:

- **`when` conditions on several sources.** A conditional `constant` may carry `when` as an object of
  source parameter names to values, all of which must hold; a bare value still conditions the entry's own
  source. A parameter named in a condition is *consulted* and needs no `dropped` entry. The cutout mapping
  reads both legacy flags: cutout on gives `mask`, cutout off with `has_alpha` on gives `blend`, both off
  gives `opaque`. (The earlier "cutout off gives `blend`" would have sent every opaque legacy material
  through the transparency pass in S3.) A scalar `opacity` below 1 with both flags off still converts to
  `opaque` plus the factor; the shells blend it, S3 decides how the standard reads that case.
- **`validate()` never raises**: an unknown type on an in-memory Document, or a non-object resolved value,
  is a `Finding`. `convert()` validates the resolved material first and refuses an invalid one as
  `MaterialError` naming the findings; a transform on a non-numeric factor is `MaterialError`, not
  `TypeError`. `load()` turns an unreadable or non-UTF-8 file into `MaterialError`. A non-object table
  entry is a finding.
- **Non-constant transforms keep the type**: float to float, colour to colour, a texture-only source to a
  texturable target; the coverage rule reports a mismatch. `load_table` is a registry lookup like
  `read_type_data`.
- **Legacy v2's `normal_map` has no `strength` of its own**: `bump_intensity` is the shell's one strength
  and converts through the `field` entry. Legacy v1's `normal_map` keeps `strength: true`, and `identity`
  now carries a source `strength` to a target that admits it, so it is no longer lost.
- `from_data` is exported (the in-memory entry every test wants); `__all__` is wider than the spec's
  "nothing else public" (the checkers, the model dataclasses), recorded here as the intent.
- Housekeeping from the review: `Traversable` from `importlib.resources.abc` (the `importlib.abc` spelling
  is removed in 3.14), a readable migration-op check, `Callable` on `_each`, a debug log line when a
  document migrates on load.
- **The condition-set rules**, from the third review (run before the fix PR opened): a `when` is a value of
  the entry's source or a non-empty object that names that source among its conditions; over the product of
  the consulted bool and enum domains, every combination is matched by exactly one entry (two would let table
  order decide, none would let the target's default decide; both are findings); a consulted parameter is not a
  loss; a `constant` into the `strength` field is a float. `convert()` refuses a target factor written twice
  by two unconditional entries, which the coverage rule alone cannot see. `load()` wraps every `OSError` (a
  directory, permissions), not only a bad encoding.
