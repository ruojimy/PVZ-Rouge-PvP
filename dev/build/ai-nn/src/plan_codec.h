#pragma once
// JSON form of a planner call (input facts, planner memory, plan) for the plan recorder
// (headless_match) and the offline re-computation (replay_planner). Doubles are written by
// nlohmann's shortest round-trip formatter, so a value read back is bit-identical.
#include "common.h"
#include "sim/typed72_app/ai_planner_r22.h"
#include "sim/typed/allegiance.h"
#include <optional>
#include <string>
#include <vector>
namespace ainn {
using pvz::typed72::Seat;
using pvz::typed72::AiUnitView;
using pvz::typed72app::AiPlanR22;
using pvz::typed72app::AiPlannerHero;
using pvz::typed72app::AiPlannerInput;
using pvz::typed72app::AiPlannerMemory;

inline J num(double v){
    if(std::isnan(v))return "nan";
    if(std::isinf(v))return v>0?"inf":"-inf";
    return v;
}
inline double num_from(const J& j){
    if(j.is_string()){const auto s=j.get<std::string>();return s=="nan"?std::nan(""):s=="inf"?HUGE_VAL:-HUGE_VAL;}
    return j.get<double>();
}
inline J opt_num(const std::optional<double>& v){return v?num(*v):J(nullptr);}
inline std::optional<double> opt_num_from(const J& j){return j.is_null()?std::nullopt:std::optional<double>(num_from(j));}
inline J opt_text(const std::optional<std::string>& v){return v?J(*v):J(nullptr);}
inline std::optional<std::string> opt_text_from(const J& j){return j.is_null()?std::nullopt:std::optional<std::string>(j.get<std::string>());}
inline std::string seat_text(Seat s){return std::string(pvz::typed72::seat_name(s));}

// Column order of one unit row in a plan record ("unit_fields" in the file header).
inline const std::vector<std::string>& unit_fields(){
    static const std::vector<std::string> f{"id","card","side","seat","x","y","hp","max_hp","plant_y","grave","vx","vy","mobile","awake","behavior",
        "card_name","card_behavior","card_cost","card_range","card_damage","card_producer","card_mushroom"};
    return f;
}
inline J unit_json(const AiUnitView& u){
    return J::array({u.id,u.card,seat_text(u.side),u.seat?J(seat_text(*u.seat)):J(nullptr),num(u.position.x),num(u.position.y),num(u.hp),num(u.max_hp),num(u.plant_y),u.grave,
        num(u.velocity.x),num(u.velocity.y),u.mobile,u.awake,opt_text(u.behavior),
        opt_text(u.card_info.name),u.card_info.behavior,opt_num(u.card_info.cost),opt_num(u.card_info.range),num(u.card_info.damage),u.card_info.producer,u.card_info.mushroom});
}
inline AiUnitView unit_from(const J& r){
    AiUnitView u;u.id=r.at(0);u.card=r.at(1);u.side=pvz::typed72::parse_seat(r.at(2).get<std::string>());
    if(!r.at(3).is_null())u.seat=pvz::typed72::parse_seat(r.at(3).get<std::string>());
    u.position={num_from(r.at(4)),num_from(r.at(5))};u.hp=num_from(r.at(6));u.max_hp=num_from(r.at(7));u.plant_y=num_from(r.at(8));u.grave=r.at(9);
    u.velocity={num_from(r.at(10)),num_from(r.at(11))};u.mobile=r.at(12);u.awake=r.at(13);u.behavior=opt_text_from(r.at(14));
    u.card_info.name=opt_text_from(r.at(15));u.card_info.behavior=r.at(16);u.card_info.cost=opt_num_from(r.at(17));u.card_info.range=opt_num_from(r.at(18));
    u.card_info.damage=num_from(r.at(19));u.card_info.producer=r.at(20);u.card_info.mushroom=r.at(21);
    return u;
}
inline J hero_json(const AiPlannerHero& h){return {{"x",num(h.x)},{"y",num(h.y)},{"hp",num(h.hp)},{"max_hp",num(h.max_hp)},{"resource",num(h.resource)}};}
inline AiPlannerHero hero_from(const J& j){return {num_from(j.at("x")),num_from(j.at("y")),num_from(j.at("hp")),num_from(j.at("max_hp")),num_from(j.at("resource"))};}
inline J input_json(const AiPlannerInput& in){
    J units=J::array();for(const auto& u:in.units)units.push_back(unit_json(u));
    return {{"side",seat_text(in.side)},{"time",num(in.time)},{"width",num(in.width)},{"me",hero_json(in.me)},{"foe",hero_json(in.foe)},
        {"deck",std::vector<std::string>(in.deck.begin(),in.deck.end())},{"recovering",in.recovering},{"units",units}};
}
// AiPlannerInput holds spans: keep the storage next to it.
struct OwnedInput {
    std::vector<std::string> deck;std::vector<AiUnitView> units;AiPlannerInput in;
    OwnedInput()=default;
    OwnedInput(const OwnedInput&)=delete;OwnedInput& operator=(const OwnedInput&)=delete;
};
inline void input_from(const J& j,OwnedInput& out){
    out.deck=j.at("deck").get<std::vector<std::string>>();out.units.clear();
    for(const auto& r:j.at("units"))out.units.push_back(unit_from(r));
    out.in.side=pvz::typed72::parse_seat(j.at("side").get<std::string>());out.in.time=num_from(j.at("time"));out.in.width=num_from(j.at("width"));
    out.in.me=hero_from(j.at("me"));out.in.foe=hero_from(j.at("foe"));out.in.deck=out.deck;out.in.units=out.units;out.in.recovering=j.at("recovering");
}
inline J memory_json(const AiPlannerMemory& m){
    return {{"mode",m.mode},{"last_pressure_at",num(m.last_pressure_at)},{"last_enemy_hp",num(m.last_enemy_hp)},{"last_attack_at",num(m.last_attack_at)},
        {"push_until",num(m.push_until)},{"peak_econ",m.peak_econ},{"peak_graves",m.peak_graves}};
}
inline AiPlannerMemory memory_from(const J& j){
    return {j.at("mode"),num_from(j.at("last_pressure_at")),num_from(j.at("last_enemy_hp")),num_from(j.at("last_attack_at")),num_from(j.at("push_until")),
        j.at("peak_econ").get<int64_t>(),j.at("peak_graves").get<int64_t>()};
}
// The plan dict in the key order Session::plan_dict builds it (priority, quotas, then the
// side's own keys). Only the keys of the plan's side are written.
inline J plan_json(const AiPlanR22& p){
    J quotas=J::array();for(const auto& [k,q]:p.quotas)quotas.push_back(J::array({k,num(q)}));
    J d={{"side",seat_text(p.side)},{"priority",p.priority},{"quotas",quotas}};
    if(p.side==Seat::plant){
        d["mode"]=opt_text(p.mode);
        d["econ_goal"]=num(p.econ_goal);d["wall_goal"]=num(p.wall_goal);d["reserve"]=num(p.reserve);d["siege_gap"]=num(p.siege_gap);
        d["teleport_hp"]=num(p.teleport_hp);d["panic_value"]=num(p.panic_value);d["bomb_value"]=num(p.bomb_value);d["siege_step"]=num(p.siege_step);
        d["siege_dwell"]=num(p.siege_dwell);d["siege_lobs"]=num(p.siege_lobs);d["rich"]=num(p.rich);d["vine_reserve"]=num(p.vine_reserve);d["global_collect"]=p.global_collect;
    }else{
        d["grave_start"]=num(p.grave_start);d["grave_max"]=num(p.grave_max);d["grave_every"]=num(p.grave_every);d["save_horizon"]=num(p.save_horizon);
        d["wave_base"]=num(p.wave_base);d["wave_growth"]=num(p.wave_growth);d["wave_cap"]=num(p.wave_cap);d["wave_hold_max"]=num(p.wave_hold_max);
        d["teleport_hp"]=num(p.teleport_hp);d["tend_every"]=num(p.tend_every);d["detonate_value"]=num(p.detonate_value);
        d["save"]=p.save?J(*p.save):J(nullptr);d["mode"]=opt_text(p.mode);
    }
    return d;
}
} // namespace ainn
