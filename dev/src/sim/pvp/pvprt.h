// Runtime used by translated PvP modules (tools/pvp2cpp.py output).
#pragma once
#include "sim/pyrt.h"
#if __has_include(<coroutine>)
#include <coroutine>
namespace pvz_co = std;
#else   // NDK 25 libc++ (clang 14): coroutines TS header
#include <experimental/coroutine>
namespace pvz_co = std::experimental;
#endif
#include <exception>
#include <functional>
#include <unordered_map>

#define PVZ_TODO(what) (::pvz::py::todo(what))

namespace pvz::py {

[[noreturn]] V todo(const char* what);

// ------------------------------------------------------------ iteration / sequences
V as_seq(const V& v);                 // sequence for tuple-unpacking (dict items, generators ...)
V list_it(const V& v);                // list(iterable)
V tuple_it(const V& v);
V set_it(const V& v);
V set_it();
inline V list_it() { return V::list(); }
inline V tuple_it() { return V::tuple({}); }
void set_add(V& s, const V& x);
V enumerate(const V& v);
V enumerate(const V& v, const V& start);
V zip(const V& a, const V& b);
V zip(const V& a, const V& b, const V& c);
V any(const V& v);
// x.get(k[, d]) / x.append(v) with plain dict / list / unit receivers inlined
inline V m_get(const V& o, const V& k, const V& d = V::none()) {
    if (o.t == V::DICT || (o.t == V::OBJ && !o.box->obj->hook)) { const V* r = o.find(k); return r && r->has() ? *r : d; }
    return callm(o, SY("get"), Args{k, d});
}
// x.get("字段"[, d]) where "字段" is a fixed unit member: direct slot read for plain units
inline V m_get_slot(const V& o, V Obj::* m, const V& k, const V& d = V::none()) {
    if (o.t == V::OBJ && !o.box->obj->hook) { const V& r = o.box->obj.get()->*m; return r.has() ? r : d; }
    return m_get(o, k, d);
}
inline V m_append(const V& o, const V& x) {
    if (o.t == V::LIST) { const_cast<V&>(o).box->items.push_back(x); return V::none(); }
    return callm(o, SY("append"), Args{x});
}
V all(const V& v);
V sum_it(const V& v);
V sum_it(const V& v, const V& start);
V next(const V& it);
V next(const V& it, const V& dflt);
V iter(const V& v);
V iter2(const V& fn, const V& sentinel);
// class statement inside a function: members are (name, value); function values are methods taking self
V local_class(const V& name, std::vector<std::pair<V, V>> members);                 // iter(callable, sentinel), collected eagerly
std::string cat_chunks(std::initializer_list<const char*> parts);   // long literals
V divmod(const V& a, const V& b);
V callable(const V& v);
V id(const V& v);
V type(const V& v);
inline V type(const V&, const V&, const V&) { throw PyError("NotImplementedError", "type(name, bases, dict)"); }
V repr(const V& v);
V invert(const V& v);
V bitop(const char* op, const V& a, const V& b);
V iadd(const V& a, const V& b);       // a += b with python list-extend-in-place semantics
V dict_of(const V& src);
V dict_of(const V& src, std::initializer_list<std::pair<V, V>> extra);
V dict_with_spread(std::initializer_list<std::pair<V, V>> kv);
const V& dict_spread_marker();
V filter(const V& f, const V& seq);
V map(const V& f, const V& seq);
V hash(const V& v);
V print(const Args& a);
V open_file(const Args& a);   // builtin open()
std::string bytes_data(const V& v);   // bytes / bytearray / list of ints -> raw bytes
V make_bytearray(const V& src);
V int_keyed(const V& d);       // JSON lost int dict keys (花费阳光 = {0: [...], 25: [...]}): "25" -> 25
V chr(const V& v);
V ord(const V& v);
V bytes_v(const char* hex);
V new_object();
void delattr(const V& o, Sym name);
V slice_step(const V& seq, const V& start, const V& stop, const V& step);

// star expressions
struct Piece { bool star; V v; };
inline Piece star(const V& v) { return {true, v}; }
inline Piece one(const V& v) { return {false, v}; }
V concat_star(std::initializer_list<Piece> parts);
Args star_args(std::initializer_list<V> pos, const V& star, std::initializer_list<std::pair<Sym, V>> kw, const V& kwstar);

// key functions for min/max/sorted
struct Key {
    V fn;
    Key() = default;
    explicit Key(V f) : fn(std::move(f)) {}
    V operator()(const V& x) const { return fn.has() ? fn.call(Args{x}) : x; }
};
inline Key keyfn(const V& f) { return Key(f); }
V max_it(const V& seq, const Key& key, const V& dflt);
V min_it(const V& seq, const Key& key, const V& dflt);
V sorted_it(const V& seq, const Key& key, bool reverse);
V sort_inplace(const V& seq, const Args& a);   // list.sort(key=, reverse=)

// strings
V percent(const V& fmt, const V& args);       // "fmt" % args
V format_spec(const V& v, const V& spec);     // f"{v:spec}" / format(v, spec)
V concat_str(std::initializer_list<V> parts);

// ------------------------------------------------------------ exceptions
V make_exc(const V& type, const Args& a, const char* bases);
[[noreturn]] void raise(const V& exc);
V exc_value(const PyError& e);
V exc_type(const V& name);

template <class F>
struct Finally {
    F f;
    bool active = true;
    ~Finally() noexcept(false) { if (active) f(); }
};
template <class F> Finally<F> finally(F f) { return Finally<F>{std::move(f)}; }

// ------------------------------------------------------------ generators (C++20 coroutines)
enum class GenKind { ITER, CONTEXT };
struct GenCtl {};
struct PyGen {
    struct promise_type {
        V current;
        std::exception_ptr exc;      // escaped from the body
        std::exception_ptr inject;   // thrown into the body at the current yield
        PyGen get_return_object() { return PyGen{pvz_co::coroutine_handle<promise_type>::from_promise(*this)}; }
        pvz_co::suspend_always initial_suspend() noexcept { return {}; }
        pvz_co::suspend_always final_suspend() noexcept { return {}; }
        struct YieldAwait {
            promise_type* p;
            bool await_ready() noexcept { return false; }
            void await_suspend(pvz_co::coroutine_handle<>) noexcept {}
            void await_resume() {
                if (p->inject) { auto e = p->inject; p->inject = nullptr; std::rethrow_exception(e); }
            }
        };
        YieldAwait yield_value(V v) { current = std::move(v); return YieldAwait{this}; }
        void return_void() {}
        void unhandled_exception() { exc = std::current_exception(); }
    };
    pvz_co::coroutine_handle<promise_type> h;
    PyGen() = default;
    explicit PyGen(pvz_co::coroutine_handle<promise_type> hh) : h(hh) {}
    PyGen(PyGen&& o) noexcept : h(o.h) { o.h = {}; }
    PyGen& operator=(PyGen&& o) noexcept { if (h) h.destroy(); h = o.h; o.h = {}; return *this; }
    PyGen(const PyGen&) = delete;
    ~PyGen() { if (h) h.destroy(); }
    // resume; returns true if a value was yielded
    bool step() {
        if (!h || h.done()) return false;
        h.resume();
        if (h.promise().exc) { auto e = h.promise().exc; h.promise().exc = nullptr; std::rethrow_exception(e); }
        return !h.done();
    }
};
V make_gen(GenKind kind, PyGen g, std::shared_ptr<PyObj> owner = nullptr);

// with-statement guard (context managers: generators, objects with __enter__/__exit__, nullcontext)
struct WithGuard {
    V mgr;
    V value;
    WithGuard(const V& m);
    ~WithGuard() noexcept(false);
};

// ------------------------------------------------------------ classes / modules / stdlib
V class_value(const V& name, Fn ctor);
V module_ns(const V& name);
void register_module_attrs(const char* name, V (*attrs)(Sym));   // generated module attribute table (module values)
void note_module_loaded(const char* qualname);                    // sys.modules bookkeeping
V& loaded_modules();                                              // the sys.modules dict
V import_pvp_module(const std::string& qualname);                 // importlib.import_module("pvp.x")
V stdlib(const V& name);
V stdlib_attr(const V& mod, const V& attr);
V stdlib_call(const V& name, const Args& a);
V builtin(const V& name);
V builtin_call(const V& name, const Args& a);
V type_method(const V& type, const V& method, const Args& a);
V isinstance_v(const V& o, const V& type);
template <class C>
V unbound(V (C::*m)(const Args&), const Args& a) {
    Args rest(std::vector<V>(a.pos.begin() + 1, a.pos.end()), a.kw);
    C* self = as<C>(a.pos.at(0));
    if (!self) throw PyError("TypeError", "unbound method called with wrong self");
    return (self->*m)(rest);
}

template <class C, class F>
V unbound_call(F f, const Args& a) {
    Args rest(std::vector<V>(a.pos.begin() + 1, a.pos.end()), a.kw);
    C* self = as<C>(a.pos.at(0));
    if (!self) throw PyError("TypeError", "unbound method called with wrong self");
    return f(self, rest);
}

// python random.Random instance (PyRandom wrapped as an object)
V make_random(int64_t seed);
V sha256_obj(const V& data);
inline V int_(const V& x, const V& base) { return V(double(std::stoll(x.str(), nullptr, int(base.num())))); }
using pvz::py::int_;
PyRandom* random_of(const V& v);

}  // namespace pvz::py

