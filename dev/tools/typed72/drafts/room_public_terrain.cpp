#include "sim/typed/room_public_terrain.h"
#include <algorithm>
namespace pvz::typed72 {
namespace {
template<class T>bool same_field(const Field<T>& a,const Field<T>& b){if(a.present()!=b.present()||a.is_null()!=b.is_null())return false;return !a.present()||a.is_null()||a.get()==b.get();}
template<class T>bool truth(const Field<T>& v){return v.present()&&!v.is_null()&&bool(v.get());}
std::string string_field(const Field<std::string>& v,const char* fallback){return !v.present()?fallback:v.is_null()?"None":v.get();}
}
bool RoomPublicTerrain::same(const TerrainCell& a,const TerrainCell& b){
    if(!same_field(a.block,b.block)||!same_field(a.inner_block,b.inner_block))return false;
#define SAME(n,k) if(!same_field(a.n,b.n))return false;
    PVZ72_TILE_NUMBERS(SAME)
    PVZ72_TILE_FLAGS(SAME)
#undef SAME
    return true;
}
RoomPublicCell RoomPublicTerrain::project(const TerrainCell& cell,const WorldTerrain& terrain){
    RoomPublicCell out;out.native=cell;out.kind=string_field(cell.block,"空");out.background=string_field(cell.inner_block,"");
    out.water=out.kind=="水"||out.kind=="海水"||out.kind=="池水"||out.kind.ends_with("水");out.ladder=out.kind=="梯子块"||out.kind=="梯子"||out.kind=="扶梯";
    out.solid=!terrain.is_empty(out.kind)&&!out.water&&!out.ladder&&!out.kind.empty()&&out.kind!="空";return out;
}
bool RoomPublicTerrain::sync(const WorldTerrain& terrain,std::span<const Cell> head_only,TargetSight& sight){
    bool changed=false;belts.clear();
    // Initial cold admission normally supplies the map. Resizing is explicit
    // for first publication or a validated map replacement, not per-frame.
    if(tiles.size()!=terrain.grid.size()){tiles.resize(terrain.grid.size());sight.solid.resize(tiles.size());sight.water.resize(tiles.size());changed=true;}
    sight.solid.resize(tiles.size());sight.water.resize(tiles.size());
    for(size_t row=0;row<terrain.grid.size();++row){
        const auto columns=terrain.grid[row].size();const bool resized=tiles[row].size()!=columns;
        const bool sight_resized=sight.solid[row].size()!=columns||sight.water[row].size()!=columns;
        sight.solid[row].resize(columns);sight.water[row].resize(columns);
        if(resized){tiles[row].resize(columns);changed=true;}
        for(size_t col=0;col<columns;++col){
            const auto& cell=*terrain.grid[row][col];if(truth(cell.belt))belts.insert(int64_t(row)*(1<<16)+int64_t(col));
            auto filtered=cell;filtered.root_animation.erase();for(const auto& head:head_only)if(head.y==int64_t(row)&&head.x==int64_t(col)){filtered.plant.erase();break;}
            if(resized||!same(tiles[row][col].native,filtered)){
                tiles[row][col]=project(filtered,terrain);sight.solid[row][col]=tiles[row][col].solid;sight.water[row][col]=tiles[row][col].water;changed=true;
            }else if(sight_resized){sight.solid[row][col]=tiles[row][col].solid;sight.water[row][col]=tiles[row][col].water;}
        }
    }
    if(changed)++revision;return changed;
}
} // namespace pvz::typed72
