#define PVZ72_CONTENT_ZOMBIES_PROBE_EMBEDDED
#include "content_zombies_probe.cpp"
#include "sim/typed/content_zombie_bindings.h"
#include "sim/typed/content_zombie56_state.h"
#include "sim/typed/content_zombie70_state.h"
namespace {
struct ContentControllersProbe : ContentZombiesProbe,SeptemberZombieServices,ContentZombie56Services,
                                 ContentZombie70Services,NativeBarrelServices,ContentZombiePresentation {
    bool wild_dance=false;
    SeptemberZombies september{battle,navigation,path_rules,path_banks,target_dispatch,commands,hero_flags,
        tick_state.present,content_revision,tick_state.scripted,*this};
    ContentZombies56 zombies56{battle,budget,sight,wild_dance,*this};
    ContentZombies70 zombies70{battle,queries,target_dispatch,taunts,budget,binding,sight,collision,*this};
    NativeBarrels barrels{battle,sight,target_dispatch,summons,*this};
    ContentZombieCombatRules combat_rules;
    ContentZombieBindings concrete{battle,carts,september,zombies56,zombies70,barrels,sight,collision,combat_rules,navigation.charm_secret,*this};
    J controller_events=J::array(),factory_events=J::array();
    bool controllers_seen=false;
    size_t orphan_sequence=0;
    explicit ContentControllersProbe(int64_t seed,double width,double splash):ContentZombiesProbe(seed,width,splash){}
    void alias_art(const std::string& first,const std::string& second)override{ContentZombiesProbe::alias_art(first,second);}
    void tint_poison(const ZombieRef& unit)override{ContentZombiesProbe::tint_poison(unit);}
    double image_height(const std::string& name)const override{return ContentZombiesProbe::image_height(name);}
    void stun_star(Point point,Point size)override{ContentZombiesProbe::stun_star(point,size);}
    void draw_content_zombie(const ZombieRef& unit)override{ContentZombiesProbe::draw_content_zombie(unit);}
    double bite_damage(const ZombieRef& unit,const ContentTarget& target)override {
        ;return concrete.bite_damage(unit,target);
    }
    double movement_factor(const ZombieRef& unit)const override{return concrete.movement_factor(unit);}
    double unit_scale(const ZombieRef& unit)const override{return concrete.unit_scale(unit);}
    void hide_headhunt_plants(const ZombieRef& unit)override{;}
    void september_gate(const ZombieRef& unit)override{;september.gate(unit);}
    void september_wave_chase(const ZombieRef& unit)override{;september.wave_chase(unit);}
    void september_finish(const ZombieRef& unit)override{;september.finish(unit);}
    void zombies56_gate(const ZombieRef& unit)override{;zombies56.gate(unit);}
    void zombies56_finish(const ZombieRef& unit)override{;zombies56.finish(unit);}
    void zombies70_gate(const ZombieRef& unit)override{;zombies70.gate(unit);}
    void barrel_correct_pair(const ZombieRef& unit)override{;barrels.correct_pair(unit);}
    void barrel_detach(const ZombieRef& unit,double hp)override{;barrels.detach(unit,hp);}
    void barrel_break(const ZombieRef& unit)override{;barrels.break_barrel(unit);}
    void barrel_move(const ZombieRef& unit,double factor)override{;barrels.move(unit,factor);}
    void barrel_contact(const ZombieRef& unit,double factor)override{;barrels.contact(unit,factor);}
    ZombieRef spawn_zombie56(const std::string& card,Point point,double facing,const ScriptedSpawnOrigin& parent)override {
        return spawn_content(card.substr(7),point,facing,parent);
    }
    void zombie56_event(const Zombie56Event& value)override {}
    void zombie70_event(const Zombie70Event& value)override {}
    ZombieRef spawn_airdrop(Point point,double facing,const ScriptedSpawnOrigin& source)override{return spawn_content("路障僵尸",point,facing,source);}
    ZombieRef spawn_bone_grave(Cell cell,const BoneSource& source)override {
        ;
        ;;return {};
    }
    PlantRef spawn_bone_gravebuster(Cell cell,double facing,const Field<std::string>& parent)override {
        ;
        ;;return {};
    }
    void draw_zombie70_effects()override {}
    void register_barrel(const ZombieRef& unit,const Field<std::string>& parent)override {
        ids.push_back(battle.units.order().back());units.push_back(unit);
        const auto id="barrel:"+std::to_string(++orphan_sequence);unit->source.id.set(id);unit->source.owner.set("zombie");
        unit->protection.card.set("zombie:滚桶僵尸");battle.native_objects.set(id,unit);
        ;;;
    }
    void barrel_event(const BarrelEvent& value)override {}
    void crush_barrel_plant(const ZombieRef& unit,const PlantRef& plant)override {
        ;;;
    }
    void draw_barrel_sprite(Point point,double angle)override {}
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="plant_fields") {
            const bool handled=ContentZombiesProbe::extra_operation(op,result);
            read(op.at("fields"),"_pvp_id",plant_ref(op.at("plant").get<size_t>())->source.id);
            return handled;
        }
        if(name=="controllers_setup") {
            controllers_seen=true;wild_dance=op.value("wild",false);
            combat_rules.black_variants=op.value("black",std::vector<std::string>{});
            combat_rules.black_hero_bite_variants=op.value("black_bites",std::vector<std::string>{});
        }
        else if(name=="controller_fields") {
            const auto unit=units.at(op.at("unit").get<size_t>());const auto& f=op.at("fields");fields(unit,f);
            auto& a=unit->content56;auto& b=unit->content70;
            read(f,"_pvp_dance_owner",a.dance_owner);read(f,"_pvp_zs_dance_parent",a.wild_parent);read(f,"_pvp_squad_owner",a.squad_owner);
            read(f,"_pvp_dance_slot",a.dance_slot);read(f,"_pvp_dance_saved_speed",a.saved_speed);read(f,"_pvp_dance_clock",a.dance_clock);
            read(f,"_pvp_dance_rate",a.dance_rate);read(f,"_pvp_dancing",a.dancing);read(f,"_pvp_dance_impulse",a.impulse);
            if(f.contains("_pvp_dance_side")){if(f.at("_pvp_dance_side").is_null())a.dance_side.set_null();else a.dance_side.set(parse_seat(f.at("_pvp_dance_side").get<std::string>()));}
            read(f,"_pvp70_clock",b.clock);read(f,"_pvp_reaper_idle",b.reaper_idle);read(f,"_pvp_airdrop_used",b.airdrop_used);
            read(f,"_pvp_bone_grave",b.bone_grave);read_point(f,"_pvp_hook_pull",b.hook_pull);read(f,"_pvp_zs_headhunt",unit->content.headhunt);
            read(f,"_pvp_reaper_hurt",unit->protection.reaper_hurt);
            if(f.contains("_pvp_barrel_position"))unit->barrel_position.set(std::make_shared<Motion>(motion(f.at("_pvp_barrel_position"))));
        }else if(name=="controller56_configure")result=zombies56.configure(units.at(op.at("unit").get<size_t>()),op.at("name").get<std::string>(),op.at("hp"),true);
        else if(name=="controller70_configure")result=zombies70.configure(units.at(op.at("unit").get<size_t>()),op.at("name").get<std::string>());
        else if(name=="controller56_before")zombies56.before_tick();
        else if(name=="controller70_projectiles")zombies70.projectiles();
        else if(name=="controller_plant_registry")battle.native_objects.set(op.at("id").get<std::string>(),plant_ref(op.at("plant").get<size_t>()));
        else if(name=="barrel_track")barrels.track(units.at(op.at("unit").get<size_t>()));
        else if(name=="barrel_tick")barrels.tick();
        else if(name=="barrel_reconcile")barrels.reconcile();
        else return ContentZombiesProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        ContentZombiesProbe::extra_snapshot(row);if(!controllers_seen)return;J records=J::array(),shots=J::array(),carriers=J::array();
        for(const auto& unit:units) {
            J item=J::object();const auto& a=unit->content56;const auto& b=unit->content70;
            write(item,"_pvp_dance_owner",a.dance_owner);write(item,"_pvp_zs_dance_parent",a.wild_parent);write(item,"_pvp_squad_owner",a.squad_owner);
            write(item,"_pvp_dance_slot",a.dance_slot);write(item,"_pvp_dance_saved_speed",a.saved_speed);write(item,"_pvp_dance_clock",a.dance_clock);
            write(item,"_pvp_dance_rate",a.dance_rate);write(item,"_pvp_dancing",a.dancing);write(item,"_pvp_dance_impulse",a.impulse);
            if(a.dance_side.present())item["_pvp_dance_side"]=a.dance_side.is_null()?J(nullptr):J(seat_name(a.dance_side.get()));
            write(item,"_pvp70_clock",b.clock);write(item,"_pvp_reaper_idle",b.reaper_idle);write(item,"_pvp_airdrop_used",b.airdrop_used);write(item,"_pvp_bone_grave",b.bone_grave);
            if(b.hook_pull.present())item["_pvp_hook_pull"]={b.hook_pull.get().x,b.hook_pull.get().y};
            if(unit->barrel_position.present())item["_pvp_barrel_position"]=as_json(*unit->barrel_position.get());records.push_back(item);
        }
        for(const auto& shot:battle.content_projectiles.shots) {
            const auto& p=shot->motion;J item={{"x",p.x},{"y",p.y},{"vx",p.vx},{"vy",p.vy},{"age",shot->age},{"direction",shot->direction}};
            write(item,"kind",shot->kind);write(item,"source",shot->source);write(item,"target",shot->target);write(item,"anchor",shot->anchor);write(item,"defused",shot->defused);
            if(shot->owner.present())item["owner"]=seat_name(shot->owner.get());if(shot->seat.present())item["seat"]=seat_name(shot->seat.get());
            if(shot->cell.present())item["cell"]={shot->cell.get().y,shot->cell.get().x};shots.push_back(item);
        }
        for(const auto& unit:barrels.carriers())carriers.push_back(index(unit));
        row["controllers"]={{"events",controller_events},{"factory",factory_events},{"units",records},{"shots",shots},{"carriers",carriers}};
    }
};
J run_content_controllers(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    ContentControllersProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;}
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
#ifndef PVZ72_CONTENT_CONTROLLERS_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: content_controllers72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);if(!input||!output)throw std::runtime_error("controller fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_content_controllers(J::parse(line)).dump()<<'\n';return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
#endif
