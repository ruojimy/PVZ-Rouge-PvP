#define PVZ72_FLYING_PLANTS_PROBE_EMBEDDED
#include "flying_plants_probe.cpp"
#include "sim/typed/reed_plants.h"

namespace {
struct ReedPlantsProbe : FlyingPlantsProbe,ReedPlantServices {
    ReedPlants reeds{battle,queries,target_dispatch,*this};
    J reed_events=J::array();
    bool observe_reeds=false,gate_reeds=false;
    explicit ReedPlantsProbe(int64_t seed,double width,double splash):FlyingPlantsProbe(seed,width,splash){}
    void reed_event(const ReedEvent& event)override {
        reed_events.push_back({"lightning",{{"source",event.source.present() && !event.source.is_null()?J(event.source.get()):J(nullptr)},
            {"kind",event.overload?"overload":"chain"},{"targets",event.targets}}});
        before("reed_event");after("reed_event");
    }
    void plant_gate(size_t index)override {
        FlyingPlantsProbe::plant_gate(index);
        if(gate_reeds)reeds.advance(battle.plant_roster->at(index));
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="reed_setup"){observe_reeds=true;reeds.electrotherapy=op.at("electro");}
        else if(name=="reed_configure")result=reeds.configure(plant_ref(op.at("plant").get<size_t>()),op.at("name").get<std::string>());
        else if(name=="reed_fields") {
            auto& plant=*plant_ref(op.at("plant").get<size_t>());const auto& fields=op.at("fields");
            read_plant_fields(plant,fields);read(fields,"_pvp_reed_clock",plant.reed_clock);
        }else if(name=="reed_cone") {
            const auto distance=reeds.in_cone(plant_ref(op.at("plant").get<size_t>()),content_target(op.at("target")));
            if(distance)result=*distance;
        }else if(name=="reed_target") {
            const auto selected=reeds.select(plant_ref(op.at("plant").get<size_t>()));
            if(selected)result=content_label(*selected);
        }else if(name=="reed_contacts") {
            result=J::array();for(const auto& target:reeds.contacts(plant_ref(op.at("plant").get<size_t>()),content_target(op.at("target"))))
                result.push_back(content_label(target));
        }else if(name=="reed_tick" || name=="reed_lightning" || name=="reed_overload" || name=="reed_region") {
            gate_reeds=name=="reed_region";
            try {
                const auto plant=op.contains("plant")?plant_ref(op.at("plant").get<size_t>()):PlantRef{};
                HeroContext context(world,{Seat::zombie,Seat::plant,CombatPhase::plants,plant?source_ref(plant):nullptr,{}});
                NativeBirthScope births_scope(battle.runtime,static_cast<PlantRegionServices&>(*this));
                if(name=="reed_tick")reeds.advance(plant);
                else if(name=="reed_lightning")reeds.lightning(plant,content_target(op.at("target")));
                else if(name=="reed_overload")reeds.overload(plant,content_target(op.at("target")));
                else plants.run();
            }catch(const std::exception&) {
                gate_reeds=false;if(!op.value("catch",false))throw;result={{"caught",true}};
            }
            gate_reeds=false;
        }else return FlyingPlantsProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        FlyingPlantsProbe::extra_snapshot(row);if(!observe_reeds)return;
        J bolts=J::array();
        for(const auto& bolt:reeds.bolts) {
            J points=J::array();for(const auto point:bolt.points)points.push_back({point.x,point.y});
            bolts.push_back({bolt.tick,bolt.content,points});
        }
        row["reeds"]={{"events",reed_events},{"bolts",bolts}};
        for(size_t i=0;i<all_plants.size();++i)write(row["all_plants"][i],"_pvp_reed_clock",all_plants[i]->reed_clock);
        for(size_t i=0;i<battle.plant_roster->size();++i)write(row["plants"][i],"_pvp_reed_clock",battle.plant_roster->at(i)->reed_clock);
    }
};
J run_reed_plants(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    ReedPlantsProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);
    probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()) {
        probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;
    }
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();
    probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: reed_plants72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("reed plant fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_reed_plants(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
