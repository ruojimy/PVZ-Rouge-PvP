#pragma once
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
#include <string>
namespace pvz::typed72 {
struct ColdPlantRegistrationState {
    Field<std::string> health_form;
    Field<double> armor_max,born;
};
struct ColdSecondhandEquipment {
    Field<bool> head,hand,carried_imp;
};
struct ColdZombieRegistrationState {
    Field<bool> temporary,floating,health72,coop_dormant,first_soldier_used;
    Field<bool> secret_pole,secret_crowd;
    Field<std::string> secret_hand;
    Field<ColdSecondhandEquipment> secondhand;
};
} // namespace pvz::typed72
