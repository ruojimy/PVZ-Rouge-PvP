#pragma once
#include "sim/typed/zombie_phase.h"
#include "sim/typed/scripted_spawn_budget.h"
#include "sim/typed/grave_clock.h"
#include "sim/typed/grave_binding.h"
#include "sim/typed/plant_maintenance.h"
#include "sim/typed/plant_region.h"
#include "sim/typed/entity_phase.h"
#include "sim/typed/owner_umbrella.h"
#include "sim/typed/sea_shroom.h"
#include "sim/typed/wind_effects.h"

namespace pvz::typed72 {
class NativeTickObserver {
public:
    virtual ~NativeTickObserver()=default;
    virtual void native_tick_done()=0;
};
struct NativeTickState {
    std::vector<Seat> present;
    std::shared_ptr<std::vector<std::string>> native_secrets=std::make_shared<std::vector<std::string>>();
    uint64_t published_revision=0;
    bool multi_target=false,multi_plant=false,scripted=false,team_mode=false;
    bool drawing=true,skip_dave_pixels=false;
    // dave_state also yields the original 玩家皮肤-受伤 set_alpha value (hp < 20 only),
    // consumed by the presentation's draw_hero in the same tick.
    std::array<std::optional<int>,4> dave_hurt_alpha{};
    double tail_activation_seconds=0.;
    ProductionRules production;
    // Corresponds to the source _pvp_record_native hook: read-only observation
    // after a complete native tick. Null in normal play.
    class NativeTickObserver* observer=nullptr;
};

using FrameEntity=std::variant<std::monostate,Seat,ZombieRef>;
class NativeTickPresentation {
public:
    virtual ~NativeTickPresentation()=default;
    virtual void begin_frame(int64_t tick)=0;
    virtual void set_drawing(bool)=0;
    virtual void draw_plants()=0;
    virtual void draw_particles(const std::vector<ParticleRect>&)=0;
    virtual void entity_override(FrameEntity)=0;
    virtual void draw_hero(Seat,bool materialize)=0;
    virtual void draw_barrel(const ZombieRef&)=0;
    virtual void snapshot()=0;
};

// These are required installed C++ patch controllers. The production
// composition must provide every method, including the cold presentation
// bridge. No method here has a default implementation or a legacy callback.
class NativeTickPatches {
public:
    virtual ~NativeTickPatches()=default;
    virtual void status_tick()=0;
    virtual void content_before_tick()=0;
    virtual void before_native_tick(double now)=0;
    virtual void content_projectiles()=0;
    virtual void expansion_before_plants()=0;
    virtual void finish_sun_source()=0;
    virtual void clear_source_gate()=0;
    virtual void after_native_tick(double now)=0;
    virtual void expansion_after_plants()=0;
    virtual void content_after_plants()=0;
    virtual void draw_patch(double now)=0;
    virtual void reconcile_barrels()=0;
};

// References all belong to the same authoritative world and outlive the
// driver. The room owns that composition for the lifetime of queued summons.
struct NativeTickSystems {
    ScriptedSpawnBudget& spawn_budget;
    HeroPhase& heroes;
    Resources& resources;
    PathTracking& paths;
    SeatPathTracking& seat_paths;
    const SeatCommands& commands;
    SweetTaunts& taunts;
    WorldRegions& regions;
    ZombiePhase& zombies;
    ZombieMotion& zombie_motion;
    ZombieNavigation& navigation;
    ZombieActionState& zombie_actions;
    WindEffects& wind;
    GraveClock& grave_clock;
    TargetIndexes& indexes;
    EntityPhase& entities;
    ProjectileRules& projectiles;
    GraveBinding& grave_binding;
    PlantMaintenance& maintenance;
    Economy& economy;
    PlantRegion& plants;
    NativeTracking& periodic_targets;
    SeaShroom& sea;
    NativeTickPatches& patches;
    NativeTickPresentation& presentation;
};

// One 250 Hz authoritative update, corresponding to _step_original. The
// 30 Hz room scheduler invokes this entry repeatedly and draws its last tick.
class NativeTick {
public:
    NativeTick(TypedBattleState& world,NativeTickState& state,NativeTickSystems systems)
        :world_(world),state_(state),systems_(systems){}
    void run(bool draw=true);
private:
    TypedBattleState& world_;
    NativeTickState& state_;
    NativeTickSystems systems_;
    void tracking();
    void append_heroes();
    void plant_actions();
    void finish_frame(bool draw);
};
} // namespace pvz::typed72
