#define PVZ72_WORLD_RULES_PROBE_EMBEDDED
#include "world_rules_probe.cpp"
#include "sim/typed/scripted_spawn_budget.h"

namespace {
struct ScriptedSpawnProbe : WorldRulesProbe,ScriptedSpawnServices {
    ScriptedSpawnBudget budget{battle,*this,false};
    J events=J::array(),calls=J::array();
    std::vector<ScriptedSpawnOrigin> origins;
    std::string spawn_mode="ok";
    size_t spawned=0;
    bool observe_budget=false;
    explicit ScriptedSpawnProbe(int64_t seed,double width,double splash):WorldRulesProbe(seed,width,splash){}
    static J source_fields(const AttackSource& source) {
        J fields=J::object();
        write(fields,"_pvp_id",source.id);write(fields,"_pvp_owner",source.owner);
        if(source.seat)fields["_pvp_seat"]=seat_name(*source.seat);
        write(fields,"_pvp_wave_index",source.wave_index);write(fields,"_pvp_content",source.content);
        write(fields,"魅惑",source.charmed);return fields;
    }
    static J origin_fields(const ScriptedSpawnOrigin& origin) {
        auto fields=source_fields(*origin.source);
        write(fields,"id",origin.public_id);write(fields,"方向",origin.facing);
        const auto motion=[&](const char* name,const Field<Motion>& field) {
            if(field.present()){const auto& p=field.get();fields[name]={p.x,p.y,p.vx,p.vy};}
        };
        motion("位置",origin.position);motion("_pvp_barrel_position",origin.barrel_position);return fields;
    }
    void summon_deferred(const ScriptedSpawnKey& key,const Field<int64_t>& wave)override {
        J payload={{"source",key.source},{"summon",key.kind},{"slot",key.slot}};
        write(payload,"wave",wave);events.push_back({"scripted_summon_deferred",payload});
        ;;
    }
    ZombieRef spawn_dancer(Point point,double facing,const ScriptedSpawnOrigin& parent)override {
        ;
        if(spawn_mode=="none")return {};
        if(spawn_mode=="throw_before")throw std::runtime_error("spawn fixture before");
        WorldRulesProbe::summon_zombie("伴舞僵尸",{point.x,point.y,0.,0.},facing);
        const auto child=units.back();child->source.id.set("dancer:"+std::to_string(++spawned));
        if(spawn_mode=="throw_after")throw std::runtime_error("spawn fixture after");
        return child;
    }
    bool hold_dance()override{return budget.enabled && budget.hold_dance();}
    bool defer_dancer(Point point,double facing,int64_t slot)override{return budget.enabled && budget.defer_dancer(point,facing,slot);}
    bool hold_sled()override{return budget.enabled && budget.hold_spawn();}
    bool hold_giant()override{return budget.enabled && budget.hold_spawn();}
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="budget_setup") {
            observe_budget=true;const auto mode=op.at("mode").get<std::string>();
            budget.enabled=mode=="pve" || mode=="coop";battle.spawn_ban_exempt=op.value("exempt",0);
        }else if(name=="budget_limits") {
            if(op.value("clear_director",false))budget.limits.director.erase();
            if(op.value("clear_rule",false))budget.limits.rule.erase();
            read(op,"director",budget.limits.director);read(op,"rule",budget.limits.rule);
        }else if(name=="budget_fields") {
            auto& unit=*units.at(op.at("unit").get<size_t>());const auto& fields=op.at("fields");
            read(fields,"_pvp_wave_index",unit.source.wave_index);
            if(fields.contains("_pvp_seat"))unit.source.seat=parse_seat(fields.at("_pvp_seat").get<std::string>());
            if(fields.contains("_pvp_orphan_barrel"))unit.orphan_barrel=fields.at("_pvp_orphan_barrel");
            if(fields.contains("_pvp_grave"))unit.protection.grave=fields.at("_pvp_grave");
            if(fields.contains("_pvp_barrel_position")) {
                const auto& p=fields.at("_pvp_barrel_position");
                unit.barrel_position.set(std::make_shared<Motion>(Motion{p.at(0),p.at(1),p.at(2),p.at(3)}));
            }
            if(op.value("erase_wave",false))unit.source.wave_index.erase();
            if(op.value("erase_seat",false))unit.source.seat.reset();
        }else if(name=="budget_can") {
            std::shared_ptr<AttackSource> source;
            if(op.contains("unit"))source=source_ref(units.at(op.at("unit").get<size_t>()));
            result=budget.can_spawn(op.value("count",int64_t(1)),source);
        }else if(name=="budget_pending") {
            std::optional<int64_t> wave;if(op.contains("wave") && !op.at("wave").is_null())wave=op.at("wave").get<int64_t>();
            result=budget.pending_count(wave);
        }else if(name=="budget_for_source") {
            std::optional<std::string_view> kind;if(op.contains("kind"))kind=op.at("kind").get_ref<const std::string&>();
            result=budget.pending_for_source(units.at(op.at("unit").get<size_t>())->source,kind);
        }else if(name=="budget_clear")budget.clear();
        else if(name=="budget_spawn_mode")spawn_mode=op.at("mode").get<std::string>();
        else if(name=="budget_snapshot")origins.push_back(scripted_spawn_origin(units.at(op.at("unit").get<size_t>())));
        else if(name=="budget_inherit") {
            const AttackSource* source=nullptr;
            if(op.contains("origin"))source=origins.at(op.at("origin").get<size_t>()).source.get();
            else if(op.contains("parent"))source=&units.at(op.at("parent").get<size_t>())->source;
            ScriptedSpawnBudget::inherit(units.at(op.at("unit").get<size_t>())->source,source);
        }else if(name=="budget_defer" || name=="budget_drain" || name=="budget_native_dancer" || name=="budget_hold") {
            try {
                if(name=="budget_drain")budget.drain();
                else if(name=="budget_hold")result=op.value("dance",false)?budget.hold_dance():budget.hold_spawn();
                else if(name=="budget_native_dancer")result=budget.defer_dancer({op.at("point").at(0),op.at("point").at(1)},op.at("facing"),op.at("slot"));
                else {
                    const auto source=source_ref(units.at(op.at("unit").get<size_t>()));
                    const auto callback=op.at("callback");
                    result=budget.defer(source,op.at("kind").get<std::string>(),op.at("slot"),[this,callback]() {
                        if(callback.contains("body"))operations(callback.at("body"),false);
                        if(callback.value("throw",false))throw std::runtime_error("deferred callback fixture");
                        return callback.value("result",true);
                    });
                }
            }catch(const std::exception&) {if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return WorldRulesProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        WorldRulesProbe::extra_snapshot(row);if(!observe_budget)return;
        J pending=J::array(),records=J::array(),snapshots=J::array();
        for(const auto& request:budget.pending())pending.push_back({{request.key.source,request.key.kind,request.key.slot},
            request.wave.present() && !request.wave.is_null()?J(request.wave.get()):J(nullptr)});
        for(const auto& unit:units)records.push_back(source_fields(unit->source));
        for(const auto& origin:origins)snapshots.push_back(origin_fields(origin));
        row["budget"]={{"enabled",budget.enabled},{"draining",budget.draining},{"limit",budget.limit()},
            {"count",budget.count()},{"available",budget.available()},{"admitted",budget.admitted},
            {"deferred",budget.deferred},{"peak",budget.peak_pending},{"pending",pending},{"units",records},
            {"origins",snapshots},{"events",events},{"calls",calls},{"exempt",battle.spawn_ban_exempt}};
    }
};
J run_budget(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    ScriptedSpawnProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));
    probe.battle.dense_planting=cfg.at("dense");probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;}
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: scripted_spawn72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("scripted spawn fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_budget(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
