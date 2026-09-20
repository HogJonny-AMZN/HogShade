# Game shading and material features: the catalogue

Date: 2026-09-20. Companion to [2026-09-20-modernization-direction.md](2026-09-20-modernization-direction.md).

OpenPBR defines how a surface responds to light. It says nothing about how the inputs to that
response are authored, mapped onto geometry, blended, filtered or faked. Those are the "game-like"
features, and they are most of what an artist touches. This catalogue lists every modern touch
point, sorts it into three kinds, and says which core module, tier and host carries it.

Three kinds:

- **Physics.** The surface response. OpenPBR's domain. Lives in `core/models/` and `core/brdf/`.
- **Surface authoring.** How parameters arrive at a pixel: projections, layers, parallax, detail,
  masks. OpenPBR is silent here. Lives in `core/surface/` and the texture cook. This is the bulk
  of the catalogue and the bulk of the shader's user-facing value.
- **Engine.** Things a single material shader cannot do alone: probes, screen-space effects,
  shadows, decals, post. Live in SpriteJammer (and in `hog_rendering`), consuming the core.

Tier column refers to the SpriteJammer tiers in the roadmap: 0 Lambert, 1 legacy game, 2 game
standard, 3 OpenPBR forward. "Look-dev" means Maya, Blender and OSL hosts regardless of tier.

## Physics (OpenPBR)

| Feature | OpenPBR | Tier | Notes |
| --- | --- | --- | --- |
| Base: diffuse (Lambert, or Oren-Nayar via `base_diffuse_roughness`) | yes | 1 (Lambert), 2 (both) | Legacy v1/v2 used Lambert and a Burley option |
| Base: metal via `base_metalness`, F82-tint Fresnel | yes | 1 (Schlick), 2 (F82) | glTF carries metalness; F82 edge tint is OpenPBR-only, tier 3 |
| Specular: GGX, `specular_roughness`, `specular_ior`, `specular_weight`, `specular_color` | yes | 1 (Blinn-Phong or GGX-lite), 2 (GGX + height-correlated Smith) | glTF `KHR_materials_ior` and `KHR_materials_specular` map directly |
| Anisotropy: `specular_anisotropy`, `specular_rotation` | yes | 2 (optional), 3 | Needs tangents in the G-buffer or a forward path; glTF `KHR_materials_anisotropy`; brushed metal, hair |
| Multiscatter energy compensation | implied | 2, 3 | Kulla-Conty style LUT; without it rough metals go dark |
| Coat: `coat_weight`, roughness, IOR, colour, anisotropy, darkening | yes | 3 | glTF `KHR_materials_clearcoat`; car paint, varnish |
| Fuzz (sheen): `fuzz_weight`, colour, roughness | yes | 3 | glTF `KHR_materials_sheen`; cloth. Engine cloth is often a separate shading model ID instead |
| Thin-film iridescence: `thin_film_weight`, thickness, IOR | yes | 3 | glTF `KHR_materials_iridescence`; cheap enough for tier 2 if wanted |
| Emission: `emission_luminance`, colour | yes | all | HDR intensity feeds bloom; glTF `KHR_materials_emissive_strength` |
| Subsurface: `subsurface_weight`, colour, radius, scale, anisotropy | yes | 3 approximated | Viewport: wrap lighting or screen-space diffusion. Engine: usually a "subsurface" or "foliage" shading model ID with a thickness map |
| Transmission: `transmission_weight`, colour, depth, dispersion | yes | 3 thin-walled only | glTF `KHR_materials_transmission` + `volume`; refraction is out of scope for a forward viewport shader |
| Geometry: `geometry_opacity`, `geometry_thin_walled`, `geometry_normal`, `geometry_coat_normal`, `geometry_tangent` | yes | all | Opacity maps to the alpha-mode enum; coat normal is a second normal map, tier 3 |
| Energy conservation between slabs (albedo scaling) | yes | 2, 3 | Tier 1 is not energy conserving by design; that is what the legacy model is |

## Surface authoring (OpenPBR is silent; this is `core/surface/` and the cook)

### Projection and tiling

