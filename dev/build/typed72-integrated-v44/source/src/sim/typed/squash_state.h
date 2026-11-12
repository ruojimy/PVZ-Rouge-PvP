#pragma once
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
#include "sim/typed/record_identity.h"
#include <string>
#include <unordered_map>
namespace pvz::typed72 {
struct SquashTargetRecord {
    Field<std::string> kind;
    Field<int64_t> index;
    Field<RecordId> identity;
    Field<Point> point;
    Field<double> direction;
};
struct SquashLock {
    Field<int64_t> target_index;
    Field<RecordId> target_id;
    Field<double> initial_speed,gravity,hit_time,direction,ahead_tiles,created;
    Field<bool> late_armed;
    bool empty()const{return !target_index.present()&&!target_id.present()&&!initial_speed.present()&&!gravity.present()&&!hit_time.present()&&!direction.present()&&!ahead_tiles.present()&&!created.present()&&!late_armed.present();}
};
struct SquashState {
    Field<SquashLock> lock;
    Field<SquashTargetRecord> target;
    Field<bool> zombie_entity,friendly,hit;
    Field<double> age,big_sit,sit,bounce_x;
};
struct BallisticObservation {Point point;double time=0.;};
struct BallisticHistory {std::unordered_map<uint64_t,BallisticObservation> positions;};
} // namespace pvz::typed72
