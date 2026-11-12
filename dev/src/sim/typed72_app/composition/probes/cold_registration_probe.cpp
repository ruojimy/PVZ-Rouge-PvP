#include "sim/typed/cold_registration.h"
#include "core/pymath.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
using namespace pvz::typed72;using J=nlohmann::json;
namespace {
template<class T>void read(Field<T>& f,const J& o,const char* key){if(o.contains(key)){if(o[key].is_null())f.set_null();else f.set(o[key].get<T>());}}
template<class T>void write(J& o,const char* key,const Field<T>& f){if(!f.present())o.erase(key);else if(f.is_null())o[key]=nullptr;else o[key]=f.get();}
void source(AttackSource& s,const J& o){read(s.id,o,"_pvp_id");read(s.owner,o,"_pvp_owner");read(s.wave_index,o,"_pvp_wave_index");if(o.contains("_pvp_seat")&&!o["_pvp_seat"].is_null())s.seat=parse_seat(o["_pvp_seat"].get<std::string>());}
void write_source(J& o,const AttackSource& s){write(o,"_pvp_id",s.id);write(o,"_pvp_owner",s.owner);write(o,"_pvp_wave_index",s.wave_index);if(s.seat)o["_pvp_seat"]=seat_name(*s.seat);else o.erase("_pvp_seat");}
struct Sink:ColdSpawnEvents{J events=J::array();void spawn(const ColdSpawnEvent& e)override{events.push_back({{"event","spawn"},{"tick",7},{"time",1.25},{"entity",e.entity},{"card",e.card},{"side",seat_name(e.side)},{"source_entity",e.entity},{"parent_entity",e.parent_entity?J(*e.parent_entity):J()},{"parent_attack",nullptr},{"native",true}});}};
J evaluate(const J& input){
    TypedBattleState world;world.heroes.time=input.value("time",1.25);const auto mode=input.value("mode",std::string("duel"));world.mode=mode=="duel"?MatchMode::duel:mode=="duo"?MatchMode::duo:mode=="coop"?MatchMode::coop:MatchMode::pve;
    ColdCatalog catalog;uint64_t ids=input.value("ids",uint64_t{});Sink sink;ColdRegistration registration(world,catalog,ids,sink);
    if(input.contains("registered"))for(const auto& p:input["registered"].items()){auto z=std::make_shared<CombatZombie>();source(z->source,p.value());world.native_objects.set(p.key(),z);}
    const auto native=input.at("native");NativeObject object;
    if(native.contains("植物")){auto p=std::make_shared<CombatPlant>(native.at("植物").get<std::string>(),Cell{0,0},1.);source(p->source,native);read(p->hp,native,"植物血");read(p->max_hp,native,"植物血上限");read(p->registration.health_form,native,"_pvp_health_form");read(p->content_state.hardening_form,native,"_pvp_hardening_form");read(p->buried,native,"埋藏");object=p;
    }else{auto z=std::make_shared<CombatZombie>();source(z->source,native);z->body.kind=native.value("僵尸",std::string("普通僵尸"));z->body.hp=native.value("血量",0.);z->body.armor_hp=native.value("防具血量",0.);read(z->native.move_speed,native,"移速");read(z->registration.health72,native,"_pvp72_health");z->protection.grave=native.value("_pvp_grave",false);const auto pos=native.value("位置",J::array({0.,0.,0.,0.}));z->body.motion.replace({pos[0].get<double>(),pos[1].get<double>(),pos[2].get<double>(),pos[3].get<double>()});object=z;}
    ColdParent parent;const bool has_parent=input.contains("parent")&&!input["parent"].is_null()&&!input["parent"].empty();
    if(has_parent){const auto& raw=input["parent"];if(raw.contains("id")&&!raw["id"].is_null())parent.id=raw["id"].get<std::string>();parent.fallback=std::make_shared<AttackSource>();source(*parent.fallback,raw);}
    ColdRegistrationContext context;context.budget_enabled=input.value("budget_enabled",false);if(input.contains("acting")&&!input["acting"].is_null())context.acting_seat=parse_seat(input["acting"].get<std::string>());if(input.contains("wave"))context.scripted_wave=input["wave"].get<int64_t>();
    const auto secrets=input.value("secrets",std::vector<std::string>{});const auto card=catalog.actual(input.at("key").get<std::string>(),secrets);
    for(const auto& action:input.at("actions")){const auto name=action.get<std::string>();if(name=="register")registration.register_unit(object,card,parse_seat(input.at("side").get<std::string>()),input.value("temporary",false),context,has_parent?&parent:nullptr);
        else if(name=="health")registration.health(std::get<PlantRef>(object),secrets);else if(name=="hardening")registration.hardening(std::get<PlantRef>(object),secrets);else if(name=="configure")registration.configure_plant(std::get<PlantRef>(object),card,secrets);else throw std::invalid_argument("unknown action");}
    J result=native;std::visit([&](const auto& p){write_source(result,p->source);write(result,"_pvp_card",p->protection.card);},object);
    if(auto* pp=std::get_if<PlantRef>(&object)){const auto& p=**pp;write(result,"植物血",p.hp);write(result,"植物血上限",p.max_hp);write(result,"_pvp_health_form",p.registration.health_form);write(result,"_pvp_hardening_form",p.content_state.hardening_form);write(result,"埋藏",p.buried);write(result,"_pvp_max_hp",p.content_state.maximum_hp);write(result,"_pvp_armor_max",p.registration.armor_max);write(result,"_pvp_born",p.registration.born);write(result,"_pvp_temporary",p.temporary);
    }else{const auto& z=*std::get<ZombieRef>(object);result["血量"]=z.body.hp;write(result,"移速",z.native.move_speed);write(result,"_pvp72_health",z.registration.health72);write(result,"__pvz_sb_observed_max_hp",z.patch.observed_max_hp);write(result,"_pvp_max_hp",z.max_hp);write(result,"_pvp_armor_max",z.armor_max);write(result,"_pvp_born",z.born);write(result,"_pvp_temporary",z.registration.temporary);write(result,"_pvp_producer",z.producer);if(z.registration.grave_anchor.present())result["_pvp_anchor"]=J::array({z.registration.grave_anchor.get().x,z.registration.grave_anchor.get().y});}
    for(auto& event:sink.events)event["time"]=pvz::py::roundn(world.heroes.time,4);
    J order=J::array();for(const auto& e:world.native_objects.entries())order.push_back(e.key);return {{"native",result},{"ids",ids},{"events",sink.events},{"registry_order",order}};
}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("inputs output required");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("open failed");std::string line;while(std::getline(in,line))if(!line.empty())out<<evaluate(J::parse(line)).dump()<<'\n';if(in.bad())throw std::runtime_error("read failed");out.close();if(!out)throw std::runtime_error("write failed");return 0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
