#include "sim/typed/ballistics.h"
#include <cmath>
namespace pvz::typed72 {
namespace {
double number(const Field<double>& v,double fallback=0.){return v.present()&&!v.is_null()?v.get():fallback;}
double sign(double n){return n<0.?-1.:1.;}
}
std::optional<BallisticSolution> NativeBallistics::intercept(Point origin,Point target,Point velocity,
        double speed,double gravity,double max_time,BallisticArc arc) {
    const auto f=[&](double time) {
        const double x=target.x+velocity.x*time-origin.x;
        const double y=target.y+velocity.y*time-origin.y-.5*gravity*time*time;
        return x*x+y*y-speed*speed*time*time;
    };
    std::optional<BallisticSolution> result;
    double previous_time=.05,previous_value=f(previous_time);
    for(double time=.10;time<=max_time;time+=.5) {
        const double value=f(time);
        if(value==0. || previous_value==0. || value*previous_value<0.) {
            double low=previous_time,high=time;
            for(int iteration=0;iteration<32;++iteration) {
                const double middle=(low+high)*.5;
                if(f(low)*f(middle)<=0.)high=middle;
                else low=middle;
            }
            const double root=(low+high)*.5;
            // Disjoint intervals give ascending roots. Checking the last
            // accepted root preserves the source's 0.1 duplicate threshold.
            if(!result || std::abs(root-result->time)>=.1) {
                result=BallisticSolution{root,(target.x+velocity.x*root-origin.x)/root,
                    (target.y+velocity.y*root-origin.y-.5*gravity*root*root)/root};
                if(arc==BallisticArc::low)return result;
            }
        }
        previous_time=time;previous_value=value;
    }
    return result;
}
std::pair<std::optional<BallisticSolution>,double> NativeBallistics::compute(const EntityRef& e,const BallisticTarget& target,Point velocity,double speed)const {
    if(policy_required_&&!policy_)throw std::logic_error("missing required content ballistic policy");
    return policy_?policy_->compute(*this,e,target,velocity,speed):compute_native(e,target,velocity,speed);
}
BallisticComputation NativeBallistics::compute_native(const EntityRef& e,const BallisticTarget& target,Point velocity,double speed)const {
    const auto& p=e->motion.get();const double gravity=2.*world_.runtime.plk;
    auto solution=intercept({p.x,p.y},target.point,velocity,speed,gravity);
    if(!solution&&(std::abs(velocity.x)>.001||std::abs(velocity.y)>.001))solution=intercept({p.x,p.y},target.point,{},speed,gravity,130.);
    return {solution,gravity};
}
RecordId NativeBallistics::identity(const CombatTarget& t)const{return t.is_hero()?world_.heroes.cached_proxy(t.hero).identity:t.unit->identity;}
const Motion& NativeBallistics::motion(const CombatTarget& t)const{return t.is_hero()?*world_.heroes.cached_proxy(t.hero).position:t.unit->body.motion.get();}
const ZombieRecordFields& NativeBallistics::body(const CombatTarget& t)const{return t.is_hero()?static_cast<const ZombieRecordFields&>(world_.heroes.cached_proxy(t.hero)):static_cast<const ZombieRecordFields&>(t.unit->body);}
Point NativeBallistics::velocity(CombatTarget t,double direction) {
    const auto& p=motion(t);if(std::abs(p.vx)>.001||std::abs(p.vy)>.001)return {p.vx*.35,p.vy*.35};
    const auto& native=t.is_hero()?world_.heroes.cached_proxy(t.hero).native:t.unit->native;
    const double speed=number(native.move_speed);
    if(speed)return {body(t).facing*speed*.35,0.};
    auto& positions=world_.ballistics.positions;const auto key=identity(t).value;
    const auto found=positions.find(key);std::optional<BallisticObservation> old;if(found!=positions.end())old=found->second;
    positions[key]={{p.x,p.y},world_.native_time};
    if(old){const double dt=std::max(.001,world_.native_time-old->time);return {(p.x-old->point.x)/dt*.35,(p.y-old->point.y)/dt*.35};}
    return {-std::abs(speed)*std::abs(direction)*.35,0.};
}
BallisticAim NativeBallistics::pick(const EntityRef& e,bool squash) {
    const auto& p=e->motion.get();const double tile=world_.runtime.tile,direction=squash?sign(e->facing):e->facing;
    std::optional<double> best_score;std::optional<CombatTarget> best_unit;BallisticAim result;const auto roster=world_.targets;
    for(size_t i=0;i<roster->size();++i)try {
        const auto t=roster->at(i);if(body(t).hp<=0.)continue;const auto& z=motion(t);const double size=squash?std::max(.8,number(body(t).size,2.)):number(body(t).size,2.);
        const double ahead=(z.x-p.x)*direction,lane=std::abs(z.y-p.y);
        if(squash?(ahead<-tile*.10||ahead>tile*2.35||lane>tile*std::max(.90,.38*size)):(ahead<-tile*1.5))continue;
        const double score=squash?std::max(0.,ahead)+lane*3.:lane*2.5+std::max(0.,ahead)*.12;
        if(!best_score||score<*best_score){best_score=score;best_unit=t;result.target=BallisticTarget{int64_t(i),identity(t),{z.x,z.y-tile*(squash?.12:.35)*size},direction};}
    }catch(const std::exception&){}
    if(best_unit)result.velocity=velocity(*best_unit,direction);return result;
}
BallisticAim NativeBallistics::current(const EntityRef& e,int64_t index) {
    if(index<0||uint64_t(index)>=world_.targets->size())return {};
    try{const auto t=world_.targets->at(size_t(index));const auto& p=motion(t);return {BallisticTarget{index,identity(t),{p.x,p.y-world_.runtime.tile*.35*number(body(t).size,2.)},e->facing},velocity(t,e->facing)};}catch(const std::exception&){return {};}
}
BallisticAim NativeBallistics::squash_locked(const EntityRef& e,const SquashLock& lock) {
    const auto index=lock.target_index.present()&&!lock.target_index.is_null()?lock.target_index.get():-1;
    if(index<0||uint64_t(index)>=world_.targets->size())return {};
    try{const auto t=world_.targets->at(size_t(index));if(lock.target_id.present()&&!lock.target_id.is_null()&&identity(t)!=lock.target_id.get())return {};
        if(body(t).hp<=0.)return {};const auto& p=motion(t);const double direction=sign(e->facing),size=std::max(.8,number(body(t).size,2.));
        return {BallisticTarget{index,identity(t),{p.x,p.y-world_.runtime.tile*.12*size},direction},velocity(t,direction)};
    }catch(const std::exception&){return {};}
}
} // namespace pvz::typed72
