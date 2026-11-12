#pragma once
#include "sim/typed/targets.h"
namespace pvz::typed72 {
enum class BallisticArc {low,high};
struct BallisticSolution {double time,vx,vy;};
struct BallisticTarget {int64_t index=-1;RecordId identity;Point point;double direction=1.;};
struct BallisticAim {std::optional<BallisticTarget> target;Point velocity;};
class NativeBallistics {
public:
    explicit NativeBallistics(TypedBattleState& w):world_(w){}
    static std::optional<BallisticSolution> intercept(Point origin,Point target,Point velocity,double speed,double gravity,double max_time=95.,BallisticArc arc=BallisticArc::low);
    std::pair<std::optional<BallisticSolution>,double> compute(const EntityRef&,const BallisticTarget&,Point velocity,double speed)const;
    Point velocity(CombatTarget,double direction);
    BallisticAim pick(const EntityRef&,bool squash=false);
    BallisticAim current(const EntityRef&,int64_t index);
    BallisticAim squash_locked(const EntityRef&,const SquashLock&);
    RecordId identity(const CombatTarget&)const;
    const Motion& motion(const CombatTarget&)const;
    const ZombieRecordFields& body(const CombatTarget&)const;
private:
    TypedBattleState& world_;
};
} // namespace pvz::typed72
