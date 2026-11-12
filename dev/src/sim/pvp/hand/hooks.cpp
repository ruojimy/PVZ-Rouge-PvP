// Hand-written replacements for PvP code that rewrote bytecode or inspected frames
// (wired in through tools/pvp2cpp.py SOURCE_PATCHES -> __pvp_native__(name, ...)).
#include "sim/pvp/pvprt.h"
#include <cmath>

namespace pvz {
namespace {

double num(const V& v) { return v.num(); }

// native_content: 位移处理 with the barrel's 1.2 x 1.2 tile footprint (co_consts 1.5->1.2, .3->.6,
// .75->.6, .2->.01) and three extra middle samples injected after the sample list is built.
V barrel_displacement(Match* G, const Args& a) {
    V weizhi = a.pos.at(0);
    double daxiao = a.pos.size() > 1 ? a.pos[1].num() : 1.0;
    double bi = G->比.num(), plk = G->plk.num();
    std::vector<std::pair<double, double>> dian;
    double x0 = weizhi.idx(0).num(), y0 = weizhi.idx(1).num();
    if (daxiao == 0) {
        dian.push_back({x0, y0});
    } else {
        dian.push_back({x0 - bi * 0.6 * daxiao, y0 - bi * 1.2 * daxiao});
        dian.push_back({x0 - bi * 0.6 * daxiao, y0 - bi * 0.01});
        dian.push_back({x0 + bi * 0.6 * daxiao, y0 - bi * 1.2 * daxiao});
        dian.push_back({x0 + bi * 0.6 * daxiao, y0 - bi * 0.01});
        dian.push_back({x0 - bi * 0.6 * daxiao, y0 - bi * 0.6});
        dian.push_back({x0 + bi * 0.6 * daxiao, y0 - bi * 0.6});
    }
    // _pvp_barrel_samples (gate at offset 268): x, y = weizhi[:2]
    for (double h : {1.2, .6, .01}) dian.push_back({x0, y0 - bi * h});
    V& vx = wr(weizhi, 2);
    V& vy = wr(weizhi, 3);
    if (vx.num() < 0) { vx = V(vx.num() + plk * 2); if (vx.num() > 0) vx = V(0.0); }
    else if (vx.num() > 0) { vx = V(vx.num() - plk * 2); if (vx.num() < 0) vx = V(0.0); }
    vy = V(vy.num() + plk * 4);
    bool hk = true, sk = true;
    const V& kong = G->kong;
    auto solid = [&](int64_t yy, int64_t xx) {
        const V& cell = rd(rd(G->ditu, V(double(yy))), V(double(xx)));
        return !kong.contains(rd(cell, V("方块")));
    };
    auto open_top_out = [&](int64_t yy, int64_t xx) { return G->不封顶出界.call(Args{V(double(yy)), V(double(xx))}).truthy(); };
    for (auto& d : dian) {
        int64_t y = int64_t(py::floordiv(d.second, bi));
        int64_t x = int64_t(py::floordiv(d.first, bi));
        int64_t yy = int64_t(py::floordiv(d.second + vy.num(), bi));
        if (open_top_out(yy, x)) sk = false;
        else if (yy >= 0 && solid(yy, x)) sk = false;
        int64_t xx = int64_t(py::floordiv(d.first + vx.num(), bi));
        if (open_top_out(y, xx)) hk = false;
        else if (y >= 0 && solid(y, xx)) hk = false;
    }
    if (!(hk || sk)) {
        wr(weizhi, 1) = V(weizhi.idx(1).num() - plk * 20);
        wr(weizhi, 0) = V(weizhi.idx(0).num() - vx.num());
    }
    double tiao = 0;
    if (sk) wr(weizhi, 1) = V(weizhi.idx(1).num() + vy.num());
    else {
        tiao = 2;
        if (vy.num() > 0) {
            tiao = 1;
            vy = V(-std::fabs(vx.num()));
            if (vy.num() < -plk * 200) vy = V(-plk * 200);
        } else vy = V(0.0);
    }
    if (hk) wr(weizhi, 0) = V(weizhi.idx(0).num() + vx.num());
    else {
        if (!(sk || hk)) wr(weizhi, 0) = V(weizhi.idx(0).num() - vx.num());
        vx = V(0.0);
    }
    auto out = [&](double yy, double xx) {
        return G->出界.call(Args{V(double(int64_t(py::floordiv(yy, bi)))), V(double(int64_t(py::floordiv(xx, bi))))}).truthy();
    };
    if (out(weizhi.idx(1).num(), weizhi.idx(0).num() - daxiao * bi * 0.6)) wr(weizhi, 0) = V(weizhi.idx(0).num() + plk * 10);
    if (out(weizhi.idx(1).num(), weizhi.idx(0).num() + daxiao * bi * 0.6)) wr(weizhi, 0) = V(weizhi.idx(0).num() - plk * 10);
    return V(tiao);
}

// native_content ContentBaseDamage: the patch's BASE_DAMAGE table, whose get() returns 60 for a
// sweet-pepper projectile (the caller's local `entity`).
struct ContentBaseDamage : PyObj {
    V table;
    const char* type_name() const override { return "ContentBaseDamage"; }
    bool isa(const char* c) const override { return std::string(c) == "dict" || std::string(c) == "object"; }
    V getitem(const V& k) override { return rd(table, k); }
    void setitem(const V& k, const V& v) override { pvz::setitem(table, k, v); }
    bool contains(const V& k) override { return table.contains(k); }
    size_t length() override { return table.len(); }
    V iterate() override { return py::iter_list(table); }
    V method(Sym name) override {
        auto sp = std::static_pointer_cast<ContentBaseDamage>(shared_from_this());
        if (name == Sym("get")) return V::func([sp](const Args& a) {
            V frame = py::getframe();
            V e = rd(frame, V("f_locals")).get(V("entity"), V::none());
            if ((e.is_dict() || e.is_obj()) && e.get(V("_pvp_content"), V::none()) == V("甜椒投手")) return V(60.0);
            return sp->table.get(a.pos.at(0), a.pos.size() > 1 ? a.pos[1] : V::none());
        });
        V self_table = sp->table;
        return V::func([self_table, name](const Args& a) { return callm(self_table, name, a); });
    }
};

}  // namespace
void register_hand_hooks() {
    {
        py::register_native_hook("barrel_displacement", [](const Args& a) {
            Match* G = &match_of(a.pos.at(0));
            return V::func([G](const Args& b) { return barrel_displacement(G, b); });
        });
        py::register_native_hook("high_intercept_solver", [](const Args& a) {
            return rd(a.pos.at(0), V("__pvp_high_solve_intercept"));
        });
        py::register_native_hook("content_base_damage", [](const Args& a) {
            auto p = std::make_shared<ContentBaseDamage>();
            p->table = a.pos.at(0);
            return V::inst(p);
        });
    }
}
}  // namespace pvz

