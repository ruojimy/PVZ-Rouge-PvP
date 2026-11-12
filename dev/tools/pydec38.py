"""A small structuring decompiler for the original PVZ-Rouge Python 3.8 bytecode.

Targets the shapes produced by CPython 3.8's compiler for this game: if/elif/
else chains, for/while loops with break/continue, short-circuit conditions,
augmented subscript assignment, nested function definitions and simple list
comprehensions.  EXTENDED_ARG padding (inserted by the 1.5.0.1 patcher) is
ignored.  Output is readable Python intended as the reference for the C++ port;
anything unexpected is emitted verbatim as a `# ??` comment, never dropped.
"""
import dis, types, sys

BINOPS = {
    "BINARY_ADD": "+", "BINARY_SUBTRACT": "-", "BINARY_MULTIPLY": "*",
    "BINARY_TRUE_DIVIDE": "/", "BINARY_FLOOR_DIVIDE": "//", "BINARY_MODULO": "%",
    "BINARY_POWER": "**", "BINARY_AND": "&", "BINARY_OR": "|", "BINARY_XOR": "^",
    "BINARY_LSHIFT": "<<", "BINARY_RSHIFT": ">>", "BINARY_MATRIX_MULTIPLY": "@",
}
INPLACE = {k.replace("BINARY_", "INPLACE_"): v for k, v in BINOPS.items()}
JUMPS = set(dis.hasjabs) | set(dis.hasjrel)
TERMINAL = {"JUMP_ABSOLUTE", "JUMP_FORWARD", "RETURN_VALUE", "RAISE_VARARGS"}


class E:
    """Expression node: text + precedence (higher binds tighter)."""
    __slots__ = ("s", "p", "inplace")

    def __init__(self, s, p=100, inplace=None):
        self.s, self.p, self.inplace = s, p, inplace

    def __repr__(self):
        return self.s


PREC = {"or": 1, "and": 2, "not": 3, "cmp": 4, "|": 5, "^": 6, "&": 7, "<<": 8, ">>": 8,
        "+": 9, "-": 9, "*": 10, "/": 10, "//": 10, "%": 10, "@": 10, "u": 11, "**": 12}


def par(e, p):
    return "(" + e.s + ")" if e.p < p else e.s


def binop(a, op, b):
    p = PREC[op]
    if op == "**":
        return E(par(a, p + 1) + " ** " + par(b, p), p)
    return E(par(a, p) + " " + op + " " + par(b, p + 1), p)


def cmpop(a, op, b):
    return E(par(a, 5) + " " + op + " " + par(b, 5), PREC["cmp"])


def neg(e):
    if e.s.startswith("not ") and e.p == PREC["not"]:
        return E(e.s[4:], 100) if True else e
    if e.p == PREC["cmp"]:
        for a, b in ((" == ", " != "), (" != ", " == "), (" < ", " >= "), (" >= ", " < "),
                     (" > ", " <= "), (" <= ", " > "), (" not in ", " in "), (" is not ", " is ")):
            if e.s.count(a) == 1 and not any(x in e.s for x in ("(", "[")) or (e.s.count(a) == 1 and _top_level(e.s, a)):
                return E(e.s.replace(a, b, 1), PREC["cmp"])
        if _top_level(e.s, " in ") and e.s.count(" in ") == 1:
            return E(e.s.replace(" in ", " not in ", 1), PREC["cmp"])
    return E("not " + par(e, PREC["not"]), PREC["not"])


def _top_level(s, needle):
    depth = 0
    i = 0
    q = None
    while i < len(s):
        c = s[i]
        if q:
            if c == "\\":
                i += 2
                continue
            if c == q:
                q = None
        elif c in "'\"":
            q = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and s.startswith(needle, i):
            return True
        i += 1
    return False


def andop(a, b):
    return E(par(a, 2) + " and " + par(b, 3), 2)


def orop(a, b):
    return E(par(a, 1) + " or " + par(b, 2), 1)


def const(v):
    if isinstance(v, types.CodeType):
        return E("<code %s>" % v.co_name)
    if isinstance(v, frozenset):
        return E("frozenset(%r)" % (set(v),))
    r = repr(v)
    return E(r, 100 if not (isinstance(v, (int, float)) and v < 0) else PREC["u"])


class Block:
    def __init__(self, start):
        self.start = start
        self.ins = []
        self.stmts = []      # list of strings (or ('def', ...) tuples)
        self.term = None     # ('jump', t) | ('cond', E, t, f) | ('for', iterE, body, exit, target) | ('ret', E) | ('fall', t) | ('raise', s)
        self.preds = set()

    def succ(self):
        t = self.term
        if t is None:
            return []
        k = t[0]
        if k in ("jump", "fall"):
            return [t[1]]
        if k == "cond":
            return [t[2], t[3]]
        if k == "for":
            return [t[2], t[3]]
        return []


