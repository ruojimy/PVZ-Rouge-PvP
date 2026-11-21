// Canonical feature encoder and independent C++ forward-pass parity tool.
#include "neural_planner.h"
#include "sim/typed72_app/cold_file.h"
#include <fstream>
#include <iostream>
#include <random>
namespace {
// Relabelled augmentation: r22 is a pure function of (input, memory), so any perturbed state
// can be labelled exactly by calling it. This covers the thresholds r22 switches on (resource,
// time, unit counts, peaks) far more densely than the states its own games happen to visit.
// Only mt19937_64 and integer-to-double arithmetic are used, so output is identical across platforms.
struct Draw {
    std::mt19937_64 rng;
    explicit Draw(uint64_t seed):rng(seed){}
    double unit(){return double(rng()>>11)*(1./9007199254740992.);}
    double range(double lo,double hi){return lo+(hi-lo)*unit();}
    bool chance(double p){return unit()<p;}
};
uint64_t mix(uint64_t h,const std::string& text){for(unsigned char c:text){h^=c;h*=1099511628211ull;}return h;}
void perturb(ainn::OwnedInput& o,ainn::AiPlannerMemory& m,Draw& d){
    auto& in=o.in;
    if(d.chance(.6))in.me.resource=std::floor(d.range(0.,900.));
    if(d.chance(.3))in.foe.resource=std::floor(d.range(0.,900.));
    if(d.chance(.5)){const double t=std::floor(d.range(0.,600.)*10.)/10.,delta=t-in.time;in.time=t;m.last_pressure_at+=delta;m.last_attack_at+=delta;m.push_until+=delta;}
    if(d.chance(.3))in.me.hp=std::max(1.,std::floor(d.range(1.,in.me.max_hp+1.)));
    if(d.chance(.3))in.foe.hp=std::max(1.,std::floor(d.range(1.,in.foe.max_hp+1.)));
    if(d.chance(.3))m.last_enemy_hp=std::floor(d.range(0.,in.foe.max_hp+1.));
    if(d.chance(.6)){
        const double q=d.range(0.,.7);std::vector<ainn::AiUnitView> kept;
        for(auto& u:o.units)if(!d.chance(q))kept.push_back(std::move(u));
        o.units=std::move(kept);in.units=o.units;
    }
    if(d.chance(.3))m.peak_econ=int64_t(d.range(0.,11.));
    if(d.chance(.3))m.peak_graves=int64_t(d.range(0.,11.));
    if(d.chance(.15))m.mode=m.mode=="siege"?"defend":"siege";
    if(d.chance(.1))in.recovering=!in.recovering;
}
}
int main(int argc,char** argv){
    try{
        using namespace ainn;
        if(argc<4)throw std::invalid_argument("neural_dataset out.jsonl model.json|- [--stride N] [--augment N] [--seed N] match.jsonl ...");
        std::shared_ptr<NeuralModel> model;if(std::string(argv[2])!="-")model=std::make_shared<NeuralModel>(J::parse(pvz::typed72app::read_file_maybe_gz(argv[2])));
        std::ofstream file_out;const bool streaming=std::string(argv[1])=="-";
        if(!streaming)file_out.open(argv[1],std::ios::binary);
        std::ostream& out=streaming?std::cout:file_out;if(!out)throw std::runtime_error("cannot write dataset");size_t count=0;
        const pvz::typed72::ColdCatalog catalog;
        // Options must precede the match files: the header records them.
        int stride=1,augment=0,feature_version=model?model->feature_version():1,policy_version=model?model->policy_version():1,relabel=0;uint64_t seed=743;int first=3;std::string inputs_list;
        for(;first+1<argc;first+=2){
            const std::string option=argv[first];
            if(option=="--stride"){if((stride=std::stoi(argv[first+1]))<1)throw std::invalid_argument("--stride needs positive integer");}
            else if(option=="--augment"){if((augment=std::stoi(argv[first+1]))<0||augment>64)throw std::invalid_argument("--augment needs 0..64");}
            else if(option=="--seed")seed=std::stoull(argv[first+1]);
            else if(option=="--feature-version")feature_version=std::stoi(argv[first+1]);
            else if(option=="--policy-version")policy_version=std::stoi(argv[first+1]);
            else if(option=="--relabel")relabel=std::stoi(argv[first+1]);
            else if(option=="--inputs-list")inputs_list=argv[first+1];
            else break;
        }
        J header={{"type","header"},{"format","pvz-neural-dataset-1"},{"behaviors",neural_behaviors()},
            {"catalog_hash",catalog.data().catalog_hash},{"rules_hash",catalog.data().rules_hash},
            {"sim_fingerprint",AI_NN_SIM_FINGERPRINT}};
        if(augment){header["augment"]=augment;header["augment_seed"]=seed;}
        if(feature_version!=1&&feature_version!=2)throw std::invalid_argument("unsupported feature version");
        if(model&&feature_version!=model->feature_version())throw std::invalid_argument("model/feature version mismatch");
        if(feature_version==2)header["feature_version"]=2;
        if(policy_version!=1&&policy_version!=2)throw std::invalid_argument("unsupported policy version");
        if(model&&policy_version!=model->policy_version())throw std::invalid_argument("model/policy version mismatch");
        if(policy_version==2)header["policy_version"]=2;
        out<<header.dump()<<'\n';
        std::vector<std::string> files;
        if(!inputs_list.empty()){
            std::ifstream list(inputs_list);if(!list)throw std::runtime_error("cannot read inputs list");std::string name;
            while(std::getline(list,name)){if(!name.empty()&&name.back()=='\r')name.pop_back();if(!name.empty())files.push_back(name);}
        }
        for(int a=first;a<argc;++a)files.push_back(argv[a]);
        if(files.empty())throw std::invalid_argument("no match files");
        for(size_t a=0;a<files.size();++a){
            if(files[a]=="--stride"){
                if(++a>=files.size()||(stride=std::stoi(files[a]))<1)throw std::invalid_argument("--stride needs positive integer");continue;
            }
            std::map<std::string,size_t> seat_records;
            std::ifstream file(files[a],std::ios::binary);if(!file)throw std::runtime_error(std::string("cannot open ")+files[a]);
            std::string line,id,map;
            while(std::getline(file,line)){
                const J r=J::parse(line);
                if(r.at("type")=="header"){id=r.at("id");map=r.at("map");continue;}
                if(r.at("type")!="plan")continue;
                if(seat_records[r.at("seat").get<std::string>()]++ % size_t(stride))continue;
                OwnedInput owned;input_from(r.at("input"),owned);
                const auto memory=memory_from(r.at("memory"));
                const auto f=neural_features(owned.in,memory,feature_version);auto p=r.at("plan");
                if(relabel){pvz::typed72app::AiPlannerR22 teacher(owned.in.side);teacher.set_memory(memory);p=plan_json(teacher.plan(owned.in));}
                const bool plant=r.at("seat")=="plant";
                std::array<int,4> y{0,0,0,2};
                if(plant){y[0]=std::clamp(p.at("econ_goal").get<int>(),0,policy_version==2?11:10);y[1]=p.at("mode")=="siege";}
                else{y[2]=std::clamp(p.at("grave_start").get<int>(),0,10);y[3]=p.at("save").is_null()?2:(p.at("save").get<bool>()?1:0);}
                J row={{"type","sample"},{"id",id},{"map",map},{"seat",r.at("seat")},{"tick",r.at("tick")},{"x",features_json(f)},{"y",y}};
                if(model){row["logits"]=model->logits(f);row["classes"]=model->classes(f);}
                out<<row.dump()<<'\n';++count;
                for(int k=1;k<=augment;++k){
                    Draw draw(mix(mix(seed*1099511628211ull+uint64_t(k),id+"/"+r.at("seat").get<std::string>()),std::to_string(r.at("tick").get<int64_t>())));
                    OwnedInput varied;input_from(r.at("input"),varied);auto memory=memory_from(r.at("memory"));perturb(varied,memory,draw);
                    const auto vf=neural_features(varied.in,memory,feature_version);
                    pvz::typed72app::AiPlannerR22 teacher(varied.in.side);teacher.set_memory(memory);const J vp=plan_json(teacher.plan(varied.in));
                    std::array<int,4> vy{0,0,0,2};
                    if(plant){vy[0]=std::clamp(vp.at("econ_goal").get<int>(),0,policy_version==2?11:10);vy[1]=vp.at("mode")=="siege";}
                    else{vy[2]=std::clamp(vp.at("grave_start").get<int>(),0,10);vy[3]=vp.at("save").is_null()?2:(vp.at("save").get<bool>()?1:0);}
                    out<<J{{"type","sample"},{"id",id},{"map",map},{"seat",r.at("seat")},{"tick",r.at("tick")},{"aug",k},{"x",features_json(vf)},{"y",vy}}.dump()<<'\n';++count;
                }
            }
        }
        if(!out)throw std::runtime_error("dataset write failed");(streaming?std::cerr:std::cout)<<J{{"samples",count}}.dump()<<'\n';return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
