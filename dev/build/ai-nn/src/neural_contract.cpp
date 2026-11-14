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
        std::cout<<J{{"passed",true},{"masked_plan_memory_comparisons",compared},{"pressure_save_preserved",true},
            {"recovery_preserved",true},{"low_hp_preserved",true}}.dump()<<'\n';return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
