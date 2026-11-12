#pragma once
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
#include <string>
#include <vector>
namespace pvz::typed72 {
struct ProjectileForm {std::string name;bool fire_lit=false;std::string zombie_fire;friend bool operator==(const ProjectileForm&,const ProjectileForm&)=default;};
struct ProjectileFlight {
    Field<Point> basket_last,last;
    Field<double> distance;
    Field<ProjectileForm> form;
    Field<std::shared_ptr<std::vector<std::string>>> torch_visits;
    Field<Point> torch_previous;
};
} // namespace pvz::typed72
