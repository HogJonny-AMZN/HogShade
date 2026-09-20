# WYSIWYG across the pipeline: blind spots in the modernization direction

Date: 2026-09-20. Reviews [2026-09-20-modernization-direction.md](2026-09-20-modernization-direction.md)
and [../ROADMAP.md](../ROADMAP.md) through a full-stack production lens: the same material must look
the same in the look-dev DCC, the content tools, the offline renderer and the engine's editor and
runtime. Each finding names the gap, why it breaks parity, and the fix that went into the roadmap.

The short version: **a shared BRDF is maybe a third of WYSIWYG.** The other two thirds are the
inputs (colour, lights, textures, geometry conventions) and the proof (automated capture and diff in
every host). The original direction covered the BRDF well and the rest barely.

## 1. Colour management is per host, so the same pixel displays differently

Maya 2026 defaults to an ACES 1.3 OCIO config. Blender 4.x defaults to AgX. SpriteJammer has its own
AgX in `tonemap_agx.wgsl`. Three view transforms, three looks, one material. The spec's "Maya's colour
management does the display" leaves each host to its own default.

**Fix.** The repo ships one OCIO config and every host uses it: Maya and Blender by pointing at it,
the engine by implementing the same view transform numerically and proving it against OCIO's output
on a test ramp. `hog_color` already has AgX and ACES; the proof is a numeric test, not a look. Texture
colour spaces are declared per texture (sRGB for colour, raw for data) in the material description,
never inferred from a filename.

## 2. Light units and IBL orientation are undefined

Maya lights are unitless intensities. Blender lights are watts. Engines use whatever they chose.
An HDR loaded in Maya (Y-up) and Blender (Z-up) points a different way unless the rotation is
specified. Cycles importance-samples the environment; the real-time hosts read prefiltered mips.
Without a convention, a "matched" light rig is matched by eye, which is the thing WYSIWYG exists to
remove.

**Fix.** A light-rig description in the repo: HDR file, rotation in a stated axis convention,
exposure in EV, and punctual lights in one unit with a documented conversion to each host. The IBL
prefilter and BRDF LUT are baked by one tool in this repo and shipped as content; no host runs its
own convolution for the real-time path. The bake is a BATS job so it is reproducible.

## 3. The game profile should be the glTF material model, not a hand-picked subset

The spec defines the game profile as "what a G-buffer can feed". glTF 2.0 with the KHR material
extensions (specular, ior, clearcoat, sheen, iridescence, transmission, emissive_strength) is a
published, tool-supported subset of the same physics, Blender exports it natively, SpriteJammer
already reads glTF, and Maya exports it through the glTF plug-in. Defining the profile as
"OpenPBR restricted to what glTF can carry" makes Blender to engine a no-code path and gives the
profile a spec other people maintain.

**Fix.** Game profile := OpenPBR parameters with a defined glTF mapping. The material description
is authored as MaterialX for look-dev and exported to glTF for the engine; a conversion table in the
repo says which OpenPBR parameter goes where and what is lost. Anything outside glTF is forward-only
(tier 3) by definition.

## 4. MaterialX is the interchange carrier and belongs early, not last

OpenPBR is defined as a MaterialX node graph. Maya LookdevX reads and writes it, USD carries it,
Blender imports it via USD, and MaterialX generates OSL and GLSL from it. Placing it last treats it
as one more host when it is the file format that lets a material travel between hosts.

**Fix.** Move the `.mtlx` document to phase 3 alongside the OpenPBR model. The material a user
authors is a `.mtlx`; each host imports it. The generated OSL and GLSL from MaterialX become
cross-checks for the hand-written hosts from that point on, not at the end.

## 5. One parameter schema should generate every host's UI

The spec has each host hand-writing its material UI: `.fx` annotations, a Blender add-on panel, an
engine editor panel. Four UIs, four places for a default or a range to drift.

**Fix.** A single machine-readable parameter schema (JSON or the `.mtlx` node definitions) with
name, type, range, default, UI group and colour space. A generator emits the Maya annotations block,
the Blender panel, the engine editor panel and the docs table. A test asserts every host's UI is
generated, not edited.

## 6. Texture packing, gamma and compression are unspecified

"Same names in every host" is not the same as the same bytes. Which channels pack into which
texture, whether roughness or glossiness is stored, whether the normal map is +Y or -Y, sRGB mips
generated in linear or not, BC5 for normals or BC7, and whether AO lives in the ORM texture's red
channel are all decisions that change the picture.

**Fix.** An authoring texture set (one map per parameter, full precision) and a runtime texture set
(packed, compressed) with one cook tool that converts the first to the second. Conventions written
down: OpenGL +Y normals (Blender's default; Maya's dx11Shader flips via a flag), ORM packing, sRGB
colour only for base colour and emissive, linear-space mip generation. The cook is a BATS job.

## 7. Tangent space must be MikkTSpace everywhere or normal maps do not match

