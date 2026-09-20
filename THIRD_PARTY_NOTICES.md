# Third-party notices

HogShade is Apache 2.0 (see `LICENSE`). The legacy shaders under `legacy/` embed or adapt code
from other projects. This file lists what a grep of that tree for copyright and licence text found,
so nothing is relicensed by accident.

| Where | What | Licence | Status |
| --- | --- | --- | --- |
| `legacy/v2.0/pbr.sif` | Disney principled BRDF functions, ported from the Walt Disney Animation Studios BRDF explorer | Apache 2.0 (Disney Enterprises, Inc.); original notice retained in the file | Compatible; retained |
| `legacy/v2.0/pbr.sif` | Snippets dedicated to the public domain by their author | Unlicense; notice retained in the file | Compatible; retained |
| `legacy/v2.0/V2_uv0bn-pbs_IBLenv.fx` (parallax occlusion) | Adapted from hamish-milne/POMUnity, a GameDev.net article and d3dcoder.net notes, as the source comments say | POMUnity: check its repository licence before announcing; the article and notes are cited, not copied | **To confirm** |
| `legacy/v1.0/propertyNames.fxh` | Material property-name macros | Was headed "@copyright 2015 Bifrost Engine" | **Resolved 2026-09-20.** The author's own file; the studio line was added by mistake at the time and the company no longer exists. Line removed and replaced with a note; the only edit ever made to a legacy file |

Nothing else in `legacy/` carries a copyright or licence notice. The legacy files are kept verbatim,
so these notices stay inside them as well as here.
