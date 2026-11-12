#include "sim/typed/terrain_effects.h"
#include "core/pymath.h"
#include <cmath>
namespace pvz::typed72 {
namespace {
int64_t integer(double value) {
    if(!std::isfinite(value)||value<-0x1p63||value>=0x1p63)throw std::out_of_range("terrain integer range");return int64_t(value);
}
int row_integer(double value) {
    const auto n=integer(value);if(n<std::numeric_limits<int>::min()||n>std::numeric_limits<int>::max())throw std::out_of_range("terrain row range");return int(n);
}
bool water(const TerrainCell& tile){return tile.block.present()&&!tile.block.is_null()&&(tile.block.get()=="水"||tile.block.get()=="黑水");}
}
bool chili_ground(const WorldTerrain& map,const TileRef& tile) {
    if(!tile)return false;
    if(tile->plant.present()&&!tile->plant.is_null()&&tile->plant.get())return false;
    if(!tile->block.present()||tile->block.is_null()||tile->block.get().empty())return false;
    const auto& name=tile->block.get();
    constexpr std::array<std::string_view,11> pass{"空","水","黑水","雪","花盆块","坟墓","梯子块","上端梯子块","孤独梯子块","下端梯子块","睡莲块"};
    if(map.is_empty(name)||std::find(pass.begin(),pass.end(),name)!=pass.end())return false;
    for(const auto token:{"梯子","花盆","坟墓","睡莲"})if(name.find(token)!=std::string::npos)return false;
    return true;
}
int64_t chili_fire_column(Point position,double tile) {
    if(tile==0.)throw std::domain_error("zero chili tile scale");return integer(py::round0(position.x/tile-1.));
}
std::optional<int> chili_lane_row(const WorldTerrain& map,Point position,double tile) {
    if(tile<=0.)return {};const auto row=row_integer(py::floordiv(position.y,tile));
    if(map.rows()>0) {
        const auto col=chili_fire_column(position,tile);const auto start=std::max(0,std::min(row,map.rows()-1));
        for(int y=start;y<map.rows();++y)if(chili_ground(map,map.at(y,col)))return y-1;
    }
    return row;
}
std::optional<int> update_chili_row_hint(const WorldTerrain& map,CombatZombie& zombie,double tile,bool force) {
    return update_chili_row_hint(map,zombie.body.motion.get(),zombie.body.gravity,zombie.patch.chili_row_hint,tile,force);
}
std::optional<int> update_chili_row_hint(const WorldTerrain& map,const Motion& p,const Field<double>& gravity,Field<double>& hint,double tile,bool force) {
    const auto old=[&]()->std::optional<int>{if(!hint.present()||hint.is_null())return {};try{return row_integer(hint.get());}catch(const std::exception&){return {};}};
    if(tile<=0.)return old();
    const auto row=chili_lane_row(map,{p.x,p.y},tile);if(!row)return old();
    const auto raw=row_integer(py::floordiv(p.y,tile));
    const double newton=gravity.present()&&!gravity.is_null()?gravity.get():0.;
    const bool grounded=std::abs(int64_t(*row)-raw)<=1&&std::abs(p.vy)<=1.&&std::abs(newton)<=.1;
    if(force||!hint.present()||grounded)hint.set(double(*row));return old();
}
std::optional<GraveCell> gravebuster_cell(const WorldTerrain& map,const CombatZombie& zombie,double tile) {
    tile=std::max(1.,tile);const auto& p=zombie.body.motion.get();
    const auto raw_row=row_integer(py::floordiv(p.y,tile));const auto raw_col=integer(py::floordiv(p.x,tile));
    if(raw_row==std::numeric_limits<int>::min())throw std::out_of_range("grave row underflow");
    const auto lane=chili_lane_row(map,{p.x,p.y},tile);std::vector<int> rows{raw_row-1};
    if(lane&&std::find(rows.begin(),rows.end(),*lane)==rows.end())rows.push_back(*lane);
    if(std::find(rows.begin(),rows.end(),raw_row)==rows.end())rows.push_back(raw_row);
    const auto fire_col=chili_fire_column({p.x,p.y},tile);std::vector<int64_t> cols{raw_col};if(fire_col!=raw_col)cols.push_back(fire_col);
    for(const int y:rows)for(const auto x:cols)if(auto cell=map.at(y,x))return GraveCell{{y,x},std::move(cell)};
    return {};
}
TileRef GravebusterEffects::clear_cell(Cell cell,const TileRef& input) {
    auto tile=input;if(!tile||water(*tile))return tile;
    try{plants_.clear(cell);}catch(const std::exception&){}
    if(auto replaced=world_.terrain.at(cell.y,cell.x))tile=std::move(replaced);
    const auto plants=*world_.plant_roster;
    for(const auto& plant:plants)if(plant->cell.y==cell.y&&plant->cell.x==cell.x) {
        plant->dead.set(DeathMarker(true));plant->shovel_dead.set(DeathMarker(true));
    }
    tile->plant.erase();tile->empty_marker.erase();tile->pot.erase();tile->stone_placeholder.erase();tile->inner_block.erase();
    tile->destroyed.erase();tile->snow_gone.erase();tile->growing.erase();tile->wave.erase();tile->wave_cd.erase();return tile;
}
bool GravebusterEffects::grave(const ZombieRef& zombie) {
    const auto found=gravebuster_cell(world_.terrain,*zombie,world_.runtime.tile);if(!found||water(*found->tile))return false;
    const auto tile=clear_cell(found->coordinate,found->tile);if(!tile||water(*tile))return false;
    tile->block.set("坟墓");tile->grave_art.set(double(world_.runtime.rng.randint(1,5)));tile->growing.set(0.);
    try{plants_.important(found->coordinate,"坟墓");}catch(const std::exception&){}
    ++graves_created;world_.runtime.sound("出坟墓",{});return true;
}
bool GravebusterEffects::plant(const ZombieRef& zombie) {
    const auto found=gravebuster_cell(world_.terrain,*zombie,world_.runtime.tile);if(!found)return false;
    const double facing=zombie->body.facing<0.?-1.:1.;
    try{plants_.plant(found->coordinate,"墓碑吞噬者",facing);}catch(const std::exception&){return false;}
    ++plants_created;return true;
}
} // namespace pvz::typed72
