#pragma once
#include "sim/typed/native_tracking.h"

namespace pvz::typed72 {
bool plant_needs_support(const TypedBattleState&,size_t,std::span<const std::string> air,
                         std::span<const std::string> flying);
bool plant_edible_target(const TypedBattleState&,size_t);
bool plant_wind_target(const Entity&,std::span<const std::string> damaging);
std::span<const int64_t> plant_pitcher_columns(const CombatPlant&);
bool plant_star_target(TypedBattleState&,NativeTracking&,size_t plant_index);
} // namespace pvz::typed72
