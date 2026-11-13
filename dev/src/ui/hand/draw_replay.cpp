// Replay of the simulation's recorded original draw frames ("native-draw-v1") onto the UI screen.
#include "ui/hand/texture_pack.h"
// Port of native_animation.DrawReplay plus world_view's asset resolution: recipes name baked atlas
// images (tools/bake_atlas.py) instead of re-running the original asset loader in a second runtime.
#include "pg/pg.h"
#include "sim/pvp/pvprt.h"
#include "sim/pvp/hand/graphics.h"
#include "ui/gen/pm_world_view.h"
#include "sim/pvp/gen/pm_native_animation.h"
#include "sim/pvp/gen/pm_native_runtime.h"
#include "sim/pvp/gen/pm_native_scale.h"
#include "sim/pvp/shim/pm_native_assets.h"
#include "core/resource_paths.h"
#include "core/fsutil.h"
#include <list>
#include <unordered_map>

namespace pvz::pg {
void register_pixel_graphics_hooks();
V exchange_transform_metrics(const V&);
namespace {

V pgmod() { static V m = py::stdlib_module(V("pygame")); return m; }
V tmod() { static V m = pvz::getattr(pgmod(), Sym("transform")); return m; }
V dmod() { static V m = pvz::getattr(pgmod(), Sym("draw")); return m; }
const V& get(const V& d, const char* k) { static const V none = V::none(); const V* p = d.find(V(k)); return p && p->has() ? *p : none; }

std::string exe_dir() {
    V exe = py::stdlib_attr(V("sys"), V("executable"));
    std::string e = exe.t == V::STR ? exe.str() : std::string();
    size_t s = e.find_last_of("/\\");
    return s == std::string::npos ? std::string(".") : e.substr(0, s);
}

// recipe asset key -> real Surface (baked PNG at its recorded size), cached for the process
V resolve_asset(const std::string& key) {
    static std::unordered_map<std::string, V> cache;
    auto it = cache.find(key);
    if (it != cache.end()) return it->second;
    static const std::pair<const char*, const char*> prefixes[] = {{"world:", "图集"}, {"ui:", "ui图集"}, {"bg:", "背景图集"}, {"near:", "近景图集"}};
    V out = V::none();
    if (key.rfind("world:@load/", 0) == 0) {   // original lazy load: 图片/<name> scaled to WxH
        std::string rest = key.substr(12);
        size_t slash = rest.rfind('/');
        if (slash != std::string::npos) {
            std::string name = rest.substr(0, slash), size = rest.substr(slash + 1);
            size_t x = size.find('x');
            if (x != std::string::npos && name.find("..") == std::string::npos) {
                int w = std::stoi(size.substr(0, x)), h = std::stoi(size.substr(x + 1));
                V img = callm(pvz::getattr(pgmod(), Sym("image")), Sym("load"), Args{V(p8(native_image_directory().parent_path() / u8p(name)))});
                out = callm(callm(tmod(), Sym("scale"), Args{img, V::tuple({V(double(w)), V(double(h))})}), Sym("convert_alpha"), Args{});
            }
        }
    } else {
        for (auto& [p, atlas] : prefixes) {
            size_t n = std::strlen(p);
            if (key.compare(0, n, p) != 0) continue;
            std::string file = gfx::atlas_file(atlas, key.substr(n));
            if (!file.empty())
                out = callm(callm(pvz::getattr(pgmod(), Sym("image")), Sym("load"), Args{V(file)}), Sym("convert_alpha"), Args{});
            break;
        }
    }
    if (out.is_none()) throw PyError("NativeGraphicsError", "缺少原始动画资产：" + key.substr(0, 160));
    cache[key] = out;
    return out;
}

// Materialization and the game renderer share the translated production replay class.
// No native result is used as a Python reference.
const bool registered_materializer = [] {
    register_pixel_graphics_hooks();
    py::register_native_hook("graphics.asset", [](const Args& a) { return resolve_asset(a.pos.at(0).str()); });
    py::register_native_hook("graphics.materialize_image", [](const Args& a) {
        texture74::OriginalScope texture74_original; // PvP74 never override authoritative pixels
        V metrics=a.pos.size()>1?a.pos[1]:V();
        struct RestoreScope {V previous;~RestoreScope(){exchange_transform_metrics(previous);}} scope{exchange_transform_metrics(metrics)};
        V replay = pm_native_animation::new_DrawReplay(Args{pgmod(), V::func([](const Args& args) { return resolve_asset(args.pos.at(0).str()); })});
        return callm(replay, Sym("surface"), Args{a.pos.at(0)});
    });
    return true;
}();
}  // namespace
}  // namespace pvz::pg

