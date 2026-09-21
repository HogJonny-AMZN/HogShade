"""
HogShade: NumPy references for core WGSL functions. Small, readable, and the thing the GPU harness compares against.
Package: hogshade/reference

Each module mirrors one core module function by function, in the same order, with the same names
minus the module prefix. The references are the specification of the maths; the WGSL is the
implementation every host runs. A test that runs the WGSL on the GPU against these is phase 2 PR C.
"""
