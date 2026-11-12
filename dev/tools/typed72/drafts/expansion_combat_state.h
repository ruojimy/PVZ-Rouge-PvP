#pragma once
#include "sim/typed/field.h"
#include <string>
namespace pvz::typed72 {
struct ExpansionCombatState {
    Field<std::string> black_armor;
    Field<double> before_vy,charge_until,charge_ready,charge_cd;
    Field<bool> charging;
    Field<double> paralysis_until,paralysis_started,paralysis_garlic;
};
// The admitted catalog supplies the frozen setup; runtime configure never
// reinterprets a generic record or consults a dynamic language backend.
struct ExpansionVariantSetup {
    std::string name,native_template,armor,riding;
    double hp=0.,armor_hp=0.,riding_hp=0.;
};
}
