"""
HogShade: the IBL cook. Equirect HDR in; prefiltered specular cube, irradiance cube, SH9 and BRDF LUT out.
Package: hogshade/ibl

Spec: Docs/specs/e1-ibl-cook.md. Every convention a host must agree on is fixed in ``cubemap``
(face directions, equirect mapping) and ``prefilter`` (roughness to mip). Nothing here tonemaps.
"""
