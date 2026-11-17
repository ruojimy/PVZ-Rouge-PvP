// Relabel the exact states visited by a student, retaining the executed plan separately.
// This is a counterfactual teacher recommendation, not a teacher-played trajectory.
#include "plan_codec.h"
#include <fstream>
#include <iostream>

int main(int argc,char** argv){
    try{
        if(argc!=3)throw std::invalid_argument("teacher_trace student.jsonl relabelled.jsonl");
        std::ifstream source(argv[1],std::ios::binary);
        std::ofstream out(argv[2],std::ios::binary);
        if(!source||!out)throw std::runtime_error("cannot open trajectory");
        std::string line;size_t count=0;
        while(std::getline(source,line)){
            auto row=ainn::J::parse(line);
            if(row.at("type")=="header"){
                row["label_source"]="r22-on-recorded-input-and-memory";
                row["trajectory_is_teacher_played"]=false;
                row["source_file"]=argv[1];
            }else if(row.at("type")=="plan"){
                ainn::OwnedInput owned;ainn::input_from(row.at("input"),owned);
                pvz::typed72app::AiPlannerR22 teacher(owned.in.side);
                teacher.set_memory(ainn::memory_from(row.at("memory")));
                row["executed_plan"]=row.at("plan");
                row["executed_planner"]=row.at("planner");
                row["plan"]=ainn::plan_json(teacher.plan(owned.in));
                row["planner"]="r22-relabelled";++count;
            }
            out<<row.dump()<<'\n';
        }
        if(!out)throw std::runtime_error("trajectory write failed");
        std::cout<<ainn::J{{"records",count},{"trajectory_is_teacher_played",false}}.dump()<<'\n';
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
