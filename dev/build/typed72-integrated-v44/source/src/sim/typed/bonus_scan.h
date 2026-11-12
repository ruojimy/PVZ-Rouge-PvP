#pragma once
#include "sim/typed/bonus_plants.h"
#include "sim/typed/plant_zombie_shooting.h"

namespace pvz::typed72 {
struct BonusScanSystems {
    BonusPlants& plants;
    BonusProjectiles& projectiles;
    NativeDeathChain& deaths;
    PlantZombieShooting& shooting;
    LanternEffects& lantern;
    ZombiePeas& peas;
    FumeEffects& fume;
    SquashEffects& squash;
};

// All combat subloops call their concrete typed implementations. UI/campaign
// installers disconnected by NativeCombatPatch never enter this scheduler.
class BonusScan {
public:
    BonusScan(TypedBattleState& world, BonusScanSystems systems)
        : world_(world), systems_(systems) {}
    double now = 0., last_scan = 0., last_maintenance = 0.;
    uint64_t tick_calls = 0;
    bool closed = false;
    void before(double time);
    void after(double time, std::span<const Seat> hero_order);
    void scan();
    void track_max_hp();
    void death_effects();
private:
    TypedBattleState& world_;
    BonusScanSystems systems_;
};
} // namespace pvz::typed72
