// Cold boundary only: construct the current 72 battle once and export its
// terrain, rules and setup globals as JSON. No simulation step ever runs here.
#include "sim/pvp/gen/pm_pvp59_graves.h"
#include "sim/pvp/pvprt.h"
#include "sim/pvp/battle_api.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "pg/pg.h"
#include "sim/pvp/hand/graphics.h"
#include "sim/pvp/gen/pm_content_catalog.h"
#include "sim/pvp/gen/pm_expansion_catalog.h"
#include "sim/pvp/gen/pm_native_targets.h"
#include "sim/pvp/gen/pm_native_scale.h"
#include "sim/pvp/gen/pm_balance.h"
#include "sim/pvp/gen/pm_pvp56_plants_catalog.h"
#include <cstdio>
#include <fstream>
#include <sstream>
using namespace pvz;
using J=nlohmann::json;
namespace {
// Particle sampling reads sprite alpha, so these pixels feed the authoritative RNG.
void write_atlas(const V& atlas,const std::string& path){
    std::ofstream o(u8p(path),std::ios::binary);uint32_t count=0;o.write(reinterpret_cast<const char*>(&count),4);
    for(const auto& [key,image]:py::items_vec(atlas)){
        V surface;
        try{surface=pvz::getattr(image,Sym("pixels"));}catch(const PyError&){continue;}
        const auto* s=pg::surf(surface);const uint32_t w=uint32_t(s->w()),h=uint32_t(s->h());const auto name=key.str();const uint32_t n=uint32_t(name.size());
        o.write(reinterpret_cast<const char*>(&n),4);o.write(name.data(),n);o.write(reinterpret_cast<const char*>(&w),4);o.write(reinterpret_cast<const char*>(&h),4);
        std::vector<uint8_t> rgba;rgba.reserve(size_t(w)*h*4);
        for(uint32_t y=0;y<h;++y)for(uint32_t x=0;x<w;++x){
            const auto* pixel=reinterpret_cast<const uint32_t*>(static_cast<const uint8_t*>(s->s->pixels)+size_t(y)*s->s->pitch)+x;
            uint8_t r,g,b,a;SDL_GetRGBA(*pixel,s->s->format,&r,&g,&b,&a);rgba.insert(rgba.end(),{r,g,b,a});
        }
        o.write(reinterpret_cast<const char*>(rgba.data()),std::streamsize(rgba.size()));++count;
    }
    o.seekp(0);o.write(reinterpret_cast<const char*>(&count),4);std::printf("atlas images %u\n",count);
    // Native frame recorder: describe() of each atlas image, its V replay recipe and metadata.
    std::ofstream r(u8p(path+".recipes.json"),std::ios::binary);r<<"{";bool first=true;
    for(const auto& [key,image]:py::items_vec(atlas)){
        V d;try{d=callm(image,Sym("describe"),Args{});}catch(const PyError&){continue;}
        r<<(first?"":",")<<dump(key)<<":"<<dump(d);first=false;
    }
    r<<"}";
}
void write_draw_atlas(const V& battle,const V& g,const std::string& path){
    const V ns=pvz::getattr(pvz::getattr(battle,Sym("patch")),Sym("ns"));
    const V patch=py::m_get(ns,V("__pvz_sb_patch_plant_zombie_assets"));
    // The installed art before the lazy patch: keys it replaces or adds are exported as
    // "world_before" ({id, describe} or null), applied until V's first patch call.
    std::map<std::string,std::pair<std::string,std::string>> before;
    {const V atlas=py::m_get(g,V("图集"));if(atlas.is_dict())for(const auto& [key,image]:py::items_vec(atlas)){
        V d;try{d=callm(image,Sym("describe"),Args{});}catch(const PyError&){continue;}before[py_str(key)]={dump(py::id(image)),dump(d)};}}
    if(!patch.is_none())(void)call(patch,Args{g});
    std::ofstream r(u8p(path),std::ios::binary);r<<"{";
    for(const char* part:{"world","ui"}){
        const V atlas=py::m_get(g,V(std::string(part)=="world"?"图集":"ui图集"));
        r<<(std::string(part)=="world"?"":",")<<"\""<<part<<"\":{";bool first=true;
        if(atlas.is_dict())for(const auto& [key,image]:py::items_vec(atlas)){
            V d;try{d=callm(image,Sym("describe"),Args{});}catch(const PyError&){continue;}
            // Keys naming one image object share it (set_alpha through either key affects both).
            r<<(first?"":",")<<dump(key)<<":{\"id\":"<<dump(py::id(image))<<",\"describe\":"<<dump(d)<<"}";first=false;
        }
        r<<"}";
    }
    r<<",\"world_before\":{";bool first=true;
    {const V atlas=py::m_get(g,V("图集"));if(atlas.is_dict())for(const auto& [key,image]:py::items_vec(atlas)){
        const auto name=py_str(key);const auto found=before.find(name);
        if(found!=before.end()&&found->second.first==dump(py::id(image)))continue;
        r<<(first?"":",")<<dump(key)<<":";first=false;
        if(found==before.end())r<<"null";else r<<"{\"id\":"<<found->second.first<<",\"describe\":"<<found->second.second<<"}";
    }}
    r<<"}}";
}
J parsed(const V& v){std::string text=dump(v);try{return J::parse(text);}catch(...){return J(text.substr(0,200));}}
}
int main(int argc,char** argv) {
    if(argc!=3&&argc!=4){std::fprintf(stderr,"usage: cold72_export scenario out [atlas]\n");return 1;}
    SDL_SetMainReady();SDL_setenv("SDL_VIDEODRIVER","dummy",0);SDL_setenv("SDL_AUDIODRIVER","dummy",0);
    gil::init();data::set_data_dir("extract/data");pg::install_pygame();callm(pg::pygame_module(),Sym("init"),Args{});
    std::ifstream f(u8p(argv[1]),std::ios::binary);auto sc=J::parse(f);sc.erase("setup");
    try {
        BattleHandle h=battle_from_scenario(sc);V b=h.battle;V g=pvz::getattr(b,Sym("g"));Match& G=match_of(g);
        J out;out["seed"]=sc.value("seed",1.0);
        const auto attr=[&](const char* name){return parsed(pvz::getattr(b,Sym(name),V::none()));};
        for(const char* k:{"tile","width","height","dt","mode","seats","present","command","commands","sky_interval","sky_progress","native_secrets","team_secrets","bans","rules","_multi_plant","_multi_target","team_mode","scripted","ids","terrain_revision"})out["battle"][k]=attr(k);
        // NativeBattle.map tiles as published so far (the _sync_terrain baseline of the typed public terrain).
        {const V map=pvz::getattr(b,Sym("map"),V::none());if(map.is_dict())out["battle"]["map_tiles"]=parsed(py::m_get(map,V("tiles")));}
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
             J e={{"side",py_str(k.idx(0))},{"key",py_str(k.idx(1))},{"secrets",names(k.idx(2))},{"bans",names(k.idx(3))},{"night",k.idx(4).truthy()},{"cost",rd(v.idx(0),V("cost")).num()}};
             memo.push_back(std::move(e));}
         out["unit_card_memo"]=memo;}
        const auto rng=[&](PyRandom& r){auto s=r.state();J w=J::array();for(const auto word:s.mt)w.push_back(word);return J{{"mt",w},{"mti",s.mti}};};
        if(argc==4){
            write_atlas(G.find_global(V("图集"))?*G.find_global(V("图集")):V::dict(),argv[3]);
            // Draw atlas: the original patch replaces the plant-zombie display art lazily at its
            // first draw (__pvz_sb_draw_plant_zombie_heads). That idempotent asset step is a cold
            // path; run it here on the installed atlas and export only the draw recipes. The
            // simulation atlas above stays as the battle constructed it.
            write_draw_atlas(b,g,std::string(argv[3])+".draw.json");
        }
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
        std::ofstream o(u8p(argv[2]),std::ios::binary);o<<out.dump(-1,' ',false,J::error_handler_t::replace);std::puts("ok");
    }catch(PyError& e){std::fprintf(stderr,"PyError %s\n",e.what());return 2;}
    catch(std::exception& e){std::fprintf(stderr,"error %s\n",e.what());return 3;}
    return 0;
}
