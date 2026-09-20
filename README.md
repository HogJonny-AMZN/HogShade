# HogShade

**One polyglot PBR shading core for Maya, Blender, wgpu, OSL and MaterialX.**

HogShade is a new project. It replaces
[Maya-PBR-BRDF-VP2](https://github.com/hogjonny/Maya-PBR-BRDF-VP2), the same author's 2015 to 2017
physically based HLSL shader for Maya Viewport 2.0, which is now frozen as a record and points here.
HogShade is one shading core, written once in WGSL, that every DCC, renderer and engine the author
uses imports as a host: Maya, modern HLSL, Blender, wgpu, OSL, MaterialX. The legacy shaders are kept
in the tree, verbatim, as selectable models beside the new OpenPBR one, because this is a place to
compare shading models, not a runtime optimised for one.

**Version:** `0.1.0-dev` (see [VERSION](VERSION)). HogShade has its own semantic versioning and its
own roadmap. It does not continue the legacy project's numbering: "v1" and "v2" in this repo always
mean the 2015 and 2017 legacy shaders under `legacy/`, never a HogShade release. `0.1.0` is the end
of phase 1; `1.0.0` is the first release where the core renders the same material in Maya and wgpu.

The direction, the roadmap and the reasoning are in [Docs/](Docs/):

- [Docs/ROADMAP.md](Docs/ROADMAP.md): what is being built, in what order, and what is waiting on the owner.
- [Docs/design/2026-09-20-modernization-direction.md](Docs/design/2026-09-20-modernization-direction.md): the architecture and the decisions.
- [Docs/design/2026-09-20-game-shading-feature-catalogue.md](Docs/design/2026-09-20-game-shading-feature-catalogue.md): every game shading feature and where it lives.
- [Docs/design/2026-09-20-wysiwyg-blindspots.md](Docs/design/2026-09-20-wysiwyg-blindspots.md): what it takes for the same material to look the same everywhere.

## Status

Phase 1, repo hygiene. The legacy shaders compile clean under `fxc` (warnings only) and are the
reference every later phase is diffed against. Nothing under `core/` or `hosts/` exists yet.

| Path | What |
| --- | --- |
| `legacy/v1.0/` | 2015 shader: Disney, Cook-Torrance and "game" BRDFs, four bound Maya lights. Entry: `mayaVP2_pbrBRDF.fx` |
| `legacy/v2.0/` | 2017 shader: IBL from pre-convolved cubes, parallax occlusion mapping with self-shadowing, tone mapping, depth-peeling transparency, a 33-mode debug view. Entry: `V2_uv0bn-pbs_IBLenv.fx` (the July 2017 rewrite; `uv0bn-pbs_IBLenv.fx` is the earlier variant with 30 debug modes and no POM self-shadowing; both compile) |
| `Docs/` | Roadmap, pre-spec design, per-phase specs and plans; see [Docs/README.md](Docs/README.md) |

## Getting started: the legacy v2 shader in Maya

Tested with Maya 2026 on Windows (`Docs/verification/`). Maya 2026 is the only supported version.

1. **Put Viewport 2.0 on DirectX 11.** Windows > Settings/Preferences > Preferences > Display >
   Viewport 2.0 > Rendering engine: DirectX 11. Restart Maya if it asks. The `dx11Shader` plug-in
   does nothing under OpenGL.
2. **Load the plug-in.** Windows > Settings/Preferences > Plug-in Manager, tick `dx11Shader.mll`
   (Loaded and Auto load).
3. **Create the material.** In the Hypershade, create a `DX11 Shader` node. In its Attribute
   Editor, set **Shader File** to `legacy/v2.0/V2_uv0bn-pbs_IBLenv.fx` from your clone. The technique
   list should populate; pick `TessellationOFF`.
4. **Assign it** to a mesh with UVs, normals and tangents. A shader ball or a simple sphere is fine.
5. **Bind lights.** In the material's Attribute Editor, the `Light 0` to `Light 3` groups each have
   a **Light Binding** menu. Bind a directional or point light from the scene to `Light 0` and
   enable it. Unbound slots are ignored.
6. **Textures.** The shader samples its maps unconditionally, so a material with nothing assigned
   is not a useful picture. Assign, in the material's texture slots: `baseColorMap` (sRGB),
   `baseNormalMap` (tangent space) and `pbrMasksMap` (packed roughness, metalness, AO and cavity;
   the slot's UI label names the channel order). Optional: `heightMap` for parallax, `emissiveMap`,
   `cavityMap`, `ambOccMap`. Environment lighting reads two pre-convolved `.dds` cubes,
   `diffuseEnvTextureCube` and `specularEnvTextureCube`, plus `brdfTextureMap`; with none of these,
   untick `useEnvMaps` and rely on the bound lights and the hemispherical ambient sky and ground
   colours. There is no test content in the repository yet: the 200 MB that used to be here is being
   removed by the phase 1 history rewrite and a small shader-ball set under Git LFS replaces it
   (`Docs/plans/phase-1-hygiene.md`, task 12). Until it lands, bring your own maps.
7. **Debug views.** The `DEBUG VIEW` slider steps through 33 intermediate values, modes 0 to 32
   (base colour, masks, normals, Fresnel terms, IBL contributions, parallax UVs, self-occlusion
   shadow, triplanar weights). It is the quickest way to see what a parameter is doing, and it
   works without textures for the modes that do not read one.

To check a shader compiles without opening Maya, on a machine with the Windows 10 SDK:

```text
fxc /T fx_5_0 /D _MAYA_=1 /Fo out.fxo legacy\v2.0\V2_uv0bn-pbs_IBLenv.fx
```

Headless `mayapy` can load the effect but cannot compile it (no DirectX device). The scripted GUI
check in `tools/maya_load_check.py` launches Maya with the viewport forced to DirectX 11 for that
session, loads the shader, logs the technique list and quits; the last run is in
`Docs/verification/`. To run it:

```text
set MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11
set HOGSHADE_LOG_DIR=Docs/verification
maya.exe -script tools/maya_load_check.mel
```

## Licence

Apache 2.0. See [LICENSE](LICENSE). Third-party code embedded in the legacy shaders, and one
provenance question still open, are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Acknowledgements

Carried forward from the 2015 README. Nothing here was invented from scratch; the implementation
draws on a lot of generously published work:

- [derkreature](https://github.com/derkreature), for [IBLBaker](https://github.com/derkreature/IBLBaker)
  (the pre-convolved environment cubes the v2 shader reads) and the
  [ShaderBall](https://github.com/derkreature/ShaderBall) used for testing
- John Hable, [filmicworlds.com](http://www.filmicworlds.com/author/john-hable/) and filmicgames.com
- Alexandre Pestana, [Disney principled BRDF implementation](http://www.alexandre-pestana.com/disney-principled-brdf-implementation/)
- [ruh.li Cook-Torrance notes](http://ruh.li/GraphicsCookTorrance.html)
- Disney, [Physically Based Shading at Disney](https://disney-animation.s3.amazonaws.com/library/s2012_pbs_disney_brdf_notes_v2.pdf)
  and the [BRDF explorer](https://github.com/wdas/brdf/blob/master/src/brdfs/disney.brdf)
- Rory Driscoll, [Physically based shading](http://www.rorydriscoll.com/2013/11/22/physically-based-shading/)
- The parallax occlusion mapping in v2 is an unabashed adaptation of
  [hamish-milne/POMUnity](https://github.com/hamish-milne/POMUnity), the GameDev.net article
  "A closer look at parallax occlusion mapping", and the d3dcoder.net notes

And everyone who contributed to those projects.
