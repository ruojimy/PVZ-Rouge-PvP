#include "sim/typed/plant_lookup.h"
#include "sim/typed/doom_effects.h"
#include <algorithm>
#include <cmath>
#include <limits>
namespace pvz::typed72 {
namespace {
double native_number(const Field<double>& f,double fallback){return f.present()&&!f.is_null()?f.get():fallback;}
int64_t grid_index(double value) {
    const double n=std::floor(value);
    if(!std::isfinite(n)||n<=double(std::numeric_limits<int64_t>::min())||n>=-double(std::numeric_limits<int64_t>::min()))throw std::out_of_range("doom cell coordinate");
    return int64_t(n);
}
}
Point DoomEffects::target_point(const CombatTarget& target)const {
    const double tile=world_.runtime.tile;
    if(target.is_hero()) {
        const auto& proxy=world_.heroes.cached_proxy(target.hero);
        return {proxy.position->x,proxy.position->y-tile*.65*std::max(.35,native_number(proxy.size,1.))};
    }
    const auto& u=*target.unit;
    if(auto head=plant_zombie_head(u,tile,catalog_))return head->center;
    return {u.body.motion.get().x,u.body.motion.get().y-tile*.65*std::max(.35,native_number(u.body.size,1.))};
}
void DoomEffects::kill_plant(const PlantRef& plant) {
    plant->hurt.set(1.);plant->hp.set(0.);
    try{plants_.clear(plant->cell);return;}catch(const std::exception&){}
    plant->dead.set(DeathMarker(true));
}
size_t DoomEffects::ash_targets(const ZombieRef& source,Point point,double scale) {
    const auto result=native_ash_targets(source,point,scale);
    if(world_.native_plant_zombies_installed) {
        const auto enemy=world_.heroes.owner(source_ref(source))==Seat::plant?Seat::zombie:Seat::plant;
        const double reach=std::max(1.,scale)*5.;
        for(const auto side:seats_for(world_.mode))if(team_of(side)==enemy){
            world_.heroes.proxy(side);
            const auto p=target_point(CombatTarget::player(side));
            if(std::abs(p.x-point.x)<=reach && std::abs(p.y-point.y)<=reach)
                world_.heroes.damage(side,world_.heroes.hero(side).max_hp.or_missing(40.),HeroHit::ash);
        }
    }
    return result;
}
size_t DoomEffects::native_ash_targets(const ZombieRef& source,Point point,double scale) {
    const auto original=world_.targets;auto extra=services_.extra_targets();
    FullTargetsScope scope(world_.targets,extra?std::optional<std::span<const CombatTarget>>(*extra):std::nullopt,original);
    const bool charmed=source->source.charmed.present();const double radius=std::max(1.,scale)*5.;
    const auto in_range=[&](Point p){return std::abs(p.x-point.x)<=radius&&std::abs(p.y-point.y)<=radius;};
    size_t count=0;
    if(!charmed) {
        const auto plants=*world_.plant_roster;
        for(const auto& p:plants) {
            if(p->dead.present()||p->shovel_dead.present()||native_number(p->hp,1.)<=0.)continue;
            const auto visible=patch_plant_point(world_,*p);if(visible&&in_range(*visible)){kill_plant(p);++count;}
        }
    }
    const auto targets=*world_.targets;
    for(const auto& target:targets) {
        if(target.unit==source)continue;
        // Hero proxies are not charmed by faction: their constructor copies
        // an ordinary uncharmed zombie; damage dispatch enforces team safety.
        const bool target_charmed=!target.is_hero()&&target.unit->source.charmed.present();
        if(target_charmed==charmed)continue;
        if(target.is_hero()) {
            const auto& proxy=world_.heroes.cached_proxy(target.hero);
            if(proxy.dead.present()||proxy.hp<=0.)continue;
        }else if(target.unit->body.ash.present()||target.unit->body.dead.present()||target.unit->body.hp<=0.)continue;
        if(!in_range(target_point(target)))continue;
        // A preceding death can replace the roster or remove earlier entries.
        // Re-resolve this retained object against the current list each time.
        const auto list=world_.targets;
        const auto found=std::find(list->begin(),list->end(),target);
        if(found==list->end())continue;
        services_.ash_target(size_t(found-list->begin()),damage_,target);++count;
    }
    return count;
}
EntityRef DoomEffects::spawn_effect(std::string name,double facing,Motion p,double expires) {
    const auto entities=world_.runtime.entities.list();const auto before=entities->size();
    try{services_.add_original_entity(std::move(name),facing,p);}catch(const std::exception&){return {};}
    if(entities->size()<=before)return {};
    auto result=entities->back();result->expires.set(expires);return result;
}
void DoomEffects::visuals(Point p,double scale) {
    auto& rt=world_.runtime;
    for(const std::string name:{"毁灭1","毁灭2","毁灭3"})if(std::find(rt.other_images.begin(),rt.other_images.end(),name)==rt.other_images.end())rt.other_images.push_back(name);
    for(int i=0;i<10;++i) {
        const double direction=rt.rng.randint(0,1)==0?-1.:1.;const double wave=(i/2)%2==0?1.:-1.;
        if(auto e=spawn_effect("毁灭3",direction,{p.x+scale-i*scale*.5,p.y-scale*4.+wave*scale*.5,0.,0.},700.))e->rotation.set(double(rt.rng.randint(0,360)));
    }
    spawn_effect("毁灭2",1.,{p.x+scale,p.y-scale*3.5,0.,0.},700.);
    spawn_effect("毁灭1",1.,{p.x+scale,p.y-scale*3.5,0.,0.},700.);
}
void DoomEffects::knock_player(Point point,double scale) {
    auto& g=world_.heroes.globals;if(!g.position.present()||g.position.is_null()||!g.position.get())return;
    auto& p=*g.position.get();
    if(std::abs(p.x-point.x)>scale*5.||std::abs(p.y-point.y)>scale*5.)return;
    p.vx+=(p.x>=point.x?1.:-1.)*900.*world_.runtime.plk;p.vy-=800.*world_.runtime.plk;g.hurt.set(1.);
}
size_t DoomEffects::destroy_blocks(Point point,double scale) {
    if(scale==0.)throw std::domain_error("zero doom scale");
    const auto col=grid_index(point.x/scale),row=grid_index(point.y/scale);size_t count=0;
    for(int y=0;y<5;++y)for(int x=0;x<5;++x) {
        if(std::abs(y-2)+std::abs(x-2)>3)continue;
        try {
            const auto yy=row-2+y,xx=col-2+x;
            if(yy<std::numeric_limits<int>::min()||yy>std::numeric_limits<int>::max())throw std::out_of_range("doom row");
            services_.destroy_block({int(yy),xx});++count;
        }catch(const std::exception&){}
    }
    return count;
}
bool DoomEffects::explode(const ZombieRef& source) {
    if(!source)throw std::invalid_argument("null doom source");
    auto& rt=world_.runtime;const Point point{source->body.motion.get().x,source->body.motion.get().y};const double scale=std::max(1.,rt.tile);
    rt.nuclear_flash.set(80.);knock_player(point,scale);ash_targets(source,point,scale);visuals(point,scale);destroy_blocks(point,scale);
    rt.screen_shake.set({200.,0.,0.});rt.sound("毁灭菇",{point.x,point.y,0.,0.});++explosions;return true;
}
} // namespace pvz::typed72
