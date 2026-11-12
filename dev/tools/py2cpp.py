"""Translate the (decompiled) original game Python into C++ over the pvz V runtime.

    python tools/py2cpp.py <out.cpp> <unit-name> <src.py>:<kind>:<cname> ...

kind = region   -> void <cname>(Match& G)          (module-level code; every name is a G member)
     = funcs    -> one C++ function per `def` in the file, registered as G.<name> = V::func(...)

Conventions of the emitted code (see src/sim/pyrt.h):
  G.名            match global (V)
  rd(v, k)        python v[k] read  (k a V; unit dict member fast path)
  wr(v, k)        python v[k] lvalue
  call(f, a...)   call a V function value
  SV("..")        static string V
"""
import ast, sys, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJ_KEYS = set()
_inc = (ROOT / "src/core/obj_fields.inc").read_text(encoding="utf-8")
OBJ_KEYS = set(re.findall(r"X\(([^)]+)\)", _inc))

BUILTIN_CALLS = {
    "len": "py::len", "int": "py::int_", "float": "py::float_", "str": "py::str", "abs": "py::abs",
    "bool": "py::bool_", "list": "py::list", "tuple": "py::tuple", "sorted": "py::sorted",
    "reversed": "py::reversed", "sum": "py::sum",
}
METHODS = {  # obj.method(args) -> template
    "append": "{o}.append({a0})", "pop": None, "insert": "py::insert({o}, {a0}, {a1})",
    "remove": "py::remove({o}, {a0})", "index": "py::index({o}, {a0})", "count": "py::count({o}, {a0})",
    "extend": "py::extend({o}, {a0})", "get": None, "setdefault": "py::setdefault({o}, {a0}, {a1})",
    "keys": "py::keys({o})", "values": "py::values({o})", "items": "py::items({o})",
    "split": "py::split({o}, {a0})", "startswith": "V(py::startswith({o}, {a0}))",
    "endswith": "V(py::endswith({o}, {a0}))", "join": "py::join({o}, {a0})",
    "replace": "py::replace({o}, {a0}, {a1})", "copy": "py::copy({o})", "update": None,
}
ATTR_CALLS = {
    ("random", "randint"): "G.rng_randint({a0}, {a1})", ("random", "random"): "G.rng_random()",
    ("random", "choice"): "G.rng_choice({a0})", ("random", "uniform"): "G.rng_uniform({a0}, {a1})",
    ("random", "shuffle"): "G.rng_shuffle({a0})",
    ("copy", "deepcopy"): "py::deepcopy({a0})", ("copy", "copy"): "py::copy({a0})",
    ("math", "sin"): "V(std::sin(({a0}).num()))", ("math", "cos"): "V(std::cos(({a0}).num()))",
    ("math", "atan2"): "V(std::atan2(({a0}).num(), ({a1}).num()))", ("math", "sqrt"): "V(std::sqrt(({a0}).num()))",
    ("math", "radians"): "V(({a0}).num() * 3.141592653589793 / 180.0)",
    ("math", "degrees"): "V(({a0}).num() * 180.0 / 3.141592653589793)",
    ("math", "atan"): "V(std::atan(({a0}).num()))", ("math", "hypot"): "V(std::hypot(({a0}).num(), ({a1}).num()))",
    ("math", "floor"): "V(std::floor(({a0}).num()))", ("math", "ceil"): "V(std::ceil(({a0}).num()))",
    ("math", "pi"): "V(3.141592653589793)",
}


# (region, live line) -> f_lasti, and (region, callee) -> f_lasti for every call of that callee
CALL_SITE_LINES = {("zombies", 164): (72400, "伤害僵尸"), ("zombies", 166): (72430, "伤害僵尸"),
                   ("zombies", 169): (72550, "伤害僵尸"), ("zombies", 282): (75606, "掉血")}
CALL_SITE_CALLEES = {("zombies", "新增僵尸"): 0, ("plants", "种植植物"): 0}


class Ctx:
    def __init__(self, kind, locals_=(), globals_decl=()):
        self.kind = kind            # region | func
        self.locals = set(locals_)
        self.globals_decl = set(globals_decl)
        self.tmp = 0

    def is_local(self, name):
        return self.kind == "func" and name in self.locals and name not in self.globals_decl


