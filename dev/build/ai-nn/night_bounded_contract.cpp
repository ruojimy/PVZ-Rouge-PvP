// Contract for a bounded, mode-preserving residual planner, including r22 goals above 11.
#include "neural_planner.h"
#include "sim/typed72_app/cold_file.h"
#include <iostream>
int main(int argc,char** argv){
    try{
        using namespace ainn;using namespace pvz::typed72app;
        if(argc!=2)throw std::invalid_argument("neural_contract bounded-model.json");
        const J original=J::parse(read_file_maybe_gz(argv[1]));
        NeuralModel actual(original);
        if(!actual.bounded_residual())throw std::runtime_error("bounded format required");
        size_t compared=0;bool above11=false,lower2=false;
        for(const auto side:{Seat::plant,Seat::zombie})for(int setting=0;setting<4;++setting)for(int cls:{0,4,5,6,10,11}){
            if(side==Seat::zombie&&cls==11)continue;
            J j=original;for(auto& row:j["heads"]["weight"])for(auto& v:row)v=0.;
            for(auto& v:j["heads"]["bias"])v=-1000.;
            j["heads"]["bias"][5]=0.;j["heads"]["bias"][12]=0.;j["heads"]["bias"][19]=0.;j["heads"]["bias"][26]=0.;
            const int offset=side==Seat::plant?0:14;j["heads"]["bias"][offset+5]=-1000.;j["heads"]["bias"][offset+cls]=1000.;
            AiPlannerInput in;in.side=side;in.width=2000.;in.time=setting==0?0.:200.;
            in.me={100.,100.,40.,40.,100.};in.foe={1000.,100.,40.,40.,0.};
            const int producers=setting==0?0:setting==1?11:17;const int fire=setting==0?0:8;
            std::vector<AiUnitView> units(producers+fire);
            for(size_t i=0;i<units.size();++i){auto& u=units[i];u.id=std::to_string(i);u.side=side;u.hp=u.max_hp=20.;
                u.position={100.,100.};u.card_info.cost=0.;u.card_info.producer=i<size_t(producers);u.card_info.behavior=u.card_info.producer?"sun":"shoot";}
            if(setting==0&&side==Seat::zombie){AiUnitView enemy;enemy.id="pressure";enemy.side=Seat::plant;enemy.hp=enemy.max_hp=20.;
                enemy.position={150.,100.};enemy.mobile=true;enemy.card_info.cost=500.;units.push_back(enemy);}
            if(setting==3){in.recovering=true;in.me.hp=5.;}
            in.units=units;AiPlannerR22 teacher(side);NeuralPlanner learner(side,std::make_shared<NeuralModel>(j));
            auto expected=teacher.plan(in);const auto baseline=expected;const int delta=std::clamp(cls-5,-1,1);
            if(side==Seat::plant){above11|=baseline.econ_goal>11.;expected.econ_goal=std::max(2.,baseline.econ_goal+delta);}
            else {lower2|=baseline.grave_start==2.;expected.grave_start=std::clamp(baseline.grave_start+delta,2.,10.);expected.grave_max=std::max(baseline.grave_max,expected.grave_start);}
            const auto got=learner.plan(in);
            if(plan_json(expected)!=plan_json(got)||memory_json(teacher.memory())!=memory_json(learner.memory()))
                throw std::runtime_error("bounded residual changed an unexpected plan field or memory");
            ++compared;
        }
        if(!above11||!lower2)throw std::runtime_error("range fixtures incomplete");
        size_t rejected=0;
        for(int kind=0;kind<3;++kind){J bad=original;if(kind==0)bad["residual"]=false;
            if(kind==1)bad["enabled_heads"]={true,true,true,false};if(kind==2)bad["enabled_heads"]={true,false,true,true};
            try{NeuralModel forbidden(bad);}catch(const std::invalid_argument&){++rejected;}}
        if(rejected!=3)throw std::runtime_error("bounded format accepted forbidden control heads");
        std::cout<<J{{"passed",true},{"plan_and_memory_cases",compared},{"economy_above_11",above11},{"grave_lower_bound",lower2},{"forbidden_forms_rejected",rejected}}.dump()<<'\n';return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
