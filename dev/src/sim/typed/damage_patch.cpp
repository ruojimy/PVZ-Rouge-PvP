#include "sim/typed/damage_patch.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
namespace {
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
std::string_view name(const Field<std::string>& f){return f.present()&&!f.is_null()?f.get():std::string_view{};}
double number(const Field<double>& f,double fallback){return f.present()&&!f.is_null()?f.get():fallback;}
bool eligible(const CombatZombie& u){return !u.body.ash.present()&&!(u.body.hp<=-1000.||u.body.hp>0.);}
}
void DamagePatch::remember_max_hp(CombatZombie& u) {
    const double hp=u.body.hp;if(hp<=0.)return;
    if(hp>number(u.patch.observed_max_hp,hp)||!u.patch.observed_max_hp.present())u.patch.observed_max_hp.set(hp);
    if(yes(u.patch.plant_zombie)&&(hp>number(u.patch.plant_max_hp,hp)||!u.patch.plant_max_hp.present()))u.patch.plant_max_hp.set(hp);
}
double DamagePatch::bite_amount(const ZombieRef& target,double amount,const NativeDamageOrigin& origin) const {
    if(!origin.charm_bite_site||!origin.current_charmed||!origin.other)return amount;
    if(!origin.current_charmed->source.charmed.present()||origin.other->source.charmed.present())return amount;
    ZombieRef source;
    if(target==origin.current_charmed)source=origin.other;
    else if(target==origin.other)source=origin.current_charmed;
    else return amount;
    amount=name(source->patch.plant_name)=="墓碑吞噬者僵尸"?60.:10.;
    const auto& secrets=heroes_.globals.secrets;
    if(target->source.charmed.present()&&!source->source.charmed.present()&&secrets.present()&&!secrets.is_null()&&secrets.get()&&
        std::find(secrets.get()->begin(),secrets.get()->end(),"魅惑")!=secrets.get()->end())amount*=.5;
    return amount;
}
void DamagePatch::pumpkin_sound(const ZombieRef& target,double amount) {
    const auto& z=target->body;
    // The original predicate has no ash check; even that RNG consumption is
    // observable before raw damage returns early for an already ashed unit.
    if(z.armor=="南瓜头防具"&&z.armor_hp>0.&&amount<z.armor_hp+z.hp) {
        runtime_.sound("路障"+std::to_string(runtime_.rng.randint(1,2)),z.motion.get());++counters.pumpkin_sound;
    }
}
HitResult DamagePatch::ordinary(const ZombieRef& unit,double facing,double amount){return ordinary_from(unit,facing,amount,{});}
HitResult DamagePatch::surface(const ZombieRef& unit,double facing,double amount){return surface_from(unit,facing,amount,{});}
HitResult DamagePatch::ash(const ZombieRef& unit){return ash_from(unit,{});}
HitResult DamagePatch::ordinary_from(const ZombieRef& unit,double facing,double amount,const NativeDamageOrigin& origin) {
    const double old=amount;amount=bite_amount(unit,amount,origin);if(std::abs(amount-old)>.001)++counters.charm_bite;
    if(origin.entity) {
        if(origin.entity->enemy_squash){++counters.squash_skipped;return HitResult::flag(false);}
        if(origin.entity->blue_tripea&&amount<30.){amount=30.;++counters.blue_damage;}
    }
    remember_max_hp(*unit);pumpkin_sound(unit,amount);damage_zombie(runtime_,unit->body,facing,amount);
    try{effects_.plant_zombie_deaths(unit);}catch(const std::exception&){}return {};
}
HitResult DamagePatch::surface_from(const ZombieRef& unit,double facing,double amount,const NativeDamageOrigin& origin) {
    if(origin.entity) {
        if(origin.entity->enemy_squash){++counters.squash_skipped;return HitResult::flag(false);}
        if(origin.entity->blue_tripea) {
            const double boosted=std::max(30.,amount);
            if(unit->body.hand=="钢门"||unit->body.hand=="梯子") {
                // The source wraps the entire boost branch in try/except.
                // A failed nested damage falls through to original surface.
                try {
                    if(!origin.entity->tracking_present)try{knockback(unit,facing*runtime_.plk*200.);}catch(const std::exception&){}
                    nested_ordinary(unit,facing,boosted);++counters.blue_surface;return HitResult::flag(true);
                }catch(const std::exception&){}
            }else if(boosted!=amount){amount=boosted;++counters.blue_surface;}
        }
    }
    remember_max_hp(*unit);const auto result=surface_hand_damage(runtime_,unit->body,facing,amount);
    if(result==SurfaceDamageResult::armorless)nested_ordinary(unit,facing,amount);
    try{effects_.plant_zombie_deaths(unit);}catch(const std::exception&){}return HitResult::flag(result==SurfaceDamageResult::hand_hit);
}
HitResult DamagePatch::ash_from(const ZombieRef& unit,const NativeDamageOrigin& origin) {
    if(origin.native_horizontal_chili){++counters.chili_skipped;return {};}
    if(origin.entity&&origin.entity->enemy_squash){++counters.squash_skipped;return {};}
    const auto index=effects_.zombie_index(unit);auto& z=unit->body;
    if(z.hp+z.armor_hp>500.)nested_ordinary(unit,1.,std::find(bosses.begin(),bosses.end(),z.kind)!=bosses.end()?300.:500.);
    else z.ash.set(0.);
    try{effects_.plant_zombie_deaths(index);}catch(const std::exception&){}return {};
}
void DamagePatch::knockback(const ZombieRef& unit,double amount) {
    auto& u=*unit;const double resistance=number(u.patch.knockback,0.);
    if(resistance!=0.)amount*=std::clamp(u.patch.knockback_is_boolean?(name(u.patch.plant_name)=="高坚果僵尸"?.25:.35):resistance,0.,1.);
    const auto wet=[&](){if(!u.body.in_water.present())throw std::logic_error("missing in-water field");return !u.body.in_water.is_null()&&u.body.in_water.get();};
    // Raw bytecode 击退僵尸: these gates are ordered and use key presence
    // for berserk/vault, including zero/None. Facing does not gate knockback.
    if(u.body.armor=="橄榄球头盔"||u.body.armor=="黑橄榄球头盔"||u.body.size.get()>2.||u.body.berserk.present()||u.body.pole_vault.present()||
        (u.body.hand=="海豚"&&wet())||(u.body.dancing.present()&&u.body.dancing.get()>0.&&u.body.hp>0.)||
        (u.body.hand=="玩偶匣"&&u.body.hp<=0.))amount=0.;
    u.body.motion.get().vx+=amount;
}
bool DamagePatch::trigger_deaths(const ZombieRef& unit) {
    bool triggered=false;
    // Keep all three catches and the order: a failed chili callback does not
    // suppress the later selectors, and a marker is written BEFORE spawning.
    try{triggered=trigger_chili(unit)||triggered;}catch(const std::exception&){}
    try{triggered=trigger_doom(unit)||triggered;}catch(const std::exception&){}
    try{triggered=trigger_grave(unit)||triggered;}catch(const std::exception&){}
    return triggered;
}
bool DamagePatch::trigger_chili(const ZombieRef& unit) {
    if(!unit)return false;auto& u=*unit;
    if(name(u.patch.plant_name)!="辣椒僵尸"||yes(u.patch.chili_exploded)||!eligible(u))return false;
    u.patch.chili_exploded.set(true);effects_.chili_row_hint(unit,true);return effects_.chili_fire_row(unit,u.source.charmed.present());
}
bool DamagePatch::trigger_doom(const ZombieRef& unit) {
    if(!unit)return false;auto& u=*unit;
    if(name(u.patch.plant_name)!="毁灭菇僵尸"||yes(u.patch.doom_exploded)||!eligible(u))return false;
    u.patch.doom_exploded.set(true);return effects_.doom_explosion(unit);
}
bool DamagePatch::trigger_grave(const ZombieRef& unit) {
    if(!unit)return false;auto& u=*unit;
    if(name(u.patch.plant_name)!="墓碑吞噬者僵尸"||yes(u.patch.gravebuster_done)||!eligible(u))return false;
    u.patch.gravebuster_done.set(true);return u.source.charmed.present()?effects_.gravebuster_plant(unit):effects_.grave_remnant(unit);
}
} // namespace pvz::typed72
