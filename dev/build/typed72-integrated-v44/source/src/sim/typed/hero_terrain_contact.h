#pragma once
#include "sim/typed/terrain.h"
#include <cmath>
namespace pvz::typed72 {
inline bool hero_terrain_contact(const WorldTerrain& terrain,const Motion& feet,double tile,bool include_water) {
    for(double dx : {-tile*.2, 0., tile*.2}) {
        const auto col=int64_t(std::floor((feet.x+dx)/tile));
        for(double dy : {.1, -tile*.5, -tile*1.2}) {
            const auto row=int64_t(std::floor((feet.y+dy)/tile));
            if(terrain.outside(row,col))continue;
            const auto& cell=terrain.native_at(row,col);
            const auto& block=cell.block.get();
            if(block=="梯子块" || block=="上端梯子块" || block=="下端梯子块" || block=="孤独梯子块" || cell.belt.or_missing(false) || (include_water && (block=="水" || block=="黑水")))return true;
        }
    }
    return false;
}
}
