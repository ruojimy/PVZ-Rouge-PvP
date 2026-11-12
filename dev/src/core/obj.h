// Obj: an original-game unit dictionary (zombie / plant / entity / Dave avatar).
// Known string keys are member slots (o->血量); other keys go to `extras`.
// Presence (`k in d`) is the slot's has(); `del d[k]` clears it. Iteration
// order is member order then extras (insertion order is not preserved).
#pragma once
#include "core/value.h"
#include "core/obj_fields.inc"
#include <vector>

namespace pvz {

struct Obj {
#define X(n) V n;
    OBJ_FIELDS(X)
#undef X
    std::vector<std::pair<V, V>> extras;
    // write interception (PvP HeroProxy, a dict subclass overriding __setitem__)
    struct Hook {
        virtual ~Hook() = default;
        virtual const char* type_name() const { return "dict"; }
        virtual bool set(Obj& self, const V& key, const V& value) = 0;
        virtual bool getattr(Obj& self, Sym name, V& out) { return false; }
        virtual bool call(Obj& self, const V& self_v, Sym name, const Args& a, V& out) { return false; }
    };
    std::shared_ptr<Hook> hook;

    V& slot(const V& key);                 // python d[key] as an lvalue (creates ABSENT slot)
    const V* find(const V& key) const;
    bool has(const V& key) const { const V* p = find(key); return p && p->has(); }
    V get(const V& key, V dflt = V::none()) const { const V* p = find(key); return (p && p->has()) ? *p : dflt; }
    void del(const V& key);
    size_t size() const;

    template <class F> void each(F&& f) const;   // f(V key, const V& value)
    std::string dump() const;
};

struct ObjKey { const char* name; V Obj::*member; };
const std::vector<ObjKey>& obj_keys();

template <class F> void Obj::each(F&& f) const {
    for (auto& k : obj_keys()) { const V& v = this->*(k.member); if (v.has()) f(V(k.name), v); }
    for (auto& p : extras) if (p.second.has()) f(p.first, p.second);
}

}  // namespace pvz
