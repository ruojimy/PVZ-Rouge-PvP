#include "sim/typed/sea_shroom.h"
#include "sim/typed/projectile_rules.h"
#include <algorithm>
#include <cmath>

namespace pvz::typed72 {
void SeaShroom::restore(){if(saved_rows_)indexes_.rows=std::move(saved_rows_);}
std::optional<int> SeaShroom::water_grave(const CombatTarget& target,std::optional<Seat> owner)const {
    if(target.is_hero())return {};
    const auto& unit=*target.unit;
    if(!unit.protection.grave || unit.body.hp<=0. || unit.body.ash.present() ||
       world_.heroes.owner(source_ref(target.unit))==owner)return {};
    const auto& point=unit.body.motion.get();const auto tile=world_.runtime.tile;
    const auto row=int(std::floor((point.y-.001)/tile));
    if(map_.water_at({point.x,(row+1)*tile+1.},tile,world_.world_width.get()))return row;
    return {};
}
void SeaShroom::gate(const PlantRef& plant) {
    restore();
    if(plant->kind!="海蘑菇" || plant->hp.or_missing(0.)<=0. || plant->sleep.present())return;
    const auto owner=world_.heroes.owner(source_ref(plant));std::vector<int64_t> extra;
    for(const auto& target:*world_.targets) {
        const auto row=water_grave(target,owner);
        if(row && *row==plant->cell.y-1)
            extra.push_back(int64_t(std::floor(target.unit->body.motion.get().x/world_.runtime.tile)));
    }
    if(extra.empty())return;
    auto rows=std::make_shared<TargetBuckets>(*indexes_.rows);
    const auto row=std::find_if(rows->begin(),rows->end(),[&](const auto& item){return item.first==plant->cell.y;});
    if(row==rows->end())rows->emplace_back(plant->cell.y,std::move(extra));
    else row->second.insert(row->second.end(),extra.begin(),extra.end());
    saved_rows_=std::exchange(indexes_.rows,std::move(rows));
}
void SeaShroom::bubbles() {
    EntityRoster shots;
    for(const auto& entity:*world_.runtime.entities.list()) {
        const auto& expires=entity->expires;
        if(entity->kind=="海泡泡" && (!expires.present() || expires.is_null() || expires.get()==0.))shots.push_back(entity);
    }
    if(shots.empty())return;
    EntityRoster spent;const auto tile=world_.runtime.tile,width=world_.world_width.get();
    for(const auto& entity:shots) {
        const auto point=entity->motion.get();const auto owner=world_.heroes.owner(source_ref(entity));
        for(const auto& target:*world_.targets) {
            if(!water_grave(target,owner))continue;
            const auto& grave=target.unit->body.motion.get();
            if(std::abs(wrap_delta(point.x,grave.x,width))>tile*.5 || !(grave.y-tile*.85<point.y && point.y<=grave.y+tile*.7))continue;
            damage_.damage(source_ref(entity),target,5.,entity->facing,true,HeroHit::content);
            spent.push_back(entity);break;
        }
    }
    if(spent.empty())return;
    auto remaining=std::make_shared<EntityRoster>();
    for(const auto& entity:*world_.runtime.entities.list())
        if(std::find(spent.begin(),spent.end(),entity)==spent.end())remaining->push_back(entity);
    world_.runtime.entities.replace(std::move(remaining));
}
} // namespace pvz::typed72
