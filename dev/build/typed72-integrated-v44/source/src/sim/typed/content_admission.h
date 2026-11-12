#pragma once
#include "sim/typed/cold_catalog.h"
#include "sim/typed/cart_lifecycle.h"
#include "sim/typed/content_plants70.h"
#include "sim/typed/content_zombies70.h"
#include "sim/typed/content_zombies64.h"
#include "sim/typed/content_zombies56.h"
#include "sim/typed/content_vines.h"
#include "sim/typed/scarecrow.h"
#include "sim/typed/mortar_plants.h"
#include "sim/typed/reed_plants.h"
#include "sim/typed/flying_plants.h"
#include "sim/typed/september_plants.h"
#include "sim/typed/native_barrels.h"
namespace pvz::typed72 {
struct ContentAdmissionSystems {
    CartLifecycle& carts;
    ContentPlants70& plants70;
    ContentZombies70& zombies70;
    MortarPlants& mortar;
    ContentZombies64& zombies64;
    SweetTaunts& sweet;
    ReedPlants& reeds;
    Scarecrows& scarecrows;
    ContentVines& vines;
    ContentZombies56& zombies56;
    FlyingPlants& flying;
    SeptemberPlants& september;
    NativeBarrels& barrels;
};
// Called after the native body and registration metadata are present. The
// actual resolved ColdCard is the one catalog record; no second card schema.
class ContentAdmission {
public:
    ContentAdmission(TypedBattleState& world,ContentAdmissionSystems systems,
        const std::vector<std::string>& black_variants)
        :world_(world),systems_(systems),black_variants_(black_variants){}
    void configure(const PlantRef&,const ColdCard&);
    void configure(const ZombieRef&,const ColdCard&);
    void configure(const NativeObject& object,const ColdCard& card){std::visit([&](const auto& unit){configure(unit,card);},object);}
private:
    TypedBattleState& world_;ContentAdmissionSystems systems_;const std::vector<std::string>& black_variants_;
    Field<double> template_speed(std::string_view);
};
} // namespace pvz::typed72
