#pragma once
// Opt-in research planner. Four learned strategy heads; r22 still owns the
// controller, card ordering/quotas, remaining constants and strategy memory.
#include "plan_codec.h"
#include "ai_nn_build.h"
#include "sim/typed/cold_catalog.h"
#include "sim/typed/ai_geometry.h"
#include <algorithm>
#include <memory>
#include <stdexcept>

namespace ainn {
struct NeuralFeatures {std::vector<double> global;std::vector<std::vector<double>> own,enemy;};
inline const std::vector<std::string>& neural_behaviors(){
    static const std::vector<std::string> values=[] {
        std::vector<std::string> v;
        const pvz::typed72::ColdCatalog catalog;
        for(const auto& c:catalog.data().cards)v.push_back(c.behavior);
        std::sort(v.begin(),v.end());v.erase(std::unique(v.begin(),v.end()),v.end());return v;
    }();return values;
}
inline double bounded(double x,double scale){return std::clamp(std::isfinite(x)?x/scale:0.,-10.,10.);}
inline NeuralFeatures neural_features(const AiPlannerInput& in,const AiPlannerMemory& m){
    const auto dx=[&](double x){return pvz::typed72::ai_wrap_delta(in.me.x,x,in.width);};
    NeuralFeatures f;
    f.global={in.side==Seat::plant?1.:0.,bounded(in.time,600.),in.time>=405.?1.:0.,bounded(in.width,4000.),in.recovering?1.:0.,
        bounded(in.me.hp,std::max(1.,in.me.max_hp)),bounded(in.foe.hp,std::max(1.,in.foe.max_hp)),
        bounded(in.me.resource,1000.),bounded(in.foe.resource,1000.),bounded(dx(in.foe.x),in.width/2.),bounded(in.foe.y-in.me.y,500.),
        m.mode=="siege"?1.:0.,bounded(in.time-m.last_pressure_at,100.),bounded(m.last_enemy_hp,40.),
        bounded(in.time-m.last_attack_at,100.),bounded(m.push_until-in.time,30.),bounded(double(m.peak_econ),10.),bounded(double(m.peak_graves),10.),
        bounded(in.me.max_hp,40.),bounded(in.foe.max_hp,40.)};
    for(const auto& u:in.units){
        if(!(u.hp>0.))continue;
        std::vector<double> r={bounded(dx(u.position.x),in.width/2.),bounded(u.position.y-in.me.y,500.),
            bounded(u.hp,std::max(1.,u.max_hp)),bounded(u.max_hp,100.),bounded(u.velocity.x,200.),bounded(u.velocity.y,200.),
            u.mobile?1.:0.,u.awake?1.:0.,u.grave?1.:0.,bounded(u.card_info.cost.value_or(25.),500.),
            bounded(u.card_info.range.value_or(0.),1000.),bounded(u.card_info.damage,100.),u.card_info.producer?1.:0.,u.card_info.mushroom?1.:0.,
            std::abs(dx(u.position.x))<350.&&std::abs(u.position.y-in.me.y)<200.?1.:0.,
            std::abs(dx(u.position.x))<500.&&std::abs(u.position.y-in.me.y)<250.?1.:0.};
        for(const auto& b:neural_behaviors())r.push_back(u.card_info.behavior==b?1.:0.);
        (u.side==in.side?f.own:f.enemy).push_back(std::move(r));
    }
    return f;
}
inline J features_json(const NeuralFeatures& f){return {{"global",f.global},{"own",f.own},{"enemy",f.enemy}};}

struct Dense {
    std::vector<std::vector<double>> w;std::vector<double> b;
    Dense()=default;
    Dense(const J& j,size_t inputs,size_t outputs){
        w=j.at("weight").get<decltype(w)>();b=j.at("bias").get<decltype(b)>();
        if(w.size()!=outputs||b.size()!=outputs)throw std::invalid_argument("model layer output dimension");
        for(const auto& row:w){if(row.size()!=inputs)throw std::invalid_argument("model layer input dimension");for(double v:row)if(!std::isfinite(v))throw std::invalid_argument("nonfinite model weight");}
        for(double v:b)if(!std::isfinite(v))throw std::invalid_argument("nonfinite model bias");
    }
    std::vector<double> operator()(const std::vector<double>& x,bool relu)const{
        auto y=b;for(size_t i=0;i<y.size();++i){for(size_t k=0;k<x.size();++k)y[i]+=w[i][k]*x[k];if(relu)y[i]=std::max(0.,y[i]);}return y;
    }
};
class NeuralModel {
    Dense unit,hidden,output;size_t embedding=0;
    std::vector<bool> enabled_heads;
public:
    explicit NeuralModel(const J& j){
        if(j.at("format")!="pvz-deepset-hybrid-1")throw std::invalid_argument("unknown neural model format");
        if(j.at("sim_fingerprint")!=AI_NN_SIM_FINGERPRINT)
            throw std::invalid_argument("neural model simulation source mismatch; use r22 or retrain");
        const pvz::typed72::ColdCatalog catalog;
        if(j.at("catalog_hash")!=catalog.data().catalog_hash||j.at("rules_hash")!=catalog.data().rules_hash)
            throw std::invalid_argument("neural model catalog/rules mismatch; use r22 or retrain");
        if(j.at("behaviors").get<std::vector<std::string>>()!=neural_behaviors())throw std::invalid_argument("neural model encoder mismatch");
        enabled_heads=j.at("enabled_heads").get<std::vector<bool>>();
        if(enabled_heads.size()!=4)throw std::invalid_argument("neural model head mask dimension");
        embedding=j.at("embedding");const size_t width=j.at("hidden");
        if(embedding<1||embedding>128||width<1||width>512)throw std::invalid_argument("neural model dimensions out of bounds");
        unit=Dense(j.at("unit"),16+neural_behaviors().size(),embedding);
        hidden=Dense(j.at("body"),20+4*embedding,width);output=Dense(j.at("heads"),width,27);
    }
    bool enabled(size_t h)const{return enabled_heads.at(h);}
    std::vector<double> logits(const NeuralFeatures& f)const{
        std::vector<double> x=f.global;
        for(const auto* group:{&f.own,&f.enemy}){
            std::vector<double> sum(embedding),maximum(embedding);
            for(const auto& row:*group){const auto h=unit(row,true);for(size_t i=0;i<embedding;++i){sum[i]+=h[i]/10.;maximum[i]=std::max(maximum[i],h[i]);}}
            x.insert(x.end(),sum.begin(),sum.end());x.insert(x.end(),maximum.begin(),maximum.end());
        }
        return output(hidden(x,true),false);
    }
    std::array<int,4> classes(const NeuralFeatures& f)const{
        const auto y=logits(f);std::array<int,4> result;const int offsets[]={0,11,13,24,27};
        for(int h=0;h<4;++h)result[h]=int(std::max_element(y.begin()+offsets[h],y.begin()+offsets[h+1])-(y.begin()+offsets[h]));
        return result;
    }
};
class NeuralPlanner final:public pvz::typed72app::IPlanner {
    pvz::typed72app::AiPlannerR22 base;std::shared_ptr<const NeuralModel> model;
public:
    NeuralPlanner(Seat s,std::shared_ptr<const NeuralModel> m):base(s),model(std::move(m)){}
    AiPlanR22 plan(const AiPlannerInput& in)override{
        const auto f=neural_features(in,base.memory());auto p=base.plan(in);const auto c=model->classes(f);
        if(in.side==Seat::plant){
            if(model->enabled(0))p.econ_goal=std::clamp(c[0],2,10);
            if(model->enabled(1))p.mode=c[1]?"siege":"defend";
            // Existing forced recovery behavior remains authoritative in this first candidate.
            if(in.recovering||in.me.hp<=10.)p.mode="defend";
            auto m=base.memory();m.mode=*p.mode;base.set_memory(m);
        }else{
            if(model->enabled(2))p.grave_start=p.grave_max=std::clamp(c[2],2,10);
            if(model->enabled(3))p.save=c[3]==2?std::nullopt:std::optional<bool>(c[3]==1);
        }
        return p;
    }
    Seat side()const override{return base.side();}
    const char* name()const override{return "nn-hybrid-v1";}
    AiPlannerMemory memory()const override{return base.memory();}
    void set_memory(const AiPlannerMemory& m)override{base.set_memory(m);}
};
} // namespace ainn
