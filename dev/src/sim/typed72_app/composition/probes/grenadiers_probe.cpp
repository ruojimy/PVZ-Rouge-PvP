#define PVZ72_FLYING_PLANTS_PROBE_EMBEDDED
#include "flying_plants_probe.cpp"
#include "sim/typed/grenadiers.h"

namespace {
struct GrenadierProbe : FlyingPlantsProbe,GrenadierServices {
    Grenadiers grenadiers{battle,queries,target_dispatch,sight,*this};
    J grenade_events=J::array(),cost_calls=J::array(),costs=J::object();
    bool observe_grenadiers=false;
    explicit GrenadierProbe(int64_t seed,double width,double splash):FlyingPlantsProbe(seed,width,splash){}
    double card_cost(std::optional<Seat> owner,const std::string& key)override {
        ;;
        const auto value=costs.at(key);;return value.get<double>();
    }
    void grenade_event(const GrenadeEvent& event)override {
        const auto nullable=[](const Field<std::string>& field)->J{return field.present() && !field.is_null()?J(field.get()):J(nullptr);};
        J fields={{"source",nullable(event.source)}};std::string name;
        switch(event.kind) {
            case GrenadeEvent::Kind::cancelled:name="grenade_cancelled";break;
            case GrenadeEvent::Kind::no_target:name="grenade_no_target";break;
            case GrenadeEvent::Kind::thrown:name="grenade_thrown";fields["target"]=nullable(event.other);break;
            case GrenadeEvent::Kind::reflected:name="grenade_reflected";fields["umbrella"]=nullable(event.other);break;
            case GrenadeEvent::Kind::explode:name="grenade_explode";fields["row"]=event.cell.y;fields["col"]=event.cell.x;
                fields["targets"]=event.targets;fields["instant"]=event.instant;break;
        }
        ;;;
    }
    static GrenadierPhase grenade_phase(std::string_view phase) {
        if(phase=="ready")return GrenadierPhase::ready;
        if(phase=="wind")return GrenadierPhase::wind;
        if(phase=="thrown")return GrenadierPhase::thrown;
        if(phase=="cancelled")return GrenadierPhase::cancelled;
        throw std::invalid_argument("unknown grenade phase");
    }
    static const char* phase_text(GrenadierPhase phase) {
        switch(phase){case GrenadierPhase::ready:return "ready";case GrenadierPhase::wind:return "wind";
            case GrenadierPhase::thrown:return "thrown";case GrenadierPhase::cancelled:return "cancelled";}
        throw std::invalid_argument("unknown grenade phase");
    }
    static void read_grenade(Grenade& grenade,const J& fields) {
        auto& p=grenade.motion;
        if(fields.contains("x"))p.x=fields.at("x");if(fields.contains("y"))p.y=fields.at("y");
        if(fields.contains("vx"))p.vx=fields.at("vx");if(fields.contains("vy"))p.vy=fields.at("vy");
        if(fields.contains("owner"))grenade.owner=parse_seat(fields.at("owner").get<std::string>());
        if(fields.contains("seat")) {
            if(fields.at("seat").is_null())grenade.seat.set_null();else grenade.seat.set(parse_seat(fields.at("seat").get<std::string>()));
        }
        read(fields,"direction",grenade.direction);read(fields,"source",grenade.source);read(fields,"instant",grenade.instant);
        if(fields.contains("target"))grenade.target=fields.at("target").get<std::string>();
        if(fields.contains("cell"))grenade.cell=cell(fields.at("cell"));
        if(fields.contains("defused"))grenade.defused=fields.at("defused").get<bool>();
        if(fields.contains("age"))grenade.age=fields.at("age").get<int64_t>();
    }
    static J grenade_fields(const Grenade& grenade) {
        const auto& p=grenade.motion;
        J result={{"x",p.x},{"y",p.y},{"vx",p.vx},{"vy",p.vy},{"owner",seat_name(grenade.owner)},
            {"target",grenade.target},{"cell",{grenade.cell.y,grenade.cell.x}},{"defused",grenade.defused},{"age",grenade.age}};
        if(grenade.seat.present())result["seat"]=grenade.seat.is_null()?J(nullptr):J(seat_name(grenade.seat.get()));
        write(result,"direction",grenade.direction);write(result,"source",grenade.source);write(result,"instant",grenade.instant);return result;
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="grenade_setup") {
            observe_grenadiers=true;battle.world_height.set(op.at("height"));costs=op.at("costs");
            const auto secrets=op.value("secrets",J::object());
            for(size_t index=0;index<world.players.size();++index)if(world.players[index]) {
                const auto key=std::string(seat_name(Seat(index)));
                world.players[index]->secrets=secrets.contains(key)?secrets.at(key).get<std::vector<std::string>>():std::vector<std::string>{};
            }
        }else if(name=="grenadier_fields") {
            auto& unit=*units.at(op.at("unit").get<size_t>());const auto& fields=op.at("fields");auto& state=unit.grenadier;
            motion_unit(unit,fields);read(fields,"_pvp_owner",unit.source.owner);
            if(fields.contains("_pvp_seat"))unit.source.seat=parse_seat(fields.at("_pvp_seat").get<std::string>());
            read(fields,"_pvp_grenade_clock",state.clock);read(fields,"_pvp_seen_hp",state.seen_hp);read(fields,"_pvp_hold_x",state.hold_x);
            if(fields.contains("_pvp_grenade")) {
                if(fields.at("_pvp_grenade").is_null())state.phase.set_null();
                else state.phase.set(grenade_phase(fields.at("_pvp_grenade").get<std::string>()));
            }
            if(fields.contains("_pvp_content_position_before"))state.before.set(motion(fields.at("_pvp_content_position_before")));
            if(fields.contains("_pvp_grave"))unit.protection.grave=fields.at("_pvp_grave").get<bool>();
            if(fields.contains("_pvp_orphan_barrel"))unit.orphan_barrel=fields.at("_pvp_orphan_barrel").get<bool>();
        }else if(name=="grenade_add") {
            auto grenade=std::make_shared<Grenade>();read_grenade(*grenade,op.at("fields"));grenadiers.grenades->push_back(grenade);
        }else if(name=="grenade_fields")read_grenade(*grenadiers.grenades->at(op.at("grenade").get<size_t>()),op.at("fields"));
        else if(name=="grenade_roster") {
            auto roster=std::make_shared<GrenadeRoster>();
            for(const auto& index:op.at("indices"))roster->push_back(grenadiers.grenades->at(index.get<size_t>()));
            grenadiers.grenades=std::move(roster);
        }else if(name=="grenade_clear")grenadiers.grenades=std::make_shared<GrenadeRoster>();
        else if(name=="grenade_registry")battle.native_objects.set(op.at("id"),units.at(op.at("unit").get<size_t>()));
        else if(name=="grenade_zombie_scale")result=Grenadiers::zombie_vs_zombie(content_target(op.at("target")));
        else if(name=="grenadier_step" || name=="grenade_target" || name=="grenade_throw" || name=="grenade_update" || name=="grenade_reflect" || name=="grenade_explode") {
            try {
                if(name=="grenadier_step")grenadiers.advance(units.at(op.at("unit").get<size_t>()),op.at("alive"));
                else if(name=="grenade_target") {
                    const auto target=grenadiers.target(units.at(op.at("unit").get<size_t>()));if(target)result=content_label(*target);
                }else if(name=="grenade_throw")grenadiers.throw_grenade(units.at(op.at("unit").get<size_t>()));
                else if(name=="grenade_update")grenadiers.update();
                else if(name=="grenade_reflect")result=grenadiers.reflect(grenadiers.grenades->at(op.at("grenade").get<size_t>()));
                else grenadiers.explode(grenadiers.grenades->at(op.at("grenade").get<size_t>()),cell(op.at("cell")));
            }catch(const std::exception&) {if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return FlyingPlantsProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        FlyingPlantsProbe::extra_snapshot(row);if(!observe_grenadiers)return;
        J records=J::array(),shots=J::array(),blasts=J::array();
        for(const auto& unit:units) {
            J fields=J::object();const auto& state=unit->grenadier;
            if(state.phase.present())fields["_pvp_grenade"]=state.phase.is_null()?J(nullptr):J(phase_text(state.phase.get()));
            write(fields,"_pvp_grenade_clock",state.clock);write(fields,"_pvp_seen_hp",state.seen_hp);write(fields,"_pvp_hold_x",state.hold_x);
            if(state.before.present())fields["_pvp_content_position_before"]=as_json(state.before.get());
            records.push_back(fields);
        }
        for(const auto& grenade:*grenadiers.grenades)shots.push_back(grenade_fields(*grenade));
        for(const auto& blast:grenadiers.blasts)blasts.push_back({blast.tick,blast.point.x,blast.point.y,blast.instant});
        row["grenadiers"]={{"events",grenade_events},{"cost_calls",cost_calls},{"grenades",shots},{"blasts",blasts},{"units",records}};
    }
};
J run_grenadiers(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    GrenadierProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;}
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
#ifndef PVZ72_GRENADIERS_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: grenadiers72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("grenadier fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_grenadiers(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
#endif
