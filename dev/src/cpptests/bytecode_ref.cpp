#include "sim/pvp/hand/original_namespace.h"
#include "core/fsutil.h"
// Test-only: original-bytecode REFERENCE replay for the translated old-suite tests (decision 2026-11-02).
//
// The old tests compare the product against windows of the ORIGINAL game bytecode executed by CPython. The
// native runtime cannot execute CPython bytecode, so:
//   * tools/bytecode_ref_capture.py runs the ORIGINAL test in CPython and records every top-level reference
//     invocation (exec of a code window / call of types.FunctionType(original code)) - see that file.
//   * here, marshal.loads parses the real pyc (so the test's own raw_window() runs natively on the real
//     co_code), and exec / reference-function calls REPLAY the recorded CPython effect, after verifying that
//     the native state handed to the reference equals what CPython saw (digest of the canonical state).
//   * the system under test (NativePhysics, NativeTargets, ...) is always the native product; its results are
//     compared by the test's original assertions against the replayed reference state.
// Fail closed: unknown test/sequence, different code window, different input, random-state consumption by
// the reference, non-data state changes, or an after-state that does not reproduce the reference -> error.
// Negative controls: PVZ_BYTECODE_REF_TAMPER=output perturbs the first replayed number (the test's
// assertions must then fail); =input corrupts the expected input digest (the replay must refuse).
// The canonical form MUST stay identical to tools/bytecode_ref_capture.py (documented there).
#include "cpptests/registry.h"
#include "sim/pvp/hand/native_marshal.h"
#include "pg/pg.h"
#include "sim/pyrt.h"
#include "sim/pvp/pvprt.h"
#include "sim/pvp/hand/runtime_probe.h"
#include "sim/pvp/gen/pm_native_physics.h"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <set>
#include <functional>
#include <sstream>
#include <unordered_map>
#include <unordered_set>

