#pragma once
#include "sim/typed/pve_director_state.h"
#include "sim/typed/cold_registration_state.h"
#include "sim/typed/expansion_clock_state.h"
#include "sim/typed/protection.h"
#include "sim/typed/flying_state.h"
#include "sim/typed/content_plant_state.h"
#include "sim/typed/content_plant70_state.h"
namespace pvz::typed72 {
#define PVZ72_PLANT_NUMBERS(X) \
 X(root_animation,"根动画") X(head_animation,"头动画") X(sun,"阳光") X(burst,"爆了") \
 X(grown,"长大") X(growth,"成长") X(eating,"吃") X(shooting,"射") X(shoot_cd,"射cd") \
 X(virtual_hp,"虚血") X(imitator_cd,"模仿cd") X(lamp,"路灯") X(buried,"埋藏") X(emerged,"出来") X(flash,"闪") \
 X(money_cd,"钱钱") X(money,"金钱") X(secondary_shot,"副射") X(secondary_cd,"副射cd") X(secondary_double,"副双发") \
 X(small_puff,"小喷") X(scared,"胆小") X(double_shot,"双发") X(gatling,"机枪") X(sleep,"睡觉") \
 X(expires,"消亡") X(grave_eating,"滚蛋") X(cannon_cd,"发射cd") X(cannon_animation,"发射动画") X(cannon_flash,"发射闪闪") X(cannon_column,"发射x") X(magnet,"吸")
struct CombatPlant {
    PvePlantState pve;
    ColdPlantRegistrationState registration;
    ExpansionClockState expansion_clock;
    BonusPlantState bonus;
    RecordId identity;
    AttackSource source;
    std::string& kind;
    Cell cell;
    double facing=1.;
    Field<double> hp,max_hp,hurt;
    Field<DeathMarker> dead,shovel_dead;
    Field<std::string> imitation;
    Field<std::string> copy_card;
    Field<std::string> grave_target;
    Field<double> pea_angle;
    Field<std::array<Field<double>,2>> split_pea_angles;
    Field<bool> one_shot,effect_done;
    Field<double> content_age,ghost_started,ghost_clock,ghost_pulse,last_fired,reed_clock,attack_clock;
    FlyingPlantState flying;
    ContentPlantState content_state;
    ContentPlant70State content70;
    Field<double> ash,ice,butter,stun;
    Field<Point> head_point;
    Field<bool> lantern_charm_healed;
    Field<DeathMarker> monochrome;
    Field<bool> crushed,secret_killed,temporary,transform_succeeded;
    Field<double> sun_due,rest_hp,rest_since,aura_factor;
#define NUM(n,k) Field<double> n;
    PVZ72_PLANT_NUMBERS(NUM)
#undef NUM
    UnitProtectionState protection;
    CombatPlant(std::string name,Cell cell,double facing):kind(initialize_name(source,std::move(name))),cell(cell),facing(facing){}
    CombatPlant(const CombatPlant&)=delete;
    CombatPlant& operator=(const CombatPlant&)=delete;
private:
    static std::string& initialize_name(AttackSource& s,std::string name){s.plant.set(std::move(name));return s.plant.get();}
};
using PlantRef=std::shared_ptr<CombatPlant>;
using PlantRoster=std::vector<PlantRef>;
inline std::shared_ptr<AttackSource> source_ref(const PlantRef& plant){return {plant,&plant->source};}
struct PlantCatalog {
    std::vector<std::string> plants,lobbers,night_plants,lottery_zombies;
};
struct PlantPlacementState {
    std::string imitation,day,sky;
    bool boss_battle=false;
};
} // namespace pvz::typed72
