#define PVZ72_CHILI_PROBE_EMBEDDED
#include "chili_probe.cpp"
#include "sim/typed/sourced_context.h"
namespace {
struct SourcedProbe:ChiliProbe {
    J observations=J::array();
    explicit SourcedProbe(int64_t seed):ChiliProbe(seed){}
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="source_call") {
            keys(op,{"op","kind","source","unit_source","entity_source","body","catch","return"});const std::string kind=op.at("kind");
            const auto call=kind=="regular"?SourcedCall::regular:kind=="spawn"?SourcedCall::spawn:kind=="player"?SourcedCall::player_hit:throw std::invalid_argument("unknown sourced call");
            try {
                SourcedContext context(battle,selected_source(op),call==SourcedCall::player_hit?CombatPhase::entities:CombatPhase::zombies,call);
                operations(op.at("body"),false);result=op.value("return",J(nullptr));context.finish();
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(action=="source_write") {
            keys(op,{"op","source","unit_source","entity_source","values"});auto s=selected_source(op);if(!s)throw std::invalid_argument("missing fixture source");const auto& v=op.at("values");
            keys(v,{"植物","魅惑","_pvp_owner","_pvp_id","_pvp_instant_attack"});read(v,"植物",s->plant);read(v,"魅惑",s->charmed);read(v,"_pvp_owner",s->owner);read(v,"_pvp_id",s->id);
            if(v.contains("_pvp_instant_attack"))s->instant_attack=attack_identity(v["_pvp_instant_attack"]);
        }else if(action=="source_throw")throw std::runtime_error("injected sourced body failure");
        else if(action=="source_observe") {
            keys(op,{"op"});J active=nullptr;if(world.active)active={{"owner",seat_name(world.active->owner)},{"target",seat_name(world.active->target)},{"phase",phase_name(world.active->phase)}};
            observations.push_back({{"active",active},{"globals",as_json(world.globals)}});
        }else return ChiliProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override {
        ChiliProbe::extra_snapshot(row);row["source_observations"]=observations;row["launch_tokens"]=J::object();
        for(size_t i=0;i<world.heroes.size();++i)if(world.contains(Seat(i))){const auto& h=world.hero(Seat(i));if(h.launch_attack)row["launch_tokens"][seat_name(Seat(i))]=h.launch_attack->hero_text();}
    }
};
J run_sourced(const J& j){SourcedProbe p(j.value("seed",int64_t(1)));configure_doom(p,j);p.operations(j.at("operations"));return p.states;}
}
#ifndef PVZ72_SOURCED_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try{if(argc!=3)throw std::invalid_argument("usage: sourced72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);if(!in||!out)throw std::runtime_error("sourced fixture files");std::string line;
        while(std::getline(in,line))if(!line.empty())out<<run_sourced(J::parse(line)).dump()<<'\n';if(!out)throw std::runtime_error("sourced output");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
#endif
