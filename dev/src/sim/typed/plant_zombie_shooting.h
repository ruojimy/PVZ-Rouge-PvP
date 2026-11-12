#pragma once
#include "sim/typed/death_chain.h"
#include "sim/typed/wind_effects.h"
#include "sim/typed/lantern_effects.h"
#include "sim/typed/service_plants.h"
#include "sim/typed/fume_effects.h"
#include "sim/typed/squash_effects.h"
#include "sim/typed/zombie_pea.h"
namespace pvz::typed72 {
struct PlantZombieSystems {
    NativeDeathChain& deaths;
    WindEffects& wind;
    LanternEffects& lantern;
    ServicePlants& services;
    FumeEffects& fume;
    SquashEffects& squash;
    ZombiePeas& peas;
};
// The actual native bonus-scan shooting subloop. It composes the installed
// typed services; the enclosing bonus scan and main driver remain separate.
class PlantZombieShooting {
public:
    PlantZombieShooting(TypedBattleState& w,PlantZombieSystems systems,const CollisionCatalog& c)
        :world_(w),systems_(systems),aim_(w,c){}
    uint64_t motion_fixes=0;
    static bool live(std::span<const CombatTarget>,std::optional<std::span<const std::string>> names={});
    void enforce_motion(const ZombieRef&,const PlantZombieConfig&);
    void jump_assist(const ZombieRef&,const PlantZombieConfig&);
    void step(std::span<const PlantZombieConfig> catalog=native_plant_zombie_catalog());
private:
    TypedBattleState& world_;
    PlantZombieSystems systems_;
    PlantZombieTargeting aim_;
    bool solid(int64_t row,int64_t col)const;
};
} // namespace pvz::typed72
