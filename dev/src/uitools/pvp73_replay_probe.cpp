#include "pg/pg.h"
#include "core/gil.h"
#include "core/fsutil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "ui/gen/pm_replay.h"
#include <SDL.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
using namespace pvz;
using J=nlohmann::json;
int main(int argc,char**argv){
    if(argc!=3)return 2;
    SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    J report=J::array();int rc=0;
    try{
        std::ifstream in(u8p(argv[1]));J raw=J::parse(in);
        const bool debug=std::getenv("PVP_REPLAY_DEBUG")!=nullptr;
        if(debug){J ops=J::array();for(const auto& op:raw["operations"])if(op["kind"]!="check"&&op["tick"].get<int>()<300)ops.push_back(op);raw["operations"]=ops;raw["ticks"]=raw["ticks"].get<int>()+1;}
        V data=py::stdlib_call(SV("json.loads"),Args{V(raw.dump())});
        auto h=battle_from_scenario({{"seed",301}});callm(h.battle,SY("close"),Args{});
        V playback=pm_replay::new_Playback(Args{data,h.bridge});
        const int64_t end=raw.at("ticks");
        for(int64_t target:{std::min<int64_t>(debug?300:700,end),std::min<int64_t>(120,end),std::min<int64_t>(1500,end),int64_t(0),end}){
            callm(playback,SY("seek"),Args{V(double(target))});setattr(playback,SY("speed"),V(8.));
            for(int n=0;n<100000&&!getattr(playback,SY("error")).truthy();++n){
                if(getattr(playback,SY("target")).is_none())break;
                callm(playback,SY("update"),Args({V(.12)},{{SY("max_steps"),V(37)},{SY("budget"),V(1.)}}));
            }
            J row={{"target",target},{"tick",getattr(getattr(playback,SY("battle")),SY("tick")).num()},
                {"error",py_str(getattr(playback,SY("error")))},{"verified",getattr(playback,SY("verified")).truthy()}};
            report.push_back(row);std::cerr<<row.dump()<<std::endl;
            if(debug){
                V snap=callm(getattr(playback,SY("battle")),SY("snapshot"),Args({},{{SY("include_map"),V(true)}}));
                std::cerr<<"typed hash "<<py_str(pm_replay::f_state_hash(Args{getattr(playback,SY("battle"))}))<<std::endl;
                std::ofstream(std::string(argv[2])+".typed.json")<<py_str(py::stdlib_call(SV("json.dumps"),Args{snap}));
                V init=rd(data,SV("initial"));
                V b=callm(pm_replay::module_ns(),SY("NativeBattle"),Args({rd(init,SV("map")),rd(init,SV("decks")),rd(init,SV("rules")),rd(init,SV("seed")),rd(init,SV("bans"))},{{SY("bridge"),h.bridge}}));
                V ops=rd(data,SV("operations"));size_t cur=0;
                for(int64_t t=0;t<=target;++t){
                    while(cur<ops.len()&&rd(ops.idx(cur),SV("tick")).num()==t){V op=ops.idx(cur++);if(rd(op,SV("kind"))==SV("input"))callm(b,SY("command_input"),Args{rd(op,SV("side")),rd(op,SV("payload"))});else callm(b,SY("clear_input"),Args{rd(op,SV("side"))});}
                    if(t<target)callm(b,SY("step"),Args{});
                }
                snap=callm(b,SY("snapshot"),Args({},{{SY("include_map"),V(true)}}));
                std::cerr<<"V hash "<<py_str(pm_replay::f_state_hash(Args{b}))<<std::endl;
                std::ofstream(std::string(argv[2])+".v.json")<<py_str(py::stdlib_call(SV("json.dumps"),Args{snap}));
                callm(b,SY("close"),Args{});break;
            }
            if(getattr(playback,SY("error")).truthy()){
                V snap=callm(getattr(playback,SY("battle")),SY("snapshot"),Args({},{{SY("include_map"),V(true)}}));
                std::ofstream(std::string(argv[2])+".snapshot.json")<<py_str(py::stdlib_call(SV("json.dumps"),Args{snap}));
                rc=1;break;
            }
        }
        callm(playback,SY("close"),Args{});
    }catch(const std::exception& e){report.push_back({{"fatal",e.what()}});std::cerr<<e.what()<<std::endl;rc=1;}
    std::ofstream(argv[2])<<report.dump(2);return rc;
}
