// Test-only JSON boundary for the typed hero chain. Never linked into a game.
#include "sim/typed/hero.h"
#include "sim/typed/projectile.h"
#include "sim/typed/targets.h"
#include "nlohmann/json.hpp"
#include <fstream>
#include <iostream>
using namespace pvz::typed72;
using J=nlohmann::ordered_json;
namespace {
void keys(const J& j,std::initializer_list<const char*> allowed) {
    if(!j.is_object())throw std::invalid_argument("expected object");
    for(auto i=j.begin();i!=j.end();++i) {
        bool found=false;for(auto key:allowed)if(i.key()==key){found=true;break;}
        if(!found)throw std::invalid_argument("unsupported field: "+i.key());
    }
}
template<class T> void read(const J& j,const char* k,Field<T>& f) {
    if(!j.contains(k))return;
    if(j[k].is_null())f.set_null();else f.set(j[k].get<T>());
}
template<class T> void write(J& j,const char* k,const Field<T>& f) {
    if(f.present())j[k]=f.is_null()?J(nullptr):J(f.get());
}
Motion motion(const J& j) {
    if(!j.is_array()||j.size()!=4)throw std::invalid_argument("motion length");
    return {j.at(0),j.at(1),j.at(2),j.at(3)};
}
J as_json(const Motion& m){return J::array({m.x,m.y,m.vx,m.vy});}
void read_frame(const J& j,HeroFrame& f,bool strict=true) {
    if(strict)keys(j,{
#define KEY(n,k) k,
        PVZ72_HERO_NUMBERS(KEY) PVZ72_HERO_BOOLEANS(KEY) PVZ72_HERO_STRINGS(KEY)
#undef KEY
        "玩家位置","秘籍"});
#define R(n,k) read(j,k,f.n);
    PVZ72_HERO_NUMBERS(R) PVZ72_HERO_BOOLEANS(R) PVZ72_HERO_STRINGS(R)
#undef R
    if(j.contains("玩家位置")) {
        if(j["玩家位置"].is_null())f.position.set_null();else f.position.set(std::make_shared<Motion>(motion(j["玩家位置"])));
    }
    if(j.contains("秘籍")) {
        if(j["秘籍"].is_null())f.secrets.set_null();else f.secrets.set(std::make_shared<std::vector<std::string>>(j["秘籍"].get<std::vector<std::string>>()));
    }
}
void erase_frame(HeroFrame& f,const std::string& key) {
#define E(n,k) if(key==k){f.n.erase();return;}
    PVZ72_HERO_NUMBERS(E) PVZ72_HERO_BOOLEANS(E) PVZ72_HERO_STRINGS(E)
#undef E
    if(key=="玩家位置"){f.position.erase();return;}
    if(key=="秘籍"){f.secrets.erase();return;}
    throw std::invalid_argument("unknown frame field");
}
J as_json(const HeroFrame& f) {
    J j=J::object();
#define W(n,k) write(j,k,f.n);
    PVZ72_HERO_NUMBERS(W) PVZ72_HERO_BOOLEANS(W) PVZ72_HERO_STRINGS(W)
#undef W
    if(f.position.present())j["玩家位置"]=f.position.is_null()?J(nullptr):as_json(*f.position.get());
    if(f.secrets.present())j["秘籍"]=f.secrets.is_null()?J(nullptr):J(*f.secrets.get());
    return j;
}
void read_hero(const J& j,HeroState& h) {
    keys(j,{
#define KEY(n,k) k,
        PVZ72_HERO_NUMBERS(KEY) PVZ72_HERO_BOOLEANS(KEY) PVZ72_HERO_STRINGS(KEY)
#undef KEY
        "玩家位置","秘籍","_pvp_max_hp","_pvp_ice","_pvp_butter","_pvp_stun","_pvp_last_damage","_pvp_regen_progress","_pvp_seat","_pvp_pea_angle","_pvp_cold_until",
        "_pvp_previous_hp","_pvp_water_damage_clock","_pvp_masochist_ready","_pvp_sturdy_down"});
    read_frame(j,h.frame,false);
    read(j,"_pvp_max_hp",h.max_hp);read(j,"_pvp_ice",h.ice);read(j,"_pvp_butter",h.butter);read(j,"_pvp_stun",h.stun);
    read(j,"_pvp_last_damage",h.last_damage);read(j,"_pvp_regen_progress",h.regen_progress);read(j,"_pvp_pea_angle",h.pea_angle);
    read(j,"_pvp_cold_until",h.cold_until);
    read(j,"_pvp_previous_hp",h.previous_hp);read(j,"_pvp_water_damage_clock",h.water_damage_clock);
    read(j,"_pvp_masochist_ready",h.masochist_ready);read(j,"_pvp_sturdy_down",h.sturdy_down);
    if(j.contains("_pvp_seat"))h.actual_seat=parse_seat(j["_pvp_seat"].get<std::string>());
}
J as_json(const HeroState& h) {
    auto j=as_json(h.frame);write(j,"_pvp_max_hp",h.max_hp);write(j,"_pvp_ice",h.ice);write(j,"_pvp_butter",h.butter);
    write(j,"_pvp_stun",h.stun);write(j,"_pvp_last_damage",h.last_damage);write(j,"_pvp_regen_progress",h.regen_progress);write(j,"_pvp_pea_angle",h.pea_angle);
    write(j,"native_ticks",h.native_ticks);write(j,"landing_result",h.landing_result);
    write(j,"_pvp_cold_until",h.cold_until);write(j,"_pvp_balloon_hp",h.balloon_hp);write(j,"_pvp_previous_hp",h.previous_hp);
    write(j,"_pvp_floating_body",h.floating_body);write(j,"_pvp_rally_before",h.rally_before);write(j,"_pvp_rally_checked",h.rally_checked);write(j,"_pvp_rally_eligible",h.rally_eligible);
    write(j,"_pvp_water_damage_clock",h.water_damage_clock);write(j,"_pvp_masochist_ready",h.masochist_ready);write(j,"_pvp_sturdy_down",h.sturdy_down);
    if(h.avatar_source){write(j,"_pvp_owner",h.avatar_source->owner);write(j,"_pvp_id",h.avatar_source->id);}
    if(h.actual_seat)j["_pvp_seat"]=seat_name(*h.actual_seat);return j;
}
// Only the independent test boundary encodes Python tuple/list repr. Live
// code receives a typed attack token at creation, never JSON on every hit.
std::string pyrepr(const J& j) {
    if(j.is_null())return "None";if(j.is_boolean())return j.get<bool>()?"True":"False";
    if(j.is_string()) {
        const auto s=j.get<std::string>();const char q=s.find('\'')!=std::string::npos&&s.find('"')==std::string::npos?'"':'\'';
        std::string out(1,q);constexpr char hex[]="0123456789abcdef";
        for(unsigned char c:s){if(c==q||c=='\\'){out+='\\';out+=char(c);}else if(c=='\n')out+="\\n";else if(c=='\r')out+="\\r";else if(c=='\t')out+="\\t";else if(c<32||c==127){out+="\\x";out+=hex[c>>4];out+=hex[c&15];}else out+=char(c);}
        return out+q;
    }
    if(j.is_array()){std::string out="[";for(size_t i=0;i<j.size();++i){if(i)out+=", ";out+=pyrepr(j[i]);}return out+"]";}
    if(j.is_number())return j.dump();
    keys(j,{"tuple"});const auto& tuple=j.at("tuple");std::string out="(";
    for(size_t i=0;i<tuple.size();++i){if(i)out+=", ";out+=pyrepr(tuple[i]);}
    if(tuple.size()==1)out+=",";return out+")";
}
std::optional<std::string> attack(const J& j) {
    if(j.is_null())return std::nullopt;
    return j.is_string()?j.get<std::string>():pyrepr(j);
}
AttackIdentity attack_identity(const J& j) {
    if(j.is_null())return AttackIdentity::null();
    if(j.is_string())return AttackIdentity::literal(j.get<std::string>());
    if(j.is_boolean())return AttackIdentity::boolean(j.get<bool>());
    if(j.is_number_integer())return AttackIdentity::integer(j.get<int64_t>());
    if(j.is_number())throw std::invalid_argument("nonintegral native attack token");
    if(!j.is_array())keys(j,{"tuple"});
    const auto& values=j.is_array()?j:j.at("tuple");
    std::vector<AttackIdentity> atoms;for(const auto& value:values)atoms.push_back(attack_identity(value));
    return AttackIdentity::sequence(atoms,j.is_array());
}
std::shared_ptr<AttackSource> source(const J& j) {
    if(j.is_null())return {};
    keys(j,{"名","植物","僵尸","_pvp_plant_kind","_pvp_content","_pvp_variant","_pvp_fire_color","__pvz_sb_zombie_pea_fire",
        "_pvp_owner","_pvp_seat","魅惑","_pvp_no_hero_attack","_pvp_cattail","_pvp_melon_splash","_pvp_id","_pvp_instant_attack",
        "_pvp_original_owner","_pvp_source_entity","_pvp_root_source","_pvp_flight_limit_tiles","火了","位置",
        "_pvp_basket_last","_pvp_flight_last","_pvp_flight_distance","_pvp_flight_form","_pvp_melon_hits","_pvp_splash_done"});
    auto s=std::make_shared<AttackSource>();read(j,"名",s->projectile);read(j,"植物",s->plant);read(j,"僵尸",s->zombie);
    read(j,"_pvp_plant_kind",s->plant_kind);read(j,"_pvp_content",s->content);read(j,"_pvp_variant",s->variant);
    read(j,"_pvp_fire_color",s->fire_color);read(j,"__pvz_sb_zombie_pea_fire",s->zombie_fire);read(j,"魅惑",s->charmed);
    read(j,"_pvp_owner",s->owner);
    if(j.contains("_pvp_seat")&&!j["_pvp_seat"].is_null())s->seat=parse_seat(j["_pvp_seat"].get<std::string>());
    read(j,"_pvp_no_hero_attack",s->no_hero_attack);read(j,"_pvp_cattail",s->cattail);read(j,"_pvp_melon_splash",s->melon_splash);
    read(j,"_pvp_original_owner",s->original_owner);read(j,"_pvp_source_entity",s->source_entity);read(j,"_pvp_root_source",s->root_source);
    read(j,"_pvp_flight_limit_tiles",s->flight_limit_tiles);read(j,"火了",s->fire_lit);
    read(j,"_pvp_melon_hits",s->melon_hits);read(j,"_pvp_splash_done",s->splash_done);
    read(j,"_pvp_id",s->id);if(j.contains("_pvp_instant_attack"))s->instant_attack=attack_identity(j["_pvp_instant_attack"]);
    return s;
}
void read_point(const J& j,const char* key,Field<Point>& point) {
    if(!j.contains(key))return;if(j[key].is_null())point.set_null();else point.set(Point{j[key].at(0),j[key].at(1)});
}
void write_point(J& j,const char* key,const Field<Point>& point) {
    if(point.present())j[key]=point.is_null()?J(nullptr):J::array({point.get().x,point.get().y});
}
J source_state(const AttackSource& s,const std::optional<Motion>& position,const ProjectileFlight& flight) {
    J j=J::object();
    write(j,"名",s.projectile);write(j,"植物",s.plant);write(j,"僵尸",s.zombie);write(j,"_pvp_plant_kind",s.plant_kind);
    write(j,"_pvp_content",s.content);write(j,"_pvp_variant",s.variant);write(j,"_pvp_fire_color",s.fire_color);write(j,"__pvz_sb_zombie_pea_fire",s.zombie_fire);
    write(j,"_pvp_owner",s.owner);if(s.seat)j["_pvp_seat"]=seat_name(*s.seat);write(j,"魅惑",s.charmed);
    write(j,"_pvp_no_hero_attack",s.no_hero_attack);write(j,"_pvp_cattail",s.cattail);write(j,"_pvp_melon_splash",s.melon_splash);
    write(j,"_pvp_id",s.id);write(j,"_pvp_original_owner",s.original_owner);write(j,"_pvp_source_entity",s.source_entity);write(j,"_pvp_root_source",s.root_source);
    write(j,"_pvp_flight_limit_tiles",s.flight_limit_tiles);write(j,"火了",s.fire_lit);
    write(j,"_pvp_melon_hits",s.melon_hits);write(j,"_pvp_splash_done",s.splash_done);
    if(s.instant_attack)j["_pvp_instant_attack_text"]=s.instant_attack->hero_text();
    if(position)j["位置"]=as_json(*position);
    write_point(j,"_pvp_basket_last",flight.basket_last);write_point(j,"_pvp_flight_last",flight.last);write(j,"_pvp_flight_distance",flight.distance);
    if(flight.form.present())j["_pvp_flight_form"]=flight.form.is_null()?J(nullptr):J::array({flight.form.get().name,flight.form.get().fire_lit,flight.form.get().zombie_fire});
    return j;
}
HeroHit hit(const J& j) {
    const std::string s=j;if(s=="normal")return HeroHit::normal;if(s=="ash")return HeroHit::ash;if(s=="swallow")return HeroHit::swallow;if(s=="content")return HeroHit::content;if(s=="lightning")return HeroHit::lightning;if(s=="spring")return HeroHit::spring;if(s=="grenade")return HeroHit::grenade;
    throw std::invalid_argument("unknown hit");
}
CombatPhase phase(const std::string& s) {
    if(s=="plants")return CombatPhase::plants;if(s=="zombies")return CombatPhase::zombies;if(s=="entities")return CombatPhase::entities;
    if(s=="summon")return CombatPhase::summon;if(s=="other")return CombatPhase::other;if(s=="content")return CombatPhase::content;throw std::invalid_argument("unknown phase");
}
std::string phase_name(CombatPhase p){switch(p){case CombatPhase::plants:return "plants";case CombatPhase::zombies:return "zombies";case CombatPhase::entities:return "entities";case CombatPhase::content:return "content";case CombatPhase::summon:return "summon";default:return "other";}}
std::optional<HeroConversion> conversion(const std::string& key) {
    if(key=="魅惑")return HeroConversion::charm;if(key=="死亡")return HeroConversion::death;
    if(key=="消亡")return HeroConversion::expiry;if(key=="出土")return HeroConversion::emerge;
    if(key=="僵尸")return HeroConversion::kind;if(key=="大小")return HeroConversion::size;
    if(key=="防具")return HeroConversion::armor;if(key=="防具血量")return HeroConversion::armor_hp;
    if(key=="手持")return HeroConversion::hand;if(key=="手持血量")return HeroConversion::hand_hp;return {};
}
J event_state(const BattleEvent& event) {
    if(const auto* e=std::get_if<HeroDamageEvent>(&event)) {
        if(e->type==HeroDamageEvent::Type::damage)return {{"type","damage"},{"target",seat_name(e->seat)},{"amount",e->amount},{"kind",hit_name(e->hit)},{"source_entity",e->source_id?J(*e->source_id):J(nullptr)},{"native",true}};
        if(e->type==HeroDamageEvent::Type::last_stand_start)return {{"type","zsecret_last_stand"},{"side",seat_name(e->seat)},{"seconds",e->amount}};
        return {{"type","zsecret_last_stand_end"},{"side",seat_name(e->seat)}};
    }
    if(const auto* e=std::get_if<RelicEvent>(&event))return {{"type","zsecret_relic"},{"entity",e->entity?J(*e->entity):J(nullptr)},{"seconds",e->seconds}};
    if(const auto* e=std::get_if<BasketballHitEvent>(&event))return {{"type","zombie_basket_hit"},{"source",e->source?J(*e->source):J(nullptr)},{"target",e->target}};
    if(const auto* e=std::get_if<SquashSplashEvent>(&event))return {{"type","squash_splash"},{"entity",e->entity?J(*e->entity):J(nullptr)}};
    if(const auto* e=std::get_if<ZombieHeroPeaEvent>(&event))return {{"type","zsecret_hero_pea"},{"side",seat_name(e->seat)}};
    if(const auto* e=std::get_if<RallyRiseEvent>(&event))return {{"type","rally_rise_check"},{"side",seat_name(e->seat)},{"eligible",true},{"early",e->early}};
    if(const auto* e=std::get_if<ResourceIncomeEvent>(&event)){
        J item={{"type","income"},{"side",seat_name(e->seat)},{"amount",e->amount},{"source",e->source},{"resource_id",e->id}};
        if(e->shared_auto)item["shared_auto"]=true;
        return item;
    }
    if(const auto* e=std::get_if<CoinIncomeEvent>(&event))return {{"type","coin"},{"side",seat_name(e->seat)},{"amount",e->amount},{"resource_id",e->id}};
    if(const auto* e=std::get_if<EnvironmentalDamageEvent>(&event))return {{"type","damage"},{"target",seat_name(e->seat)},{"amount",e->amount},{"kind","deathmatch_water"}};
    if(const auto* e=std::get_if<HeroHealEvent>(&event))return {{"type","heal"},{"target",seat_name(e->seat)},{"amount",e->amount},{"kind","out_of_combat"}};
    if(const auto* e=std::get_if<SturdyEvent>(&event))return {{"type","sturdy"},{"side",seat_name(e->seat)},{"cards",e->cards}};
    if(const auto* e=std::get_if<GraveWokenEvent>(&event))return {{"type","grave_woken"},{"entity",e->entity?J(*e->entity):J(nullptr)},{"cause",e->cause}};
    const auto& e=std::get<MelonSplashEvent>(event);return {{"type","melon_splash"},{"x",e.position.x},{"y",e.position.y},{"side",e.owner?J(seat_name(*e.owner)):J(nullptr)},{"source_entity",e.source?J(*e.source):J(nullptr)}};
}
J proxy_state(const HeroProxyState& p,Seat side) {
    J j={{"僵尸",p.kind},{"防具",p.armor},{"手持",p.hand},{"血量",p.hp},{"防具血量",p.armor_hp},
         {"手持血量",p.hand_hp},{"方向",p.facing},{"位置",p.position?as_json(*p.position):J(nullptr)},{"受伤",p.hurt},{"手持受伤",p.hand_hurt},
         {"_pvp_hero",seat_name(side)}};
    write(j,"_pvp_owner",p.source.owner);write(j,"_pvp_id",p.source.id);
    write(j,"灰烬",p.ash);write(j,"气球",p.balloon);write(j,"大小",p.size);write(j,"狂暴",p.berserk);
    write(j,"撑杆",p.pole_vault);write(j,"跳舞",p.dancing);write(j,"入水",p.in_water);
    write(j,"冰冻",p.ice);write(j,"黄油",p.butter);write(j,"眩晕",p.stun);write(j,"牛顿",p.gravity);
    write(j,"__pvz_sb_chili_zombie_row_hint",p.chili_row_hint);
    write(j,"__pvz_sb_zombie_observed_max_hp",p.observed_max_hp);write(j,"__pvz_sb_plant_zombie_max_hp",p.plant_max_hp);
    if(p.dead.present())j["死"]=p.dead.is_null()?J(nullptr):p.dead.get().boolean_encoding()?J(p.dead.get().number()!=0.):J(p.dead.get().number());
#define NUM(n,k) write(j,k,p.native.n);
    PVZ72_ZOMBIE_NATIVE_NUMBERS(NUM)
#undef NUM
    write_point(j,"出场初位置",p.native.entry_start);write_point(j,"出场末位置",p.native.entry_end);write_point(j,"绳初位置",p.native.rope_start);
    write(j,"出土",p.native.emerged);write(j,"手持动画",p.native.hand_animation);return j;
}
J snapshot(const HeroCombat& w,const CombatRuntime& v,const std::vector<std::shared_ptr<AttackSource>>& sources) {
    J j={{"heroes",J::object()},{"players",J::object()},{"globals",as_json(w.globals)},{"water_ice",w.water_ice},{"sequence",w.sequence},
         {"budgets",J::array()},{"events",J::array()},{"proxies",J::object()},{"sounds",J::array()},{"particles",J::array()},
         {"particle_state",J::array()},{"rng",J::array()},{"last_stand",J::object()},{"last_stand_used",J::array()},{"source_ids",J::array()},{"active",nullptr}};
    for(size_t i=0;i<4;++i) {
        const auto s=Seat(i);const std::string key(seat_name(s));
        if(w.contains(s))j["heroes"][key]=as_json(w.hero(s));
        if(w.players[i]){const auto& p=*w.players[i];j["players"][key]={{"hp",p.hp},{"marked_until",p.marked_until},{"hero_damage",p.hero_damage},{"secrets",p.secrets}};}
        if(w.proxies[i])j["proxies"][key]=proxy_state(*w.proxies[i],s);
        if(w.last_stand_used[i])j["last_stand_used"].push_back(key);
    }
    for(auto s:w.last_stand_order)j["last_stand"][seat_name(s)]=*w.last_stand[seat_index(s)];
    for(const auto& b:w.budgets())j["budgets"].push_back(J::array({J::array({seat_name(b.key.seat),hit_name(b.key.hit),b.key.attack}),J::array({b.tick,b.used})}));
    for(const auto& e:w.events)if(!std::holds_alternative<RelicEvent>(e)&&!std::holds_alternative<BasketballHitEvent>(e)&&!std::holds_alternative<MelonSplashEvent>(e))j["events"].push_back(event_state(e));
    for(const auto& s:v.sounds)j["sounds"].push_back(s.name);
    for(const auto& p:v.particles)j["particles"].push_back(J::array({p.name,J::array({p.position.x,p.position.y}),p.count}));
    for(const auto& p:v.particle_state)j["particle_state"].push_back(J::array({p.color,as_json(p.motion),p.age}));
    const auto rng=v.rng.state();for(auto n:rng.mt)j["rng"].push_back(n);j["rng"].push_back(rng.mti);
    for(const auto& s:sources)j["source_ids"].push_back(s&&s->id.present()&&!s->id.is_null()?J(s->id.get()):J(nullptr));
    if(w.active)j["active"]={{"target",seat_name(w.active->target)},{"owner",seat_name(w.active->owner)},{"phase",phase_name(w.active->phase)}};
    return j;
}
struct Probe {
    TypedBattleState battle;
    CombatRuntime& visual=battle.runtime;
    HeroCombat& world=battle.heroes;
    std::vector<std::shared_ptr<AttackSource>> sources;
    std::vector<std::optional<Motion>> positions;
    std::vector<ProjectileFlight> flights;
    std::vector<ChiliAttackKey> chili_keys;
    std::vector<std::shared_ptr<AttackSource>> held_proxy_sources;
    bool tagging = false;
    J states=J::array();
    explicit Probe(int64_t seed):battle(seed){battle.native_plant_zombies_installed=false;battle.terrain.periodic_x=false;}
    virtual ~Probe()=default;
    virtual bool extra_operation(const J&,J&){return false;}
    virtual void extra_snapshot(J&){}
    virtual std::shared_ptr<AttackSource> selected_source(const J& op) {
        if(op.contains("unit_source"))throw std::invalid_argument("unit source unsupported by hero-only probe");
        return op.contains("source")&&!op["source"].is_null()?sources.at(op["source"].get<size_t>()):nullptr;
    }
    void operations(const J& ops,bool record=true) {
        for(const auto& op:ops) {
            const std::string action=op.at("op");J result=nullptr;
            if(action=="context") {
                keys(op,{"op","target","owner","phase","source","attack","body","unit_source","entity_source"});
                auto s=selected_source(op);
                HeroSelection select{parse_seat(op.at("target").get<std::string>()),parse_seat(op.at("owner").get<std::string>()),phase(op.at("phase")),s,attack(op.value("attack",J(nullptr)))};
                HeroContext context(world,std::move(select));operations(op.at("body"),record);context.close();
            } else if(action=="batch") {
                keys(op,{"op","body"});operations(op.at("body"),false);
            } else if(action=="damage") {
                keys(op,{"op","target","amount","kind"});result=world.damage(parse_seat(op.at("target").get<std::string>()),op.at("amount"),hit(op.value("kind",J("normal"))));
            } else if(action=="player_damage") {
                keys(op,{"op","amount"});auto r=world.player_damage(op.at("amount"));result=r?J(*r):J(nullptr);
            } else if(action=="source_amount") {
                keys(op,{"op","target"});auto r=world.source_amount(parse_seat(op.at("target").get<std::string>()));result=r?J(*r):J(nullptr);
            } else if(action=="write") {
                keys(op,{"op","target","values","erase"});
                const std::string target=op.at("target");auto& f=target=="globals"?world.globals:world.hero(parse_seat(target)).frame;
                if(op.contains("values"))read_frame(op["values"],f);
                if(op.contains("erase"))for(const auto& key:op["erase"])erase_frame(f,key.get<std::string>());
            } else if(action=="position") {
                keys(op,{"op","target","values"});const std::string target=op.at("target");
                auto& f=target=="globals"?world.globals:world.hero(parse_seat(target)).frame;*f.position.get()=motion(op.at("values"));
            } else if(action=="proxy_try") {
                keys(op,{"op","target"});const auto side=parse_seat(op.at("target").get<std::string>());
                const auto roster=battle.targets;const auto count=roster->size();
                bool caught=false;try{world.proxy(side);}catch(const std::exception&){caught=true;}
                result={{"caught",caught},{"roster_preserved",battle.targets==roster&&roster->size()==count}};
            } else if(action=="proxy_inspect") {
                keys(op,{"op","target"});const auto side=parse_seat(op.at("target").get<std::string>());
                const auto& p=world.cached_proxy(side);const auto& f=world.hero(side).frame;
                result={{"position_alias",f.position.present()&&!f.position.is_null()&&p.position==f.position.get()},
                        {"source_kind",p.source.zombie_name()},{"source_owner",p.source.owner.get()},{"in_world_units",false}};
                for(const auto& t:*battle.targets)if(t.is_hero()&&t.hero==side)result["in_world_units"]=true;
            } else if(action=="rng_advance") {
                keys(op,{"op","low","high"});result=visual.rng.randint(op.at("low"),op.at("high"));
            } else if(action=="proxy_hold") {
                keys(op,{"op","target"});const auto side=parse_seat(op.at("target").get<std::string>());world.proxy(side);
                held_proxy_sources.push_back(world.proxy_source(side));
            } else if(action=="proxy_forget") {
                keys(op,{"op","target"});world.proxies.at(seat_index(parse_seat(op.at("target").get<std::string>()))).reset();
            } else if(action=="proxy_held_kinds") {
                keys(op,{"op"});result=J::array();for(const auto& s:held_proxy_sources)result.push_back(s->zombie_name());
            } else if(action=="proxy"||action=="proxy_write") {
                keys(op,{"op","target","key","value"});const auto side=parse_seat(op.at("target").get<std::string>());
                if(action=="proxy")world.proxy(side);
                else {
                    const std::string k=op.at("key");
                    if(const auto c=conversion(k))world.write_proxy_conversion(side,*c);
                    else if(k=="血量")world.write_proxy_hp(side,op.at("value"));else if(k=="灰烬")world.write_proxy_ash(side);
                    else if(k=="冰冻"||k=="黄油"||k=="眩晕")world.write_proxy_status(side,k=="冰冻"?HeroStatus::ice:k=="黄油"?HeroStatus::butter:HeroStatus::stun,op.at("value"));
                    else throw std::invalid_argument("unsupported proxy write");
                }
            } else if(action=="clock") {
                keys(op,{"op","tick","time"});world.tick=op.at("tick");world.time=op.at("time");
            } else if(action=="last_stand_step") {
                keys(op,{"op"});world.step_last_stand();
            } else if(action=="index") {
                keys(op,{"op","value"});world.source_index=op.at("value").is_null()?std::optional<int64_t>{}:std::optional<int64_t>(op["value"].get<int64_t>());
            } else if(action=="owner") {
                keys(op,{"op"});auto r=world.owner();result=r?J(seat_name(*r)):J(nullptr);
            } else if(action=="tag") {
                keys(op,{"op","entity","owner","source"});const auto i=op.at("entity").get<size_t>();
                const auto parent=op.contains("source")&&!op["source"].is_null()?sources.at(op["source"].get<size_t>()):nullptr;
                const auto owner=op.contains("owner")&&!op["owner"].is_null()?std::optional<Seat>(parse_seat(op["owner"].get<std::string>())):std::nullopt;
                world.tag_entity(sources.at(i),positions.at(i)?&*positions[i]:nullptr,flights.at(i),owner,parent);
            } else if(action=="begin_flight") {
                keys(op,{"op","entity","source"});const auto i=op.at("entity").get<size_t>();
                const auto parent=op.contains("source")&&!op["source"].is_null()?sources.at(op["source"].get<size_t>()):nullptr;
                begin_flight(*sources.at(i),flights.at(i),positions.at(i)?&*positions[i]:nullptr,parent.get());
            } else if(action=="source_position") {
                keys(op,{"op","source","value"});positions.at(op.at("source").get<size_t>())=motion(op.at("value"));
            } else if(action=="chili_key") {
                keys(op,{"op"});auto key=world.chili_attack_key();size_t i=0;
                for(;i<chili_keys.size();++i)if(chili_keys[i]==key)break;
                if(i==chili_keys.size())chili_keys.push_back(std::move(key));result=i;
            } else if(!extra_operation(op,result))throw std::invalid_argument("unknown operation: "+action);
            if(record){auto row=snapshot(world,visual,sources);row["op"]=action;row["result"]=std::move(result);
                if(tagging){row["source_state"]=J::array();for(size_t i=0;i<sources.size();++i)row["source_state"].push_back(sources[i]?source_state(*sources[i],positions[i],flights[i]):J(nullptr));}
                extra_snapshot(row);
                states.push_back(std::move(row));}
        }
    }
};
void configure_probe(Probe& p,const J& j) {
    keys(j,{"seed","heroes","players","globals","sources","phase_sources","aliases","operations","tick","time","mark_seconds","damage_factors","last_stand","damage_events","presentation","tagging"});
    auto& w=p.world;
    read_frame(j.at("globals"),w.globals);
    for(auto i=j.at("heroes").begin();i!=j.at("heroes").end();++i) {
        const auto k=seat_index(parse_seat(i.key()));w.heroes[k].emplace();read_hero(i.value(),*w.heroes[k]);
    }
    if(j.contains("aliases"))for(auto i=j["aliases"].begin();i!=j["aliases"].end();++i)w.aliases[seat_index(parse_seat(i.key()))]=seat_index(parse_seat(i.value().get<std::string>()));
    for(auto i=j.at("players").begin();i!=j.at("players").end();++i) {
        keys(i.value(),{"secrets","hp","marked_until","hero_damage"});const auto& a=i.value();
        w.players[seat_index(parse_seat(i.key()))]=HeroPlayer{a.value("secrets",std::vector<std::string>{}),a.value("hp",40.),a.value("marked_until",0.),a.value("hero_damage",0.)};
    }
    w.tick=j.value("tick",0);w.time=j.value("time",0.);w.mark_seconds=j.value("mark_seconds",8.);
    w.damage_factors_enabled=j.value("damage_factors",true);w.last_stand_enabled=j.value("last_stand",true);w.damage_events_enabled=j.value("damage_events",true);
    p.tagging=j.value("tagging",false);
    for(const auto& s:j.at("sources")) {
        p.sources.push_back(source(s));p.positions.push_back(s.contains("位置")?std::optional<Motion>(motion(s["位置"])):std::nullopt);
        p.flights.emplace_back();auto& flight=p.flights.back();
        read_point(s,"_pvp_basket_last",flight.basket_last);read_point(s,"_pvp_flight_last",flight.last);read(s,"_pvp_flight_distance",flight.distance);
        if(s.contains("_pvp_flight_form")){if(s["_pvp_flight_form"].is_null())flight.form.set_null();else {const auto& f=s["_pvp_flight_form"];flight.form.set(ProjectileForm{f.at(0).get<std::string>(),f.at(1).get<bool>(),f.at(2).get<std::string>()});}}
    }
    if(j.contains("phase_sources"))for(auto i=j["phase_sources"].begin();i!=j["phase_sources"].end();++i) {
        const auto ph=phase(i.key());if(ph==CombatPhase::other||ph==CombatPhase::content)throw std::invalid_argument("unknown source list");
        for(const auto& index:i.value())w.phase_sources[size_t(ph)].push_back(index.is_null()?nullptr:p.sources.at(index.get<size_t>()));
    }
    if(j.contains("presentation")) {
        const auto& a=j["presentation"];keys(a,{"enabled","camera","screen_width","atlas"});
        p.visual.presentation.enabled=a.value("enabled",false);const auto camera=a.value("camera",J::array({0.,0.}));
        p.visual.presentation.camera={camera.at(0),camera.at(1)};p.visual.presentation.screen_width=a.value("screen_width",1152.);
        const auto atlas=a.value("atlas",J::object());for(auto i=atlas.begin();i!=atlas.end();++i) {
            keys(i.value(),{"width","height","pixels"});const auto& s=i.value();
            p.visual.presentation.atlas.emplace(i.key(),SpritePixels{s.at("width"),s.at("height"),s.at("pixels").get<std::vector<Color>>()});
        }
    }
}
J run(const J& j){Probe p(j.value("seed",int64_t(1)));configure_probe(p,j);p.operations(j.at("operations"));return p.states;}
}
#ifndef PVZ72_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc==2&&std::string(argv[1])=="--capabilities") {
            std::cout<<J({{"backend_actual","typed72-hero-chain"},{"full_battle_supported",false},{"fallback_count",0}}).dump()<<'\n';return 0;
        }
        if(argc!=3)throw std::invalid_argument("usage: hero72_probe input.jsonl output.jsonl");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("cannot open probe files");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run(J::parse(line)).dump()<<'\n';
        if(!output)throw std::runtime_error("cannot write probe result");
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
#endif
