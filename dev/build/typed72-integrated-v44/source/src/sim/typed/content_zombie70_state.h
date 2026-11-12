#pragma once
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
namespace pvz::typed72 {
struct ContentZombie70State {
    Field<double> clock;
    Field<bool> reaper_idle,airdrop_used,bone_grave;
    Field<Point> hook_pull;
};
} // namespace pvz::typed72
