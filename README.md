# HogShade

**One polyglot PBR shading core for Maya, Blender, wgpu, OSL and MaterialX.**

HogShade is a shading research repo. It grew out of
[Maya-PBR-BRDF-VP2](https://github.com/hogjonny/Maya-PBR-BRDF-VP2), a 2015 to 2017 physically based
HLSL shader for the Maya Viewport 2.0 `dx11Shader` plug-in, and is becoming one shading core, written
once, that every DCC, renderer and engine the author uses imports as a host. The legacy shaders stay
in the tree, verbatim, as selectable models beside the new ones: this is a place to compare shading
models, not a runtime optimised for one.

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
| `legacy/v2.0/` | 2017 shader: IBL from pre-convolved cubes, parallax occlusion mapping with self-shadowing, tone mapping, depth-peeling transparency, a 32-mode debug view. Entry: `uv0bn-pbs_IBLenv.fx` |
| `Docs/` | Roadmap, pre-spec design, per-phase specs and plans; see [Docs/README.md](Docs/README.md) |

## Getting started: the legacy v2 shader in Maya

Tested with Maya 2026 on Windows. Maya 2024 should behave the same; report if it does not.

1. **Put Viewport 2.0 on DirectX 11.** Windows > Settings/Preferences > Preferences > Display >
   Viewport 2.0 > Rendering engine: DirectX 11. Restart Maya if it asks. The `dx11Shader` plug-in
   does nothing under OpenGL.
2. **Load the plug-in.** Windows > Settings/Preferences > Plug-in Manager, tick `dx11Shader.mll`
   (Loaded and Auto load).
3. **Create the material.** In the Hypershade, create a `DX11 Shader` node. In its Attribute
   Editor, set **Shader File** to `legacy/v2.0/uv0bn-pbs_IBLenv.fx` from your clone. The technique
   list should populate; pick `TessellationOFF`.
4. **Assign it** to a mesh with UVs, normals and tangents. A shader ball or a simple sphere is fine.
5. **Bind lights.** In the material's Attribute Editor, the `Light 0` to `Light 3` groups each have
   a **Light Binding** menu. Bind a directional or point light from the scene to `Light 0` and
   enable it. Unbound slots are ignored.
6. **Textures.** The material expects a base colour, a normal map, and packed masks; the parameter
   names in the UI say which. Environment lighting reads two pre-convolved `.dds` cubes (diffuse and
   specular). The 200 MB of test content that used to live in this repo is being removed by the phase 1
   history rewrite and replaced by a small set under Git LFS; see `Docs/plans/phase-1-hygiene.md`.
7. **Debug views.** The `DEBUG VIEW` slider steps through 32 intermediate values (base colour,
   roughness, normals, Fresnel terms, IBL contributions, parallax UVs, triplanar weights). It is the
   quickest way to see what a parameter is doing.

To check a shader compiles without opening Maya, on a machine with the Windows 10 SDK:

```text
fxc /T fx_5_0 /D _MAYA_=1 /Fo out.fxo legacy\v2.0\uv0bn-pbs_IBLenv.fx
```

Headless `mayapy` can load the effect but cannot compile it (no DirectX device). The scripted GUI
check in `tools/maya_load_check.py` launches Maya with the viewport forced to DirectX 11 for that
session, loads the shader, logs the technique list and quits; the last run is in
`Docs/verification/`. To run it:

```text
set MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11
set HOGSHADE_LOG_DIR=Docserification
maya.exe -script tools\maya_load_check.mel
```

## Licence

Apache 2.0. See [LICENSE](LICENSE).

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
