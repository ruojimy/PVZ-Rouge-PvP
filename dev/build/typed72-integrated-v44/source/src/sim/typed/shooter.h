#pragma once
#include "sim/typed/targets.h"
namespace pvz::typed72 {
void shooter_attack(TypedBattleState&,size_t plant_index,ShooterKind,
                    const std::vector<int64_t>* row_targets,bool emperor,bool star_target);
} // namespace pvz::typed72
