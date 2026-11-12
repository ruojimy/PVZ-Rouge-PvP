// Runtime support for translated original-game code (tools/py2cpp.py output)
// and the hand-written PvP layer: the match namespace `Match` (python `g`).
#pragma once
#include "core/pyops.h"
#include "core/pyrandom.h"
#include "core/pyobj.h"
#include "sim/match_globals.inc"
#include <array>
#include <initializer_list>

namespace pvz {

// static string value per call site
#define SV(lit) ([]() -> const ::pvz::V& { static const ::pvz::V v_(lit); return v_; }())

struct Match {
#define X(n) V n;
    MATCH_GLOBALS(X)
#undef X
    PyRandom own_rng;
    PyRandom* rng_p = &own_rng;   // points into g["random"] (a random.Random object) once installed
    PyRandom& rng() { return *rng_p; }
    std::vector<std::pair<V, V>> extra_globals;   // names not in MATCH_GLOBALS

    V rng_randint(const V& a, const V& b) {
        return V(double(rng().randint(int64_t(a.num()), int64_t(b.num()))));
    }
    V rng_random() { return V(rng().random()); }
    V rng_uniform(const V& a, const V& b) { return V(rng().uniform(a.num(), b.num())); }
    V rng_choice(const V& seq) { return seq.idx(int64_t(rng().choice_index(seq.len()))); }
    V rng_shuffle(V& seq) {
        auto& it = seq.items();
        rng().shuffle(it.size(), [&](size_t i, size_t j) { std::swap(it[i], it[j]); });
        return V::none();
    }
    V pygame_attr(const V& name);

    // g[name] by string (hand-written PvP code / dynamic access)
    V& global(const V& name);
    template <class F> void each_present(F&& f) const;
    const V* find_global(const V& name) const;
    bool has_global(const V& name) const { const V* p = find_global(name); return p && p->has(); }
};

// ------------------------------------------------------------ subscripts
namespace py { const V& dict_missing(const V& d, const V& k); }   // Counter / defaultdict, else KeyError
inline const V& rd(const V& c, const V& k) {
    switch (c.t) {
        case V::LIST: case V::TUPLE: return c.idx(int64_t(k.num()));
        case V::DICT: case V::OBJ: {
            const V* p = c.find(k);
            if (!p || !p->has()) return py::dict_missing(c, k);
            return *p;
        }
        case V::INST: {
            thread_local V tmp_[8]; thread_local int ti_ = 0;
            V& slot = tmp_[(ti_++) & 7];
            slot = c.box->inst->getitem(k);
            return slot;
        }
        case V::STR: {
            thread_local V stmp_[8]; thread_local int si_ = 0;
            V& slot = stmp_[(si_++) & 7];
            slot = py::slice(c, k, V(k.num() == -1 ? V::none() : V(k.num() + 1)));
            return slot;
        }
        default: throw PyError("TypeError", "'" + c.type_name() + "' object is not subscriptable");
    }
}
inline const V& rd(const V& c, double k) { return c.idx(int64_t(k)); }
inline const V& rd(const V& c, int k) { return c.idx(int64_t(k)); }
inline V& wr(const V& c, const V& k) {
    switch (c.t) {
        case V::LIST: return const_cast<V&>(c).idx(int64_t(k.num()));
        case V::DICT: case V::OBJ: return const_cast<V&>(c).at(k);
        default: throw PyError("TypeError", "'" + c.type_name() + "' object does not support item assignment");
    }
}
inline V& wr(const V& c, double k) { return const_cast<V&>(c).idx(int64_t(k)); }
inline V& wr(const V& c, int k) { return const_cast<V&>(c).idx(int64_t(k)); }
// member fast path for literal string keys
inline const V& rdm(const V& c, V Obj::*m, const V& k) {
    if (c.t == V::OBJ) {
        const V& v = c.box->obj.get()->*m;
        if (!v.has()) throw PyError("KeyError", py_str(k));
        return v;
    }
    return rd(c, k);
}
// d["literal"] as an assignment target. A plain unit writes its member slot directly; a hooked unit (PvP
// HeroProxy, a dict subclass overriding __setitem__) must see every write, including `d[k] += x`, exactly as
// python routes d[k] = v / d[k] op= v through __setitem__.
inline void setm(const V& c, V Obj::*m, const V& k, const V& v);
struct MemberRef {
    const V& c; V Obj::*m; const V& k;
    bool hooked() const { return c.t == V::OBJ && c.box->obj->hook; }
    V& raw() const { return c.t == V::OBJ ? c.box->obj.get()->*m : wr(c, k); }
    template <class T> const MemberRef& operator=(T&& v) const {
        if (hooked()) setm(c, m, k, V(std::forward<T>(v))); else raw() = V(std::forward<T>(v));
        return *this;
    }
    const MemberRef& operator=(const MemberRef& o) const { return *this = V(o.raw()); }
    template <class T> const MemberRef& operator+=(T&& v) const {
        if (hooked()) { V cur = raw(); cur += V(std::forward<T>(v)); setm(c, m, k, cur); } else raw() += V(std::forward<T>(v));
        return *this;
    }
    template <class T> const MemberRef& operator-=(T&& v) const {
        if (hooked()) { V cur = raw(); cur -= V(std::forward<T>(v)); setm(c, m, k, cur); } else raw() -= V(std::forward<T>(v));
        return *this;
    }
    operator V&() const { return raw(); }
};
inline MemberRef wrm(const V& c, V Obj::*m, const V& k) { return MemberRef{c, m, k}; }
inline void py_del(const V& c, const V& k) {
    if (c.t == V::LIST) {
        auto& it = const_cast<V&>(c).items();
        int64_t i = int64_t(k.num()), n = int64_t(it.size());
        if (i < 0) i += n;
        if (i < 0 || i >= n) throw PyError("IndexError", "list assignment index out of range");
        it.erase(it.begin() + i);
        return;
    }
    if (c.t == V::DICT || c.t == V::OBJ) {
        if (!c.contains(k)) throw PyError("KeyError", py_str(k));
        const_cast<V&>(c).erase(k);
        return;
    }
    throw PyError("TypeError", "object doesn't support item deletion");
}

// ------------------------------------------------------------ calls
template <class... A>
inline V call(const V& f, A&&... args) {
    return f.call(Args{V(std::forward<A>(args))...});
}
inline V call(const V& f) { return f.call(Args{}); }
inline V call(const V& f, const Args& a) { return f.call(a); }
inline V call(const V& f, Args& a) { return f.call(a); }
inline V call(const V& f, Args&& a) { return f.call(a); }
inline const V py_none_v = V::none();

// attribute access on namespace-like values (dict / obj); python attr(x, name)
inline V attr(const V& o, const V& name) {
    if (o.t == V::DICT || o.t == V::OBJ) {
        const V* p = o.find(name);
        if (p && p->has()) return *p;
    }
    return pvz::getattr(o, name.sym());
}

// ------------------------------------------------------------ misc
inline V py_and(const V& a, const std::function<V()>& b) { return a.truthy() ? b() : a; }
inline V py_or(const V& a, const std::function<V()>& b) { return a.truthy() ? a : b(); }
inline bool py_is(const V& a, const V& b) {
    if (a.is_none() || b.is_none()) return a.is_none() && b.is_none();
    if (a.box || b.box) {
        if (a.box == b.box) return true;
        return a.t == V::INST && b.t == V::INST && a.box && b.box && a.box->inst.get() == b.box->inst.get();   // self() boxes afresh
    }
    if (a.t != b.t) return false;
    return a.t == V::BOOL ? a.b == b.b : a.t == V::STR ? str_eq(a, b) : a.n == b.n;
}
inline V py_dict(std::initializer_list<std::pair<V, V>> kv) {
    V d = V::dict();
    for (auto& p : kv) d.at(p.first) = p.second;
    return d;
}
inline V py_update(const V& d, const V& other) {
    if (other.is_obj()) other.o()->each([&](const V& k, const V& v) { const_cast<V&>(d).at(k) = v; });
    else for (auto& p : other.kv()) const_cast<V&>(d).at(p.first) = p.second;
    return V::none();
}

// periodic row (PvP PeriodicRow): list whose out-of-range index wraps
inline V periodic_list(V l) { l.box->periodic = true; return l; }

}  // namespace pvz

