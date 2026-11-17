// Directed guard cases absent from the first self-play dataset. Synthetic
// weights force decisions here; they are fixtures, never delivery checkpoints.
#include "neural_planner.h"
#include "sim/typed72_app/cold_file.h"
#include <iostream>
int main(int argc,char** argv){
    try{
        using namespace ainn;using namespace pvz::typed72app;
        if(argc!=2)throw std::invalid_argument("neural_contract model.json");
        J j=J::parse(read_file_maybe_gz(argv[1]));
        j["residual"]=false;
        for(auto& row:j["heads"]["weight"])for(auto& value:row)value=0.;
        for(auto& value:j["heads"]["bias"])value=0.;
        j["heads"]["bias"][10]=100.; // economy 10
        j["heads"]["bias"][12]=100.; // siege
        j["heads"]["bias"][23]=100.; // grave 10
        j["heads"]["bias"][26]=100.; // save absent
        auto model=std::make_shared<NeuralModel>(j);
        AiPlannerInput in;in.width=2000.;in.time=200.;in.me={100.,100.,40.,40.,1000.};in.foe={1000.,100.,40.,40.,1000.};
        AiUnitView enemy;enemy.id="charmed-mobile-fixture";enemy.side=Seat::plant;enemy.position={150.,100.};
        enemy.hp=enemy.max_hp=20.;enemy.mobile=true;enemy.card_info.cost=500.;enemy.card_info.behavior="bite";
        std::vector<AiUnitView> units{enemy};in.units=units;in.side=Seat::zombie;
        NeuralPlanner z(Seat::zombie,model);const auto zp=z.plan(in);
        if(zp.save!=std::optional<bool>(false))throw std::runtime_error("untrained save head overrode r22 pressure handling");
        in.side=Seat::plant;in.recovering=true;
        NeuralPlanner p(Seat::plant,model);if(p.plan(in).mode!=std::optional<std::string>("defend"))throw std::runtime_error("recovery safety lost");
        in.recovering=false;in.me.hp=5.;if(p.plan(in).mode!=std::optional<std::string>("defend"))throw std::runtime_error("low-HP safety lost");
        j["enabled_heads"]={false,false,false,false};model=std::make_shared<NeuralModel>(j);
        size_t compared=0;
        for(const auto side:{Seat::plant,Seat::zombie}){
            AiPlannerR22 r22(side);NeuralPlanner masked(side,model);in.side=side;
            for(double t:{0.,60.,200.,450.}){
                in.time=t;in.me.hp=t<450.?40.:8.;
                if(plan_json(r22.plan(in))!=plan_json(masked.plan(in))||memory_json(r22.memory())!=memory_json(masked.memory()))
                    throw std::runtime_error("disabled neural heads changed r22 strategy or memory");
                ++compared;
            }
        }
        j["residual"]=true;j["enabled_heads"]={true,true,true,false};
        for(auto& value:j["heads"]["bias"])value=0.;
        j["heads"]["bias"][5]=100.;j["heads"]["bias"][11]=100.;j["heads"]["bias"][18]=100.;
        model=std::make_shared<NeuralModel>(j);
        units.assign(15,AiUnitView{});
        for(size_t i=0;i<units.size();++i){auto& u=units[i];u.id=std::to_string(i);u.side=Seat::plant;
            u.hp=u.max_hp=20.;u.position={100.,100.};u.card_info.cost=0.;
            u.card_info.producer=i<11;u.card_info.behavior=i<11?"sun":"shoot";}
        in.units=units;in.me.resource=100.;in.foe.resource=0.;in.me.hp=40.;in.recovering=false;
        size_t neutral_compared=0;bool goal11=false;
        for(const auto side:{Seat::plant,Seat::zombie}){
            AiPlannerR22 r22(side);NeuralPlanner neutral(side,model);in.side=side;
            for(double t:{200.,210.,450.}){
                in.time=t;const auto base=r22.plan(in),nn=neutral.plan(in);
                goal11|=side==Seat::plant&&base.econ_goal==11.;
                if(plan_json(base)!=plan_json(nn)||memory_json(r22.memory())!=memory_json(neutral.memory()))
                    throw std::runtime_error("neutral residual changed r22 plan or memory: "+J{{"base",plan_json(base)},{"nn",plan_json(nn)}}.dump());
                ++neutral_compared;
            }
        }
        if(!goal11)throw std::runtime_error("neutral fixture did not exercise economy goal 11");
        size_t correction_compared=0;
        for(const int delta:{-5,5}){
            for(auto& value:j["heads"]["bias"])value=0.;
            j["heads"]["bias"][5+delta]=100.;j["heads"]["bias"][12]=100.;j["heads"]["bias"][18+delta]=100.;
            model=std::make_shared<NeuralModel>(j);
            for(const auto side:{Seat::plant,Seat::zombie})for(int condition=0;condition<3;++condition){
                in.side=side;in.time=200.;in.recovering=condition==1;in.me.hp=condition==2?5.:40.;
                AiPlannerR22 r22(side);NeuralPlanner nn(side,model);auto expected=r22.plan(in);
                if(side==Seat::plant){
                    expected.econ_goal=std::clamp(int(expected.econ_goal)+delta,2,10);
                    expected.mode=expected.mode==std::optional<std::string>("siege")?"defend":"siege";
                    if(in.recovering||in.me.hp<=10.)expected.mode="defend";
                    auto memory=r22.memory();memory.mode=*expected.mode;r22.set_memory(memory);
                }else{
                    expected.grave_start=std::clamp(int(expected.grave_start)+delta,2,10);
                    expected.grave_max=std::max(expected.grave_max,expected.grave_start);
                }
                if(plan_json(nn.plan(in))!=plan_json(expected)||memory_json(nn.memory())!=memory_json(r22.memory()))
                    throw std::runtime_error("residual correction, mode flip, safety or grave cap contract changed");
                ++correction_compared;
            }
        }
        std::cout<<J{{"passed",true},{"masked_plan_memory_comparisons",compared},{"neutral_plan_memory_comparisons",neutral_compared},{"neutral_econ_goal_11_preserved",goal11},{"pressure_save_preserved",true},
            {"residual_correction_comparisons",correction_compared},{"recovery_preserved",true},{"low_hp_preserved",true}}.dump()<<'\n';return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
