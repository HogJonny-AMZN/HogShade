"""
HogShade: run a core function on the GPU over arrays of test vectors, through a wgpu-py compute shader.
Package: tests/core/gpu_harness

A test writes a small compute kernel that reads its inputs from one float storage buffer with a
fixed stride per item, calls the core function, and writes results to an output buffer with its
own stride. The harness stitches the core in front of the kernel (no validation entry point),
compiles it on the adapter the conftest chose, dispatches one thread per item, and returns the
output as a NumPy array. Everything is float32; tolerances in the tests account for that.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import build_shaders as bs

KERNEL_PRELUDE = """
@group(0) @binding(0) var<storage, read> hs_in: array<f32>;
@group(0) @binding(1) var<storage, read_write> hs_out: array<f32>;
"""


def core_source() -> str:
    """The stitched core, exactly what hosts/wgpu/generated/hogshade_core.wgsl holds."""
    return bs.stitch(bs.load_manifest(), with_validate=False)


class GpuRunner:
    def __init__(self, device) -> None:
        self.device = device
        self._core = core_source()

    def run(self, kernel: str, inputs: np.ndarray, out_stride: int, count: int) -> np.ndarray:
        """Compile core + prelude + kernel (entry point ``main``), run ``count`` threads, return (count, out_stride)."""
        import wgpu

        source = self._core + KERNEL_PRELUDE + kernel
        module = self.device.create_shader_module(code=source)
        data = np.ascontiguousarray(inputs, dtype=np.float32).reshape(-1)
        buf_in = self.device.create_buffer_with_data(data=data.tobytes(), usage=wgpu.BufferUsage.STORAGE)
        out_bytes = max(count * out_stride, 1) * 4
        buf_out = self.device.create_buffer(size=out_bytes, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC)
        pipeline = self.device.create_compute_pipeline(layout="auto", compute={"module": module, "entry_point": "main"})
        bind_group = self.device.create_bind_group(
            layout=pipeline.get_bind_group_layout(0),
            entries=[
                {"binding": 0, "resource": {"buffer": buf_in, "offset": 0, "size": buf_in.size}},
                {"binding": 1, "resource": {"buffer": buf_out, "offset": 0, "size": buf_out.size}},
            ],
        )
        encoder = self.device.create_command_encoder()
        cpass = encoder.begin_compute_pass()
        cpass.set_pipeline(pipeline)
        cpass.set_bind_group(0, bind_group)
        cpass.dispatch_workgroups(math.ceil(count / 64))
        cpass.end()
        self.device.queue.submit([encoder.finish()])
        result = np.frombuffer(self.device.queue.read_buffer(buf_out), dtype=np.float32)
        return result[: count * out_stride].reshape(count, out_stride).copy()


def kernel(body: str, in_stride: int, count_name: str = "hs_count") -> str:
    """Wrap a per-item body into a compute entry point. ``i`` is the item index, ``base`` its input offset."""
    return f"""
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {{
    let i = gid.x;
    if (i >= u32(arrayLength(&hs_in) / {in_stride}u)) {{ return; }}
    let base = i * {in_stride}u;
{body}
}}
"""


def unit_vectors(n: int, seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=(n, 3))
    return v / np.linalg.norm(v, axis=-1, keepdims=True)
