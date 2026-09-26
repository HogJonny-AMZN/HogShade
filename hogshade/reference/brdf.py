"""
HogShade: NumPy mirror of core/brdf.wgsl, function by function, same names minus the prefix.
Package: hogshade/reference/brdf
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from hogshade.core_constants import INV_PI, PI, ROUGHNESS_BIAS

_MODULE_NAME = "hogshade.reference.brdf"
__version__ = "0.1.0"
__updated__ = "2026-09-21"


def ggx_d(n_dot_h: NDArray, alpha: NDArray) -> NDArray:
    a2 = alpha * alpha
    d = n_dot_h * n_dot_h * (a2 - 1.0) + 1.0
    return a2 / (PI * d * d)


def smith_v_height_correlated(n_dot_v: NDArray, n_dot_l: NDArray, alpha: NDArray) -> NDArray:
    a2 = alpha * alpha
    gv = n_dot_l * np.sqrt(n_dot_v * n_dot_v * (1.0 - a2) + a2)
    gl = n_dot_v * np.sqrt(n_dot_l * n_dot_l * (1.0 - a2) + a2)
    return 0.5 / np.maximum(gv + gl, 1e-5)


def fresnel_schlick(f0: NDArray, v_dot_h: NDArray) -> NDArray:
    fc = (1.0 - v_dot_h) ** 5
    return f0 + (1.0 - f0) * fc[..., None]


def fresnel_f82(f0: NDArray, tint: NDArray, v_dot_h: NDArray) -> NDArray:
    mu = np.clip(v_dot_h, 0.0, 1.0)[..., None]
    mu_bar = 1.0 / 7.0
    denom = mu_bar * (1.0 - mu_bar) ** 6
    f_schlick_bar = f0 + (1.0 - f0) * (1.0 - mu_bar) ** 5
    a = (f_schlick_bar - f_schlick_bar * tint) / max(denom, 1e-6)
    f_schlick = f0 + (1.0 - f0) * (1.0 - mu) ** 5
    return np.maximum(f_schlick - a * mu * (1.0 - mu) ** 6, 0.0)


def g1_schlick_ggx(n_dot_x: NDArray, k: NDArray) -> NDArray:
    return 1.0 / np.maximum(n_dot_x * (1.0 - k) + k, 1e-5)


def vis_hable(n_dot_l: NDArray, n_dot_v: NDArray, alpha: NDArray) -> NDArray:
    k = alpha * 0.5
    return g1_schlick_ggx(n_dot_l, k) * g1_schlick_ggx(n_dot_v, k)


def lambert(albedo: NDArray) -> NDArray:
    return albedo * INV_PI


def burley(albedo: NDArray, roughness: NDArray, n_dot_v: NDArray, n_dot_l: NDArray, v_dot_h: NDArray) -> NDArray:
    fd90 = 0.5 + 2.0 * roughness * v_dot_h * v_dot_h
    light_scatter = 1.0 + (fd90 - 1.0) * (1.0 - n_dot_l) ** 5
    view_scatter = 1.0 + (fd90 - 1.0) * (1.0 - n_dot_v) ** 5
    return albedo * INV_PI * (light_scatter * view_scatter)[..., None]


def specular_ggx(n: NDArray, v: NDArray, l: NDArray, f0: NDArray, roughness: NDArray) -> NDArray:
    h = v + l
    h = h / np.linalg.norm(h, axis=-1, keepdims=True)
    n_dot_l = np.maximum((n * l).sum(-1), 0.0)
    n_dot_v = np.maximum((n * v).sum(-1), 1e-4)
    n_dot_h = np.maximum((n * h).sum(-1), 0.0)
    v_dot_h = np.maximum((v * h).sum(-1), 0.0)
    alpha = np.maximum((roughness + ROUGHNESS_BIAS) ** 2, 1e-4)
    d = ggx_d(n_dot_h, alpha)
    vis = smith_v_height_correlated(n_dot_v, n_dot_l, alpha)
    f = fresnel_schlick(f0, v_dot_h)
    return (d * vis * n_dot_l)[..., None] * f


if __name__ == "__main__":
    print("ggx_d at n.h=1, alpha=0.5:", ggx_d(np.array(1.0), np.array(0.5)))
    print("schlick at grazing:", fresnel_schlick(np.array([[0.04, 0.04, 0.04]]), np.array([0.0])))
