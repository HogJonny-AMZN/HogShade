# S2 spec: the generators, the Maya shell's material UI and the docs table from the schema

**Status:** Proposed. Drafted 2026-10-01 from the locked design, after S1 (#31, #33); the owner approves
it, then the plan runs as one PR. S2 needs nothing from gate G4.

Date: 2026-10-01. Design: [../../design/2026-09-27-material-schema.md](../../design/2026-09-27-material-schema.md),
"The Python library" (`generate(host)`) and "Increments" (S2). Decision:
[ADR-009](../../decisions/ADR-009-hogshade-owns-the-material-schema.md). S1:
[s1-material-schema.md](s1-material-schema.md). Plan: [../plans/s2-material-generators.md](../plans/s2-material-generators.md).
Vocabulary: [../../glossary.md](../../glossary.md), "Materials".

## Deliverable

`hogshade.material.generate(host)` returns one host's material UI as text, produced from the shipped
material-type files and a per-host map of names. Two hosts in S2:

- `maya_dx11`: the material block of `hosts/maya_dx11/hogshade.fx` (the maps, the material properties,
  the normal parameters, the legacy v1 lobes, the parallax group), which today is hand-written. After S2
  the block sits between two marker lines in the shell and is generated; a tool regenerates it or checks
  it, CI runs the check, and a hand edit inside the markers fails CI. This is the design's WYSIWYG lever:
  the shell's UI cannot drift from the schema.
- `docs`: a Markdown reference of every material type (one table per type: parameter, type, default,
  range, group, widget, semantic, doc), written to `Docs/reference/material-types.md`, generated whole and
  checked the same way.

Nothing renders differently after S2. The generated block declares the same parameters, defaults, ranges,
labels, orders, colour spaces and semantics the shell declares today; the first regeneration is checked
by a test that the shell's parameter set, defaults and ranges before and after are identical (the union
test of S1 is the instrument). The wgpu binding is S3; Blender and the `ogsfx` host are later.

## Package layout

```text
hogshade/material/
  generators.py                 # generate(host, **options) -> str; one function per host inside
  hosts/                        # package data: one map per host
    maya_dx11.json
tools/generate_material_ui.py   # --check (CI) | --write; both hosts; a diff on mismatch
hosts/maya_dx11/hogshade.fx     # the block between the markers is generated; everything else hand-written
Docs/reference/material-types.md  # generated whole; its first line says so
tests/material/test_material_generate.py
```

`generators.py`, not `generate.py`: the package exports `generate`, and a module of that name would be
shadowed (failure-modes entry 13). `pyproject.toml` package data gains `hosts/*.json`.

## The host map

One JSON file per host, keyed by schema parameter name, carrying only what the schema does not know:
the host's names, labels and ordering. Defaults, ranges, choices, colour spaces and docs always come from
the schema; a value repeated in the map is a finding.

```json
{
  "host": "maya_dx11", "version": 1,
  "groups": {
    "Material Maps": 100, "Material Properties": 150, "Normal Params": 207,
    "Legacy v1 Disney": 180, "Parallax Occlusion": 190
  },
  "parameters": {
    "roughness": {"name": "materialRoughness", "label": "Roughness", "group": "Material Properties", "order": 151,
                  "map": {"name": "roughnessMap", "flag": "useRoughnessMap", "label": "Roughness Map (green)", "order": 104}},
    "opacity": {"name": "opacity", "label": "Opacity", "group": "Material Properties", "order": 166, "semantic": "OPACITY"},
    "normal_flip": {"group": "Normal Params", "components": [
        {"name": "NormalCoordsysX", "label": "Normal X (Red)", "order": 207},
        {"name": "NormalCoordsysY", "label": "Normal Y (Green)", "order": 208},
        {"name": "NormalCoordsysZ", "label": "Normal Z (Blue)", "order": 209}],
      "component_choices": "Positive:Negative"},
    "normal_map": {"map": {"name": "baseNormalMap", "flag": "useNormalMap", "label": "Normal Map (tangent, +Y up)", "order": 102}},
    "parallax_enabled": {"name": "useParallaxOcclusionMapping", "label": "Use Parallax Occlusion Mapping", "group": "Parallax Occlusion", "order": 190},
    "self_shadow": {"name": "parallaxOccShadowType", "label": "Self Shadow", "group": "Parallax Occlusion", "order": 194}
  }
}
```

Rules, checked by `check_host_map()` and a test on the shipped file:

