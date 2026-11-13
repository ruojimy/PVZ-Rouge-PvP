#include "core/function_profile.h"
#include "sim/typed/native_tick.h"
#include "core/pymath.h"
#include <cmath>

namespace pvz::typed72 {
namespace {
// Original dave_state region 67018..67400, run for each avatar through
// _draw_dave on every native tick, drawn or not. Its alpha is presentation;
// the hurt clock it advances is authoritative state. HP is compared on the
// source's 20-point scale.
std::optional<int> dave_state(HeroState& hero) {
    auto& f=hero.frame;const double maximum=hero.max_hp.or_missing(20.);
    const double hp=maximum!=20.?f.hp.get()*20./maximum:f.hp.get();
    double hurt=f.hurt.or_missing(0.);
    std::optional<int> alpha;
    if(hp<=0.)hurt=1.;
    if(hp<20.){
        const double lzx=hp*13.;double llzx=0.,lllzx=1.;
        if(f.recovery.or_missing(0.)>2000.)lllzx=std::pow(f.down.or_missing(0.)/90.,.5);
        if(hurt>0.){hurt+=1.;llzx=double(int64_t(std::pow(1.-(hurt/50.),.5)*lzx));}
        alpha=int(int64_t(((llzx+255.)-lzx)*lllzx));
        if(hurt==50.)hurt=0.;
    }
    f.hurt.set(hurt);
    return alpha;
}
}
void NativeTick::tracking() {
    systems_.paths.begin_tracking_phase();systems_.seat_paths.begin_tracking_phase();
    struct EndTracking {PathTracking& paths;SeatPathTracking& seats;~EndTracking(){paths.end_tracking_phase();seats.end_tracking_phase();}} end_tracking{systems_.paths,systems_.seat_paths};
    auto& heroes=world_.heroes;
    if(state_.multi_target || world_.mode==MatchMode::pve) {
        systems_.seat_paths.advance_team(state_.present);
    }else {
        const auto source=systems_.commands.shared==PathMode::follow_hero?Seat::zombie:Seat::plant;
        const auto& position=*heroes.hero(source).frame.position.get();
        systems_.paths.advance({position.x,position.y},systems_.commands.shared);
    }
    systems_.seat_paths.advance_rallies(state_.present,state_.published_revision);
    systems_.taunts.update();
    heroes.globals.overlay(heroes.hero(Seat::plant).frame,true);
    heroes.globals.mode.set("正常模式");
    heroes.globals.secrets.set(state_.native_secrets);
}

void NativeTick::append_heroes() {
    auto& heroes=world_.heroes;
    if(!state_.scripted && !state_.team_mode) {
        heroes.proxy(Seat::zombie);
        world_.targets->push_back(CombatTarget::player(Seat::zombie));
        return;
    }
    for(const auto seat:state_.present) {
        if(team_of(seat)!=Seat::zombie)continue;
        heroes.proxy(seat);
        world_.targets->push_back(CombatTarget::player(seat));
    }
}

void NativeTick::plant_actions() {
    HeroContext context(world_.heroes,{Seat::zombie,Seat::plant,CombatPhase::plants,{},{}});
    GraveBinding::Plants binding(systems_.grave_binding);
    const auto finish=[&] {
        systems_.patches.finish_sun_source();
        systems_.patches.clear_source_gate();
        systems_.periodic_targets.restore();
    };
    try {systems_.plants.run();}
    catch(...) {finish();throw;}
    finish();
}

void NativeTick::finish_frame(bool draw) {
    // The source assigns a new list. Retained earlier rosters continue to
    // contain their proxy records and preserve their independent identity.
    auto visible=std::make_shared<TargetRoster>();
    visible->reserve(world_.targets->size());
    for(const auto& target:*world_.targets)
        if(target.unit && !target.unit->protection.hero)visible->push_back(target);
    world_.targets=std::move(visible);
    for(const auto& target:*world_.targets) {
        const auto& unit=target.unit;
        if(unit->protection.grave && unit->anchor.present() && !unit->anchor.is_null()) {
            const auto point=unit->anchor.get();
            unit->body.motion.get()={point.x,point.y,0.,0.};
        }
    }
    auto& presentation=systems_.presentation;
    for(const auto seat:state_.present) {
        state_.dave_hurt_alpha.at(seat_index(seat))=dave_state(world_.heroes.hero(seat));
        presentation.entity_override(seat);
        presentation.draw_hero(seat,draw || !state_.skip_dave_pixels);
    }
    presentation.entity_override(std::monostate{});
    systems_.patches.reconcile_barrels();
    const auto barrels=world_.targets;
    for(size_t i=0;i<barrels->size();++i) {
        const auto unit=barrels->at(i).unit;
        if(!unit || !unit->orphan_barrel)continue;
        presentation.entity_override(unit);
        presentation.draw_barrel(unit);
    }
    presentation.entity_override(std::monostate{});
    const double width=world_.world_width.get();
    for(const auto& target:*world_.targets) {
        auto& position=target.unit->body.motion.get();
        position.x=py::mod(position.x,width);
    }
    for(const auto& entity:*world_.runtime.entities.list()) {
        auto& position=entity->motion.get();
        position.x=py::mod(position.x,width);
    }
    if(draw)presentation.snapshot();
}

void NativeTick::run(bool draw) {
    PVP_PROFILE_SCOPE("NativeTick::run");
    function_profile::Phases profile;
    LiveBattleSources sources(world_);
    auto& heroes=world_.heroes;
    // Stamp at emission, never at a later drain. Native callbacks use this
    // tick; room-level economy callbacks between ticks keep the last completed
    // tick even if their sounds are drained by the following native frame.
    world_.runtime.sound_tick=heroes.tick+1;
    struct SoundClock {CombatRuntime& runtime;HeroCombat& heroes;~SoundClock(){runtime.sound_tick=heroes.tick;}} sound_clock{world_.runtime,heroes};
    auto& systems=systems_;
    if(!heroes.published_tick)heroes.published_tick=heroes.tick;
    ++heroes.tick;
    systems.spawn_budget.drain();
    if(state_.scripted && systems.navigation.ladder_cooldown>0)--systems.navigation.ladder_cooldown;
    const double now=double(heroes.tick)/250.;
    heroes.published_tick=heroes.tick;
    systems.patches.status_tick();
    systems.patches.content_before_tick();
    systems.presentation.begin_frame(heroes.tick);
    systems.presentation.set_drawing(draw);
    state_.drawing=draw;
    systems.zombie_actions.drawing=draw;
    systems.indexes.rows=std::make_shared<TargetBuckets>();
    systems.indexes.columns=std::make_shared<TargetBuckets>();
    systems.heroes.advance(state_.present);
    systems.resources.advance_suns();
    tracking();
    systems.regions.water_animation();
    systems.regions.important_blocks();
    systems.patches.before_native_tick(now);
    profile.mark("NativeTick::setup");
    const auto graves=systems.zombies.run(state_.present,state_.multi_plant);
    profile.mark("ZombiePhase::run");
    systems.wind.after_zombies();
    for(const auto& plant:*world_.plant_roster)
        if(plant->hp.or_missing(1.)<=0. && !plant->dead.present())plant->dead.set(DeathMarker(0.));
    const bool boosted=world_.protection.deathmatch || !heroes.last_stand_order.empty();
    systems.grave_clock.advance(graves,state_.present,boosted?state_.production.multiplier:1.);
    append_heroes();
    for(size_t index=0;index<world_.targets->size();++index)systems.zombie_motion.register_stationary(index);
    systems.heroes.effects(state_.present,now,state_.tail_activation_seconds);
    if(draw)systems.presentation.draw_plants();
    profile.mark("NativeTick::effects_and_draw_plants");
    systems.entities.run();
    profile.mark("EntityPhase::run");
    systems.patches.content_projectiles();
    profile.mark("NativeTickPatches::content_projectiles");
    systems.projectiles.cull_flight();
    Point shake;
    if(world_.runtime.screen_shake.present()) {
        const auto& values=world_.runtime.screen_shake.get();
        shake={values[1],values[2]};
    }
    advance_particles(world_.runtime,world_.terrain,draw,shake,&heroes.source_index);
    // region_particles draws each live particle as a screen rect in this same order.
    if(draw)systems.presentation.draw_particles(world_.runtime.particle_rects);
    world_.runtime.particle_rects.clear();
    profile.mark("NativeTick::particles");
    systems.grave_binding.before_native_tick();
    {
        HeroContext context(heroes,{Seat::zombie,Seat::plant,CombatPhase::plants,{},{}});
        systems.maintenance.run();
    }
    systems.patches.expansion_before_plants();
    auto production=state_.production;
    production.deathmatch=world_.protection.deathmatch;
    systems.economy.plant_production(production);
    owner_umbrella_effects(world_,false,state_.present);
    systems.wind.before_plants();
    profile.mark("NativeTick::maintenance_and_economy");
    plant_actions();
    profile.mark("NativeTick::plant_actions");
    systems.sea.restore();
    owner_umbrella_effects(world_,true,state_.present);
    systems.wind.after_plants();
    systems.patches.clear_source_gate();
    systems.patches.after_native_tick(now);
    systems.patches.expansion_after_plants();
    systems.patches.content_after_plants();
    systems.regions.ice_clock();
    if(draw)systems.patches.draw_patch(now);
    profile.mark("NativeTick::after_plants");
    finish_frame(draw);
    profile.mark("NativeTick::finish_frame");
    if(state_.observer)state_.observer->native_tick_done();
}
} // namespace pvz::typed72
