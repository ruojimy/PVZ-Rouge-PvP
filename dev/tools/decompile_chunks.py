"""Decompile original combat regions in safe chunks.

A cut point is an instruction offset where (a) no jump crosses it and (b) the
linear stack depth is zero.  Chunks of <= MAX bytes are decompiled in worker
processes; a failed chunk is split again at the midpoint cut point, and a
chunk that still fails is emitted as an annotated disassembly block.

Usage: python tools/decompile_chunks.py [region ...]
Output: extract/regions/<region>.py
"""
import dis, marshal, sys, io, os
from pathlib import Path
from multiprocessing import Pool

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "pylib"))
sys.path.insert(0, str(HERE))
from slice_regions import REGIONS, rebase, ROOT

OUT = HERE.parent / "extract" / "regions"
MAX = 1600
EXT = dis.opmap["EXTENDED_ARG"]

_root = None


def root():
    global _root
    if _root is None:
        _root = marshal.loads((ROOT / "reverse_engineered/raw/pvzrouge.pyc").read_bytes())
    return _root


def cut_points(code, s, e):
    ins = [i for i in dis.get_instructions(code) if s <= i.offset < e]
    jumps = []
    for i in ins:
        if i.opcode in dis.hasjabs or i.opcode in dis.hasjrel:
            a, b = sorted((i.offset, i.argval))
            jumps.append((a, b))
    # SETUP_FINALLY / FOR_ITER etc are in hasjrel already
    depth = 0
    ok = []
    prev_ext = False
    for idx, i in enumerate(ins):
        if depth == 0 and not prev_ext:
            ok.append(i.offset)
        prev_ext = i.opcode == EXT
        if i.opcode == EXT:
            continue
        try:
            eff = dis.stack_effect(i.opcode, i.arg if i.opcode >= dis.HAVE_ARGUMENT else None, jump=False)
        except ValueError:
            eff = 0
        depth += eff
        if i.opname in ("JUMP_ABSOLUTE", "JUMP_FORWARD", "RETURN_VALUE", "RAISE_VARARGS"):
            pass
    ok.append(e)
    # remove cut points crossed by any jump (strictly inside)
    import bisect
    crossed = set()
    okset = sorted(set(ok))
    for a, b in jumps:
        lo = bisect.bisect_right(okset, a)
        hi = bisect.bisect_left(okset, b + 1)
        # cut c is crossed if a < c <= b  (a jump to exactly c from before is fine only if c==b? no: target==c means jump enters chunk boundary from before -> crossing)
        for c in okset[lo:hi]:
            if a < c <= b and not (c == b and False):
                crossed.add(c)
    res = [c for c in okset if c not in crossed or c in (s, e)]
    return res


def try_decompile(args):
    s, e = args
    sys.setrecursionlimit(20000)
    from decompyle3.main import decompile
    try:
        c = rebase(root(), s, e)
    except Exception as ex:
        return s, e, None, "rebase: %r" % ex
    buf = io.StringIO()
    try:
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            decompile(c, (3, 8, 10), buf, showgrammar=False)
        text = buf.getvalue()
        lines = [l for l in text.splitlines() if not l.startswith("# ")]
        # strip trailing implicit "return" artefacts
        while lines and lines[-1].strip() in ("", "return", "return None"):
            lines.pop()
        return s, e, "\n".join(lines), None
    except BaseException as ex:
        return s, e, None, "%s: %s" % (type(ex).__name__, str(ex)[:120])


def disasm(s, e):
    out = []
    for i in dis.get_instructions(root()):
        if s <= i.offset < e:
            out.append("#DIS %6d %-22s %s" % (i.offset, i.opname, i.argrepr))
    return "\n".join(out)


def plan(cuts, s, e):
    chunks = []
    cur = s
    last_ok = s
    for c in cuts:
        if c <= cur:
            continue
        if c - cur > MAX and last_ok > cur:
            chunks.append((cur, last_ok))
            cur = last_ok
        last_ok = c
    if cur < e:
        chunks.append((cur, e))
    return chunks


def run_region(pool, name, s, e):
    code = root()
    cuts = cut_points(code, s, e)
    pending = plan(cuts, s, e)
    done = {}
    rounds = 0
    while pending:
        rounds += 1
        results = pool.map(try_decompile, pending, chunksize=1)
        pending = []
        for cs, ce, text, err in results:
            if text is not None:
                done[cs] = (ce, text, None)
                continue
            inner = [c for c in cuts if cs < c < ce]
            if inner and ce - cs > 40:
                mid = min(inner, key=lambda c: abs(c - (cs + ce) // 2))
                pending += [(cs, mid), (mid, ce)]
            else:
                done[cs] = (ce, None, err)
    parts = []
    nfail = 0
    for cs in sorted(done):
        ce, text, err = done[cs]
        parts.append("# ---- @%d..%d" % (cs, ce))
        if text is None:
            nfail += 1
            parts.append("# DECOMPILE FAILED: %s" % err)
            parts.append(disasm(cs, ce))
        else:
            parts.append(text)
    (OUT / (name + ".py")).write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("%-20s chunks=%d failed=%d rounds=%d" % (name, len(done), nfail, rounds), flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or list(REGIONS)
    with Pool(16) as pool:
        for n in names:
            s, e = REGIONS[n]
            run_region(pool, n, s, e)


if __name__ == "__main__":
    main()
