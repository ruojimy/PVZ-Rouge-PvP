#include "sim/pyrt.h"
#include "core/pyobj.h"
#include <unordered_map>

namespace pvz {

static const std::unordered_map<uint32_t, V Match::*>& match_index() {
    static const std::unordered_map<uint32_t, V Match::*> idx = [] {
        std::unordered_map<uint32_t, V Match::*> m;
#define X(n) m.emplace(Sym(#n).id, &Match::n);
        MATCH_GLOBALS(X)
#undef X
        return m;
    }();
    return idx;
}

V& Match::global(const V& name) {
    if (name.t == V::STR) {
        auto& idx = match_index();
        auto it = idx.find(name.sym().id);
        if (it != idx.end()) return this->*(it->second);
    }
    for (auto& p : extra_globals) if (py_eq(p.first, name)) return p.second;
    extra_globals.emplace_back(name, V());
    return extra_globals.back().second;
}

const V* Match::find_global(const V& name) const {
    if (name.t == V::STR) {
        auto& idx = match_index();
        auto it = idx.find(name.sym().id);
        if (it != idx.end()) return &(this->*(it->second));
    }
    for (auto& p : extra_globals) if (py_eq(p.first, name)) return &p.second;
    return nullptr;
}

const std::vector<std::pair<const char*, V Match::*>>& match_members() {
    static const std::vector<std::pair<const char*, V Match::*>> m = {
#define X(n) {#n, &Match::n},
        MATCH_GLOBALS(X)
#undef X
    };
    return m;
}

V Match::pygame_attr(const V& name) { return pvz::getattr(pygame, name.sym()); }

}  // namespace pvz
