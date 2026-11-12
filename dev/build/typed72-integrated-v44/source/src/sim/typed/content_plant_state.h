#pragma once
#include "sim/typed/field.h"
#include <string>
namespace pvz::typed72 {
struct ContentPlantState {
    Field<double> maximum_hp;
    Field<double> interval,before_shot,before_cd,vine_clock,lantern_timer;
    Field<bool> vine_produced,awake_forever;
    Field<std::string> hardening_form;
};
} // namespace pvz::typed72
