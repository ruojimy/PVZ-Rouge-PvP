#pragma once
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
#include <memory>
#include <string>
#include <vector>
namespace pvz::typed72 {
struct TerrainCell;
struct ContentPlant70State {
    Field<double> clock,head_clock,head_age,head_crushed;
    Field<std::string> parent,head_phase,head_target;
    Field<int> head_color;
    Field<bool> was_asleep,head_gone,basin_removed;
    Field<Point> head_aim,head_goal,head_start;
    Field<std::vector<std::string>> heads,head_hits;
    Field<std::shared_ptr<TerrainCell>> basin_terrain;
};
} // namespace pvz::typed72