class Translator:
    def __init__(self):
        self.globals_used = set()
        self.strings = {}
        self.funcs_out = []
        self.problems = []

    # ------------------------------------------------------------ names
    def name(self, n, ctx):
        if ctx.is_local(n):
            return "L_" + n
        if n in ("True", "False"):
            return "V(%s)" % n.lower()
        if n == "None":
            return "V::none()"
        self.globals_used.add(n)
        return "G." + n

    def sv(self, s):
        return "SV(%s)" % json.dumps(s, ensure_ascii=False)

    def const(self, v):
        if v is None:
            return "V::none()"
        if isinstance(v, bool):
            return "V(%s)" % ("true" if v else "false")
        if isinstance(v, (int, float)):
            r = repr(float(v))
            if r in ("inf", "-inf", "nan"):
                r = {"inf": "INFINITY", "-inf": "-INFINITY", "nan": "NAN"}[r]
            return "V(%s)" % r
        if isinstance(v, str):
            return self.sv(v)
        if isinstance(v, tuple):
            return "V::tuple({%s})" % ", ".join(self.const(x) for x in v)
        self.problems.append("const %r" % (v,))
        return "/*?const*/V::none()"

    # ------------------------------------------------------------ expressions
    def expr(self, e, ctx):
        m = getattr(self, "e_" + type(e).__name__, None)
        if m is None:
            self.problems.append("expr %s" % type(e).__name__)
            return "/*?%s*/V::none()" % type(e).__name__
        return m(e, ctx)

    def cond(self, e, ctx):
        """C++ bool expression for a Python truth test."""
        if isinstance(e, ast.BoolOp):
            op = " && " if isinstance(e.op, ast.And) else " || "
            return "(" + op.join(self.cond(v, ctx) for v in e.values) + ")"
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not):
            return "!" + self.cond(e.operand, ctx)
        if isinstance(e, ast.Compare):
            return self.compare(e, ctx)
        if isinstance(e, ast.Constant) and isinstance(e.value, bool):
            return "true" if e.value else "false"
        return "(%s).truthy()" % self.expr(e, ctx)

    def e_Constant(self, e, ctx):
        return self.const(e.value)

    def e_Name(self, e, ctx):
        return self.name(e.id, ctx)

    def e_BinOp(self, e, ctx):
        a, b = self.expr(e.left, ctx), self.expr(e.right, ctx)
        op = type(e.op).__name__
        if op == "FloorDiv":
            return "floordiv(%s, %s)" % (a, b)
        if op == "Pow":
            return "pow(%s, %s)" % (a, b)
        sym = {"Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "Mod": "%"}.get(op)
        if sym is None:
            self.problems.append("binop " + op)
            return "/*?%s*/V::none()" % op
        return "(%s %s %s)" % (a, sym, b)

    def e_UnaryOp(self, e, ctx):
        if isinstance(e.op, ast.Not):
            return "V(%s)" % self.cond(e, ctx)
        if isinstance(e.op, ast.USub):
            if isinstance(e.operand, ast.Constant) and isinstance(e.operand.value, (int, float)):
                return self.const(-e.operand.value)
            return "(-%s)" % self.expr(e.operand, ctx)
        if isinstance(e.op, ast.UAdd):
            return self.expr(e.operand, ctx)
        self.problems.append("unary")
        return "V::none()"

    def e_BoolOp(self, e, ctx):
        # value context: python returns the deciding operand
        vals = [self.expr(v, ctx) for v in e.values]
        out = vals[-1]
        for v in reversed(vals[:-1]):
            if isinstance(e.op, ast.And):
                out = "py_and(%s, [&]() -> V { return %s; })" % (v, out)
            else:
                out = "py_or(%s, [&]() -> V { return %s; })" % (v, out)
        return out

    def compare(self, e, ctx):
        parts = []
        left = self.expr(e.left, ctx)
        for op, right_node in zip(e.ops, e.comparators):
            right = self.expr(right_node, ctx)
            o = type(op).__name__
            if o == "In":
                parts.append("py::in(%s, %s)" % (left, right))
            elif o == "NotIn":
                parts.append("!py::in(%s, %s)" % (left, right))
            elif o == "Is":
                parts.append("py_is(%s, %s)" % (left, right))
            elif o == "IsNot":
                parts.append("!py_is(%s, %s)" % (left, right))
            else:
                sym = {"Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">="}[o]
                parts.append("(%s %s %s)" % (left, sym, right))
            left = right
        if len(parts) > 1:
            self.problems.append("chained comparison (operands evaluated twice)")
        return "(" + " && ".join(parts) + ")" if len(parts) > 1 else parts[0]

    def e_Compare(self, e, ctx):
        return "V(%s)" % self.compare(e, ctx)

    def key_expr(self, s):
        return self.expr(s, None) if False else None

    def e_Subscript(self, e, ctx):
        base = self.expr(e.value, ctx)
        sl = e.slice
        if isinstance(sl, ast.Index):
            sl = sl.value
        if isinstance(sl, ast.Slice):
            lo = self.expr(sl.lower, ctx) if sl.lower else "V::none()"
            hi = self.expr(sl.upper, ctx) if sl.upper else "V::none()"
            return "py::slice(%s, %s, %s)" % (base, lo, hi)
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str) and sl.value in OBJ_KEYS:
            return "rdm(%s, &Obj::%s, %s)" % (base, sl.value, self.sv(sl.value))
        return "rd(%s, %s)" % (base, self.expr(sl, ctx))

    def lvalue(self, t, ctx):
        if isinstance(t, ast.Name):
            return self.name(t.id, ctx)
        if isinstance(t, ast.Subscript):
            base = self.expr(t.value, ctx)
            sl = t.slice.value if isinstance(t.slice, ast.Index) else t.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str) and sl.value in OBJ_KEYS:
                return "wrm(%s, &Obj::%s, %s)" % (base, sl.value, self.sv(sl.value))
            return "wr(%s, %s)" % (base, self.expr(sl, ctx))
        if isinstance(t, ast.Attribute):
            return "attr(%s, %s)" % (self.expr(t.value, ctx), self.sv(t.attr))
        self.problems.append("lvalue %s" % type(t).__name__)
        return "/*?lvalue*/G._dummy"

    def e_Attribute(self, e, ctx):
        if isinstance(e.value, ast.Name) and (e.value.id, e.attr) in ATTR_CALLS and e.attr == "pi":
            return ATTR_CALLS[(e.value.id, e.attr)]
        if isinstance(e.value, ast.Name) and e.value.id == "pygame":
            return "G.pygame_attr(%s)" % self.sv(e.attr)
        return "attr(%s, %s)" % (self.expr(e.value, ctx), self.sv(e.attr))

    def e_Call(self, e, ctx):
        args = [self.expr(a, ctx) for a in e.args]
        if e.keywords:
            kw = ", ".join("{SY(%s), %s}" % (json.dumps(k.arg, ensure_ascii=False), self.expr(k.value, ctx)) for k in e.keywords)
            argv = "Args({%s}, {%s})" % (", ".join(args), kw)
            if isinstance(e.func, ast.Attribute):
                return "callm(%s, SY(%s), %s)" % (self.expr(e.func.value, ctx), json.dumps(e.func.attr, ensure_ascii=False), argv)
            return "(%s).call(%s)" % (self.expr(e.func, ctx), argv)
        f = e.func
        if isinstance(f, ast.Name):
            n = f.id
            if not ctx.is_local(n):
                if n == "range":
                    return "py::range(%s)" % ", ".join("(int64_t)(%s).num()" % a for a in args)
                if n == "min" or n == "max":
                    return "py::%s(%s)" % (n, ", ".join(args))
                if n == "round":
                    return "py::round(%s)" % ", ".join(args)
                if n == "isinstance":
                    self.problems.append("isinstance")
                if n == "随":
                    return "G.rng_randint(py::int_(%s), py::int_(%s))" % (args[0], args[1])
                if n in BUILTIN_CALLS:
                    return "%s(%s)" % (BUILTIN_CALLS[n], ", ".join(args))
            region = getattr(self, "region", None)
            site = CALL_SITE_LINES.get((region, getattr(self, "cur_line", None)))
            if site is not None and site[1] == n:
                self.globals_used.add("__region_" + region)
                return "py::call_site(G.__region_%s, %d, G.__self_ns, %s, Args{%s})" % (region, site[0], self.name(n, ctx), ", ".join(args))
            if (region, n) in CALL_SITE_CALLEES:
                self.globals_used.add("__region_" + region)
                return "py::call_site(G.__region_%s, %d, G.__self_ns, %s, Args{%s})" % (region, CALL_SITE_CALLEES[(region, n)], self.name(n, ctx), ", ".join(args))
            return "call(%s%s)" % (self.name(n, ctx), "".join(", " + a for a in args))
        if isinstance(f, ast.Attribute):
            if isinstance(f.value, ast.Name) and (f.value.id, f.attr) in ATTR_CALLS:
                t = ATTR_CALLS[(f.value.id, f.attr)]
                return t.format(**{"a%d" % i: a for i, a in enumerate(args)})
            o = self.expr(f.value, ctx)
            if f.attr in METHODS:
                t = METHODS[f.attr]
                if f.attr == "pop":
                    return "py::pop(%s%s)" % (o, "".join(", " + a for a in args))
                if f.attr == "get":
                    return "(%s).get(%s)" % (o, ", ".join(args))
                if f.attr == "update" and args:
                    return "py_update(%s, %s)" % (o, args[0])
                if t is not None:
                    return t.format(o=o, **{"a%d" % i: a for i, a in enumerate(args)})
            return "callm(%s, SY(%s), Args{%s})" % (o, json.dumps(f.attr, ensure_ascii=False), ", ".join(args))
        return "call(%s%s)" % (self.expr(f, ctx), "".join(", " + a for a in args))

    def e_List(self, e, ctx):
        return "V::list({%s})" % ", ".join(self.expr(x, ctx) for x in e.elts)

    def e_Tuple(self, e, ctx):
        return "V::tuple({%s})" % ", ".join(self.expr(x, ctx) for x in e.elts)

    def e_Dict(self, e, ctx):
        return "py_dict({%s})" % ", ".join("{%s, %s}" % (self.expr(k, ctx), self.expr(v, ctx)) for k, v in zip(e.keys, e.values))

    def e_IfExp(self, e, ctx):
        return "(%s ? V(%s) : V(%s))" % (self.cond(e.test, ctx), self.expr(e.body, ctx), self.expr(e.orelse, ctx))

    def e_ListComp(self, e, ctx):
        if len(e.generators) != 1:
            self.problems.append("multi-generator comprehension")
        g = e.generators[0]
        it = self.expr(g.iter, ctx)
        var = g.target.id
        sub = Ctx("func", ctx.locals | {var}, ctx.globals_decl)
        sub.kind = "func"
        conds = " && ".join(self.cond(c, sub) for c in g.ifs) or "true"
        return ("[&]() -> V { V out_ = V::list(); V it_ = py::iter_list(%s); for (size_t i_ = 0; i_ < it_.len(); ++i_) { V L_%s = it_.idx(i_); if (%s) out_.append(%s); } return out_; }()"
                % (it, var, conds, self.expr(e.elt, sub)))

    def e_Lambda(self, e, ctx):
        params = [a.arg for a in e.args.args]
        sub = Ctx("func", set(params), ())
        body = self.expr(e.body, sub)
        unpack = "".join("V L_%s = A.get(%d, SY(%s), &py_none_v); " % (p, i, json.dumps(p, ensure_ascii=False)) for i, p in enumerate(params))
        return "V::func([&G](const Args& A) -> V { %sreturn %s; })" % (unpack, body)

    # ------------------------------------------------------------ statements
    def block(self, stmts, ctx, ind):
        out = []
        for s in stmts:
            out += self.stmt(s, ctx, ind)
        return out

    def stmt(self, s, ctx, ind):
        self.cur_line = getattr(s, "lineno", None)
        m = getattr(self, "s_" + type(s).__name__, None)
        if m is None:
            self.problems.append("stmt %s" % type(s).__name__)
            return [ind + "/* ?? %s */" % type(s).__name__]
        return m(s, ctx, ind)

    def s_Expr(self, s, ctx, ind):
        if isinstance(s.value, ast.Constant) and isinstance(s.value.value, str):
            return []
        return [ind + "(void)%s;" % self.expr(s.value, ctx)]

    def s_Assign(self, s, ctx, ind):
        val = self.expr(s.value, ctx)
        out = []
        if len(s.targets) == 1 and isinstance(s.targets[0], ast.Tuple):
            ctx.tmp += 1
            t = "tu%d_" % ctx.tmp
            out.append(ind + "{ V %s = %s;" % (t, val))
            for i, el in enumerate(s.targets[0].elts):
                out.append(ind + "  %s = %s.idx(%d);" % (self.lvalue(el, ctx), t, i))
            out.append(ind + "}")
            return out
        if len(s.targets) > 1:
            ctx.tmp += 1
            t = "as%d_" % ctx.tmp
            out.append(ind + "{ V %s = %s;" % (t, val))
            for tg in s.targets:
                out.append(ind + "  %s = %s;" % (self.lvalue(tg, ctx), t))
            out.append(ind + "}")
            return out
        return [ind + "%s = %s;" % (self.lvalue(s.targets[0], ctx), val)]

    def s_AugAssign(self, s, ctx, ind):
        op = type(s.op).__name__
        val = self.expr(s.value, ctx)
        tgt = self.lvalue(s.target, ctx)
        if op == "FloorDiv":
            return [ind + "{ V& r_ = %s; r_ = floordiv(r_, %s); }" % (tgt, val)]
        sym = {"Add": "+=", "Sub": "-=", "Mult": "*=", "Div": "/=", "Mod": "%="}[op]
        return [ind + "%s %s %s;" % (tgt, sym, val)]

    def s_If(self, s, ctx, ind):
        out = [ind + "if (%s) {" % self.cond(s.test, ctx)]
        out += self.block(s.body, ctx, ind + "    ")
        orelse = s.orelse
        while len(orelse) == 1 and isinstance(orelse[0], ast.If):
            e = orelse[0]
            out.append(ind + "} else if (%s) {" % self.cond(e.test, ctx))
            out += self.block(e.body, ctx, ind + "    ")
            orelse = e.orelse
        if orelse:
            out.append(ind + "} else {")
            out += self.block(orelse, ctx, ind + "    ")
        out.append(ind + "}")
        return out

    def s_While(self, s, ctx, ind):
        out = [ind + "while (%s) {" % self.cond(s.test, ctx)]
        out += self.block(s.body, ctx, ind + "    ")
        out.append(ind + "}")
        if s.orelse:
            self.problems.append("while-else")
        return out

    def s_For(self, s, ctx, ind):
        ctx.tmp += 1
        k = ctx.tmp
        tgt = s.target
        it = s.iter
        out = []
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range" and not ctx.is_local("range"):
            a = [self.expr(x, ctx) for x in it.args]
            if len(a) == 1:
                start, stop, step = "0", "(int64_t)(%s).num()" % a[0], "1"
            else:
                start, stop = "(int64_t)(%s).num()" % a[0], "(int64_t)(%s).num()" % a[1]
                step = "(int64_t)(%s).num()" % a[2] if len(a) > 2 else "1"
            out.append(ind + "{ const int64_t b%d_ = %s, e%d_ = %s, s%d_ = %s;" % (k, start, k, stop, k, step))
            out.append(ind + "for (int64_t i%d_ = b%d_; s%d_ > 0 ? i%d_ < e%d_ : i%d_ > e%d_; i%d_ += s%d_) {" % (k, k, k, k, k, k, k, k, k))
            out.append(ind + "    %s = V(double(i%d_));" % (self.lvalue(tgt, ctx), k))
        else:
            out.append(ind + "{ V it%d_ = py::iter_list(%s);" % (k, self.expr(it, ctx)))
            out.append(ind + "for (size_t i%d_ = 0; i%d_ < it%d_.len(); ++i%d_) {" % (k, k, k, k))
            if isinstance(tgt, ast.Tuple):
                out.append(ind + "    V el%d_ = it%d_.idx(int64_t(i%d_));" % (k, k, k))
                for i, el in enumerate(tgt.elts):
                    out.append(ind + "    %s = el%d_.idx(%d);" % (self.lvalue(el, ctx), k, i))
            else:
                out.append(ind + "    %s = it%d_.idx(int64_t(i%d_));" % (self.lvalue(tgt, ctx), k, k))
        out += self.block(s.body, ctx, ind + "    ")
        out.append(ind + "}}")
        if s.orelse:
            self.problems.append("for-else")
        return out

    def s_Break(self, s, ctx, ind):
        return [ind + "break;"]

    def s_Continue(self, s, ctx, ind):
        return [ind + "continue;"]

    def s_Try(self, s, ctx, ind):
        # Recovered original image helpers use a bare Python except. Keep this
        # supported shape explicit; other handler forms must not silently pass.
        if len(s.handlers) != 1 or s.handlers[0].type is not None or s.orelse or s.finalbody:
            raise NotImplementedError("original translator: unsupported try shape")
        return ([ind + "try {"] + self.block(s.body,ctx,ind+"    ") +
                [ind + "} catch (const PyError&) {"] + self.block(s.handlers[0].body,ctx,ind+"    ") + [ind + "}"])

    def s_Pass(self, s, ctx, ind):
        return []

    def s_Return(self, s, ctx, ind):
        if ctx.kind == "region":
            return [ind + "return;"]
        return [ind + "return %s;" % (self.expr(s.value, ctx) if s.value else "V::none()")]

    def s_Delete(self, s, ctx, ind):
        out = []
        for t in s.targets:
            if isinstance(t, ast.Subscript):
                sl = t.slice.value if isinstance(t.slice, ast.Index) else t.slice
                out.append(ind + "py_del(%s, %s);" % (self.expr(t.value, ctx), self.expr(sl, ctx)))
            elif isinstance(t, ast.Name):
                out.append(ind + "%s.del();" % self.name(t.id, ctx))
        return out

    def s_Global(self, s, ctx, ind):
        return []

    def s_FunctionDef(self, s, ctx, ind):
        self.function(s)
        self.globals_used.add(s.name)
        return [ind + "G.%s = V::func([&G](const Args& A) -> V { return fn_%s(G, A); });" % (s.name, s.name)]

    def s_Import(self, s, ctx, ind):
        return []

    s_ImportFrom = s_Import

    # ------------------------------------------------------------ functions
    def function(self, fdef):
        params = [a.arg for a in fdef.args.args]
        defaults = fdef.args.defaults
        assigned = set(params)
        gdecl = set()
        for node in ast.walk(fdef):
            if isinstance(node, ast.Global):
                gdecl.update(node.names)
            elif isinstance(node, (ast.Name,)) and isinstance(node.ctx, ast.Store):
                assigned.add(node.id)
            elif isinstance(node, ast.FunctionDef) and node is not fdef:
                assigned.add(node.name)
        ctx = Ctx("func", assigned, gdecl)
        body = []
        nd = len(defaults)
        for i, p in enumerate(params):
            di = i - (len(params) - nd)
            dflt = self.expr(defaults[di], ctx) if di >= 0 else "V::none()"
            body.append("    V L_%s = A.get(%d, SY(%s), %s);" % (p, i, json.dumps(p, ensure_ascii=False), "&py_none_v" if dflt == "V::none()" and di >= 0 else ("nullptr" if di < 0 else "&dflt%d_" % i)))
            if di >= 0 and dflt != "V::none()": body.insert(len(body) - 1, "    static const V dflt%d_ = %s;" % (i, dflt))
        for n in sorted(assigned - set(params) - gdecl):
            body.append("    V L_%s;" % n)
        body += self.block(fdef.body, ctx, "    ")
        body.append("    return V::none();")
        self.funcs_out.append("V fn_%s(Match& G, const Args& A) {\n%s\n}\n" % (fdef.name, "\n".join(body)))


