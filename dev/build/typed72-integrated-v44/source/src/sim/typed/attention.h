#pragma once
#include "sim/typed/content_target.h"
#include "sim/typed/plant_lookup.h"
namespace pvz::typed72 {
inline ZombieRef attention_owner(ZombieRef u){
    // Only connected Eater segments explicitly share attention. Broken links
    // stop traversal immediately, before the segment transforms into a head.
    for(int i=0;u&&u->terraria&&u->terraria->type>=13&&u->terraria->type<=15&&i<700;++i){
        auto ahead=u->terraria->ahead.lock();
        if(!ahead||ahead->body.hp<=0.||!ahead->terraria||ahead->terraria->removed)break;
        u=std::move(ahead);
    }return u;
}
inline ZombieRef attention_owner(const std::shared_ptr<AttackSource>& s){return s?attention_owner(s->unit.lock()?s->unit.lock():s->attention_origin.lock()):ZombieRef{};}
inline std::string attention_id(const ContentTarget& t){
    if(const auto* p=std::get_if<PlantRef>(&t))return (*p)->source.id.or_missing("p"+std::to_string((*p)->identity.value));
    const auto& z=std::get<CombatTarget>(t);return z.is_hero()?"hero:"+std::string(seat_name(z.hero)):z.unit->source.id.or_missing("z"+std::to_string(z.unit->identity.value));
}
inline void attention_damage(const std::shared_ptr<AttackSource>& source,const ContentTarget& target,double amount,double now){
    if(auto u=attention_owner(source))u->attention.damage(attention_id(target),amount,now);
}
inline void attention_prefer(const ZombieRef& source,std::vector<ContentTarget>& candidates,double now){
    auto u=attention_owner(source);if(!u||!u->attention.enabled())return;
    // All marked is a fallback, never a reason to idle or retreat.
    if(std::any_of(candidates.begin(),candidates.end(),[&](const auto& t){return !u->attention.contains(attention_id(t),now);}))
        std::erase_if(candidates,[&](const auto& t){return u->attention.contains(attention_id(t),now);});
}
inline std::vector<ContentTarget> attention_enemies(TypedBattleState& w,const ZombieRef& u){
    std::vector<ContentTarget> out;const auto owner=w.heroes.owner(source_ref(u));
    if(owner==Seat::zombie)for(const auto& p:*w.plant_roster)if(september_targetable(*p))out.emplace_back(p);
    for(const auto& t:*w.targets)if(t.unit&&t.unit->body.hp>0.&&!t.unit->body.ash.present()&&w.heroes.owner(source_ref(t.unit))!=owner)out.emplace_back(t);
    if(!u->source.no_hero_attack.or_missing(false))for(auto s:seats_for(w.mode))if(!(w.solo.izombie()&&team_of(s)==Seat::zombie)&&team_of(s)!=owner&&w.heroes.contains(s)&&w.heroes.hero(s).frame.hp.get()>0.)out.emplace_back(CombatTarget::player(s));
    attention_prefer(u,out,w.heroes.time);return out;
}
inline bool attention_accepts(TypedBattleState& w,const ZombieRef& u,const ContentTarget& t){
    auto a=attention_owner(u);if(!a||!a->attention.contains(attention_id(t),w.heroes.time))return true;
    auto list=attention_enemies(w,u);return std::find(list.begin(),list.end(),t)!=list.end();
}
}
