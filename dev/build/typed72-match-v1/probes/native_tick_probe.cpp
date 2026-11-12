#define PVZ72_CONTENT_ZOMBIES64_PROBE_EMBEDDED
#include "content_zombies64_probe.cpp"
#include "sim/typed/native_tick.h"

namespace {
// The full native regions are concrete here. Unmigrated outer controllers
// are observed fixture boundaries, so this probe cannot accept a product.
struct NativeTickProbe : ContentZombie64Probe,NativeTickPatches,NativeTickPresentation,
                         ZombiePhaseServices,GraveBindingServices {
    GraveIdleRules grave_rules{20.,20.,.5,6.,"稻草人"};
    GraveClock grave_clock{battle,economy_state,grave_rules};
    PlantDeathRules death_rules;
    PlantDeathState death_state;
    PlantDeathPolicy death_policy{battle,resources,economy_state,death_state,death_rules};
    PlantMaintenance maintenance{battle,world_region,*this,*this,static_cast<ZombieMotionServices&>(*this),death_policy};
    GraveBinding binding{battle,action_state,*this,*this};
    SeaShroom sea{battle,indexes,sight,target_dispatch};
    ZombiePhase zombie_phase{battle,mobile,navigation,action_state,static_cast<ZombieMotionServices&>(*this),
                            *this,*this,static_cast<EntityRegionBindings&>(*this),path_banks,taunts};
    NativeTickState tick_state;
    NativeTick driver{battle,tick_state,{budget,hero_phase,resources,paths,path_banks,commands,taunts,regions,
        zombie_phase,mobile,navigation,action_state,wind,grave_clock,indexes,owner_phase,flight,binding,
        maintenance,economy,plants,chart,sea,*this,*this}};
    J tick_events=J::array();
    FrameEntity frame_entity;
    bool observe_tick=false;
    explicit NativeTickProbe(int64_t seed,double width,double splash):ContentZombie64Probe(seed,width,splash){}

    void record(std::string name) {
        tick_events.push_back({name,world.tick,world.attack_tick(),battle.native_time});
        before("tick_"+name);
        after("tick_"+name);
    }
    void status_tick()override{record("status");}
    void content_before_tick()override{record("content_before");}
    void before_native_tick(double now)override{battle.native_time=now;record("patch_before");}
    void content_projectiles()override{record("content_projectiles");}
    void expansion_before_plants()override{record("expansion_before");}
    void finish_sun_source()override{record("sun_source");}
    void clear_source_gate()override{battle.runtime.presentation.source_art.clear();}
    void after_native_tick(double)override{record("patch_after");}
    void expansion_after_plants()override{record("expansion_after");}
    void content_after_plants()override{record("content_after");}
    void draw_patch(double)override{record("patch_draw");}
    void reconcile_barrels()override{record("barrels");}
    void begin_frame(int64_t)override{record("begin_frame");}
    void set_drawing(bool draw)override{record(draw?"drawing":"hidden");}
    void draw_plants()override{record("draw_plants");}
    void draw_particles(const std::vector<ParticleRect>&)override{}
    void entity_override(FrameEntity source)override{frame_entity=std::move(source);}
    void draw_hero(Seat seat,bool materialize)override {
        record("hero_"+std::string(seat_name(seat))+(materialize?"_pixels":"_hidden"));
    }
    void draw_barrel(const ZombieRef& unit)override{record("barrel_"+std::to_string(index(unit)));}
    void snapshot()override{record("snapshot");}
    void finish_content_zombie()override{record("content_zombie_finish");}
    void finish_expansion_zombie()override{record("expansion_zombie_finish");}
    void release_pending_destination()override{ContentZombie64Probe::release_pending_destination();}
    void zombie_gate(size_t index)override {
        ContentZombie64Probe::zombie_gate(index);
        before("tick_zombie_gate");after("tick_zombie_gate");
    }
    void summon_zombie(std::string name,Motion p,double facing)override {
        ContentZombie64Probe::summon_zombie(std::move(name),p,facing);
    }
    bool hold_dance()override{return budget.hold_dance();}
    bool defer_dancer(Point p,double facing,int64_t slot)override{return budget.defer_dancer(p,facing,slot);}
    bool hold_sled()override{return budget.hold_spawn();}
    bool hold_giant()override{return budget.hold_spawn();}
    void ash_zombie(size_t index)override{ContentZombie64Probe::ash_zombie(index);}
    void line(Point start,Point end)override{ContentZombie64Probe::line(start,end);}
    void crop(std::string name,Point p,bool mirror,Point size)override{ContentZombie64Probe::crop(std::move(name),p,mirror,size);}
    uint64_t flat_sprite(std::string name,Point size,bool mirror)override{return ContentZombie64Probe::flat_sprite(std::move(name),size,mirror);}
    bool has_sprite(const std::string& name)const override{return ContentZombie64Probe::has_sprite(name);}
    void grave_consumed(const ZombieRef& unit,const PlantRef&)override{record("grave_consumed_"+std::to_string(index(unit)));}
    void grave_event(GraveBindingEvent event)override{record("grave_event_"+std::to_string(size_t(event.kind)));}
    void destroy_block(Cell point)override{binding.destroy(point);}
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="native_tick_setup") {
            observe_tick=true;
            tick_state.present.clear();
            for(const auto& seat:op.at("present"))tick_state.present.push_back(parse_seat(seat.get<std::string>()));
            present=tick_state.present;
            tick_state.native_secrets=std::make_shared<std::vector<std::string>>(op.at("native_secrets").get<std::vector<std::string>>());
            world.published_tick=world.tick;
            tick_state.drawing=action_state.drawing;
            tick_state.multi_target=op.at("multi_target");tick_state.multi_plant=op.at("multi_plant");
            tick_state.scripted=op.at("scripted");tick_state.team_mode=op.at("team_mode");
            navigation.scripted=tick_state.scripted;budget.enabled=tick_state.scripted;
            tick_state.skip_dave_pixels=op.at("skip_pixels");tick_state.tail_activation_seconds=op.at("tail_at");
            tick_state.production={op.at("quiet"),op.at("ramp"),op.at("bonus"),op.at("multiplier"),false};
            commands.shared=op.at("command")=="follow"?PathMode::follow_hero:PathMode::attack_plants;
            for(const auto& [seat,mode]:op.at("commands").items())
                commands.by_seat[seat_index(parse_seat(seat))]=mode=="follow"?PathMode::follow_hero:PathMode::attack_plants;
            for(size_t i=0;i<world.heroes.size();++i)if(world.heroes[i])world.heroes[i]->actual_seat=Seat(i);
        }else if(name=="tick_unit") {
            const auto unit=units.at(op.at("unit").get<size_t>());
            read64(*unit,op.at("fields"));
            const auto& fields=op.at("fields");
            if(fields.contains("防具"))unit->body.armor=fields.at("防具");
            if(fields.contains("防具血量"))unit->body.armor_hp=fields.at("防具血量");
            if(fields.contains("手持"))unit->body.hand=fields.at("手持");
            if(fields.contains("手持血量"))unit->body.hand_hp=fields.at("手持血量");
            read_point(op.at("fields"),"_pvp_anchor",unit->anchor);
            read(op.at("fields"),"_pvp_producer",unit->producer);
            read(op.at("fields"),"_pvp_idle",unit->idle);
        }else if(name=="native_tick") {
            try{driver.run(op.value("draw",true));}
            catch(const std::exception&) {if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(name=="native_zombie_phase") {
            try {
                const auto stationary=zombie_phase.run(tick_state.present,tick_state.multi_plant);
                result=J::array();for(const auto& unit:stationary)result.push_back(index(unit));
            }catch(const std::exception&) {if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(name=="tick_grenade_wind") {
            wind.wind(units.at(op.at("unit").get<size_t>()),op.value("strength",1.));
        }else if(name=="tick_anchor_identity") {
            const auto unit=units.at(op.at("unit").get<size_t>());
            unit->body.motion.get().x=op.at("x");
        }else return ContentZombie64Probe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        ContentZombie64Probe::extra_snapshot(row);
        if(!observe_tick)return;
        J suspended=J::array();for(const auto& unit:battle.suspended_graves)suspended.push_back(index(unit));
        J source=nullptr;
        if(const auto* seat=std::get_if<Seat>(&frame_entity))source=seat_name(*seat);
        if(const auto* unit=std::get_if<ZombieRef>(&frame_entity))source=index(*unit);
        row["native_tick"]={{"tick",world.tick},{"published",world.attack_tick()},{"draw",tick_state.drawing},
            {"events",tick_events},{"suspended",suspended},{"override",source},{"binding_depth",binding.depth()}};
    }
};
J run_native_tick(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    NativeTickProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;}
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
#ifndef PVZ72_NATIVE_TICK_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: native_tick72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("native tick fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_native_tick(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
#endif
