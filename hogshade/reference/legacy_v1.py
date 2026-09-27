"""
HogShade: NumPy mirror of core/models/legacy_v1.wgsl, function by function, same names minus the prefix.
Package: hogshade/reference/legacy_v1

Every function works on n rows at once. The v1 characteristics and the port's deviations are listed
in the WGSL header; this file is the numeric specification the GPU is checked against.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hogshade.core_constants import INV_PI, MODEL_LEGACY_V1
from hogshade.reference import brdf, lighting
from hogshade.reference._common import _col, _unit
from hogshade.reference.legacy_v2 import EnvSamples

_MODULE_NAME = "hogshade.reference.legacy_v1"
__version__ = "0.1.0"
__updated__ = "2026-09-27"

DEBUG_MODE_NAMES = ("final", "NdotL", "clampNdotL", "NdotV", "H.x", "NdotH", "LdotH", "VdotH", "vis")


@dataclass
class Material:
    base_color: NDArray
    metalness: NDArray
    subsurface: NDArray
    specular: NDArray
    roughness: NDArray
    specular_tint: NDArray
    anisotropic: NDArray
    sheen: NDArray
    sheen_tint: NDArray
    clearcoat: NDArray
    clearcoat_gloss: NDArray
    use_vertex_color_ao: NDArray
    has_alpha: NDArray
    use_vertex_alpha: NDArray
    use_cutout_alpha: NDArray
    flip_backface_normals: NDArray
    rough_is_gloss: NDArray
    use_specular_mask: NDArray
    normal_flip: NDArray


@dataclass
class Samples:
    base_color: NDArray  # (n, 4)
    specular: NDArray  # (n, 4)
    roughness: NDArray
    metalness: NDArray
    ao: NDArray  # (n, 3)
    normal_ts: NDArray
    use_base_map: NDArray
    use_specular_map: NDArray
    use_roughness_map: NDArray
    use_metalness_map: NDArray
    use_normal_map: NDArray


@dataclass
class Geometry:
    normal_ws: NDArray
    tangent_ws: NDArray
    binormal_ws: NDArray
    view_ws: NDArray
    position_ws: NDArray
    vertex_color: NDArray  # (n, 4)
    front_face: NDArray


@dataclass
class Inputs:
    """ShadingInputs, flattened, with the tangent frame and the two model parameter vectors."""

    base_color: NDArray
    metalness: NDArray
    roughness: NDArray
    ao: NDArray
    emissive: NDArray
    normal_ws: NDArray
    view_ws: NDArray
    position_ws: NDArray
    specular_f0: NDArray
    cavity: NDArray
    opacity: NDArray
    specular_weight: NDArray
    tangent_ws: NDArray
    binormal_ws: NDArray
    params_a: NDArray  # (n, 4): subsurface, specular_tint, anisotropic, sheen
    params_b: NDArray  # (n, 4): sheen_tint, clearcoat, clearcoat_gloss, 0
    model: int = MODEL_LEGACY_V1


@dataclass
class Terms:
    color: NDArray
    specular: NDArray  # (n,)


def luminance(c: NDArray) -> NDArray:
    return 0.3 * c[..., 0] + 0.6 * c[..., 1] + 0.1 * c[..., 2]


def _ctint(albedo: NDArray) -> NDArray:
    lum = luminance(albedo)
    safe = np.where(lum > 0.0, lum, 1.0)
    return np.where((lum > 0.0)[:, None], albedo / safe[:, None], 1.0)


def inputs(m: Material, s: Samples, g: Geometry) -> Inputs:
    on = lambda f: np.asarray(f) != 0
    albedo = np.where(on(s.use_base_map)[:, None], s.base_color[:, :3], m.base_color)
    spec_map = np.where(on(m.use_specular_mask), s.specular[:, 3], s.specular[:, 0])
    spec_a = np.where(on(s.use_specular_map), spec_map, m.specular)
    rough_map = np.where(on(m.rough_is_gloss), s.roughness, 1.0 - s.roughness)
    rough_a = np.where(on(s.use_roughness_map), rough_map, m.roughness)
    metal_a = np.where(on(s.use_metalness_map), s.metalness, m.metalness)
    ao = np.where(on(m.use_vertex_color_ao)[:, None], s.ao * g.vertex_color[:, :3], s.ao)
    opacity = np.ones(len(albedo))
    cut = on(m.use_cutout_alpha)
    opacity = np.where(cut & on(m.has_alpha), s.base_color[:, 3], opacity)
    opacity = np.where(cut & on(m.use_vertex_alpha), opacity * g.vertex_color[:, 3], opacity)
    n = _unit(g.normal_ws)
    flip = on(m.flip_backface_normals) & ~on(g.front_face)
    n = np.where(flip[:, None], -n, n)
    t = _unit(g.tangent_ws)
    b = g.binormal_ws
    raw = s.normal_ts * m.normal_flip
    mapped = _unit(raw[:, 0:1] * t + raw[:, 1:2] * b + raw[:, 2:3] * n)
    n = np.where(on(s.use_normal_map)[:, None], mapped, n)
    ctint = _ctint(albedo)
    dielectric = _col(spec_a) * 0.08 * (1.0 + (ctint - 1.0) * _col(m.specular_tint))
    cspec0 = dielectric + (albedo - dielectric) * _col(metal_a)
    zeros = np.zeros((len(albedo), 4))
    return Inputs(
        base_color=albedo,
        metalness=metal_a,
        roughness=rough_a,
        ao=ao[:, 0],
        emissive=np.zeros_like(albedo),
        normal_ws=n,
        view_ws=_unit(g.view_ws),
        position_ws=g.position_ws,
        specular_f0=cspec0,
        cavity=np.ones(len(albedo)),
        opacity=opacity,
        specular_weight=spec_a,
        tangent_ws=t,
        binormal_ws=b,
        params_a=np.stack([m.subsurface, m.specular_tint, m.anisotropic, m.sheen], axis=-1),
        params_b=np.stack([m.sheen_tint, m.clearcoat, m.clearcoat_gloss, zeros[:, 0]], axis=-1),
    )


def env_lookup(i: Inputs) -> NDArray:
    n_dot_v = np.clip((i.view_ws * i.normal_ws).sum(-1), 0.0, 1.0)
    return np.stack([-n_dot_v, i.roughness], axis=-1)


def dbrdf(i: Inputs, l: NDArray) -> Terms:
    n, v, x, y = i.normal_ws, i.view_ws, i.tangent_ws, i.binormal_ws
    subsurface, anisotropic, sheen = i.params_a[:, 0], i.params_a[:, 2], i.params_a[:, 3]
    sheen_tint, clearcoat, clearcoat_gloss = i.params_b[:, 0], i.params_b[:, 1], i.params_b[:, 2]
    alpha = i.roughness * i.roughness
    h = _unit(l + v)
    nl = np.clip((n * l).sum(-1), 0.0, 1.0)
    nv = np.clip((n * v).sum(-1), 0.0, 1.0)
    nh = np.clip((n * h).sum(-1), 0.0, 1.0)
    lh = np.clip((l * h).sum(-1), 0.0, 1.0)
    cdlin = i.base_color
    ctint = _ctint(cdlin)
    cspec0 = i.specular_f0
    csheen = 1.0 + (ctint - 1.0) * _col(sheen_tint)
    fl = brdf.schlick_weight(nl)
    fv = brdf.schlick_weight(nv)
    fd90 = 0.5 + 2.0 * lh * lh * alpha
    fd = (1.0 + (fd90 - 1.0) * fl) * (1.0 + (fd90 - 1.0) * fv)
    fss90 = lh * lh * alpha
    fss = (0.999 + (fss90 - 0.999) * fl) * (0.999 + (fss90 - 0.999) * fv)
    ss = 1.25 * (fss * (1.0 / (nl + nv + 0.0001) - 0.5) + 0.5)
    aspect = np.sqrt(1.0 - anisotropic * 0.9)
    ax = np.maximum(0.001, (alpha * alpha) / aspect)
    ay = np.maximum(0.001, (alpha * alpha) * aspect)
    ds = brdf.gtr2_aniso(nh, (h * x).sum(-1), (h * y).sum(-1), ax, ay)
    fh = brdf.schlick_weight(lh)
    fs = cspec0 + (1.0 - cspec0) * _col(fh)
    roughg = (alpha * 0.5 + 0.5) ** 2
    gs = brdf.smith_g_ggx_disney(nl, roughg) * brdf.smith_g_ggx_disney(nv, roughg)
    fsheen = _col(fh * sheen) * csheen
    dr = brdf.gtr1(nh, 0.1 + (0.001 - 0.1) * clearcoat_gloss)
    fr = 0.04 + (1.0 - 0.04) * fh
    gr = brdf.smith_g_ggx_disney(nl, 0.25) * brdf.smith_g_ggx_disney(nv, 0.25)
    diffuse = fd + (ss - fd) * subsurface
    color = (INV_PI * _col(diffuse) * cdlin + fsheen) * _col((1.0 - i.metalness) * nl)
    spec_rgb = _col(gs) * fs * _col(ds)
    specular = (spec_rgb[:, 0] + 0.25 * clearcoat * gr * fr * dr) * nl
    return Terms(color, specular)


def evaluate_light(i: Inputs, light: NDArray, env: EnvSamples) -> NDArray:
    l_ws, att, valid = lighting.incident(light, i.position_ws)
    t = dbrdf(i, l_ws)
    out = (t.color + _col(t.specular * i.specular_weight)) * lighting.radiance(light, att)
    return np.where(valid[:, None], out, 0.0)


def evaluate_env(i: Inputs, env: EnvSamples) -> NDArray:
    albedo, metal = i.base_color, _col(i.metalness)
    dome = dbrdf(i, i.normal_ws)
    amb_total = dome.color * env.hemisphere
    diff_env = albedo * (1.0 - metal) * env.irradiance_over_pi
    cspec = (0.04 + (albedo - 0.04) * metal) * env.brdf[:, 0:1] + env.brdf[:, 1:2]
    spec_env = env.specular * cspec * _col(i.specular_weight)
    return (amb_total + diff_env + spec_env) * _col(i.ao)


def shade(i: Inputs, lights: list[NDArray], env: EnvSamples) -> NDArray:
    total = np.zeros_like(i.base_color)
    for light in lights:
        total = total + evaluate_light(i, light, env)
    return total + evaluate_env(i, env) + i.emissive


def debug(i: Inputs, lights: list[NDArray], env: EnvSamples, mode: int) -> NDArray:
    n = len(i.roughness)
    if mode == 0:
        return shade(i, lights, env)
    l = np.tile([0.0, 1.0, 0.0], (n, 1))
    if lights:
        l_ws, _att, valid = lighting.incident(lights[0], i.position_ws)
        l = np.where(valid[:, None], l_ws, l)
    nn, v = i.normal_ws, i.view_ws
    nl = (nn * l).sum(-1)
    nv = (nn * v).sum(-1)
    h = _unit(l + v)
    a = np.maximum(0.001, i.roughness * i.roughness)
    vis = brdf.vis_hable(nl, nv, a)
    grey = lambda x: np.repeat(np.asarray(x)[:, None], 3, axis=-1)
    table = {
        1: grey(nl),
        2: grey(np.maximum(nl, 0.0)),
        3: grey(nv),
        4: grey(h[:, 0]),
        5: grey((nn * h).sum(-1)),
        6: grey((l * h).sum(-1)),
        7: grey((v * h).sum(-1)),
        8: grey(vis),
    }
    return table.get(mode, np.zeros((n, 3)))


if __name__ == "__main__":
    print(len(DEBUG_MODE_NAMES), "debug modes; Cspec0 for grey 0.5 at specular 0.5:", 0.5 * 0.08)
