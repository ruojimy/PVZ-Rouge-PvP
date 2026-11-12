"""Same benchmark protocol, with every child pinned to one verified CPU core."""
import argparse
import ctypes
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark_release as base

if '--baseline-manifest' in sys.argv:
    from benchmark_pvp72 import main as compare_manifests
    compare_manifests()
    raise SystemExit(0)

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
parser.add_argument("--repeats", type=int, default=3)
parser.add_argument("--cpu", type=int, default=12)
args = parser.parse_args()
mask = 1 << args.cpu
original_popen = base.subprocess.Popen
original_save = base.save


def pinned_popen(*a, **kw):
    child = original_popen(*a, **kw)
    handle = ctypes.c_void_p(int(child._handle))
    if not ctypes.windll.kernel32.SetProcessAffinityMask(handle, ctypes.c_size_t(mask)):
        child.kill()
        raise ctypes.WinError()
    actual, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not ctypes.windll.kernel32.GetProcessAffinityMask(handle, ctypes.byref(actual), ctypes.byref(system)) or actual.value != mask:
        child.kill()
        raise RuntimeError("CPU affinity was not applied")
    return child


def save_with_affinity(path, value):
    if Path(path).name == "metadata.json":
        value["cpu_affinity"] = {"logical_cpu": args.cpu, "mask": mask, "verified_for_each_child": True,
                                 "efficiency_class_at_discovery": 1,
                                 "reason": "Windows reports hybrid cores; unrestricted runs showed substantial scheduling variance"}
        value["controlled_wrapper_sha256"] = base.sha(__file__)
    original_save(path, value)


base.subprocess.Popen = pinned_popen
base.save = save_with_affinity
base.main(args)