- The map covers exactly the union of the legacy types' parameters (`hogshade-legacy-v2` and
  `hogshade-legacy-v1`; `hogshade-lambert` is a subset). A parameter present in two types has one host-map
  entry, and its definitions agree on the fields the Maya emission reads (`type`, `default`, `range`,
  `choices`, `colour_space`); a test asserts that. The fields that do not reach the block may differ
  (`doc`, `strength`: v1's `normal_map` carries `strength` and v2's does not, after #33). A parameter
  without an entry, or an entry without a parameter, is a finding.
- An entry carries `name`, `label`, `group`, `order` for a parameter that has a factor (every type but
  `texture`); a texturable parameter also carries `map` (`name`, `flag`, `label`, `order`); a `texture`
  parameter carries only `map`. `vector3` carries `components` (three) and `component_choices` instead of
  `name`; the shell exposes a flip vector as three sign dropdowns.
- `group` is one of the map's `groups`; every `order`, including map orders and the `order + 1` of each
  map's flag, is unique across the host; `name`, `flag` and component names are unique HLSL identifiers.
- `semantic` is optional and only `OPACITY` in S2 (the one Maya semantic the shell uses).
- Host-only parameters are not in the map and not in the generated block: `shadingModel`,
  `linearSpaceLighting`, `gammaCorrectionValue`, `shadowMultiplier` stay hand-written outside the markers,
  in a "display and model" section the plan moves them to.

## The generated Maya block

Between `// BEGIN hogshade.material generated (tools/generate_material_ui.py --write); do not edit` and
`// END hogshade.material generated`, in this order: the maps (a `Texture2D` and its `bool` use flag per
texturable parameter, `ColorSpace` from the schema: `srgb` is `"sRGB"`, `raw` is `"Raw"`), then the
groups by their `groups` order, each parameter as an explicit declaration:

| Schema | Declaration |
| --- | --- |
| `color3` | `float3 NAME < UIGroup; UIName; UIWidget = "Color"; UIOrder; > = { r, g, b };` |
| `float` | `float NAME [: SEMANTIC] < UIGroup; UIName; UIWidget = "Slider"; UIMin; UIMax; UIStep = 0.001; UIOrder; > = default;` |
| `int` | as `float`, type `int`, `UIStep = 1` |
| `bool` | `bool NAME < UIGroup; UIName; UIOrder; > = true|false;` |
| `enum` | `int NAME < UIGroup; UIFieldNames = "a:b:c" (the choices); UIName; UIOrder; > = index;` |
| `vector3` | three `int` dropdowns with `UIFieldNames = component_choices`, `0` for +1, `1` for -1 |
| `texture` | the map pair only |

`soft` ranges emit the hard `UIMin`/`UIMax` the schema gives (Maya's slider bounds are the UI's, the
typed field accepts beyond them). The shell's `HOGSHADE_SLIDER`, `HOGSHADE_BOOL`, `HOGSHADE_V1` and
`HOGSHADE_MAP` macros are retired: explicit declarations are what the generator emits and what the
S1 union test parses (its macro classification becomes a group classification only). The block's
formatting is fixed by the generator; `--write` never touches text outside the markers.

The shell's body reads the same identifiers it reads today (`materialRoughness`, `useRoughnessMap`,
`NormalCoordsysX`, ...); the map's names are chosen to keep every one of them, so the shell's
functions do not change in S2. A test asserts each identifier the body uses is declared by the block or
in the hand-written sections.

## The docs reference

`generate("docs")` writes, for each shipped type in `types()` order, a heading, the title, the groups,
and a table of parameters in file order: name, type, default, range (with "soft" when it is), group,
widget, semantic, colour space, overridable, tier, doc. The file's first line names the generator and
the commit's intent (do not edit). `Docs/README.md` gains the reference row; `check_docs.py` sees a
`**Status:**` line (Living) that the generator writes.

## The library

| Function | Contract |
| --- | --- |
| `generate(host, *, types=None) -> str` | The host's text: `"maya_dx11"` the material block, `"docs"` the reference. `types` restricts the docs reference; the Maya block always takes the legacy union. Unknown host is `MaterialError`. |
| `host_map(host) -> dict` | The shipped map, parsed; `MaterialError` when there is none. |
| `check_host_map(host_map, types) -> list[Finding]` | The rules above; empty when the map is complete and consistent. |
| `hosts() -> list[str]` | The shipped maps' names. |

`tools/generate_material_ui.py --check` regenerates both outputs to memory and compares: the Maya block
against the text between the shell's markers, the reference against the file; a mismatch prints a unified
diff and exits 1 (the CI step). `--write` replaces the block and the file. Missing markers are an error
naming the shell.

## Tests (`tests/material/test_material_generate.py`)

- The shipped map passes `check_host_map`; a map missing a parameter, naming a parameter that does not
  exist, repeating an order, repeating a name, or carrying a `default` key each produce the named finding.
- `generate("maya_dx11")` equals the text between the markers of the committed shell (the CI check as a
  test, so `pytest` alone catches drift).
- Before and after: the generated block, parsed with the S1 union test's parser, declares the same
  parameter set as the schema union (the existing test now runs over generated text); a second test
  parses the block back and asserts every decoded default and every emitted slider range (`float` and
  `int`; a colour or a vector carries no range in HLSL) equals the schema's.
- Every identifier the shell's body references (regex over the text outside the markers for the map's
  names and flags) is declared.
- `generate("docs")` equals the committed reference; its tables list every parameter of every type.
- The import test of S1 still holds (no new dependency).

## Acceptance gate

- `uv run pytest tests/material` green on CI with the new step `uv run tools/generate_material_ui.py --check`
  in `.github/workflows/tests.yml`; `tools/check_docs.py` and `check_hygiene.py` clean.
- The regenerated shell compiles and loads in Maya 2026: `tools/maya/ibl_check.py` on the
  `hogshade_maya_gui` worker (a BATS job when the orchestrator runs; otherwise a human launch, stated in
  the PR), with the pictures under `verification/maya-2026/ibl-check/` compared to the previous check's,
  and the attribute editor showing the same groups and sliders. A human run, since CI has no Maya.
- `tools/build_shaders.py --check --require-compilers` still clean (the core is untouched).

## Out of scope

- The wgpu binding (`bind()`, S3), the Blender panel, the `ogsfx` host's UI.
- Any change to parameter names, defaults or ranges: S2 reproduces the shell's UI, it does not redesign it.
  A difference the first regeneration surfaces is a finding to settle before `--write`, not a silent fix.
- The standard type's UI in any host (no host carries the standard before C3 and S3).
