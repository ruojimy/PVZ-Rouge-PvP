#pragma once
#include "sim/typed/native_tracking.h"
#include <set>
namespace pvz::typed72 {
struct RoomPublicCell {
    std::string kind,background;
    bool solid=false,water=false,ladder=false;
    TerrainCell native;
};
// Terrain publication strips only the same two engine-only fields as PvP72.
// Cell comparison is typed; JSON serialization occurs only when requested by
// a snapshot consumer, never in NativeTick or the 30 Hz publish loop.
class RoomPublicTerrain {
public:
    std::vector<std::vector<RoomPublicCell>> tiles;
    std::set<int64_t> belts;
    int64_t revision=0;
    bool sync(const WorldTerrain&,std::span<const Cell> head_only,TargetSight& published_sight);
    static RoomPublicCell project(const TerrainCell&,const WorldTerrain&);
private:
    static bool same(const TerrainCell&,const TerrainCell&);
};
} // namespace pvz::typed72
