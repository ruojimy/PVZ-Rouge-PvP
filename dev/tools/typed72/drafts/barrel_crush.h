#pragma once
#include "sim/typed/zombie_actions.h"
namespace pvz::typed72 {
// NativeBarrelServices::crush_barrel_plant delegates here. The original native
// plant-death, virtual HP, flattened art and expiry implementation is shared
// with vehicle/giant actions, and remains the one authoritative implementation.
class NativeBarrelCrush {
public:
    NativeBarrelCrush(TypedBattleState& world,ZombieActions& actions,const ZombieActionServices& art)
        :world_(world),actions_(actions),art_(art){}
    void crush(const ZombieRef&,const PlantRef&);
private:
    TypedBattleState& world_;
    ZombieActions& actions_;
    const ZombieActionServices& art_;
};
} // namespace pvz::typed72
