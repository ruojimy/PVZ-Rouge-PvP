#include "sim/typed/plant_lookup.h"
#include "sim/typed/lantern_effects.h"
#include "sim/typed/damage_patch.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
double number(const Field<double>& f,double fallback=0.){return f.present()&&!f.is_null()?f.get():fallback;}
bool yes(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
bool charmed(const CombatTarget& t){return !t.is_hero()&&t.unit->source.charmed.present();}
}
void LanternEffects::track_max_hp() {
    const auto targets=*world_.targets;
    for(const auto& t:targets)if(!t.is_hero())DamagePatch::remember_max_hp(*t.unit);
    else {auto& p=world_.heroes.cached_proxy(t.hero);const auto hp=p.hp;if(hp>0.&&(hp>number(p.observed_max_hp,hp)||!p.observed_max_hp.present()))p.observed_max_hp.set(hp);}
}
bool LanternEffects::heal_zombie(const CombatTarget& target,double amount) {
    const auto proxy=target.is_hero()?world_.heroes.proxies.at(seat_index(target.hero)):std::shared_ptr<HeroProxyState>{};
    auto& body=proxy?static_cast<ZombieRecordFields&>(*proxy):static_cast<ZombieRecordFields&>(target.unit->body);
    if(body.ash.present()||body.hp<=0.)return false;
    const auto& specific=proxy?proxy->plant_max_hp:target.unit->patch.plant_max_hp;
    const auto& observed=proxy?proxy->observed_max_hp:target.unit->patch.observed_max_hp;
    const double hp=body.hp,maximum=number(specific.present()?specific:observed,hp);
    if(maximum<=hp)return false;const double healed=std::min(maximum,hp+amount);if(healed<=hp)return false;
    // Native HeroProxy intercepts increases. The original helper nevertheless
    // writes hurt and returns True after attempting the assignment.
    if(proxy)world_.heroes.write_proxy_hp(target.hero,healed);else body.hp=healed;body.hurt=1.;return true;
}
bool LanternEffects::heal_plant(const PlantRef& plant,double amount) {
    auto& p=*plant;if(p.dead.present()||p.shovel_dead.present())return false;
    const double hp=number(p.hp),maximum=number(p.max_hp,hp);if(hp<=0.||maximum<=hp)return false;
    const double healed=std::min(maximum,hp+amount);if(healed<=hp)return false;p.hp.set(healed);p.hurt.set(1.);return true;
}
int LanternEffects::multiplier()const {
    const auto& f=world_.heroes.globals.secrets;
    return f.present()&&!f.is_null()&&f.get()&&std::find(f.get()->begin(),f.get()->end(),"光疗")!=f.get()->end()?2:1;
}
bool LanternEffects::in_range(Point center,Point point,double tiles)const {
    const double radius=std::max(1.,world_.runtime.tile)*tiles;
    return std::abs(point.x-center.x)<=radius&&std::abs(point.y-center.y)<=radius;
}
void LanternEffects::effects(Point point,int64_t count) {
    auto& rt=world_.runtime;
    if(std::find(rt.other_images.begin(),rt.other_images.end(),"光疗")==rt.other_images.end())rt.other_images.push_back("光疗");
    const double scale=std::max(1.,rt.tile),plk=rt.plk;
    for(int64_t i=0;i<std::max<int64_t>(1,count);++i)try {
        const double ox=(rt.rng.randint(-18,18)/100.)*scale,oy=(rt.rng.randint(-12,12)/100.)*scale;
        const auto entities=rt.entities.list();const auto before=entities->size();
        try{services_.add_original_entity("光疗",1.,{point.x+ox,point.y-scale*.65+oy,0.,-50.*plk});}catch(const std::exception&){continue;}
        if(entities->size()>before){const auto e=entities->back();e->expires.set(800.);e->gravity.set(0.);}
    }catch(const std::exception&){}
}
size_t LanternEffects::heal_targets(const ZombieRef& source,Point center) {
    size_t healed=0;const int factor=source->source.charmed.present()?multiplier():1,effect_count=factor>1?2:1;
    if(source->source.charmed.present()) {
        const auto plants=*world_.plant_roster;
        for(const auto& p:plants)try {
            if(p->kind=="大蒜")continue;const auto visible=patch_plant_point(world_,*p);if(!visible)continue;const auto point=*visible;
            if(in_range(center,point)&&heal_plant(p,6.*factor)){effects(point,effect_count);++healed;}
        }catch(const std::exception&){}
    }
    const auto targets=*world_.targets;
    for(const auto& t:targets)try {
        const auto& body=t.is_hero()?static_cast<const ZombieRecordFields&>(world_.heroes.cached_proxy(t.hero)):t.unit->body;
        if(body.ash.present()||charmed(t)!=source->source.charmed.present())continue;
        const double amount=60.*(source->source.charmed.present()?factor:1);const auto point=aim_.zombie_point(t);
        if(in_range(center,point)&&heal_zombie(t,amount)){effects(point,source->source.charmed.present()?effect_count:1);++healed;}
    }catch(const std::exception&){}
    return healed;
}
void LanternEffects::raw_update(const ZombieRef& source,const PlantZombieConfig& config) {
    auto& p=source->patch;const double direction=source->body.facing<0.?-1.:1.;
    if(number(p.fire_animation)>0.)p.aim_angle.set(number(p.aim_angle,native_direction_angle(direction))+direction*8.);
    const auto cd=p.lantern_cooldown.present()&&!p.lantern_cooldown.is_null()?int64_t(p.lantern_cooldown.get()):world_.runtime.rng.randint(0,25);
    if(cd>0){p.lantern_cooldown.set(double(cd-1));return;}
    const auto center=native_plant_zombie_head_center(*source,world_.runtime.tile,catalog_);
    p.fire_animation.set(double(std::max<int64_t>(1,int64_t(number(config.fire_anim,125.)))));p.shoot.set(1.);
    p.aim_angle.set(native_direction_angle(direction));p.lantern_cooldown.set(double(std::max<int64_t>(1,int64_t(number(config.cooldown,300.)))));
    world_.runtime.sound("治疗",{center.x,center.y,0.,0.});const auto healed=heal_targets(source,center);
    effects(center,source->source.charmed.present()&&multiplier()>1?2:1);zombie_heals+=healed;
}
void LanternEffects::update(const ZombieRef& source,const PlantZombieConfig& config) {
    SourcedContext scope(world_,source_ref(source),CombatPhase::zombies);raw_update(source,config);scope.finish();
}
void LanternEffects::native_charmed_healing() {
    const auto captured=world_.targets;bool any=false;
    for(const auto& t:*captured)if(charmed(t)&&!t.unit->body.dead.present()&&!t.unit->body.ash.present()&&t.unit->body.hp>0.){any=true;break;}
    if(!any)return;
    const int factor=multiplier(),effect_count=factor>1?2:1;const double amount=60.*factor;
    const auto plants=*world_.plant_roster;
    for(const auto& p:plants)try {
        if(p->kind!="路灯花")continue;const auto active=int64_t(number(p->burst));
        if(active<=0){p->lantern_charm_healed.erase();continue;}
        if(active<125||yes(p->lantern_charm_healed))continue;
        const auto visible=patch_plant_point(world_,*p);if(!visible)continue;const auto center=*visible;
        size_t healed=0;const auto targets=*captured;
        for(const auto& t:targets)try {
            if(!charmed(t)||t.unit->body.ash.present())continue;const auto point=aim_.zombie_point(t);
            if(in_range(center,point)&&heal_zombie(t,amount)){effects(point,effect_count);++healed;}
        }catch(const std::exception&){}
        p->lantern_charm_healed.set(true);native_charmed_heals+=healed;
    }catch(const std::exception&){}
}
} // namespace pvz::typed72
