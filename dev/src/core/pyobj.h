// Python class instances for the translated PvP layer.
//   * every translated class derives PyObj; declared attributes are V members
//     reachable through the generated virtual slot(); others go to `dyn`.
//   * methods are virtual C++ members; method(name) returns a bound V::func.
//   * getattr()/setattr()/callm() give python attribute semantics on any V.
#pragma once
#include "core/value.h"
#include <memory>
#include <algorithm>
#include <string>
#include <vector>

namespace pvz {

// Name -> case index for generated dispatch: interned symbol ids are small dense integers, so a flat
// array indexed by id is a single load. Names interned after the table was built are not members.
struct SymIndex {
    std::vector<int16_t> tab;
    SymIndex(std::initializer_list<Sym> names) {
        uint32_t mx = 0;
        for (Sym n : names) mx = std::max(mx, n.id);
        tab.assign(size_t(mx) + 1, int16_t(-1));
        int16_t k = 0;
        for (Sym n : names) { if (tab[n.id] < 0) tab[n.id] = k; ++k; }
    }
    int find(Sym n) const { return n.id < tab.size() ? tab[n.id] : -1; }
};

struct PyObj : std::enable_shared_from_this<PyObj> {
    std::vector<std::pair<Sym, V>> dyn;   // attributes not declared by the class
    virtual ~PyObj() = default;
    virtual const char* type_name() const { return "object"; }
    virtual bool isa(const char* cls) const { return std::string(cls) == "object"; }
    virtual V* slot(Sym) { return nullptr; }          // declared attribute storage
    virtual V method(Sym) { return V(); }             // bound method (ABSENT if none)
    // direct method call without creating a bound method object; false if no such method
    virtual bool call_method(Sym, const Args&, V&) { return false; }
    virtual V property(Sym, bool& found) { found = false; return V(); }
    virtual bool set_property(Sym, const V&) { return false; }
    virtual V call_self(const Args&);                 // __call__
    // mapping protocol for dict-like classes (__getitem__ ...)
    virtual V getitem(const V& key);
    virtual void setitem(const V& key, const V& value);
    virtual void delitem(const V& key);
    virtual bool contains(const V& key);
    virtual size_t length();
    virtual bool truth() { return true; }   // __bool__ / __len__ for native objects
    virtual V iterate();   // list of iteration items
    V self() { return V::inst(shared_from_this()); }

    V getattr(Sym name);
    bool hasattr(Sym name);
    void setattr(Sym name, V value);
    V* find_dyn(Sym name) { for (auto& p : dyn) if (p.first == name) return &p.second; return nullptr; }
};

// python getattr(o, name[, default]) / setattr / hasattr on any V
V getattr(const V& o, Sym name);
V getattr(const V& o, Sym name, const V& dflt);
void setattr(const V& o, Sym name, const V& value);
bool hasattr(const V& o, Sym name);

// o.name(*args) for any V: instance methods, builtin list/dict/str/set methods
V callm(const V& o, Sym name, const Args& a);

// isinstance(o, <type name>)
bool isinstance(const V& o, const char* type);

template <class T>
inline T* as(const V& v) { return v.t == V::INST ? dynamic_cast<T*>(v.box->inst.get()) : nullptr; }

template <class T, class... A>
inline V make_inst(A&&... a) {
    auto p = std::make_shared<T>();
    V self = V::inst(p);
    p->m___init__(Args(std::forward<A>(a)...));
    return self;
}

}  // namespace pvz
