#pragma once
#include "sim/typed/content_target.h"
#include "sim/typed/native_tracking.h"

namespace pvz::typed72 {
class SeaShroom {
public:
    SeaShroom(TypedBattleState& world,TargetIndexes& indexes,const TargetSight& map,ContentTargets& damage)
        :world_(world),indexes_(indexes),map_(map),damage_(damage){}
    ~SeaShroom(){restore();}
    SeaShroom(const SeaShroom&)=delete;
    void gate(const PlantRef&);
    void restore();
    void bubbles();
    bool active()const{return bool(saved_rows_);}
private:
    TypedBattleState& world_;
    TargetIndexes& indexes_;
    const TargetSight& map_;
    ContentTargets& damage_;
    std::shared_ptr<TargetBuckets> saved_rows_;
    std::optional<int> water_grave(const CombatTarget&,std::optional<Seat>)const;
};
} // namespace pvz::typed72
