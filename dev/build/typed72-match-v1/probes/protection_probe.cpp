// Offline boundary for the positive-unit-damage policy and its state effects.
#include "sim/typed/protection.h"
#include "nlohmann/json.hpp"
#include <fstream>
#include <iostream>
using namespace pvz::typed72;
using J=nlohmann::ordered_json;
namespace {
void keys(const J& j,std::initializer_list<const char*> allowed) {
    if(!j.is_object())throw std::invalid_argument("expected object");
    for(auto i=j.begin();i!=j.end();++i){bool found=false;for(auto key:allowed)if(i.key()==key){found=true;break;}
        if(!found)throw std::invalid_argument("unsupported field: "+i.key());}
}
template<class T> void read(const J& j,const char* k,Field<T>& f) {
    if(!j.contains(k))return;if(j[k].is_null())f.set_null();else f.set(j[k].get<T>());
}
template<class T> void write(J& j,const char* k,const Field<T>& f) {
    if(f.present())j[k]=f.is_null()?J(nullptr):J(f.get());
}
struct Unit {
    double hp=0,hand_hp=0;
    std::string hand;
    AttackSource source;
    UnitProtectionState state;
    DamageTarget target(){return {hp,hand,source,state};}
};
Unit unit(const J& j) {
    keys(j,{"血量","手持","手持血量","植物","魅惑","_pvp_owner","_pvp_id","_pvp_content","_pvp_card","_pvp_hero","_pvp_grave",
        "_pvp_anchor_until","_pvp_zs_hurt","_pvp_zs_crowd_factor","_pvp_zs_relic_until","篮球","_pvp_reaper_hurt","_pvp_zs_lock_done","_pvp_zs_locked"});
    Unit u;u.hp=j.at("血量");u.hand=j.value("手持",std::string{});u.hand_hp=j.value("手持血量",0.);
    read(j,"植物",u.source.plant);read(j,"魅惑",u.source.charmed);read(j,"_pvp_owner",u.source.owner);read(j,"_pvp_id",u.source.id);read(j,"_pvp_content",u.source.content);
    read(j,"_pvp_card",u.state.card);u.state.hero=j.value("_pvp_hero",false);u.state.grave=j.value("_pvp_grave",false);
    read(j,"_pvp_anchor_until",u.state.anchor_until);read(j,"_pvp_zs_hurt",u.state.hurt_tick);read(j,"_pvp_zs_crowd_factor",u.state.crowd_factor);
    read(j,"_pvp_zs_relic_until",u.state.relic_until);read(j,"篮球",u.state.basketball);read(j,"_pvp_reaper_hurt",u.state.reaper_hurt);
    u.state.lock_done=j.value("_pvp_zs_lock_done",false);read(j,"_pvp_zs_locked",u.state.locked);return u;
}
J snapshot(const UnitProtection& p,const std::vector<Unit>& units) {
    J j={{"units",J::array()},{"events",J::array()}};
    for(const auto& u:units) {
        J row={{"血量",u.hp},{"手持",u.hand},{"手持血量",u.hand_hp}};
        write(row,"_pvp_zs_hurt",u.state.hurt_tick);write(row,"_pvp_zs_relic_until",u.state.relic_until);
        write(row,"_pvp_reaper_hurt",u.state.reaper_hurt);write(row,"_pvp_zs_locked",u.state.locked);
        j["units"].push_back(std::move(row));
    }
    for(const auto& event:p.events)if(const auto* e=std::get_if<RelicEvent>(&event))j["events"].push_back({{"type","zsecret_relic"},{"entity",e->entity?J(*e->entity):J(nullptr)},{"seconds",e->seconds}});
    return j;
}
J run(const J& input) {
    keys(input,{"players","cards","until","factor","units","operations"});
    CombatStages visual;HeroCombat heroes(visual);UnitProtection policy(heroes);
    for(size_t i=0;i<4;++i){heroes.heroes[i].emplace();heroes.players[i].emplace();}
    for(auto i=input.at("players").begin();i!=input.at("players").end();++i)heroes.players[seat_index(parse_seat(i.key()))]->secrets=i.value().get<std::vector<std::string>>();
    policy.secrets.configure(heroes.players);
    for(auto i=input.at("cards").begin();i!=input.at("cards").end();++i)policy.cards[i.key()]={i.value().get<bool>()};
    policy.until=input.at("until");policy.producer_factor=input.at("factor");
    std::vector<Unit> units;for(const auto& j:input.at("units"))units.push_back(unit(j));
    J results=J::array();
    for(const auto& op:input.at("operations")) {
        keys(op,{"function","unit","amount","tick","time","deathmatch","last_stand","owner","selected"});
        if(op.contains("tick"))heroes.tick=op["tick"];
        if(op.contains("time"))heroes.time=op["time"];
        if(op.contains("deathmatch"))policy.deathmatch=op["deathmatch"];
        if(op.contains("last_stand")) {
            heroes.last_stand_order.clear();if(op["last_stand"].get<bool>())heroes.last_stand_order.push_back(Seat::zombie);
        }
        if(op.contains("owner")) {
            if(op["owner"].is_null())heroes.active.reset();else heroes.active=HeroSelection{Seat::plant,parse_seat(op["owner"].get<std::string>()),CombatPhase::zombies,{},{}};
        }
        if(op.contains("selected"))for(auto i=op["selected"].begin();i!=op["selected"].end();++i)
            policy.selected_grave[seat_index(parse_seat(i.key()))]=i.value().is_null()?std::optional<std::string>{}:std::optional<std::string>(i.value().get<std::string>());
        const std::string fn=op.at("function");auto& u=units.at(op.at("unit").get<size_t>());auto target=u.target();J value;
        if(fn=="amount")value=policy.amount(target,op.at("amount"));
        else if(fn=="multiplier")value=policy.multiplier(target);
        else if(fn=="damage_factor")value=policy.damage_factor(target);
        else if(fn=="shield_first")value=policy.shield_first(target,u.hand_hp);
        else if(fn=="focused")value=policy.focused(target);
        else if(fn=="berserk")value=policy.berserk();
        else if(fn=="selected")value=policy.selected(target);
        else throw std::invalid_argument("unknown protection operation");
        auto row=snapshot(policy,units);row["result"]=std::move(value);results.push_back(std::move(row));
    }
    return results;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: protection72_probe input.jsonl output.jsonl");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("cannot open probe files");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run(J::parse(line)).dump()<<'\n';
        if(!output)throw std::runtime_error("cannot write results");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