| Feature | Tier | Hosts | Notes |
| --- | --- | --- | --- |
| UV sets, UV transform (tile, offset, rotate), per-texture | all | all | Maya UV set selection; glTF `KHR_texture_transform` |
| Triplanar, world or object space, explicit up axis, tiling in metres | 2, 3, look-dev | Maya, Blender nodes, OSL, wgpu | Normalised weights with a sharpness exponent; per-plane tangent frames for normal maps; per-axis rotation to break symmetry. The owner's stated feature |
| Biplanar | 2 | wgpu | Two-sample variant for the horde tier; same weights, drops the smallest axis |
| Stochastic and hex tiling (Deliot-Heitz, Burley) | 2, 3, look-dev | all except OSL closure limits | Kills visible repetition on terrain and large props; costs three samples plus a blend |
| Detail maps: detail normal, detail albedo, detail roughness with a mask and a tiling scale | 2, 3 | all | Normal blending by reoriented normal mapping (RNM) or partial derivatives; UDN and whiteout as cheaper options |
| Macro variation: low-frequency tint and roughness noise in world space | 2 | all | Breaks tiling at distance; one noise sample |
| World-aligned coverage (snow, moss, dust): world-up mask with a height and normal threshold | 2, 3 | all | Uses the triplanar weights' up component; blends a second material set |
| Wetness and puddles: darkens base, drops roughness, raises F0, puddle mask from height | 2, 3 | all | Standard "wet surface" maths; a per-material or per-region scalar |
| Decal-ready inputs: per-pixel material override from a screen-space decal buffer | engine | wgpu | The shader reads a DBuffer; the decal projection itself is engine work |

### Height, parallax and depth

| Feature | Tier | Hosts | Notes |
| --- | --- | --- | --- |
| Height map input, shared by all of the below | all | all | One channel, authoring-set full precision, runtime packed |
| Parallax offset mapping (single step) | 1, 2 | all | Cheapest; the horde tier's option |
| Relief and steep parallax (fixed-step ray march) | 2 | all raster | Between offset and POM |
| Parallax occlusion mapping: ray march with linear interpolation, LOD by distance, sample count by view angle | 2, 3, look-dev | Maya, Blender gpu, wgpu; OSL offset-only | The v2 feature, rebuilt per projection for triplanar |
| POM self-shadowing (soft and hard) | 3, look-dev | raster hosts | v2 had it; expensive; keep behind a flag |
| Silhouette clipping at UV borders | 3, look-dev | raster hosts | Discards outside the parallaxed tile; only on tiling-safe surfaces |
| Pixel depth offset (PDO): write the parallaxed depth so shadows, decals and intersections respect the displaced surface | 2, 3 | wgpu, Maya | Writing `frag_depth` disables early-Z; SpriteJammer's "Depth Offset Maps" (ADR-002) is exactly this, and it is already a per-material opt-in there. The shadow pass must apply the same offset or contact shadows detach |
| Tessellation and displacement | look-dev | Maya (dx11 hull/domain), Blender | v2 had a `TessellationOFF` technique; real displacement is a look-dev comparison against POM, not an engine feature here |
| Vertex offset: wind, sway, flag, breathing | 2 (engine) | wgpu, Maya preview | Vertex shader work driven by a mask; foliage and cloth. Ties into the skinned path |

### Blending and layering

| Feature | Tier | Hosts | Notes |
| --- | --- | --- | --- |
| Vertex colour masks: layer blend, AO, wetness, tint (sRGB-aware) | all | all | v2 had vertex colour and vertex AO |
| Vertex alpha for dissolve and fade | all | all | Pairs with the alpha-mode enum |
| Height-based layer blending (two to four layers, height maps sharpen the transition) | 2, 3 | all | Terrain and props; the classic UE "height lerp" |
| Index and weight splat blending from a mask texture | 2 | wgpu, Maya | The owner's IndexBlendMask tool produces the input; LargeWorlds terrain consumes it |
| Material layer stack in the editor (base plus N layers with masks) | tooling | editor | Authoring convenience over the blends above; the parameter schema must allow nested layers |
| Two-sided lighting with back-face normal flip and optional translucency | 2, 3 | all | Foliage cards; cheap thin translucency uses a thickness or transmission mask |

### Occlusion and micro detail

