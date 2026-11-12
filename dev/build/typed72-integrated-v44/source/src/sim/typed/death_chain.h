#pragma once
#include "sim/typed/chili_effects.h"
#include "sim/typed/damage_patch.h"
#include "sim/typed/doom_effects.h"
#include "sim/typed/sourced_context.h"
namespace pvz::typed72 {
class DeathServices:public DoomServices,public ChiliServices {
public:
    virtual void armor_broken(const ZombieRef&,ArmorSlot,const std::string&,double)=0;
    // PvP73: NativeBattle._install_grave_deaths overrides of the patch's gravebuster death effects.
    // Default (fixtures without a PvP battle): the original tile grave / native gravebuster plant.
    virtual std::optional<bool> gravebuster_bone(const ZombieRef&){return std::nullopt;}
    virtual std::optional<bool> gravebuster_charmed_plant(const ZombieRef&){return std::nullopt;}
};
// One synchronous chain, one packet set, one authoritative world. Remaining
// plant admission, omitted-target registry and asset loading are required
// installed services, not alternate dynamic backends.
class NativeDeathChain final:public DamagePatchEffects,public ChiliDispatch {
public:
    NativeDeathChain(TypedBattleState&,PlantLifecycle&,DeathServices&,const CollisionCatalog&);
    DamagePatch patch;
    TargetDamage damage;
    DoomEffects doom;
    GravebusterEffects graves;
    ChiliEffects chili;
    bool sourced_fastpath=true;
    bool plant_zombie_deaths(const DeathTarget&)override;
    int64_t zombie_index(const ZombieRef&)override;
    bool auto_explode(const ZombieRef&,std::optional<double> now={});
    void chili_row_hint(const ZombieRef& u,bool force)override{row_hint(CombatTarget::zombie(u),force);}
    bool chili_fire_row(const ZombieRef&,bool friendly)override;
    bool doom_explosion(const ZombieRef&)override;
    bool grave_remnant(const ZombieRef& u)override{if(const auto r=services_.gravebuster_bone(u))return *r;return graves.grave(u);}
    bool gravebuster_plant(const ZombieRef& u)override{if(const auto r=services_.gravebuster_charmed_plant(u))return *r;return graves.plant(u);}
    void armor_broken(const ZombieRef&,ArmorSlot,const std::string&,double)override;
    std::optional<int> row_hint(const CombatTarget&,bool force)override;
    void enemy_scan(const EntityRef&,FlameBox,double)override;
    void player_hit(const EntityRef&,FlameBox,double)override;
    void hit_zombies(const EntityRef&,FlameBox,double,bool,const std::optional<FireRows>&)override;
private:
    TypedBattleState& world_;
    DeathServices& services_;
    ZombieRef resolve(const DeathTarget&)const;
    void context_effects(const std::shared_ptr<AttackSource>&);
};
} // namespace pvz::typed72