// scripted_spawn_budget.ScriptedSpawnBudget.install_native_guards: python injects four
// iteration gates into the zombies bytecode; the gated region is pre-translated
// (extract/live/zombies_scripted.py, tools/dump_live_scripted.py).
#include "sim/pvp/gen/pm_scripted_spawn_budget.h"
namespace pvz { V scripted_zombies_region(const V& g); }
namespace pvz::pm_scripted_spawn_budget {
V C_ScriptedSpawnBudget::m_install_native_guards(const Args&) {
    if (!a_enabled.truthy()) return V::none();
    V g = pvz::getattr(a_b, SY("g"));
    pvz::setitem(g, SV("_pvp_spawn_hold_dance"), pvz::getattr(self_v(), SY("_hold_dance")));
    pvz::setitem(g, SV("_pvp_spawn_defer_dancer"), pvz::getattr(self_v(), SY("_defer_dancer")));
    pvz::setitem(g, SV("_pvp_spawn_hold_sled"), pvz::getattr(self_v(), SY("_hold_sled")));
    pvz::setitem(g, SV("_pvp_spawn_hold_giant"), pvz::getattr(self_v(), SY("_hold_giant")));
    V regions = pvz::getattr(pvz::getattr(a_b, SY("engine")), SY("regions"));
    pvz::setitem(regions, SV("zombies"), scripted_zombies_region(g));
    return V::none();
}
}  // namespace pvz::pm_scripted_spawn_budget