| Feature | Tier | Hosts | Notes |
| --- | --- | --- | --- |
| Ambient occlusion map (in the ORM texture's red channel) | all | all | Diffuse only, by convention |
| Specular occlusion from AO (Lagarde) and from bent normals | 2, 3 | all | Stops metals glowing in crevices |
| Cavity and micro-cavity map (multiplies specular, optionally diffuse) | 2, 3 | all | v1/v2 had cavity |
| Bent normals for diffuse occlusion direction | 3 | forward, look-dev | Rare in games; keep for look-dev comparison |
| Horizon-based specular occlusion (normal map horizon clamp) | 2 | raster | Removes light leaks where the normal map tilts below the geometry horizon |
| Micro-shadowing from AO and NdotL | 2 | raster | Cheap contact-darkening trick |

### Texture data and filtering

| Feature | Tier | Hosts | Notes |
| --- | --- | --- | --- |
| Packed runtime set: base colour + alpha or mask, normal (BC5, +Y), ORM, emissive, height, optional detail and coat normal | all | wgpu; look-dev reads the authoring set | The cook produces this; see the blind-spot spec |
| Normal map strength and green-channel flip | all | all | Per texture, in the schema |
| Roughness from normal variance (Toksvig, LEAN) baked into mips | 2, 3 | cook | Specular anti-aliasing at distance |
| Geometric specular anti-aliasing in the shader | 2, 3 | raster | Screen-space derivative of the normal widens roughness |
| Mip bias and anisotropic filtering settings per texture | all | all | Sampler state in the schema |
| Colour space per texture: sRGB for base colour and emissive, raw for everything else | all | all | Declared, never inferred |
| Alpha-to-coverage and dithered alpha | 2 | wgpu, Maya | MASK mode with soft edges under MSAA; SpriteJammer uses dithered alpha |
| Dithered LOD and distance fade | engine | wgpu | Temporal dither on the alpha test; an engine per-instance scalar |

## Rendering paths: which half of the core each feature runs in

SpriteJammer is deferred; the DCC hosts are forward. The core is split at the G-buffer (see the
direction spec). Every feature above belongs to one half, and that decides where it runs and what
it costs in a deferred frame:

| Half | Runs in | Features |
| --- | --- | --- |
| Material half (`surface/`, model `inputs()`) | Forward: the material shader. Deferred: `gbuffer_fill`, once per pixel of opaque geometry | UV and triplanar projection, stochastic tiling, detail maps, macro variation, coverage, wetness, parallax and POM, PDO, vertex offset, layer blending, vertex masks, cavity, texture filtering. All of it is paid once and never per light |
| Lighting half (`brdf/`, model `evaluate()`, `lighting/`) | Forward: same shader. Deferred: `deferred_light`, once per pixel per light after culling | Diffuse and specular lobes, multiscatter, coat, fuzz, iridescence, subsurface approximation, specular occlusion, horizon clamp, micro-shadowing, IBL |
| Shadow and depth entry | Shadow maps and the depth prepass | Alpha mask, vertex offset, PDO. Nothing else |
| Forward-only | Engine hero and transparent passes, all DCC hosts | Anything the G-buffer cannot carry: anisotropy, coat, fuzz, thin-film, subsurface, transmission, alpha BLEND |

The practical consequence for the engine: the expensive surface-authoring features (POM, stochastic
tiling, layering) cost the same in deferred as in forward and do not multiply with light count,
while the physics tiers are what scale with lights. That is why tier 1 versus tier 2 is a
lighting-half choice and POM versus offset mapping is a material-half choice, and the two are
capped independently.

## Lights: how they reach the shader

The v2 shader binds Maya scene lights into a fixed array of slots through `Object = "Light N"`
annotations (`MayaLight lights[MAX_NUM_MAYA_LIGHTS]`; 4 slots in the committed v2; the owner recalls a 16-slot version, which is not in git and not in the
archived v3 folder). Maya fills the slots from whichever scene lights are bound, so the
shader "gathers" lights without knowing the scene: type, direction or position, colour, intensity,
cone, shadow map and view-projection per slot, and an enabled flag. That is the right shape for a
DCC and the right fallback for anything without a light list.

| Route | Host | Notes |
| --- | --- | --- |
| DCC light binding into fixed slots | Maya `dx11Shader`, `ogsfx` | The v2 pattern, kept. 16 slots as the default, a compile-time constant. Maya's viewport light limit applies. Shadow maps per slot where the host provides them |
| Engine light list in a storage buffer, culled per tile or cluster | wgpu | The engine already runs 500 lights this way; the core's light loop reads a buffer instead of an array. Light channels from GB2 mask the list |
| Fixed slots as an engine fallback | wgpu forward passes, `blender_gpu`, Substance Painter | Same 16-slot array, filled by the host from its own light list. Lets a forward material or a preview viewport light without the culling machinery |
| Renderer integration | OSL, Blender nodes, MaterialX | No light loop in the shader; the renderer owns lights |

The core therefore exposes one `ILightSource` over the punctual light description (type, position,
direction, colour in a stated unit, range and falloff, cone angles, shadow term) and two providers:
`FixedSlots<N>` and `LightBuffer`. Every model's light loop is written once against the interface.
Area lights via LTC and IES profiles are engine-side additions to `LightBuffer`; the fixed-slot
provider carries directional, point and spot only, which is what DCCs bind.

## Engine (SpriteJammer and `hog_rendering`; consumers of the core)

| Feature | Notes |
| --- | --- |
| Shading model ID per material: Lambert, legacy game, game standard, OpenPBR forward, plus later cloth, foliage or subsurface, hair, eye, unlit | The GB2 byte. UE's list is the reference; the roadmap's four tiers are the first four |
| Reflection probes: parallax-corrected box or sphere, blend between probes, one global sky probe | Split-sum needs a prefiltered probe; the octahedral probe machinery exists |
| Irradiance: SH L2 or a small irradiance map per probe | Diffuse IBL |
| Screen-space reflections and screen-space AO or GTAO | Both respect the Layer classification in GB2 |
| Shadow maps with PCF or PCSS, normal-offset bias, PDO applied in the shadow pass | Contact shadows detach without the PDO in both passes |
| Light types: directional, point, spot with cookie, area via LTC, IES profiles, light channels | 500 lights already run; channels are in GB2 |
| Clustered or tiled light culling | Exists as 2D tiled per the contested ADR-002 claim |
| Deferred decals (DBuffer) | Engine projection, shader reads |
| Fog: height fog, distance fog | Post-light, before tonemap |
| Post: exposure (auto or fixed EV), bloom from HDR emissive, colour grading LUT, the shared view transform | `hog_color` has the maths; the OCIO config from the blind-spot spec fixes the transform |
| GPU instancing with per-instance colour and material scalar overrides | The crowd tint already does this; extend to wetness and tier cap |
| Skinning and vertex animation textures | The skinned path exists; wind is a vertex-offset feature above |
| Material instances: a parent material with overridable parameters | Editor and content model, not a shader feature; the schema needs "overridable" per parameter |

## Content tools and workflow touch points

| Touch point | What it needs from this repo |
| --- | --- |
| Substance Painter and Designer | An export preset for the packed runtime set and one for the authoring set; Painter's viewport shader can be given the game profile as a GLSL shader so Painter is WYSIWYG too (a possible seventh host, cheap because it is GLSL) |
| Maya LookdevX | The `.mtlx` document and the OpenPBR node; the `dx11Shader` host stays for the legacy models and the research views |
| Blender | The node generator add-on with an "export game profile to glTF" button; the calibration scene as a `.blend` |
| Houdini | Reads MaterialX natively (Karma) and OSL; no extra host. A BATS worker can bake there |
| glTF | The game-profile interchange; the converter table; the Khronos validator in CI (S14 found it is the only thing that catches malformed data) |
| BATS and Job_Orchestrator | Texture cook, IBL and LUT bake, calibration capture in each host, sprite bake. Every reproducible step is a MODULE-mode job in a `hogshade.jobs` library with an agent-readable manifest, registered so the MCP tools list it (roadmap, track E) |
| Engine editor | Material panel generated from the schema, live link over the command bus, tier cap as a setting |

## What the direction spec did not name and now must

- Stochastic and hex tiling, detail maps with RNM blending, macro variation.
- World-aligned coverage and wetness.
- PDO and its shadow-pass counterpart, named as the engine's existing Depth Offset Maps.
- Height-based and splat layer blending, and the editor layer stack.
- Specular occlusion, cavity, horizon clamp, micro-shadowing.
- Two-sided foliage with thin translucency; wind vertex offset.
- Specular anti-aliasing in both the cook and the shader.
- A Substance Painter GLSL host as an option.
- The light-provider split: DCC-bound fixed slots (the v2 gather pattern, 16 slots) as the universal
  fallback, an engine light buffer as the fast path, one light loop against one interface.

These are added to the roadmap under C4 (surface), C6 (hosts) and D (engine).
