#include "sim/typed/wind_effects.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
double number(const Field<double>& f,double fallback=0.){return f.present()&&!f.is_null()?f.get():fallback;}
double sign(double v){return v<0.?-1.:1.;}
bool side(double center,double target,double direction,double tile){return (target-center)*direction>=-tile*.25;}
void directed_limit(Motion& p,double direction,double limit){limit=std::max(0.,limit);p.vx=direction>0.?std::min(p.vx,limit):std::max(p.vx,-limit);}
void push(Motion& p,double direction,double amount,double limit){p.vx+=direction*amount;p.vx=direction>0.?std::min(p.vx,limit):std::max(p.vx,-limit);}
template<class T> class Restore {
public:
    explicit Restore(T& v):current_(v),saved_(v){}
    ~Restore(){current_=std::move(saved_);}
private:T& current_;T saved_;
};
class EntityView {
public:
    EntityView(EntityCollection& c,std::shared_ptr<EntityRoster> v):collection_(c),saved_(c.exchange_view(std::move(v))){}
    ~EntityView(){collection_.exchange_view(std::move(saved_));}
private:EntityCollection& collection_;std::shared_ptr<EntityRoster> saved_;
};
}
ZombieRecordFields& WindEffects::fields(const CombatTarget& t)const {
    return t.is_hero()?static_cast<ZombieRecordFields&>(world_.heroes.cached_proxy(t.hero)):t.unit->body;
}
std::shared_ptr<Motion> WindEffects::position(const CombatTarget& t)const {
    return t.is_hero()?world_.heroes.cached_proxy(t.hero).position:t.unit->body.motion.retain();
}
void WindEffects::mapped_surface(size_t index,double direction,double amount) {
    if(!surface_roster_){services_.wind_surface(index,direction,amount);return;}
    const auto actual=surface_indices_.at(index);Restore restore(world_.targets);world_.targets=surface_roster_;
    services_.wind_surface(actual,direction,amount);
}
void WindEffects::raw_wind(const ZombieRef& source,double strength) {
    const auto center=native_plant_zombie_head_center(*source,world_.runtime.tile,catalog_);
    const double direction=sign(source->body.facing),scale=std::max(1.,world_.runtime.tile),plk=world_.runtime.plk;
    strength=std::max(.1,strength);const auto names=world_.wind_environment.damage_entities;
    // These are shallow native list snapshots: callbacks may replace lists,
    // remove objects or replace an object's independently retained position.
    const auto entities=*world_.runtime.entities.list();
    for(const auto& e:entities)if(std::find(names->begin(),names->end(),e->kind)!=names->end()) {
        auto& p=e->motion.get();if(side(center.x,p.x,direction,scale)){p.vx+=direction*1.5*plk*strength;e->facing=direction;}
    }
    const auto rain=*world_.wind_environment.rain;
    for(const auto& p:rain)if(p->size()>=3)(*p)[2]+=direction*600.*plk*strength;
    const double speed=std::max(1.,world_.wind_environment.zombie_speed_max);
    const auto targets=*world_.targets;
    for(size_t i=0;i<targets.size();++i)try {
        const auto& t=targets[i];if(t.unit==source)continue;
        const auto proxy=t.is_hero()?world_.heroes.proxies.at(seat_index(t.hero)):std::shared_ptr<HeroProxyState>{};
        auto& f=proxy?static_cast<ZombieRecordFields&>(*proxy):static_cast<ZombieRecordFields&>(t.unit->body);
        if(f.ash.present()||f.hp<=0.)continue;
        const auto retained_position=proxy?proxy->position:t.unit->body.motion.retain();auto& p=*retained_position;
        if(!side(center.x,p.x,direction,scale))continue;
        const auto handheld=f.hand;
        if(handheld=="报纸")try{mapped_surface(i,direction,1.);}catch(const std::exception&){}
        const bool balloon=handheld=="气球"||number(f.balloon)!=0.;
        p.vx+=direction*(balloon?20.:6.)*plk*strength;
        p.vy=std::min(p.vy,-(balloon?14.:8.)*plk*strength);f.gravity.set(std::max(number(f.gravity),2.*plk));
        const double size=std::max(.35,number(f.size,1.));
        directed_limit(p,direction,balloon?speed*10.:speed*36./std::max(.05,size*size*size));
    }catch(const std::exception&){}
}
void WindEffects::radius_wind(const ZombieRef& source,double strength) {
    const auto center=native_plant_zombie_head_center(*source,world_.runtime.tile,catalog_);const double tile=world_.runtime.tile;
    const auto near=[&](double x,double y){return std::hypot(wrap_delta(center.x,x,width_),y-center.y)<=8.*tile;};
    Restore targets_restore(world_.targets);Restore rain_restore(world_.wind_environment.rain);
    Restore surface_restore(surface_roster_);Restore indices_restore(surface_indices_);
    surface_roster_=world_.targets;surface_indices_.clear();auto selected=std::make_shared<TargetRoster>();
    for(size_t i=0;i<surface_roster_->size();++i){const auto& t=surface_roster_->at(i);const auto p=position(t);if(near(p->x,p->y-tile)){selected->push_back(t);surface_indices_.push_back(i);}}
    world_.targets=std::move(selected);
    auto entities=std::make_shared<EntityRoster>();for(const auto& e:*world_.runtime.entities.list()){const auto& p=e->motion.get();if(near(p.x,p.y))entities->push_back(e);}
    EntityView entity_view(world_.runtime.entities,std::move(entities));
    auto rain=std::make_shared<RainRoster>();for(const auto& p:*world_.wind_environment.rain)if(p->size()>=2&&near((*p)[0],(*p)[1]))rain->push_back(p);
    world_.wind_environment.rain=std::move(rain);raw_wind(source,strength);
}
void WindEffects::wind(const ZombieRef& source,double strength) {
    // Installation order: PvP70 -> FlyingPlants -> Wind radius -> raw patch.
    // Hidden flying shots are added by identity only, and the names/list views
    // are restored even when a nested callback replaces them.
    {
        const auto original=world_.runtime.entities.list();auto entities=std::make_shared<EntityRoster>(*original);
        for(const auto& e:world_.content_projectiles.flying)if(std::find(original->begin(),original->end(),e)==original->end())entities->push_back(e);
        EntityView view(world_.runtime.entities,std::move(entities));Restore names_restore(world_.wind_environment.damage_entities);
        auto names=std::make_shared<std::vector<std::string>>(*world_.wind_environment.damage_entities);names->push_back("芜菁球弹");names->push_back("芦笋线弹");world_.wind_environment.damage_entities=std::move(names);
        radius_wind(source,strength);
    }
    const auto center=native_plant_zombie_head_center(*source,world_.runtime.tile,catalog_);
    const auto shots=world_.content_projectiles.shots;
    const auto grenades=*world_.content_projectiles.grenades;
    const auto blow=[&](const auto& shot) {
        if(shot->kind.present() && !shot->kind.is_null() && shot->kind.get()=="hook")return;
        auto& position=shot->motion;
        const double dx=wrap_delta(center.x,position.x,width_);
        if(std::hypot(dx,position.y-center.y)<=8.*world_.runtime.tile &&
           side(center.x,center.x+dx,source->body.facing,world_.runtime.tile))
            position.vx+=source->body.facing*1.5*world_.runtime.plk*strength;
    };
    for(const auto& shot:shots)blow(shot);
    for(const auto& grenade:grenades)blow(grenade);
}
void WindEffects::raw_update(const ZombieRef& source,const PlantZombieConfig& config) {
    auto& p=source->patch;const double direction=sign(source->body.facing);
    if(number(p.fire_animation)>0.) {
        p.aim_angle.set(number(p.aim_angle,native_direction_angle(direction))+direction*24.);
        const auto tick=int64_t(number(p.blover_wind_tick))+1;p.blover_wind_tick.set(double(tick));if(tick%3==0)wind(source,3.);
    }
    const auto cd=p.blover_cooldown.present()&&!p.blover_cooldown.is_null()?int64_t(p.blover_cooldown.get()):world_.runtime.rng.randint(0,25);
    if(cd>0){p.blover_cooldown.set(double(cd-1));return;}
    const auto center=native_plant_zombie_head_center(*source,world_.runtime.tile,catalog_);
    p.fire_animation.set(double(std::max<int64_t>(1,int64_t(number(config.fire_anim,270.)))));p.shoot.set(1.);
    p.aim_angle.set(native_direction_angle(direction));p.blover_cooldown.set(double(std::max<int64_t>(1,int64_t(number(config.cooldown,500.)))));
    world_.runtime.sound("三叶草",{center.x,center.y,0.,0.});p.blover_wind_tick.set(0.);wind(source,3.);++blows;
}
void WindEffects::update(const ZombieRef& source,const PlantZombieConfig& config) {
    SourcedContext scope(world_,source_ref(source),CombatPhase::zombies);raw_update(source,config);scope.finish();
}
double WindEffects::hero_acceleration()const {const double p=world_.runtime.plk;return 6.*(p==0.?1.:p)*2.;}
double WindEffects::hero_limit()const {const double s=world_.wind_environment.zombie_speed_max;return (s==0.?10.:s)*36./8.*2.;}
void WindEffects::before_plants() {
    plant_baselines_.fill({});bool clover=false;
    for(const auto& p:*world_.plant_roster)if(p->kind=="三叶草"&&number(p->hp)>0.&&!p->dead.present()){clover=true;break;}
    if(clover)for(const auto seat:seats_for(world_.mode))if(team_of(seat)==Seat::zombie)plant_baselines_[seat_index(seat)]=world_.heroes.hero(seat).frame.position.get()->vx;
}
void WindEffects::after_plants() {
    const double accel=hero_acceleration(),limit=hero_limit(),tile=world_.runtime.tile;
    for(size_t i=0;i<plant_baselines_.size();++i)if(plant_baselines_[i]) {
        auto& hero=world_.heroes.hero(Seat(i));if(number(hero.frame.hp)<=0.)continue;
        auto& pos=*hero.frame.position.get();Motion velocity{0.,0.,*plant_baselines_[i],0.};bool pushed=false;
        for(const auto& p:*world_.plant_roster)if(p->kind=="三叶草"&&number(p->hp)>0.&&!p->dead.present()) {
            const double x=(p->cell.x+.5)*tile,direction=p->facing==1.?1.:-1.;
            if((direction==1.&&pos.x>=x)||(direction==-1.&&pos.x<=x)){push(velocity,direction,accel,limit);pushed=true;}
        }
        if(pushed)pos.vx=velocity.vx;
    }
}
void WindEffects::after_zombies() {
    const double accel=hero_acceleration(),limit=hero_limit(),tile=world_.runtime.tile;
    for(const auto& target:*world_.targets)if(!target.is_hero()) {
        const auto& z=*target.unit;const auto& p=z.patch;
        if(!p.plant_name.present()||p.plant_name.is_null()||p.plant_name.get()!="三叶草僵尸"||number(p.fire_animation)<=0.||z.body.hp<=0.||z.body.ash.present()||z.protection.hero)continue;
        const auto owner=world_.heroes.owner(source_ref(target.unit));if(!owner||(*owner!=Seat::plant&&*owner!=Seat::zombie))continue;
        const auto center=native_plant_zombie_head_center(z,tile,catalog_);const double direction=sign(z.body.facing);
        for(const auto seat:seats_for(world_.mode))if(team_of(seat)!=*owner) {
            auto& h=world_.heroes.hero(seat).frame;if(number(h.hp)<=0.)continue;auto& pos=*h.position.get();
            const double dx=wrap_delta(center.x,pos.x,width_);if(dx*direction< -tile*.25||std::hypot(dx,pos.y-tile-center.y)>8.*tile)continue;
            push(pos,direction,accel,limit);
        }
    }
}
} // namespace pvz::typed72
