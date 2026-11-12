#pragma once
#include "sim/typed/plant_spawn.h"
#include "sim/typed/projectile_rules.h"
namespace pvz::typed72 {
// Calls retain the installed synchronous hooks. Missing hooks cannot silently
// select the old runtime or suppress a required explosion effect.
class DoomServices {
public:
    virtual ~DoomServices()=default;
    virtual void add_entity(std::string,double facing,Motion)=0;
    virtual void destroy_block(Cell)=0;
    virtual std::optional<TargetRoster> extra_targets()=0;
    virtual void ash_target(size_t,TargetDamage& damage,CombatTarget target){damage.ash(std::move(target));}
};
class DoomEffects {
public:
    DoomEffects(TypedBattleState& world,TargetDamage& damage,PlantLifecycle& plants,DoomServices& services,const CollisionCatalog& catalog)
        :world_(world),damage_(damage),plants_(plants),services_(services),catalog_(catalog){}
    bool explode(const ZombieRef&);
    size_t ash_targets(const ZombieRef&,Point,double scale);
    size_t destroy_blocks(Point,double scale);
    void visuals(Point,double scale);
    void knock_player(Point,double scale);
    void kill_plant(const PlantRef&);
    uint64_t explosions=0;
private:
    size_t native_ash_targets(const ZombieRef&,Point,double);
    TypedBattleState& world_;
    TargetDamage& damage_;
    PlantLifecycle& plants_;
    DoomServices& services_;
    const CollisionCatalog& catalog_;
    Point target_point(const CombatTarget&)const;
    EntityRef spawn_effect(std::string,double facing,Motion,double expires);
};
} // namespace pvz::typed72
