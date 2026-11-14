// Actual Room population configuration -> cold export -> production admission.
#include "pg/pg.h"
#include "core/gil.h"
#include "core/trace.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/typed72_app/cold_export.h"
#include "sim/typed72_app/session.h"
#include "ui/gen/pm_room.h"
#include <fstream>
#include <iostream>
using namespace pvz;
using J=nlohmann::json;
namespace {
void require(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
V value(const J& j){return py::json_loads(V(j.dump()));}
J configured_room(int limit){
    auto h=battle_from_scenario({{"seed",742},{"fixture_flat",true},{"durable_heroes",true}});
    V room=pm_room::new_Room(Args{h.bridge,getattr(h.battle,SY("rules"))});
    auto* r=as<pm_room::C_Room>(room);
    r->a_mode=SV("coop");r->a_phase=SV("config");r->a_seed=V(742);
    r->a_members=value({{"host","plant"},{"guest","plant2"}});
    r->a_connected=value({{"host",true},{"guest",true}});r->a_replay_enabled=V(false);
    const auto setup=py_str(callm(room,SY("set_pve"),Args({V(9),value({"plant:向日葵"})},{{SY("seed"),V(742)},{SY("max_zombies"),V(40)}})));
    require(setup.empty(),"Room.set_pve: "+setup);
    const auto error=py_str(callm(room,SY("command"),Args{SV("host"),value({{"type","pve_population"},{"max_zombies",limit},{"revision",r->a_revision.num()}})}));
    require(error.empty(),"Room.command pve_population: "+error);
    callm(room,SY("_start_pve"),Args{});
    const V b=r->a_battle;
    const double rule=rd(getattr(b,SY("rules")),SV("pve_max_zombies")).num();
    const double director=getattr(getattr(b,SY("director")),SY("max_zombies")).num();
    require(rule==limit,"configured rule lost before typed entry");
    require(director==limit,"configured director lost before typed entry");
    int accepted=0;for(int i=0;i<limit+1;++i)if(!callm(b,SY("spawn"),Args{SV("zombie:普通僵尸"),SV("zombie"),V(1000.+i),V(960.),V(1.)}).is_none())++accepted;
    J result={{"rule",rule},{"director",director},{"requested",limit+1},{"expected",limit},{"accepted",accepted},{"matched",accepted==limit}};
    callm(r->a_battle,SY("close"),Args{});callm(h.battle,SY("close"),Args{});
    return result;
}
J spawn_count(typed72app::ColdExport cold,int requested,int expected){
    J config={{"rule",cold.cold.at("battle").at("rules").value("pve_max_zombies",J(nullptr))},
              {"director",cold.cold.contains("director")?cold.cold.at("director").value("max_zombies",J(nullptr)):J(nullptr)}};
    auto b=typed72app::Session::create(std::move(cold),"population-entry-audit");
    int accepted=0;for(int i=0;i<requested;++i)if(b->spawn("zombie:普通僵尸","zombie",1000.+i,960.,1.,false))++accepted;
    config["requested"]=requested;config["accepted"]=accepted;config["expected"]=expected;
    config["matched"]=accepted==expected;return config;
}
}
int main(int argc,char** argv){
    if(argc<2||!std::getenv("PVP_USERDATA"))return 2;
    install_crash_handler();SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");pg::install_pygame();init_pvp_modules();
    J rows=J::array();int failures=0;
    auto test=[&](const std::string& name,auto run){J row={{"name",name}};try{row["evidence"]=run();row["passed"]=row["evidence"].at("matched");if(!row["passed"].get<bool>())++failures;}catch(const std::exception& e){print_last_cpp_throw(stderr);row["passed"]=false;row["error"]=e.what();++failures;}std::cerr<<row.dump()<<std::endl;rows.push_back(std::move(row));};
    for(int limit:{2,40,120})test("Room_command_population_"+std::to_string(limit),[&](){return configured_room(limit);});
    test("duel_ignores_scripted_population_cap",[](){auto h=battle_from_scenario({{"seed",742},{"fixture_flat",true},{"rules",{{"pve_max_zombies",2}}}});auto cold=typed72app::export_cold(h.battle,742);callm(h.battle,SY("close"),Args{});return spawn_count(std::move(cold),5,5);});
    const J conversions=J::array({
        J{{"value",nullptr},{"limit",40}},J{{"value","2"},{"limit",2}},
        J{{"value",2.9},{"limit",2}},J{{"value",false},{"limit",1}},
        J{{"value",-1},{"limit",1}},J{{"value",201},{"limit",200}},
        J{{"value","invalid"},{"limit",40}}
    });
    for(const auto& input:conversions)
        test("cold_rule_conversion_"+input.at("value").dump(),[&](){
            auto h=battle_from_scenario({{"seed",742},{"fixture_flat",true},{"mode","coop"},{"rules",{{"pve_max_zombies",input.at("value")}}}});
            const double original=getattr(getattr(h.battle,SY("scripted_spawn_budget")),SY("limit")).num();
            const int expected=input.at("limit");require(original==expected,"original cold budget contract differs");
            auto cold=typed72app::export_cold(h.battle,742);callm(h.battle,SY("close"),Args{});
            auto result=spawn_count(std::move(cold),expected+1,expected);result["original_limit"]=original;result["raw_rule"]=input.at("value");return result;
        });
    std::ofstream(argv[1],std::ios::binary)<<J{{"passed",failures==0},{"failures",failures},{"cases",rows},{"scope","Actual Room.set_pve + host Room.command pve_population + Room._start_pve, then production typed Session::spawn. No simulation tick or behavior override."}}.dump(2);
    return failures?1:0;
}
