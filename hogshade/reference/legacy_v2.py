"""
HogShade: NumPy mirror of core/models/legacy_v2.wgsl, function by function, same names minus the prefix.
Package: hogshade/reference/legacy_v2

Every function works on n rows at once: vectors are (n, 3) arrays, scalars (n,) arrays, flags (n,)
integer arrays. The v2 characteristics and the port's deviations are listed in the WGSL header;
this file is the numeric specification the GPU is checked against.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hogshade.core_constants import MODEL_LEGACY_V2, ROUGHNESS_BIAS
from hogshade.reference import brdf, lighting

_MODULE_NAME = "hogshade.reference.legacy_v2"
__version__ = "0.1.0"
__updated__ = "2026-09-25"

N_DOT_V_EPSILON = 1e-4  # v2: #define EPSILON 10e-5f

# g_DebugMode 0..32 of V2_uv0bn-pbs_IBLenv.fx, in order; the UI string of the legacy shader.
DEBUG_MODE_NAMES = (
    "final",
    "baseColorTex.rgb",
    "baseColorTex.aaa",
    "bColorLin",
    "mColorLin",
    "vertexColor.rgb",
    "vertexColor.aaa",
    "metalness",
    "roughness",
    "bumpAO",
    "cavity",
    "normalMap",
    "normalRaw",
    "F0",
    "bClum",
    "Ctint",
    "Cspec0",
    "diffuse",
    "specular",
    "roughness",
    "roughA",
    "roughA2",
    "roughnessBiasedA",
    "roughnessBiasedA2",
    "NdotV",
    "ambDomeColor",
    "ambDomeLinColor",
    "diffEnvLin",
    "specEnvLin",
    "cSpecLin",
    "uvRange",
    "selfOccShadow",
    "triplanarWeights",
)
DEBUG_INPUTS_MODES = frozenset({1, 2, 5, 6, 11, 12, 13, 14, 15, 25, 30, 31})


@dataclass
class Material:
    base_color: NDArray
    roughness: NDArray
    metalness: NDArray
    specular: NDArray
    specular_tint: NDArray
    ior: NDArray
    bump_intensity: NDArray
    use_vertex_color: NDArray
    use_vertex_ao: NDArray
    use_vertex_alpha: NDArray
    has_alpha: NDArray
    normal_flip: NDArray
    flip_backface_normals: NDArray
    specular_f0_from_map: NDArray


@dataclass
class Samples:
    base_color: NDArray  # (n, 4)
    roughness: NDArray
    metalness: NDArray
    specular_f0: NDArray
    specular_amount: NDArray
    ao: NDArray
    cavity: NDArray
    emissive: NDArray
    normal_ts: NDArray


@dataclass
class Geometry:
    normal_ws: NDArray
    tangent_ws: NDArray
    binormal_ws: NDArray
    view_ws: NDArray
    position_ws: NDArray
    vertex_color: NDArray  # (n, 4)
    vertex_ao: NDArray
    front_face: NDArray


@dataclass
class Inputs:
    """ShadingInputs, flattened: the surface fields then the forward-only ones."""

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
    model: int = MODEL_LEGACY_V2


@dataclass
class EnvSamples:
    irradiance_over_pi: NDArray
    specular: NDArray
    brdf: NDArray  # (n, 2)
    hemisphere: NDArray
    hemisphere_mode: NDArray


@dataclass
class Terms:
    diffuse: NDArray
    specular: NDArray


def _unit(v: NDArray) -> NDArray:
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def _col(x: NDArray) -> NDArray:
    return np.asarray(x)[..., None]


def alpha_biased(roughness: NDArray) -> NDArray:
    rough_a = roughness * roughness
    return rough_a * (1.0 - ROUGHNESS_BIAS) + ROUGHNESS_BIAS


def roughness_biased(roughness: NDArray) -> NDArray:
    return roughness * (1.0 - ROUGHNESS_BIAS) + ROUGHNESS_BIAS


def luminance(c: NDArray) -> NDArray:
    return 0.3 * c[..., 0] + 0.6 * c[..., 1] + 0.1 * c[..., 2]


def f0_from_ior(ior: NDArray) -> NDArray:
    n_f0 = np.abs((1.0 - ior) / (1.0 + ior))
    return n_f0 * n_f0


def normal_ts(m: Material, s: Samples, front_face: NDArray) -> NDArray:
    raw = s.normal_ts
    z = np.sqrt(1.0 - np.clip((raw[:, :2] * raw[:, :2]).sum(-1), 0.0, 1.0))
    n = np.concatenate([raw[:, :2] * _col(m.bump_intensity), z[:, None]], axis=-1) * m.normal_flip
    flip = (m.flip_backface_normals != 0) & (front_face == 0)
    return np.where(flip[:, None], -n, n)


def _ctint(base_lin: NDArray) -> tuple[NDArray, NDArray]:
    lum = luminance(base_lin)
    safe = np.where(lum > 0.0, lum, 1.0)
    ctint = np.where((lum > 0.0)[:, None], base_lin / safe[:, None], 1.0)
    return lum, ctint


def _f0(m: Material, s: Samples) -> NDArray:
    f0 = np.repeat(f0_from_ior(m.ior)[:, None], 3, axis=-1)
    return np.where((m.specular_f0_from_map != 0)[:, None], s.specular_f0, f0)


def inputs(m: Material, s: Samples, g: Geometry) -> Inputs:
    base_lin = m.base_color * s.base_color[:, :3]
    base_lin = np.where((m.use_vertex_color != 0)[:, None], base_lin * g.vertex_color[:, :3], base_lin)
    roughness = s.roughness * m.roughness
    metalness = s.metalness * m.metalness
    ao = 1.0 + (s.ao - 1.0) * m.bump_intensity
    ao = np.where(m.use_vertex_ao != 0, ao * g.vertex_ao[:, 0], ao)
    opacity = np.where(m.has_alpha != 0, s.base_color[:, 3], 1.0)
    opacity = np.where(m.use_vertex_alpha != 0, opacity * g.vertex_color[:, 3], opacity)
    n_ts = normal_ts(m, s, g.front_face)
    n_ws = _unit(n_ts[:, 0:1] * g.tangent_ws + n_ts[:, 1:2] * g.binormal_ws + n_ts[:, 2:3] * g.normal_ws)
    f0 = _f0(m, s)
    _, ctint = _ctint(base_lin)
    tinted = _col(m.specular) * f0 * (1.0 + (ctint - 1.0) * _col(m.specular_tint))
    cspec0 = tinted + (base_lin - tinted) * _col(metalness)
    return Inputs(
        base_color=base_lin,
        metalness=metalness,
        roughness=roughness,
        ao=ao,
        emissive=s.emissive,
        normal_ws=n_ws,
        view_ws=_unit(g.view_ws),
        position_ws=g.position_ws,
        specular_f0=cspec0,
        cavity=s.cavity,
        opacity=opacity,
        specular_weight=m.specular * s.specular_amount,
    )


def n_dot_v(i: Inputs) -> NDArray:
    return np.abs((i.normal_ws * i.view_ws).sum(-1)) + N_DOT_V_EPSILON


def c_spec(i: Inputs, env: EnvSamples) -> NDArray:
    mixed = i.specular_f0 + (i.base_color - i.specular_f0) * _col(i.metalness)
    return mixed * env.brdf[:, 0:1] + env.brdf[:, 1:2]


def light_terms(i: Inputs, light: NDArray) -> Terms:
    l_ws, att, valid = lighting.incident(light, i.position_ws)
    n, v = i.normal_ws, i.view_ws
    h = _unit(l_ws + v)
    nv = n_dot_v(i)
    nl = np.clip((n * l_ws).sum(-1), 0.0, 1.0)
    lh = np.clip((l_ws * h).sum(-1), 0.0, 1.0)
    nh = np.clip((n * h).sum(-1), 0.0, 1.0)
    alpha = alpha_biased(i.roughness)
    diffuse_term = brdf.burley(np.ones((len(nl), 3)), alpha, nv, nl, lh)[:, 0]
    d = brdf.ggx_d(nh, alpha)
    f = brdf.fresnel_schlick(i.specular_f0[:, 0:1], lh)[:, 0]
    vis = brdf.vis_hable(nl, nv, alpha)
    specular_term = nl * d * f * vis
    rad = lighting.radiance(light, att)
    diffuse = _col(diffuse_term * nl) * rad
    specular = _col(specular_term * nl) * rad
    keep = valid[:, None]
    return Terms(np.where(keep, diffuse, 0.0), np.where(keep, specular, 0.0))


def composite(i: Inputs, env: EnvSamples, t: Terms) -> NDArray:
    base = i.base_color
    m_color = base * _col(1.0 - i.metalness)
    ao = _col(i.ao)
    return t.diffuse * m_color * ao + t.specular * c_spec(i, env) * _col(i.specular_weight) * base * ao * _col(i.cavity)


def env_terms(env: EnvSamples) -> Terms:
    add = (env.hemisphere_mode == 1)[:, None]
    mul = (env.hemisphere_mode == 2)[:, None]
    diffuse = np.where(add, env.irradiance_over_pi + env.hemisphere, env.irradiance_over_pi)
    diffuse = np.where(mul, env.irradiance_over_pi * env.hemisphere, diffuse)
    specular = np.where(add, env.specular + env.hemisphere, env.specular)
    specular = np.where(mul, env.specular * env.hemisphere, specular)
    return Terms(diffuse, specular)


def evaluate_light(i: Inputs, light: NDArray, env: EnvSamples) -> NDArray:
    return composite(i, env, light_terms(i, light))


def evaluate_env(i: Inputs, env: EnvSamples) -> NDArray:
    return composite(i, env, env_terms(env))


def evaluate_slots(i: Inputs, lights: list[NDArray], env: EnvSamples) -> NDArray:
    total = np.zeros_like(i.base_color)
    for light in lights:
        total = total + evaluate_light(i, light, env)
    return total


def shade(i: Inputs, lights: list[NDArray], env: EnvSamples) -> NDArray:
    return evaluate_slots(i, lights, env) + evaluate_env(i, env) + i.emissive


def triplanar_weights(n_ws: NDArray) -> NDArray:
    a = np.abs(_unit(n_ws))
    t = np.clip((a - 0.57357644) / (0.81915204 - 0.57357644), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def debug_inputs(
    m: Material,
    s: Samples,
    g: Geometry,
    uv: NDArray,
    self_shadow: NDArray,
    sky: NDArray,
    ground: NDArray,
    up_ws: NDArray,
    mode: int,
) -> NDArray:
    n = len(m.ior)
    base_lin = m.base_color * s.base_color[:, :3]
    base_lin = np.where((m.use_vertex_color != 0)[:, None], base_lin * g.vertex_color[:, :3], base_lin)
    lum, ctint = _ctint(base_lin)
    f0 = _f0(m, s)
    grey = lambda x: np.repeat(np.asarray(x)[:, None], 3, axis=-1)
    if mode == 1:
        return s.base_color[:, :3]
    if mode == 2:
        return grey(s.base_color[:, 3])
    if mode == 5:
        return g.vertex_color[:, :3]
    if mode == 6:
        return grey(g.vertex_color[:, 3])
    if mode == 11:
        return s.normal_ts * 0.5 + 0.5
    if mode == 12:
        return s.normal_ts
    if mode == 13:
        return grey(f0[:, 0])
    if mode == 14:
        return grey(lum)
    if mode == 15:
        return ctint
    if mode == 25:
        t = np.clip((_unit(g.normal_ws) * up_ws).sum(-1) * 0.5 + 0.5, 0.0, 1.0)
        return ground + (sky - ground) * t[:, None]
    if mode == 30:
        c = np.zeros((n, 3))
        c[uv[:, 0] < 0.0] = (0.0, 1.0, 0.0)
        c[uv[:, 1] < 0.0] = (0.0, 0.0, 1.0)
        c[uv[:, 0] > 1.0] = (1.0, 0.0, 0.0)
        c[uv[:, 1] > 1.0] = (1.0, 0.0, 1.0)
        return c
    if mode == 31:
        return grey(self_shadow)
    return np.zeros((n, 3))


def debug(i: Inputs, lights: list[NDArray], env: EnvSamples, mode: int) -> NDArray:
    n = len(i.roughness)
    grey = lambda x: np.repeat(np.asarray(x)[:, None], 3, axis=-1)
    base = i.base_color
    rough_a = i.roughness * i.roughness
    alpha = alpha_biased(i.roughness)
    lum = luminance(base)
    if mode == 0:
        return shade(i, lights, env)
    if mode in (1, 3):
        return base
    if mode in (2, 6):
        return grey(i.opacity)
    if mode == 4:
        return base * _col(1.0 - i.metalness)
    if mode == 5:
        return np.ones((n, 3))
    if mode == 7:
        return grey(i.metalness)
    if mode in (8, 19):
        return grey(i.roughness)
    if mode == 9:
        return grey(i.ao)
    if mode == 10:
        return grey(i.cavity)
    if mode in (11, 12):
        return i.normal_ws * 0.5 + 0.5
    if mode == 13:
        return grey(i.specular_f0[:, 0])
    if mode == 14:
        return grey(lum)
    if mode == 15:
        safe = np.where(lum > 0.0, lum, 1.0)
        return np.where((lum > 0.0)[:, None], base / safe[:, None], 1.0)
    if mode == 16:
        return i.specular_f0
    if mode in (17, 18):
        direct = Terms(np.zeros((n, 3)), np.zeros((n, 3)))
        for light in lights:
            t = light_terms(i, light)
            direct = Terms(direct.diffuse + t.diffuse, direct.specular + t.specular)
        e = env_terms(env)
        if mode == 17:
            return direct.diffuse + e.diffuse
        return (direct.specular + e.specular) * c_spec(i, env) * _col(i.specular_weight)
    if mode == 20:
        return grey(rough_a)
    if mode == 21:
        return grey(rough_a * rough_a)
    if mode == 22:
        return grey(alpha)
    if mode == 23:
        return grey(alpha * alpha)
    if mode == 24:
        return grey(n_dot_v(i))
    if mode in (25, 26):
        return env.hemisphere
    if mode == 27:
        return env_terms(env).diffuse
    if mode == 28:
        return env_terms(env).specular
    if mode == 29:
        return c_spec(i, env)
    if mode == 30:
        return np.zeros((n, 3))
    if mode == 31:
        return np.ones((n, 3))
    if mode == 32:
        return triplanar_weights(i.normal_ws)
    return np.zeros((n, 3))


if __name__ == "__main__":
    print(len(DEBUG_MODE_NAMES), "debug modes; F0 at IOR 1.5:", f0_from_ior(np.array([1.5])))
