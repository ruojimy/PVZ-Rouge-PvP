"""Check decompiled text against the original bytecode.

Recompiles the decompiled text inside a function and compares the multiset of
(normalized opcode, argument) pairs of all non-control instructions.  A missing
or duplicated statement shows up as a difference.
"""
import dis, marshal, sys, types, collections, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from slice_regions import REGIONS, ROOT
from pydec38 import Decompiler

SKIP = {"EXTENDED_ARG", "NOP", "POP_JUMP_IF_FALSE", "POP_JUMP_IF_TRUE", "JUMP_ABSOLUTE",
        "JUMP_FORWARD", "RETURN_VALUE", "POP_TOP", "UNARY_NOT", "GET_ITER", "FOR_ITER",
        "POP_BLOCK", "SETUP_LOOP", "BREAK_LOOP", "CONTINUE_LOOP", "JUMP_IF_FALSE_OR_POP", "JUMP_IF_TRUE_OR_POP"}
NORM = {"LOAD_NAME": "LOAD", "LOAD_GLOBAL": "LOAD", "LOAD_FAST": "LOAD", "LOAD_DEREF": "LOAD",
        "STORE_NAME": "STORE", "STORE_GLOBAL": "STORE", "STORE_FAST": "STORE", "STORE_DEREF": "STORE",
        "LOAD_METHOD": "LOAD_ATTR", "CALL_METHOD": "CALL_FUNCTION"}


def norm_ops(code, s=0, e=None, deep=True):
    c = collections.Counter()
    for i in dis.get_instructions(code):
        if i.offset < s or (e is not None and i.offset >= e):
            continue
        if i.opname in SKIP:
            continue
        if i.opname == "COMPARE_OP" and i.argrepr in ("not in", "is not", "in", "is"):
            c[("COMPARE_OP", i.argrepr.split()[-1])] += 1   # negation folded
            continue
        if i.opname == "COMPARE_OP" and i.argrepr in ("!=", ">=", "<=", "==", "<", ">"):
            c[("COMPARE_OP", "cmp")] += 1
            continue
        a = i.argval
        if isinstance(a, types.CodeType):
            a = "code:" + a.co_name
        if i.opname == "LOAD_CONST" and a is None:
            continue
        c[(NORM.get(i.opname, i.opname), repr(a))] += 1
    return c


def check_text(text, original_counter, is_func=False):
    body = text.replace("return  # region end", "return")
    src = "def __r():\n" + "\n".join("    " + l for l in body.splitlines()) + "\n"
    try:
        top = compile(src, "<dec>", "exec")
    except SyntaxError as ex:
        return "SYNTAX %s line %s: %r" % (ex.msg, ex.lineno, (ex.text or "").strip()[:100])
    fn = [k for k in top.co_consts if isinstance(k, types.CodeType)][0]
    got = norm_ops(fn)
    # nested defs: compare their code by name only
    diff_missing = original_counter - got
    diff_extra = got - original_counter
    if not diff_missing and not diff_extra:
        return None
    return "missing=%s extra=%s" % (dict(list(diff_missing.items())[:8]), dict(list(diff_extra.items())[:8]))


def main():
    root = marshal.loads((ROOT / "reverse_engineered/raw/pvzrouge.pyc").read_bytes())
    sys.stdout.reconfigure(encoding="utf-8")
    names = sys.argv[1:] or list(REGIONS)
    for name in names:
        if name == "functions":
            for c in root.co_consts:
                if isinstance(c, types.CodeType):
                    try:
                        d = Decompiler(c)
                        t = "\n".join(d.decompile_lines())
                        r = check_text(t, norm_ops(c))
                    except Exception as ex:
                        r = "CRASH %r" % ex
                    print("func %-16s %s" % (c.co_name, r or "OK"), flush=True)
            continue
        s, e = REGIONS[name]
        d = Decompiler(root, s, e)
        try:
            t = "\n".join(d.decompile_lines())
        except Exception as ex:
            print("%-20s CRASH %r" % (name, ex)); continue
        print("%-20s %s" % (name, check_text(t, norm_ops(root, s, e)) or "OK"), flush=True)


if __name__ == "__main__":
    main()
