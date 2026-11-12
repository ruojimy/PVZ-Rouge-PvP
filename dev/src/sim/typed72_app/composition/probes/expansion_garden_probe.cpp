#define PVZ72_BONUS_PROBE_EMBEDDED
#include "bonus_probe.cpp"
#include "sim/typed/expansion_garden.h"

namespace {
constexpr std::array<const char*,10> garden_keys{"射cd","射","吃","发射cd","发射动画","埋藏","滚蛋","吸","爆了","路灯"};
struct GardenProbe : BonusProbe, ScarecrowServices {
    Scarecrows scarecrows{battle,sight,*this};
    ExpansionGarden garden{battle,scarecrows};
    bool garden_seen=false,garden_installed=false;
    explicit GardenProbe(int64_t seed,double width,double splash):BonusProbe(seed,width,splash){}
    std::optional<std::string> spawn_echo_crow(Point,double,const std::string&)override {
        throw std::logic_error("garden-only probe has no crow spawn boundary");
    }
    void crow_echo_event(const std::string&,const Field<std::string>&,const std::string&)override {
        throw std::logic_error("garden-only probe has no crow event boundary");
    }
    void expansion_before_plants()override {
        BonusProbe::expansion_before_plants();
        if(garden_installed)garden.before_plants(path_rules.producers);
    }
    void expansion_after_plants()override {
        BonusProbe::expansion_after_plants();
        if(garden_installed)garden.after_plants();
    }
    static void read_clock(const J& values,const char* key,Field<ExpansionClockValues>& field) {
        if(!values.contains(key))return;
        if(values.at(key).is_null()){field.set_null();return;}
        ExpansionClockValues items;
        for(size_t i=0;i<garden_keys.size();++i)read(values.at(key),garden_keys[i],items[i]);
        field.set(std::move(items));
    }
    static J clock_json(const ExpansionClockValues& values) {
        J result=J::object();
        for(size_t i=0;i<garden_keys.size();++i)write(result,garden_keys[i],values[i]);
        return result;
    }
    static void write_clock(J& row,const char* key,const Field<ExpansionClockValues>& field) {
        if(field.present())row[key]=field.is_null()?J(nullptr):clock_json(field.get());
    }
    void plant_garden(J& row,const PlantRef& plant) {
        write(row,"_pvp_aura_factor",plant->aura_factor);
        write_clock(row,"_pvp_clock_delta",plant->expansion_clock.delta);
        write_clock(row,"_pvp_clock_credit",plant->expansion_clock.credit);
        write_clock(row,"_pvp_clock_debt",plant->expansion_clock.debt);
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="garden_setup") {
            garden_seen=true;garden_installed=op.value("installed",false);
            const auto secrets=op.value("secrets",J::object());
            for(size_t i=0;i<world.players.size();++i)if(world.players[i]) {
                const auto seat=std::string(seat_name(Seat(i)));
                world.players[i]->secrets=secrets.value(seat,std::vector<std::string>{});
            }
            garden.configure_locked_secrets();
        }else if(name=="garden_plant") {
            auto plant=plant_ref(op.at("plant").get<size_t>());
            const auto& fields=op.at("fields");
            read_clock(fields,"_pvp_clock_delta",plant->expansion_clock.delta);
            read_clock(fields,"_pvp_clock_credit",plant->expansion_clock.credit);
            read_clock(fields,"_pvp_clock_debt",plant->expansion_clock.debt);
        }else if(name=="garden_avatar") {
            auto& avatar=world.heroes.at(seat_index(parse_seat(op.at("seat").get<std::string>()))).value();
            avatar.frame.hp.set(op.at("hp"));
            auto& position=*avatar.frame.position.get();
            position.x=op.at("point").at(0);position.y=op.at("point").at(1);
        }else if(name=="garden_tick")world.tick=op.at("tick");
        else if(name=="garden_scarecrow") {
            const auto unit=units.at(op.at("unit").get<size_t>());
            scarecrows.configure(unit,"稻草人",op.value("hp",100.));
            unit->source.owner.set(op.value("owner",std::string("zombie")));
            if(op.value("ash",false))unit->body.ash.set(0.);
        }else if(name=="garden_call") {
            const auto action=op.at("action").get<std::string>();
            if(action=="before")garden.before_plants(path_rules.producers);
            else if(action=="after")garden.after_plants();
            else if(action=="absorb")garden.absorb_clock_cap();
            else if(action=="aura")result=garden.aura(plant_ref(op.at("plant").get<size_t>()));
            else if(action=="pressure")result=garden.pressure(plant_ref(op.at("plant").get<size_t>()));
            else throw std::invalid_argument("garden operation");
        }else return BonusProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        BonusProbe::extra_snapshot(row);if(!garden_seen)return;
        for(size_t i=0;i<all_plants.size();++i)plant_garden(row["all_plants"][i],all_plants[i]);
        for(size_t i=0;i<battle.plant_roster->size();++i)plant_garden(row["plants"][i],battle.plant_roster->at(i));
        J centers=J::array(),cells=J::array(),slow=J::array(),spots=J::array(),before=J::array();
        for(const auto& cell:garden.aura_centers)centers.push_back({cell.y,cell.x});
        for(const auto& [cell,count]:garden.aura_cells)cells.push_back({cell.first,cell.second,count});
        for(const auto& [y,x]:garden.slow_cells)slow.push_back({y,x});
        for(const auto& spot:garden.pressure_positions)spots.push_back({spot.x,spot.y});
        for(size_t i=0;i<all_plants.size();++i) {
            const auto found=garden.timer_before.find(all_plants[i]->identity.value);
            if(found!=garden.timer_before.end())before.push_back({i,clock_json(found->second)});
        }
        row["garden"]={{"centers",centers},{"cells",cells},{"slow",slow},{"before",before},
            {"pressure_tick",garden.pressure_tick?J(*garden.pressure_tick):J(nullptr)},{"spots",spots}};
    }
};
J run_garden(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    GardenProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));
    probe.battle.dense_planting=cfg.at("dense");probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;}
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();
    probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
#ifndef PVZ72_EXPANSION_GARDEN_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: expansion_garden72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("garden fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_garden(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
#endif
