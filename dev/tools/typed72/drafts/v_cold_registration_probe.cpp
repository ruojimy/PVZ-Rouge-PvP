#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/gen/pm_native_battle.h"
#include "sim/pvp/gen/pm_scripted_spawn_budget.h"
#include <fstream>
#include <iostream>
using namespace pvz;using J=nlohmann::json;
namespace {
V decode(const J& v){if(v.is_null())return V::none();if(v.is_boolean())return V(v.get<bool>());if(v.is_number())return V(v.get<double>());if(v.is_string())return V(v.get<std::string>());if(v.is_array()){V r=V::list();for(const auto& x:v)r.append(decode(x));return r;}V r=V::dict();for(const auto& p:v.items())setitem(r,V(p.key()),decode(p.value()));return r;}
J encode(const V& v){if(!v.has()||v.is_none())return nullptr;if(v.t==V::BOOL)return v.truthy();if(v.is_num())return v.num();if(v.is_str())return v.str();if(v.is_dict()){J r=J::object();for(const auto& p:py::items_vec(v))r[p.first.str()]=encode(p.second);return r;}J r=J::array();for(const auto& x:py::iter_list(v).items())r.push_back(encode(x));return r;}
J evaluate(const J& input){
    auto owner=std::make_shared<pm_native_battle::C_NativeBattle>();auto& b=*owner;
    b.a_ids=V(input.value("ids",0));b.a_time=V(input.value("time",1.25));b.a_tick=V(7);
    b.a_mode=V(input.value("mode",std::string("duel")));b.a__acting_seat=decode(input.value("acting",J()));
    b.a__native_objects=decode(input.value("registered",J::object()));b.a_events=V::list();b.a_log=V::list();
    b.a_team_secrets=decode(J{{"plant",input.value("secrets",J::array())}});
    auto patch=std::make_shared<PyObj>();patch->setattr(SY("ns"),decode(J{{"__pvz_sb_K_ZOMBIE_OBSERVED_MAX_HP","__pvz_sb_observed_max_hp"}}));b.a_patch=V::inst(patch);
    auto budget=std::make_shared<pm_scripted_spawn_budget::C_ScriptedSpawnBudget>();budget->a_enabled=V(input.value("budget_enabled",false));b.a_scripted_spawn_budget=V::inst(budget);
    if(input.contains("wave"))b.setattr(SY("_scripted_spawn_wave"),decode(input["wave"]));
    auto native=decode(input.at("native"));const auto card=pm_catalog::f_actual_card(Args{decode(input.at("key")),decode(input.value("secrets",J::array())),V(false)});
    const auto parent=decode(input.value("parent",J()));
    for(const auto& action:input.at("actions")){
        const auto name=action.get<std::string>();
        if(name=="register")b.m__register(Args{native,card,decode(input.at("side")),V(input.value("temporary",false)),parent,V::none()});
        else if(name=="health")b.m__apply_pvp_health(Args{native});
        else if(name=="hardening")b.m__apply_pvp_hardening(Args{native});
        else if(name=="configure")b.m__configure_plant(Args{native,card});
        else throw std::invalid_argument("unknown registration action");
    }
    J order=J::array();for(const auto& entry:py::items_vec(b.a__native_objects))order.push_back(entry.first.str());
    return {{"native",encode(native)},{"ids",encode(b.a_ids)},{"events",encode(b.a_events)},{"registry_order",order}};
}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("inputs output required");SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");SDL_setenv("SDL_VIDEODRIVER","dummy",1);SDL_setenv("SDL_AUDIODRIVER","dummy",1);pg::install_pygame();init_pvp_modules();
    std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("input/output open failed");std::string line;
    while(std::getline(in,line))if(!line.empty())out<<evaluate(J::parse(line)).dump()<<'\n';if(in.bad())throw std::runtime_error("read failed");out.close();if(!out)throw std::runtime_error("write failed");return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
