#pragma once
#include "sim/typed/resources.h"
#include "sim/typed/native_tracking.h"

namespace pvz::typed72 {
struct HeroRecoveryRules {
    double delay=0.,interval=0.,amount=0.;
    bool deathmatch=false;
};
class HeroRecovery {
public:
    HeroRecovery(TypedBattleState& world,Resources& resources,const TargetSight& map)
        :world_(world),resources_(resources),map_(map){}
    void water_damage(std::span<const Seat>,double elapsed,bool deathmatch);
    void masochist(Seat);
    void sturdy(Seat);
    void regenerate(double elapsed,const HeroRecoveryRules&);
    void advance(std::span<const Seat>,double elapsed,const HeroRecoveryRules&);
private:
    TypedBattleState& world_;
    Resources& resources_;
    const TargetSight& map_;
};
} // namespace pvz::typed72
