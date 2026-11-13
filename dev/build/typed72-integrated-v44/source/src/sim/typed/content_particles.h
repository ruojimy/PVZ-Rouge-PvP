#pragma once
#include "sim/typed/targets.h"
#include "sim/typed/particle_dispatch.h"
namespace pvz::typed72 {
class ContentParticles final : public NativeParticleDispatch {
public:
    explicit ContentParticles(TypedBattleState& world):world_(world){}
    std::function<void(const std::string&,Point)> observe;
    void emit(CombatRuntime&,const std::string&,Point,int,std::optional<int>)override;
private:
    TypedBattleState& world_;
};
} // namespace pvz::typed72
