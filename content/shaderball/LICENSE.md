# Shader ball

`shaderBall.obj` is the "no crease" shader ball from https://github.com/derkreature/ShaderBall
(`shaderBallNoCrease/shaderBall.obj`, fetched 2026-09-26), released into the public domain under the
Unlicense (https://unlicense.org). The FBX, the textures and the cover image from that repository are
not included; the OBJ carries positions, UVs and normals for 34,623 vertices and 33,980 quads.

The file is stored under Git LFS (`content/**/*.obj`). `hogshade.wgpu_host.load_obj` reads it.