namespace pvz {
// The match namespace exposed to PvP code as a dict-like object (python `g`).
struct MatchNS : PyObj {
    Match* G = nullptr;
    // NativePhysics with a caller-owned dict: every write through this namespace is mirrored into that dict at
    // once (python writes the dict itself); names in mirror_hidden (native bookkeeping) are never mirrored
    V mirror, mirror_hidden;
    void mirror_key(const V& key);
    const char* type_name() const override { return "dict"; }
    bool isa(const char* c) const override { return std::string(c) == "dict" || std::string(c) == "object"; }
    V getitem(const V& key) override;
    void setitem(const V& key, const V& value) override;
    void delitem(const V& key) override;
    bool contains(const V& key) override;
    size_t length() override;
    V iterate() override;
    V method(Sym name) override;
    bool call_method(Sym name, const Args& a, V& out) override;
};
V match_ns(Match& G);
Match& match_of(const V& g);
}  // namespace pvz

namespace pvz {
// Namespace object of a dynamic module (python exec'd source globals, e.g. the 1.5.0.1 patch).
struct DynNS : PyObj {
    std::unordered_map<uint32_t, V> map;
    std::vector<Sym> order;
    const char* type_name() const override { return "dict"; }
    bool isa(const char* c) const override { return std::string(c) == "dict" || std::string(c) == "object"; }
    const V& get_(Sym name);                // NameError if missing
    // cached global slot: element addresses of the map stay valid across rehash; erase clears the cache
    std::vector<V*> gcache;
    const V& gslot_(size_t i, Sym name) {
        if (i < gcache.size()) { V* p = gcache[i]; if (p && p->has()) return *p; }
        auto it = map.find(name.id);
        if (it == map.end() || !it->second.has()) return get_(name);   // raises NameError
        if (i >= gcache.size()) gcache.resize(i + 1, nullptr);
        gcache[i] = &it->second;
        return it->second;
    }
    void set_(Sym name, const V& v);
    V getitem(const V& key) override;
    void setitem(const V& key, const V& value) override;
    void delitem(const V& key) override;
    bool contains(const V& key) override;
    size_t length() override { return map.size(); }
    V iterate() override;
    V method(Sym name) override;
    bool call_method(Sym name, const Args& a, V& out) override;
};
}  // namespace pvz
namespace pvz::py {
V noop_module(const V& name);                   // object whose every attribute is a no-op function
V stdlib_module(const V& name);
extern bool g_real_clock;   // time.* reads the wall clock (game) instead of 0 (oracle runs)
void register_module(const std::string& name, const V& module);   // native module for import / stdlib_call                 // module object for `import math` in dynamic modules
V data_value(const char* module, const char* key);   // exported PvP71 constant (data/<module>.json)
V atlas_image(const V& key);                    // image handle from the baked atlas
V atlas_ground_gap(const V& name);
V module_file(const V& module);
V path_new(const Args& a);                      // pathlib.Path(*parts)
// ---- sys._getframe(1) emulation: instrumented call sites push a frame for their direct callee
V call_site(const V& code, double lasti, const V& locals, const V& f, const Args& a);
V getframe();
// ---- hand-written replacements for bytecode-level tricks (registered in src/sim/pvp/hand)
V native_hook(const V& name, const Args& a);
void register_native_hook(const std::string& name, Fn fn);
bool has_native_hook(const std::string& name);
inline V with_globals(V f, const V& ns, const V& name) {
    f.box->fattrs.emplace_back(Sym("__globals__"), ns);
    f.box->fattrs.emplace_back(Sym("__name__"), name);
    f.box->fattrs.emplace_back(Sym("__code__"), V(Sym("patch:" + name.str())));
    return f;
}
V json_loads(const V& text);
}  // namespace pvz::py
