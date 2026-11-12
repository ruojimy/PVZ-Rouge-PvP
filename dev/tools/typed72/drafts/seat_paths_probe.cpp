#define PVZ72_RESOURCES_PROBE_EMBEDDED
#include "resources_probe.cpp"
#include "sim/typed/seat_path_tracking.h"
#include <map>

namespace {
struct SeatPathsProbe:ResourcesProbe {
    SeatCommands commands;
    SeatPathTracking banks{battle,navigation,path_rules,sight,hero_flags,commands};
    uint64_t published_revision=0;
    bool observe_banks=false;
    explicit SeatPathsProbe(int64_t seed,double width,double splash):ResourcesProbe(seed,width,splash){}
    static PathMode mode(const J& j){return j.get<std::string>()=="follow"?PathMode::follow_hero:PathMode::attack_plants;}
    std::optional<PathSnapshot> phase_baseline;
    bool extra_operation(const J& op,J& result)override{
        const auto name=op.at("op").get<std::string>();
        if(name=="banks_setup"){
            observe_banks=true;commands.shared=mode(op.at("command"));
            for(const auto& [s,m]:op.at("commands").items())commands.by_seat[seat_index(parse_seat(s))]=mode(m);
            navigation.scripted=op.at("scripted");published_revision=op.at("revision");
            const auto seats=seats_for(battle.mode);present.assign(seats.begin(),seats.end());
            for(size_t i=0;i<world.heroes.size();++i)if(world.heroes[i])world.heroes[i]->actual_seat=Seat(i);
        }else if(name=="banks_command"){
            commands.shared=mode(op.at("command"));
            for(const auto& [s,m]:op.at("commands").items())commands.by_seat[seat_index(parse_seat(s))]=mode(m);
        }else if(name=="banks_flag"){
            const auto seat=parse_seat(op.at("side").get<std::string>());
            std::optional<Point> point;
            if(!op.at("point").is_null())point=Point{op.at("point").at(0),op.at("point").at(1)};
            if(battle.mode==MatchMode::duo)hero_flags.by_seat[seat_index(seat)]=point;
            if(seat==Seat::zombie || battle.mode!=MatchMode::duo)hero_flags.shared=point;
        }else if(name=="banks_team")result=seat_name(banks.advance_team(present));
        else if(name=="banks_rallies")banks.advance_rallies(present,published_revision);
        else if(name=="banks_destination"){
            const auto point=banks.destination(parse_seat(op.at("side").get<std::string>()),published_revision);
            if(point)result=J::array({point->x,point->y});
        }else if(name=="banks_publish"){
            for(const auto& edit:op.at("changes"))sight.solid.at(edit.at(0).get<size_t>()).at(edit.at(1).get<size_t>())=edit.at(2).get<uint8_t>();
            published_revision=op.at("revision");
        }else if(name=="banks_public_hp")world.players[seat_index(parse_seat(op.at("side").get<std::string>()))]->hp=op.at("value");
        else if(name=="banks_begin"){phase_baseline=banks.capture();banks.begin_zombies();}
        else if(name=="banks_end"){banks.end_zombies();phase_baseline.reset();}
        else if(name=="banks_alias")world.select_plant_seat(parse_seat(op.at("side").get<std::string>()));
        else if(name=="banks_switch")banks.switch_for(*units.at(op.at("unit").get<size_t>()),present);
        else if(name=="banks_rally"){
            const auto unit=units.at(op.at("unit").get<size_t>());
            for(size_t i=0;i<battle.targets->size();++i)if(battle.targets->at(i).unit==unit){world.source_index=int64_t(i);break;}
            banks.select_rally(*unit);
        }else if(name=="banks_restore")banks.restore_rally();
        else if(name=="banks_native_write"){
            navigation.hold_plant=op.at("hold");navigation.running=op.at("running");navigation.target_plant=op.at("target");
            navigation.flood[0].cooldown=op.at("cooldown");
            const auto& c=op.at("cell");
            navigation.chase_fields.at(op.at("field").get<size_t>())->at(c.at(0).get<size_t>()*battle.terrain.cols()+c.at(1).get<size_t>())=c.at(2);
        }else if(name=="banks_unit"){
            auto& source=units.at(op.at("unit").get<size_t>())->source;
            if(op.at("seat").is_null())source.seat.reset();else source.seat=parse_seat(op.at("seat").get<std::string>());
            if(op.at("charm").get<bool>())source.charmed.set(0.);else source.charmed.erase();
        }else return ResourcesProbe::extra_operation(op,result);
        return true;
    }
    J grid(const std::vector<int>& field)const{
        J result=J::array();const auto cols=battle.terrain.cols();
        for(int y=0;y<battle.terrain.rows();++y){
            J row=J::array();for(int x=0;x<cols;++x)row.push_back(field.at(size_t(y)*cols+x));
            result.push_back(std::move(row));
        }
        return result;
    }
    std::map<const void*,size_t> identities;
    size_t identity(const void* pointer){return identities.try_emplace(pointer,identities.size()).first->second;}
    J chase_json(const ChaseSnapshot& state){
        J fields=J::array(),aliases=J::array();
        for(const auto& field:state.fields){fields.push_back(grid(*field));aliases.push_back(identity(field.get()));}
        return {{"fields",fields},{"aliases",aliases},{"goal",{state.goal.y,state.goal.x}},
                {"target",state.target},{"running",state.running},{"output",state.output}};
    }
    J path_json(const PathSnapshot& state){
        J fields=J::array(),aliases=J::array();
        const auto chase=chase_json(state.chase);
        for(const auto& f:state.flood){
            J queue=J::array();for(const auto c:*f.queue)queue.push_back({c.y,c.x});
            fields.push_back({f.cooldown,f.sign,grid(*f.field),queue});
            aliases.push_back(identity(f.field.get()));aliases.push_back(identity(f.queue.get()));
        }
        return {{"fields",fields},{"chase",chase},{"hold",state.hold},
                {"hero",{state.wjy.get(),state.wjx.get()}},{"aliases",aliases}};
    }
    J rally_json(const RallyPathBank& state){
        return {{"path",path_json(state.path)},{"goal",state.goal?J::array({state.goal->x,state.goal->y}):J(nullptr)}};
    }
    void extra_snapshot(J& row)override{
        ResourcesProbe::extra_snapshot(row);if(!observe_banks)return;
        identities.clear();J value=J::object();value["current"]=path_json(banks.capture());
        value["seats"]=J::object();value["rallies"]=J::object();
        for(size_t i=0;i<4;++i)if(banks.seats()[i])value["seats"][seat_name(Seat(i))]=path_json(*banks.seats()[i]);
        for(size_t i=0;i<4;++i)if(banks.rally_seats()[i])value["rallies"][seat_name(Seat(i))]=rally_json(*banks.rally_seats()[i]);
        value["shared"]=banks.shared_rally()?rally_json(*banks.shared_rally()):J(nullptr);
        value["base"]=banks.rally_base()?chase_json(*banks.rally_base()):J(nullptr);
        value["phase"]=phase_baseline?path_json(*phase_baseline):J(nullptr);
        value["selected"]=banks.selected_seat()?J(seat_name(*banks.selected_seat())):J(nullptr);
        row["path_banks"]=std::move(value);
    }
};
J run_seat_paths(const J& j){
    J base=j;const auto cfg=base.at("world_rules");base.erase("world_rules");
    SeatPathsProbe p(j.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));configure_shooting(p,base);
    p.battle.world_width.set(cfg.at("width"));p.battle.dense_planting=cfg.at("dense");
    p.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){p.battle.protection.secrets.team.set(size_t(DamageSecret::rage));p.battle.protection.secrets.enabled=true;}
    p.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();p.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    p.rules.homing_height=cfg.at("heights").get<decltype(p.rules.homing_height)>();p.collision.unit_scale=cfg.at("scale").get<decltype(p.collision.unit_scale)>();
    p.operations(j.at("operations"));return p.states;
}
}
int main(int argc,char** argv){
    try{
        if(argc!=3)throw std::invalid_argument("usage: seat_paths72_probe inputs output");
        std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);
        if(!in||!out)throw std::runtime_error("seat path fixture streams");
        std::string line;while(std::getline(in,line))if(!line.empty())out<<run_seat_paths(J::parse(line)).dump()<<'\n';
        return out?0:2;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
