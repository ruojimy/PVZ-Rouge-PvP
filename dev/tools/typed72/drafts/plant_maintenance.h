#pragma once
#include "sim/typed/plant_death_rules.h"
#include "sim/typed/plant_lookup.h"
#include "sim/typed/squash_effects.h"

namespace pvz::typed72 {
// The PvP entry owns the same plants HeroContext as NativeBattle._step_original.
// That context selects normal mode for the complete maintenance region.
class PlantMaintenance {
public:
    PlantMaintenance(TypedBattleState& world,WorldRegionState& region,PlantLifecycle& plants,
                     SquashCallbacks& combat,NativeEntityConstructor& constructor,PlantDeathPolicy& policy)
        :world_(world),region_(region),plants_(plants),combat_(combat),constructor_(constructor),policy_(policy){}
    void run();
private:
    TypedBattleState& world_;
    WorldRegionState& region_;
    PlantLifecycle& plants_;
    SquashCallbacks& combat_;
    NativeEntityConstructor& constructor_;
    PlantDeathPolicy& policy_;
    CombatPlant& plant(size_t index)const{return *world_.plant_roster->at(index);}
    ZombieRecordFields& body(size_t)const;
    Motion& motion(size_t)const;
    Point center(size_t)const;
    Entity& spawn(std::string,double facing,Motion,double expires);
    void knock(Point,double radius,double horizontal,double vertical);
    void doom(size_t);
    void cherry(size_t);
    void chili(size_t);
    void kelp(size_t);
    void mine(size_t);
    void supplement(size_t);
    bool burnable(Cell)const;
};
} // namespace pvz::typed72
