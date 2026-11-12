#include "sim/typed/content_ballistics.h"
namespace pvz::typed72 {
namespace {
bool pepper(const AttackSource& source){return source.content.present()&&!source.content.is_null()&&source.content.get()=="甜椒投手";}
}
BallisticComputation ContentBallistics::compute(const NativeBallistics& lower,const EntityRef& entity,
        const BallisticTarget& target,Point velocity,double speed)const {
    const auto source=world_.heroes.source();
    if(!pepper(entity->source)&&(!source||!pepper(*source)))return lower.compute_native(entity,target,velocity,speed);
    const auto& position=entity->motion.get();const Point origin{position.x,position.y};const double gravity=4.*world_.runtime.plk;
    auto solution=NativeBallistics::intercept(origin,target.point,velocity,speed,gravity,2000.,BallisticArc::high);
    if(!solution)solution=NativeBallistics::intercept(origin,target.point,{},speed,gravity,2000.,BallisticArc::high);
    return {solution,gravity};
}
bool ContentBallistics::allows_reaim(const EntityRef& entity)const{return !pepper(entity->source);}
} // namespace pvz::typed72
