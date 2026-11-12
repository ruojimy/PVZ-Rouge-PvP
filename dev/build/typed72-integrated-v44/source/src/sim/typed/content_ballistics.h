#pragma once
#include "sim/typed/ballistics.h"
namespace pvz::typed72 {
class ContentBallistics final : public BallisticComputePolicy {
public:
    explicit ContentBallistics(TypedBattleState& world):world_(world){}
    BallisticComputation compute(const NativeBallistics&,const EntityRef&,const BallisticTarget&,Point,double)const override;
    bool allows_reaim(const EntityRef&)const override;
private:
    TypedBattleState& world_;
};
} // namespace pvz::typed72
