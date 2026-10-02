"""
HogShade: NumPy mirror of the texture-free functions in core/environment.wgsl, row by row.
Package: hogshade/reference/environment

The sampling functions (specular cube, irradiance cube, the LUT) read textures and are exercised by the
hosts; these three are pure maths and the GPU harness compares them (tests/core/test_environment_gpu.py).
"""

from __future__ import annotations

import logging as _logging

import numpy as np
from numpy.typing import NDArray

from hogshade.core_constants import SH_A0, SH_A1, SH_A2

_MODULE_NAME = "hogshade.reference.environment"
__version__ = "0.1.0"
__updated__ = "2026-09-27"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: The real SH basis constants environment_irradiance_sh9 uses, in the order of the nine coefficients.
_Y = (0.282095, 0.488603, 0.488603, 0.488603, 1.092548, 1.092548, 0.315392, 1.092548, 0.546274)


def irradiance_sh9(sh9: NDArray, n_ws: NDArray, exposure: NDArray) -> NDArray:
    """
    E(n) / pi from radiance coefficients, as environment_irradiance_sh9: (n, 9, 3) coefficients, (n, 3)
    normals, (n,) exposure -> (n, 3). Band weights A0, A1, A2; clamped at zero; scaled by exposure.
    """
    x, y, z = n_ws[:, 0], n_ws[:, 1], n_ws[:, 2]
    basis = np.stack(
        [
            np.full_like(x, _Y[0]),
            _Y[1] * y,
            _Y[2] * z,
            _Y[3] * x,
            _Y[4] * x * y,
            _Y[5] * y * z,
            _Y[6] * (3.0 * z * z - 1.0),
            _Y[7] * x * z,
            _Y[8] * (x * x - y * y),
        ],
        axis=-1,
    )
    weights = np.array([SH_A0] + [SH_A1] * 3 + [SH_A2] * 5)
    e = np.einsum("nk,nkc->nc", basis * weights, sh9) / np.pi
    return np.maximum(e, 0.0) * exposure[:, None]


def hemisphere(sky: NDArray, ground: NDArray, n_ws: NDArray, up_ws: NDArray) -> NDArray:
    """The v2 ambient dome: ground below, sky above, blended on dot(n, up); as the shader, neither is normalised."""
    t = np.clip((n_ws * up_ws).sum(-1) * 0.5 + 0.5, 0.0, 1.0)[:, None]
    return ground + (sky - ground) * t


def samples_none() -> dict[str, NDArray]:
    """environment_samples_none: black, and the neutral LUT (scale 1, bias 0)."""
    return {
        "irradiance_over_pi": np.zeros(3),
        "specular": np.zeros(3),
        "brdf": np.array([1.0, 0.0]),
        "hemisphere": np.zeros(3),
        "hemisphere_mode": np.array(0),
    }


if __name__ == "__main__":
    coeffs = np.zeros((1, 9, 3))
    coeffs[0, 0] = 1.0  # a constant radiance of 1 / (A0 * Y00) reconstructs to E/pi = 1 * A0 * Y00 / pi
    print("dc-only irradiance/pi:", irradiance_sh9(coeffs, np.array([[0.0, 1.0, 0.0]]), np.ones(1)))
    print(
        "dome at the horizon:",
        hemisphere(np.ones((1, 3)), np.zeros((1, 3)), np.array([[1.0, 0, 0]]), np.array([[0, 1.0, 0]])),
    )
