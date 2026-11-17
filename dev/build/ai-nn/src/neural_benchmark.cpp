// Compare inference alone on identical recorded features (no game-time confound).
#include "neural_planner.h"
#include "sim/typed72_app/cold_file.h"
#include <chrono>
#include <fstream>
#include <iostream>

int main(int argc,char** argv){
    try{
        using namespace ainn;
        if(argc<3)throw std::invalid_argument("neural_benchmark features.jsonl model.json ...");
        std::ifstream input(argv[1],std::ios::binary);std::string line;
        std::vector<NeuralFeatures> states;
        while(std::getline(input,line)&&states.size()<256){
            const auto row=J::parse(line);
            if(row.at("type")!="sample"||row.value("aug",0))continue;
            const auto& x=row.at("x");
            states.push_back({x.at("global").get<std::vector<double>>(),
                             x.at("own").get<std::vector<std::vector<double>>>(),
                             x.at("enemy").get<std::vector<std::vector<double>>>()});
        }
        if(states.empty())throw std::invalid_argument("no benchmark states");
        J result={{"format","pvz-neural-benchmark-1"},{"states",states.size()},{"rounds",9},
                  {"repeats_per_round",8},{"scope","model logits only; feature encoding and game simulation excluded"},
                  {"models",J::array()}};
        double checksum=0.;
        for(int a=2;a<argc;++a){
            const auto doc=J::parse(pvz::typed72app::read_file_maybe_gz(argv[a]));
            NeuralModel model(doc);std::vector<double> elapsed;
            size_t params=0;
            for(const auto* key:{"unit","body","heads"}){
                params+=doc.at(key).at("bias").size();
                for(const auto& row:doc.at(key).at("weight"))params+=row.size();
            }
            for(const auto& f:states)checksum+=model.logits(f)[0];
            for(int round=0;round<9;++round){
                const auto begin=std::chrono::steady_clock::now();
                for(int repeat=0;repeat<8;++repeat)for(const auto& f:states)checksum+=model.logits(f)[0];
                const double micro=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-begin).count();
                elapsed.push_back(micro/(8.*states.size()));
            }
            auto sorted=elapsed;std::sort(sorted.begin(),sorted.end());
            result["models"].push_back({{"path",argv[a]},{"parameters",params},{"embedding",doc.at("embedding")},
                {"hidden",doc.at("hidden")},{"microseconds_per_plan_median",sorted[4]},
                {"microseconds_per_plan_worst_round",sorted.back()},{"round_us",elapsed}});
        }
        result["checksum"]=checksum;std::cout<<result.dump(2)<<'\n';return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
