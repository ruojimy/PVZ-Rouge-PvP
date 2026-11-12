#pragma once
#include "sim/typed/field.h"
#include <memory>
#include <vector>
namespace pvz::typed72 {
struct Entity;
struct ZombiePeaState {
    Field<double> x,y,previous_x,previous_y,vx,vy,age;
    Field<bool> zombie_pea,native_move,charmed_pea;
};
struct ZombiePeaWorld {
    // The shipped patch's separately retained legacy shots have the same
    // entity schema; these are references, not a second projectile format.
    std::shared_ptr<std::vector<std::shared_ptr<Entity>>> legacy=std::make_shared<std::vector<std::shared_ptr<Entity>>>();
    bool pvp_active=true,secret_system_enabled=false,shotgun=false;
};
} // namespace pvz::typed72
