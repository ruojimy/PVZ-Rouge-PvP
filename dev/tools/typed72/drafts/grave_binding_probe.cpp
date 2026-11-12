#define PVZ72_PLANT_REGION_PROBE_EMBEDDED
#include "plant_region_probe.cpp"
#include "sim/typed/grave_binding.h"

namespace {
struct GraveBindingProbe : PlantRegionProbe,GraveBindingServices {
    GraveBinding bindings{battle,action_state,*this,*this};
    J binding_events=J::array();
    bool observe_bindings=false;
    explicit GraveBindingProbe(int64_t seed,double width,double splash):PlantRegionProbe(seed,width,splash){}
    size_t plant_index(const PlantRef& plant)const {
        const auto found=std::find(all_plants.begin(),all_plants.end(),plant);
        if(found==all_plants.end())throw std::logic_error("unregistered grave buster");
        return size_t(found-all_plants.begin());
    }
    void destroy_block(Cell point)override{bindings.destroy(point);}
    void grave_consumed(const ZombieRef& grave,const PlantRef& plant)override {
        calls.push_back(J::array({"grave_consume",index(grave),plant_index(plant)}));
        before("grave_consume");after("grave_consume");
    }
    void grave_event(GraveBindingEvent event)override {
        static constexpr const char* names[]={"grave_consume_started","grave_consumed","grave_consume_cancelled"};
        J fields={{"source_entity",event.source_id.present()&&!event.source_id.is_null()?J(event.source_id.get()):J(nullptr)},
                  {"target",event.target_id},{"native_tick",event.native_tick}};
        if(event.reason!=GraveBindingReason::none)
            fields["reason"]=event.reason==GraveBindingReason::plant_unavailable?"plant_unavailable":"target_unavailable";
        binding_events.push_back(J::array({names[size_t(event.kind)],fields}));
        before("grave_event");after("grave_event");
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="binding_setup")observe_bindings=true;
        else if(name=="binding_attach") {
            try {
                if(!op.at("target").is_string())throw std::invalid_argument("expected stable grave id");
                bindings.attach(plant_ref(op.at("plant").get<size_t>()),op.at("target"));
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(name=="binding_before")bindings.before_native_tick();
        else if(name=="binding_close")bindings.close();
        else if(name=="binding_destroy") {
            world.source_index=op.value("index",int64_t(-1));
            bindings.destroy(cell(op.at("cell")));
        }else if(name=="binding_coin") {
            action_state.coins.push_back({op.value("age",0.),motion(op.at("point")),op.value("cooldown",0.),op.at("kind")});
        }else if(name=="binding_draw_target") {
            const auto link=bindings.draw_target(op.at("index").get<size_t>());
            if(link)result=J::array({link->cell.y,link->cell.x,link->target_id});
        }else if(name=="binding_region" || name=="binding_scope") {
            try {
                HeroContext context(world,{Seat::zombie,Seat::plant,CombatPhase::plants,{},{}});
                GraveBinding::Plants scope(bindings);
                if(name=="binding_region")plants.run();else operations(op.at("body"),false);
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return PlantRegionProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        PlantRegionProbe::extra_snapshot(row);
        if(!observe_bindings)return;
        J links=J::array();
        for(const auto& link:bindings.links())links.push_back({plant_index(link->plant),index(link->target),link->target_id,{link->cell.y,link->cell.x}});
        std::vector<size_t> cancelled;
        for(const auto& [unused,plant]:bindings.cancelled())cancelled.push_back(plant_index(plant));
        std::sort(cancelled.begin(),cancelled.end());
        row["grave_binding"]={{"links",links},{"cancelled",cancelled},{"events",binding_events},
                              {"depth",bindings.depth()},{"closed",bindings.closed()}};
    }
};
J run_grave_binding(const J& input) {
    J base=input;
    const auto cfg=base.at("world_rules");base.erase("world_rules");
    GraveBindingProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);
    probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()) {
        probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));
        probe.battle.protection.secrets.enabled=true;
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
        if(argc!=3)throw std::invalid_argument("usage: grave_binding72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);
        std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("grave binding fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_grave_binding(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
