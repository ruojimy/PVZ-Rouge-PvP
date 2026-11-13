#pragma once
#include "sim/typed/content_darts.h"
#include "sim/typed/content_lantern.h"
#include "sim/typed/content_vines.h"
#include "sim/typed/barrel_projectiles.h"
#include "sim/typed/content_zombies56.h"
#include "sim/typed/content_zombies70.h"
#include "sim/typed/content_zombies64.h"
#include "sim/typed/september_plants.h"
#include "sim/typed/reed_plants.h"
#include "sim/typed/mortar_plants.h"
#include "sim/typed/flying_plants.h"
#include "sim/typed/sea_shroom.h"
#include "sim/typed/entity_phase.h"
#include <type_traits>
namespace pvz::typed72 {
class ContentPhasePresentation {
public:
    virtual ~ContentPhasePresentation()=default;
    virtual void draw_mortar_projectile(const EntityRef&,double angle,const std::optional<Point>& trail,std::string_view tail)=0;
    virtual void draw_ghost_effect(const GhostBlast&)=0;
    virtual void draw_reed_effect(const ReedBolt&)=0;
    virtual void draw_spring_effect(const SpringSwipe&)=0;
    virtual void draw_grenade_effect(const GrenadeBlast&)=0;
    virtual void draw_grenade_projectile(const GrenadeRef&,double angle,double alpha)=0;
    virtual void draw_hook_rope(Point)=0;
    virtual void draw_zombie_projectile(const ContentProjectileRef&,std::string_view sprite,double angle,double alpha)=0;
    virtual void draw_lettuce_flash(const LettuceFlash&)=0;
    virtual void restore_content_art()=0;
    virtual void alias_content_art(const std::string&,const std::string&)=0;
    virtual bool has_content_sprite(const std::string&)const=0;
};
struct NativeContentPhaseSystems {
    ContentTargets& targets;
    ContentPlants70& plants70;
    MortarPlants& mortar;
    ContentZombies64& zombies64;
    ContentZombies56& zombies56;
    ContentZombies70& zombies70;
    FlyingPlants& flying;
    NativeBarrels& barrels;
    BarrelProjectiles& barrel_projectiles;
    ContentDarts& darts;
    Grenadiers& grenadiers;
    SeaShroom& sea;
    ContentFrost& frost;
    ContentLantern& lantern;
    ContentVines& vines;
    SeptemberPlants& september;
    ReedPlants& reeds;
};
// This owns the actual NativeContent phase ordering. It uses the same world,
// rosters and concrete controllers as the native regions and PvP wrappers.
class NativeContentPhases : public EntityContentGate {
public:
    NativeContentPhases(TypedBattleState& world,NativeContentPhaseSystems systems,
        const std::vector<std::string>& custom_plants,const bool& drawing,ContentPhasePresentation& presentation)
        :world_(world),systems_(systems),custom_plants_(custom_plants),drawing_(drawing),presentation_(presentation){}
    void before_tick();
    void projectiles();
    void after_plants();
    void plant_gate(PlantRef);
    void entity_gate(const EntityRef&)override;
    // The PvP70 controller invokes this after updating its shots. Flash
    // expiration intentionally occurs only on drawing ticks, like the source.
    void draw_zombie70_effects();
    // Capture before invoking the installed inner constructor: callbacks may
    // replace the entity roster or append additional projectiles synchronously.
    template<class F> decltype(auto) add_entity(std::string kind,double facing,Motion position,F&& inner) {
        const size_t before=world_.runtime.entities.list()->size();const auto source=world_.heroes.source();
        if(source&&source->content.present()&&!source->content.is_null()&&source->content.get()=="甜椒投手"&&kind=="西瓜"){position.vx*=1.5;position.vy*=1.5;}
        if constexpr(std::is_void_v<std::invoke_result_t<F,std::string,double,Motion>>) {
            inner(std::move(kind),facing,position);after_birth(source,before);
        }else {auto result=inner(std::move(kind),facing,position);after_birth(source,before);return result;}
    }
    void after_birth(const std::shared_ptr<AttackSource>&,size_t first);
private:
    TypedBattleState& world_;NativeContentPhaseSystems systems_;const std::vector<std::string>& custom_plants_;
    const bool& drawing_;ContentPhasePresentation& presentation_;
    bool custom(const Field<std::string>&)const;
    void draw_projectiles();
    void draw_effects();
};
} // namespace pvz::typed72
