#include "sim/pvp/gen/pm_pvp59_graves.h"
#include "sim/typed72_app/cold_export.h"
#include "pg/pg.h"
#include "sim/pvp/gen/pm_content_catalog.h"
#include "sim/pvp/gen/pm_expansion_catalog.h"
#include "sim/pvp/gen/pm_native_targets.h"
#include "sim/pvp/gen/pm_native_scale.h"
#include "sim/pvp/shim/pm_content_assets.h"
#include "sim/pvp/gen/pm_balance.h"
#include "sim/pvp/gen/pm_pvp56_plants_catalog.h"
#include <SDL.h>
#include <map>
namespace pvz::typed72app {
namespace {
using J=nlohmann::json;
J parsed(const V& v){std::string text=dump(v);try{return J::parse(text);}catch(...){return J(text.substr(0,200));}}
J describe(const V& image){return J::parse(dump(callm(image,Sym("describe"),Args{})));}
// Particle sampling reads sprite alpha, so these pixels feed the authoritative RNG.
std::vector<std::pair<std::string,ColdPixels>> atlas_pixels(const V& atlas){
    std::vector<std::pair<std::string,ColdPixels>> out;
    if(!atlas.is_dict())return out;
    for(const auto& [key,image]:py::items_vec(atlas)){
        V surface;
        try{surface=pvz::getattr(image,Sym("pixels"));}catch(const PyError&){continue;}
        const auto* s=pg::surf(surface);ColdPixels p;p.width=s->w();p.height=s->h();p.rgba.reserve(size_t(p.width)*p.height);
        for(int y=0;y<p.height;++y)for(int x=0;x<p.width;++x){
            const auto* pixel=reinterpret_cast<const uint32_t*>(static_cast<const uint8_t*>(s->s->pixels)+size_t(y)*s->s->pitch)+x;
            uint8_t r,g,b,a;SDL_GetRGBA(*pixel,s->s->format,&r,&g,&b,&a);p.rgba.push_back({r,g,b,a});
        }
        out.emplace_back(key.str(),std::move(p));
    }
    return out;
}
J draw_atlas(const V& battle,const V& g){
    const V ns=pvz::getattr(pvz::getattr(battle,Sym("patch")),Sym("ns"));
    const V patch=py::m_get(ns,V("__pvz_sb_patch_plant_zombie_assets"));
    std::map<std::string,std::pair<J,J>> before;
    {const V atlas=py::m_get(g,V("图集"));if(atlas.is_dict())for(const auto& [key,image]:py::items_vec(atlas)){
        J d;try{d=describe(image);}catch(const PyError&){continue;}before[py_str(key)]={J::parse(dump(py::id(image))),d};}}
    if(!patch.is_none())(void)call(patch,Args{g});
    J out=J::object();
    for(const char* part:{"world","ui"}){
        const V atlas=py::m_get(g,V(std::string(part)=="world"?"图集":"ui图集"));J entries=J::object();
        // Keys naming one image object share it (set_alpha through either key affects both).
        if(atlas.is_dict())for(const auto& [key,image]:py::items_vec(atlas)){
            J d;try{d=describe(image);}catch(const PyError&){continue;}
            entries[py_str(key)]={{"id",J::parse(dump(py::id(image)))},{"describe",d}};
        }
        out[part]=entries;
    }
    J changed=J::object();
    {const V atlas=py::m_get(g,V("图集"));if(atlas.is_dict())for(const auto& [key,image]:py::items_vec(atlas)){
        const auto name=py_str(key);const auto found=before.find(name);
        if(found!=before.end()&&found->second.first==J::parse(dump(py::id(image))))continue;
        changed[name]=found==before.end()?J(nullptr):J{{"id",found->second.first},{"describe",found->second.second}};
    }}
    out["world_before"]=changed;
    return out;
}
}
ColdExport export_cold(const V& b,double seed){
    ColdExport e;const V g=pvz::getattr(b,Sym("g"));Match& G=match_of(g);
    J out;out["seed"]=seed;
    const auto attr=[&](const char* name){return parsed(pvz::getattr(b,Sym(name),V::none()));};
    for(const char* k:{"tile","width","height","dt","mode","seats","present","command","commands","sky_interval","sky_progress","native_secrets","team_secrets","bans","rules","_multi_plant","_multi_target","team_mode","scripted","ids","terrain_revision"})out["battle"][k]=attr(k);
    // The original cold budget resolves director precedence, Python int conversion
    // and the 1..200 clamp. Admit that effective value once; population changes
    // are only accepted by Room in config, before this session is constructed.
    {const V budget=pvz::getattr(b,Sym("scripted_spawn_budget"),V::none());
     if(!budget.is_none())out["scripted_spawn_limit"]=parsed(pvz::getattr(budget,Sym("limit")));}
    // NativeBattle.map tiles as published so far (the _sync_terrain baseline of the typed public terrain).
    {const V map=pvz::getattr(b,Sym("map"),V::none());if(map.is_dict())out["battle"]["map_tiles"]=parsed(py::m_get(map,V("tiles")));
     // map.environment.zombie_points as rv_tactics18.pick_front reads them: p[0] for a
     // sequence, p.get('x') for a dict, None entries dropped (cold: static map facts).
     J points=J::array();
     if(map.is_dict()){const V env=py::m_get(map,V("environment"),V::dict());const V raw=env.is_dict()?py::m_get(env,V("zombie_points"),V::none()):V::none();
         if(raw.truthy())for(const auto& item:py::iter_list(raw).items()){
             const V x=item.is_list()?item.idx(0):item.is_dict()?py::m_get(item,V("x"),V::none()):V::none();
             if(!x.is_none())points.push_back(x.num());
         }}
     out["battle"]["ai_zombie_points"]=points;}
    out["avatars"]=attr("avatars");out["players"]=attr("players");
    J globals=J::object(),skipped=J::array();
#define X(n) {const V& value=G.n;if(value.has()){std::string text=dump(value);if(text.size()<400000)try{globals[#n]=J::parse(text);}catch(...){skipped.push_back(#n);}else skipped.push_back(#n);}}
    MATCH_GLOBALS(X)
#undef X
    for(const auto& [key,value]:G.extra_globals){std::string text=dump(value);std::string name=py_str(key);if(text.size()<400000)try{globals[name]=J::parse(text);}catch(...){skipped.push_back(name);}else skipped.push_back(name);}
    const auto names=[&](const V& v){J list=J::array();if(v.is_dict()){for(const auto& [key,value]:py::items_vec(v))list.push_back(py_str(key));}else for(const auto& item:py::iter_list(v).items())list.push_back(py_str(item));return list;};
    out["constants"]={{"content_plants",names(pm_content_catalog::PLANTS)},{"content_zombies",names(pm_content_catalog::ZOMBIES)},{"black_zombies",names(pm_expansion_catalog::BLACK_ZOMBIES)},
        {"black_bites",names(pm_native_targets::BLACK_BITE_VARIANTS)},{"air_plants",names(pm_pvp56_plants_catalog::AIR_PLANTS)},{"scale_factor",parsed(pm_native_scale::FACTOR)},{"rider_lift",parsed(pm_native_scale::LIFT)},{"gold_magnet_bucket_hp",pm_balance::GOLD_MAGNET_BUCKET_HP.num()},
            // pvp59_graves rule constants, read from the module as GraveIdle does at run time
            // (a patched/rebalanced value reaches the typed GraveClock); inf travels as text.
            {"grave_idle",[]{J g=J::object();for(const char* k:{"GRAVE_IDLE_SECONDS","GRAVE_DOZE_SECONDS","DROWSY_RATE","SCARECROW_RADIUS"}){
                const double v=pvz::getattr(pm_pvp59_graves::module_ns(),Sym(k)).num();g[k]=std::isfinite(v)?J(v):J(v>0.?"inf":"-inf");}return g;}()}};
    // NativeContent.homing_aim_y uses both tables, with shrunk sizes taking precedence.
    pm_content_assets::init();pm_native_scale::init();
    J heights=parsed(pm_content_assets::SCALE_TILES);
    const J shrunk_heights=parsed(pm_native_scale::SCALE_TILES);
    for(const auto& [name,height]:shrunk_heights.items())heights[name]=height;
    out["constants"]["homing_height"]=std::move(heights);
    out["globals"]=globals;out["skipped_globals"]=skipped;
    // pvp64 plant_sink: ground gap measured from each plant's -帧0 PNG (cold, cached by V too).
    {J sinks=J::object();const V content=pvz::getattr(b,Sym("content"),V::none());
     const V p64=content.is_none()?V::none():pvz::getattr(content,Sym("pvp64"),V::none());
     if(!p64.is_none())for(const char* n:{"甜薯","豌豆迫击炮","弹簧草"}){try{sinks[n]=callm(p64,Sym("plant_sink"),Args{V(n)}).num();}catch(const PyError&){}}
     out["constants"]["pvp64_sinks"]=sinks;}
    // NativeBattle._unit_card_memo (sim_fastpath): entries formed during construction keep
    // the cost of their first resolution (an imitator's copy price); the typed memo is seeded.
    {J memo=J::array();const V m=pvz::getattr(b,Sym("_unit_card_memo"),V::none());
     if(m.is_dict())for(const auto& [k,v]:py::items_vec(m)){
         J entry={{"side",py_str(k.idx(0))},{"key",py_str(k.idx(1))},{"secrets",names(k.idx(2))},{"bans",names(k.idx(3))},{"night",k.idx(4).truthy()},{"cost",rd(v.idx(0),V("cost")).num()}};
         memo.push_back(std::move(entry));}
     out["unit_card_memo"]=memo;}
    const auto rng=[&](PyRandom& r){auto s=r.state();J w=J::array();for(const auto word:s.mt)w.push_back(word);return J{{"mt",w},{"mti",s.mti}};};
    e.atlas=atlas_pixels(G.find_global(V("图集"))?*G.find_global(V("图集")):V::dict());
    e.draw_atlas=draw_atlas(b,g);
    out["rng_room"]=rng(*py::random_of(pvz::getattr(b,Sym("rng"))));out["rng_match"]=rng(G.rng());
    // pve.WaveDirector.__init__+bind run inside NativeBattle construction: export what they leave.
    const V director=pvz::getattr(b,Sym("director"),V::none());
    if(!director.is_none()){
        const auto da=[&](const V& o,const char* n){return parsed(pvz::getattr(o,Sym(n),V::none()));};
        J d;for(const char* k:{"day","seed","coop","max_zombies","points","pool","plan","next_wave"})d[k]=da(director,k);
        d["rng"]=rng(*py::random_of(pvz::getattr(director,Sym("rng"))));
        const V cycle=pvz::getattr(director,Sym("cycle"),V::none());
        if(!cycle.is_none())d["cycle"]={{"initial_night",da(cycle,"initial_night")},{"phase",da(cycle,"phase")},{"rng",rng(*py::random_of(pvz::getattr(cycle,Sym("rng"))))}};
        out["director"]=d;
    }
    e.cold=std::move(out);
    return e;
}
} // namespace pvz::typed72app
