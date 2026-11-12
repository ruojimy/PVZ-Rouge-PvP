#pragma once
#include "sim/typed/targets.h"
namespace pvz::typed72 {
enum class BallisticArc {low,high};
struct BallisticSolution {double time,vx,vy;};
struct BallisticTarget {int64_t index=-1;RecordId identity;Point point;double direction=1.;};
struct BallisticAim {std::optional<BallisticTarget> target;Point velocity;};
class NativeBallistics;
using BallisticComputation=std::pair<std::optional<BallisticSolution>,double>;
class BallisticComputePolicy {
public:
    virtual ~BallisticComputePolicy()=default;
    virtual BallisticComputation compute(const NativeBallistics&,const EntityRef&,const BallisticTarget&,Point,double)const=0;
    virtual bool allows_reaim(const EntityRef&)const=0;
};
class NativeBallistics {
public:
    explicit NativeBallistics(TypedBattleState& w):world_(w){}
    static std::optional<BallisticSolution> intercept(Point origin,Point target,Point velocity,double speed,double gravity,double max_time=95.,BallisticArc arc=BallisticArc::low);
    std::pair<std::optional<BallisticSolution>,double> compute(const EntityRef&,const BallisticTarget&,Point velocity,double speed)const;
    BallisticComputation compute_native(const EntityRef&,const BallisticTarget&,Point velocity,double speed)const;
    void bind_compute_policy(BallisticComputePolicy& policy){if(policy_&&policy_!=&policy)throw std::logic_error("ballistic compute policy already bound");policy_=&policy;}
    void require_compute_policy(bool required=true){policy_required_=required;}
    bool allows_reaim(const EntityRef& entity)const {
        if(policy_required_&&!policy_)throw std::logic_error("missing required content ballistic policy");
        return !policy_||policy_->allows_reaim(entity);
    }
    Point velocity(CombatTarget,double direction);
    BallisticAim pick(const EntityRef&,bool squash=false);
    BallisticAim current(const EntityRef&,int64_t index);
    BallisticAim squash_locked(const EntityRef&,const SquashLock&);
    RecordId identity(const CombatTarget&)const;
    const Motion& motion(const CombatTarget&)const;
    const ZombieRecordFields& body(const CombatTarget&)const;
private:
    TypedBattleState& world_;
    BallisticComputePolicy* policy_=nullptr;
    bool policy_required_=false;
};
} // namespace pvz::typed72