A normal map baked in one tangent basis and read in another shows seams and shading direction
errors. Blender bakes MikkTSpace. Maya's dx11Shader uses the mesh's tangents, which Maya computes
its own way unless the FBX or glTF path supplies them. SpriteJammer imports glTF, which requires
MikkTSpace-compatible tangents when present and leaves generation to the importer otherwise.

**Fix.** MikkTSpace is the convention. The engine importer generates tangents with a MikkTSpace
implementation when the file has none. The Maya host reads supplied tangents and the test scene
carries them. The triplanar path builds its per-plane frames from world axes and is exempt.

## 8. Coordinate conventions for triplanar are unstated

Maya is Y-up in centimetres by default; Blender is Z-up in metres; SpriteJammer is its own. A
triplanar projection "in world space" tiles differently in each unless the projection axes, the
up axis and the tiling unit are declared.

**Fix.** Triplanar takes an explicit up axis and a tiling scale in metres. Each host passes its
own up axis and unit conversion. The debug view for projection axes exists to catch this.

## 9. Alpha and transparency modes are not defined

Maya offers depth peeling and weighted average. Blender has blend, hashed and clip. SpriteJammer
uses dithered alpha (ADR-002). OpenPBR has geometry opacity and nothing about how a rasteriser
should treat it.

**Fix.** One alpha-mode enum on the material, matching glTF's OPAQUE, MASK and BLEND, with each
host's mapping documented. MASK is the game default because it keeps early-Z and matches the
engine's dither. BLEND is look-dev only unless a tier needs it.

## 10. Sprite baking is the largest WYSIWYG risk in SpriteJammer

The engine bakes 3D sources to sprites (ADR-010). If a sprite is baked as lit colour, the runtime
lighting can never match a Maya look-dev of the same asset. If it is baked as material channels
(base colour, normal, roughness, metallic, emissive, per octahedral view) and lit in the deferred
pass, the shading model at runtime is the same one look-dev used. The G-buffer layout supports the
second; the roadmap did not say the bake must produce it.

**Fix.** The impostor bake outputs the game-profile channels, not lit colour. The bake tool renders
through the core (the `blender_gpu` or wgpu host) so the channels are the same the look-dev saw.
A lit-colour bake stays available as an explicit cheaper option, labelled as breaking parity.

## 11. Nothing proves parity; "screenshot diff" is a hope, not a tool

Each phase gate says "screenshot diff" and no phase builds the thing that takes screenshots.
Capturing a frame in Maya batch, Blender headless and an engine offscreen target are three
different scripts, and a diff needs a tolerance, a mask for the background and a report.

**Fix.** A calibration scene, not just a shader ball: a metal and a dielectric roughness ramp, an
18 percent grey card, a colour checker, a normal-map test tile, a triplanar cube, one alpha cutout.
Same camera, same rig, same HDR. A capture script per host (`mayapy`, `blender -b`, the engine's
offscreen path) and one diff tool producing a proof page in the style the owner already likes.
This is a phase of its own and lands before the OpenPBR model, so the model is judged by it.

## 12. Specular aliasing will make the engine look worse than the DCC at distance

A 2.5D long lens over a dense crowd means many high-frequency normals per pixel. Offline renderers
supersample; the engine does not. Without roughness filtering the engine sparkles where Maya and
Cycles do not, and no BRDF parity fixes it.

**Fix.** Normal-variance roughness filtering (Toksvig or the LEAN-style variant) in the game
profile's texture cook, plus geometric specular anti-aliasing in the light pass. Measured on the
crowd, not the shader ball.

## 13. Live look-dev has no link

WYSIWYG for an artist means change a slider in Maya and see the engine update. The engine has a
command bus (S16) that already takes `set_property` over MCP and gRPC; BATS speaks the same job
shape. Nothing in the plan connects a Maya material to it.

**Fix.** A material live link: the Maya host's parameter changes publish over the command bus to a
running engine, keyed by material name. Later, not first, but the bus design should not preclude it.

## 14. Versions are unpinned and generated code is not committed

Slang, naga, wgpu-py, Blender and Maya all move. Consumers vendoring generated WGSL should not need
Slang installed.

**Fix.** Pin naga and wgpu-py in `pyproject.toml`; CI on Maya 2026 where a
licence allows, Blender LTS; commit `hosts/*/generated/` so consumers vendor files, with a CI check
that regenerating produces no diff.

## 15. Terrain shares the surface module and was not mentioned

LargeWorlds terrain and any SpriteJammer ground will use triplanar with splat or index blending
(the owner already has an IndexBlendMask tool). That is the same `surface/` module plus a layer
blend the spec does not have.

**Fix.** `surface/` gains a layered-material blend (index mask or height-based) as a later item,
so terrain in both engines runs the same code as props.

## What changes in the roadmap

A new track E, "Parity and pipeline", carries items 1, 2, 6, 7, 11, 12, 14. Items 3, 4, 5, 8, 9
amend the spec's decisions. Item 10 amends track D. Items 13 and 15 are later items in tracks D and
C. The phase order changes in one place: the calibration scene and capture tooling (item 11) now
precede the OpenPBR model, and MaterialX (item 4) joins it.