class Decompiler:
    def __init__(self, code, start=None, end=None, indent="    ", tramp_base=None):
        self.code = code
        self.tramp_base = tramp_base
        self.indent = indent
        allins = [i for i in dis.get_instructions(code)]
        self.start = start if start is not None else 0
        self.end = end if end is not None else len(code.co_code)
        # real instruction offsets; map EXTENDED_ARG offsets forward
        self.ins = [i for i in allins if self.start <= i.offset < self.end and i.opname != "EXTENDED_ARG"]
        self.fwd = {}
        nxt = self.end
        for i in reversed([i for i in allins if self.start <= i.offset < self.end]):
            if i.opname != "EXTENDED_ARG":
                nxt = i.offset
            self.fwd[i.offset] = nxt
        self.fwd[self.end] = self.end
        self.EXIT = self.end
        self.problems = []

    def tgt(self, ins):
        t = ins.argval
        if t >= self.end or t < self.start:
            if t < self.start:
                self.problems.append("jump below region %d->%d" % (ins.offset, t))
            return self.EXIT if t >= self.end else t
        return self.fwd.get(t, t)

    # ---------------------------------------------------------------- blocks
    def build(self):
        leaders = {self.ins[0].offset} if self.ins else set()
        for k, i in enumerate(self.ins):
            if i.opcode in JUMPS:
                leaders.add(self.tgt(i))
                if k + 1 < len(self.ins):
                    leaders.add(self.ins[k + 1].offset)
            elif i.opname in TERMINAL and k + 1 < len(self.ins):
                leaders.add(self.ins[k + 1].offset)
            if i.opname == "FOR_ITER":
                leaders.add(i.offset)
        leaders.discard(self.EXIT)
        blocks = {}
        cur = None
        for i in self.ins:
            if i.offset in leaders:
                cur = Block(i.offset)
                blocks[i.offset] = cur
            cur.ins.append(i)
        order = sorted(blocks)
        self.blocks = blocks
        self.order = order
        self.nextof = {o: (order[k + 1] if k + 1 < len(order) else self.EXIT) for k, o in enumerate(order)}

    # ------------------------------------------------------ symbolic execution
    def run_blocks(self):
        entry = {self.order[0]: []} if self.order else {}
        work = list(self.order[:1])
        seen = set()
        while work:
            b = work.pop(0)
            if b in seen or b == self.EXIT:
                continue
            seen.add(b)
            stack = list(entry.get(b, []))
            blk = self.blocks[b]
            out = self.exec_block(blk, stack)
            for s, st in out:
                if s == self.EXIT:
                    continue
                if s not in entry:
                    entry[s] = st
                work.append(s)
        # drop unreachable blocks (dead code, other regions of a sliced module)
        for b in list(self.order):
            if b not in seen:
                del self.blocks[b]
        self.order = [b for b in self.order if b in seen]
        self.nextof_live = {o: (self.order[k + 1] if k + 1 < len(self.order) else self.EXIT) for k, o in enumerate(self.order)}

    def exec_block(self, blk, stack):
        st = blk.stmts
        out = []
        ins = blk.ins
        k = 0
        pending_unpack = None
        while k < len(ins):
            i = ins[k]
            op = i.opname
            a = i.argval
            if op in ("LOAD_NAME", "LOAD_GLOBAL", "LOAD_FAST", "LOAD_DEREF", "LOAD_CLASSDEREF"):
                stack.append(E(str(a)))
            elif op == "LOAD_CLOSURE":
                stack.append(E(str(a)))
            elif op == "LOAD_CONST":
                stack.append(const(a) if not isinstance(a, types.CodeType) else E("<code>", 100, inplace=("code", a)))
            elif op in ("STORE_NAME", "STORE_GLOBAL", "STORE_FAST", "STORE_DEREF"):
                v = stack.pop()
                if pending_unpack is not None:
                    pending_unpack[1].append(str(a))
                    if len(pending_unpack[1]) == pending_unpack[2]:
                        st.append("%s = %s" % (", ".join(pending_unpack[1]), pending_unpack[0].s))
                        pending_unpack = None
                elif v.inplace and v.inplace[0] == "func":
                    st.append(("def", str(a), v.inplace[1], v.inplace[2]))
                elif v.inplace and v.inplace[0] == "iop" and v.inplace[1] == str(a):
                    st.append("%s %s= %s" % (a, v.inplace[2], v.inplace[3].s))
                elif v.s == "<FORITEM>":
                    st.append(("forstore", str(a)))
                else:
                    st.append("%s = %s" % (a, v.s))
            elif op in ("DELETE_NAME", "DELETE_FAST", "DELETE_GLOBAL"):
                st.append("del %s" % a)
            elif op == "STORE_ATTR":
                obj = stack.pop(); v = stack.pop()
                tgt = "%s.%s" % (par(obj, 100), a)
                if v.inplace and v.inplace[0] == "iop" and v.inplace[1] == tgt:
                    st.append("%s %s= %s" % (tgt, v.inplace[2], v.inplace[3].s))
                elif pending_unpack is not None:
                    pending_unpack[1].append(tgt)
                    if len(pending_unpack[1]) == pending_unpack[2]:
                        st.append("%s = %s" % (", ".join(pending_unpack[1]), pending_unpack[0].s)); pending_unpack = None
                else:
                    st.append("%s = %s" % (tgt, v.s))
            elif op == "LOAD_ATTR":
                o = stack.pop()
                stack.append(E("%s.%s" % (par(o, 100), a)))
            elif op == "LOAD_METHOD":
                o = stack.pop()
                stack.append(E("%s.%s" % (par(o, 100), a)))
            elif op == "BINARY_SUBSCR":
                key = stack.pop(); o = stack.pop()
                stack.append(E("%s[%s]" % (par(o, 100), key.s)))
            elif op == "STORE_SUBSCR":
                key = stack.pop(); o = stack.pop(); v = stack.pop()
                tgt = "%s[%s]" % (par(o, 100), key.s)
                if v.inplace and v.inplace[0] == "iop" and v.inplace[1] == tgt:
                    st.append("%s %s= %s" % (tgt, v.inplace[2], v.inplace[3].s))
                elif pending_unpack is not None:
                    pending_unpack[1].append(tgt)
                    if len(pending_unpack[1]) == pending_unpack[2]:
                        st.append("%s = %s" % (", ".join(pending_unpack[1]), pending_unpack[0].s)); pending_unpack = None
                else:
                    st.append("%s = %s" % (tgt, v.s))
            elif op == "DELETE_SUBSCR":
                key = stack.pop(); o = stack.pop()
                st.append("del %s[%s]" % (par(o, 100), key.s))
            elif op == "DUP_TOP":
                stack.append(stack[-1])
            elif op == "DUP_TOP_TWO":
                stack.extend(stack[-2:])
            elif op == "ROT_TWO":
                stack[-1], stack[-2] = stack[-2], stack[-1]
            elif op == "ROT_THREE":
                stack[-1], stack[-2], stack[-3] = stack[-2], stack[-3], stack[-1]
            elif op == "ROT_FOUR":
                stack[-1], stack[-2], stack[-3], stack[-4] = stack[-2], stack[-3], stack[-4], stack[-1]
            elif op == "POP_TOP":
                v = stack.pop()
                if v.s not in ("<FORITEM>", "<iter>"):
                    st.append(v.s)
            elif op in BINOPS:
                b = stack.pop(); x = stack.pop()
                if op == "BINARY_SUBSCR":
                    pass
                stack.append(binop(x, BINOPS[op], b))
            elif op in INPLACE:
                b = stack.pop(); x = stack.pop()
                stack.append(E("<inplace>", 100, inplace=("iop", x.s, INPLACE[op], b)))
            elif op == "UNARY_NEGATIVE":
                x = stack.pop(); stack.append(E("-" + par(x, PREC["u"]), PREC["u"]))
            elif op == "UNARY_POSITIVE":
                x = stack.pop(); stack.append(E("+" + par(x, PREC["u"]), PREC["u"]))
            elif op == "UNARY_INVERT":
                x = stack.pop(); stack.append(E("~" + par(x, PREC["u"]), PREC["u"]))
            elif op == "UNARY_NOT":
                x = stack.pop(); stack.append(neg(x))
            elif op == "COMPARE_OP":
                b = stack.pop(); x = stack.pop()
                stack.append(cmpop(x, i.argrepr, b))
            elif op in ("CALL_FUNCTION", "CALL_METHOD"):
                n = i.arg
                args = stack[len(stack) - n:] if n else []
                del stack[len(stack) - n:]
                f = stack.pop()
                if f.inplace and f.inplace[0] == "comp":
                    stack.append(E(self.comprehension(f.inplace[1], args[0])))
                else:
                    stack.append(E("%s(%s)" % (par(f, 100), ", ".join(x.s for x in args))))
            elif op == "CALL_FUNCTION_KW":
                names = stack.pop()
                n = i.arg
                args = stack[len(stack) - n:]
                del stack[len(stack) - n:]
                f = stack.pop()
                kn = eval(names.s)
                pos = args[:n - len(kn)]
                kw = ["%s=%s" % (k, v.s) for k, v in zip(kn, args[n - len(kn):])]
                stack.append(E("%s(%s)" % (par(f, 100), ", ".join([x.s for x in pos] + kw))))
            elif op == "CALL_FUNCTION_EX":
                kw = stack.pop() if i.arg & 1 else None
                ar = stack.pop()
                f = stack.pop()
                parts = ["*" + ar.s] + (["**" + kw.s] if kw else [])
                stack.append(E("%s(%s)" % (par(f, 100), ", ".join(parts))))
            elif op in ("BUILD_LIST", "BUILD_TUPLE", "BUILD_SET"):
                n = i.arg
                items = stack[len(stack) - n:] if n else []
                del stack[len(stack) - n:]
                inner = ", ".join(x.s for x in items)
                if op == "BUILD_LIST":
                    stack.append(E("[" + inner + "]"))
                elif op == "BUILD_TUPLE":
                    stack.append(E("(" + inner + ("," if n == 1 else "") + ")"))
                else:
                    stack.append(E("{" + inner + "}" if n else "set()"))
            elif op == "BUILD_MAP":
                n = i.arg
                items = stack[len(stack) - 2 * n:] if n else []
                del stack[len(stack) - 2 * n:]
                stack.append(E("{" + ", ".join("%s: %s" % (items[j].s, items[j + 1].s) for j in range(0, len(items), 2)) + "}"))
            elif op == "BUILD_CONST_KEY_MAP":
                keys = eval(stack.pop().s)
                n = i.arg
                items = stack[len(stack) - n:]
                del stack[len(stack) - n:]
                stack.append(E("{" + ", ".join("%r: %s" % (k, v.s) for k, v in zip(keys, items)) + "}"))
            elif op in ("LIST_EXTEND", "LIST_TO_TUPLE"):
                stack.append(E("<%s>" % op))
            elif op == "BUILD_SLICE":
                n = i.arg
                items = stack[len(stack) - n:]
                del stack[len(stack) - n:]
                txt = [("" if x.s == "None" else x.s) for x in items]
                stack.append(E(":".join(txt)))
            elif op == "UNPACK_SEQUENCE":
                v = stack.pop()
                pending_unpack = (v, [], i.arg)
                for _ in range(i.arg):
                    stack.append(E("<unpacked>"))
            elif op == "MAKE_FUNCTION":
                qual = stack.pop()
                codee = stack.pop()
                code = codee.inplace[1] if codee.inplace else None
                defaults = closure = None
                if i.arg & 8:
                    closure = stack.pop()
                if i.arg & 4:
                    stack.pop()
                if i.arg & 2:
                    stack.pop()
                if i.arg & 1:
                    defaults = stack.pop()
                if code is not None and code.co_name in ("<listcomp>", "<setcomp>", "<dictcomp>", "<genexpr>"):
                    stack.append(E("<comp>", 100, inplace=("comp", code)))
                elif code is not None and code.co_name == "<lambda>":
                    body = Decompiler(code).lambda_body()
                    stack.append(E("(lambda %s: %s)" % (", ".join(code.co_varnames[:code.co_argcount]), body)))
                else:
                    stack.append(E("<function>", 100, inplace=("func", code, defaults)))
            elif op == "GET_ITER":
                x = stack.pop(); stack.append(E("<iter>", 100, inplace=("iter", x)))
            elif op == "FOR_ITER":
                it = stack[-1]
                body = self.nextof[blk.start] if blk.ins[-1] is i else None
                exitt = self.tgt(i)
                blk.term = ("for", it.inplace[1] if it.inplace else it, self.nextof[blk.start], exitt)
                out.append((self.nextof[blk.start], stack + [E("<FORITEM>")]))
                out.append((exitt, stack[:-1]))
                return out
            elif op == "RETURN_VALUE":
                v = stack.pop()
                blk.term = ("ret", v)
                return out
            elif op == "RAISE_VARARGS":
                args = [stack.pop() for _ in range(i.arg)][::-1]
                blk.term = ("raise", ", ".join(x.s for x in args))
                return out
            elif op in ("POP_JUMP_IF_FALSE", "POP_JUMP_IF_TRUE"):
                c = stack.pop()
                t = self.tgt(i)
                nx = self.nextof[blk.start]
                if op == "POP_JUMP_IF_FALSE":
                    blk.term = ("cond", c, nx, t)
                else:
                    blk.term = ("cond", c, t, nx)
                out.append((nx, list(stack))); out.append((t, list(stack)))
                blk.exit_stack = list(stack)
                return out
            elif op in ("JUMP_IF_FALSE_OR_POP", "JUMP_IF_TRUE_OR_POP"):
                # value-context and/or: emitted as conditional on stack (rare)
                c = stack[-1]
                t = self.tgt(i)
                nx = self.nextof[blk.start]
                if op == "JUMP_IF_FALSE_OR_POP":
                    blk.term = ("vcond", "and", c, nx, t)
                else:
                    blk.term = ("vcond", "or", c, nx, t)
                out.append((nx, stack[:-1])); out.append((t, list(stack)))
                return out
            elif op in ("JUMP_ABSOLUTE", "JUMP_FORWARD"):
                t = self.tgt(i)
                blk.term = ("jump", t)
                blk.exit_stack = list(stack)
                out.append((t, list(stack)))
                return out
            elif op == "NOP":
                pass
            elif op == "LIST_APPEND":
                v = stack.pop()
                st.append("<append %s>" % v.s)
            elif op == "FORMAT_VALUE":
                fmt = None
                if (i.arg & 4):
                    fmt = stack.pop()
                v = stack.pop()
                stack.append(E("{" + v.s + "}"))
            elif op == "BUILD_STRING":
                n = i.arg
                items = stack[len(stack) - n:]
                del stack[len(stack) - n:]
                stack.append(E("f" + repr("".join(x.s if x.s.startswith("{") else eval(x.s) for x in items))))
            else:
                st.append("# ?? %s %r" % (op, a))
                self.problems.append("op %s at %d" % (op, i.offset))
            k += 1
        # fallthrough
        nx = self.nextof[blk.start]
        blk.term = ("fall", nx)
        blk.exit_stack = list(stack)
        out.append((nx, list(stack)))
        return out

    # --------------------------------------------- value-context expressions
    def collapse_ternaries(self):
        """cond block X -> A (push v1, jump J) / B (push v2, fall J): J gets `v1 if c else v2`."""
        changed = True
        while changed:
            changed = False
            for x in self.order:
                bx = self.blocks.get(x)
                if bx is None or bx.term is None or bx.term[0] != "cond":
                    continue
                _, c, t, f = bx.term
                bt, bf = self.blocks.get(t), self.blocks.get(f)
                if bt is None or bf is None or bt.stmts or bf.stmts:
                    continue
                if len(bt.preds) != 1 or len(bf.preds) != 1:
                    continue
                st_t = getattr(bt, "exit_stack", None); st_f = getattr(bf, "exit_stack", None)
                base = getattr(bx, "exit_stack", None)
                if st_t is None or st_f is None or base is None:
                    continue
                if len(st_t) != len(base) + 1 or len(st_f) != len(base) + 1:
                    continue
                jt = bt.succ(); jf = bf.succ()
                if len(jt) != 1 or jt != jf:
                    continue
                v = E("%s if %s else %s" % (par(st_t[-1], 1), par(c, 1), par(st_f[-1], 1)), 0)
                self.ternary_fix(x, jt[0], v)
                changed = True
                break

    def ternary_fix(self, x, j, v):
        raise NotImplementedError("ternary expressions in branch context")

    # ------------------------------------------------- condition merging
    def link(self):
        for b in self.blocks.values():
            b.preds = set()
        for o, b in self.blocks.items():
            for s in b.succ():
                if s in self.blocks:
                    self.blocks[s].preds.add(o)

    def merge_conditions(self):
        changed = True
        while changed:
            changed = False
            self.link()
            for x in self.order:
                bx = self.blocks[x]
                if bx.term is None or bx.term[0] != "cond":
                    continue
                _, c1, A, B = bx.term
                for yi, y in ((0, A), (1, B)):
                    by = self.blocks.get(y)
                    if by is None or by is bx or by.stmts or by.term is None or by.term[0] != "cond":
                        continue
                    if len(by.preds) != 1:
                        continue
                    if getattr(by, "isloophead", False):
                        continue
                    _, c2, P, Q = by.term
                    other = B if yi == 0 else A
                    if yi == 0:   # c1 true -> Y
                        if other == Q:
                            nc, nt, nf = andop(c1, c2), P, Q
                        elif other == P:
                            nc, nt, nf = orop(neg(c1), c2), P, Q
                        else:
                            continue
                    else:         # c1 false -> Y
                        if other == P:
                            nc, nt, nf = orop(c1, c2), P, Q
                        elif other == Q:
                            nc, nt, nf = andop(neg(c1), c2), P, Q
                        else:
                            continue
                    bx.term = ("cond", nc, nt, nf)
                    by.merged = True
                    del self.blocks[y]
                    self.order.remove(y)
                    changed = True
                    break
                if changed:
                    break

    # ----------------------------------------------------------- structure
    def analyse(self):
        self.link()
        self.loopheads = {}
        # for-loops
        for o, b in self.blocks.items():
            if b.term and b.term[0] == "for":
                self.loopheads[o] = ("for", b.term[3])
        # while loops: back edges to non-for heads
        for o, b in self.blocks.items():
            if self.tramp_base is not None and o >= self.tramp_base:
                continue
            for s in b.succ():
                if s != self.EXIT and s <= o and s not in self.loopheads:
                    # exit of a while loop: the false branch of a cond head, or
                    # the block after the latest back-edge source
                    hb = self.blocks.get(s)
                    ex = None
                    if hb is not None and hb.term and hb.term[0] == "cond" and hb.term[3] > o:
                        ex = hb.term[3]
                    self.loopheads[s] = ("while", ex)
        for s, (kind, ex) in list(self.loopheads.items()):
            if kind == "while" and ex is None:
                latches = [o for o, b in self.blocks.items() if s in b.succ() and o >= s
                           and not (self.tramp_base is not None and o >= self.tramp_base)]
                body = {s}
                work = list(latches)
                while work:
                    n = work.pop()
                    if n in body:
                        continue
                    body.add(n)
                    work.extend(p for p in self.blocks[n].preds if p in self.blocks)
                exits = {}
                for n in body:
                    for t in self.blocks[n].succ():
                        if t not in body:
                            exits[t] = exits.get(t, 0) + 1
                if exits:
                    # prefer the exit no other exit can reach (the outermost join)
                    cands = sorted(exits)
                    best = None
                    for c in cands:
                        if all(c == o or c not in self.reach(o, body) for o in cands):
                            pass
                    # choose: an exit reachable from every other exit, else smallest
                    for c in cands:
                        if all(c == o or c in self.reach(o, body | {c}) or self.resolve(o) == c for o in cands):
                            best = c
                            break
                    ex = best if best is not None else min(cands)
                else:
                    latest = max(latches) if latches else s
                    ex = self.nextof_live.get(latest, self.EXIT)
                self.loopheads[s] = ("while", ex)

    def reach(self, start, stops):
        seen = set()
        work = [start]
        while work:
            b = work.pop()
            if b in seen or b in stops or b == self.EXIT or b not in self.blocks:
                continue
            seen.add(b)
            work.extend(self.blocks[b].succ())
        return seen

    def postdoms(self):
        """Immediate post-dominators (Cooper-Harvey-Kennedy on the reverse CFG)."""
        SINK = "SINK"
        nodes = list(self.blocks)
        succ = {n: [s if s in self.blocks else SINK for s in self.blocks[n].succ()] or [SINK] for n in nodes}
        pred = {n: [] for n in nodes}
        pred[SINK] = []
        for n in nodes:
            for s in succ[n]:
                pred.setdefault(s, []).append(n)
        # reverse postorder on the reverse graph from SINK
        order, seen = [], set()
        stack = [(SINK, iter(pred[SINK]))]
        seen.add(SINK)
        while stack:
            n, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop(); order.append(n)
            elif nxt not in seen:
                seen.add(nxt); stack.append((nxt, iter(pred.get(nxt, []))))
        rpo = list(reversed(order))
        idx = {n: i for i, n in enumerate(rpo)}
        ipd = {SINK: SINK}
        changed = True
        while changed:
            changed = False
            for n in rpo:
                if n == SINK:
                    continue
                cands = [s for s in succ[n] if s in ipd]
                if not cands:
                    continue
                new = cands[0]
                for s in cands[1:]:
                    a, b = new, s
                    while a != b:
                        while idx[a] > idx[b]:
                            a = ipd[a]
                        while idx[b] > idx[a]:
                            b = ipd[b]
                    new = a
                if ipd.get(n) != new:
                    ipd[n] = new; changed = True
        self.ipdom = ipd

    def find_follow(self, x, t, f, stops, ab=frozenset()):
        if t in stops and t not in ab:
            return t
        if f in stops and f not in ab:
            return f
        if t in ab or t == self.EXIT:
            return f
        if f in ab or f == self.EXIT:
            return t
        p = self.ipdom.get(x)
        rt = self.reach(t, stops | {x})
        rf = self.reach(f, stops | {x})
        if p not in (None, "SINK") and p in stops and p not in ab:
            return p
        if p not in (None, "SINK") and (p in rt or p == t) and (p in rf or p == f):
            return p
        if f in rt:
            return f
        if t in rf:
            return t
        common = rt & rf
        if not common:
            return f
        return min(common)

    def emit(self, start, stops, loops, depth, out, natural=None):
        b = start
        guard = 0
        while True:
            guard += 1
            if guard > 100000:
                out.append(self.indent * depth + "# ?? structuring loop")
                return
            if b == self.EXIT:
                if natural != self.EXIT:
                    if loops or depth:
                        out.append(self.indent * depth + "return  # region end")
                return
            if loops and b == loops[-1][0]:
                if b != natural:
                    out.append(self.indent * depth + "continue")
                return
            if loops and loops[-1][1] is not None and (b == loops[-1][1] or self.resolve(b) == self.resolve(loops[-1][1])):
                if b != natural:
                    out.append(self.indent * depth + "break")
                return
            outer = self.outer_jump(b, loops)
            if outer:
                out.append(self.indent * depth + outer)
                return
            if b in stops:
                if b != natural:
                    out.append(self.indent * depth + "# goto @%d" % b)
                return
            if b in self.loopheads and (not loops or loops[-1][0] != b):
                b = self.emit_loop(b, stops, loops, depth, out)
                continue
            blk = self.blocks[b]
            self.emitted[b] = self.emitted.get(b, 0) + 1
            if self.emitted[b] > getattr(self, "dup_limit", 1) and b >= 0:
                self.problems.append("block %d emitted twice" % b)
                out.append(self.indent * depth + "# !! GOTO @%d (already emitted above)" % b)
                return
            for s in blk.stmts:
                self.emit_stmt(s, depth, out)
            t = blk.term
            k = t[0]
            if k in ("fall", "jump"):
                b = t[1]
                continue
            if k == "ret":
                out.append(self.indent * depth + "return %s" % t[1].s if t[1].s != "None" else self.indent * depth + "return")
                return
            if k == "raise":
                out.append(self.indent * depth + "raise " + t[1])
                return
            if k == "cond":
                _, c, tt, ff = t
                ab = self.loopstops(loops)
                fol = self.find_follow(b, tt, ff, stops | ab, ab)
                if fol == ff:
                    out.append(self.indent * depth + "if %s:" % c.s)
                    self.emit_body(tt, stops | {fol}, loops, depth + 1, out, fol)
                elif fol == tt:
                    out.append(self.indent * depth + "if %s:" % neg(c).s)
                    self.emit_body(ff, stops | {fol}, loops, depth + 1, out, fol)
                else:
                    out.append(self.indent * depth + "if %s:" % c.s)
                    self.emit_body(tt, stops | ({fol} if fol is not None else set()), loops, depth + 1, out, fol)
                    # elif chain
                    out.append(self.indent * depth + "else:")
                    self.emit_body(ff, stops | ({fol} if fol is not None else set()), loops, depth + 1, out, fol)
                if fol is None:
                    return
                b = fol
                continue
            if k == "vcond":
                out.append(self.indent * depth + "# ?? value-context and/or at @%d" % b)
                return
            if k == "for":
                out.append(self.indent * depth + "# ?? stray for @%d" % b)
                return

    def resolve(self, b):
        seen = set()
        while b in self.blocks and b not in seen:
            seen.add(b)
            blk = self.blocks[b]
            if blk.stmts or blk.term is None or blk.term[0] not in ("jump", "fall"):
                break
            if b in self.loopheads:
                break
            b = blk.term[1]
        return b

    def outer_jump(self, b, loops):
        """A jump from an inner loop to an enclosing loop's head/exit."""
        if len(loops) < 2:
            return None
        inner_exit = loops[-1][1]
        rb = self.resolve(b)
        for j in range(len(loops) - 2, -1, -1):
            h, e = loops[j]
            if rb in (h, self.resolve(h)) or rb in (e, self.resolve(e) if e is not None else None):
                if inner_exit is not None and self.resolve(inner_exit) == rb:
                    return "break"
                kind = "continue" if rb in (h, self.resolve(h)) else "break"
                return "# ?? %s of outer loop @%d (%d levels)" % (kind, h, len(loops) - 1 - j)
        return None

    def loopstops(self, loops):
        s = set()
        for h, e in loops:
            s.add(h)
            if e is not None:
                s.add(e)
        s.add(self.EXIT)
        return s

    def emit_body(self, start, stops, loops, depth, out, natural):
        n = len(out)
        self.emit(start, stops, loops, depth, out, natural)
        if all(l.strip().startswith("#") for l in out[n:]):
            out.append(self.indent * depth + "pass")

    def emit_loop(self, h, stops, loops, depth, out):
        kind, ex = self.loopheads[h]
        blk = self.blocks[h]
        if kind == "for":
            it = blk.term[1]
            body = blk.term[2]
            bb = self.blocks.get(body)
            var = "_"
            if bb is not None and bb.stmts and isinstance(bb.stmts[0], tuple) and bb.stmts[0][0] == "forstore":
                var = bb.stmts[0][1]
                bb.stmts = bb.stmts[1:]
            elif bb is not None and bb.stmts and isinstance(bb.stmts[0], str) and bb.stmts[0].endswith("= <unpacked>"):
                pass
            for s in blk.stmts:
                self.emit_stmt(s, depth, out)
            out.append(self.indent * depth + "for %s in %s:" % (var, it.s))
            self.emit_body(body, stops, loops + [(h, ex)], depth + 1, out, h)
            return ex
        # while loop
        if blk.term and blk.term[0] == "cond" and not blk.stmts and blk.term[3] == ex:
            out.append(self.indent * depth + "while %s:" % blk.term[1].s)
            self.emit_body(blk.term[2], stops, loops + [(h, ex)], depth + 1, out, h)
        else:
            out.append(self.indent * depth + "while True:")
            # body starts at the head itself; temporarily hide the head from loopheads
            saved = self.loopheads.pop(h)
            sub = []
            self.emit_inner_head(h, stops, loops + [(h, ex)], depth + 1, sub)
            self.loopheads[h] = saved
            out.extend(sub if sub else [self.indent * (depth + 1) + "pass"])
        return ex

    def emit_inner_head(self, h, stops, loops, depth, out):
        blk = self.blocks[h]
        for s in blk.stmts:
            self.emit_stmt(s, depth, out)
        # emulate emit() from inside the head block with its terminator
        self._fake = getattr(self, "_fake", 0) - 1
        tmp_id = self._fake
        fake = Block(tmp_id)
        self.blocks[tmp_id] = fake
        fake.stmts = []
        fake.term = blk.term
        try:
            self.emit(tmp_id, stops, loops, depth, out, h)
        finally:
            del self.blocks[tmp_id]

    def emit_stmt(self, s, depth, out):
        ind = self.indent * depth
        if isinstance(s, tuple):
            if s[0] == "def":
                _, name, code, defaults = s
                args = list(code.co_varnames[:code.co_argcount + code.co_kwonlyargcount])
                if code.co_flags & 4:
                    args.append("*" + code.co_varnames[code.co_argcount + code.co_kwonlyargcount])
                if defaults is not None:
                    try:
                        dv = eval(defaults.s)
                        if not isinstance(dv, tuple):
                            dv = (dv,)
                        for j, d in enumerate(dv):
                            idx = code.co_argcount - len(dv) + j
                            args[idx] = "%s=%r" % (args[idx], d)
                    except Exception:
                        args.append("# defaults " + defaults.s)
                out.append(ind + "def %s(%s):" % (name, ", ".join(args)))
                sub = Decompiler(code, indent=self.indent)
                try:
                    body = sub.decompile_lines()
                except Exception as ex:
                    body = ["# !! body not decompiled (%r); disassembly:" % ex] + [
                        "#   %d %s %s" % (i.offset, i.opname, i.argrepr) for i in dis.get_instructions(code)
                        if i.opname != "EXTENDED_ARG"]
                for line in body:
                    out.append(ind + self.indent + line)
                if not body:
                    out.append(ind + self.indent + "pass")
                self.problems += ["%s: %s" % (name, p) for p in sub.problems]
                return
            if s[0] == "forstore":
                out.append(ind + "%s = <FORITEM>" % s[1])
                return
        out.append(ind + s)

    def comprehension(self, code, iterable):
        d = Decompiler(code)
        d.build(); d.run_blocks()
        # gather: for var in .0: [if cond:] <append expr>
        txt = " ".join(d.decompile_lines())
        lines = d.decompile_lines()
        it = iterable.inplace[1].s if iterable.inplace else iterable.s
        # simple shapes
        import re
        flat = [l.strip() for l in lines if l.strip() and not l.strip().startswith("return")]
        expr = None; conds = []; var = None
        for l in flat:
            m = re.match(r"for (.+) in \.0:$", l)
            if m:
                var = m.group(1); continue
            m = re.match(r"if (.+):$", l)
            if m:
                conds.append(m.group(1)); continue
            m = re.match(r"<append (.+)>$", l)
            if m:
                expr = m.group(1); continue
            if l == ".0 = []" or l.startswith("[]") or l == "pass":
                continue
        if var and expr:
            return "[%s for %s in %s%s]" % (expr, var, it, "".join(" if " + c for c in conds))
        return "<comprehension %s over %s: %s>" % (code.co_name, it, " | ".join(flat))

    def lambda_body(self):
        lines = self.decompile_lines()
        if len(lines) == 1 and lines[0].startswith("return "):
            return lines[0][7:]
        return " ; ".join(lines)

    def decompile_lines(self):
        if not self.ins:
            return []
        self.build()
        self.run_blocks()
        self.link()
        self.merge_conditions()
        self.analyse()
        self.postdoms()
        self.emitted = {}
        out = []
        self.emit(self.order[0], set(), [], 0, out, self.EXIT)
        # trim trailing bare return in functions
        while out and out[-1] in ("return", "return None"):
            out.pop()
        if self.code.co_flags & 0x02:   # CO_NEWLOCALS: a function body
            gl = []
            for i in dis.get_instructions(self.code):
                if i.opname in ("STORE_GLOBAL", "DELETE_GLOBAL") and i.argval not in gl:
                    gl.append(i.argval)
            if gl:
                out.insert(0, "global " + ", ".join(gl))
        return out


def decompile(code, start=None, end=None):
    d = Decompiler(code, start, end)
    lines = d.decompile_lines()
    return "\n".join(lines), d.problems


if __name__ == "__main__":
    import marshal
    code = marshal.loads(open(sys.argv[1], "rb").read())
    s = int(sys.argv[2]) if len(sys.argv) > 2 else None
    e = int(sys.argv[3]) if len(sys.argv) > 3 else None
    text, probs = decompile(code, s, e)
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    for p in probs:
        print("# PROBLEM", p)
