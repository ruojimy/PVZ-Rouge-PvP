#pragma once
#include "sim/typed/state.h"
#include "sim/typed/grenadier_state.h"
namespace pvz::typed72 {
// Native rain is a numeric list, not an entity dictionary. Its third slot
// is changed by the original wind patch even when no fourth slot exists.
using RainPoint=std::shared_ptr<std::vector<double>>;
using RainRoster=std::vector<RainPoint>;
struct WindEnvironment {
    std::shared_ptr<RainRoster> rain=std::make_shared<RainRoster>();
    std::shared_ptr<std::vector<std::string>> damage_entities=std::make_shared<std::vector<std::string>>();
    double zombie_speed_max=10.;
};
// PvP64 grenades and PvP70 hook/bone projectiles have their own authoritative
// records, outside the native entity movement loop. These are their actual
// common fields; kind is absent on grenades. No copied wind-only bodies.
struct ContentProjectile {
    Field<std::string> kind,source,target;
    Motion motion;
    double age=0.,direction=1.;
    Field<Seat> owner,seat;
    Field<Cell> cell;
    Field<bool> anchor,defused,instant;
};
using ContentProjectileRef=std::shared_ptr<ContentProjectile>;
struct ContentProjectiles {
    EntityRoster flying;
    std::vector<ContentProjectileRef> shots;
    std::shared_ptr<GrenadeRoster> grenades=std::make_shared<GrenadeRoster>();
};
} // namespace pvz::typed72
