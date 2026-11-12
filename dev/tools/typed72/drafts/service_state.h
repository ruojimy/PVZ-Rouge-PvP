#pragma once
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
#include "sim/typed/record_identity.h"
namespace pvz::typed72 {
struct SmartProjectile {
    Field<int64_t> target_index;
    Field<RecordId> target_id;
    Field<double> initial_speed,gravity,hit_time,lead_scale,created;
};
struct EntityServiceState {
    Field<SmartProjectile> smart;
    Field<bool> smart_skip,attract;
    Field<RecordId> reflected_by;
    Field<Point> attract_start,attract_end;
};
} // namespace pvz::typed72
