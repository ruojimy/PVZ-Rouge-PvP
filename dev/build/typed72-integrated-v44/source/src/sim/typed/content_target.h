#pragma once
#include "sim/typed/targets.h"
namespace pvz::typed72 {
struct CollisionCatalog;
// NativeContent can address stationary plants as well as entries in the
// zombie/hero roster. A plant is never inserted into that other roster.
using ContentTarget=std::variant<PlantRef,CombatTarget>;
class ContentUnitDamage {
public:
    virtual ~ContentUnitDamage()=default;
    virtual void ordinary(size_t index,double facing,double amount)=0;
    virtual void surface(size_t index,double facing,double amount)=0;
};
class ContentTargets {
public:
    ContentTargets(TypedBattleState& world,TargetDamage& damage,const CollisionCatalog& catalog,double width)
        :world_(world),damage_(&damage),catalog_(catalog),width_(width){}
    ContentTargets(TypedBattleState& world,ContentUnitDamage& dispatch,const CollisionCatalog& catalog,double width)
        :world_(world),dispatch_(&dispatch),catalog_(catalog),width_(width){}
    Point point(const ContentTarget&)const;
    bool contact(const ContentTarget&,Point start,Point delta)const;
    void damage(const std::shared_ptr<AttackSource>& source,const ContentTarget&,double amount,
                double facing=1.,bool surface=false,HeroHit kind=HeroHit::content);
private:
    TypedBattleState& world_;
    TargetDamage* damage_=nullptr;
    ContentUnitDamage* dispatch_=nullptr;
    const CollisionCatalog& catalog_;
    double width_;
    std::optional<Seat> owner(const ContentTarget&)const;
};
} // namespace pvz::typed72