namespace pvz::pm_world_view {
V C_WorldView::m__ensure_native_replay(const Args& A) {
    V terrain=A.get(0,Sym("terrain"),nullptr,"_ensure_native_replay"),tile=A.get(1,Sym("tile"),nullptr,"_ensure_native_replay");
    if(a__native_replay.has() && !a__native_replay.is_none() && a__native_tile==tile)return a__native_replay;
    if(a__native_load_error.truthy())throw PyError("NativeGraphicsError",a__native_load_error.str());
    try {
        if(a_bridge.is_none() || !py::callable(pvz::getattr(a_bridge,Sym("combat_payload"),V::none())).truthy())throw PyError("NativeGraphicsError","Local native combat source and assets are unavailable");
        V payload=callm(a_bridge,Sym("combat_payload"),Args{}),root=payload.idx(0),source=payload.idx(1),assets=payload.idx(2);
        V runtime=pm_native_runtime::new_NativeRuntime(Args({root,terrain},{{Sym("seed"),V(0)},{Sym("pygame"),a_pg}}));
        V ns=pvz::getattr(runtime,Sym("g")),patch=pm_native_runtime::f_load_patch(Args{source});
        pm_native_assets::f_load_original_assets(Args{ns,root,assets,tile,patch});
        // The baked native atlas already includes the original expansion/content
        // installs. Reapplying the pixel mutators would transform those assets twice.
        pm_native_scale::f_install(Args{ns,a_pg});
        V graphics=pm_native_animation::new_NamespaceGraphics(Args{a_pg,tile});callm(graphics,Sym("install"),Args{ns,root});
        a__native_runtime=runtime;a__native_graphics=graphics;a__native_tile=tile;a__native_dynamic_loads=V(0);
        V cosmetic_resolver=pvz::getattr(self(),Sym("_native_asset"));cosmetic_resolver.box->fattrs.emplace_back(Sym("__texture74_display_resolver__"),V(true)); // PvP74
        a__native_replay=pm_native_animation::new_DrawReplay(Args({a_pg},{{Sym("asset_resolver"),cosmetic_resolver}}));
        return a__native_replay;
    }catch(const PyError& error){a__native_load_error=V(std::string(error.what()).substr(0,200));throw PyError("NativeGraphicsError",a__native_load_error.str());}
}

V C_WorldView::m__native_asset(const Args& A) {
    V L_key = A.get(0, SY("key"), nullptr, "_native_asset");
    V L_NativeGraphicsError;
    V L_h;
    V L_name;
    V L_normalized;
    V L_parts;
    V L_separator;
    V L_size;
    V L_source;
    V L_w;
    L_NativeGraphicsError = pvz::getattr(pm_native_animation::module_ns(), SY("NativeGraphicsError"));
    L_source = py::m_get(pvz::getattr(a__native_graphics, SY("sources")), L_key);
    if (!py_is(L_source, V::none())) {
        return L_source;
    }
    if ((!(V((isinstance(L_key, "str")))).truthy() || !(callm(L_key, SY("startswith"), Args{SV("world:@load/")})).truthy())) {
        py::raise((L_NativeGraphicsError).call(Args{(SV("缺少原始动画资产：") + py::slice(py::str(L_key), V::none(), V(160.0)))}));
    }
    { V ut1_ = py::as_seq(callm(py::slice(L_key, py::len(SV("world:@load/")), V::none()), SY("rpartition"), Args{SV("/")})); L_name = ut1_.idx(0); L_separator = ut1_.idx(1); L_size = ut1_.idx(2); } 
    L_normalized = callm(L_name, SY("replace"), Args{SV("\\"), SV("/")});
    L_parts = callm(L_normalized, SY("split"), Args{SV("/")});
    if ((!(L_separator).truthy() || !(L_name).truthy() || (py::len(L_name) > V(160.0)) || py::in(SV(":"), L_name) || ([&]() -> V { V L_p; { V it3_ = py::iter_list(L_parts); for (size_t i3_ = 0; i3_ < it3_.len(); ++i3_) { L_p = it3_.idx(int64_t(i3_)); if (py::in(L_p, V::tuple({SV(""), SV("."), SV("..")}))) return V(true); }}return V(false); }()).truthy() || (py::len(L_parts) > V(2.0)) || ((py::len(L_parts) == V(2.0)) && (rd(L_parts, V(0.0)) != SV("图片"))))) {
        py::raise((L_NativeGraphicsError).call(Args{SV("非法原始资产名称")}));
    }
    if(py::len(callm(L_size,SY("split"),Args{SV("x")}))!=V(2))throw PyError("NativeGraphicsError","Invalid original asset dimensions");
    try {
        { V ut5_ = py::as_seq([&]() -> V { V out_ = V::list(); V L_value; { V it4_ = py::iter_list(callm(L_size, SY("split"), Args{SV("x")})); for (size_t i4_ = 0; i4_ < it4_.len(); ++i4_) { L_value = it4_.idx(int64_t(i4_)); out_.append(py::int_(L_value)); }}return out_; }()); L_w = ut5_.idx(0); L_h = ut5_.idx(1); } 
    } catch (PyError& exc_) {
        if (exc_.matches("TypeError") || exc_.matches("ValueError")) {
            py::raise((L_NativeGraphicsError).call(Args{SV("非法原始资产尺寸")}));
        }
        else throw;
    }
    if ((!((V(0.0) < L_w) && (L_w <= V(8192.0))) || !((V(0.0) < L_h) && (L_h <= V(8192.0))) || ((L_w * L_h) > (V(4096.0) * V(4096.0))))) {
        py::raise((L_NativeGraphicsError).call(Args{SV("非法原始资产尺寸")}));
    }
    if ((a__native_dynamic_loads >= V(256.0))) {
        py::raise((L_NativeGraphicsError).call(Args{SV("原始动态资产数量超过限制")}));
    }
    (void)((rd(pvz::getattr(a__native_runtime, SY("g")), SV("加载图"))).call(Args{L_name, L_w, L_h}));
    L_source = py::m_get(pvz::getattr(a__native_graphics, SY("sources")), L_key);
    if (py_is(L_source, V::none())) {
        py::raise((L_NativeGraphicsError).call(Args{(SV("原始资产加载标识不一致：") + py::slice(L_key, V::none(), V(160.0)))}));
    }
    a__native_dynamic_loads = py::iadd(a__native_dynamic_loads, V(1.0));
    return L_source;
    return V::none();
}
}  // namespace pvz::pm_world_view
