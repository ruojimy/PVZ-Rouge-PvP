#pragma once
#include "sim/typed/native_barrels.h"
#include "sim/typed/content_combat_state.h"
#include "sim/typed/projectile_rules.h"
namespace pvz::typed72 {
class BarrelProjectileServices : public ProjectileImpactDamage {
public:
    virtual void surface_zombie(size_t,double facing,double amount)=0;
    virtual std::optional<TargetRoster> extra_targets()=0;
};
// The same Entity, BonusEntityState, SmartProjectile and live rosters used by
// the native entity phase are consumed here; no copied projectile model.
class BarrelProjectiles {
public:
    BarrelProjectiles(TypedBattleState& world,ContentCombatState& state,
                      ProjectileRules& rules,BarrelProjectileServices& services)
        :world_(world),state_(state),rules_(rules),services_(services){}
    void step();
private:
    TypedBattleState& world_;
    ContentCombatState& state_;
    ProjectileRules& rules_;
    BarrelProjectileServices& services_;
    void record_melon(size_t);
};
} // namespace pvz::typed72