namespace pvz {
void region_unit_target_index(Match&);
void region_menu_callback(Match&);
void region_physics_hero_effects(Match&);void region_dave_draw(Match&);
void test_window_pea_collision(Match&); void test_window_chomper(Match&);
void test_window_cattail(Match&); void test_window_spike_tracking(Match&);
}
namespace pvz::cpptests {
namespace {
using json = nlohmann::json;

std::string g_test;   // module.Binding.test of the running test ("" outside a test body)
std::map<std::string, size_t> g_seq;
thread_local int g_compiled_reference_depth=0;

// ------------------------------------------------------------------ CPython 3.8 marshal (pyc payload)
std::string sha256hex(const std::string& data);
using OriginalWindowFn = void (*)(Match&);
struct CodeObj : PyObj {
    std::map<std::string, V> f;   // co_* fields
    std::string source_sha256;
    std::shared_ptr<CodeObj> origin;
    OriginalWindowFn native_window = nullptr;
    const char* type_name() const override { return "code"; }
    bool isa(const char* c) const override { return !strcmp(c, "CodeType") || !strcmp(c, "code") || !strcmp(c, "object"); }
    bool set_property(Sym, const V&) override { throw PyError("AttributeError", "code objects are immutable"); }
    V property(Sym n, bool& found) override {
        auto it = f.find(n.str());
        found = it != f.end();
        return found ? it->second : V();
    }
    V method(Sym n) override {
        if (n != Sym("replace")) return V();
        auto self = std::static_pointer_cast<CodeObj>(shared_from_this());
        return V::func([self](const Args& a) {
            auto c = std::make_shared<CodeObj>(); c->f = self->f;
            c->source_sha256 = self->source_sha256; c->origin = self->origin ? self->origin : self;
            for (auto& kw : a.kw) {
                if (!c->f.count(kw.first.str())) throw PyError("TypeError", "replace() got an unexpected keyword argument '" + kw.first.str() + "'");
                c->f[kw.first.str()] = kw.first == Sym("co_code") ? V::bytes(py::bytes_data(kw.second)) : kw.second;
            }
            return V::inst(c);
        });
    }
};

#include "cpptests/dis38.inc"
static const std::pair<const char*, int> k_opmap38[] = {
#include "cpptests/opmap38.inc"
};
template<size_t N> bool opcode_in(int op, const int (&values)[N]) {
    return std::find(std::begin(values), std::end(values), op) != std::end(values);
}
struct Instruction38 : PyObj {
    std::map<std::string, V> fields;
    const char* type_name() const override { return "Instruction"; }
    V property(Sym n, bool& found) override {
        auto i = fields.find(n.str()); found = i != fields.end();
        return found ? i->second : V();
    }
    V method(Sym n) override {
        if (n != Sym("_replace")) return V();
        auto self = std::static_pointer_cast<Instruction38>(shared_from_this());
        return V::func([self](const Args& a) {
            auto result = std::make_shared<Instruction38>(); result->fields = self->fields;
            for (auto& [key, value] : a.kw) {
                if (!result->fields.count(key.str())) throw PyError("ValueError", "Unknown Instruction field: " + key.str());
                result->fields[key.str()] = value;
            }
            return V::inst(result);
        });
    }
};
// Decode actual 3.8 wordcode, retaining EXTENDED_ARG instructions and byte-addressed jumps.
// This is inspection only; executing a code object still requires an independent reference capture.
V instructions38(const Args& a) {
    V code = a.get(0, Sym("x"), nullptr);
    if (!isinstance(code, "CodeType")) throw PyError("TypeError", "get_instructions requires a code object");
    std::string bytes = py::bytes_data(pvz::getattr(code, Sym("co_code")));
    if (bytes.size() % 2) throw PyError("ValueError", "Truncated Python 3.8 wordcode");
    std::map<size_t, int64_t> lines;
    int64_t line = int64_t(pvz::getattr(code, Sym("co_firstlineno")).num()), last_line = -1;
    size_t address = 0;
    std::string lnotab = py::bytes_data(pvz::getattr(code, Sym("co_lnotab")));
    for (size_t i = 0; i + 1 < lnotab.size(); i += 2) {
        unsigned delta = uint8_t(lnotab[i]);
        if (delta) {
            if (line != last_line) { lines[address] = line; last_line = line; }
            address += delta;
        }
        line += int8_t(lnotab[i + 1]);
    }
    if (line != last_line) lines[address] = line;
    V constants = pvz::getattr(code, Sym("co_consts")), names = pvz::getattr(code, Sym("co_names"));
    V locals = pvz::getattr(code, Sym("co_varnames"));
    V cells = py::iter_list(pvz::getattr(code, Sym("co_cellvars")));
    V frees = py::iter_list(pvz::getattr(code, Sym("co_freevars")));
    std::vector<V> free_names = cells.items();
    free_names.insert(free_names.end(), frees.items().begin(), frees.items().end());
    V freevars = V::tuple(free_names);
    std::string opnames[256];
    for (int i = 0; i < 256; ++i) opnames[i] = "<" + std::to_string(i) + ">";
    for (auto& [name, op] : k_opmap38) opnames[op] = name;
    std::vector<V> result; result.reserve(bytes.size() / 2);
    std::set<int64_t> labels;
    uint64_t extended = 0;
    for (size_t off = 0; off < bytes.size(); off += 2) {
        int op = uint8_t(bytes[off]);
        V arg = V::none(), value = V::none(); std::string representation;
        if (op >= k_have_argument) {
            uint64_t number = uint8_t(bytes[off + 1]) | extended;
            arg = value = V(double(number));
            extended = op == k_extended_arg ? number << 8 : 0;
            if (opcode_in(op, k_hasconst)) { value = constants.idx(int64_t(number)); representation = py::repr(value).str(); }
            else if (opcode_in(op, k_hasname)) { value = names.idx(int64_t(number)); representation = value.str(); }
            else if (opcode_in(op, k_haslocal)) { value = locals.idx(int64_t(number)); representation = value.str(); }
            else if (opcode_in(op, k_hasfree)) { value = freevars.idx(int64_t(number)); representation = value.str(); }
            else if (opcode_in(op, k_hascompare)) {
                if (number >= sizeof(k_cmp_op) / sizeof(*k_cmp_op)) throw PyError("IndexError", "Invalid COMPARE_OP argument");
                value = V(k_cmp_op[number]); representation = value.str();
            } else if (opcode_in(op, k_hasjrel) || opcode_in(op, k_hasjabs)) {
                int64_t target = int64_t(number) + (opcode_in(op, k_hasjrel) ? int64_t(off + 2) : 0);
                value = V(double(target)); labels.insert(target); representation = "to " + std::to_string(target);
            } else if (op == 155) {   // FORMAT_VALUE: conversion and format-spec flag
                V conversion = V::none();
                if ((number & 3) == 1) { conversion = py::stdlib_attr(V("builtins"), V("str")); representation = "str"; }
                if ((number & 3) == 2) { conversion = py::stdlib_attr(V("builtins"), V("repr")); representation = "repr"; }
                if ((number & 3) == 3) { conversion = py::stdlib_attr(V("builtins"), V("ascii")); representation = "ascii"; }
                value = V::tuple({conversion, V(bool(number & 4))});
                if (number & 4) representation += representation.empty() ? "with format" : ", with format";
            }
        } else extended = 0;
        auto ins = std::make_shared<Instruction38>();
        ins->fields = {{"opname", V(opnames[op])}, {"opcode", V(double(op))}, {"arg", arg}, {"argval", value},
                       {"argrepr", V(representation)}, {"offset", V(double(off))},
                       {"starts_line", lines.count(off) ? V(double(lines[off])) : V::none()}, {"is_jump_target", V(false)}};
        result.push_back(V::inst(ins));
    }
    for (auto& value : result) {
        auto* ins = as<Instruction38>(value);
        ins->fields["is_jump_target"] = V(labels.count(int64_t(ins->fields["offset"].num())) != 0);
    }
    return V::list(result);
}

struct Marshal {
    const std::string& b; size_t p = 0; std::vector<V> refs;
    std::string source_sha256;
    explicit Marshal(const std::string& data) : b(data), source_sha256(sha256hex(data)) {}
    uint8_t u8() { if (p >= b.size()) throw PyError("EOFError", "marshal data too short"); return uint8_t(b[p++]); }
    int32_t i32() { uint32_t v = 0; for (int i = 0; i < 4; ++i) v |= uint32_t(u8()) << (8 * i); return int32_t(v); }
    std::string raw(size_t n) { if (p + n > b.size()) throw PyError("EOFError", "marshal data too short"); std::string s = b.substr(p, n); p += n; return s; }
    V obj() {
        uint8_t code = u8(); bool flag = code & 0x80; code &= 0x7f;
        size_t slot = 0;
        auto reserve = [&] { if (flag) { slot = refs.size(); refs.push_back(V::none()); } };
        auto keep = [&](V v) { if (flag) refs[slot] = v; return v; };
        switch (code) {
            case 'N': return V::none();
            case 'F': return V(false);
            case 'T': return V(true);
            case '0': return V();
            case 'S': reserve(); return keep(V("StopIteration"));
            case '.': reserve(); return keep(V("Ellipsis"));
            case 'i': { reserve(); return keep(V(double(i32()))); }
            case 'l': {
                reserve(); int32_t n = i32(); double v = 0, scale = 1;
                for (int32_t i = 0; i < std::abs(n); ++i) { uint16_t d = uint16_t(u8()) | uint16_t(u8()) << 8; v += d * scale; scale *= 32768.0; }
                return keep(V(n < 0 ? -v : v));
            }
            case 'g': { reserve(); double d; std::string s = raw(8); memcpy(&d, s.data(), 8); return keep(V(d)); }
            case 'y': { reserve(); raw(16); return keep(py::new_object()); }   // complex: not used by the tests
            case 's': { reserve(); int32_t n = i32(); return keep(V::bytes(raw(size_t(n)))); }
            case 't': case 'u': case 'a': case 'A': { reserve(); int32_t n = i32(); return keep(V(raw(size_t(n)))); }
            case 'z': case 'Z': { reserve(); uint8_t n = u8(); return keep(V(raw(n))); }
            case ')': case '(': case '[': case '<': case '>': {
                reserve(); int32_t n = code == ')' ? u8() : i32();
                std::vector<V> items; items.reserve(size_t(n));
                if (code == ')' || code == '(') { V t = V::tuple({}); keep(t); }
                for (int32_t i = 0; i < n; ++i) items.push_back(obj());
                V out = code == '[' ? V::list(items) : (code == '<' || code == '>') ? py::set_it(V::list(items)) : V::tuple(items);
                return keep(out);
            }
            case '{': {
                reserve(); V d = V::dict(); keep(d);
                for (;;) { V k = obj(); if (!k.has()) break; V v = obj(); d.at(k) = v; }
                return d;
            }
            case 'r': { int32_t i = i32(); if (i < 0 || size_t(i) >= refs.size()) throw PyError("ValueError", "bad marshal data (invalid reference)"); return refs[size_t(i)]; }
            case 'c': {
                reserve(); auto c = std::make_shared<CodeObj>(); c->source_sha256 = source_sha256; V cv = V::inst(c); keep(cv);
                for (const char* k : {"co_argcount", "co_posonlyargcount", "co_kwonlyargcount", "co_nlocals", "co_stacksize", "co_flags"}) c->f[k] = V(double(i32()));
                for (const char* k : {"co_code", "co_consts", "co_names", "co_varnames", "co_freevars", "co_cellvars", "co_filename", "co_name"}) c->f[k] = obj();
                c->f["co_firstlineno"] = V(double(i32()));
                c->f["co_lnotab"] = obj();
                return cv;
            }
            default: throw PyError("ValueError", std::string("bad marshal data (unknown type code ") + std::to_string(int(code)) + ")");
        }
    }
};

OriginalWindowFn resolve_original_window(const V& value) {
    auto* code = as<CodeObj>(value);
    if (!code || !code->origin || code->source_sha256 != "6f10bada57913dd51bc4c87900d38ba875841d04febe3daafaeaa2d2f4cdf914" ||
        code->origin->f.at("co_name") != V("<module>"))
        throw PyError("NotImplementedError", "Native window fixture is not the pinned original code");
    if (code->native_window) return code->native_window;
    std::string bytes = py::bytes_data(code->f.at("co_code"));
    int64_t entry = 0; bool jump = false;
    for (size_t i = 0; i + 1 < bytes.size() && i < 8; i += 2) {
        int op = uint8_t(bytes[i]); entry = (entry << 8) | uint8_t(bytes[i + 1]);
        if (op == 144) continue;
        jump = op == 113; break;
    }
    // This original menu test has two independent return trampolines, rather
    // than slice_original's one end. Validate every field and all original
    // bytes before selecting the compiled callback; never trust entry alone.
    if(jump && entry==34910) {
        std::string expected=py::bytes_data(code->origin->f.at("co_code"));
        expected[0]=char(144);expected[1]=char(entry>>8);expected[2]=char(113);expected[3]=char(entry&255);
        const V& constants=code->origin->f.at("co_consts");size_t none=0;
        while(none<constants.len() && !constants.idx(int64_t(none)).is_none())++none;
        if(none==constants.len())throw PyError("RuntimeError","Original menu constant table has no None");
        const char stop[]={char(144),char(none>>8),char(100),char(none&255),char(83),char(0)};
        for(size_t offset:{size_t(36188),size_t(36234)})expected.replace(offset,6,stop,6);
        if(bytes!=expected)throw PyError("NotImplementedError","Original menu callback bytecode changed");
        for(const auto& [key,field]:code->origin->f)if(key!="co_code" && !py_eq(field,code->f.at(key)))throw PyError("NotImplementedError","Original menu callback differs in "+key);
        code->native_window=region_menu_callback;return region_menu_callback;
    }
    struct Window { int start, end; OriginalWindowFn run; };
    static const Window windows[] = {{98256, 98618, region_unit_target_index},
        {101746, 103540, test_window_pea_collision}, {133022, 134236, test_window_chomper},
        {130014, 130492, test_window_cattail}, {103540, 103934, test_window_spike_tracking},
        {65894,66870,region_physics_hero_effects},{66870,67400,region_dave_draw}};
    for (auto& window : windows) if (jump && entry == window.start) {
        V expected = pm_native_physics::f_slice_original(Args{V::inst(code->origin), V(window.start), V(window.end)});
        for (auto& [key, field] : as<CodeObj>(expected)->f) if (!py_eq(field, code->f.at(key)))
            throw PyError("NotImplementedError", "Native window fixture differs in " + key);
        code->native_window = window.run;
        return window.run;
    }
    throw PyError("NotImplementedError", "No compiled native stimulus for this original code window");
}

// ------------------------------------------------------------------ canonical form (== bytecode_ref_capture.py)
struct C {
    enum K { NUL, TRUE_, FALSE_, INT, STR, LIST } k = NUL;
    long long i = 0; std::string s; std::vector<C> l;
    static C str(std::string v) { C c; c.k = STR; c.s = std::move(v); return c; }
    static C list(std::vector<C> v) { C c; c.k = LIST; c.l = std::move(v); return c; }
    static C tag(const char* t) { return list({str(t)}); }
};
std::string jesc(const std::string& s) {
    std::string o = "\"";
    for (unsigned char ch : s) {
        switch (ch) {
            case '"': o += "\\\""; break; case '\\': o += "\\\\"; break; case '\n': o += "\\n"; break;
            case '\r': o += "\\r"; break; case '\t': o += "\\t"; break; case '\b': o += "\\b"; break; case '\f': o += "\\f"; break;
            default: if (ch < 0x20) { char b[8]; snprintf(b, sizeof b, "\\u%04x", ch); o += b; } else o += char(ch);
        }
    }
    return o + "\"";
}
std::string jtext(const C& c) {   // == json.dumps(c, ensure_ascii=False, separators=(",", ":"))
    switch (c.k) {
        case C::NUL: return "null"; case C::TRUE_: return "true"; case C::FALSE_: return "false";
        case C::INT: return std::to_string(c.i); case C::STR: return jesc(c.s);
        default: { std::string o = "["; for (size_t i = 0; i < c.l.size(); ++i) { if (i) o += ","; o += jtext(c.l[i]); } return o + "]"; }
    }
}
std::string ser(const C& c) {
    switch (c.k) {
        case C::NUL: return "N"; case C::TRUE_: return "T"; case C::FALSE_: return "F";
        case C::INT: return "i" + std::to_string(c.i);
        case C::STR: return "s" + std::to_string(c.s.size()) + ":" + c.s;
        default: { std::string o = "["; for (size_t i = 0; i < c.l.size(); ++i) { if (i) o += ","; o += ser(c.l[i]); } return o + "]"; }
    }
}
std::string hexs(const std::string& raw) { static const char* d = "0123456789abcdef"; std::string o; for (unsigned char ch : raw) { o += d[ch >> 4]; o += d[ch & 15]; } return o; }
std::string numtext(double x) { char b[64]; snprintf(b, sizeof b, "%.17g", x); return b; }
std::string sha256hex(const std::string& data) { return callm(py::stdlib_call(V("hashlib.sha256"), Args{V::bytes(data)}), Sym("hexdigest"), Args{}).str(); }

struct RefFunc;
struct Canon {
    std::unordered_map<const void*, long long> memo;
    V pressed;   // the state's pygame.key.get_pressed() result -> ["K"]
    std::string key(const V& k) { Canon fresh; return jtext(fresh.val(k)); }
    bool alias(const void* p, C& out) {
        auto it = memo.find(p);
        if (it != memo.end()) { C n; n.k = C::INT; n.i = it->second; out = C::list({C::str("@"), n}); return true; }
        memo.emplace(p, (long long)memo.size());
        return false;
    }
    C rows(std::vector<std::pair<V, V>> kv) {
        std::vector<std::pair<std::string, C>> r;
        for (auto& [k, v] : kv) {
            if (!v.has()) continue;
            std::string kt = key(k);
            if (k.t == V::STR && k.str() == "get_pressed" && (v.t == V::FUNC || v.is_inst())) {
                V held = v.call(Args{});
                std::vector<C> p;
                for (int i = 1; i <= 3; ++i) {
                    // native held keys are a {1,2,3 -> bool} dict (membership like python's _HeldKeys); else __getitem__
                    bool on;
                    if (held.t == V::DICT || held.t == V::OBJ) { const V* x = held.find(V(double(i))); on = x && x->truthy(); }
                    else on = callm(held, Sym("__getitem__"), Args{V(double(i))}).truthy();
                    C b; b.k = on ? C::TRUE_ : C::FALSE_; p.push_back(b);
                }
                r.emplace_back(kt, C::list({C::str("P"), C::list(p)}));
            } else r.emplace_back(kt, C());   // value filled below, in sorted order (memo order = python's)
        }
        std::vector<size_t> order(r.size());
        for (size_t i = 0; i < order.size(); ++i) order[i] = i;
        std::sort(order.begin(), order.end(), [&](size_t a, size_t b) { return r[a].first < r[b].first; });
        std::map<std::string, V> byk;
        for (auto& [k, v] : kv) if (v.has()) byk[key(k)] = v;
        std::vector<C> out;
        for (size_t i : order) {
            C v = r[i].second.k == C::LIST && !r[i].second.l.empty() && r[i].second.l[0].s == "P" ? r[i].second : val(byk[r[i].first]);
            out.push_back(C::list({C::str(r[i].first), v}));
        }
        return C::list({C::str("D"), C::list(out)});
    }
    C val(const V& v);
};
struct RefFunc : PyObj {
    V code, globals, name, native_implementation;
    bool native_reference=true;
    const char* type_name() const override { return "function"; }
    V property(Sym n, bool& found) override {
        found = true;
        if (n == Sym("__code__")) return code;
        if (n == Sym("__globals__")) return globals;
        if (n == Sym("__name__")) return name;
        found = false; return V();
    }
    V call_self(const Args& a) override;
};
C Canon::val(const V& v) {
    C c;
    if (pressed.has() && v.t == pressed.t && v.box && v.box.get() == pressed.box.get()) return C::tag("K");
    switch (v.t) {
        case V::ABSENT: case V::NONE: return c;
        case V::BOOL: c.k = v.b ? C::TRUE_ : C::FALSE_; return c;
        case V::NUM: return C::list({C::str("n"), C::str(numtext(v.n))});
        case V::STR: return v.byt ? C::list({C::str("b"), C::str(hexs(v.str()))}) : C::list({C::str("s"), C::str(v.str())});
        case V::TUPLE: { std::vector<C> l; for (auto& x : v.box->items) l.push_back(val(x)); return C::list({C::str("T"), C::list(l)}); }
        case V::LIST: { if (alias(v.box.get(), c)) return c; std::vector<C> l; for (auto& x : v.box->items) l.push_back(val(x)); return C::list({C::str("L"), C::list(l)}); }
        case V::SET: {
            if (alias(v.box.get(), c)) return c;
            std::vector<C> l; for (auto& x : v.box->items) l.push_back(val(x));
            std::sort(l.begin(), l.end(), [](const C& a, const C& b) { return jtext(a) < jtext(b); });
            return C::list({C::str("S"), C::list(l)});
        }
        case V::DICT: { if (alias(v.box.get(), c)) return c; return rows(v.kv()); }
        case V::OBJ: {
            if (alias(v.box.get(), c)) return c;
            std::vector<std::pair<V, V>> kv; v.box->obj->each([&](const V& k, const V& x) { kv.emplace_back(k, x); });
            return rows(kv);
        }
        case V::FUNC: return C::tag("f");
        case V::INST: {
            PyObj* p = v.box->inst.get();
            std::string tn = p->type_name();
            if (tn == "module") return C::tag("m");
            if (tn == "bytearray") { if (alias(p, c)) return c; return C::list({C::str("ba"), C::str(hexs(py::bytes_data(v)))}); }
            if (dynamic_cast<RefFunc*>(p)) return C::tag("f");
            return C::list({C::str("o"), C::str(tn)});
        }
    }
    return c;
}
bool is_data(const C& c) { return !(c.k == C::LIST && !c.l.empty() && c.l[0].k == C::STR && (c.l[0].s == "f" || c.l[0].s == "m")); }

V decode_key(const std::string& kt);   // below (Decoder)
struct State {   // the reference's view: its globals plus call arguments
    V g; std::vector<V> args; std::vector<std::pair<Sym, V>> kw;
    std::vector<std::pair<std::string, V>> items() const {
        std::vector<std::pair<std::string, V>> out;
        Canon k;
        if (g.t == V::DICT) for (auto& [key, v] : g.kv()) { if (v.has() && !(key.t == V::STR && key.str() == "__builtins__")) out.emplace_back("g:" + k.key(key), v); }
        else if (g.t == V::OBJ) g.box->obj->each([&](const V& key, const V& v) { out.emplace_back("g:" + k.key(key), v); });
        else if (auto* ns = as<MatchNS>(g)) {
            V keys = ns->iterate();
            for (auto& key : keys.items()) if (key != V("__builtins__")) out.emplace_back("g:" + k.key(key), ns->getitem(key));
        }
        for (size_t i = 0; i < args.size(); ++i) out.emplace_back("a:" + std::to_string(i), args[i]);
        for (auto& [n, v] : kw) out.emplace_back("k:" + n.str(), v);
        std::sort(out.begin(), out.end(), [](auto& a, auto& b) { return a.first < b.first; });
        return out;
    }
    static const V* field(const V& d, const char* name) {
        if (auto* ns = as<MatchNS>(d)) return ns->G->find_global(V(name));
        if (auto* mod = as<pg::Module>(d)) for (auto& [key, value] : mod->attrs) if (key == Sym(name)) return &value;
        return (d.t == V::DICT || d.t == V::OBJ) ? d.find(V(name)) : nullptr;
    }
    V pressed() const {   // == bytecode_ref_capture.pressed_of
        const V* pg = field(g, "pygame"); if (!pg) return V();
        const V* key = field(*pg, "key"); if (!key) return V();
        const V* fn = field(*key, "get_pressed"); if (!fn || !(fn->t == V::FUNC || fn->is_inst())) return V();
        try { return fn->call(Args{}); } catch (const PyError&) { return V(); }
    }
    std::string digest() const {
        Canon c; c.pressed = pressed(); std::vector<C> full;
        for (auto& [k, v] : items()) full.push_back(C::list({C::str(k), c.val(v)}));
        return sha256hex(ser(C::list(full)));
    }
    std::map<std::string, std::string> key_digests() const {
        std::map<std::string, std::string> out;
        V p = pressed();
        for (auto& [k, v] : items()) { Canon c; c.pressed = p; out[k] = sha256hex(ser(c.val(v))).substr(0, 16); }
        return out;
    }
    V resolve(const json& path) const {   // ["@p", [entry, step...]] -> the existing native object
        std::string entry = path.at(0).get<std::string>();
        V cur; bool found = false;
        for (auto& [k, v] : items()) if (k == entry) { cur = v; found = true; break; }
        if (!found) throw PyError("RuntimeError", "bytecode reference: alias path entry missing natively: " + entry);
        for (size_t i = 1; i < path.size(); ++i) {
            const json& s = path[i];
            if (s.is_number_integer()) { if (cur.t != V::LIST || size_t(s.get<long long>()) >= cur.len()) throw PyError("RuntimeError", "bytecode reference: alias path index"); cur = cur.idx(s.get<long long>()); }
            else {
                V key = decode_key(s.get<std::string>());
                const V* nxt = (cur.t == V::DICT || cur.t == V::OBJ) ? cur.find(key) : nullptr;
                if (!nxt) throw PyError("RuntimeError", "bytecode reference: alias path key missing natively");
                cur = *nxt;
            }
        }
        return cur;
    }
};

// decode a recorded canonical value (standalone memo, same visit order as the capture)
struct Decoder {
    std::vector<V> memo;
    const State* st = nullptr;                // for ["K"] and ["@p", path]
    std::unordered_set<const void*> aliases;  // objects re-bound from the existing native state
    V key(const std::string& kt) { Decoder d; return d.val(json::parse(kt)); }
    V val(const json& j) {
        if (j.is_null()) return V::none();
        if (j.is_boolean()) return V(j.get<bool>());
        const std::string t = j.at(0).get<std::string>();
        if (t == "K") {
            V p = st ? st->pressed() : V();
            if (!p.has()) throw PyError("RuntimeError", "bytecode reference: recorded key-state object, but the native state has no pygame.key.get_pressed");
            if (p.box) aliases.insert(p.box.get());
            return p;
        }
        if (t == "@p") {
            if (!st) throw PyError("RuntimeError", "bytecode reference: alias path outside a state");
            V a = st->resolve(j.at(1));
            if (a.box) aliases.insert(a.box.get());
            return a;
        }
        if (t == "n") { std::string s = j.at(1).get<std::string>(); return V(s == "nan" ? NAN : s == "inf" ? INFINITY : s == "-inf" ? -INFINITY : std::stod(s)); }
        if (t == "s") return V(j.at(1).get<std::string>());
        if (t == "b" || t == "ba") {
            std::string h = j.at(1).get<std::string>(), raw;
            for (size_t i = 0; i + 1 < h.size(); i += 2) raw += char(std::stoi(h.substr(i, 2), nullptr, 16));
            if (t == "b") return V::bytes(raw);
            V out = py::make_bytearray(V::bytes(raw)); memo.push_back(out); return out;
        }
        if (t == "T") { std::vector<V> l; for (auto& x : j.at(1)) l.push_back(val(x)); return V::tuple(l); }
        if (t == "L") { V out = V::list({}); memo.push_back(out); for (auto& x : j.at(1)) out.append(val(x)); return out; }
        if (t == "S") { V out = py::set_it(); memo.push_back(out); for (auto& x : j.at(1)) callm(out, Sym("add"), Args{val(x)}); return out; }
        if (t == "D") { V out = V::dict(); memo.push_back(out); for (auto& row : j.at(1)) out.at(key(row.at(0).get<std::string>())) = val(row.at(1)); return out; }
        if (t == "@") { size_t i = j.at(1).get<size_t>(); if (i >= memo.size()) throw PyError("RuntimeError", "bytecode reference: bad alias"); return memo[i]; }
        throw PyError("NotImplementedError", "bytecode reference: recorded change has no native representation: " + j.dump().substr(0, 120));
    }
};

V decode_key(const std::string& kt) { Decoder d; return d.val(json::parse(kt)); }

bool container(const V& v) { return v.t == V::LIST || v.t == V::DICT || v.t == V::OBJ; }
const std::unordered_set<const void*>* g_aliases = nullptr;   // of the change being merged
bool rebound(const V& v) { return g_aliases && v.box && g_aliases->count(v.box.get()); }
void merge(V& dst, const V& src) {   // in place, keeping container identity like CPython's in-place mutation
    if (dst.t == V::LIST && src.t == V::LIST) {
        auto& d = dst.box->items; const auto& s = src.box->items;
        if (d.size() != s.size()) { d = s; return; }
        for (size_t i = 0; i < d.size(); ++i) { if (!rebound(s[i]) && container(d[i]) && container(s[i]) && d[i].t == s[i].t) merge(d[i], s[i]); else d[i] = s[i]; }
        return;
    }
    if ((dst.t == V::DICT || dst.t == V::OBJ) && src.t == V::DICT) {
        std::vector<V> drop;
        if (dst.t == V::DICT) { for (auto& [k, v] : dst.kv()) if (!src.find(k)) drop.push_back(k); }
        else dst.box->obj->each([&](const V& k, const V&) { if (!src.find(k)) drop.push_back(k); });
        for (auto& k : drop) py_del(dst, k);
        for (auto& [k, v] : src.kv()) {
            const V* cur = dst.find(k);
            if (!rebound(v) && cur && container(*cur) && container(v) && (cur->t == v.t || (cur->t == V::OBJ && v.t == V::DICT))) { V c = *cur; merge(c, v); }
            else pvz::setitem(dst, k, v);
        }
        return;
    }
    dst = src;
}

std::map<std::string, json>& refs() { static std::map<std::string, json> r; return r; }
const json& module_refs(const std::string& module) {
    auto it = refs().find(module);
    if (it != refs().end()) return it->second;
    const char* dir = std::getenv("PVZ_BYTECODE_REF_DIR");
    if (!dir) throw PyError("RuntimeError", "bytecode reference: PVZ_BYTECODE_REF_DIR not set (tools/run_cpp_suite.py sets it)");
    std::ifstream in(std::string(dir) + "/" + module + ".json", std::ios::binary);
    if (!in) throw PyError("NotImplementedError", "bytecode reference: no CPython capture for " + module + " (run tools/bytecode_ref_capture.py)");
    json doc = json::parse(in);
    // source fingerprints: the capture must come from exactly the pyc, original test source and capture tool
    // of this run (tools/run_cpp_suite.py writes the actual hashes); any mismatch or missing data fails closed
    const char* fp = std::getenv("PVZ_BYTECODE_REF_FINGERPRINTS");
    if (!fp) throw PyError("RuntimeError", "bytecode reference: PVZ_BYTECODE_REF_FINGERPRINTS not set (tools/run_cpp_suite.py sets it)");
    std::ifstream fin(fp, std::ios::binary);
    if (!fin) throw PyError("RuntimeError", std::string("bytecode reference: cannot read fingerprints ") + fp);
    json actual = json::parse(fin);
    auto require = [&](const std::string& field, const json& want) {
        if (!doc.contains(field) || !want.is_string() || doc[field] != want)
            throw PyError("RuntimeError", "bytecode reference: " + module + " " + field + " does not match this run (recorded " +
                          (doc.contains(field) ? doc[field].dump() : std::string("none")) + ", actual " + want.dump() + "); re-capture");
    };
    require("pyc_sha256", actual.value("pyc_sha256", json()));
    json owner=actual["modules"].value(module,json::object());
    if(module=="test_pvp_native_animation") {
        if(owner.value("capture_policy_id",std::string())!="native-assets-head-key-order-v1")throw PyError("RuntimeError","Unknown native asset capture policy owner");
        require("tool_sha256",owner.value("tool_sha256",json()));
        require("baseline_capture_tool_sha256",actual.value("tool_sha256",json()));
        for(const char* field:{"capture_policy_id","native_assets_source_sha256","capture_policy_ast_sha256"})require(field,owner.value(field,json()));
    }else require("tool_sha256", actual.value("tool_sha256", json()));
    require("test_source_sha256",owner.value("test_source_sha256",json()));
    return refs()[module] = std::move(doc);
}

// every captured invocation of a test must have been replayed (a native path that skips the reference
// comparisons cannot pass silently); "" when complete or when the module has no capture
std::string consumption_error(const std::string& id) {
    if (id.empty()) return "";
    std::string module = id.substr(0, id.find('.'));
    const char* dir = std::getenv("PVZ_BYTECODE_REF_DIR");
    if (!dir) return "";
    if (!refs().count(module)) {
        std::ifstream probe(std::string(dir) + "/" + module + ".json", std::ios::binary);
        if (!probe) return "";
        try { module_refs(module); } catch (const PyError& e) { return e.what(); }
    }
    const json& cases = refs()[module].at("cases");
    if (!cases.contains(id)) return "";
    size_t want = cases.at(id).size(), got = g_seq.count(id) ? g_seq[id] : 0;
    if (got == want) return "";
    return "bytecode reference: " + id + " replayed " + std::to_string(got) + " of " + std::to_string(want) + " CPython reference invocations";
}

void tamper_first_number(json& j, bool& done) {
    if (done) return;
    if (j.is_array() && j.size() == 2 && j[0].is_string() && j[0] == "n") { j[1] = numtext(std::stod(j[1].get<std::string>()) + 1.0); done = true; return; }
    if (j.is_array() || j.is_object()) for (auto& x : j) tamper_first_number(x, done);
}

V replay(const char* kind, const V& code, State st, OriginalWindowFn native_stimulus = nullptr, const std::function<V()>& native_call = {}) {
    if (g_test.empty()) throw PyError("NotImplementedError", "bytecode reference invoked outside a test body (setUpClass capture not supported)");
    std::string module = g_test.substr(0, g_test.find('.'));
    const json& doc = module_refs(module);
    const json& cases = doc.at("cases");
    if (!cases.contains(g_test)) throw PyError("RuntimeError", "bytecode reference: no captured invocations for " + g_test);
    size_t seq = g_seq[g_test]++;
    const json& list = cases.at(g_test);
    if (seq >= list.size()) throw PyError("RuntimeError", "bytecode reference: " + g_test + " made more reference invocations than CPython (" + std::to_string(list.size()) + ")");
    json rec = list.at(seq);
    std::string where = g_test + " #" + std::to_string(seq) + " (" + rec.value("co_name", std::string("?")) + ")";
    std::string sha = sha256hex(py::bytes_data(pvz::getattr(code, Sym("co_code"))));
    if (rec.at("kind") != kind || rec.at("code_sha256") != sha) throw PyError("RuntimeError", "bytecode reference: sequence differs at " + where + ": native ran another code window");
    std::string expect = rec.at("input_digest").get<std::string>();
    const char* tamper = std::getenv("PVZ_BYTECODE_REF_TAMPER");
    if (tamper && !strcmp(tamper, "native_input") && st.g.t == V::DICT)   // perturb product-derived state
        for (auto& [k, v] : st.g.kv()) if (v.t == V::NUM) { v = V(v.n + 1.0); break; }
    if (tamper && !strcmp(tamper, "input")) expect = "tampered-" + expect;
    std::string observed_input = st.digest();
    if (observed_input != expect) {
        if (const char* dump = std::getenv("PVZ_BYTECODE_REF_DUMP")) {
            Canon canon; canon.pressed = st.pressed(); std::vector<C> full;
            for (auto& [key, value] : st.items()) full.push_back(C::list({C::str(key), canon.val(value)}));
            std::ofstream(std::string(dump) + "/native-input.json", std::ios::binary) << jtext(C::list(full));
        }
        std::string diff;
        auto mine = st.key_digests();
        for (auto& [k, d] : rec.at("input_keys").items()) {
            auto m = mine.find(k);
            if (m == mine.end()) diff += " missing:" + k;
            else if (m->second != d.get<std::string>()) {
                std::string native;
                for (auto& [ik, iv] : st.items()) if (ik == k) { Canon c; native = jtext(c.val(iv)).substr(0, 160); }
                diff += " differs:" + k + " native=" + native;
            }
        }
        for (auto& [k, d] : mine) if (!rec.at("input_keys").contains(k)) diff += " extra:" + k;
        throw PyError("RuntimeError", "bytecode reference: native input differs from CPython at " + where + ":" + (diff.empty() ? std::string(" (aliasing only)") : diff.substr(0, 600)));
    }
    if (native_stimulus || native_call) {
        // A window executed in the product world is TEST INPUT, not the reference side.
        // Execute actual C++ and native callbacks, then compare with the independently captured Python
        // state. Never assign the recorded changes/results to this world. Native RNG executes normally.
        V computed=V::none();std::exception_ptr failure;std::string error_kind,error_message;
        try{if(native_call)computed=native_call();else native_stimulus(match_of(st.g));}
        catch(const PyError& error){failure=std::current_exception();error_kind=error.kind;error_message=error.what();std::string prefix=error_kind+": ";if(error_message.rfind(prefix,0)==0)error_message.erase(0,prefix.size());}
        if(rec.contains("exception")) {
            if(!failure || rec["exception"][0]!=error_kind || rec["exception"][1]!=error_message)throw PyError("AssertionError","native original invocation exception differs at "+where);
        }else if(failure)std::rethrow_exception(failure);
        if(rec.contains("result")){Canon canonical;json observed=json::parse(jtext(canonical.val(computed)));if(observed!=rec["result"])throw PyError("AssertionError","native original invocation return value differs at "+where);}

        std::string after = st.digest();
        if (after != rec.at("after_digest").get<std::string>()) {
            std::string diff; auto mine = st.key_digests();
            for (auto& [key, expected] : rec.at("after_keys").items()) {
                auto found = mine.find(key);
                if (found == mine.end()) diff += " missing:" + key;
                else if (found->second != expected.get<std::string>()) diff += " differs:" + key;
            }
            for (auto& [key, digest] : mine) if (!rec.at("after_keys").contains(key)) diff += " extra:" + key;
            throw PyError("AssertionError", "native original-window result differs from CPython at " + where + ":" + diff);
        }
        if (const char* audit = std::getenv("PVZ_BYTECODE_REF_AUDIT")) {
            std::ofstream output(audit, std::ios::binary | std::ios::app);
            output << json{{"test", g_test}, {"sequence", seq}, {"mode", "native_stimulus"}, {"code_sha256", sha},
                           {"input_digest", observed_input}, {"after_digest", after}}.dump() << "\n";
            if (!output) throw PyError("OSError", "Cannot write native stimulus audit");
        }
        if(failure)std::rethrow_exception(failure);return computed;
    }
    if (rec.value("rng", false)) throw PyError("NotImplementedError", "bytecode reference consumed random state at " + where + "; replay cannot reproduce it");
    if (!rec.at("nondata_changed").empty()) throw PyError("NotImplementedError", "bytecode reference changed non-data entries at " + where + ": " + rec.at("nondata_changed").dump().substr(0, 200));
    json changes = rec.at("changes");
    if (tamper && !strcmp(tamper, "output")) { bool done = false; tamper_first_number(changes, done); }
    // Apply in dependency order: an ["@p", [entry, ...]] alias into ANOTHER changed entry is resolved only after
    // that entry has been applied (cycles fail closed). Unchanged entries are the same before and after.
    std::map<std::string, std::set<std::string>> deps;
    std::function<void(const json&, std::set<std::string>&)> scan = [&](const json& j, std::set<std::string>& out) {
        if (j.is_array() && j.size() == 2 && j[0].is_string() && j[0] == "@p" && j[1].is_array() && !j[1].empty()) out.insert(j[1][0].get<std::string>());
        if (j.is_array()) for (auto& x : j) scan(x, out);
    };
    for (auto& [k, cj] : changes.items()) { std::set<std::string> s; scan(cj, s); s.erase(k); for (auto& e : s) if (changes.contains(e)) deps[k].insert(e); }
    std::vector<std::string> order; std::set<std::string> done;
    while (order.size() < changes.size()) {
        bool progress = false;
        for (auto& [k, cj] : changes.items()) {
            if (done.count(k)) continue;
            bool ready = true; for (auto& e : deps[k]) if (!done.count(e)) ready = false;
            if (ready) { order.push_back(k); done.insert(k); progress = true; }
        }
        if (!progress) throw PyError("RuntimeError", "bytecode reference: cyclic alias paths between changed entries at " + where);
    }
    for (auto& k : order) {
        Decoder d; d.st = &st; V nv = d.val(changes.at(k));
        g_aliases = &d.aliases;
        struct Reset { ~Reset() { g_aliases = nullptr; } } reset_;
        if (k.rfind("g:", 0) == 0) {
            V key = decode_key(k.substr(2));
            const V* cur = st.g.find(key);
            bool rebind = false;   // CPython bound this name to another object (not an in-place mutation)
            if (rec.contains("rebound")) for (auto& r : rec.at("rebound")) if (r.get<std::string>() == k) rebind = true;
            if (!rebind && !rebound(nv) && cur && container(*cur) && container(nv)) { V c = *cur; merge(c, nv); } else pvz::setitem(st.g, key, nv);
        } else if (k.rfind("a:", 0) == 0) {
            size_t i = std::stoul(k.substr(2));
            if (i >= st.args.size() || !container(st.args[i])) throw PyError("RuntimeError", "bytecode reference: cannot mutate argument " + k + " at " + where);
            merge(st.args[i], nv);
        } else throw PyError("NotImplementedError", "bytecode reference: keyword-argument mutation at " + where);
    }
    for (auto& k : rec.at("removed")) {
        std::string ks = k.get<std::string>();
        if (ks.rfind("g:", 0) != 0) throw PyError("NotImplementedError", "bytecode reference: removal of " + ks);
        Decoder d; py_del(st.g, d.key(ks.substr(2)));
    }
    std::string observed_after = st.digest();
    if (!(tamper && !strcmp(tamper, "output")) && observed_after != rec.at("after_digest").get<std::string>()) {
        std::string diff;
        if (rec.contains("after_keys")) {
            auto mine = st.key_digests();
            for (auto& [k, d] : rec.at("after_keys").items()) { auto m = mine.find(k); if (m == mine.end()) diff += " missing:" + k; else if (m->second != d.get<std::string>()) diff += " differs:" + k; }
            for (auto& [k, d] : mine) if (!rec.at("after_keys").contains(k)) diff += " extra:" + k;
        }
        if (const char* dump = std::getenv("PVZ_BYTECODE_REF_DUMP")) {   // diagnostics only
            Canon c; c.pressed = st.pressed(); std::vector<C> full;
            for (auto& [k, v] : st.items()) full.push_back(C::list({C::str(k), c.val(v)}));
            std::ofstream(std::string(dump) + "/native-after.json", std::ios::binary) << jtext(C::list(full));
        }
        throw PyError("RuntimeError", "bytecode reference: replayed state does not reproduce CPython's at " + where + ":" +
                      (diff.empty() ? std::string(" (aliasing between entries)") : diff.substr(0, 500)));
    }
    if (const char* audit = std::getenv("PVZ_BYTECODE_REF_AUDIT")) {
        std::ofstream output(audit, std::ios::binary | std::ios::app);
        output << json{{"test", g_test}, {"sequence", seq}, {"code_sha256", sha},
                       {"input_digest", observed_input}, {"after_digest", observed_after}}.dump() << "\n";
        if (!output) throw PyError("OSError", "Cannot write reference audit");
    }
    if (rec.contains("exception")) throw PyError(rec["exception"][0].get<std::string>(), rec["exception"][1].get<std::string>());
    if (rec.contains("result")) { Decoder d; return d.val(rec["result"]); }
    return V::none();
}

// A reference function called from INSIDE a native region (the test put it into a caller-owned world dict)
// must see that dict exactly as python's world dict is at that moment: flush the native world into it first
// and reload it afterwards (hooks provided by the product's NativePhysics dict mode; absent otherwise).
void world_hook(const char* name) {
    try { py::native_hook(V(name), Args{}); } catch (const PyError& e) { if (!e.matches("NotImplementedError")) throw; }
}
V RefFunc::call_self(const Args& a) {
    if(native_implementation.has()) {
        if(!native_reference) {
            V result=native_implementation.call(a);
            const char* negative=std::getenv("PVZ_NEGATIVE_CONTROL_NATIVE_ANIMATION");
            if(negative && std::string(negative)=="1" && name==V("显示植物") && g_test.rfind("test_pvp_native_animation.",0)==0) {
                V recorder=rd(globals,V("screen")),commands=pvz::getattr(recorder,Sym("commands"));
                if(commands.len()==0)throw PyError("RuntimeError","Native animation negative control has no computed commands");
                V position=py::m_get(commands.idx(0),V("pos"));
                if(!position.is_list() || position.len()!=2 || !position.idx(0).is_num())throw PyError("RuntimeError","Native animation negative control has no computed image position");
                V before=position.idx(0);position.idx(0)=before+V(1);
                printf("NATIVE_ANIMATION_NEGATIVE_CONTROL %s\n",json{{"test",g_test},{"before_x",before.num()},{"after_x",position.idx(0).num()},{"scope","actual computed native draw command; reference untouched"}}.dump().c_str());
            }
            return result;
        }
        if(g_test.empty() || g_compiled_reference_depth)return native_implementation.call(a);
        world_hook("native_world_flush");flush_active_compiled_original_namespace(globals);
        State st{globals,a.pos,a.kw};
        V result=replay("call",code,st,nullptr,[&]{
            ++g_compiled_reference_depth;struct Restore{~Restore(){--g_compiled_reference_depth;}} restore;
            V value=native_implementation.call(a);flush_active_compiled_original_namespace(globals);return value;
        });
        world_hook("native_world_reload");return result;
    }
    world_hook("native_world_flush");
    State st{globals, a.pos, a.kw};
    V out = replay("call", code, st);
    world_hook("native_world_reload");
    return out;
}

}  // namespace

void set_current_test(const std::string& id) { g_test = id; g_seq.erase(id); }
std::string reference_consumption_error(const std::string& id) { return consumption_error(id); }

void install_bytecode_ref() {
    py::register_native_hook("test.compiled_original.mark",[](const Args& a){mark_compiled_original_namespace(a.pos.at(0));return V::none();});
    py::register_native_hook("test.compiled_original.function",[](const Args& a){if(a.pos.size()<2)throw PyError("TypeError","Compiled source fixture needs code and globals");mark_compiled_original_namespace(a.pos.at(1));return py::stdlib_call(V("types.FunctionType"),a);});
    py::register_native_hook("test.animation.observe_pixels",[](const Args& a){
        const char* path=std::getenv("PVZ_ANIMATION_PIXELS_LOG");if(!path)return V::none();
        if(g_test.rfind("test_pvp_native_animation.",0)!=0)throw PyError("RuntimeError","Unexpected animation pixel observation owner");
        static std::map<std::string,size_t> sequences;
        const std::string raw=py::bytes_data(a.pos.at(1));
        V size=callm(a.pos.at(0),Sym("get_size"),Args{});
        std::ofstream output(u8p(path),std::ios::binary|std::ios::app);
        output<<json{{"test",g_test},{"sequence",sequences[g_test]++},{"size",{int(size.idx(0).num()),int(size.idx(1).num())}},{"bytes",raw.size()},{"rgba_sha256",sha256hex(raw)}}.dump()<<"\n";
        if(!output)throw PyError("OSError","Cannot write native animation pixel observations");return V::none();
    });

    py::register_native_hook("test.resolve_unit_target_index", [](const Args& a) {
        if (resolve_original_window(a.pos.at(0)) != region_unit_target_index)
            throw PyError("NotImplementedError", "Target index requires the pinned original indexing window");
        Match* world = &match_of(a.pos.at(1));
        return V::func([world](const Args&) { region_unit_target_index(*world); return V::none(); });
    });
    const char* negative_native = std::getenv("PVZ_NEGATIVE_CONTROL_NATIVE");
    if (negative_native && std::string(negative_native) == "1") {
        set_native_physics_result_probe([](const V& world, const V& region) {
            if (region != V("displacement")) return;
            Match& G = match_of(world);
            if (G.玩家位置.t == V::LIST && !G.玩家位置.box->items.empty())
                G.玩家位置.box->items[0] += V(0.25);   // alter only a computed native result
        });
    }
    V marshal = pg::new_module("marshal");
    pg::module_of(marshal)->fn("loads", [](const Args& a) { std::string data = py::bytes_data(a.pos.at(0)); Marshal m(data); return m.obj(); });
    pg::module_of(marshal)->fn("dumps", py::native_marshal_dumps);
    py::register_module("marshal", marshal);
    V dis = pg::new_module("dis");
    V opmap = V::dict();
    for (auto& [n, v] : k_opmap38) opmap.at(V(n)) = V(double(v));
    pg::module_of(dis)->add("opmap", opmap);
    auto classification = [&](const char* name, const auto& values) {
        std::vector<V> list; for (int op : values) list.push_back(V(double(op)));
        pg::module_of(dis)->add(name, V::list(list));
    };
    classification("hasconst", k_hasconst); classification("hasname", k_hasname);
    classification("hasjrel", k_hasjrel); classification("hasjabs", k_hasjabs);
    classification("haslocal", k_haslocal); classification("hascompare", k_hascompare); classification("hasfree", k_hasfree);
    pg::module_of(dis)->fn("get_instructions", instructions38);
    py::register_module("dis", dis);
    py::register_native_hook("test.dis38.report", [](const Args& a) {
        std::ifstream input(a.pos.at(0).str(), std::ios::binary);
        if (!input) throw PyError("OSError", "Cannot open wordcode input");
        std::ostringstream buffer; buffer << input.rdbuf(); std::string payload = buffer.str();
        Marshal parser(payload); V root = parser.obj();
        std::function<json(const V&)> value = [&](const V& v) -> json {
            if (v.is_none()) return nullptr;
            if (v.t == V::NUM) return v.num();
            if (v.t == V::BOOL) return v.truthy();
            if (v.t == V::STR) return v.str();
            if (isinstance(v, "CodeType")) return json{{"code", pvz::getattr(v, Sym("co_name")).str()}};
            if (v.is_list() || v.t == V::TUPLE) {
                json items = json::array(); for (auto& item : v.items()) items.push_back(value(item)); return items;
            }
            return json{{"other", true}};
        };
        json report = json::array();
        std::function<void(const V&, const std::string&)> visit = [&](const V& code, const std::string& path) {
            json instructions = json::array(); V decoded = instructions38(Args{code});
            for (auto& ins : decoded.items()) {
                json row;
                for (const char* field : {"offset", "opcode", "opname", "arg", "argval", "starts_line", "is_jump_target"})
                    row[field] = value(pvz::getattr(ins, Sym(field)));
                instructions.push_back(std::move(row));
            }
            report.push_back(json{{"path", path}, {"instructions", std::move(instructions)}});
            V constants = pvz::getattr(code, Sym("co_consts"));
            for (size_t i = 0; i < constants.len(); ++i)
                if (isinstance(constants.idx(int64_t(i)), "CodeType")) visit(constants.idx(int64_t(i)), path + "/" + std::to_string(i));
        };
        visit(root, "root");
        std::ofstream output(a.pos.at(1).str(), std::ios::binary); output << report.dump();
        if (!output) throw PyError("OSError", "Cannot write wordcode report");
        return V::none();
    });
    // types.FunctionType(code, globals, name=None, argdefs=None): a reference function; its calls are replayed
    // (argdefs only matter to CPython's execution, which the capture already performed)
    py::register_native_hook("types.FunctionType", [](const Args& a) -> V {
        auto f = std::make_shared<RefFunc>();
        f->code = a.pos.at(0); f->globals = a.pos.at(1);
        f->name = a.pos.size() > 2 && !a.pos[2].is_none() ? a.pos[2] : pvz::getattr(f->code, Sym("co_name"));
        if(is_compiled_original_namespace(f->globals)) {
            auto* source=as<CodeObj>(f->code);
            if(!source || source->origin || source->source_sha256!="6f10bada57913dd51bc4c87900d38ba875841d04febe3daafaeaa2d2f4cdf914" || source->f.at("co_freevars").len())throw PyError("RuntimeError","Compiled original fixture requires the unchanged pinned original function code");
            if(!a.kw.empty() || a.pos.size()>4)throw PyError("NotImplementedError","Compiled original fixture does not accept replacement capture cells");
            f->native_implementation=bind_compiled_original_function(f->globals,pvz::getattr(f->code,Sym("co_name")));
            V pg=py::m_get(f->globals,V("pygame"));f->native_reference=!pvz::hasattr(pg,Sym("g"));
        }

        return V::inst(f);
    });
    py::register_native_hook("exec", [](const Args& a) -> V {
        V code = a.pos.at(0);
        if (!code.is_inst() || !dynamic_cast<CodeObj*>(code.box->inst.get())) throw PyError("NotImplementedError", "exec of source text has no native equivalent");
        if (a.pos.size() < 2 || a.pos.size() > 2) throw PyError("NotImplementedError", "exec(code, globals) only");
        State st{a.pos[1], {}, {}};
        // Only this pinned real menu region may enter from an unmarked UI
        // dictionary. All other exec fixtures retain their existing route.
        auto* parsed=as<CodeObj>(code);
        if(st.g.is_dict() && !is_compiled_original_namespace(st.g) && parsed && parsed->origin && sha256hex(py::bytes_data(parsed->f.at("co_code")))=="e8102fe13b9db9ef4c9ac46e22ca4ca88c6c9f343d94e7a6806654638cfa536d") {
            if(resolve_original_window(code)!=region_menu_callback)throw PyError("RuntimeError","Wrong compiled menu callback");
            mark_compiled_original_namespace(st.g);
        }
        if(is_compiled_original_namespace(st.g)) {
            OriginalWindowFn run=resolve_original_window(code);
            return replay("exec",code,st,nullptr,[&]{++g_compiled_reference_depth;struct Restore{~Restore(){--g_compiled_reference_depth;}} restore;return invoke_compiled_original_namespace(st.g,[&](Match& world){run(world);return V::none();});});
        }
        return replay("exec", code, st, as<MatchNS>(st.g) ? resolve_original_window(code) : nullptr);
    });
}
}  // namespace pvz::cpptests
