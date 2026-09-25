"""
HogShade: a GPU device for the core tests, or a skip that says why.
Package: tests/core/conftest
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def gpu():
    try:
        import wgpu
    except ImportError:
        pytest.skip("wgpu not installed (uv sync --extra gpu)")
    try:
        adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
        device = adapter.request_device_sync()
    except Exception as e:  # noqa: BLE001 - any adapter failure is a skip, not an error
        pytest.skip(f"no GPU adapter: {e!r}")
    from gpu_harness import GpuRunner

    return GpuRunner(device)
