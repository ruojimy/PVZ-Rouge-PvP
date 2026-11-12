#pragma once
#include "sim/typed/native_tracking.h"

namespace pvz::typed72 {
struct PlantAimTarget {
    size_t index;
    CombatTarget target;
    Point point;
};
// Selection keeps list-index tie breaking and repeated-object identities.
std::vector<std::optional<PlantAimTarget>> pick_tripea_targets(
    TypedBattleState&,NativeTracking&,const PlantRef&,double facing,std::span<const Point> centers);

class PeaHybrid {
public:
    PeaHybrid(TypedBattleState& world,NativeTracking& chart,TargetIndexes& indexes)
        :world_(world),chart_(chart),indexes_(indexes){}
    ~PeaHybrid(){restore();}
    PeaHybrid(const PeaHybrid&)=delete;
    void gate(const PlantRef&,bool enabled);
    void restore();
    void after_birth(const PlantRef& captured_source,size_t first_entity);
    bool active()const{return bool(saved_rows_);}
private:
    TypedBattleState& world_;
    NativeTracking& chart_;
    TargetIndexes& indexes_;
    std::shared_ptr<TargetBuckets> saved_rows_;
    std::optional<PlantAimTarget> target(const PlantRef&,Point,double facing);
    void aim(const PlantRef&);
};
} // namespace pvz::typed72
