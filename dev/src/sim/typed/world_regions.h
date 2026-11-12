#pragma once
#include "sim/typed/plant_spawn.h"
#include "sim/typed/flood.h"

namespace pvz::typed72 {
struct NativeSun {
    double age=0.;
    Motion motion;
    double animation=0.,size=1.;
    std::optional<Seat> producer;
    std::optional<double> bloom_amount;
};
struct WorldRegionState {
    double water_wave=0.,water_offset=0.;
    int landing=0;
    std::vector<std::shared_ptr<NativeSun>> loose_suns;
};
class WorldRegions {
public:
    WorldRegions(TypedBattleState& world,WorldRegionState& state,PlantLifecycle& plants)
        :world_(world),state_(state),plants_(plants){}
    void water_animation();
    void important_blocks();
    void ice_clock();
    void sun_motion(NativeSun&);
private:
    TypedBattleState& world_;
    WorldRegionState& state_;
    PlantLifecycle& plants_;
};
} // namespace pvz::typed72
