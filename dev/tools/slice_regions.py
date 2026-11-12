"""Cut the original pvzrouge.pyc main module into standalone region code objects
and try to decompile each with decompyle3.  Output: extract/regions/<name>.py
(or .dis.txt when decompilation fails).

Usage: python38-embed/python.exe tools/slice_regions.py [start end name ...]
"""
import dis, marshal, sys, types, io, os, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "pylib"))
ROOT = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
OUT = HERE.parent / "extract" / "regions"
OUT.mkdir(parents=True, exist_ok=True)

REGIONS = {
    "definitions": (64, 29952),
    "unit_tables": (30678, 32104),
    "zombies": (68412, 97986),
    "plant_draw": (97986, 98256),
    "unit_target_index": (98256, 98618),
    "entities": (98618, 108808),
    "particles": (108808, 109352),
    "plant_maintenance": (113444, 119530),
    "plants": (121092, 144612),
    "placement": (109352, 110754),
    "coffee": (159944, 160138),
    "shovel": (159198, 159300),
    "sun_motion": (145426, 145550),
    "water_animation": (59028, 59116),
    "important_blocks": (64692, 65216),
    "cannon_select": (158214, 158400),
    "cannon_fire": (160744, 160856),
}

EXT = dis.opmap["EXTENDED_ARG"]


def rebase(code, start, end):
    raw = bytearray(code.co_code[start:end])
    # rewrite absolute jumps, keeping instruction sizes
    i = 0
    prefix_start = None
    while i < len(raw):
        op, arg = raw[i], raw[i + 1]
        if op == EXT:
            if prefix_start is None:
                prefix_start = i
            i += 2
            continue
        if op in dis.hasjabs:
            ps = prefix_start if prefix_start is not None else i
            n = (i - ps) // 2  # number of EXTENDED_ARG
            full = 0
            for k in range(n):
                full = (full << 8) | raw[ps + 2 * k + 1]
            full = (full << 8) | arg
            new = full - start
            if new < 0 or new > end - start:
                raise ValueError("abs jump escapes %d->%d" % (start + i, full))
            for k in range(n, -1, -1):
                pos = ps + 2 * k + 1 if k < n else i + 1
                # fill from lowest byte at i+1 backwards
            b = new
            raw[i + 1] = b & 0xFF; b >>= 8
            for k in range(n - 1, -1, -1):
                raw[ps + 2 * k + 1] = b & 0xFF; b >>= 8
            if b:
                raise ValueError("jump does not fit")
        prefix_start = None
        i += 2
    consts = list(code.co_consts)
    if None not in consts:
        consts.append(None)
    none = consts.index(None)
    raw += bytes([dis.opmap["LOAD_CONST"], none, dis.opmap["RETURN_VALUE"], 0])
    return code.replace(co_code=bytes(raw), co_consts=tuple(consts), co_lnotab=b"",
                        co_firstlineno=1, co_name="<region>")


def main(argv):
    root = marshal.loads((ROOT / "reverse_engineered/raw/pvzrouge.pyc").read_bytes())
    regions = REGIONS
    if argv:
        regions = {argv[i + 2]: (int(argv[i]), int(argv[i + 1])) for i in range(0, len(argv), 3)}
    from decompyle3.main import decompile
    for name, (s, e) in regions.items():
        try:
            c = rebase(root, s, e)
        except Exception as ex:
            print(name, "REBASE FAIL", ex)
            continue
        with open(OUT / (name + ".dis.txt"), "w", encoding="utf-8") as f:
            for ins in dis.get_instructions(c):
                f.write("%6d %-22s %s\n" % (ins.offset + s, ins.opname, ins.argrepr))
        buf = io.StringIO()
        try:
            decompile(c, (3, 8, 10), buf, showgrammar=False)
            (OUT / (name + ".py")).write_text(buf.getvalue(), encoding="utf-8")
            print(name, "OK", len(buf.getvalue().splitlines()), "lines")
        except Exception as ex:
            (OUT / (name + ".py")).write_text(buf.getvalue() + "\n# FAILED: %r\n" % ex, encoding="utf-8")
            print(name, "FAIL", type(ex).__name__, str(ex)[:200])


if __name__ == "__main__":
    main(sys.argv[1:])
