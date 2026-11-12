// Existing V/hand oracle only. Never linked into the typed battle runtime.
#include "pg/pg.h"
#include "core/gil.h"
#include "data/datastore.h"
#include "sim/pvp/battle_api.h"
#include "sim/pvp/gen/pm_catalog.h"
#include "sim/pvp/gen/pm_balance.h"
#include "sim/pvp/gen/pm_zombie_secret_catalog.h"
#include "sim/pvp/gen/pm_pvp66_secrets.h"
#include "sim/pvp/gen/pm_pvp71_catalog.h"
#include "sim/pvp/gen/pm_native_battle.h"
#include <fstream>
#include <iostream>
using namespace pvz;
using J=nlohmann::json;
namespace {
J encode(const V& value) {
    if(!value.has()||value.is_none())return nullptr;
    if(value.t==V::BOOL)return value.truthy();
    if(value.is_str())return value.str();
    if(value.is_num())return value.num();
    if(value.is_dict()){J result=J::object();for(const auto& pair:py::items_vec(value))result[pair.first.str()]=encode(pair.second);return result;}
    J result=J::array();for(const auto& item:py::iter_list(value).items())result.push_back(encode(item));return result;
}
V decode(const J& value) {
    if(value.is_null())return V::none();
    if(value.is_boolean())return V(value.get<bool>());
    if(value.is_number())return V(value.get<double>());
    if(value.is_string())return V(value.get<std::string>());
    if(value.is_array()){V result=V::list();for(const auto& item:value)result.append(decode(item));return result;}
    V result=V::dict();for(const auto& item:value.items())setitem(result,V(item.key()),decode(item.value()));return result;
}
J exported() {
    J result={{"backend_actual","existing-v-hand-catalog"},{"full_product_acceptance",false},
        {"catalog_hash",pm_catalog::f_catalog_hash(Args{}).str()},
        {"rules_hash",pm_catalog::f_rules_hash(Args{}).str()},
        {"raw_templates",encode(pm_catalog::CARDS)},{"rules",encode(pm_catalog::RULES)},
        {"replacements",encode(pm_catalog::REPLACEMENTS)},{"derived_bases",encode(pm_catalog::DERIVED_BASES)},
        {"protected",encode(pm_catalog::PROTECTED)},{"boss_names",encode(pm_catalog::BOSS_NAMES)},
        {"costs",encode(pm_balance::COSTS)},{"health",encode(pm_balance::HEALTH)},
        {"plant_cooldowns",encode(pm_balance::PLANT_COOLDOWNS)},{"zombie_cooldowns",encode(pm_balance::ZOMBIE_COOLDOWNS)},
        {"zombie_cost_set",encode(pm_zombie_secret_catalog::COST_SET)},
        {"zombie_cost_add",encode(pm_zombie_secret_catalog::COST_ADD)},
        {"zombie_hp_factor",encode(pm_zombie_secret_catalog::HP_FACTOR)},
        {"deathmatch_allowed_producers",encode(pm_balance::DEATHMATCH_ALLOWED_PRODUCERS)},
        {"fast_plant_cooldown_factor",encode(pm_balance::FAST_PLANT_COOLDOWN_FACTOR)},
        {"hardening_min_base_hp",encode(pm_balance::HARDENING_MIN_BASE_HP)},
        {"hardening_hp_factor",encode(pm_balance::HARDENING_HP_FACTOR)},
        {"starfruit_cost",encode(pm_pvp66_secrets::STARFRUIT_COST)},
        {"sea_shroom_surcharge",encode(pm_pvp66_secrets::SEA_SHROOM_SURCHARGE)},
        {"imitate_secret",encode(pm_pvp71_catalog::IMITATE_SECRET)},
        {"imitate_cooldown_factor",encode(pm_pvp71_catalog::IMITATE_COOLDOWN_FACTOR)},
        {"rush_cooldown",encode(pm_zombie_secret_catalog::RUSH_COOLDOWN)},
        {"rage_torch_art",encode(pm_zombie_secret_catalog::RAGE_TORCH_ART)}};
    J ordered=J::array();for(const auto& item:py::items_vec(pm_catalog::CARDS))ordered.push_back(item.first.str());
    result["card_order"]=ordered;
    for(const char* field:{"COST_SET","COST_ADD","HP_FACTOR"}) {
        const V table=field==std::string("COST_SET")?pm_zombie_secret_catalog::COST_SET:
                      field==std::string("COST_ADD")?pm_zombie_secret_catalog::COST_ADD:pm_zombie_secret_catalog::HP_FACTOR;
        J order=J::array();for(const auto& item:py::items_vec(table))order.push_back(item.first.str());
        result[std::string("zombie_order_")+field]=order;
    }
    return result;
}
J evaluate(const J& request) {
    const V key=decode(request.at("key")),secrets=decode(request.value("secrets",J::array())),
        bans=decode(request.value("bans",J::array())),night=V(request.value("night",false));
    const auto op=request.value("op",std::string("actual"));
    try {
        V value;
        if(op=="actual")value=pm_catalog::f_actual_card(Args{key,secrets,night});
        else if(op=="resolve")value=pm_catalog::f_resolve_card(Args{key,secrets,bans,night});
        else if(op=="allowed")value=pm_catalog::f_allowed(Args{key,bans,V(request.value("for_spawn",false)),secrets});
        else if(op=="native_secrets")value=pm_catalog::f_native_secret_names(Args{secrets,bans});
        else if(op=="player"||op=="unit"){
            pm_native_battle::C_NativeBattle battle;
            const V side=V(request.value("side",std::string("plant")));
            battle.a_players=V::dict();setitem(battle.a_players,side,decode(J{{"secrets",request.value("secrets",J::array())},{"last_copy_card",request.value("last_copy_card",std::string{})}}));
            battle.a_map=decode(J{{"environment",{{"night",request.value("night",false)}}}});battle.a_bans=bans;
            value=op=="player"?battle.m__card(Args{side,key}):battle.m__unit_card_resolved(Args{side,key});
        }
        else throw std::invalid_argument("Unknown cold catalog operation");
        return {{"ok",true},{"value",encode(value)}};
    }catch(const PyError& error){return {{"ok",false},{"error",error.what()}};}
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: v_cold_catalog_probe --export output | inputs output");
        SDL_SetMainReady();gil::init();data::set_data_dir("extract/data");
        SDL_setenv("SDL_VIDEODRIVER","dummy",1);SDL_setenv("SDL_AUDIODRIVER","dummy",1);
        SDL_setenv("PVP_USERDATA","test_results/cold-catalog-work/userdata",1);
        pg::install_pygame();init_pvp_modules();
        std::ofstream output(argv[2],std::ios::binary);
        if(std::string(argv[1])=="--export")output<<exported().dump(2)<<'\n';
        else {std::ifstream input(argv[1],std::ios::binary);std::string line;
            while(std::getline(input,line))if(!line.empty())output<<evaluate(J::parse(line)).dump()<<'\n';
            if(input.bad())throw std::runtime_error("Input read failed");}
        output.close();if(!output)throw std::runtime_error("Output write failed");return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
