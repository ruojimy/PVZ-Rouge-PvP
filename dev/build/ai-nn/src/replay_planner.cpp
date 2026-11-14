// Step 4b: recompute r22 offline from the recorded planner calls of headless_match and
// compare every plan with the recorded one.
//   replay_planner <match.jsonl> [more.jsonl ...]
// For each "plan" record a fresh AiPlannerR22 gets the recorded memory and input; the plan
// (and the memory after the call, checked against the same seat's next record) must be equal.
#include "plan_codec.h"
#include <fstream>
#include <iostream>
#include <map>
int main(int argc,char** argv){
    try{
        if(argc<2)throw std::invalid_argument("usage: replay_planner <match.jsonl> [more.jsonl ...]");
        using namespace ainn;using pvz::typed72app::AiPlannerR22;
        uint64_t files=0,records=0,plan_mismatch=0,memory_checked=0,memory_mismatch=0,skipped=0;
        for(int a=1;a<argc;++a){
            std::ifstream in(argv[a],std::ios::binary);if(!in)throw std::runtime_error(std::string("cannot open ")+argv[a]);
            ++files;std::string line;std::map<std::string,J> expected_memory;   // seat -> memory after its previous plan
            while(std::getline(in,line)){
                if(line.empty())continue;
                const J row=J::parse(line);
                if(row.value("type",std::string{})!="plan")continue;
                if(row.at("planner")!="r22"){++skipped;continue;}
                ++records;
                const std::string seat=row.at("seat");
                if(auto f=expected_memory.find(seat);f!=expected_memory.end()){++memory_checked;if(f->second!=row.at("memory")){++memory_mismatch;if(memory_mismatch<=3)std::cerr<<argv[a]<<" tick "<<row.at("tick")<<" "<<seat<<": memory differs\n";}}
                OwnedInput owned;input_from(row.at("input"),owned);
                AiPlannerR22 planner(owned.in.side);planner.set_memory(memory_from(row.at("memory")));
                const J plan=plan_json(planner.plan(owned.in));
                if(plan!=row.at("plan")){++plan_mismatch;if(plan_mismatch<=3)std::cerr<<argv[a]<<" tick "<<row.at("tick")<<" "<<seat<<": plan differs\n  recorded "<<row.at("plan").dump()<<"\n  replayed "<<plan.dump()<<'\n';}
                expected_memory[seat]=memory_json(planner.memory());
            }
        }
        std::cout<<J{{"files",files},{"plan_records",records},{"plan_mismatches",plan_mismatch},{"memory_checks",memory_checked},{"memory_mismatches",memory_mismatch},{"skipped_non_r22",skipped}}.dump()<<'\n';
        return plan_mismatch||memory_mismatch?1:0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
