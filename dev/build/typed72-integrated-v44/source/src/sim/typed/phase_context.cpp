#include "sim/typed/phase_context.h"
#include "sim/typed/projectile_rules.h"
#include "core/pymath.h"
#include <set>

namespace pvz::typed72 {
Seat nearest_plant_seat(const TypedBattleState& world,Point point,std::span<const Seat> present) {
    std::optional<std::pair<double,Seat>> best;
    for(const auto seat:present) {
        if(team_of(seat)!=Seat::plant || world.heroes.players.at(seat_index(seat)).value().hp<=0.)continue;
        const auto& position=*world.heroes.heroes.at(seat_index(seat)).value().frame.position.get();
        const auto key=std::pair{py::hypot(wrap_delta(point.x,position.x,world.world_width.get()),point.y-position.y),seat};
        if(!best || key<*best)best=key;
    }
    return best?best->second:Seat::plant;
}

HiddenGhostCells::HiddenGhostCells(TypedBattleState& world,bool hide) {
    if(!hide)return;
    std::set<std::pair<int,int64_t>> occupied;
    const auto roster=world.plant_roster;
    for(const auto& plant:*roster)
        if(september_targetable(*plant))occupied.emplace(plant->cell.y,plant->cell.x);
    saved_.reserve(roster->size());
    const auto equals=[](const Field<std::string>& field,std::string_view value) {
        return field.present() && !field.is_null() && field.get()==value;
    };
    for(const auto& plant:*roster) {
        if(occupied.contains({plant->cell.y,plant->cell.x}))continue;
        if(!equals(plant->source.content,"幽灵辣椒") &&
           !(plant->kind=="模仿者" && equals(plant->copy_card,"plant:幽灵辣椒")))continue;
        const auto cell=world.terrain.at(plant->cell.y,world.terrain.wrap(plant->cell.x));
        if(cell && cell->plant.present()) {
            saved_.emplace_back(cell,cell->plant);
            cell->plant.erase();
        }
    }
}
void HiddenGhostCells::close() {
    for(const auto& [cell,marker]:saved_)cell->plant=marker;
    saved_.clear();
}
HiddenGhostCells::~HiddenGhostCells(){close();}
} // namespace pvz::typed72
