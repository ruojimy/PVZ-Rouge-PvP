"""Collect the original unittest identities without running test methods.

Import-time code uses isolated userdata; the reference source is read-only.
"""
import argparse
import inspect
import json
import os
from pathlib import Path
import sys
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT.parent / "PVZ-Rouge-v1.4.8" / "next-pvp71"


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--modules", required=True, type=Path)
    args = ap.parse_args()
    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
        APPDATA=str(out.parent / "reference-userdata"),
        PVP_USERDATA=str(out.parent / "reference-userdata" / "pvp_userdata"))
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(REFERENCE / "tests"), str(REFERENCE / "modkit")]
    records = {}
    for module in args.modules.read_text(encoding="utf-8-sig").splitlines():
        module = module.strip()
        if not module or module.startswith("#"):
            continue
        started = time.time()
        try:
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(module)
            tests = list(flatten(suite))
            bindings = []
            imported = sys.modules.get(module)
            if imported is not None:
                for name, cls in sorted(vars(imported).items()):
                    if inspect.isclass(cls) and issubclass(cls, unittest.TestCase):
                        names = loader.getTestCaseNames(cls)
                        if names:
                            bindings.append(dict(binding=name, module=cls.__module__,
                                                 cls=cls.__name__, tests=names))
            records[module] = dict(ids=[t.id() for t in tests],
                                   bindings=bindings,
                                   loader_errors=loader.errors,
                                   seconds=round(time.time() - started, 3))
        except Exception:
            records[module] = dict(ids=[], loader_errors=[traceback.format_exc()],
                                   seconds=round(time.time() - started, 3))
        out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(module, len(records[module]["ids"]),
              "errors", len(records[module]["loader_errors"]), flush=True)
    return int(any(r["loader_errors"] for r in records.values()))


if __name__ == "__main__":
    raise SystemExit(main())
