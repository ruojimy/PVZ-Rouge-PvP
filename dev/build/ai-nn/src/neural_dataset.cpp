// Canonical feature encoder and independent C++ forward-pass parity tool.
#include "neural_planner.h"
#include "sim/typed72_app/cold_file.h"
#include <fstream>
#include <iostream>
int main(int argc,char** argv){
    try{
        using namespace ainn;
        if(argc<4)throw std::invalid_argument("neural_dataset out.jsonl model.json|- match.jsonl ...");
        std::shared_ptr<NeuralModel> model;if(std::string(argv[2])!="-")model=std::make_shared<NeuralModel>(J::parse(pvz::typed72app::read_file_maybe_gz(argv[2])));
        std::ofstream out(argv[1],std::ios::binary);if(!out)throw std::runtime_error("cannot write dataset");size_t count=0;
        const pvz::typed72::ColdCatalog catalog;
        out<<J{{"type","header"},{"format","pvz-neural-dataset-1"},{"behaviors",neural_behaviors()},
            {"catalog_hash",catalog.data().catalog_hash},{"rules_hash",catalog.data().rules_hash},
            {"sim_fingerprint",AI_NN_SIM_FINGERPRINT}}.dump()<<'\n';
        int stride=1;
        for(int a=3;a<argc;++a){
            if(std::string(argv[a])=="--stride"){
                if(++a>=argc||(stride=std::stoi(argv[a]))<1)throw std::invalid_argument("--stride needs positive integer");continue;
            }
            std::map<std::string,size_t> seat_records;
            std::ifstream file(argv[a],std::ios::binary);if(!file)throw std::runtime_error(std::string("cannot open ")+argv[a]);
            std::string line,id,map;
            while(std::getline(file,line)){
                const J r=J::parse(line);
                if(r.at("type")=="header"){id=r.at("id");map=r.at("map");continue;}
                if(r.at("type")!="plan")continue;
                if(seat_records[r.at("seat").get<std::string>()]++ % size_t(stride))continue;
                OwnedInput owned;input_from(r.at("input"),owned);
                const auto f=neural_features(owned.in,memory_from(r.at("memory")));const auto& p=r.at("plan");
                const bool plant=r.at("seat")=="plant";
                std::array<int,4> y{0,0,0,2};
                if(plant){y[0]=p.at("econ_goal").get<int>();y[1]=p.at("mode")=="siege";}
                else{y[2]=p.at("grave_start").get<int>();y[3]=p.at("save").is_null()?2:(p.at("save").get<bool>()?1:0);}
                J row={{"type","sample"},{"id",id},{"map",map},{"seat",r.at("seat")},{"tick",r.at("tick")},{"x",features_json(f)},{"y",y}};
                if(model){row["logits"]=model->logits(f);row["classes"]=model->classes(f);}
                out<<row.dump()<<'\n';++count;
            }
        }
        if(!out)throw std::runtime_error("dataset write failed");std::cout<<J{{"samples",count}}.dump()<<'\n';return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
