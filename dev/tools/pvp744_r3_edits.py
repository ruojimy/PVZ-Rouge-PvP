"""One-time, exact-anchor source edits for the r3 feedback work."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
K='build/typed72-integrated-v44/source/src/sim/typed/'
def edit(name,old,new):
    p=ROOT/name;s=p.read_text(encoding='utf-8');assert old in s,(name,old[:120]);p.write_text(s.replace(old,new,1),encoding='utf-8',newline='\n')
def attention():
    edit(K+'targets.h','#include "sim/typed/terraria_state.h"','#include "sim/typed/terraria_state.h"\n#include "sim/typed/attention_state.h"')
    edit(K+'targets.h','struct CombatZombie {','struct CombatZombie {\n    AttentionState attention;')
    edit(K+'targets.h','unit->source.unit.bind(unit);','unit->source.unit.bind(unit);if(unit->attention.enabled())unit->source.attention_origin=unit;')
    edit(K+'attack_source.h','    EntitySourceLink entity;','    std::weak_ptr<CombatZombie> attention_origin; // attribution survives projectile metadata copies\n    EntitySourceLink entity;')
    edit(K+'cold_catalog.h','    Field<double> defense;','    Field<double> attention_hits,attention_seconds; // opt-in, independent unless explicitly linked\n    Field<double> defense;')
    edit(K+'cold_registration.cpp','        if(card.defense.present())z.body.defense=card.defense;','        if(card.defense.present())z.body.defense=card.defense;\n        z.attention.hits=int(card.attention_hits.or_missing(0.));z.attention.seconds=card.attention_seconds.or_missing(0.);')
    edit(K+'terraria_bosses.cpp','#include "sim/typed/terraria_bosses.h"','#include "sim/typed/terraria_bosses.h"\n#include "sim/typed/attention.h"')
    edit(K+'terraria_bosses.cpp','c.defense.set(npc.defense);','c.defense.set(npc.defense);c.attention_hits.set(npc.type>=13&&npc.type<=15?1.:3.);c.attention_seconds.set(npc.type>=13&&npc.type<=15?10.:6.);')
    edit(K+'terraria_bosses.cpp','auto list=enemies();auto& n=*u->terraria;','auto owner=attention_owner(u);if(owner!=u){auto result=target(owner,closest);u->terraria->target_id=owner->terraria->target_id;return result;}auto list=enemies();attention_prefer(owner,list,world_.heroes.time);auto& n=*u->terraria;')
    edit(K+'hero.cpp','#include "sim/typed/targets.h"','#include "sim/typed/targets.h"\n#include "sim/typed/attention.h"')
    edit(K+'hero.cpp','    sync_proxies();return amount;','    attention_damage(s,CombatTarget::player(hero(side).actual_seat.value_or(side)),amount,time);\n    sync_proxies();return amount;')
    edit(K+'content_target.cpp','#include "sim/typed/content_target.h"','#include "sim/typed/content_target.h"\n#include "sim/typed/attention.h"')
    edit(K+'content_target.cpp','        plant.hp.set(old-loss);plant.hurt.set(1.);','        plant.hp.set(old-loss);plant.hurt.set(1.);\n        attention_damage(source,target,std::min(std::max(0.,old),loss),heroes.time);')
    edit(K+'targets.cpp','#include "sim/typed/targets.h"','#include "sim/typed/targets.h"\n#include "sim/typed/attention.h"')
    edit(K+'targets.cpp','    const double head_hp=target->body.armor_hp,hand_hp=target->body.hand_hp;','    const auto attacker=heroes_.source();const double body_hp=std::max(0.,target->body.hp);\n    const double head_hp=target->body.armor_hp,hand_hp=target->body.hand_hp;')
    edit(K+'targets.cpp','    if(failure)std::rethrow_exception(failure);return result;','    if(failure)std::rethrow_exception(failure);\n    const double loss=body_hp-std::max(0.,target->body.hp)+std::max(0.,head_hp)-std::max(0.,target->body.armor_hp)+std::max(0.,hand_hp)-std::max(0.,target->body.hand_hp);\n    attention_damage(attacker,CombatTarget::zombie(target),loss,heroes_.time);return result;')
    edit(K+'content_queries.cpp','#include "sim/typed/content_queries.h"','#include "sim/typed/content_queries.h"\n#include "sim/typed/attention.h"')
    edit(K+'content_queries.cpp','    if(!spatial741_enabled()){auto all=enemies(source(origin));','    const auto unit=attention_owner(source(origin));\n    if((unit&&unit->attention.enabled())||!spatial741_enabled()){auto all=enemies(source(origin));attention_prefer(unit,all,world_.heroes.time);')
    edit(K+'content_queries.cpp','    if(spatial741_enabled())return spatial_nearest(origin);','    const auto unit=attention_owner(source(origin));\n    if(spatial741_enabled()&&(!unit||!unit->attention.enabled()))return spatial_nearest(origin);')
    edit(K+'content_queries.cpp','    std::optional<ContentTarget> nearest,hero;','    attention_prefer(unit,candidates,world_.heroes.time);\n    std::optional<ContentTarget> nearest,hero;')
    edit(K+'content_queries.cpp','    return taunts_.taunt_target(origin,std::move(nearest));','    auto result=taunts_.taunt_target(origin,nearest);\n    if(unit&&unit->attention.enabled()&&result&&std::find(candidates.begin(),candidates.end(),*result)==candidates.end())return nearest;\n    return result;')
    edit('build/typed72-match-v1/match_probe.cpp','u->body.defense.set(def.defense);u->body.external_lifecycle','u->body.defense.set(def.defense);u->attention.hits=type>=13&&type<=15?1:3;u->attention.seconds=type>=13&&type<=15?10.:6.;u->body.external_lifecycle')
    edit('build/typed72-match-v1/match_probe.cpp','        if(u.terraria){const auto& t=','        if(u.attention.enabled())j["attention"]={{"hits",u.attention.hits},{"seconds",u.attention.seconds},{"last",u.attention.last},{"consecutive",u.attention.consecutive},{"marked",u.attention.marked}};\n        if(u.terraria){const auto& t=')
    edit('build/typed72-match-v1/match_probe.cpp','                if(k=="防御"){assign(z.body.defense,v);continue;}','                if(k=="防御"){assign(z.body.defense,v);continue;}\n                if(k=="注意力次数"){z.attention.hits=std::max(0,v.get<int>());continue;}\n                if(k=="注意力时间"){z.attention.seconds=std::max(0.,v.get<double>());continue;}')
    edit('build/typed72-match-v1/snapshot_layer.inc','        if(c.defense.present())j["defense"]=opt_json(c.defense);','        if(c.defense.present())j["defense"]=opt_json(c.defense);\n        if(c.attention_hits.present())j["attention_hits"]=opt_json(c.attention_hits);\n        if(c.attention_seconds.present())j["attention_seconds"]=opt_json(c.attention_seconds);')
if __name__=='__main__':attention()
