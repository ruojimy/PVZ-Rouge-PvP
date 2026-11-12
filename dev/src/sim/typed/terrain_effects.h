#pragma once
#include "sim/typed/plant_spawn.h"
namespace pvz::typed72 {
int64_t chili_fire_column(Point,double tile);
bool chili_ground(const WorldTerrain&,const TileRef&);
std::optional<int> chili_lane_row(const WorldTerrain&,Point,double tile);
std::optional<int> update_chili_row_hint(const WorldTerrain&,CombatZombie&,double tile,bool force=false);
std::optional<int> update_chili_row_hint(const WorldTerrain&,const Motion&,const Field<double>& gravity,Field<double>& hint,double tile,bool force=false);
struct GraveCell {Cell coordinate;TileRef tile;};
std::optional<GraveCell> gravebuster_cell(const WorldTerrain&,const CombatZombie&,double tile);

// The exact placement/clear/important-block chain is an explicit synchronous
// dependency. PvP's full constructor/admission wrappers will implement this
// same typed interface; the raw implementation is independently executable.
class OriginalPlantLifecycle : public PlantLifecycle {
public:
    explicit OriginalPlantLifecycle(TypedBattleState& world):world_(world){}
    bool clear(Cell cell)override{return clear_original_plant(world_,cell);}
    void plant(Cell cell,std::string name,double facing)override{plant_original(world_,cell,std::move(name),facing);}
    void important(Cell cell,std::string name)override{world_.terrain.important.push_back({cell,std::move(name)});}
protected:
    TypedBattleState& world_;
};
class GravebusterEffects {
public:
    GravebusterEffects(TypedBattleState& world,PlantLifecycle& plants):world_(world),plants_(plants){}
    TileRef clear_cell(Cell,const TileRef&);
    bool grave(const ZombieRef&);
    bool plant(const ZombieRef&);
    uint64_t graves_created=0,plants_created=0;
private:
    TypedBattleState& world_;
    PlantLifecycle& plants_;
};
} // namespace pvz::typed72
