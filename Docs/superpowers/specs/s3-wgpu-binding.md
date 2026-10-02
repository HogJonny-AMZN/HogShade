# S3 spec: the wgpu binding, a material document into the wgpu host's frame

**Status:** Accepted. Drafted 2026-10-02 from the locked design, approved as #37 and built the same day on
`feat/s3-wgpu-binding`; the build's amendments are the last section. S3 needed nothing from gate G4.

Date: 2026-10-02. Design: [../../design/2026-09-27-material-schema.md](../../design/2026-09-27-material-schema.md),
"The Python library" (`bind(resolved, host) -> Binding`) and "Increments" (S3). Decision:
[ADR-009](../../decisions/ADR-009-hogshade-owns-the-material-schema.md). S1:
[s1-material-schema.md](s1-material-schema.md); S2: [s2-material-generators.md](s2-material-generators.md).
Plan: [../plans/s3-wgpu-binding.md](../plans/s3-wgpu-binding.md). Vocabulary:
[../../glossary.md](../../glossary.md), "Materials" (Binding).

## Deliverable

`hogshade.material.bind(resolved, "wgpu")` turns a resolved material into the material-owned values the
wgpu host's frame carries, and the host renders from that instead of from `Scene`'s hand-set material
fields. A material document, loaded and resolved by S1's library, is what `tools/wgpu/viewport.py`
renders; the first two documents of the library of materials exist to prove it. After S3 a document is
the one way a material reaches either host: the Maya shell's UI from S2, the wgpu frame from S3.

The binding is a per-host **host map** again, the S2 mechanism with a wgpu entry shape: for each
parameter of the types the host carries, which frame field and component receives it, or that the host
cannot carry it and why. The coverage rule is the same as S2's: every parameter of the host's types has
an entry; a parameter the host does not reach is `unsupported` with a reason, never silently dropped.

## Package layout

```text
hogshade/material/
  binding.py                    # bind(resolved, host) -> Binding; the wgpu binder inside
  hosts/wgpu.json               # the wgpu host map: parameter -> frame field and component, or unsupported
hogshade/wgpu_host.py           # Scene takes a MaterialBinding; the hand-set material fields move into it
tools/wgpu/viewport.py          # --material <path.material.json>; the default is the library's default document
content/materials/
  legacy-v2/default.material.json
  legacy-v1/default.material.json   # the first two documents of the library (S4 fills the rest)
tests/material/test_material_bind.py
tests/host/test_wgpu_host.py    # a document renders the same frame bytes as the equivalent hand-set Scene
```

`binding.py`, not `bind.py`: the package exports `bind` (failure-modes entry 13). `pyproject.toml` package
data already covers `hosts/*.json`.

## The wgpu host map

An abbreviated, non-normative excerpt; the shipped file carries an entry for every parameter of the three
types (38 of them), every unbound one `unsupported` with its reason, and the test holds it to the coverage
rule below:

```json
{
  "host": "wgpu", "version": 1,
  "types": ["hogshade-legacy-v2", "hogshade-legacy-v1", "hogshade-lambert"],
  "fields": {"base_color": 4, "material": 4, "model": 4, "params_a": 4, "params_b": 4},
  "parameters": {
    "base_color":    {"field": "base_color", "components": [0, 1, 2]},
    "roughness":     {"field": "base_color", "components": [3]},
    "metalness":     {"field": "material", "components": [0]},
    "specular":      {"field": "material", "components": [1]},
    "specular_tint": {"field": "material", "components": [2], "types": ["hogshade-legacy-v2"]},
    "specular_tint@hogshade-legacy-v1": {"field": "params_a", "components": [1]},
    "ior":           {"field": "material", "components": [3]},
    "rough_is_gloss": {"field": "model", "components": [1]},
    "subsurface":    {"field": "params_a", "components": [0]},
    "bump_intensity": {"unsupported": "the host samples no normal map; the core receives 1.0"},
    "normal_map":    {"unsupported": "no texture bindings in the wgpu host before the comparison framework; the path is carried on the Binding"}
  }
}
```