def main():
    out = Path(sys.argv[1])
    unit = sys.argv[2]
    tr = Translator()
    pieces = []
    registrations = []
    for spec in sys.argv[3:]:
        src, kind, cname = spec.rsplit(":", 2)
        text = Path(src).read_text(encoding="utf-8")
        lines = text.splitlines()   # keep header comments so AST line numbers equal file line numbers
        tree = ast.parse("\n".join(lines))
        if kind == "region":
            ctx = Ctx("region")
            tr.region = cname[len("region_"):] if cname.startswith("region_") else cname
            if tr.region.endswith("_scripted"):tr.region = tr.region[:-len("_scripted")]   # same call sites / f_code identity
            body = tr.block(tree.body, ctx, "    ")
            pieces.append("void %s(Match& G) {\n%s\n}\n" % (cname, "\n".join(body)))
        elif kind == "funcs":
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    tr.function(node)
                    registrations.append(node.name)
    tr.globals_used.update(registrations)
    header = ["// Generated by tools/py2cpp.py from the decompiled original game. Do not edit by hand;",
              "// fix the translator or override the function in hand-written code instead.",
              '#include "sim/pyrt.h"', "", "namespace pvz {", ""]
    fwd = [re.match(r"V (fn_\S+)\(", f).group(1) for f in tr.funcs_out]
    header += ["V %s(Match& G, const Args& A);" % f for f in fwd] + [""]
    reg = []
    if registrations:
        reg.append("void register_%s(Match& G) {" % unit)
        for n in registrations:
            reg.append("    G.%s = V::func([&G](const Args& A) -> V { return fn_%s(G, A); });" % (n, n))
        reg.append("}")
    text = "\n".join(header) + "\n" + "\n".join(tr.funcs_out) + "\n" + "\n".join(pieces) + "\n" + "\n".join(reg) + "\n}  // namespace pvz\n"
    out.write_text(text, encoding="utf-8")
    gfile = out.with_suffix(".globals.txt")
    gfile.write_text("\n".join(sorted(tr.globals_used)) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print("%s: %d functions, %d regions, %d globals, %d problems" % (out.name, len(tr.funcs_out), len(pieces), len(tr.globals_used), len(tr.problems)))
    from collections import Counter
    for p, n in Counter(tr.problems).most_common(20):
        print("   problem x%d: %s" % (n, p))


if __name__ == "__main__":
    main()
