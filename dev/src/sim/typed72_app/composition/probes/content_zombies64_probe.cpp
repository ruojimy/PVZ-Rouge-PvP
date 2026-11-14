#define PVZ72_GRENADIERS_PROBE_EMBEDDED
#include "grenadiers_probe.cpp"
#include "sim/typed/content_zombies64.h"

namespace {
struct ContentZombie64Probe : GrenadierProbe,ContentZombie64Services,ScriptedSpawnServices {
    ScriptedSpawnBudget budget{battle,*this,false};
    ContentZombies64 content64{battle,taunts,grenadiers,budget,sight,*this};
    J events64=J::array(),aliases64=J::array(),draws64=J::array(),spawns64=J::array();
    std::string spawn_mode64="ok";
    size_t spawned64=0,sync64=0;
    bool observe64=false;
    explicit ContentZombie64Probe(int64_t seed,double width,double splash):GrenadierProbe(seed,width,splash){}
    static J nullable(const Field<std::string>& value) {
        return value.present() && !value.is_null()?J(value.get()):J(nullptr);
    }
    void emit64(std::string name,J fields) {
        events64.push_back({name,fields});;;
    }
    void summon_deferred(const ScriptedSpawnKey& key,const Field<int64_t>& wave)override {
        J fields={{"source",key.source},{"summon",key.kind},{"slot",key.slot}};
        write(fields,"wave",wave);emit64("scripted_summon_deferred",fields);
    }
    ZombieRef spawn_dancer(Point,double,const ScriptedSpawnOrigin&)override {
        throw std::logic_error("dancer outside zombie64 fixture");
    }
    void alias_art(const std::string& source,const std::string& target)override {
        ;;;
    }
    void draw_zombie(const ZombieRef& unit)override {
        draws64.push_back(index(unit));;;
    }
    void publish_terrain()override {
        ++sync64;content64.belt_keys.clear();
        for(size_t row=0;row<battle.terrain.grid.size();++row) {
            const auto& line=battle.terrain.grid[row];
            for(size_t col=0;col<line.size();++col) {
                const auto& tile=*line[col];
                if(tile.belt.present() && !tile.belt.is_null() && tile.belt.get() &&
                   tile.block.present() && !tile.block.is_null() && tile.block.get()=="梯子块")
                    content64.belt_keys.insert(int64_t(row)*65536+int64_t(col));
            }
        }
        ;;
    }
    std::optional<SpawnedContentZombie> spawn_slime(const std::string& name,Point point,double facing,const SlimeSpawnParent& parent)override {
        const auto& origin=parent.origin;const auto& source=*origin.source;J fields=J::object();
        write(fields,"id",origin.public_id);write(fields,"_pvp_id",source.id);write(fields,"_pvp_owner",source.owner);
        if(source.seat)fields["_pvp_seat"]=seat_name(*source.seat);
        write(fields,"_pvp_wave_index",source.wave_index);write(fields,"_pvp_content",source.content);write(fields,"魅惑",source.charmed);
        write(fields,"方向",origin.facing);write(fields,"_pvp_slime_sticky",parent.sticky);
        if(origin.position.present())fields["位置"]=as_json(origin.position.get());
        if(origin.barrel_position.present())fields["_pvp_barrel_position"]=as_json(origin.barrel_position.get());
        spawns64.push_back({"zombie:"+name,"zombie",point.x,point.y,facing,true,fields,battle.spawn_ban_exempt,
            world.active?J(seat_name(world.active->owner)):J(nullptr),world.active?J(phase_name(world.active->phase)):J(nullptr)});
        ;
        if(spawn_mode64=="none")return {};
        if(spawn_mode64=="throw_before")throw std::runtime_error("slime constructor before");
        PlantRegionProbe::summon_zombie("普通僵尸",{point.x,point.y,0.,0.},facing);
        const auto child=units.back();const auto id="slime:"+std::to_string(++spawned64);
        child->source.id.set(id);battle.native_objects.set(id,child);
        if(spawn_mode64=="throw_after")throw std::runtime_error("slime constructor after");
        ;return SpawnedContentZombie{id,child};
    }
    void zombie64_event(const Zombie64Event& event)override {
        J fields=J::object();std::string name;
        if(event.kind==Zombie64Event::Kind::belt_placed) {
            name="belt_placed";fields={{"row",event.cell.y},{"col",event.cell.x},{"entity",nullable(event.entity)}};
        }else {
            fields["source"]=nullable(event.source);
            if(event.kind==Zombie64Event::Kind::slime_split) {
                name="slime_split";fields["card"]=event.card;fields["entities"]=event.children;
            }else {
                name=event.kind==Zombie64Event::Kind::grab?"redeye_grab":"redeye_throw";
                fields["entity"]=nullable(event.entity);
            }
        }
        emit64(name,fields);
    }
    void read64(CombatZombie& unit,const J& fields) {
        motion_unit(unit,fields);auto& state=unit.content64;
        read(fields,"_pvp_owner",unit.source.owner);read(fields,"_pvp_id",unit.source.id);
        read(fields,"_pvp_wave_index",unit.source.wave_index);read(fields,"_pvp_base_speed",unit.base_speed);
        read(fields,"_pvp_throw_clock",state.throw_clock);read(fields,"_pvp_grabbed_by",state.grabbed_by);
        read(fields,"_pvp_thrown_by",state.thrown_by);read(fields,"_pvp_split",state.split);read(fields,"_pvp_slime_sticky",state.sticky);
        read(fields,"_pvp_zs_hand_kind",state.hand_kind);read(fields,"_pvp_flight",unit.flight);
        if(fields.contains("_pvp_seat"))unit.source.seat=parse_seat(fields.at("_pvp_seat").get<std::string>());
        if(fields.contains("_pvp_grave"))unit.protection.grave=fields.at("_pvp_grave").get<bool>();
        if(fields.contains("_pvp_orphan_barrel"))unit.orphan_barrel=fields.at("_pvp_orphan_barrel").get<bool>();
        if(fields.contains("_pvp_grab")) {
            if(fields.at("_pvp_grab").is_null())state.grab.set_null();
            else {
                const auto& fields_grab=fields.at("_pvp_grab");auto grab=std::make_shared<RedeyeGrab>();
                read(fields_grab,"id",grab->id);grab->ticks=fields_grab.at("ticks");state.grab.set(grab);
            }
        }
        if(fields.contains("_pvp_grenade"))unit.grenadier.phase.set(grenade_phase(fields.at("_pvp_grenade").get<std::string>()));
        read(fields,"_pvp_grenade_clock",unit.grenadier.clock);
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="zombie64_setup") {
            observe64=true;const auto mode=op.at("mode").get<std::string>();budget.enabled=mode=="pve" || mode=="coop";
            const auto secrets=op.at("secrets");
            for(size_t index=0;index<world.players.size();++index)if(world.players[index]) {
                const auto key=std::string(seat_name(Seat(index)));
                world.players[index]->secrets=secrets.contains(key)?secrets.at(key).get<std::vector<std::string>>():std::vector<std::string>{};
            }
        }else if(name=="zombie64_fields") {
            auto& unit=*units.at(op.at("unit").get<size_t>());read64(unit,op.at("fields"));
            for(const auto& key:op.value("erase",std::vector<std::string>{})) {
                if(key=="魅惑")unit.source.charmed.erase();else if(key=="灰烬")unit.body.ash.erase();
                else throw std::invalid_argument("unhandled zombie64 erase");
            }
        }else if(name=="zombie64_registry") {
            const auto key=op.at("id").get<std::string>();
            if(op.contains("unit"))battle.native_objects.set(key,units.at(op.at("unit").get<size_t>()));
            else battle.native_objects.erase(key);
        }else if(name=="zombie64_belts")content64.belt_keys=op.at("keys").get<std::unordered_set<int64_t>>();
        else if(name=="zombie64_limit")read(op,"value",budget.limits.director);
        else if(name=="zombie64_spawn_mode")spawn_mode64=op.at("value").get<std::string>();
        else if(name=="zombie64_restore_taunt")taunts.restore();
        else if(name=="zombie64_configure" || name=="zombie64_gate" || name=="zombie64_finish" || name=="zombie64_on_belt" ||
                 name=="zombie64_throwable" || name=="zombie64_redeye" || name=="zombie64_landed" || name=="zombie64_split" ||
                 name=="zombie64_drain" || name=="zombie64_tag") {
            try {
                const auto unit=op.contains("unit")?units.at(op.at("unit").get<size_t>()):ZombieRef{};
                if(name=="zombie64_configure")result=content64.configure(unit,op.at("name").get<std::string>(),op.at("hp"),op.at("observed"));
                else if(name=="zombie64_gate")content64.gate(unit);
                else if(name=="zombie64_finish")content64.finish(unit,op.at("alive"));
                else if(name=="zombie64_on_belt")result=content64.on_belt(unit);
                else if(name=="zombie64_throwable") {const auto target=content64.throwable(unit);if(target)result=index(target);}
                else if(name=="zombie64_redeye")content64.redeye(unit);
                else if(name=="zombie64_landed")content64.landed();
                else if(name=="zombie64_split")content64.split(unit);
                else if(name=="zombie64_drain")budget.drain();
                else {
                    const auto point=op.at("point");const auto tag=op.at("name").get<std::string>();
                    content64.tag_belt(tag,{point.at(0),point.at(1)});
                    battle.runtime.emit_particles(tag,{point.at(0),point.at(1)},6);
                }
            }catch(const std::exception&) {if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return GrenadierProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        GrenadierProbe::extra_snapshot(row);if(!observe64)return;
        J records=J::array(),tiles=J::array(),pending=J::array();
        for(const auto& unit:units) {
            const auto& state=unit->content64;J fields=J::object();
            write(fields,"_pvp_content",unit->source.content);write(fields,"_pvp_max_hp",unit->max_hp);
            write(fields,"_pvp_base_speed",unit->base_speed);write(fields,"__pvz_sb_zombie_observed_max_hp",unit->patch.observed_max_hp);
            write(fields,"_pvp_throw_clock",state.throw_clock);write(fields,"_pvp_grabbed_by",state.grabbed_by);
            write(fields,"_pvp_thrown_by",state.thrown_by);write(fields,"_pvp_split",state.split);write(fields,"_pvp_slime_sticky",state.sticky);
            write(fields,"_pvp_zs_hand_kind",state.hand_kind);write(fields,"_pvp_flight",unit->flight);
            write(fields,"_pvp_taunted_by",unit->taunted_by);write(fields,"_pvp_id",unit->source.id);
            if(unit->source.seat)fields["_pvp_seat"]=seat_name(*unit->source.seat);
            write(fields,"_pvp_wave_index",unit->source.wave_index);
            if(state.grab.present()) {
                if(state.grab.is_null())fields["_pvp_grab"]=nullptr;
                else {J grab={{"ticks",state.grab.get()->ticks}};write(grab,"id",state.grab.get()->id);fields["_pvp_grab"]=grab;}
            }
            records.push_back(fields);
        }
        for(size_t y=0;y<battle.terrain.grid.size();++y)for(size_t x=0;x<battle.terrain.grid[y].size();++x) {
            const auto& field=battle.terrain.grid[y][x]->belt;
            if(field.present())tiles.push_back({y,x,field.is_null()?J(nullptr):J(field.get())});
        }
        for(const auto& request:budget.pending())pending.push_back({{request.key.source,request.key.kind,request.key.slot},
            request.wave.present() && !request.wave.is_null()?J(request.wave.get()):J(nullptr)});
        std::vector<int64_t> belts(content64.belt_keys.begin(),content64.belt_keys.end());std::sort(belts.begin(),belts.end());
        row["zombies64"]={{"events",events64},{"aliases",aliases64},{"draws",draws64},{"spawn",spawns64},
            {"sync",sync64},{"belts",belts},{"exempt",battle.spawn_ban_exempt},{"units",records},{"tiles",tiles},
            {"budget",{{"enabled",budget.enabled},{"draining",budget.draining},{"count",budget.count()},
                {"available",budget.available()},{"limit",budget.limit()},{"deferred",budget.deferred},
                {"admitted",budget.admitted},{"peak",budget.peak_pending},{"pending",pending}}}};
    }
};
J run_zombies64(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    ContentZombie64Probe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;}
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
#ifndef PVZ72_CONTENT_ZOMBIES64_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: content_zombies64_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("zombie64 fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_zombies64(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
#endif