Rules, checked by `check_host_map()` (extended with the wgpu entry shape) and a test on the shipped file:

- `types` names shipped types; the map covers exactly the union of their parameters (the S2 rule). A
  parameter present in several types has one entry unless `types` on the entry restricts it (legacy v1's
  `specular_tint` lands in `params_a[1]`, v2's in `material[2]`: two entries, one per type, so the map has
  entries keyed `specular_tint` and `specular_tint@hogshade-legacy-v1`; the key's suffix selects the type).
- A bound entry names a `field` from `fields` and `components` within that field's width: one component
  for a `float`, `int`, `bool` or `enum` (bool as 0 or 1, enum as its index), three for `color3` and
  `vector3`. No two entries write the same component of one field; a component nobody writes stays 0.
- A `texture` parameter is `unsupported` in S3 with the reason above; the `Binding` still lists every
  bound texture's resolved path so a later host revision can bind it without touching the map's shape.
- `unsupported` carries a reason; a parameter cannot be both bound and unsupported.
- `float` and `int` factors are written as floats; a parameter whose resolved value has no factor (a
  texture-only parameter) writes nothing.

## The Binding

```python
@dataclass(frozen=True)
class Binding:
    host: str                       # "wgpu"
    material_type: str              # the resolved type's name
    model: str                      # "legacy-v2" | "legacy-v1" | "lambert", from the type (MODELS in wgpu_host)
    fields: dict[str, tuple[float, ...]]   # every frame field in the map's `fields`, full width, zeros where unwritten
    textures: dict[str, str]        # parameter name -> the texture path as the document spells it (relative)
    unsupported: tuple[Unbound, ...]  # the parameters the host cannot carry, with the map's reasons
```

`Unbound(parameter, reason)` is a new record in `model.py`, distinct from `Loss`: a `Loss` is what a
conversion between types drops, an `Unbound` is what one host cannot carry from a type it does render.
The glossary gains the noun.

`model` is derived from the type: `hogshade-legacy-v2` is `legacy-v2`, `hogshade-legacy-v1` is
`legacy-v1`, `hogshade-lambert` is `lambert`; `hogshade-standard` has no wgpu model before C3, so
`bind()` of a standard material is `MaterialError` naming C3. The `model` field's x component (the
`HOGSHADE_MODEL_*` id) is written by the binder from `model`, not by a map entry.

## The library

| Function | Contract |
| --- | --- |
| `bind(resolved, host) -> Binding` | A `Resolved` into the host's values through its map; the caller resolves (so the parent chain's file reads and their errors stay in `resolve()`, as the design places them). A `Document` is refused. Unknown host, a type the host does not carry, or a material that does not validate is `MaterialError`. Pure: no numpy, no wgpu. |
| `hosts()`, `host_map(host)`, `check_host_map(hmap, params)` | As S2, with the wgpu entry shape. `check_host_map` reads the map's `host` to pick the shape. |

`hogshade.wgpu_host`:

- A `MaterialBinding` dataclass holds what `Scene` carried by hand (`base_color`, `roughness`, `metalness`,
  `specular`, `specular_tint`, `ior`, `model`, `rough_is_gloss`, the six v1 lobes). `Scene.material:
  MaterialBinding` replaces those fields on `Scene`. **Its defaults are the legacy v2 type's schema
  defaults** (roughness 0.5, IOR 1.45, base colour 0.6), not the host's old hand-set ones (0.2, 1.5, 0.5):
  the schema is the one source of a default, and the old values were a host author's taste. The pre-S3
  default render is therefore not preserved; the wgpu pictures under `verification/wgpu/` are recaptured
  in the PR and the diff stated. `MaterialBinding.from_binding(binding)` reads a `Binding`'s `fields`; the
  packing into `frame_bytes` becomes one loop over the map's `fields`, so a map change cannot miss a field.
