#include "sim/typed/mortar_plants.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <tuple>

namespace pvz::typed72 {
namespace {
constexpr double pi=0x1.921fb54442d18p+1;
bool yes(const Field<bool>& value){return value.present() && !value.is_null() && value.get();}
bool custom_plant(std::string_view name){return name=="豌豆迫击炮" || name=="弹簧草";}
double hp(const TypedBattleState& world,const ContentTarget& target) {
    if(const auto* plant=std::get_if<PlantRef>(&target))return (*plant)->hp.or_missing(1.);
    const auto& body=std::get<CombatTarget>(target);
    return body.is_hero()?world.heroes.cached_proxy(body.hero).hp:body.unit->body.hp;
}
}
bool MortarPlants::configure(const PlantRef& plant,std::string_view name) {
    if(!custom_plant(name))return false;
    plant->kind=name;plant->source.content.set(std::string(name));
    plant->content_age.set(0.);plant->attack_clock.set(0.);plant->one_shot.erase();
    return true;
}
void MortarPlants::advance(const PlantRef& plant) {
    const auto name=plant->source.content;
    if(!name.present() || name.is_null() || !custom_plant(name.get()) || plant->hp.or_missing(0.)<=0. ||
       plant->dead.present() || plant->sleep.present())return;
    plant->content_age.set(plant->content_age.or_missing(0.)+1.);
    const double period=name.get()=="豌豆迫击炮"?500.:300.;
    const double advance=1./std::max(.01,plant->aura_factor.or_missing(1.));
    plant->attack_clock.set(std::min(period,plant->attack_clock.or_missing(0.)+advance));
    if(plant->attack_clock.get()+1e-8<period)return;
    const bool fired=name.get()=="豌豆迫击炮"?mortar(plant):spring(plant);
    if(fired){plant->attack_clock.get()-=period;plant->last_fired.set(double(world_.heroes.tick));}
    else if(name.get()=="豌豆迫击炮")plant->attack_clock.set(period-50.);
}
std::vector<ContentTarget> MortarPlants::enemies(const PlantRef& plant) {
    auto result=queries_.enemies(source_ref(plant));
    std::erase_if(result,[&](const auto& target){return hp(world_,target)<=0.;});
    return result;
}
std::pair<Point,double> MortarPlants::muzzle(const PlantRef& plant)const {
    const double direction=plant->facing>=0.?1.:-1.,tile=world_.runtime.tile;
    return {{(plant->cell.x+.5+direction*.28)*tile,(plant->cell.y+.25)*tile},direction};
}
std::vector<ContentTarget> MortarPlants::mortar_targets(const PlantRef& plant) {
    const auto [origin,direction]=muzzle(plant);const double tile=world_.runtime.tile;
    struct Candidate {double distance;std::string id;ContentTarget target;};
    std::vector<Candidate> candidates;
    for(const auto& target:enemies(plant)) {
        const auto point=targets_.point(target);
        const double dx=wrap_delta(origin.x,point.x,world_.world_width.get()),dy=point.y-origin.y;
        if(dx*direction<-.5*tile || std::abs(dx)>16.*tile || std::abs(dy)>10.*tile)continue;
        candidates.push_back({std::hypot(dx,dy),world_.heroes.source_id(queries_.source(target)),target});
    }
    std::stable_sort(candidates.begin(),candidates.end(),[](const auto& a,const auto& b){
        return std::tie(a.distance,a.id)<std::tie(b.distance,b.id);
    });
    std::vector<ContentTarget> result;result.reserve(candidates.size());
    for(const auto& candidate:candidates)result.push_back(candidate.target);
    return result;
}
Point MortarPlants::lead(const ContentTarget& target)const {
    const auto* body=std::get_if<CombatTarget>(&target);
    if(!body || body->is_hero())return {};
    const auto& unit=body->unit->body;
    if(unit.ice.or_missing(0.)>1000. || unit.butter.or_missing(0.)>0. || unit.stun.or_missing(0.)>0.)return {};
    return {unit.motion.get().vx,0.};
}
MortarAim MortarPlants::aim(const PlantRef& plant,const ContentTarget& target)const {
    const auto [origin,direction]=muzzle(plant);auto point=targets_.point(target);
    point.x=origin.x+wrap_delta(origin.x,point.x,world_.world_width.get());
    auto solution=NativeBallistics::intercept(origin,point,lead(target),speed_,gravity_,2000.,BallisticArc::high);
    if(!solution)solution=NativeBallistics::intercept(origin,point,{},speed_,gravity_,2000.,BallisticArc::high);
    return {origin,solution};
}
bool MortarPlants::mortar(const PlantRef& plant) {
    struct Aim {ContentTarget target;Point start;BallisticSolution solution;};
    std::vector<Aim> aims;aims.reserve(5);
    for(const auto& target:mortar_targets(plant)) {
        const auto result=aim(plant,target);
        if(!result.solution)continue;
        aims.push_back({target,result.start,*result.solution});
        if(aims.size()==5)break;
    }
    if(aims.empty())return false;
    const bool red=blue_secret();
    for(size_t shot=0;shot<5;++shot) {
        const auto& [target,start,solution]=aims[shot%aims.size()];
        const size_t before=world_.runtime.entities.list()->size();
        const double direction=solution.vx>=0.?1.:-1.;
        world_.runtime.native_constructor->add_entity(red?"火豆":"豌豆",direction,{start.x,start.y,solution.vx,solution.vy});
        // Construction may replace the live list. Python slices that new
        // list, then retains those object references for the whole loop.
        const auto live=world_.runtime.entities.list();
        const EntityRoster created(live->begin()+std::min(before,live->size()),live->end());
        for(const auto& entity:created) {
            entity->mortar.mortar.set(true);entity->mortar.speed.set(speed_);
            entity->mortar.target.set(world_.heroes.source_id(queries_.source(target)));
            entity->source.content.set("豌豆迫击炮");entity->facing=direction;
            if(red)red_pea(entity);
        }
    }
    try{world_.runtime.play_sound("射豆");}catch(const std::exception&){}
    MortarPlantEvent event{plant->source.id,false,5,{}};
    for(const auto& result:aims)event.targets.push_back(world_.heroes.source_id(queries_.source(result.target)));
    services_.mortar_event(event);return true;
}
void MortarPlants::red_pea(const EntityRef& entity) {
    entity->kind="火豆";entity->source.fire_lit.set(0.);entity->source.fire_color.set("fire");
    entity->mortar.multi_red.set(true);entity->mortar.tripea_blue.erase();
}
void MortarPlants::split_pea_blue(const EntityRef& entity)const {
    if(entity->kind=="豌豆" && blue_secret())red_pea(entity);
}
bool MortarPlants::blue_secret()const {
    const auto& field=world_.heroes.globals.secrets;
    if(!field.present())return false;
    const auto& secrets=*field.get();
    return std::find(secrets.begin(),secrets.end(),"三向蓝火")!=secrets.end();
}
void MortarPlants::before_entities() {
    const auto roster=world_.runtime.entities.list();
    for(const auto& entity:*roster)if(yes(entity->mortar.mortar))entity->motion.get().vy+=gravity_;
}
double MortarPlants::projectile_damage(const EntityRef& source,const ContentTarget& target,double amount) {
    const auto* body=std::get_if<CombatTarget>(&target);
    auto& shot=source->mortar;
    if(!yes(shot.mortar) || yes(shot.bonus_done) || (body && body->is_hero()))return amount;
    shot.bonus_done.set(true);
    const auto& motion=source->motion.get();const double speed=std::hypot(motion.vx,motion.vy);
    const double initial=std::max(1e-6,shot.speed.or_missing(speed));
    return amount+amount*.45*std::max(0.,speed/initial-1.);
}
bool MortarPlants::spring(const PlantRef& plant) {
    const double tile=world_.runtime.tile,direction=plant->facing>=0.?1.:-1.;
    const Point origin{(plant->cell.x+.5)*tile,(plant->cell.y+.45)*tile};
    struct Candidate {double distance;std::string id;ContentTarget target;Point delta;};
    std::vector<Candidate> candidates;
    for(const auto& target:enemies(plant)) {
        const auto point=targets_.point(target);
        const Point delta{wrap_delta(origin.x,point.x,world_.world_width.get()),point.y-origin.y};
        const double distance=std::hypot(delta.x,delta.y);
        if(distance>2.4*tile || delta.x*direction<-.3*tile)continue;
        candidates.push_back({distance,world_.heroes.source_id(queries_.source(target)),target,delta});
    }
    if(candidates.empty())return false;
    const auto nearest=std::min_element(candidates.begin(),candidates.end(),[](const auto& a,const auto& b){
        return std::tie(a.distance,a.id)<std::tie(b.distance,b.id);
    });
    const double axis=nearest->distance>1e-6?std::atan2(nearest->delta.y,nearest->delta.x):(direction>0.?0.:pi);
    std::vector<Candidate> hits;
    for(const auto& candidate:candidates) {
        const double angle=candidate.distance>1e-6?std::atan2(candidate.delta.y,candidate.delta.x):axis;
        if(std::abs(py::mod((angle-axis)*(180./pi)+180.,360.)-180.)<=30.+1e-9 || candidate.target==nearest->target)
            hits.push_back(candidate);
    }
    std::vector<size_t> order(hits.size());
    for(size_t i=0;i<order.size();++i)order[i]=i;
    std::stable_sort(order.begin(),order.end(),[&](size_t a,size_t b){return hits[a].id<hits[b].id;});
    for(const auto index:order) {
        const auto& hit=hits[index];const auto* body=std::get_if<CombatTarget>(&hit.target);
        const bool hero=body && body->is_hero();
        targets_.damage(source_ref(plant),hit.target,hero?3.:6.,plant->facing,true,HeroHit::spring);
        if(!body || hero)continue;
        const auto roster=world_.targets;
        const auto found=std::find(roster->begin(),roster->end(),*body);
        if(found==roster->end() || body->unit->body.hp<=0.)continue;
        const auto& content=body->unit->source.content;
        if(content.present() && !content.is_null() && (content.get()=="海盗鹦鹉" || content.get()=="乌鸦")) {
            const double max_speed=world_.wind_environment.zombie_speed_max;
            const double limit=(max_speed?max_speed:10.)*50.;
            const double distance=std::hypot(hit.delta.x,hit.delta.y),length=distance?distance:1.;
            const Point unit=distance>1e-6?Point{hit.delta.x/length,hit.delta.y/length}:Point{direction,0.};
            auto& motion=body->unit->body.motion.get();
            if(motion.vx*unit.x<limit*std::abs(unit.x))motion.vx=unit.x*limit;
            motion.vy=unit.y*limit;body->unit->body.blown.set(true);
        }else services_.spring_knockback(size_t(found-roster->begin()),direction*world_.runtime.plk*200.);
    }
    swipes.push_back({world_.heroes.tick,origin,axis});
    try{world_.runtime.play_sound("射豆");}catch(const std::exception&){}
    MortarPlantEvent event{plant->source.id,true,0,{}};
    for(const auto& hit:hits)event.targets.push_back(hit.id);
    services_.mortar_event(event);return true;
}
size_t reflect_mortar_projectiles(TypedBattleState& world,const AttackSource& source,Point center,double radius_tiles) {
    const auto mark=source.id;size_t hits=0;
    const double radius=std::max(1.,world.runtime.tile)*radius_tiles;
    const auto entities=*world.runtime.entities.list();
    for(const auto& entity:entities) {
        auto& state=entity->mortar;
        const bool marked=state.umbrella_reflected.present() && !state.umbrella_reflected.is_null();
        const bool sourced=mark.present() && !mark.is_null();
        if(!yes(state.mortar) || (marked==sourced && (!marked || state.umbrella_reflected.get()==mark.get())))continue;
        auto& motion=entity->motion.get();
        if(std::abs(motion.x-center.x)>radius || std::abs(motion.y-center.y)>radius)continue;
        motion.vx=std::abs(motion.vx)>.001?-motion.vx:(motion.x>=center.x?1.:-1.)*world.runtime.plk*120.;
        entity->facing=motion.vx>=0.?1.:-1.;
        if(sourced)state.umbrella_reflected=mark;else state.umbrella_reflected.set_null();
        ++hits;
    }
    return hits;
}
} // namespace pvz::typed72
