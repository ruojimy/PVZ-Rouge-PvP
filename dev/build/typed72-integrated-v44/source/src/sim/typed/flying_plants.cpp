#include "sim/typed/flying_plants.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>

namespace pvz::typed72 {
namespace {
constexpr double pi=0x1.921fb54442d18p+1;
bool flying_kind(std::string_view name){return name=="旋转芜菁" || name=="芦笋战机";}
bool yes(const Field<bool>& field){return field.present() && !field.is_null() && field.get();}
}
bool FlyingPlants::configure(const PlantRef& plant,std::string_view name) {
    if(!flying_kind(name))return false;
    plant->kind=name;
    plant->source.content.set(std::string(name));
    plant->content_age.set(0.);
    plant->flying.clock.set(0.);
    plant->flying.rest.set(0.);
    plant->flying.mode.set("idle");
    plant->one_shot.erase();
    return true;
}
std::vector<ContentTarget> FlyingPlants::nearby(const PlantRef& plant,double radius) {
    const auto origin=targets_.point(plant);
    const double r=radius*world_.runtime.tile;
    auto result=queries_.enemies_in_box(source_ref(plant),{origin.x-r,origin.y-r,origin.x+r,origin.y+r});
    std::erase_if(result,[&](const auto& target){
        ++queries_.range_exact_tests;
        const auto point=targets_.point(target);
        return std::hypot(wrap_delta(origin.x,point.x,world_.world_width.get()),point.y-origin.y)>radius*world_.runtime.tile;
    });
    return result;
}
bool FlyingPlants::solid(Point point)const {
    if(point.y<0. || point.y>=world_.world_height.get())return true;
    const auto row=size_t(std::floor(point.y/world_.runtime.tile));
    if(row>=published_.solid.size())return true;
    const auto col=size_t(std::floor(py::mod(point.x,world_.world_width.get())/world_.runtime.tile));
    const auto& cells=published_.solid.at(row);
    if(cells.empty())throw std::domain_error("empty published row");
    return cells[col%cells.size()]!=0;
}
bool FlyingPlants::clear_line(Point origin,Point target)const {
    const Point delta{wrap_delta(origin.x,target.x,world_.world_width.get()),target.y-origin.y};
    const auto steps=std::max(int64_t(1),int64_t(std::hypot(delta.x,delta.y)/(world_.runtime.tile*.25)));
    for(int64_t step=1;step<steps;++step)
        if(solid({origin.x+delta.x*step/steps,origin.y+delta.y*step/steps}))return false;
    return true;
}
std::optional<ContentTarget> FlyingPlants::turnip_target(const PlantRef& plant) {
    const auto origin=targets_.point(plant);
    const double tile=world_.runtime.tile,width=world_.world_width.get();
    const double ray_width=std::max(18.,tile*.42);
    const auto wraps=int64_t(std::ceil(64.*tile/width))+1;
    for(const auto& target:queries_.enemies(source_ref(plant))) {
        double size=1.;
        Point point=targets_.point(target);
        if(const auto* body=std::get_if<CombatTarget>(&target)) {
            const auto& position=body->is_hero()?*world_.heroes.cached_proxy(body->hero).position:body->unit->body.motion.get();
            size=body->is_hero()?world_.heroes.cached_proxy(body->hero).size.or_missing(2.):body->unit->body.size.or_missing(2.);
            point={position.x,position.y-tile*.35*size};
        }
        const double dx=wrap_delta(origin.x,point.x,width),dy=point.y-origin.y;
        const double limit=ray_width+tile*std::max(.22,.18*size)*unit_scale_factor(*queries_.source(target),collision_);
        for(int64_t wrap=-wraps;wrap<=wraps;++wrap) {
            const double image_dx=dx+wrap*width;
            if(std::hypot(image_dx,dy)<tile*.45)continue;
            for(const Point ray:std::array<Point,4>{{{-1.,-1.},{1.,-1.},{1.,1.},{-1.,1.}}}) {
                const double along=(image_dx*ray.x+dy*ray.y)/std::sqrt(2.);
                if(tile*.25<along && along<=64.*tile && std::abs(image_dx*ray.y-dy*ray.x)/std::sqrt(2.)<=limit)
                    return target;
            }
        }
    }
    return {};
}
void FlyingPlants::advance(const PlantRef& plant) {
    const auto& content=plant->source.content;
    if(!content.present() || content.is_null() || !flying_kind(content.get()) ||
       plant->hp.or_missing(0.)<=0. || plant->dead.present() || plant->sleep.present())return;
    ++plant->content_age.get();
    const double advance=1./std::max(.01,plant->aura_factor.or_missing(1.));
    auto& state=plant->flying;
    if(content.get()=="旋转芜菁") {
        state.clock.set(std::min(250.,state.clock.get()+advance));
        if(state.clock.get()+1e-8>=250. && turnip_target(plant)) {
            state.clock.get()-=250.;
            for(const double angle:{-135.,-45.,45.,135.})fire(plant,angle);
            world_.runtime.play_sound("射豆");
            plant->last_fired.set(double(world_.heroes.tick));
        }
        return;
    }
    if(state.rest.get()>0.) {
        state.rest.set(std::max(0.,state.rest.get()-advance));
        state.mode.set("rest");
        return;
    }
    if(state.mode.get()!="sweep") {
        const auto origin=targets_.point(plant);
        std::optional<ContentTarget> nearest;
        double distance=std::numeric_limits<double>::infinity();
        for(const auto& target:nearby(plant,16.)) {
            const auto point=targets_.point(target);
            if(!clear_line(origin,point))continue;
            const double candidate=std::hypot(wrap_delta(origin.x,point.x,world_.world_width.get()),point.y-origin.y);
            if(candidate<distance){nearest=target;distance=candidate;}
        }
        if(!nearest){state.mode.set("idle");return;}
        const auto point=targets_.point(*nearest);
        const double facing=plant->facing>=0.?1.:-1.;
        const double heading=facing>0.?0.:180.;
        const double angle=std::atan2(point.y-origin.y,wrap_delta(origin.x,point.x,world_.world_width.get()))*(180./pi);
        const double relative=py::mod(angle-heading+180.,360.)-180.;
        state.mode.set("sweep");state.sweep_age.set(0.);
        state.sweep_angle.set(std::clamp(relative,-40.,40.));state.sweep_facing.set(facing);state.clock.set(62.5);
        services_.flying_sweep({plant->source.id,state.sweep_angle.get(),facing});
    }
    const double facing=state.sweep_facing.get(),angle=state.sweep_angle.get();
    state.clock.get()+=advance;
    if(state.clock.get()+1e-8>=62.5) {
        state.clock.get()-=62.5;
        fire(plant,(facing>0.?0.:180.)+angle);
        world_.runtime.play_sound("投掷");
        plant->last_fired.set(double(world_.heroes.tick));
    }
    ++state.sweep_age.get();
    state.sweep_angle.set(std::clamp(angle-facing*60./750.,-40.,40.));
    if(state.sweep_age.get()>=750. || (facing>0. && state.sweep_angle.get()<=-40.) ||
       (facing<0. && state.sweep_angle.get()>=40.)) {
        state.mode.set("rest");state.rest.set(1500.);
    }
}
EntityRef FlyingPlants::fire(const PlantRef& plant,double angle) {
    const auto point=targets_.point(plant);
    const double radians=angle*(pi/180.);
    const bool turnip=plant->source.content.get()=="旋转芜菁";
    const double speed=world_.runtime.tile*(turnip?12.:48.)/250.;
    const double cosine=std::cos(radians);
    auto entity=std::make_shared<Entity>(turnip?"芜菁球弹":"芦笋线弹",cosine>=0.?1.:-1.,
        Motion{point.x,point.y,cosine*speed,std::sin(radians)*speed});
    entity->source.content=plant->source.content;entity->flying_plant.set(true);
    entity->flying.distance.set(0.);entity->flying.hits.set({});entity->flying.angle.set(angle);
    entity->source.plant_kind.set(plant->kind);entity->flying.damage.set(turnip?5.:10.);entity->flying.piercing.set(!turnip);
    world_.heroes.tag_entity(source_ref(entity),&entity->motion.get(),entity->flight,{},source_ref(plant));
    // These custom records bypass the native constructor and its birth hooks.
    world_.runtime.entities.emplace(entity);
    plant->flying.shots.set(plant->flying.shots.or_missing(0.)+1.);
    return entity;
}
void FlyingPlants::before_tick() {
    EntityRoster flying;
    auto native=std::make_shared<EntityRoster>();
    for(const auto& entity:*world_.runtime.entities.list()) {
        if(yes(entity->flying_plant))flying.push_back(entity);else native->push_back(entity);
    }
    world_.content_projectiles.flying=std::move(flying);
    world_.runtime.entities.replace(std::move(native));
}
double FlyingPlants::wall_contact(Point origin,Point delta)const {
    const auto steps=std::max(int64_t(1),int64_t(std::ceil(std::hypot(delta.x,delta.y)/(world_.runtime.tile*.1))));
    for(int64_t step=0;step<=steps;++step) {
        const double fraction=double(step)/steps;
        if(solid({origin.x+delta.x*fraction,origin.y+delta.y*fraction}))return fraction;
    }
    return 2.;
}
double FlyingPlants::contact_reach(const ContentTarget& target,Point point)const {
    const double tile=world_.runtime.tile;
    const double scale=unit_scale_factor(*queries_.source(target),collision_);
    double reach=std::holds_alternative<PlantRef>(target)?tile*.45:tile*.8*std::max(scale,1.);
    const auto* body=std::get_if<CombatTarget>(&target);
    if(body && !body->is_hero()) {
        if(const auto head=plant_zombie_head(*body->unit,tile,collision_))
            reach=std::max({reach,std::abs(wrap_delta(point.x,head->center.x,world_.world_width.get()))+head->rx,
                           std::abs(head->center.y-point.y)+head->ry});
    }
    return reach+2.;
}
void FlyingPlants::projectiles() {
    struct Candidate {ContentTarget target;double along;};
    EntityRoster survivors;
    const double width=world_.world_width.get();
    auto& shots=world_.content_projectiles.flying;
    for(size_t index=0;index<shots.size();++index) {
        const auto entity=shots[index];
        const Motion motion=entity->motion.get();
        const Point origin{motion.x,motion.y},delta{motion.vx,motion.vy};
        const double step=std::hypot(delta.x,delta.y);
        entity->flying.distance.get()+=step;
        const double limit=entity->source.content.get()=="芦笋战机"?32.:64.;
        if(entity->flying.distance.get()>world_.runtime.tile*limit)continue;
        const double wall=wall_contact(origin,delta);
        const auto source=source_ref(entity);
        std::vector<Candidate> candidates;
        const CoverageBox sweep{std::min(origin.x,origin.x+delta.x),std::min(origin.y,origin.y+delta.y),std::max(origin.x,origin.x+delta.x),std::max(origin.y,origin.y+delta.y)};
        for(const auto& target:queries_.enemies_in_box(source,sweep)) {
            ++queries_.range_exact_tests;
            const auto point=targets_.point(target);const double reach=contact_reach(target,point);
            const double dx=wrap_delta(origin.x,point.x,width),dy=point.y-origin.y;
            if(std::abs(dx)<=reach+step && std::abs(dy)<=reach+step)
                candidates.push_back({target,dx*delta.x+dy*delta.y});
        }
        std::stable_sort(candidates.begin(),candidates.end(),[](const auto& a,const auto& b){return a.along<b.along;});
        bool destroyed=false;
        for(const auto& candidate:candidates) {
            const auto uid=world_.heroes.source_id(queries_.source(candidate.target));
            auto& hits=entity->flying.hits.get();
            if(std::find(hits.begin(),hits.end(),uid)!=hits.end())continue;
            const double fraction=std::min(1.,wall);
            if(!targets_.contact(candidate.target,origin,{delta.x*fraction,delta.y*fraction}))continue;
            hits.push_back(uid);
            entity->motion.get().x=py::mod(origin.x+delta.x*fraction,world_.world_width.get());
            entity->motion.get().y=origin.y+delta.y*fraction;
            const auto* body=std::get_if<CombatTarget>(&candidate.target);
            const double amount=body && body->is_hero()?(yes(entity->flying.piercing)?1.:2.5):entity->flying.damage.get();
            targets_.damage(source,candidate.target,amount,entity->facing,true);
            queries_.invalidate();
            if(!yes(entity->flying.piercing)){destroyed=true;break;}
        }
        if(destroyed || wall<=1.)continue;
        entity->motion.get().x=py::mod(origin.x+delta.x,world_.world_width.get());
        entity->motion.get().y=origin.y+delta.y;
        services_.draw_flying_shot(entity);
        survivors.push_back(entity);
    }
    for(const auto& entity:survivors)world_.runtime.entities.emplace(entity);
    shots.clear();
}
} // namespace pvz::typed72