namespace pvz {
// ------------------------------------------------------------ writes (hook-aware)
void trace_key_write(const V& c, const V& k, const V& v);
inline void setm(const V& c, V Obj::*m, const V& k, const V& v) {
    trace_key_write(c, k, v);
    if (c.t == V::OBJ) {
        Obj* o = c.box->obj.get();
        if (o->hook && o->hook->set(*o, k, v)) return;
        o->*m = v;
        return;
    }
    if (c.t == V::INST) { c.box->inst->setitem(k, v); return; }
    wr(c, k) = v;
}
inline void setitem(const V& c, const V& k, const V& v) {
    trace_key_write(c, k, v);
    if (c.t == V::OBJ) {
        trace_key_write(c, k, v);
        Obj* o = c.box->obj.get();
        if (o->hook && o->hook->set(*o, k, v)) return;
        o->slot(k) = v;
        return;
    }
    if (c.t == V::INST) { c.box->inst->setitem(k, v); return; }
    wr(c, k) = v;
}
inline void delitem(const V& c, const V& k) {
    if (c.t == V::INST) { c.box->inst->delitem(k); return; }
    py_del(c, k);
}
}  // namespace pvz

namespace pvz::py {
// sys._getframe(1) emulation (defined in sim/pvp/pvprt.cpp)
V call_site(const V& code, double lasti, const V& locals, const V& f, const Args& a);
V getframe();
void push_region_frame(const V& code, const V& ns);
void pop_region_frame();
}  // namespace pvz::py
namespace pvz {
const std::vector<std::pair<const char*, V Match::*>>& match_members();
template <class F> void Match::each_present(F&& f) const {
    for (auto& m : match_members()) if ((this->*(m.second)).has()) f(V(m.first));
    for (auto& p : extra_globals) if (p.second.has()) f(p.first);
}
}  // namespace pvz
