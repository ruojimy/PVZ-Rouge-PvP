#define PVZ72_SHOOTING_PROBE_EMBEDDED
#include "shooting_probe.cpp"
#include "sim/typed/plant_lookup.h"
#include "sim/typed/entity_contacts.h"
#include "sim/typed/entity_region.h"
#include "sim/typed/entity_phase.h"
#include "sim/typed/zombie_motion.h"
#include "sim/typed/zombie_actions.h"
#include "sim/typed/zombie_spawn.h"
#include "sim/typed/hero_physics.h"
#include "sim/typed/hero_phase.h"
namespace {
struct WorldRulesProbe:ShootingProbe,EntityRegionBindings,EntityPhaseServices,ZombieMotionServices,ZombieActionServices {
    EntityRegionRules rules;
    EntityContacts contacts;
    EntityRegionEnvironment region_env;
    ProjectileRules flight;
    EntityRegion region;
    TargetIndexes indexes;
    TargetSight sight;
    NativeTracking chart;
    EntityPhase owner_phase;
    std::vector<std::string> assets;
    bool observe_index=false;
    std::optional<size_t> nearest;
    J render_log=J::array();
#include "zombie_motion_fixture.inc"
    HeroPhysics physics{battle,indexes,*this,*this,static_cast<EntityRegionBindings&>(*this)};
    RallyPoints hero_flags;
    HeroPhase hero_phase{battle,physics,chart,sight,hero_flags};
    bool observe_hero_inputs=false;
    explicit WorldRulesProbe(int64_t seed,double width,double splash):ShootingProbe(seed,true),
        contacts(battle,*this,collision,rules),flight(battle,chain.damage,collision,width,splash),
        region(battle,region_env,rules,contacts,flight,squash,*this,*this,*this),
        chart(battle,indexes,sight),owner_phase(battle,region_env,rules,contacts,flight,squash,*this,*this,torches,indexes,sight,*this){
        battle.native_plant_zombies_installed=true;
    }
    bool has_sprite(const std::string& s)const override{return std::find(assets.begin(),assets.end(),s)!=assets.end();}
    bool clear(Cell c)override{
        if(!observe_motion)return ShootingProbe::clear(c);
        calls.push_back(J::array({"clear",c.y,c.x}));before("clear");const auto cleared=clear_pvp_plant(battle,c);after("clear");return cleared;
    }
    void ash_target(size_t i,TargetDamage&,CombatTarget)override{ash_zombie(i);}
    void release_pending_destination()override{render_log.push_back(J::array({"release_destination"}));}
    TrackingSource track_source(const J& op) {
        if(op.contains("plant"))return TrackingSource::from(plant_ref(op.at("plant").get<size_t>()));
        if(op.contains("entity"))return TrackingSource::from(births.at(op.at("entity").get<size_t>()));
        return {};
    }
    void tracking_gate(size_t i)override {render_log.push_back(J::array({"source",i}));}
    std::optional<size_t> nearest_target()const override{return nearest;}
    static J sprite_id(const EntitySprite& sprite) {
        return std::visit([](const auto& v){return J(v);},sprite);
    }
    void draw(EntityDraw d)override {
        J size=nullptr;if(d.dimensions)size=J::array({d.dimensions->x,d.dimensions->y});
        render_log.push_back(J::array({"draw",sprite_id(d.sprite),{d.position.x,d.position.y},d.mirrored,d.rotation?J(*d.rotation):J(nullptr),size}));
    }
    void alpha(const EntitySprite& s,double a)override{render_log.push_back(J::array({"alpha",sprite_id(s),a}));}
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="hero_phase_setup"){
            observe_hero_inputs=true;
            sight.water=op.at("water").get<std::vector<std::vector<uint8_t>>>();
            for(const auto& [key,item]:op.at("seats").items()){
                auto side=parse_seat(key);auto& player=world.players.at(seat_index(side)).value();const auto& p=item.at("point");
                hero_phase.initialize(side,{p.at(0),p.at(1)},item.at("hp"),item.at("deck").get<std::vector<std::string>>(),item.at("native_secrets").get<std::vector<std::string>>());
                player.move=item.at("move");player.jump_held=item.at("held");player.jump_presses=item.at("presses");
            }
        }else if(action=="hero_phase_status"){
            auto& a=world.hero(parse_seat(op.at("side").get<std::string>()));
            read_hero(op.at("fields"),a);
            if(op.contains("launch"))a.launch_attack=attack_identity(op.at("launch"));
        }else if(action=="hero_flag"){
            auto flag=op.at("on").get<bool>()?std::optional<Point>(Point{480.,240.}):std::nullopt;
            const auto side=parse_seat(op.at("side").get<std::string>());
            if(battle.mode==MatchMode::duo)hero_flags.by_seat[seat_index(side)]=flag;
            if(side==Seat::zombie || battle.mode!=MatchMode::duo)hero_flags.shared=flag;
        }else if(action=="hero_phase_step")hero_phase.advance(seats_for(battle.mode));
        else if(action=="hero_phase_effects")hero_phase.effects(seats_for(battle.mode),op.at("now"),op.at("tail_at"));
        else if(action=="hero_make"){
            auto& avatar=world.hero(parse_seat(op.at("side").get<std::string>()));
            avatar=HeroState{};
            const auto& p=op.at("point");
            avatar.frame=physics.make_state({p.at(0),p.at(1)},op.at("mode"),op.at("hp"),op.at("secrets").get<std::vector<std::string>>());
        }else if(action=="hero_step"){
            auto& avatar=world.hero(parse_seat(op.at("side").get<std::string>()));
            HeroInput input{op.at("move"),op.at("held"),op.at("press")};
            physics.step(avatar,input,op.at("cap"),op.at("balloon_hp"));
        }else if(action=="hero_effects"){
            const int target=op.value("nearest",-1);
            indexes.nearest=target<0?std::nullopt:std::optional<size_t>(target);
            physics.effects(world.hero(parse_seat(op.at("side").get<std::string>())),op.at("tail").get<bool>());
        }else if(action=="zombie_run")zombies.run();
        else if(action=="action_setup") {
            observe_actions=true;action_state.drawing=op.value("draw",false);
            action_state.coin_count=op.value("coin_count",0);
            action_state.large_zombies=op.value("large",std::vector<std::string>{});
        }else if(action=="motion_setup")motion_setup(op);
        else if(action=="motion_unit")motion_unit(*units.at(op.at("unit").get<size_t>()),op.at("values"));
        else if(action=="motion_body") {
            const auto f=mobile.advance(op.at("index").get<size_t>());
            result={f.cell.x,f.cell.y,f.flood_index,f.heading,f.immobile,f.can_bite,f.collision};
        }else if(action=="motion_static")mobile.register_stationary(op.at("index").get<size_t>());
        else if(action=="track_setup") {
            observe_index=true;battle.terrain.periodic_x=true;
            *indexes.rows=op.at("rows").get<TargetBuckets>();*indexes.columns=op.at("cols").get<TargetBuckets>();
            indexes.nearest.reset();indexes.nearest_distance=op.value("distance",-1.);
            const auto mode=op.value("mode",std::string("duel"));
            battle.mode=mode=="duo"?MatchMode::duo:mode=="coop"?MatchMode::coop:mode=="pve"?MatchMode::pve:MatchMode::duel;
            sight.solid=op.at("solid").get<std::vector<std::vector<uint8_t>>>();
            assets=op.value("assets",std::vector<std::string>{});
            for(const auto& item:op.at("players").items()) {
                auto& p=world.players.at(seat_index(parse_seat(item.key()))).value();
                const auto& v=item.value();p.position={v.at(0),v.at(1)};p.height=v.at(2);p.marked_until=v.at(3);
            }
            region_env.water_particle="水";
        } else if(action=="track_unit") {
            auto u=units.at(op.at("unit").get<size_t>());
            read(op,"entry",u->native.entry);read(op,"split",u->native.split);read(op,"owner",u->source.owner);
            if(op.contains("hand"))u->body.hand=op.at("hand").get<std::string>();
        } else if(action=="track_begin")chart.begin(track_source(op));
        else if(action=="track_restore")chart.restore();
        else if(action=="track_index")chart.target_index(track_source(op));
        else if(action=="track_lock")result=chart.hero_lock(track_source(op),parse_seat(op.at("side").get<std::string>()));
        else if(action=="phase_run")owner_phase.run();
        else if(action=="pz_fume"){
            const auto index=op.at("index").get<size_t>();result=fume.damage_zombie(index,battle.targets->at(index),op.at("amount"),op.at("direction"));
        }
        else if(action=="region_run") {
            battle.terrain.periodic_x=true;nearest.reset();if(op.contains("nearest")&&!op["nearest"].is_null())nearest=op["nearest"].get<size_t>();
            region_env.driving=op.value("driving",0.);region_env.camera_y=op.value("camera_y",0.);
            region_env.water_particle=op.value("water",std::string("水"));region.run();
        } else if(action=="region_fields") {
            auto& e=*births.at(op.at("entity").get<size_t>());auto remaining=op.at("values");
            read_death(remaining,"黑白",e.monochrome);read(remaining,"入水",e.in_water);read(remaining,"锁敌",e.cannon_lock);
            read(remaining,"落点",e.cannon_column);read(remaining,"扁",e.flat_sprite);read(remaining,"火了",e.source.fire_lit);
            read(remaining,"旋转",e.rotation);read(remaining,"穿墙",e.through_wall);
            read(remaining,"_pvp_art_name",e.art_name);read(remaining,"_pvp_cattail",e.source.cattail);
            for(auto k:{"黑白","入水","锁敌","落点","扁","火了","旋转","穿墙","_pvp_art_name","_pvp_cattail"})remaining.erase(k);
            pea_fields(e,remaining);
        } else if(action=="rules_torch_tick")torches.tick();
        else if(action=="rules_charmed_tick")torches.ignite_charmed_peas();
        else if(action=="rules_zombie_torch")torches.zombie_pea(births.at(op.at("entity").get<size_t>()));
        else if(action=="rules_plant") {
            auto& p=*plant_ref(op.at("plant").get<size_t>());
            read(op,"copy_card",p.copy_card);read(op,"content",p.source.content);read(op,"id",p.source.id);
            if(op.contains("kind"))p.kind=op["kind"].get<std::string>();
        } else if(action=="rules_grave") {
            auto& u=*units.at(op.at("unit").get<size_t>());
            if(op.contains("grave"))u.protection.grave=op["grave"];
            read(op,"card",u.protection.card);read(op,"paid",u.patch.torch_brain);
            read(op,"until",u.patch.torch_sleep_until);read(op,"id",u.source.id);
            if(op.contains("position"))u.body.motion.replace(motion(op["position"]));
        } else if(action=="rules_position") {
            auto e=births.at(op.at("entity").get<size_t>());
            e->motion.replace(motion(op.at("position")));
        } else if(action=="rules_lookup") {
            const auto index=lookup_pvp_plant(battle,cell(op.at("cell")),op.value("skip",false));
            result=index?J(*index):J(-1);
        } else if(action=="rules_point") {
            const auto p=patch_plant_point(battle,*plant_ref(op.at("plant").get<size_t>()));
            result=p?J::array({p->x,p->y}):J(nullptr);
        } else if(action=="rules_strike") {
            const size_t l=op.at("index");
            const std::string name=battle.runtime.entities.list()->at(l)->kind;
            result=contacts.strike(l,name,op.value("driving",0.));
        } else if(action=="rules_home") {
            std::optional<size_t> target_index;
            if(!op.at("nearest").is_null())target_index=op.at("nearest").get<size_t>();
            contacts.home(op.at("index"),target_index);
        } else if(action=="rules_freeze")contacts.freeze_melon(op.at("index"));
        else return ShootingProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        ShootingProbe::extra_snapshot(row);
        snapshot_motion(row);
        if(observe_hero_inputs){
            row["hero_controls"]=J::object();
            for(auto s:seats_for(battle.mode)){const auto& player=world.players.at(seat_index(s)).value();row["hero_controls"][seat_name(s)]={player.jump_presses,player.max_hp};}
        }
        row["region_trace"]=render_log;
        if(observe_index)row["tracking"]={*indexes.rows,*indexes.columns,indexes.ladders,indexes.nearest?J(*indexes.nearest):J(-1),indexes.nearest_distance,chart.active()};
        const auto fields=[](const EntityRef& e,J& j){
            death_state(j,"黑白",e->monochrome);write(j,"入水",e->in_water);write(j,"锁敌",e->cannon_lock);
            write(j,"落点",e->cannon_column);write(j,"扁",e->flat_sprite);write(j,"_pvp_art_name",e->art_name);
        };
        for(size_t i=0;i<births.size();++i)fields(births[i],row["effect_births"][i]);
        const auto entities=battle.runtime.entities.list();
        for(size_t i=0;i<entities->size();++i)fields(entities->at(i),row["entities"][i]);
        row["grave_clocks"]=J::array();
        for(const auto& u:units) {
            J record=J::object();
            write(record,"_pvp_torch_brain",u->patch.torch_brain);
            write(record,"_pvp_torch_sleep_until",u->patch.torch_sleep_until);
            write(record,"_pvp_id",u->source.id);
            row["grave_clocks"].push_back(std::move(record));
        }
    }
};
J run_world_rules(const J& j) {
    J base=j;const auto cfg=base.at("world_rules");base.erase("world_rules");
    WorldRulesProbe p(j.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));configure_shooting(p,base);
    p.battle.world_width.set(cfg.at("width"));p.battle.dense_planting=cfg.at("dense");
    p.battle.protection.deathmatch=cfg.at("deathmatch");if(cfg.at("rage").get<bool>()){
        // The reference adds zsecrets 暴怒 (verify_world_rules.py:139), which drives the torch rules,
        // not 狂暴/DamageSecret::rage.
        p.torches.fury=true;
    }
    p.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();
    p.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    p.rules.homing_height=cfg.at("heights").get<decltype(p.rules.homing_height)>();
    p.collision.unit_scale=cfg.at("scale").get<decltype(p.collision.unit_scale)>();
    p.operations(j.at("operations"));return p.states;
}
}
#ifndef PVZ72_WORLD_RULES_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: world_rules72_probe inputs output");
        std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);
        if(!in||!out)throw std::runtime_error("world rules fixture streams");
        std::string line;while(std::getline(in,line))if(!line.empty())out<<run_world_rules(J::parse(line)).dump()<<'\n';
        return out?0:2;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
#endif
