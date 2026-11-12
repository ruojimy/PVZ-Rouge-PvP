#include "sim/typed/content_queries.h"
#include "sim/typed/plant_lookup.h"
#include "sim/typed/projectile_rules.h"
#include <algorithm>
#include <limits>

namespace pvz::typed72 {
std::shared_ptr<AttackSource> ContentQueries::source(const ContentTarget& target)const {
    if(const auto* plant=std::get_if<PlantRef>(&target))return source_ref(*plant);
    const auto& body=std::get<CombatTarget>(target);
    return body.is_hero()?world_.heroes.proxy_source(body.hero):source_ref(body.unit);
}
std::vector<ContentTarget> ContentQueries::enemies(const std::shared_ptr<AttackSource>& source) {
    const auto owner=world_.heroes.owner(source);
    std::vector<ContentTarget> result;
    result.reserve(world_.targets->size()+world_.plant_roster->size()+2);
    for(const auto& target:*world_.targets)
        if(!target.is_hero() && target.unit->body.hp>0. && world_.heroes.owner(source_ref(target.unit))!=owner)
            result.emplace_back(target);
    if(owner==Seat::zombie)
        for(const auto& plant:*world_.plant_roster)if(september_targetable(*plant))result.emplace_back(plant);
    const auto enemy=owner==Seat::plant?Seat::zombie:Seat::plant;
    for(const auto seat:seats_for(world_.mode)) {
        if(team_of(seat)!=enemy)continue;
        if(world_.heroes.proxy(seat).hp>0.)result.emplace_back(CombatTarget::player(seat));
    }
    return result;
}
std::optional<ContentTarget> ContentQueries::route(const ContentTarget& source,std::optional<ContentTarget> goal,
    std::span<const ContentTarget> candidates)const {
    if(!goal)return {};
    const auto a=targets_.point(source),b=targets_.point(*goal);
    const auto width=world_.world_width.get();
    const double dx=wrap_delta(a.x,b.x,width),dy=b.y-a.y,length2=dx*dx+dy*dy;
    if(length2<=1e-12)return goal;
    auto chosen=goal;
    double first=1.;
    const double radius=world_.runtime.tile*.65,radius2=radius*radius;
    for(const auto& target:candidates) {
        if(target==*goal)continue;
        const auto point=targets_.point(target);
        const double x=wrap_delta(a.x,point.x,width),y=point.y-a.y;
        const double along=(x*dx+y*dy)/length2;
        if(along<0. || along>=first)continue;
        const double ex=x-along*dx,ey=y-along*dy;
        if(ex*ex+ey*ey<=radius2){chosen=target;first=along;}
    }
    return chosen;
}
std::optional<ContentTarget> ContentQueries::nearest(const ContentTarget& origin) {
    const auto record=source(origin);
    auto candidates=enemies(record);
    const auto point=targets_.point(origin);
    const auto width=world_.world_width.get();
    const bool no_hero=record->no_hero_attack.present() && !record->no_hero_attack.is_null() && record->no_hero_attack.get();
    if(no_hero)std::erase_if(candidates,[](const auto& target){
        const auto* body=std::get_if<CombatTarget>(&target);return body && body->is_hero();
    });
    std::optional<ContentTarget> nearest,hero;
    double best=std::numeric_limits<double>::infinity(),hero_best=best;
    for(const auto& target:candidates) {
        const auto position=targets_.point(target);
        const double dx=wrap_delta(point.x,position.x,width),dy=position.y-point.y,distance=dx*dx+dy*dy;
        if(distance<best){nearest=target;best=distance;}
        const auto* body=std::get_if<CombatTarget>(&target);
        if(record->charmed.present() && body && body->is_hero() && distance<hero_best){hero=target;hero_best=distance;}
    }
    if(record->charmed.present() && hero)nearest=route(origin,hero,candidates);
    return taunts_.taunt_target(origin,std::move(nearest));
}
} // namespace pvz::typed72
