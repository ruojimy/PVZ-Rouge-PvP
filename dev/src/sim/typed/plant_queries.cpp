#include "sim/typed/plant_queries.h"
#include "sim/typed/plant_lookup.h"
#include <algorithm>
#include <cmath>
#include <numeric>

namespace pvz::typed72 {
namespace {
bool named(const Field<std::string>& field,std::string_view name) {
    return field.present() && !field.is_null() && field.get()==name;
}
bool contains(std::span<const std::string> names,std::string_view name) {
    return std::find(names.begin(),names.end(),name)!=names.end();
}
bool tagged(const CombatPlant& plant,std::span<const std::string> names) {
    if(plant.source.content.present() && !plant.source.content.is_null() && contains(names,plant.source.content.get()))return true;
    if(plant.kind!="模仿者" || !plant.copy_card.present() || plant.copy_card.is_null())return false;
    const auto& card=plant.copy_card.get();
    return contains(names,card.size()>6?std::string_view(card).substr(6):std::string_view{});
}
double number(const Field<double>& field,double fallback) {
    return field.present() && !field.is_null()?field.get():fallback;
}
struct StarBody {double hp,size;Point point;};
StarBody star_body(TypedBattleState& world,const CombatTarget& target) {
    if(target.is_hero()) {
        const auto& proxy=world.heroes.cached_proxy(target.hero);
        return {proxy.hp,number(proxy.size,2.),{proxy.position->x,proxy.position->y}};
    }
    const auto& body=target.unit->body;const auto& p=body.motion.get();
    return {body.hp,number(body.size,2.),{p.x,p.y}};
}
bool on_ray(StarBody body,Point origin,double tile,const std::array<Point,5>& rays) {
    if(body.hp<=0.)return false;
    const double dx=body.point.x-origin.x,dy=body.point.y-tile*.35*body.size-origin.y;
    if(std::sqrt(dx*dx+dy*dy)<tile*.45)return false;
    const double limit=std::max(18.,tile*.42)+tile*std::max(.22,.18*body.size);
    return std::any_of(rays.begin(),rays.end(),[&](Point ray) {
        return dx*ray.x+dy*ray.y>tile*.25 && std::abs(dx*ray.y-dy*ray.x)<=limit;
    });
}
class StarChart {
public:
    StarChart(NativeTracking& chart,Point origin):chart_(chart),restore_(!chart.active()) {
        if(!restore_)return;
        auto source=std::make_shared<AttackSource>();source->projectile.set("star-target");source->owner.set("plant");
        chart_.begin({std::move(source),{},origin});
    }
    ~StarChart(){if(restore_)chart_.restore();}
private:
    NativeTracking& chart_;
    bool restore_;
};
}
bool plant_needs_support(const TypedBattleState& world,size_t index,std::span<const std::string> air,
                         std::span<const std::string> flying) {
    const auto& plant=*world.plant_roster->at(index);
    if(named(plant.source.content,"水盆") || named(plant.source.content,"抓人草触手"))return false;
    if(pvp_shell(plant))for(const auto& other:*world.plant_roster) {
        if(other.get()!=&plant && other->cell==plant.cell && other->hp.or_missing(0.)>0. &&
           !other->dead.present() && tagged(*other,flying))return false;
    }
    const auto& secrets=*world.heroes.globals.secrets.get();
    if(plant.kind=="海蘑菇" && contains(secrets,"水兵"))return false;
    return !tagged(plant,air) && plant.kind!="花盆" && plant.kind!="墓碑吞噬者";
}
bool plant_edible_target(const TypedBattleState& world,size_t index) {
    const auto& target=world.targets->at(index);
    if(target.is_hero())return number(world.heroes.cached_proxy(target.hero).size,0.)==2.;
    const auto& unit=*target.unit;
    if(world.heroes.tick<unit.protection.anchor_until.or_missing(0.))return false;
    if(named(unit.source.variant,"角斗士巨人") || named(unit.source.content,"红眼巨人"))return false;
    if((unit.source.content.present() && !unit.source.content.is_null() && !unit.source.content.get().empty()) ||
       (unit.source.variant.present() && !unit.source.variant.is_null() && !unit.source.variant.get().empty()))return true;
    return number(unit.body.size,0.)==2.;
}
bool plant_wind_target(const Entity& entity,std::span<const std::string> damaging) {
    return (entity.flying_plant.present() && !entity.flying_plant.is_null() && entity.flying_plant.get()) || contains(damaging,entity.kind);
}
std::span<const int64_t> plant_pitcher_columns(const CombatPlant& plant) {
    static const auto columns=[] {std::array<int64_t,36> result{};std::iota(result.begin(),result.end(),0);return result;}();
    return std::span<const int64_t>(columns).first(named(plant.source.content,"甜椒投手")?36:16);
}
bool plant_star_target(TypedBattleState& world,NativeTracking& chart,size_t index) {
    const auto& plant=*world.plant_roster->at(index);const double tile=world.runtime.tile;
    const Point origin{(plant.cell.x+.5)*tile,(plant.cell.y+.5)*tile};
    const double pi=std::acos(-1.),base=plant.facing<0.?0.:pi,step=2.*pi/5.;
    std::array<Point,5> rays{};const std::array<int,5> offsets{0,-1,1,-2,2};
    for(size_t i=0;i<rays.size();++i) {const auto angle=base+offsets[i]*step;rays[i]={std::cos(angle),-std::sin(angle)};}
    {
        StarChart scope(chart,origin);
        for(const auto& target:*world.targets)if(on_ray(star_body(world,target),origin,tile,rays))return true;
    }
    // NativeBattle copies the hero heads before the second wrapped query.
    // A temporary periodic chart affects the original records, so the copied
    // points deliberately retain the coordinates observed at this boundary.
    std::vector<StarBody> heads;
    for(const auto& target:*world.targets)if(target.is_hero()) {
        auto head=star_body(world,target);head.point.y-=tile*.7;heads.push_back(head);
    }
    if(heads.empty())return false;
    StarChart scope(chart,origin);
    return std::any_of(heads.begin(),heads.end(),[&](const auto& head){return on_ray(head,origin,tile,rays);});
}
} // namespace pvz::typed72
