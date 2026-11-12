"""Scoped Windows V-runtime math adapter for source-oracle comparisons.

The V runtime and generated PvP64 source call std::hypot, backed by the
Windows UCRT. CPython 3.8 math.hypot uses compensated accumulation instead.
This adapter is installed only into the extracted PvP64 oracle namespace;
it never changes Python's math module or the unmodified secondary oracle.
Its ABI/result equivalence is checked by native_math72_probe before use.
"""
import ctypes
import math
import os


class NativeMath:
    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('This adapter represents the verified Windows V runtime only')
        self._runtime = ctypes.CDLL('ucrtbase.dll')
        self._hypot = self._runtime._hypot
        self._hypot.argtypes = (ctypes.c_double, ctypes.c_double)
        self._hypot.restype = ctypes.c_double

    def hypot(self, x, y):
        return self._hypot(float(x), float(y))

    def __getattr__(self, name):
        return getattr(math, name)
