#pragma once
#include "sim/typed/plant_lookup.h"

namespace pvz::typed72 {
Seat nearest_plant_seat(const TypedBattleState&,Point,std::span<const Seat> present);

// Retain each affected cell itself. A terrain publication inside the region
// must not redirect restoration to a replacement cell at the same coordinate.
class HiddenGhostCells {
public:
    explicit HiddenGhostCells(TypedBattleState&,bool hide=true);
    ~HiddenGhostCells();
    HiddenGhostCells(const HiddenGhostCells&)=delete;
    void close();
private:
    std::vector<std::pair<TileRef,Field<bool>>> saved_;
};
} // namespace pvz::typed72
