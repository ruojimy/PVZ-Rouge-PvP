#include "core/obj.h"
#include <unordered_map>

namespace pvz {

const std::vector<ObjKey>& obj_keys() {
    static const std::vector<ObjKey> keys = {
#define X(n) {#n, &Obj::n},
        OBJ_FIELDS(X)
#undef X
    };
    return keys;
}

static const std::unordered_map<uint32_t, V Obj::*>& member_index() {
    static const std::unordered_map<uint32_t, V Obj::*> idx = [] {
        std::unordered_map<uint32_t, V Obj::*> m;
        for (auto& k : obj_keys()) m.emplace(Sym(k.name).id, k.member);
        return m;
    }();
    return idx;
}

V& Obj::slot(const V& key) {
    if (key.t == V::STR) {
        auto& idx = member_index();
        auto it = idx.find(key.sym().id);
        if (it != idx.end()) return this->*(it->second);
    }
    for (auto& p : extras) if (py_eq(p.first, key)) return p.second;
    extras.emplace_back(key, V());
    return extras.back().second;
}

const V* Obj::find(const V& key) const {
    if (key.t == V::STR) {
        auto& idx = member_index();
        auto it = idx.find(key.sym().id);
        if (it != idx.end()) return &(this->*(it->second));
    }
    for (auto& p : extras) if (py_eq(p.first, key)) return &p.second;
    return nullptr;
}

void Obj::del(const V& key) {
    if (key.t == V::STR) {
        auto& idx = member_index();
        auto it = idx.find(key.sym().id);
        if (it != idx.end()) { (this->*(it->second)).del(); return; }
    }
    for (size_t i = 0; i < extras.size(); ++i)
        if (py_eq(extras[i].first, key)) { extras.erase(extras.begin() + i); return; }
}

size_t Obj::size() const { size_t n = 0; each([&](const V&, const V&) { ++n; }); return n; }

std::string Obj::dump() const {
    std::string o = "{";
    bool first = true;
    each([&](const V& k, const V& v) {
        if (!first) o += ',';
        first = false;
        o += '"'; o += py_str(k); o += "\":"; o += pvz::dump(v);
    });
    return o + "}";
}

}  // namespace pvz
