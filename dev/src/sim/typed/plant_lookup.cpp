#include "sim/typed/plant_lookup.h"
#include <algorithm>

namespace pvz::typed72 {
namespace {
bool equals(const Field<std::string>& value,std::string_view name) {
    return value.present() && !value.is_null() && value.get()==name;
}
}
bool pvp_shell(const CombatPlant& plant) {
    const auto& tag=plant.source.content;
    return plant.kind=="南瓜头" || equals(tag,"阳光藤蔓") || equals(tag,"忧郁藤蔓") ||
           equals(tag,"抓人草") || (plant.kind=="模仿者" && equals(plant.copy_card,"plant:抓人草"));
}
bool september_targetable(const CombatPlant& plant) {
    return plant.hp.or_missing(0.)>0. && !plant.dead.present() &&
           !equals(plant.source.content,"幽灵辣椒") &&
           !(plant.kind=="模仿者" && equals(plant.copy_card,"plant:幽灵辣椒"));
}
std::optional<size_t> lookup_pvp_plant(const TypedBattleState& world,Cell cell,bool skip_shell) {
    const auto& active=world.heroes.active;
    const bool hide=active && active->owner==Seat::zombie &&
        (active->phase==CombatPhase::zombies || active->phase==CombatPhase::entities);
    std::optional<size_t> shell,found;
    for(size_t i=0;i<world.plant_roster->size();++i) {
        const auto& p=*world.plant_roster->at(i);
        if(p.cell!=cell)continue;
        const bool is_shell=pvp_shell(p);
        if(hide && !september_targetable(p) && !is_shell)continue;
        if(is_shell) {
            if(skip_shell)continue;
            if((!world.dense_planting && !shell) || (world.dense_planting && hide))shell=i;
        }
        found=i;
    }
    return shell?shell:found;
}
bool clear_pvp_plant(TypedBattleState& world,Cell cell){
    const auto i=lookup_pvp_plant(world,cell,false);
    if(!i)return false;
    world.plant_roster->at(*i)->dead.set(DeathMarker(0.));return true;
}
PeaShellScope::PeaShellScope(TypedBattleState& world)
    : world_(world),previous_(world.pea_shell_cells),installed_(world.dense_planting) {
    if(!installed_)return;
    for(const auto& plant:*world.plant_roster) {
        if(pvp_shell(*plant) && plant->hp.or_missing(0.)>0. && !plant->dead.present())
            cells_.push_back(plant->cell);
    }
    // A row-major, sorted unique set admits negative and off-grid columns.
    const auto less=[](Cell a,Cell b) {return a.y!=b.y?a.y<b.y:a.x<b.x;};
    std::sort(cells_.begin(),cells_.end(),less);
    cells_.erase(std::unique(cells_.begin(),cells_.end()),cells_.end());
    world_.pea_shell_cells=&cells_;
}
PeaShellScope::~PeaShellScope() {
    if(installed_)world_.pea_shell_cells=previous_;
}
std::optional<Point> patch_plant_point(const TypedBattleState& world,const CombatPlant& plant) {
    if(const auto* cells=world.pea_shell_cells; cells && !pvp_shell(plant)) {
        const auto less=[](Cell a,Cell b) {return a.y!=b.y?a.y<b.y:a.x<b.x;};
        if(std::binary_search(cells->begin(),cells->end(),plant.cell,less))return {};
    }
    const auto tile=world.runtime.tile;
    return Point{plant.cell.x*tile+tile*.50,plant.cell.y*tile+tile*.45};
}
} // namespace pvz::typed72