- `tools/wgpu/viewport.py` takes `--material <path.material.json>` and renders it; without the flag it
  renders `content/materials/legacy-v2/default.material.json`, which binds to the same values as
  `MaterialBinding()`'s defaults (a test says so, component for component). `--model` goes: the document's
  type picks the model.

## The first documents

`content/materials/legacy-v2/default.material.json` and `legacy-v1/default.material.json`: the type's
defaults written out explicitly for the six scalar parameters the host carries (so a reader sees the
values), nothing else; `ext` empty. They are the library's first two entries and S4's starting point;
S4 decides the directory layout beyond this (its design, track F).

## Tests

- `tests/material/test_material_bind.py`: the shipped wgpu map passes `check_host_map` and covers the
  union of its three types; mutations (a component written twice, a component beyond the field's width,
  a parameter both bound and unsupported, a missing reason, an unknown field) each produce the named
  finding; `bind(resolve(doc), "wgpu")` of the v2 default document gives `fields` equal to
  `MaterialBinding()`'s defaults, component for component; the v1 default binds the lobes into
  `params_a`/`params_b` and `specular_tint` into `params_a[1]`, not `material[2]`; a lambert document binds
  `base_color` only; a standard document is `MaterialError` naming C3; a raw `Document` is refused; a
  document with a bound normal map lists it in `textures` and `unsupported`; `bind()` refuses an invalid
  material.
- `tests/host/test_wgpu_host.py`: `Scene(material=MaterialBinding.from_binding(bind(resolve(doc), "wgpu")))`
  and the equivalent hand-set `Scene(material=MaterialBinding(...))` give identical `frame_bytes`; on a
  GPU, the v2 default document and `Scene()` render the same forward image, and a v1 document with `sheen`
  differs from one without (the lobes reach the shader through the binding).
- The S1 import test still holds; `binding.py` imports nothing outside the standard library.

## Acceptance gate

- `uv run pytest tests/material tests/host` green on CI (the GPU tests skip without an adapter, as today);
  `tools/wgpu/viewport.py --material content/materials/legacy-v1/default.material.json` renders on the
  owner's GPU with the picture under `verification/wgpu/` named in the PR.
- `tools/check_docs.py`, `check_hygiene.py`, `generate_material_ui.py --check` clean.

## Out of scope

- Texture sampling in the wgpu host (no texture bind group exists; the comparison framework or S5 adds it).
- The standard type's wgpu model (C3). Blender. The Maya side of `bind()`: the Maya shell reads a
  document through its own generated UI, not through a frame; a Maya `bind()` is a later increment if the
  check scripts want it.
- The library's layout and content beyond the two default documents (S4).

## Amendments made in the build (2026-10-02)

- **A third document**, `content/materials/legacy-v2/metal.material.json` (metalness 1, roughness 0.2), so the
  committed `metal` variant of the wgpu pictures stays reproducible now that the viewport takes only a
  document; S4 owns the layout from here.
- **`Binding` and `Unbound` live in `model.py`** beside `Loss`, as the other records do; `binding.py` holds
  `bind()` and `pack_fields()`. `MaterialBinding.from_binding()` carries the `Binding`'s fields as they are
  and `fields()` returns them unchanged; a hand-set `MaterialBinding` packs through the same `pack_fields()`,
  so the two paths cannot disagree.
- **`entries_for(hmap, type)`** is the one place the `@type` suffix and an entry's `types` list are read;
  the checker, the binder and the host all go through it. A wgpu finding is reported once per entry, not
  once per type that shares it.
- **`Scene.model` is a property** of `Scene.material`; the host's `WGPU_TYPES` is the inverse of the
  binder's `WGPU_MODELS`.
- The unsupported count for the legacy v2 type is 24 of 30 parameters; the host carries six scalars and
  the model id. Every unsupported entry's reason names what the host does instead.
