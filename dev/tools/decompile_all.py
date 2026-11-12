"""Decompile all original combat regions and functions with pydec38.

Outputs extract/original/regions/<name>.py and extract/original/functions.py,
plus a summary of gotos / unsupported ops.
"""
import marshal, sys, types, re
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from slice_regions import REGIONS, ROOT
from pydec38 import Decompiler

OUT = HERE.parent / "extract" / "original"
(OUT / "regions").mkdir(parents=True, exist_ok=True)
sys.setrecursionlimit(100000)


def main():
    root = marshal.loads((ROOT / "reverse_engineered/raw/pvzrouge.pyc").read_bytes())
    summary = []
    extra = {}
    if len(sys.argv) > 1 and sys.argv[1] == "--whole":
        extra = {"whole_module": (0, len(root.co_code))}
    for name, (s, e) in list(REGIONS.items()) + list(extra.items()):
        d = Decompiler(root, s, e)
        try:
            lines = d.decompile_lines()
        except Exception as ex:
            import traceback
            lines = ["# DECOMPILER CRASH: %r" % ex] + ["# " + l for l in traceback.format_exc().splitlines()]
        text = "\n".join(lines)
        (OUT / "regions" / (name + ".py")).write_text(
            "# original pvzrouge.pyc bytes %d..%d\n" % (s, e) + text + "\n", encoding="utf-8")
        gotos = text.count("# goto")
        unk = text.count("# ??")
        summary.append("%-22s lines=%6d gotos=%3d unknown=%3d problems=%d" % (name, len(lines), gotos, unk, len(d.problems)))
    funcs = []
    for c in root.co_consts:
        if isinstance(c, types.CodeType):
            d = Decompiler(c)
            try:
                body = d.decompile_lines()
            except Exception as ex:
                body = ["# DECOMPILER CRASH: %r" % ex]
            args = list(c.co_varnames[:c.co_argcount])
            funcs.append("def %s(%s):\n%s\n" % (c.co_name, ", ".join(args),
                                                 "\n".join("    " + l for l in body) or "    pass"))
            t = "\n".join(body)
            if "# goto" in t or "# ??" in t or d.problems:
                summary.append("func %-18s gotos=%d unknown=%d problems=%s" % (c.co_name, t.count("# goto"), t.count("# ??"), d.problems[:3]))
    (OUT / "functions.py").write_text("\n".join(funcs), encoding="utf-8")
    (OUT / "SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
