#include "sim/typed/content_queries.h"
#include "sim/typed/plant_lookup.h"
#include "sim/typed/projectile_rules.h"
#include "sim/typed/spatial_mode.h"
#include "core/function_profile.h"
#include <algorithm>
#include <limits>

namespace pvz::typed72 {
namespace {
const void* object_key(const ContentTarget& t){if(const auto* p=std::get_if<PlantRef>(&t))return p->get();return std::get<CombatTarget>(t).unit.get();}
}
bool ContentQueries::valid_index()const{return index_tick_==world_.heroes.tick&&zombie_roster_==world_.targets.get()&&plant_roster_==world_.plant_roster.get()&&zombie_data_==world_.targets->data()&&zombie_count_==world_.targets->size()&&plant_data_==world_.plant_roster->data()&&plant_count_==world_.plant_roster->size();}
void ContentQueries::prepare(){
    if(valid_index())return;PVP_PROFILE_SCOPE("ContentQueries::prepare");
    coverage_tick_=-1;
    std::vector<ContentTarget> next;next.reserve(world_.targets->size()+world_.plant_roster->size());
    for(const auto& t:*world_.targets)if(!t.is_hero())next.emplace_back(t);
    for(const auto& p:*world_.plant_roster)next.emplace_back(p);
    if(next!=indexed_){indexed_=std::move(next);object_ids_.clear();zombie_coverage_.reset(world_.runtime.tile,world_.world_width.get(),indexed_.size());plant_coverage_.reset(world_.runtime.tile,world_.world_width.get(),indexed_.size());}
    points_.reset(world_.runtime.tile,world_.world_width.get(),indexed_.size());
    query_seen_.assign(indexed_.size(),0);query_stamp_=0;
    for(size_t i=0;i<indexed_.size();++i){object_ids_[object_key(indexed_[i])]=i;points_.move(i,targets_.point(indexed_[i]));}
    index_tick_=world_.heroes.tick;zombie_roster_=world_.targets.get();plant_roster_=world_.plant_roster.get();zombie_data_=world_.targets->data();zombie_count_=world_.targets->size();plant_data_=world_.plant_roster->data();plant_count_=world_.plant_roster->size();
}
void ContentQueries::prepare_coverage(){
    if(coverage_tick_==world_.heroes.tick)return;
    PVP_PROFILE_SCOPE("ContentQueries::prepare_coverage");
    for(size_t i=0;i<indexed_.size();++i)(std::holds_alternative<PlantRef>(indexed_[i])?plant_coverage_:zombie_coverage_).cover(i,targets_.bounds(indexed_[i]));
    coverage_tick_=world_.heroes.tick;
}
void ContentQueries::moved(const ContentTarget& target){
    if(!valid_index())return;const auto found=object_ids_.find(object_key(target));if(found!=object_ids_.end()){points_.move(found->second,targets_.point(target));if(coverage_tick_==world_.heroes.tick)(std::holds_alternative<PlantRef>(target)?plant_coverage_:zombie_coverage_).cover(found->second,targets_.bounds(target));}
}
std::vector<ContentTarget> ContentQueries::enemies_in_box(const std::shared_ptr<AttackSource>& record,CoverageBox box){
    PVP_PROFILE_SCOPE("ContentQueries::enemies_in_box");++range_queries;
    if(record&&record->plant.present()){
        if(seeking_tick_!=world_.heroes.tick){seeking_tick_=world_.heroes.tick;seeking_.clear();}
        if(seeking_.insert(record.get()).second){++seeking_plant_ticks;max_seeking_plants=std::max<uint64_t>(max_seeking_plants,seeking_.size());}
    }
    const auto owner=world_.heroes.owner(record);
    range_full_scan+=world_.targets->size()+(owner==Seat::zombie?world_.plant_roster->size():0);
    static const bool enabled=[]{const char* p=std::getenv("PVP742_TARGETING");return !p||*p!='0';}();
    if(!enabled||!spatial741_enabled()){auto result=enemies(record);range_candidates+=result.size();return result;}
    prepare();prepare_coverage();std::vector<ContentTarget> result;
    const auto ids=zombie_coverage_.rectangle(box);result.reserve(ids.size()+4);
    for(const auto id:ids)if(eligible(indexed_[id],owner)){++range_candidates;result.push_back(indexed_[id]);}
    if(owner==Seat::zombie)for(const auto id:plant_coverage_.rectangle(box))if(eligible(indexed_[id],owner)){++range_candidates;result.push_back(indexed_[id]);}
    // Hero context swaps are live and are not frozen into either shared index.
    for(const auto& hero:enemy_heroes(owner)){++range_candidates;result.push_back(hero);}
    return result;
}
bool ContentQueries::eligible(const ContentTarget& t,std::optional<Seat> owner)const{
    if(const auto* p=std::get_if<PlantRef>(&t))return owner==Seat::zombie&&september_targetable(**p);
    const auto& z=std::get<CombatTarget>(t);return !z.is_hero()&&z.unit->body.hp>0.&&world_.heroes.owner(source_ref(z.unit))!=owner;
}
std::vector<ContentTarget> ContentQueries::enemy_heroes(std::optional<Seat> owner){
    std::vector<ContentTarget> out;const auto foe=owner==Seat::plant?Seat::zombie:Seat::plant;
    for(const auto side:seats_for(world_.mode))if(team_of(side)==foe&&world_.heroes.proxy(side).hp>0.)out.emplace_back(CombatTarget::player(side));return out;
}
std::optional<ContentTarget> ContentQueries::route_enemies(const ContentTarget& origin,std::optional<ContentTarget> goal,bool heroes){
    PVP_PROFILE_SCOPE("ContentQueries::route_enemies");
    if(!spatial741_enabled()){auto all=enemies(source(origin));if(!heroes)std::erase_if(all,[](const auto& t){const auto* c=std::get_if<CombatTarget>(&t);return c&&c->is_hero();});return route(origin,goal,all);}
    if(!goal)return {};prepare();++local_queries;const auto owner=world_.heroes.owner(source(origin));
    const auto a=targets_.point(origin),b=targets_.point(*goal);const auto width=world_.world_width.get();const double dx=wrap_delta(a.x,b.x,width),dy=b.y-a.y,length2=dx*dx+dy*dy;
    if(length2<=1.e-12)return goal;const double radius=world_.runtime.tile*.65,r2=radius*radius;
    auto chosen=goal;double first=1.;size_t ordinal=std::numeric_limits<size_t>::max();
    const auto consider=[&](const ContentTarget& target,size_t id){++local_candidates;if(target==*goal)return;
        const auto p=targets_.point(target);const double x=wrap_delta(a.x,p.x,width),y=p.y-a.y,along=(x*dx+y*dy)/length2;
        if(along<0.||along>=1.||along>first||(along==first&&id>=ordinal))return;
        const double ex=x-along*dx,ey=y-along*dy;if(ex*ex+ey*ey<=r2){chosen=target;first=along;ordinal=id;}
    };
    // Query the swept route expanded by the original .65-tile intercept
    // radius, then retain its exact projection test and roster-order tie.
    const auto ids=points_.rectangle({std::min(a.x,a.x+dx)-radius,std::min(a.y,b.y)-radius,std::max(a.x,a.x+dx)+radius,std::max(a.y,b.y)+radius});
    for(const auto i:ids)if(eligible(indexed_[i],owner))consider(indexed_[i],i);
    if(heroes){size_t i=indexed_.size();for(const auto& h:enemy_heroes(owner))consider(h,i++);}
    return chosen;
}
std::optional<ContentTarget> ContentQueries::spatial_nearest(const ContentTarget& origin){
    const auto record=source(origin);const auto owner=world_.heroes.owner(record);const auto p=targets_.point(origin);const auto width=world_.world_width.get();
    const bool no_hero=record->no_hero_attack.present()&&!record->no_hero_attack.is_null()&&record->no_hero_attack.get();
    auto heroes=enemy_heroes(owner);if(no_hero)heroes.clear();
    std::optional<ContentTarget> best;double distance=std::numeric_limits<double>::infinity();size_t ordinal=std::numeric_limits<size_t>::max();
    const auto consider=[&](const ContentTarget& t,size_t i){++local_candidates;const auto q=targets_.point(t);const double dx=wrap_delta(p.x,q.x,width),dy=q.y-p.y,d=dx*dx+dy*dy;
        if(d<distance||(d==distance&&i<ordinal)){best=t;distance=d;ordinal=i;}
    };
    for(size_t i=0;i<heroes.size();++i)consider(heroes[i],std::numeric_limits<size_t>::max()-heroes.size()+i);
    // In the original selector a charmed unit always chooses the nearest
    // opposing Dave and then intercepts entities on that route. Computing a
    // nearest ordinary unit first cannot affect that result.
    if(record->charmed.present()&&best)return taunts_.taunt_target(origin,route_enemies(origin,best));
    prepare();++local_queries;const double limit=points_.covering_radius(p);double radius=std::min(world_.runtime.tile,limit);
    if(++query_stamp_==0){std::fill(query_seen_.begin(),query_seen_.end(),0);++query_stamp_;}
    for(;;){const auto ids=points_.rectangle({p.x-radius,p.y-radius,p.x+radius,p.y+radius});
        for(const auto i:ids)if(query_seen_[i]!=query_stamp_){query_seen_[i]=query_stamp_;if(eligible(indexed_[i],owner))consider(indexed_[i],i);}
        if(distance<=radius*radius||radius>=limit)break;radius=std::min(limit,radius*2.);
    }
    return taunts_.taunt_target(origin,std::move(best));
}
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
    PVP_PROFILE_SCOPE("ContentQueries::nearest");
    if(spatial741_enabled())return spatial_nearest(origin);
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
