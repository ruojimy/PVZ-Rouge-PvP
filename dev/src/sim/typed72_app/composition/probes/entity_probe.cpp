#define PVZ72_TARGET_PROBE_EMBEDDED
#include "targets_probe.cpp"
namespace {
struct EntityProbe : TargetProbe {
    std::vector<EntityRef> retained;
    std::vector<Store<EntityRef>::Id> handles;
    std::shared_ptr<EntityRoster> original_entity_roster=visual.entities.list();
    explicit EntityProbe(int64_t seed):TargetProbe(seed,true){}
    std::shared_ptr<AttackSource> selected_source(const J& op)override {
        if(op.contains("entity_source")) {
            const auto& e=retained.at(op["entity_source"].get<size_t>());
            if(!e)throw std::invalid_argument("released entity source");return source_ref(e);
        }
        return TargetProbe::selected_source(op);
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="spawn_entity") {
            keys(op,{"op","name","position","facing"});visual.spawn(op.at("name"),op.value("facing",1.),motion(op.at("position")));
            const auto id=visual.entities.order().back();handles.push_back(id);retained.push_back(visual.entities.at(id));
        }else if(action=="erase_entity") {
            keys(op,{"op","entity"});result=visual.entities.erase(handles.at(op.at("entity").get<size_t>()));
        }else if(action=="release_entity") {
            keys(op,{"op","entity"});retained.at(op.at("entity").get<size_t>()).reset();
        }else if(action=="entity_kind") {
            keys(op,{"op","entity","name"});auto& e=retained.at(op.at("entity").get<size_t>());if(!e)throw std::logic_error("released entity");e->kind=op.at("name");
        }else if(action=="entity_position") {
            keys(op,{"op","entity","position"});auto& e=retained.at(op.at("entity").get<size_t>());if(!e)throw std::logic_error("released entity");e->motion=motion(op.at("position"));
        }else if(action=="tag_retained") {
            keys(op,{"op","entity","owner","source"});const auto& e=retained.at(op.at("entity").get<size_t>());
            const auto owner=op.contains("owner")?std::optional<Seat>(parse_seat(op.at("owner").get<std::string>())):std::nullopt;
            const auto parent=op.contains("source")?sources.at(op.at("source").get<size_t>()):nullptr;
            world.tag_entity(source_ref(e),&e->motion.get(),e->flight,owner,parent);
        }else return TargetProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        TargetProbe::extra_snapshot(row);row["retained_entities"]=J::array();row["entity_handles_alive"]=J::array();
        row["original_entity_roster_identity"]=visual.entities.list()==original_entity_roster;
        for(size_t i=0;i<retained.size();++i) {
            const auto& e=retained[i];row["retained_entities"].push_back(e?source_state(e->source,e->motion.get(),e->flight):J(nullptr));
            row["entity_handles_alive"].push_back(visual.entities.find(handles[i])!=nullptr);
        }
    }
};
J run_entity(const J& j){EntityProbe p(j.value("seed",int64_t(1)));configure_targets(p,j);p.operations(j.at("operations"));return p.states;}
}
#ifndef PVZ72_ENTITY_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: entity72_probe input.jsonl output.jsonl");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("cannot open entity fixture files");std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_entity(J::parse(line)).dump()<<'\n';
        if(!output)throw std::runtime_error("cannot write entity results");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
#endif
