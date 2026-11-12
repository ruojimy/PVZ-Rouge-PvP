#pragma once
#include "sim/typed/native_tracking.h"
#include "sim/typed/entity_region.h"

namespace pvz::typed72 {
struct HeroInput {
    int move=0;
    bool jump_held=false,jump_down=false;
};
class HeroPhysics {
public:
    HeroPhysics(TypedBattleState& world,TargetIndexes& indexes,PlantLifecycle& plants,
                NativeEntityConstructor& births,EntityRenderer& renderer)
        :world_(world),indexes_(indexes),plants_(plants),births_(births),renderer_(renderer){}
    HeroFrame make_state(Point,std::string mode,double hp,std::vector<std::string> secrets)const;
    void step(HeroState&,HeroInput,int jump_cap=2,int balloon_hp=10);
    void effects(HeroState&,bool tail_enabled);
private:
    TypedBattleState& world_;
    TargetIndexes& indexes_;
    PlantLifecycle& plants_;
    NativeEntityConstructor& births_;
    EntityRenderer& renderer_;
    void environment(HeroFrame&,HeroInput,double);
    void recover(HeroFrame&,int);
    void tail(HeroFrame&);
};
} // namespace pvz::typed72
