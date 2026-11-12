#include "sim/typed/scarecrow.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
namespace {
bool named(const Field<std::string>& content,std::string_view name) {
    return content.present() && !content.is_null() && content.get()==name;
}
bool id_less(const Field<std::string>& first,const Field<std::string>& second) {
    if(first.is_null() && second.is_null())return false;
    return first.or_missing("")<second.or_missing("");
}
class SpawnBanExemption {
public:
    explicit SpawnBanExemption(TypedBattleState& world):world_(world){++world_.spawn_ban_exempt;}
    ~SpawnBanExemption(){--world_.spawn_ban_exempt;}
    SpawnBanExemption(const SpawnBanExemption&)=delete;
private:
    TypedBattleState& world_;
};
}
bool Scarecrows::configure(const ZombieRef& unit,std::string_view name,double hp) {
    if(name!="稻草人" && name!="乌鸦")return false;
    unit->source.content.set(std::string(name));unit->body.hp=hp;unit->max_hp.set(hp);
    unit->base_speed.set(unit->native.move_speed.or_missing(0.));
    unit->body.hand.clear();unit->body.hand_hp=0.;
    if(name=="稻草人") {
        unit->patch.bite_plant.set(0.);unit->patch.no_attack.set(true);unit->source.no_hero_attack.set(true);
        unit->hop_clock.set(0.);unit->walk_speed.set(unit->native.move_speed.get());unit->native.move_speed.set(.001);
    }else {
        unit->body.size.set(2.);unit->patch.bite_plant.set(3.);unit->body.balloon.erase();unit->flight.set(true);
    }
    return true;
}
std::vector<ZombieRef> Scarecrows::living()const {
    std::vector<ZombieRef> result;
    for(const auto& target:*world_.targets)if(target.unit && named(target.unit->source.content,"稻草人") &&
       target.unit->body.hp>0. && !target.unit->body.ash.present())result.push_back(target.unit);
    return result;
}
ScarecrowCells Scarecrows::aura_cells()const {
    ScarecrowCells cells;const double tile=world_.runtime.tile;
    const auto columns=int64_t(world_.world_width.get()/tile);
    for(const auto& unit:living()) {
        if(world_.heroes.owner(source_ref(unit))!=Seat::zombie)continue;
        if(columns<=0)throw std::domain_error("scarecrow map has no columns");
        const auto& point=unit->body.motion.get();
        const auto row=int(std::floor((point.y-tile*.5)/tile));
        const auto column=int64_t(py::mod(std::floor(point.x/tile),double(columns)));
        for(int y=-3;y<=3;++y)for(int x=-3;x<=3;++x)
            cells.emplace(row+y,int64_t(py::mod(double(column+x),double(columns))));
    }
    return cells;
}
double Scarecrows::slow_factor(const PlantRef& plant,const ScarecrowCells& cells) {
    if(!cells.contains({plant->cell.y,plant->cell.x}))return 1.;
    const auto& owner=plant->source.owner;
    return !owner.present() || named(owner,"plant")?1.15:1.;
}
ZombieRef Scarecrows::grave_goal(const ZombieRef& unit)const {
    const auto owner=world_.heroes.owner(source_ref(unit));const auto& position=unit->body.motion.get();
    const auto same_owner=[&](const ZombieRef& grave) {
        const auto& field=grave->source.owner;
        if(!field.present() || field.is_null())return !owner;
        return owner && field.get()==seat_name(*owner);
    };
    std::vector<ZombieRef> graves;
    for(const auto& target:*world_.targets)if(target.unit) {
        const auto& grave=target.unit;
        if(grave->protection.grave && grave->body.hp>0. && same_owner(grave) && !grave->body.ash.present())graves.push_back(grave);
    }
    for(const auto& grave:world_.suspended_graves)if(grave->protection.grave && grave->body.hp>0. && same_owner(grave) &&
       std::find(graves.begin(),graves.end(),grave)==graves.end())graves.push_back(grave);
    ZombieRef best;double best_distance=0.;
    for(const auto& grave:graves) {
        const auto& point=grave->body.motion.get();
        const double dx=wrap_delta(position.x,point.x,world_.world_width.get()),dy=point.y-position.y;
        const double distance=dx*dx+dy*dy;
        if(!best || distance<best_distance ||
           (distance==best_distance && id_less(grave->source.id,best->source.id))) {
            best=grave;best_distance=distance;
        }
    }
    return best;
}
bool Scarecrows::solid(Point point)const {
    const auto row=int64_t(std::floor(point.y/world_.runtime.tile));
    if(row<0)return false;
    if(uint64_t(row)>=published_.solid.size())return true;
    const auto column=size_t(std::floor(py::mod(point.x,world_.world_width.get())/world_.runtime.tile));
    const auto& cells=published_.solid.at(size_t(row));
    if(cells.empty())throw std::domain_error("empty published scarecrow row");
    return cells[column%cells.size()]!=0;
}
void Scarecrows::advance(const ZombieRef& unit,double factor) {
    const auto position=unit->body.motion.get();const double tile=world_.runtime.tile;
    const double plk=world_.runtime.plk?world_.runtime.plk:1.;
    const bool grounded=solid({position.x,position.y+tile*.08}) && std::abs(unit->body.motion.get().vy)<=plk*6.;
    unit->hop_clock.set(unit->hop_clock.or_missing(0.)+(factor?1.:0.));
    if(!factor)return;
    const auto goal=grave_goal(unit);
    const double dx=goal?wrap_delta(position.x,goal->body.motion.get().x,world_.world_width.get()):0.;
    if(std::abs(dx)>tile*1.2) {
        const double direction=dx>0.?1.:-1.;unit->body.facing=direction;
        const double step=std::min(std::abs(dx)-tile,unit->walk_speed.or_missing(0.)*factor);
        if(solid({position.x+direction*(tile*.35+step),position.y-tile*.5})) {
            if(grounded && !solid({position.x,position.y-tile*1.8}))unit->body.motion.get().vy=-world_.runtime.plk*400.;
        }else unit->body.motion.get().x=py::mod(position.x+direction*step,world_.world_width.get());
    }else if(goal)unit->body.facing=dx>=0.?1.:-1.;
    if(grounded && unit->hop_clock.get()>=230.) {
        unit->hop_clock.set(0.);unit->body.motion.get().vy=-world_.runtime.plk*260.;
    }
}
std::optional<std::string> Scarecrows::crow_echo(Point position,const std::string& id) {
    ZombieRef farthest;double best_distance=0.;
    for(const auto& unit:living()) {
        if(world_.heroes.owner(source_ref(unit))!=Seat::zombie)continue;
        const auto& point=unit->body.motion.get();
        const double dx=wrap_delta(position.x,point.x,world_.world_width.get()),dy=point.y-position.y;
        const double distance=-(dx*dx+dy*dy);
        if(!farthest || distance<best_distance ||
           (distance==best_distance && id_less(unit->source.id,farthest->source.id))) {
            farthest=unit;best_distance=distance;
        }
    }
    if(!farthest)return {};
    const auto point=farthest->body.motion.get();std::optional<std::string> child;
    {
        SpawnBanExemption exemption(world_);
        child=services_.spawn_echo_crow({point.x,point.y-world_.runtime.tile},farthest->body.facing,id);
    }
    if(child)services_.crow_echo_event(id,farthest->source.id,*child);
    return child;
}
} // namespace pvz::typed72
