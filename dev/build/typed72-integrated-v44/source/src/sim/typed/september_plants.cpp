#include "sim/typed/september_plants.h"
#include "sim/typed/projectile_rules.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
bool SeptemberPlants::configure(const PlantRef& plant,std::string_view name) {
    if(name!="黄金蓓蕾" && name!="幽灵辣椒")return false;
    plant->source.content.set(std::string(name));plant->kind=name;
    plant->one_shot.set(true);plant->content_age.set(0.);plant->effect_done.set(false);plant->burst.erase();
    return true;
}
bool SeptemberPlants::inside(const PlantRef& plant,const ContentTarget& target,double horizontal,double vertical)const {
    const auto origin=targets_.point(plant),point=targets_.point(target);
    const auto tile=world_.runtime.tile,width=world_.world_width.get();
    if(std::abs(wrap_delta(origin.x,point.x,width))<=horizontal*tile &&
       std::abs(point.y-origin.y)<=vertical*tile)return true;
    const auto* body=std::get_if<CombatTarget>(&target);
    return body && !body->is_hero() && head_overlaps_area(*body->unit,origin,horizontal*tile,vertical*tile,tile,width,collision_);
}
void SeptemberPlants::attack(const PlantRef& plant,double amount,double horizontal,double vertical,
                             double hero_amount,HeroHit kind) {
    const auto source=source_ref(plant);
    const auto origin=targets_.point(plant);const double tile=world_.runtime.tile;
    for(const auto& target:queries_.enemies_in_box(source,{origin.x-horizontal*tile,origin.y-vertical*tile,origin.x+horizontal*tile,origin.y+vertical*tile})) {
        ++queries_.range_exact_tests;
        if(!inside(plant,target,horizontal,vertical))continue;
        const auto* body=std::get_if<CombatTarget>(&target);
        targets_.damage(source,target,body && body->is_hero()?hero_amount:amount,plant->facing,false,kind);
    }
}
void SeptemberPlants::advance(const PlantRef& plant) {
    const auto& name=plant->source.content;
    if(!name.present() || name.is_null() || (name.get()!="黄金蓓蕾" && name.get()!="幽灵辣椒"))return;
    if(plant->effect_done.present() && !plant->effect_done.is_null() && plant->effect_done.get())return;
    if(plant->hp.or_missing(0.)<=0. || plant->dead.present() || plant->sleep.present())return;
    ++plant->content_age.get();
    const auto now=world_.heroes.tick;
    if(name.get()=="黄金蓓蕾") {
        if(plant->content_age.get()<125.)return;
        plant->effect_done.set(true);
        const auto point=targets_.point(plant);
        const double amount=now<120*250?15.:25.;
        const auto plk=world_.runtime.plk;
        for(int index=0;index<8;++index) {
            const double angle=0x1.921fb54442d18p+1*(index+.5)/8.;
            auto sun=std::make_shared<NativeSun>();
            sun->motion={point.x,point.y,std::cos(angle)*plk*100.,-std::sin(angle)*plk*150.};
            sun->bloom_amount=amount;
            resources_.loose_suns.push_back(std::move(sun));
        }
        plant->dead.set(DeathMarker(0.));
        services_.september_event({SeptemberPlantEvent::Kind::bloom,plant->source.id,8.*amount});
        return;
    }
    if(!plant->ghost_started.present()) {
        bool trigger=false;
        const auto origin=targets_.point(plant);const double tile=world_.runtime.tile;
        for(const auto& target:queries_.enemies_in_box(source_ref(plant),{origin.x-5.*tile,origin.y-.85*tile,origin.x+5.*tile,origin.y+.85*tile})) {
            ++queries_.range_exact_tests;
            const auto* body=std::get_if<CombatTarget>(&target);
            if(!body)continue;
            const auto hp=body->is_hero()?world_.heroes.cached_proxy(body->hero).hp:body->unit->body.hp;
            if((!body->is_hero() && body->unit->protection.grave) || hp<=0.)continue;
            if(inside(plant,target,5.,.85)){trigger=true;break;}
        }
        if(!trigger)return;
        plant->ghost_started.set(double(now));plant->ghost_clock.set(0.);
        services_.september_event({SeptemberPlantEvent::Kind::ghost_activated,plant->source.id});
        return;
    }
    const double elapsed=now-plant->ghost_started.get();
    plant->ghost_clock.get()+=1./std::max(.01,plant->aura_factor.or_missing(1.));
    if(plant->ghost_clock.get()+1e-8>=250.) {
        plant->ghost_clock.get()-=250.;
        attack(plant,25.,5.,.85,2.5);
        plant->ghost_pulse.set(double(world_.heroes.tick));
    }
    if(elapsed>=2500.) {
        plant->effect_done.set(true);
        attack(plant,250.,1.25,1.25,250.,HeroHit::ash);
        effects.push_back({world_.heroes.tick,targets_.point(plant)});
        plant->dead.set(DeathMarker(0.));
        services_.september_event({SeptemberPlantEvent::Kind::ghost_exploded,plant->source.id});
    }
}
} // namespace pvz::typed72
