#include "sim/typed/reed_plants.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
#include <unordered_set>

namespace pvz::typed72 {
namespace {
constexpr double pi=0x1.921fb54442d18p+1;
bool reed(std::string_view name){return name=="闪电芦苇" || name=="超载芦苇";}
bool hero_target(const ContentTarget& target) {
    const auto* body=std::get_if<CombatTarget>(&target);
    return body && body->is_hero();
}
}
bool ReedPlants::configure(const PlantRef& plant,std::string_view name) {
    if(!reed(name))return false;
    plant->kind=name;plant->source.content.set(std::string(name));
    plant->content_age.set(0.);plant->reed_clock.set(0.);plant->one_shot.erase();
    return true;
}
double ReedPlants::hp(const ContentTarget& target,double fallback)const {
    if(const auto* plant=std::get_if<PlantRef>(&target))return (*plant)->hp.or_missing(fallback);
    const auto& body=std::get<CombatTarget>(target);
    return body.is_hero()?world_.heroes.cached_proxy(body.hero).hp:body.unit->body.hp;
}
std::vector<ContentTarget> ReedPlants::enemies(const PlantRef& plant) {
    auto result=queries_.enemies(source_ref(plant));
    std::erase_if(result,[&](const auto& target){return hp(target,1.)<=0.;});
    return result;
}
std::optional<double> ReedPlants::in_cone(const PlantRef& plant,const ContentTarget& target)const {
    const auto origin=targets_.point(plant),point=targets_.point(target);
    const double dx=wrap_delta(origin.x,point.x,world_.world_width.get()),dy=point.y-origin.y;
    const double distance=std::hypot(dx,dy);
    if(distance>12.*world_.runtime.tile)return {};
    const double heading=plant->facing>=0.?0.:180.;
    const double angle=distance>1e-6?std::atan2(dy,dx)*(180./pi):heading;
    if(std::abs(py::mod(angle-heading+180.,360.)-180.)>40.+1e-9)return {};
    return distance;
}
std::optional<ContentTarget> ReedPlants::select(const PlantRef& plant) {
    std::optional<ContentTarget> chosen;
    std::pair<double,std::string> best;
    const bool closest=plant->source.content.get()=="闪电芦苇";
    for(const auto& target:enemies(plant)) {
        const auto distance=in_cone(plant,target);
        if(!distance)continue;
        const auto candidate=std::pair{*distance,world_.heroes.source_id(queries_.source(target))};
        if(!chosen || (closest?candidate<best:candidate>best)){chosen=target;best=candidate;}
    }
    return chosen;
}
void ReedPlants::advance(const PlantRef& plant) {
    const auto& name=plant->source.content;
    if(!name.present() || name.is_null() || !reed(name.get()) || plant->hp.or_missing(0.)<=0. ||
       plant->dead.present() || plant->sleep.present())return;
    plant->content_age.set(plant->content_age.or_missing(0.)+1.);
    const double advance=1./std::max(.01,plant->aura_factor.or_missing(1.));
    plant->reed_clock.set(std::min(375.,plant->reed_clock.or_missing(0.)+advance));
    if(plant->reed_clock.get()+1e-8<375.)return;
    const auto target=select(plant);
    if(!target)return;
    plant->reed_clock.get()-=375.;plant->last_fired.set(double(world_.heroes.tick));
    if(name.get()=="闪电芦苇")lightning(plant,*target);else overload(plant,*target);
    try{world_.runtime.play_sound("打雷");}
    catch(const std::exception&){world_.runtime.play_sound("射豆");}
}
void ReedPlants::strike(const PlantRef& plant,const ContentTarget& target,double amount,bool direct) {
    targets_.damage(source_ref(plant),target,amount,plant->facing,false,HeroHit::lightning);
    if(!direct || !electrotherapy)return;
    const auto* body=std::get_if<CombatTarget>(&target);
    if(!body)return;
    if(body->is_hero()) {
        const double stun=std::max(world_.heroes.cached_proxy(body->hero).stun.or_missing(0.),188.);
        world_.heroes.write_proxy_status(body->hero,HeroStatus::stun,stun);
    }else if(body->unit->body.hp>0.) {
        auto& stun=body->unit->body.stun;stun.set(std::max(stun.or_missing(0.),188.));
    }
}
void ReedPlants::lightning(const PlantRef& plant,const ContentTarget& first) {
    std::vector<ContentTarget> hits{first};
    std::unordered_set<std::string> seen{world_.heroes.source_id(queries_.source(first))};
    auto current=first;
    for(int jump=0;jump<5;++jump) {
        const auto origin=targets_.point(current);
        std::optional<ContentTarget> best;
        std::pair<double,std::string> best_key;
        for(const auto& other:enemies(plant)) {
            const auto uid=world_.heroes.source_id(queries_.source(other));
            if(seen.contains(uid))continue;
            const auto point=targets_.point(other);
            const double distance=std::hypot(wrap_delta(origin.x,point.x,world_.world_width.get()),point.y-origin.y);
            const auto key=std::pair{distance,uid};
            if(distance<=world_.runtime.tile+1e-6 && (!best || key<best_key)){best=other;best_key=key;}
        }
        if(!best)break;
        seen.insert(best_key.second);hits.push_back(*best);current=*best;
    }
    for(const auto& target:hits)strike(plant,target,hero_target(target)?6.:7.5,target==first);
    add_bolt(plant,hits);emit(plant,false,hits);
}
std::vector<ContentTarget> ReedPlants::contacts(const PlantRef& plant,const ContentTarget& target) {
    const auto origin=targets_.point(plant),point=targets_.point(target);
    const Point delta{wrap_delta(origin.x,point.x,world_.world_width.get()),point.y-origin.y};
    auto touched=enemies(plant);
    std::erase_if(touched,[&](const auto& other){return other!=target && !targets_.contact(other,origin,delta);});
    return touched;
}
void ReedPlants::overload(const PlantRef& plant,const ContentTarget& target) {
    auto touched=contacts(plant,target);
    if(std::find(touched.begin(),touched.end(),target)==touched.end())touched.push_back(target);
    strike(plant,target,hero_target(target)?3.:6.,true);
    std::vector<std::pair<std::string,ContentTarget>> ordered;
    ordered.reserve(touched.size());
    for(const auto& other:touched)ordered.emplace_back(world_.heroes.source_id(queries_.source(other)),other);
    std::stable_sort(ordered.begin(),ordered.end(),[](const auto& a,const auto& b){return a.first<b.first;});
    for(const auto& [uid,other]:ordered) {
        if(hero_target(other))strike(plant,other,6.);
        else if(hp(other,0.)>0. || other==target)strike(plant,other,12.);
    }
    add_bolt(plant,std::span<const ContentTarget>(&target,1));emit(plant,true,touched);
}
void ReedPlants::add_bolt(const PlantRef& plant,std::span<const ContentTarget> hits) {
    const auto origin=targets_.point(plant);const double tile=world_.runtime.tile;
    std::vector<Point> points{{origin.x+(plant->facing>=0.?tile*.35:-tile*.35),origin.y-tile*.3}};
    for(const auto& target:hits) {
        const auto point=targets_.point(target);const double last=points.back().x;
        points.push_back({last+wrap_delta(last,point.x,world_.world_width.get()),point.y});
    }
    bolts.push_back({world_.heroes.tick,plant->source.content.get(),std::move(points)});
}
void ReedPlants::emit(const PlantRef& plant,bool overload,std::span<const ContentTarget> hits) {
    ReedEvent event{plant->source.id,overload,{}};event.targets.reserve(hits.size());
    for(const auto& target:hits)event.targets.push_back(world_.heroes.source_id(queries_.source(target)));
    services_.reed_event(event);
}
} // namespace pvz::typed72
