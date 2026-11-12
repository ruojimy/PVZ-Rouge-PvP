// native_periodic_targets.PeriodicTargetsPy.begin / restore, hand-written (the Python build
// uses its C++ twin _pvpcore.PeriodicTargets for the same reason: it runs once per attack).
// Same float operations in the same order as the Python reference.
#include "sim/pvp/pvprt.h"
#include "sim/pvp/gen/pm_native_periodic_targets.h"
#include "core/pymath.h"
#include <cmath>

namespace pvz { namespace pm_native_periodic_targets {

V f_NativePeriodicTargets(const Args& A) {
    // This standalone build has no CPython _pvpcore extension to select.
    // Both implementations below are the existing C++ begin/restore methods;
    // constructing them directly avoids obsolete __code__ introspection.
    V battle = A.get(0, SY("battle"), nullptr, "NativePeriodicTargets");
    return new_PeriodicTargetsPy(Args{battle});
}

static inline double wrap_delta(double a, double b, double width) {
    return py::mod(b - a + width / 2., width) - width / 2.;
}

V C_PeriodicTargetsPy::m_begin(const Args& A) {
    V source = A.get(0, SY("source"), nullptr, "begin");
    if (!isinstance(source, "dict")) return V::none();
    if (callm(pvz::getattr(a_b, SY("targets")), SY("owner"), Args{source}) != SV("plant")) return V::none();
    double x;
    if (const V* c = source.find(SV("坐标")); c && c->has()) {
        x = (rd(*c, V(1.0)).num() + .5) * pvz::getattr(a_b, SY("tile")).num();
    } else if (source.find(SV("名")) && source.find(SV("名"))->has() && source.find(SV("位置")) && source.find(SV("位置"))->has()) {
        x = rd(*source.find(SV("位置")), V(0.0)).num();
    } else {
        return V::none();
    }
    a_active = V(true);
    V g = pvz::getattr(a_b, SY("g"));
    double width = pvz::getattr(a_b, SY("width")).num(), tile = pvz::getattr(a_b, SY("tile")).num();
    V zombies = rdm(g, &Obj::僵尸, SV("僵尸"));
    V zl = py::iter_list(zombies);
    for (size_t i = 0, n = zl.len(); i < n; ++i) {
        const V& target = zl.items()[i];
        V pos = py::m_get(target, SV("位置"));
        if (pos.t != V::LIST) continue;
        if (py::m_get(target, SV("血量"), V(0.0)) <= V(0.0)) continue;
        double p0 = rd(pos, V(0.0)).num();
        double nearest = x + wrap_delta(x, p0, width);
        if (std::fabs(nearest - p0) > width * .5) {
            py::m_append(a_shifted, V::tuple({target, pos}));
            pos.items()[0] = V(p0 + (nearest > p0 ? width : -width));
        }
    }
    double columns = double(py::to_int(width / tile)), origin = x / tile;
    auto column = [&](double col) {
        return col - origin < -columns / 2. ? col + columns : col - origin >= columns / 2. ? col - columns : col;
    };
    V rows = rd(g, SV("同横尸")), vertical = rd(g, SV("同竖尸"));
    auto row_items = py::items_vec(rows);
    bool moved = false;
    for (auto& kv : row_items) {
        V vals = py::iter_list(kv.second);
        for (auto& c : vals.items()) if (column(c.num()) != c.num()) { moved = true; break; }
        if (moved) break;
    }
    if (moved) {
        a_indexes = V::tuple({rows, vertical});
        V nr = V::dict();
        auto& nkv = nr.box->kv;
        nkv.reserve(row_items.size());
        for (auto& kv : row_items) {
            V vals = py::iter_list(kv.second);
            std::vector<V> out; out.reserve(vals.len());
            for (auto& c : vals.items()) out.emplace_back(column(c.num()));
            nkv.emplace_back(kv.first, V::list(std::move(out)));   // keys unique (copied from a dict)
        }
        pvz::setitem(g, SV("同横尸"), nr);
        // translated.setdefault(column(col), []).extend(values), insertion ordered
        V translated = V::dict();
        auto& tkv = translated.box->kv;
        std::vector<std::pair<double, size_t>> slots;
        for (auto& kv : py::items_vec(vertical)) {
            double c = column(kv.first.num());
            size_t at = SIZE_MAX;
            for (auto& sl : slots) if (sl.first == c) { at = sl.second; break; }
            if (at == SIZE_MAX) { at = tkv.size(); slots.push_back({c, at}); tkv.emplace_back(V(c), V::list()); }
            V src = py::iter_list(kv.second);
            auto& dst = tkv[at].second.box->items;
            dst.insert(dst.end(), src.items().begin(), src.items().end());
        }
        pvz::setitem(g, SV("同竖尸"), translated);
    }
    return V::none();
}

V C_PeriodicTargetsPy::m_restore(const Args&) {
    double width = 0;
    bool have_w = false;
    for (auto& pr : a_shifted.items()) {
        if (!have_w) { width = pvz::getattr(a_b, SY("width")).num(); have_w = true; }
        V target = pr.idx(0), orig = pr.idx(1);
        orig.items()[0] = V(py::mod(rd(orig, V(0.0)).num(), width));
        V cur = py::m_get(target, SV("位置"));
        if (cur.t == V::LIST && !py_is(cur, orig))
            cur.items()[0] = V(py::mod(rd(cur, V(0.0)).num(), width));
    }
    a_shifted.items().clear();
    if (!py_is(a_indexes, V::none())) {
        V g = pvz::getattr(a_b, SY("g"));
        pvz::setitem(g, SV("同横尸"), a_indexes.idx(0));
        pvz::setitem(g, SV("同竖尸"), a_indexes.idx(1));
        a_indexes = V::none();
    }
    a_active = V(false);
    return V::none();
}

}}  // namespace pvz::pm_native_periodic_targets
