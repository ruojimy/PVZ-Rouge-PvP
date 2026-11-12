// Legal duel deck corpus for offline cold exports (AI work, docs/ai-nn).
// For every (map, night, seed, ban variant): random unit bans, then the lobby AI's own draft
// choice (draft_advisor.recommend_ai, zombie first, then plant knowing the zombie deck), checked
// with catalog.validate_deck. Writes a JSON list of cold73_export scenarios.
//   deck73_corpus out.json [seeds_per_map=3] [ban_variants=2]
#include "sim/pvp/pvprt.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_native_bridge.h"
#include "sim/pvp/gen/pm_maps.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "ui/gen/pm_draft_advisor.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "pg/pg.h"
#include <cstdio>
#include <fstream>
#include <random>
#include <algorithm>
using namespace pvz;
using J=nlohmann::json;
static J parsed(const V& v){return J::parse(dump(v));}
static V list_of(const std::vector<std::string>& xs){std::vector<V> it;for(const auto& x:xs)it.push_back(V(x));return V::list(it);}
int main(int argc,char** argv){
    if(argc<2){std::fprintf(stderr,"usage: deck73_corpus out.json [seeds] [ban_variants]\n");return 1;}
    const int seeds=argc>2?std::atoi(argv[2]):3,variants=argc>3?std::atoi(argv[3]):2;
    SDL_SetMainReady();SDL_setenv("SDL_VIDEODRIVER","dummy",0);SDL_setenv("SDL_AUDIODRIVER","dummy",0);
    gil::init();data::set_data_dir("extract/data");pg::install_pygame();callm(pg::pygame_module(),Sym("init"),Args{});
    J out=J::array();
    try{
        init_pvp_modules();pm_native_bridge::init();pm_maps::init();pm_catalog::init();pm_draft_advisor::init();
        V bridge=pm_native_bridge::C_NativeBridge::m_from_marshaled(Args{});
        std::vector<std::string> maps;{const V t=pm_native_bridge::MAP_NAMES;for(size_t i=0;i<size_t(t.len());++i)maps.push_back(py_str(t.idx(int64_t(i))));}
        std::fprintf(stderr,"maps %zu\n",maps.size());
        std::vector<std::string> plant_units,zombie_units;
        for(const auto& [k,c]:pm_catalog::CARDS.kv()){
            const auto cat=py_str(py::m_get(c,V("category"))),side=py_str(py::m_get(c,V("side")));
            if(cat=="secret")continue;
            (side=="plant"?plant_units:zombie_units).push_back(py_str(k));
        }
        std::mt19937 rng(73);
        for(const auto& map:maps)for(int night=0;night<2;++night)for(int s=0;s<seeds;++s)for(int v=0;v<variants;++v){
            const int seed=1000*(s+1)+17*v+(night?500:0);
            J sc={{"map",map},{"seed",seed},{"night",bool(night)}};
            try{
                V terrain=pm_maps::f_build_snapshot(Args({bridge,V(map),V(double(seed))},{{Sym("weather"),V("clear")}}));
                if(night){V d=callm(terrain,Sym("to_dict"),Args{});setitem(py::m_get(d,V("environment")),V("night"),V(true));
                    callm(d,Sym("pop"),Args{V("terrain_hash"),V::none()});terrain=callm(pm_maps::cls_MapSnapshot(),Sym("from_dict"),Args{d});}
                // v==0: no bans (the AI's preferred deck); otherwise 2 random unit bans per side.
                std::vector<std::string> bans;
                auto view=[&](const J& decks){V d=V::dict();d.at(V("map"))=terrain;d.at(V("bans"))=list_of(bans);d.at(V("rules"))=py::copy(pm_catalog::RULES);
                    V dk=V::dict();for(const auto& [k,x]:decks.items())dk.at(V(k))=list_of(x.get<std::vector<std::string>>());d.at(V("decks"))=dk;return d;};
                // v>0: ban 2 random units of each side's unbanned AI deck (variety), plus v-1 random units per side.
                if(v){
                    J zb=parsed(py::m_get(pm_draft_advisor::f_recommend_ai(Args{view(J::object()),V("zombie")}),V("deck")));
                    J pb=parsed(py::m_get(pm_draft_advisor::f_recommend_ai(Args{view(J{{"zombie",zb}}),V("plant")}),V("deck")));
                    for(const J* deck:{&pb,&zb}){std::vector<std::string> units;for(const auto& k:*deck){const auto key=k.get<std::string>();
                            if(py_str(py::m_get(py::m_get(pm_catalog::CARDS,V(key)),V("category")))!="secret")units.push_back(key);}
                        std::shuffle(units.begin(),units.end(),rng);bans.insert(bans.end(),units.begin(),units.begin()+std::min<size_t>(2,units.size()));}
                    for(auto* pool:{&plant_units,&zombie_units}){auto p=*pool;std::shuffle(p.begin(),p.end(),rng);
                        for(int i=0,n=0;i<int(p.size())&&n<v-1;++i)if(std::find(bans.begin(),bans.end(),p[i])==bans.end()){bans.push_back(p[i]);++n;}}
                }
                J zdeck=parsed(py::m_get(pm_draft_advisor::f_recommend_ai(Args{view(J::object()),V("zombie")}),V("deck")));
                J pdeck=parsed(py::m_get(pm_draft_advisor::f_recommend_ai(Args{view(J{{"zombie",zdeck}}),V("plant")}),V("deck")));
                const V start=pm_catalog::f_starting_resource(Args{V("zombie"),pm_catalog::RULES,terrain});
                J errors=J::object();
                for(const auto& [side,deck]:{std::pair<std::string,J>{"plant",pdeck},{"zombie",zdeck}}){
                    V e=pm_catalog::f_validate_deck(Args{V(side),list_of(deck.get<std::vector<std::string>>()),list_of(bans),
                        py::m_get(pm_catalog::RULES,V(side+"_slots")),terrain,start});
                    if(e.truthy())errors[side]=py_str(e);
                }
                sc["decks"]={{"plant",pdeck},{"zombie",zdeck}};sc["bans"]=bans;
                if(!errors.empty()){sc["invalid"]=errors;}
                std::fprintf(stderr,"%s night=%d seed=%d plant=%zu zombie=%zu %s\n",map.c_str(),night,seed,pdeck.size(),zdeck.size(),errors.empty()?"ok":errors.dump().c_str());
            }catch(const PyError& e){sc["error"]=e.what();std::fprintf(stderr,"%s night=%d seed=%d ERROR %s\n",map.c_str(),night,seed,e.what());}
            out.push_back(sc);
        }
    }catch(const PyError& e){std::fprintf(stderr,"PyError %s\n",e.what());return 2;}
    std::ofstream(u8p(argv[1]),std::ios::binary)<<out.dump(1,' ',false);
    std::printf("scenarios %zu\n",out.size());return 0;
}
